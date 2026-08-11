# Báo cáo Day 13 Observability

> ⚠️ Các dòng đánh dấu `CHƯA CÓ` cần người phụ trách tự điền bằng số liệu/ảnh
> thật trước khi nộp. Không điền số liệu ước đoán — RULES.md yêu cầu mọi nhận
> định phải có trace ID, log line hoặc metric cụ thể.

## 1. Thông tin nhóm

- Tên nhóm: K3-2A202602030-TranHieu (Nhóm Day 13 K3)
- Repository URL: https://github.com/Marvis12957/Day13-K3-2A202602030-TranHieu
- Commit SHA cuối: `ece1b0f` (feat(vai-d): challenge + prompt versioning + dashboard spec + REPORT)
- Thành viên và vai trò:
  - Phạm Quốc Tuấn (2A202601983) — Vai A: Logging & Middleware (branch `2a202601983-PhamQuocTuan`)
  - Trần Hiếu (2A202602030) — Vai B: Security & Compliance / PII (branch `hieu`)
  - Thái Đức (2A202601581) — Vai C: Metrics, Tracing & Alerting (branch `2A202601581-ThaiDuc`)
  - Trung Hiếu — Vai D: QA, Incident & Điều phối

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** — 22 log record, 0 record thiếu required
  field, 0 record thiếu enrichment, 10+ unique correlation ID, 0 PII leak.
  (Đo trên `main`, `load_test.py --concurrency 5`, API local.)
- Tổng số traces: **38 traces trên Langfuse** (trong đó 17 trace có tag `cid:*` từ
  test của nhóm — vượt yêu cầu tối thiểu ≥10). Key Langfuse đã cấu hình trong
  `.env`, `/health` báo `tracing_enabled: true`.
- Số PII leak còn lại: **0** (`validate_logs.py` báo `Potential PII leaks detected: 0`;
  `grep -iE "@|4111|0987654321" data/logs.jsonl` không có kết quả).
- Link/đường dẫn dashboard: contract `config/dashboard.yaml` (6 panel), spec chi
  tiết `docs/dashboard-spec.md`; số liệu runtime từ `GET /metrics` + `data/logs.jsonl`
  ghi trong `submission/evidence/vai-d-challenge.md` (baseline + incident).
- `python -m pytest -q`: **22 passed**. Lưu ý: phải `pip install -r requirements.txt`
  trước (thiếu `langfuse==3.2.1` sẽ làm 2 test tracing fail).

## 3. Logging và tracing

- Evidence correlation ID: [submission/evidence/vai-a-correlation-id.md](evidence/vai-a-correlation-id.md) (Tuấn — Vai A).
- Evidence correlation ID: mỗi request có ID riêng dạng `req-<8hex>` do
  `CorrelationIdMiddleware` sinh, xuất hiện trong mọi log của cùng request và
  trong response header `x-request-id`. Ví dụ thật từ `data/logs.jsonl`:
  `req-d39feaa6`, `req-e3b2c68e`, `req-5fc94fb9` (10 ID cho 10 request).
- Evidence PII redaction: 3 log line `request_received` chứa PII đã được che,
  không còn dữ liệu thô:
  ```json
  {"correlation_id":"req-d39feaa6","event":"request_received","payload":{"message_preview":"What is your refund policy? My email is [REDACTED_EMAIL]"}}
  {"correlation_id":"req-e3b2c68e","event":"request_received","payload":{"message_preview":"Here is my phone [REDACTED_PHONE_VN], what should be logged?"}}
  {"correlation_id":"req-5fc94fb9","event":"request_received","payload":{"message_preview":"What is the policy for PII and credit card [REDACTED_CREDIT_CARD]?"}}
  ```
  `user_id` không bao giờ vào log dạng thô — chỉ có `user_id_hash` (SHA-256, 12 ký tự đầu).
- Evidence trace waterfall: trace `b44173150cb303648bf06956e978e69d` (challenge
  `rag_slow`) — waterfall 3 tầng `run`(3.682s) → `retrieve`(2.506s) +
  `generate`(0.166s). Chi tiết span trong `submission/evidence/vai-d-challenge.md`.
  Code: `run()` là generation, `retrieve()` và `FakeLLM.generate()` bọc
  `@observe(as_type="span")` nên waterfall có 3 tầng.
- Giải thích một span đáng chú ý: span `retrieve` là span cần theo dõi nhất, vì
  đây là điểm hỏng của cả hai incident dựng sẵn — `rag_slow` thêm `sleep(2.5s)`
  và `tool_fail` raise `RuntimeError("Vector store timeout")` ngay trong
  `retrieve()`. Baseline đo được là P95 ≈ 160ms cho toàn request, nên khi
  `retrieve` một mình chiếm ~2500ms thì trên waterfall span này sẽ dài áp đảo
  span `generate` (~150ms) — đó là cách phân biệt "RAG chậm" với "LLM chậm" mà
  chỉ nhìn latency tổng thì không thấy được.
