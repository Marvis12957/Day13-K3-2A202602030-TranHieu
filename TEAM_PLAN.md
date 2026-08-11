# Kế hoạch phân công chi tiết — Day 13 Observability (K3)

> Nguồn: Codelabs Lab 13 (8 bước) + docs trong repo. Điều phối & kiểm tra: **Trung Hiếu**.
> Luồng điều tra luôn: **Metrics → Traces → Logs**.

## ⏱ Timeline 4 giờ (theo Codelabs)

| Mốc | Thời gian | Checkpoint | Người |
|---|---|---|---|
| CP0 Setup & Baseline | 0:00–0:30 | log ≥10 records, pytest pass | Cả nhóm |
| CP1 Logging, Correlation ID & PII | 0:30–1:30 | `validate_logs.py` ≥ 80/100 | Tuấn + Trần Hiếu |
| CP2 Metrics, Traces, Dashboard & Alerts | 1:30–2:30 | ≥10 traces, 6 panel, SLO, alert | Thái Đức + Trung Hiếu |
| CP3 Challenge Investigation | 2:30–3:30 | root cause + evidence 3 lớp | Trung Hiếu (chủ trì) |
| Báo cáo & Nộp bài | 3:30–4:00 | REPORT.md, pytest, git | Cả nhóm |

## Phụ thuộc

```
CP1 (Tuấn + Trần Hiếu song song) → CP2 (Thái Đức: traces/SLO/alert; Trung Hiếu: dashboard) → CP3 (Trung Hiếu, Thái Đức hỗ trợ)
```

- A và B làm xong → báo Trung Hiếu chạy load test để có log thật.
- Trước khi test: **xóa log cũ** `Remove-Item data/logs.jsonl` rồi restart uvicorn.

---

# Vai A — Tuấn (Logging & Middleware) — CP1

**File:** `app/middleware.py`, `app/main.py`

## 1. `app/middleware.py` — hoàn thành 4 TODO (code mẫu từ Codelabs)
```python
async def dispatch(self, request: Request, call_next):
    # 1. Xóa context cũ tránh leak giữa request
    clear_contextvars()
    # 2. Lấy từ header hoặc tạo mới, format req-<8 hex>
    correlation_id = request.headers.get("x-request-id", f"req-{uuid.uuid4().hex[:8]}")
    # 3. Bind vào structlog context — mọi log sau tự có trường này
    bind_contextvars(correlation_id=correlation_id)
    request.state.correlation_id = correlation_id

    start = time.perf_counter()
    response = await call_next(request)

    # 4. Trả correlation ID + thời gian xử lý trong response header
    response.headers["x-request-id"] = correlation_id
    response.headers["x-response-time-ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"
    return response
```

## 2. `app/main.py` — enrich log context (bind TRƯỚC `request_received`)
```python
@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    bind_contextvars(
        user_id_hash=hash_user_id(body.user_id),   # KHÔNG log user_id thô
        session_id=body.session_id,
        feature=body.feature,
        model="claude-sonnet-4-5",
        env=os.getenv("APP_ENV", "dev"),
    )
    log.info("request_received", service="api", payload={"message_preview": summarize_text(body.message)})
    ...
```

## 3. (Phần mở rộng + tiến độ) Giữ correlation ID khi lỗi 500
- `app/main.py`: thêm generic exception handler đính `x-request-id` vào response lỗi.
- `scripts/load_test.py` (dòng ~21): đọc ID từ header trước:
  `cid = r.headers.get("x-request-id") or r.json().get("correlation_id", "None")`

## ✅ Tự kiểm tra (Vai A)
```bash
Remove-Item data/logs.jsonl -ErrorAction SilentlyContinue
# Terminal 1: uvicorn app.main:app --reload --env-file .env
# Terminal 2:
python scripts/load_test.py --concurrency 5
python scripts/validate_logs.py      # Correlation ID propagation PASS + Enrichment PASS
```
- `correlation_id` không còn `"MISSING"`, format `req-<8hex>`.
- Log `request_received` có `user_id_hash`, `session_id`, `feature`, `model`, `env`.

## 📸 Evidence bàn giao
- Log JSON có `correlation_id` (từ `data/logs.jsonl`).
- Ảnh response header `x-request-id`.

---

# Vai B — Trần Hiếu (Security & Compliance) — CP1

**File:** `app/logging_config.py`, `app/pii.py`

## 1. `app/logging_config.py` — bật PII scrubber
- **Uncomment `scrub_event`** trong `processors`.
- **Thứ tự bắt buộc:** SAU `TimeStamper`, TRƯỚC `JsonlFileProcessor` + `JSONRenderer` (scrub trước khi ghi/console).

