from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Xóa context cũ để tránh rò rỉ giữa các request
        clear_contextvars()

        # 2. Lấy correlation ID từ header x-request-id, nếu không có thì sinh mới
        correlation_id = request.headers.get("x-request-id", f"req-{uuid.uuid4().hex[:8]}")

        # 3. Bind vào structlog contextvars — mọi log sau tự động có trường này
        bind_contextvars(correlation_id=correlation_id)

        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)

        # 4. Trả correlation ID + thời gian xử lý (ms) trong response header
        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = f"{(time.perf_counter() - start) * 1000:.1f}"

        return response
