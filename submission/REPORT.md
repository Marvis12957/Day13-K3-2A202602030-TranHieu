# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL:
- Commit SHA cuối:
- Thành viên và vai trò:

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`:
- Tổng số traces:
- Số PII leak còn lại:
- Link/đường dẫn dashboard:

## 3. Logging và tracing

- Evidence correlation ID: [submission/evidence/vai-a-correlation-id.md](evidence/vai-a-correlation-id.md) (Tuấn — Vai A)
- Evidence PII redaction:
- Evidence trace waterfall:
- Giải thích một span đáng chú ý:

## 4. Prompt versioning

- Prompt name:
- Version/label baseline:
- Version/label candidate:
- Trace ID của mỗi version:
- Bằng chứng đổi label hoặc rollback:

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`:
- Evidence dashboard:
- SLO đã chọn và lý do:
- Alert rules và runbook:

## 6. Điều tra challenge

- Challenge ID:
- Triệu chứng từ metrics:
- Trace ID liên quan:
- Log line/correlation ID liên quan:
- Root cause:
- Fix action:
- Preventive measure:

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Tuấn (Vai A — Logging & Middleware) | Correlation ID middleware (`app/middleware.py`), enrich log context + giữ correlation ID khi lỗi 500 (`app/main.py`), cập nhật `scripts/load_test.py` | branch `2a202601983-PhamQuocTuan`, commit "feat(vai-a): correlation ID middleware + log context enrichment (TICKET A1+A2)" | Vì sao phải `clear_contextvars()` đầu mỗi request để tránh rò rỉ context giữa các request chạy đồng thời; cách structlog contextvars tự động đính kèm field vào mọi log trong cùng request |
| | | | |