## 2. Nâng cấp scrub TOÀN BỘ trường (không chỉ payload/event)
Thay hàm `scrub_event` bằng bản quét mọi string/dict:
```python
def scrub_event(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key, val in event_dict.items():
        if isinstance(val, str):
            event_dict[key] = scrub_text(val)
        elif isinstance(val, dict):
            event_dict[key] = {k: scrub_text(v) if isinstance(v, str) else v for k, v in val.items()}
    return event_dict
```

## 3. `app/pii.py` — thêm patterns
```python
PII_PATTERNS = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone_vn": r"(?:\+84|0)[ \.-]?\d{3}[ \.-]?\d{3}[ \.-]?\d{3,4}",
    "cccd": r"\b\d{12}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "passport": r"\b[A-Z]\d{7,8}\b",                       # mới
    "address_vn": r"\b(?:số nhà|đường|phường|quận|huyện|tỉnh|thành phố)\b",  # mới
}
```

## ✅ Tự kiểm tra (Vai B)
```bash
python scripts/validate_logs.py      # PII scrubbing PASS (0 leaks)
grep -i "@" data/logs.jsonl          # KHÔNG có kết quả
grep "4111" data/logs.jsonl          # KHÔNG có kết quả
grep "REDACTED" data/logs.jsonl      # PHẢI có kết quả
```
- Email `student@vinuni.edu.vn`, phone `0987654321`, thẻ `4111 1111 1111 1111` phải thành `[REDACTED_...]`.

## 📸 Evidence bàn giao
- Log chứng minh `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CREDIT_CARD]`; không có raw PII.

---

# Vai C — Thái Đức (Metrics & Alerting) — CP1 + CP2

**File:** `app/metrics.py`, `app/agent.py`, `config/slo.yaml`, `config/alert_rules.yaml`, `docs/alerts.md` + Langfuse

## 1. `app/metrics.py` — thêm `error_rate_pct` (tính trong `snapshot()`)
```python
total_errors = sum(ERRORS.values())
total_requests = TRAFFIC + total_errors
error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0.0
# trong dict trả về thêm:
"error_rate_pct": round(error_rate, 2),
```

## 2. `app/agent.py` — đính `correlation_id` vào Langfuse trace
```python
from structlog.contextvars import get_contextvars
langfuse_client.update_current_trace(
    user_id=hash_user_id(user_id),
    session_id=session_id,
    tags=["lab", feature, self.model],
    metadata={"correlation_id": get_contextvars().get("correlation_id", "MISSING")},
)
```

## 3. CP2 — Traces trên Langfuse
- Chạy `python scripts/load_test.py` → tạo **≥10 traces**.
- Mở `https://cloud.langfuse.com` → kiểm tra Trace ID, User ID (hash), Session ID, Tags, Waterfall.
- **(Mở rộng, nên làm)** sub-component trace cho waterfall rõ hơn:
  - `app/mock_rag.py`: `@observe(as_type="span")` lên `retrieve`
  - `app/mock_llm.py`: `@observe(as_type="span")` lên `FakeLLM.generate`
- **Prompt versioning** (theo `docs/PROMPT_VERSIONING.md`): tạo prompt `day13-chat` v1 (labels `baseline`+`production`) và v2 (label `candidate`); chạy cùng input với 2 label; trace phải ghi `prompt_name/label/version/source`.

## 4. CP2 — SLO & Alerts
- `config/slo.yaml`: giữ mục tiêu mặc định (P95≤3000/99.5%, error≤2%/99%, cost≤$2.5, quality≥0.75).
- `config/alert_rules.yaml`: điền 3 alert (symptom-based, KHÔNG dùng tên implementation):
  ```yaml
  - name: high_latency_p95      severity: warning  condition: "latency_p95 > 3000ms for 5 minutes"      owner: on-call-engineer  runbook: docs/alerts.md#alert-1
  - name: elevated_error_rate   severity: critical condition: "error_rate_pct > 5 for 3 minutes"        owner: on-call-engineer  runbook: docs/alerts.md#alert-2
  - name: cost_budget_exceeded  severity: warning  condition: "daily_cost_usd > 2.5"                     owner: team-lead         runbook: docs/alerts.md#alert-3
  ```
- `docs/alerts.md`: viết 3 runbook (tên, severity, SLI/SLO, điều kiện, ảnh hưởng user, **3 bước kiểm tra đầu tiên**, mitigation, owner).

## ✅ Tự kiểm tra (Vai C)
- `curl http://localhost:8000/metrics | python -m json.tool` thấy `error_rate_pct`.
- Langfuse có ≥10 traces + trace có `correlation_id`, `prompt_*`.
- `python scripts/validate_dashboard.py` vẫn `HỢP LỆ: 6/6`.

