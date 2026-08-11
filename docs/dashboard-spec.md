# Dashboard Spec — Day 13 AI Observability

> Contract chuẩn chấm điểm: `config/dashboard.yaml` (không đổi contract).
> Nguồn dữ liệu chuẩn: `data/logs.jsonl` + `GET /metrics` (in-process snapshot).
> Thời gian mặc định: 60 phút · Refresh: 30 giây · Có threshold/SLO line cho mỗi panel.

## Tổng quan

- **Tên dashboard:** Day 13 AI Observability
- **Công cụ:** dựng theo spec này (Langfuse/Grafana/Streamlit tương đương) — contract
  không phụ thuộc công cụ.
- **6 panel** (khớp `config/dashboard.yaml`), mỗi panel có: tên, đơn vị, aggregation,
  threshold.

## Các panel

| # | Panel (id) | Event/field nguồn | Aggregation | Đơn vị | Threshold |
|---|---|---|---|---|---|
| 1 | Latency percentiles (`latency`) | `response_sent.latency_ms` | P50, P95, P99 | ms | P95 ≤ 3000 |
| 2 | Request traffic (`traffic`) | `request_received` | count, rate/phút | requests/min | rate ≥ 1 |
| 3 | Error rate and breakdown (`errors`) | `request_received` + `request_failed.error_type` | error_rate_pct, breakdown | % | ≤ 2% |
| 4 | Cost over time (`cost`) | `response_sent.cost_usd` | sum theo phút + total | USD | total ≤ 2.5 |
| 5 | Input/output tokens (`tokens`) | `response_sent.tokens_in/tokens_out` | sum từng field | tokens | ≤ 50000 |
| 6 | Quality proxy (`quality`) | `response_sent.quality_score` | mean | score 0–1 | ≥ 0.75 |

## Chi tiết từng panel

### 1. Latency percentiles
- **Nguồn:** `data/logs.jsonl`, event `response_sent`, field `latency_ms`.
- **Phép tính:** `percentile(latency_ms, [50, 95, 99])`.
- **Đơn vị:** ms. **Threshold/SLO:** P95 ≤ 3000ms (SLO `latency_p95_ms` target 99.5%).
- **Đọc:** P50 thấp + P95 cao = long-tail (một phần request chậm); cả hai cao = hệ thống chậm.

### 2. Request traffic
- **Nguồn:** `data/logs.jsonl`, event `request_received`.
- **Phép tính:** `count() by 1m` → requests/phút.
- **Đơn vị:** requests/min. **Threshold:** rate ≥ 1 (liên tục có traffic).
- **Đọc:** tăng đột biến cần đối chiếu với cost/error để biết do load hợp lệ hay retry lỗi.

### 3. Error rate and breakdown
- **Nguồn:** `request_received` + `request_failed.error_type`.
- **Phép tính:** `count(request_failed)/count(request_received)*100` + `count_by(error_type)`.
- **Đơn vị:** %. **Threshold:** ≤ 2% (SLO `error_rate_pct` target 99.0%; alert bắn ở 5%).
- **Đọc:** breakdown theo `error_type` (vd `RuntimeError`) khoanh vùng lỗi tập trung.

### 4. Cost over time
- **Nguồn:** `response_sent.cost_usd`.
- **Phép tính:** `sum(cost_usd) by 1m` + `sum(cost_usd)` toàn cửa sổ.
- **Đơn vị:** USD. **Threshold:** total ≤ $2.5/ngày (SLO `daily_cost_usd`).
- **Đọc:** cost tăng do **traffic** tăng hay **mỗi request đắt hơn** (so `avg_cost_usd`).

### 5. Input/output tokens
- **Nguồn:** `response_sent.tokens_in` / `tokens_out`.
- **Phép tính:** `sum(tokens_in)`, `sum(tokens_out)`.
- **Đơn vị:** tokens. **Threshold:** ≤ 50000 (tổng cửa sổ).
- **Đọc:** `tokens_out` phình bất thường là dấu hiệu câu trả lời dài (scenario `cost_spike` x4).

### 6. Quality proxy
- **Nguồn:** `response_sent.quality_score`.
- **Phép tính:** `mean(quality_score)`.
- **Đơn vị:** score 0–1. **Threshold:** ≥ 0.75 (SLO `quality_score_avg` target 95%).
- **Đọc:** quality giảm giữa các prompt version / khi fallback không có context.

## Kiểm tra

```bash
python scripts/validate_dashboard.py   # phải báo HỢP LỆ: 6/6 panel
```

Số liệu runtime (baseline + incident) minh hoạ: `submission/evidence/vai-d-challenge.md`.