- Cầu nối trace ↔ log: mỗi trace mang tag `cid:req-<8hex>` và generation
  metadata có `correlation_id`, nên từ một trace chậm trên Langfuse có thể lọc
  ngay log của đúng request đó trong `data/logs.jsonl`.

## 4. Prompt versioning

> Phần này đã chạy được với key Langfuse (xem `submission/evidence/vai-d-prompt-version.md`).

- Prompt name: `day13-chat` (biến `LANGFUSE_PROMPT_NAME`)
- Version/label baseline: v1, labels `baseline` + `production` — template
  `Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}`
- Version/label candidate: v2, label `candidate` — thêm dòng
  `Answer concisely under 200 words.`, giữ nguyên 3 biến của prompt contract
- Trace ID của mỗi version (cùng input "What is your refund policy?"):
  - v1 (`production`): `d0dd8d0f609767ebf898f2679f6a5bd5`
  - v2 (`candidate`): `b782eff7771dc844c88fb2e80cc47002`
  (cả hai đều `prompt_source=langfuse`)
- Bằng chứng đổi label hoặc rollback: `setup_prompts.py --promote 2`
  (production→v2) rồi `--promote 1` (rollback về v1) — log lệnh + trace ID trong
  `submission/evidence/vai-d-prompt-version.md`.

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: **`HỢP LỆ: 6/6 panel có trong dashboard contract.`**
- Evidence dashboard: spec chi tiết 6 panel ở `docs/dashboard-spec.md` (đối chiếu
  contract `config/dashboard.yaml`); số liệu runtime baseline + incident từ
  `GET /metrics` và `data/logs.jsonl` trong
  `submission/evidence/vai-d-challenge.md`. 6 panel theo
  `config/dashboard.yaml`: latency (P50/P95/P99, ms) · traffic (requests) ·
  errors (`error_rate_pct` + breakdown, %) · cost (USD) · tokens (in/out) ·
  quality (score 0–1). Nguồn dữ liệu: `data/logs.jsonl` + `GET /metrics`.
- SLO đã chọn và lý do (`config/slo.yaml`, cửa sổ 28 ngày):
  - `latency_p95_ms ≤ 3000`, target 99.5% — baseline đo được P95 ≈ 160ms nên
    ngưỡng này rất thoáng cho vận hành bình thường, nhưng vẫn bắt được incident
    `rag_slow` (cộng thêm 2.5s vào bước retrieve).
  - `error_rate_pct ≤ 2`, target 99.0% — lỗi làm người dùng không có câu trả lời
    nào nên đặt chặt; alert lại bắn ở mức 5% để chỉ gọi on-call khi vượt xa SLO.
  - `daily_cost_usd ≤ 2.5` — mỗi request ≈ 0.0021 USD (đo thật:
    `avg_cost_usd: 0.0021`), tương đương ~1200 request/ngày; scenario
    `cost_spike` nhân output token lên 4 lần sẽ vượt ngân sách này.
  - `quality_score_avg ≥ 0.75` — baseline đo được 0.88. Đây là quality proxy
    heuristic, dùng để phát hiện tụt chất lượng tương đối giữa các prompt
    version, không phải đánh giá của con người.
- Alert rules và runbook (`config/alert_rules.yaml` + `docs/alerts.md`) — cả 3
  đều symptom-based và có ngưỡng thời gian duy trì:

  | Alert | Severity | Condition | Owner | Runbook |
  |---|---|---|---|---|
  | `high_latency_p95` | warning | `latency_p95 > 3000ms for 5 minutes` | on-call-engineer | `docs/alerts.md#alert-1` |
  | `elevated_error_rate` | critical | `error_rate_pct > 5 for 3 minutes` | on-call-engineer | `docs/alerts.md#alert-2` |
  | `cost_budget_exceeded` | warning | `daily_cost_usd > 2.5 for 15 minutes` | team-lead | `docs/alerts.md#alert-3` |

  Mỗi runbook có SLI/SLO liên quan, ảnh hưởng tới người dùng, 3 bước kiểm tra
  đầu tiên theo luồng Metrics → Traces → Logs, mitigation tạm thời và owner.

## 6. Điều tra challenge

> Vai D chủ trì (TICKET D3) — đã chạy xong, chi tiết: `submission/evidence/vai-d-challenge.md`.

- Challenge ID: `day13-k3-observability-v1` (cohort K3, incident `rag_slow`,
  affected feature `refund`, `latency_threshold_ms` 2000, seed 1303)
- Triệu chứng từ metrics: `latency_p95` tăng **2730 → 3837ms** (vượt ngưỡng
  2000ms); 5 request challenge (`feature=refund`) có `latency_ms` **3640–3837ms**
  so với baseline ~1200ms; `error_rate_pct` = 0.0 (không phải lỗi 500).
