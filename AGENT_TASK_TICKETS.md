# Ticket giao việc cho Agent Coding — Day 13 Observability

> Cách dùng: mỗi thành viên copy **nguyên khối ticket** của mình (từ `## TICKET...` đến `⚠️ Cấm`) dán vào agent coding.
> Sau khi agent xong: chạy phần «✅ Kiểm tra» rồi báo Trung Hiếu để chạy load test chung.
> Nguyên tắc chung (mọi ticket): **KHÔNG hard-code** để qua validator, không tự tạo/sửa `config/challenge.json`, không commit `.env`/secret.
> 🎓 **BẮT BUỘC với mọi thành viên (điểm B1+B2 = 40đ):** sau khi agent xong, bạn PHẢI tự commit phần việc của mình (message ghi rõ tên + ticket, ví dụ `Tuấn: feat CP1 correlation id middleware`) và tự điền dòng của mình vào bảng «Đóng góp cá nhân» trong `submission/REPORT.md` kèm link commit — giám khảo sẽ đối chiếu với Git. Không commit thay cho người khác.

---

# 🧑💻 TUẤN — Vai A (Logging & Middleware)

## TICKET A1 — Correlation ID Middleware
**File:** `app/middleware.py`

Nhiệm vụ: hoàn thành 4 TODO trong `CorrelationIdMiddleware.dispatch()`:
1. `clear_contextvars()` đầu mỗi request (tránh rò rỉ context giữa các request).
2. Lấy correlation ID từ header `x-request-id`, nếu không có thì sinh mới dạng `req-<8-ký-tự-hex>`:
   `correlation_id = request.headers.get("x-request-id", f"req-{uuid.uuid4().hex[:8]}")`
3. `bind_contextvars(correlation_id=correlation_id)` và gán `request.state.correlation_id = correlation_id`.
4. Sau `call_next`: thêm response header `x-request-id` và `x-response-time-ms` (ms, 1 số lẻ).

Giữ nguyên cấu trúc class; `time` và `uuid` đã được import sẵn.

✅ Kiểm tra: chạy API + load test, log `request_received` có `correlation_id` dạng `req-<8hex>` (không còn `"MISSING"`); response có header `x-request-id`.
⚠️ Cấm: đặt correlation_id cứng / dùng lại ID cũ / không `clear_contextvars`.

## TICKET A2 — Enrich Log Context + Giữ ID khi lỗi 500
**File:** `app/main.py`, `scripts/load_test.py`

Phần 1 — `app/main.py`, hàm `chat()`: bind metadata **TRƯỚC** dòng `log.info("request_received", ...)`:
```python
bind_contextvars(
    user_id_hash=hash_user_id(body.user_id),   # hash, KHÔNG log user_id thô
    session_id=body.session_id,
    feature=body.feature,
    model="claude-sonnet-4-5",
    env=os.getenv("APP_ENV", "dev"),
)
```
Phần 2 (mở rộng, nên làm) — giữ `x-request-id` khi API trả lỗi 500:
- Thêm generic exception handler trong `app/main.py` đính header `x-request-id` (lấy từ `request.state.correlation_id`) vào `JSONResponse` 500.
- Sửa `scripts/load_test.py` (dòng ~21) để ưu tiên đọc ID từ header:
  `cid = r.headers.get("x-request-id") or r.json().get("correlation_id", "None")`

✅ Kiểm tra: log `request_received` có `user_id_hash`, `session_id`, `feature`, `model`, `env`; `validate_logs.py` PASS mục **Log enrichment**.
⚠️ Cấm: log `user_id` nguyên văn; ghi metadata sau dòng `request_received`.

---

# 🧑💻 TRẦN HIẾU — Vai B (Security & Compliance)

## TICKET B1 — Bật PII Scrubbing toàn bộ
**File:** `app/logging_config.py`

