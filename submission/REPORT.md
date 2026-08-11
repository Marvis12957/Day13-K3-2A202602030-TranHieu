# Báo cáo Day 13 Observability

> ⚠️ Các dòng đánh dấu `CHƯA CÓ` cần người phụ trách tự điền bằng số liệu/ảnh
> thật trước khi nộp. Không điền số liệu ước đoán — RULES.md yêu cầu mọi nhận
> định phải có trace ID, log line hoặc metric cụ thể.

## 1. Thông tin nhóm

- Tên nhóm: `CHƯA CÓ`
- Repository URL: https://github.com/Marvis12957/Day13-K3-2A202602030-TranHieu
- Commit SHA cuối: `CHƯA CÓ` (điền sau khi merge hết các branch thành viên)
- Thành viên và vai trò:
  - Phạm Quốc Tuấn (2A202601983) — Vai A: Logging & Middleware (branch `2a202601983-PhamQuocTuan`)
  - Trần Hiếu (2A202602030) — Vai B: Security & Compliance / PII (branch `hieu`)
  - Thái Đức (2A202601581) — Vai C: Metrics, Tracing & Alerting (branch `2A202601581-ThaiDuc`)
  - Trung Hiếu — Vai D: QA, Incident & Điều phối

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: **100/100** — 21 log record, 0 record thiếu required
  field, 0 record thiếu enrichment, 10 unique correlation ID, 0 PII leak.
  (Đo trên branch `2A202601581-ThaiDuc`, `load_test.py --concurrency 5`, API local.)
- Tổng số traces: `CHƯA CÓ` — máy chạy chưa có `.env` với key Langfuse nên
  `tracing_enabled()` = false. Cần chạy lại load test khi có key để có ≥10 traces.
- Số PII leak còn lại: **0** (`validate_logs.py` báo `Potential PII leaks detected: 0`;
  `grep -iE "@|4111|0987654321" data/logs.jsonl` không có kết quả).
- Link/đường dẫn dashboard: `CHƯA CÓ` — contract ở `config/dashboard.yaml`, spec ở
  `docs/dashboard-spec.md`; ảnh dashboard runtime do Vai D nộp.
- `python -m pytest -q`: **22 passed**. Lưu ý: phải `pip install -r requirements.txt`
  trước (thiếu `langfuse==3.2.1` sẽ làm 2 test tracing fail).

## 3. Logging và tracing

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
- Evidence trace waterfall: `CHƯA CÓ` ảnh (cần key Langfuse). Code đã sẵn sàng:
  `run()` là generation, `retrieve()` và `FakeLLM.generate()` được bọc
  `@observe(as_type="span")` nên waterfall sẽ có 3 tầng.
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

> Phần này **chưa chạy được** vì chưa có key Langfuse. `scripts/setup_prompts.py`
> đã viết sẵn để tạo version và đổi label; cần chạy rồi điền số liệu thật.

- Prompt name: `day13-chat` (biến `LANGFUSE_PROMPT_NAME`)
- Version/label baseline: v1, labels `baseline` + `production` — template
  `Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}`
- Version/label candidate: v2, label `candidate` — thêm dòng
  `Answer concisely under 200 words.`, giữ nguyên 3 biến của prompt contract
- Trace ID của mỗi version: `CHƯA CÓ`
- Bằng chứng đổi label hoặc rollback: `CHƯA CÓ` — quy trình:
  `setup_prompts.py --create` → chạy load test với `LANGFUSE_PROMPT_LABEL=baseline`
  rồi `=candidate` → `--promote 2` (production sang v2) → `--promote 1` (rollback).
  Trace phải có `prompt_source=langfuse`, không phải `local-fallback`.

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: **`HỢP LỆ: 6/6 panel có trong dashboard contract.`**
- Evidence dashboard: `CHƯA CÓ` ảnh runtime (Vai D). 6 panel theo
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

> Vai D chủ trì (TICKET D3). Chưa chạy trên branch này.

- Challenge ID: `day13-k3-observability-v1` (cohort K3, incident `rag_slow`,
  affected feature `refund`, `latency_threshold_ms` 2000, seed 1303)
- Triệu chứng từ metrics: `CHƯA CÓ` (baseline để so sánh: P95 = 160ms,
  `error_rate_pct` = 0.0, `quality_avg` = 0.88)
- Trace ID liên quan: `CHƯA CÓ`
- Log line/correlation ID liên quan: `CHƯA CÓ`
- Root cause: `CHƯA CÓ`
- Fix action: `CHƯA CÓ`
- Preventive measure: `CHƯA CÓ`

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Thái Đức (2A202601581) — Vai C: Metrics, Tracing & Alerting | C1 `error_rate_pct` trong `app/metrics.py`; C2 đưa correlation ID vào trace (`app/agent.py`); C4 SLO note + 3 alert rule + 3 runbook (`config/slo.yaml`, `config/alert_rules.yaml`, `docs/alerts.md`); C5 span cho `retrieve`/`generate`; C3 `scripts/setup_prompts.py` (chưa chạy được vì thiếu key Langfuse) | branch `2A202601581-ThaiDuc`: `db29bb1` (C1), `45e65f4` (C2+C5), `66ed219` (C4), `d6425d3` (C3) | Error rate phải tính trên tổng request đã nhận, không phải trên request thành công — nếu chia cho `TRAFFIC` thì càng nhiều lỗi tỉ lệ càng bị làm nhẹ đi. Alert cần ngưỡng thời gian duy trì, nếu không thì mọi spike ngắn đều gọi on-call. Và khi ticket yêu cầu thêm `correlation_id` vào trace metadata thì public test `test_agent_prompt_trace.py` fail vì test assert metadata bằng đúng 4 key prompt — nên phải chuyển sang tag trace + generation metadata để vừa nối được trace ↔ log vừa giữ pytest pass. |
| | | | |