- Trace ID liên quan: `b44173150cb303648bf06956e978e69d` (tag `cid:req-336fca6a`)
  — span `retrieve` = **2.506s**, `generate` = 0.166s.
- Log line/correlation ID liên quan: `req-336fca6a` → `response_sent` với
  `latency_ms: 3676`, `feature: refund`; 5 correlation ID là `req-1d72f2b8`,
  `req-b2c33b4a`, `req-336fca6a`, `req-2d4a3370`, `req-16782bca`.
- Root cause: incident `rag_slow` chèn `time.sleep(2.5)` trong `retrieve()`
  (`app/mock_rag.py`) — span `retrieve` 2.506s khớp đúng delay 2.5s và chiếm gần
  hết tổng latency; LLM (`generate` 0.166s) và API không lỗi.
- Fix action: tắt incident (`inject_incident.py --scenario rag_slow --disable`);
  trong production thêm timeout cho retrieval (~500ms) + fail-open fallback khi
  RAG quá hạn thay vì để người dùng chờ.
- Preventive measure: alert `high_latency_p95` (3000ms/5 phút) + runbook
  `docs/alerts.md#alert-1` theo luồng Metrics→Traces→Logs; theo dõi span
  `retrieve` như một SLI riêng (baseline tức thời, incident ~2500ms).

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Tuấn (Vai A — Logging & Middleware) | Correlation ID middleware (`app/middleware.py`), enrich log context + giữ correlation ID khi lỗi 500 (`app/main.py`), cập nhật `scripts/load_test.py` | branch `2a202601983-PhamQuocTuan`, commit "feat(vai-a): correlation ID middleware + log context enrichment (TICKET A1+A2)" | Vì sao phải `clear_contextvars()` đầu mỗi request để tránh rò rỉ context giữa các request chạy đồng thời; cách structlog contextvars tự động đính kèm field vào mọi log trong cùng request |
| Trần Hiếu (2A202602030) — Vai B: Security & PII | Bật `scrub_event` quét **toàn bộ** trường string/dict (`app/logging_config.py`), thêm pattern `passport` + `address_vn` (`app/pii.py`), lưu evidence log PII | branch `hieu`: `89f50bc` (done block 1), `14e8699` (fix bỏ duplicate trace + `structlog.configure()` trống + global scrub) | Scrubbing phải chạy **trước** khi render JSON và ghi file; regex cần boundary `\b`/`(?<!\w)` để không cắt nhầm log hợp lệ; một `structlog.configure()` trống cuối hàm là code chết dễ phá logging khi đổi version |
| Thái Đức (2A202601581) — Vai C: Metrics, Tracing & Alerting | C1 `error_rate_pct` trong `app/metrics.py`; C2 đưa correlation ID vào trace (`app/agent.py`); C4 SLO note + 3 alert rule + 3 runbook (`config/slo.yaml`, `config/alert_rules.yaml`, `docs/alerts.md`); C5 span cho `retrieve`/`generate`; C3 `scripts/setup_prompts.py` + tạo prompt `day13-chat` v1/v2 trên Langfuse | branch `2A202601581-ThaiDuc`: `db29bb1` (C1), `45e65f4` (C2+C5), `66ed219` (C4), `d6425d3` (C3) | Error rate phải tính trên tổng request đã nhận, không phải trên request thành công — nếu chia cho `TRAFFIC` thì càng nhiều lỗi tỉ lệ càng bị làm nhẹ đi. Alert cần ngưỡng thời gian duy trì, nếu không thì mọi spike ngắn đều gọi on-call. Và khi ticket yêu cầu thêm `correlation_id` vào trace metadata thì public test `test_agent_prompt_trace.py` fail vì test assert metadata bằng đúng 4 key prompt — nên phải chuyển sang tag trace + generation metadata để vừa nối được trace ↔ log vừa giữ pytest pass. |
| Trung Hiếu (2A202602030) — Vai D: QA, Incident & Điều phối | Điều phối + review/merge 3 branch thành viên về `main`; chạy baseline + điều tra challenge `rag_slow` theo luồng Metrics→Traces→Logs; tạo prompt v1/v2 + bằng chứng label/rollback; lấp `REPORT.md` và evidence Vai D | `main` merge `9e0019f`; evidence `submission/evidence/vai-d-challenge.md`, `vai-d-prompt-version.md` | Luồng điều tra phải bắt đầu từ metrics để biết **triệu chứng**, trace để **khoanh vùng**, log để **chứng minh** — không được kết luận từ một lớp duy nhất; span `retrieve` 2.506s khớp delay 2.5s mới là bằng chứng root cause, không phải latency tổng |
| | | | |