Nhiệm vụ:
1. Trong `configure_logging()`, **uncomment `scrub_event`** trong danh sách `processors` — vị trí hiện tại (sau `TimeStamper`, trước `StackInfoRenderer`/`JsonlFileProcessor`) là đúng, giữ nguyên.
2. Nâng cấp hàm `scrub_event` để quét **MỌI trường string/dict** (không chỉ `payload`/`event`):
```python
def scrub_event(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key, val in event_dict.items():
        if isinstance(val, str):
            event_dict[key] = scrub_text(val)
        elif isinstance(val, dict):
            event_dict[key] = {k: scrub_text(v) if isinstance(v, str) else v for k, v in val.items()}
    return event_dict
```
LƯU Ý THỨ TỰ: scrub phải chạy SAU `TimeStamper` (không scrub timestamp) và TRƯỚC `JsonlFileProcessor` + `JSONRenderer` (PII che trước khi ghi file/console).

✅ Kiểm tra: `grep -i "@" data/logs.jsonl` và `grep "4111" data/logs.jsonl` → không có kết quả; `grep "REDACTED" data/logs.jsonl` → có kết quả.
⚠️ Cấm: để scrub chạy sau khi JSON đã render; đổi thứ tự processor.

## TICKET B2 — Thêm PII Patterns + Kiểm chứng
**File:** `app/pii.py`

Nhiệm vụ: thêm vào `PII_PATTERNS`:
```python
"passport": r"\b[A-Z]\d{7,8}\b",
"address_vn": r"\b(?:số nhà|đường|phường|quận|huyện|tỉnh|thành phố)\b",
```
Đảm bảo `scrub_text`/`summarize_text` xử lý đúng. Sau đó chạy API + load test và kiểm tra 3 mẫu PII trong `data/sample_queries.jsonl` (`student@vinuni.edu.vn`, `0987654321`, `4111 1111 1111 1111`) đều thành `[REDACTED_...]`.

✅ Kiểm tra: `python scripts/validate_logs.py` → **PII scrubbing PASS (0 leaks)**; grep các mẫu PII trong `data/logs.jsonl` → không có kết quả.
⚠️ Cấm: xóa pattern có sẵn; dùng regex quá rộng làm hỏng log hợp lệ (test thử).

---

# 🧑💻 THÁI ĐỨC — Vai C (Metrics & Alerting)

## TICKET C1 — Error Rate trong Metrics
**File:** `app/metrics.py`

Nhiệm vụ: trong `snapshot()`, tính và thêm `error_rate_pct`:
```python
total_errors = sum(ERRORS.values())
total_requests = TRAFFIC + total_errors
error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0.0
# trong dict trả về (cạnh error_breakdown):
"error_rate_pct": round(error_rate, 2),
```
✅ Kiểm tra: `curl http://localhost:8000/metrics` trả về `error_rate_pct` (0.0 khi chưa có lỗi).
⚠️ Cấm: chia cho 0 (phải guard `total_requests > 0`).

## TICKET C2 — Gắn Correlation ID vào Trace + Xác minh Langfuse
**File:** `app/agent.py`

Nhiệm vụ:
1. Import `from structlog.contextvars import get_contextvars`.
2. Trong `run()`, khi gọi `langfuse_client.update_current_trace(...)`, thêm vào `metadata`:
   `"correlation_id": get_contextvars().get("correlation_id", "MISSING")`
3. Chạy `python scripts/load_test.py` (đã có key trong `.env`) → mở `https://cloud.langfuse.com` xác nhận **≥10 traces**, mỗi trace có `correlation_id`, User ID (hash), Session ID, Tags.

✅ Kiểm tra: trace trên Langfuse có `correlation_id` khớp với log trong `data/logs.jsonl`.
⚠️ Cấm: ghi correlation_id cứng / giả trace.