## 📸 Evidence bàn giao
- Ảnh danh sách ≥10 traces + 1 waterfall.
- 2 trace ID 2 prompt version + ảnh rollback.
- `config/alert_rules.yaml` + `docs/alerts.md` hoàn thiện.

---

# Vai D — Trung Hiếu (QA & Incident Analyst) — CP2/CP3 + Điều phối

**File:** `docs/dashboard-spec.md`, `submission/REPORT.md`, `submission/evidence/` + chạy test

## 1. CP2 — Dashboard 6 nhóm chỉ số
- Nguồn: `/metrics` endpoint + `data/logs.jsonl` (contract `config/dashboard.yaml`).
- 6 panel: **Latency** (P50/P95/P99) · **Traffic** · **Error** (error_rate_pct + breakdown) · **Cost** (total/avg) · **Tokens** (in/out) · **Quality** (avg).
- Ghi vào `docs/dashboard-spec.md`: tên panel, đơn vị, time range mặc định, threshold/SLO line, công cụ.
- `python scripts/validate_dashboard.py` → `HỢP LỆ: 6/6`.

## 2. Sinh dữ liệu & Baseline
- Sau khi CP1 xong: `python scripts/load_test.py --concurrency 5` → có log thật + traces.
- Lưu baseline `validate_logs.py` vào mục 2 `REPORT.md`.

## 3. CP3 — Điều tra Challenge (file đã release: `day13-k3-observability-v1`, incident `rag_slow`)
```bash
python -c "from app.challenge import load_challenge; print('Hợp lệ:', load_challenge().challenge_id)"
python scripts/inject_incident.py
python scripts/load_test.py --challenge --concurrency 5
```
- **Metrics**: `curl http://localhost:8000/metrics | python -m json.tool` → P95 vượt ngưỡng = triệu chứng.
- **Traces**: mở Langfuse, lọc trace trong khoảng bất thường → span `run` chậm (hoặc span `retrieve` nếu đã làm sub-component). Lấy Trace ID.
- **Logs**: lọc log cùng correlation ID:
  ```bash
  python -c "import json; [print(json.dumps(r, indent=2)) for r in (json.loads(l) for l in open('data/logs.jsonl')) if r.get('correlation_id')=='req-<8hex>']"
  ```
- Kết luận: Triệu chứng → Vị trí → Root cause → Fix action → Preventive measure.
- Nếu không có challenge: ghi `"Practice scenario: rag_slow"` vào mục Challenge ID.

## 4. Báo cáo & Nộp bài
- Điền đầy đủ `submission/REPORT.md` (thông tin nhóm, kết quả kỹ thuật, logging/tracing, dashboard/SLO/alert, challenge, đóng góp cá nhân kèm commit).
- Evidence vào `submission/evidence/` (danh sách trace, waterfall, PII, dashboard, challenge).
- Check cuối:
  ```bash
  python -m pytest -q
  python scripts/validate_logs.py
  git status --short
  ```
- KHÔNG commit `.env`, `.venv/`, log PII, `config/challenge.json` đã sửa.
- Commit + push, nộp URL repo + commit SHA lên Codelabs.

## 📸 Evidence bàn giao
- Ảnh dashboard 6 panel + `validate_dashboard.py` 6/6.
- Metrics screenshot, trace ID, log line của challenge.
- `submission/REPORT.md` hoàn chỉnh.

---

# Bonus (+10, nếu còn thời gian — sau khi xong CP3)
- **Cost optimization**: bật `cost_spike`, đo `total_cost_usd` before → đề xuất (giới hạn output tokens, cache) → after. Ảnh before/after.
- **Audit log**: ghi `data/audit.jsonl` (đường dẫn đã có `AUDIT_LOG_PATH`) cho incident enable/disable, config change.
- **Automation**: script tự phát hiện anomaly/PII leak từ `data/logs.jsonl`.

# Checklist chung trước khi nộp
- [ ] `validate_logs.py` ≥ 80/100 (đích 100/100) — Tuấn + Trần Hiếu
- [ ] ≥10 traces + waterfall + prompt v1/v2 + rollback — Thái Đức + Trung Hiếu
- [ ] `validate_dashboard.py` = 6/6 + ảnh dashboard — Trung Hiếu
- [ ] SLO + alert_rules + runbook — Thái Đức
- [ ] Challenge: metrics→traces→logs→root cause — Trung Hiếu
- [ ] `pytest -q` pass, `REPORT.md` + evidence đầy đủ — cả nhóm