from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_challenge_evidence_is_generated_from_challenge_log_records(tmp_path: Path) -> None:
    output = tmp_path / "challenge-evidence.html"

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "generate_challenge_evidence.py"),
            "--out",
            str(output),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    page = output.read_text(encoding="utf-8")
    assert "day13-k3-observability-v1" in page
    assert "3837 ms" in page
    assert "req-336fca6a" in page