## TICKET C3 — Prompt Versioning (v1/v2 + label + rollback)
Theo `docs/PROMPT_VERSIONING.md`. Tạo prompt text `day13-chat` trên Langfuse (dùng SDK hoặc UI):
- **v1** template: `Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}` — labels `baseline` + `production`.
- **v2**: thay đổi nhỏ (ví dụ thêm dòng `Answer concisely under 200 words.`) — label `candidate`.
- Chạy cùng 1 input với `LANGFUSE_PROMPT_LABEL=baseline` và `=candidate` (đổi biến trong `.env`, restart API) → mở 2 trace ghi lại `prompt_name`, `prompt_label`, `prompt_version`.
- Demo rollback: chuyển label `production` từ v1 → v2, chạy 1 request, rồi đưa `production` về v1. Chụp ảnh.

✅ Kiểm tra: trace metadata có `prompt_source=langfuse` (không phải `local-fallback`); 2 version khác nhau; có bằng chứng đổi label/rollback.
⚠️ Cấm: sửa code để ghi giả `prompt_version`; tự sửa `config/challenge.json`.

## TICKET C4 — SLO + Alert Rules + Runbook
**File:** `config/slo.yaml`, `config/alert_rules.yaml`, `docs/alerts.md`

Nhiệm vụ:
1. `config/slo.yaml`: giữ mục tiêu mặc định (latency P95 ≤3000 target 99.5 · error ≤2 target 99.0 · cost ≤$2.5 · quality ≥0.75). Có thể điều chỉnh số cho hợp lý và cập nhật REPORT.md.
2. `config/alert_rules.yaml`: thay 3 `TODO_alert_*` bằng alert thật, dựa **triệu chứng người dùng** (không dùng tên hàm):
   - `high_latency_p95` (warning) — `latency_p95 > 3000ms for 5 minutes` — runbook `docs/alerts.md#alert-1`
   - `elevated_error_rate` (critical) — `error_rate_pct > 5 for 3 minutes` — runbook `docs/alerts.md#alert-2`
   - `cost_budget_exceeded` (warning) — `daily_cost_usd > 2.5` — runbook `docs/alerts.md#alert-3`
3. `docs/alerts.md`: điền đủ 3 alert (tên, severity, SLI/SLO, điều kiện, ảnh hưởng user, **3 bước kiểm tra đầu tiên**, mitigation tạm thời, owner).

✅ Kiểm tra: `python scripts/validate_dashboard.py` vẫn `HỢP LỆ: 6/6`; không còn `TODO_` trong `config/alert_rules.yaml`.
⚠️ Cấm: alert dựa trên tên implementation (vd `tool_fail`); condition không có ngưỡng thời gian duy trì.

## TICKET C5 (Mở rộng, khuyên làm) — Sub-component Trace
**File:** `app/mock_rag.py`, `app/mock_llm.py`
Gắn `@observe(as_type="span")` (import từ `app.tracing`) lên `retrieve()` và `FakeLLM.generate()`. Sau khi chạy load test, waterfall trên Langfuse hiện các span `retrieve`/`generate` lồng dưới `run` — rất hữu ích cho CP3.
✅ Kiểm tra: trace waterfall có nhiều hơn 1 span.

---

# 🧑💻 TRUNG HIẾU — Vai D (QA & Incident + Điều phối)

## TICKET D1 — Dashboard Spec 6 nhóm
**File:** `docs/dashboard-spec.md` (+ `config/dashboard.yaml` là contract)

Nhiệm vụ: điền spec đủ 6 nhóm chỉ số, mỗi panel ghi rõ tên, đơn vị, time range mặc định, threshold/SLO line, nguồn (đối chiếu `config/dashboard.yaml`):
1. Latency (P50/P95/P99) — ms
2. Traffic (count/QPS) — requests/min
3. Error (error_rate_pct + breakdown) — %
4. Cost (total/avg) — USD
5. Tokens (in/out) — tokens
6. Quality (avg) — score 0-1
Chạy `python scripts/validate_dashboard.py` → phải `HỢP LỆ: 6/6 panel`.
✅ Kiểm tra: validator 6/6; spec đủ tên/đơn vị/time range/threshold cho cả 6 panel.

