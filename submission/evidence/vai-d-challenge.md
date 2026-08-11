# Evidence Vai D — Điều tra Challenge (Metrics → Traces → Logs)

> Người phụ trách: Trung Hiếu (Vai D — QA & Incident Analyst)
> Challenge: `day13-k3-observability-v1` · Incident: `rag_slow` · Feature bị ảnh hưởng: `refund` · Threshold: `latency_threshold_ms = 2000`

## 1. Triệu chứng từ Metrics

**Baseline** (10 request, `load_test.py --concurrency 5`, trước khi bật incident):

```json
{
  "traffic": 10,
  "latency_p50": 1207,
  "latency_p95": 2730,
  "latency_p99": 2730,
  "error_rate_pct": 0.0,
  "quality_avg": 0.88,
  "total_cost_usd": 0.0187
}
```

**Sau khi bật incident `rag_slow` + chạy challenge** (5 request `--challenge --concurrency 5`):

```json
{
  "traffic": 15,
  "latency_p50": 1253,
  "latency_p95": 3837,
  "latency_p99": 3837,
  "error_rate_pct": 0.0,
  "quality_avg": 0.8733,
  "total_cost_usd": 0.0281
}
```

**Triệu chứng:** `latency_p95` tăng `2730 → 3837 ms` (vượt ngưỡng challenge 2000ms).
Toàn bộ 5 request của challenge (`feature=refund`) có `latency_ms` trong log là
**3640–3837ms** so với baseline ~1200ms — gấp ~3 lần. Error rate vẫn 0 (không phải lỗi 500).

## 2. Trace ID — khoanh vùng vị trí

Trace trên Langfuse tìm được qua tag `cid:req-336fca6a`:

```
TRACE ID: b44173150cb303648bf06956e978e69d
name: run | tags: ['cid:req-336fca6a', 'claude-sonnet-4-5', 'lab', 'refund']

span  GENERATION | run      | 3.682 s
span  SPAN       | retrieve | 2.506 s   ← span chiếm gần hết thời gian
span  SPAN       | generate | 0.166 s
```

**Vị trí:** span `retrieve` (RAG retrieval) chiếm **2.506s** trong tổng 3.682s —
span `generate` (LLM) chỉ 0.166s. Vấn đề nằm ở khâu RAG retrieval, không phải LLM.

## 3. Log line — chứng minh root cause

Lọc `data/logs.jsonl` theo correlation ID của 5 request challenge (`feature=refund`):

```
req-1d72f2b8 | feature=refund | latency_ms=3788 | quality=0.9
req-b2c33b4a | feature=refund | latency_ms=3640 | quality=0.8
req-336fca6a | feature=refund | latency_ms=3676 | quality=0.9
req-2d4a3370 | feature=refund | latency_ms=3662 | quality=0.8
req-16782bca | feature=refund | latency_ms=3837 | quality=0.9
```

Ví dụ log `response_sent` đầy đủ của `req-336fca6a`:

```json
{"service":"api","latency_ms":3676,"tokens_in":40,"tokens_out":111,"cost_usd":0.001845,
 "quality_score":0.9,"payload":{"answer_preview":"Starter answer. ..."},
 "event":"response_sent","user_id_hash":"...","feature":"refund",
 "correlation_id":"req-336fca6a","env":"dev","session_id":"k3-challenge-s03",
 "model":"claude-sonnet-4-5"}
```

## 4. Root cause

Incident `rag_slow` bật thêm **`time.sleep(2.5)`** trong hàm `retrieve()` của
`app/mock_rag.py` (mô phỏng vector store chậm). Span `retrieve` trên trace
`b44173150cb303648bf06956e978e69d` = **2.506s** khớp chính xác với delay 2.5s được
inject → đây là thời gian chờ của RAG retrieval, không phải lỗi LLM hay lỗi API.

## 5. Fix action

- **Tạm thời:** tắt incident (`python scripts/inject_incident.py --scenario rag_slow --disable`) — đã thực hiện, `/health` báo `incidents: {rag_slow: false}`.
- **Trong production:** thêm timeout cho bước retrieval (ví dụ 500ms) và fail-open —
  nếu RAG quá hạn thì trả lời bằng fallback không có context thay vì để người dùng
  chờ 2.5s+; giảm concurrency của client khi RAG yếu.

## 6. Preventive measure

- Alert `high_latency_p95` (warning, `latency_p95 > 3000ms for 5 minutes`) sẽ bắn
  trước khi người dùng chịu ảnh hưởng lâu — đã định nghĩa trong `config/alert_rules.yaml`.
- Runbook `docs/alerts.md#alert-1` hướng dẫn đúng luồng Metrics → Traces → Logs
  (bước 3 dùng `correlation_id` từ trace để lọc log).
- Giám sát span `retrieve` như một SLI riêng (baseline ~tức thời, incident làm nó
  tăng lên ~2500ms) để phát hiện sớm khi RAG bắt đầu chậm.