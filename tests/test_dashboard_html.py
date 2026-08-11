from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_generator_writes_self_contained_html(tmp_path: Path) -> None:
    output = tmp_path / "dashboard.html"

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "generate_dashboard.py"),
            "--html",
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
    assert "Day 13 AI Observability" in page
    assert all(
        f'data-panel="{panel}"' in page
        for panel in ("latency", "traffic", "errors", "cost", "tokens", "quality")
    )
