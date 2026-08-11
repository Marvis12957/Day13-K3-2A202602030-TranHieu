from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Audit log tách biệt hoàn toàn với data/logs.jsonl:
# - logs.jsonl: phục vụ debug/observability theo từng request (latency, tokens, lỗi...).
# - audit.jsonl: phục vụ truy vết AI/khi nào một hành động thay đổi trạng thái hệ thống
#   (bật/tắt incident, đổi config) — phục vụ compliance, không lẫn với log vận hành.
AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", "data/audit.jsonl"))


def record_audit_event(event: str, actor: str, details: dict[str, Any] | None = None) -> None:
    """Ghi một sự kiện audit vào AUDIT_LOG_PATH dạng JSONL (append-only).

    event:   tên hành động, vd "incident_enabled", "incident_disabled", "config_changed".
    actor:   ai/ yêu cầu nào gây ra hành động — dùng correlation_id để đối chiếu ngược
             sang data/logs.jsonl khi cần điều tra.
    details: bối cảnh bổ sung (vd {"name": "rag_slow"}).
    """
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "actor": actor,
        "details": details or {},
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
