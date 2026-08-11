# Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

Nguồn số liệu: `GET /metrics` (in-process snapshot) và `data/logs.jsonl`. SLO tham chiếu: [`config/slo.yaml`](../config/slo.yaml). Định nghĩa alert: [`config/alert_rules.yaml`](../config/alert_rules.yaml).

Nguyên tắc điều tra chung — **Metrics → Traces → Logs**: metrics cho biết *có* sự cố, trace cho biết *ở đâu*, log cho biết *vì sao*.

## Alert 1

- Tên: `high_latency_p95`
- Severity: warning
- SLI/SLO liên quan: `latency_p95_ms` — SLO: P95 ≤ 3000ms, đạt ≥ 99.5% thời gian trong cửa sổ 28 ngày.
- Điều kiện và thời gian duy trì: `latency_p95 > 3000ms` **duy trì liên tục 5 phút**. Ngưỡng 5 phút để bỏ qua spike ngắn do cold start hoặc một batch request lẻ.
- Ảnh hưởng tới người dùng: người dùng thấy câu trả lời trả về chậm, cảm giác "app bị treo"; client có timeout 30s bắt đầu có nguy cơ hủy request và mất câu trả lời đã tính phí.
- Ba bước kiểm tra đầu tiên:
  1. `curl -s http://localhost:8000/metrics | python -m json.tool` — so P50 với P95: nếu P50 vẫn thấp mà P95 cao thì chỉ một phần request bị chậm (long tail), nếu cả hai đều cao thì cả hệ thống chậm.
  2. Mở Langfuse, lọc trace trong khoảng thời gian bất thường, sắp theo latency giảm dần → xem waterfall trace chậm nhất để biết span nào ăn thời gian (`retrieve` hay `generate`).
  3. Lấy `correlation_id` từ metadata của trace đó rồi lọc log cùng ID để xem toàn bộ vòng đời request:
     ```bash
     python -c "import json; [print(json.dumps(r, ensure_ascii=False)) for r in (json.loads(l) for l in open('data/logs.jsonl')) if r.get('correlation_id')=='req-<8hex>']"
     ```
- Mitigation tạm thời: kiểm tra và tắt incident đang bật (`python scripts/inject_incident.py --scenario rag_slow --disable`); nếu nguyên nhân là RAG chậm thì đặt timeout ngắn cho bước retrieve và trả lời bằng fallback không có context thay vì để người dùng chờ; giảm concurrency của client để hạ tải.
- Owner: on-call-engineer

## Alert 2

- Tên: `elevated_error_rate`
- Severity: critical
- SLI/SLO liên quan: `error_rate_pct` — SLO: error rate ≤ 2%, đạt ≥ 99.0% thời gian. Ngưỡng alert đặt ở 5% (cao hơn SLO) để chỉ bắn khi thực sự vượt xa mục tiêu, tránh nhiễu.
- Điều kiện và thời gian duy trì: `error_rate_pct > 5` **duy trì liên tục 3 phút**. Cửa sổ ngắn hơn Alert 1 vì lỗi ảnh hưởng người dùng nặng hơn latency.
- Ảnh hưởng tới người dùng: request trả HTTP 500, người dùng không nhận được câu trả lời nào; nếu client tự retry thì tải và cost còn tăng thêm.
- Ba bước kiểm tra đầu tiên:
  1. `curl -s http://localhost:8000/metrics | python -m json.tool` — đọc `error_rate_pct` và `error_breakdown` để biết lỗi tập trung ở một `error_type` (ví dụ `RuntimeError` từ vector store) hay rải rác nhiều loại.
  2. `curl -s http://localhost:8000/health` — xác nhận app còn sống và xem `incidents` có scenario nào đang bật.
  3. Lọc log lỗi để lấy correlation ID và thông điệp thật, rồi mở trace tương ứng trên Langfuse:
     ```bash
     grep -E '"event": ?"(request_failed|unhandled_exception)"' data/logs.jsonl | tail -5
     ```
- Mitigation tạm thời: tắt incident đang bật (`python scripts/inject_incident.py --scenario tool_fail --disable`); nếu lỗi đến từ một dependency (vector store) thì cho bước retrieve fail-open — trả lời bằng fallback không có document thay vì raise 500; rollback deploy/prompt version gần nhất nếu lỗi bắt đầu ngay sau khi đổi.
- Owner: on-call-engineer

## Alert 3

- Tên: `cost_budget_exceeded`
- Severity: warning
- SLI/SLO liên quan: `daily_cost_usd` — SLO: chi phí ≤ 2.5 USD/ngày.
- Điều kiện và thời gian duy trì: `daily_cost_usd > 2.5` **duy trì 15 phút** (đánh giá trên tổng tích lũy trong ngày). Không bắn ngay lần đầu vượt để tránh nhiễu khi có một batch load test hợp lệ.
- Ảnh hưởng tới người dùng: chưa lỗi ngay, nhưng vượt ngân sách dẫn tới nguy cơ bị rate-limit hoặc phải hạ cấp model — khi đó chất lượng câu trả lời giảm hoặc dịch vụ bị chặn.
- Ba bước kiểm tra đầu tiên:
  1. `curl -s http://localhost:8000/metrics | python -m json.tool` — so `total_cost_usd` với `avg_cost_usd` và `traffic`: cost cao do **nhiều request** (traffic tăng) hay do **mỗi request đắt hơn** (avg tăng).
  2. Xem `tokens_out_total` so với `tokens_in_total`: output token phình ra là dấu hiệu câu trả lời dài bất thường (scenario `cost_spike` nhân output token lên 4 lần).
  3. Mở Langfuse, sắp trace theo cost giảm dần, kiểm tra `prompt_label`/`prompt_version` của các trace đắt nhất — một prompt version mới có thể đang sinh câu trả lời dài hơn.
- Mitigation tạm thời: tắt `cost_spike` (`python scripts/inject_incident.py --scenario cost_spike --disable`); giới hạn `max_output_tokens` cho response; rollback prompt label `production` về version rẻ hơn; bật cache cho các câu hỏi lặp lại.
- Owner: team-lead
