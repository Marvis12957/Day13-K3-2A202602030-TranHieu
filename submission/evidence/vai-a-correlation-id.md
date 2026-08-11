# Evidence — Vai A (Tuấn): Correlation ID Middleware & Log Enrichment

> Ghi chú: đây là evidence dạng text (terminal output thật, chạy ngày 2026-08-11).
> Nếu Lab Coach yêu cầu bắt buộc ảnh chụp màn hình, hãy tự chạy lại đúng các lệnh bên dưới
> và chụp màn hình để bổ sung — nội dung sẽ giống hệt vì đã kiểm chứng thực tế.

## 1. Response header có `x-request-id` và `x-response-time-ms`

Lệnh chạy:
```bash
curl -si -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" \
  -d '{"user_id":"u1","feature":"qa","session_id":"s1","message":"hello"}'
```

Kết quả:
```
HTTP/1.1 200 OK
date: Tue, 11 Aug 2026 03:28:48 GMT
server: uvicorn
content-length: 269
content-type: application/json
x-request-id: req-63add29c
x-response-time-ms: 154.6

{"answer":"Starter answer. ...","correlation_id":"req-63add29c","latency_ms":150,"tokens_in":21,"tokens_out":158,"cost_usd":0.002433,"quality_score":0.8}
```

## 2. Log JSON có `correlation_id` + đủ enrichment (`user_id_hash`, `session_id`, `feature`, `model`, `env`)

Trích từ `data/logs.jsonl` (cùng correlation_id `req-63add29c` cho cả `request_received` và `response_sent`):
```json
{"service": "api", "payload": {"message_preview": "hello"}, "event": "request_received", "feature": "qa", "user_id_hash": "bb82030dbc2b", "env": "dev", "model": "claude-sonnet-4-5", "session_id": "s1", "correlation_id": "req-63add29c", "level": "info", "ts": "2026-08-11T03:28:48.689763Z"}
{"service": "api", "latency_ms": 150, "tokens_in": 21, "tokens_out": 158, "cost_usd": 0.002433, "quality_score": 0.8, "payload": {"answer_preview": "Starter answer. ..."}, "event": "response_sent", "feature": "qa", "user_id_hash": "bb82030dbc2b", "env": "dev", "model": "claude-sonnet-4-5", "session_id": "s1", "correlation_id": "req-63add29c", "level": "info", "ts": "2026-08-11T03:28:48.842530Z"}
```

## 3. Kết quả tự kiểm tra

```
$ python -m pytest -q
22 passed, 2 warnings in 2.28s

$ python scripts/validate_logs.py
+ [PASSED] Basic JSON schema
+ [PASSED] Correlation ID propagation
+ [PASSED] Log enrichment
+ [PASSED] PII scrubbing
Estimated Score: 100/100
```

## 4. Commit

- Branch: `2a202601983-PhamQuocTuan`
- Commit: `feat(vai-a): correlation ID middleware + log context enrichment (TICKET A1+A2)`
- File thay đổi: `app/middleware.py`, `app/main.py`, `scripts/load_test.py`

## 5. Trả lời câu hỏi phản biện CP1

**Sự khác biệt lớn nhất giữa log baseline (CP0) và log sau CP1?**
Log baseline có `correlation_id` cố định là `"MISSING"` — không thể tách các request đang chạy đồng thời ra khỏi nhau, và không có `user_id_hash`, `session_id`, `feature`, `model`, `env` nên không đủ ngữ cảnh để lọc/điều tra. Sau CP1, mỗi request có `correlation_id` riêng biệt dạng `req-<8hex>` (khớp giữa response header và mọi dòng log của request đó), cộng thêm 5 trường enrichment — cho phép truy vết toàn trình một request và phân tích theo từng chiều (theo feature, theo user, theo session...).

**Tại sao `clear_contextvars()` ở đầu middleware là bắt buộc?**
`structlog.contextvars` lưu dữ liệu theo context của thread/task hiện tại, không tự động reset giữa các request. Nếu không gọi `clear_contextvars()` đầu mỗi request, khi có nhiều request chạy đồng thời (`--concurrency`), một request có thể vô tình "thừa kế" `correlation_id`/`user_id_hash`/`session_id` còn sót lại từ request trước đó xử lý trên cùng context — gây log sai lệch, thậm chí rò rỉ thông tin của người dùng khác sang log của người dùng hiện tại.
