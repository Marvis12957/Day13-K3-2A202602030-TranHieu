from __future__ import annotations

import json
from pathlib import Path

from app import audit


def test_record_audit_event_appends_jsonl(monkeypatch, tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", audit_path)

    audit.record_audit_event("incident_enabled", actor="req-12345678", details={"name": "rag_slow"})
    audit.record_audit_event("incident_disabled", actor="req-12345678", details={"name": "rag_slow"})

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["event"] == "incident_enabled"
    assert first["actor"] == "req-12345678"
    assert first["details"] == {"name": "rag_slow"}
    assert "ts" in first


def test_record_audit_event_creates_parent_dir(monkeypatch, tmp_path: Path) -> None:
    nested_path = tmp_path / "nested" / "audit.jsonl"
    monkeypatch.setattr(audit, "AUDIT_LOG_PATH", nested_path)

    audit.record_audit_event("config_changed", actor="system", details=None)

    assert nested_path.exists()
    record = json.loads(nested_path.read_text(encoding="utf-8").splitlines()[0])
    assert record["details"] == {}