## TICKET D2 — Sinh dữ liệu + Baseline
Nhiệm vụ: sau khi A+B xong:
```bash
Remove-Item data/logs.jsonl -ErrorAction SilentlyContinue
# Terminal 1: uvicorn app.main:app --reload --env-file .env
# Terminal 2:
python scripts/load_test.py --concurrency 5
python scripts/validate_logs.py
```
Ghi baseline cuối cùng vào mục 2 của `submission/REPORT.md`. Đảm bảo `data/logs.jsonl` có ≥10 bản ghi và traces trên Langfuse ≥10.
✅ Kiểm tra: `validate_logs.py` ≥80 (đích 100); log có correlation ID + PII đã che.

## TICKET D3 — Challenge Investigation (CP3)
`config/challenge.json` đã release (`day13-k3-observability-v1`, incident `rag_slow`).
```bash
python -c "from app.challenge import load_challenge; print('Hợp lệ:', load_challenge().challenge_id)"
python scripts/inject_incident.py
python scripts/load_test.py --challenge --concurrency 5
```
- **Metrics:** `curl http://localhost:8000/metrics | python -m json.tool` → P95 vượt ngưỡng (latency spike).
- **Traces:** mở Langfuse, lọc trace trong khoảng bất thường → span nào chậm (lấy Trace ID).
- **Logs:** lọc log cùng correlation ID:
  ```bash
  python -c "import json; [print(json.dumps(r, indent=2)) for r in (json.loads(l) for l in open('data/logs.jsonl')) if r.get('correlation_id')=='req-<8hex>']"
  ```
- Kết luận: Triệu chứng → Vị trí → **Root cause** (`rag_slow` = RAG retrieval delay 2.5s) → Fix action → Preventive measure. Ghi vào mục 6 `REPORT.md`.
- Tắt incident sau khi xong: `python scripts/inject_incident.py --scenario rag_slow --disable`.
✅ Kiểm tra: số liệu/correlation ID thật lấy từ metrics/trace/log (không bịa).
⚠️ Cấm: tự sửa `config/challenge.json`; xóa log lỗi.

## TICKET D4 — REPORT.md + Evidence + Nộp bài
Nhiệm vụ:
1. Điền đủ `submission/REPORT.md`: thông tin nhóm, kết quả kỹ thuật, logging/tracing, dashboard/SLO/alert, challenge, **đóng góp cá nhân kèm link commit** cho từng thành viên.
2. Thu evidence từ cả nhóm vào `submission/evidence/` (validate_logs, ≥10 traces, 1 waterfall, prompt v1/v2 + rollback, log correlation ID, PII redacted, dashboard, challenge).
3. Check lần cuối:
```bash
python -m pytest -q
python scripts/validate_logs.py
git status --short
```
4. Commit + push; nộp URL repo + commit SHA lên Codelabs.
✅ Kiểm tra: `pytest` pass; không có `.env`/`.venv`/PII trong git; `REPORT.md` đầy đủ.
⚠️ Cấm: commit `.env`, secret, `.venv/`, log PII, `config/challenge.json` đã sửa.

---

# 🎁 BONUS (nếu còn thời gian, +10đ)
- **Cost optimization** (Thái Đức + Trung Hiếu): bật `--scenario cost_spike`, đo `total_cost_usd` before → đề xuất (giới hạn output tokens, cache) → after. Ảnh before/after.
- **Audit log**: file `data/audit.jsonl` (đã có `AUDIT_LOG_PATH` trong `.env.example`) ghi incident enable/disable, config change.
- **Automation**: script phát hiện anomaly/PII leak từ `data/logs.jsonl`.

# ✅ Checklist combo trước khi nộp
- [ ] A1+A2+B1+B2 → `validate_logs.py` ≥ 80/100
- [ ] C1–C4 → `error_rate_pct`, ≥10 traces, prompt v1/v2, SLO/alert/runbook
- [ ] D1–D2 → dashboard 6/6 + baseline
- [ ] D3 → challenge root cause có evidence 3 lớp
- [ ] D4 → `pytest` pass, REPORT + evidence đầy đủ, không lộ secret
- [ ] **Mỗi thành viên đã tự commit phần việc + kê khai trong REPORT (B1+B2=40đ)**