"""Tạo dashboard 6 panel từ data/logs.jsonl (khớp config/dashboard.yaml).

    python scripts/generate_dashboard.py [--out submission/evidence/dashboard.png] [--json]

Đọc các event `request_received` / `response_sent` / `request_failed` trong
data/logs.jsonl, tính 6 nhóm chỉ số và render ra PNG bằng matplotlib.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.cli import configure_utf8_stdio  # noqa: E402

LOG_PATH = Path("data/logs.jsonl")
PANELS = ["latency", "traffic", "errors", "cost", "tokens", "quality"]
THRESHOLDS = {"latency": 3000, "errors": 2.0, "cost": 2.5, "tokens": 50000, "quality": 0.75}


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    items = sorted(values)
    idx = max(0, min(len(items) - 1, round((p / 100) * len(items) + 0.5) - 1))
    return float(items[idx])


def load_records() -> list[dict]:
    if not LOG_PATH.exists():
        print(f"Không tìm thấy {LOG_PATH}", file=sys.stderr)
        sys.exit(1)
    records = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def summarize(records: list[dict]) -> dict:
    latencies = [r["latency_ms"] for r in records if r.get("event") == "response_sent" and "latency_ms" in r]
    costs = [r["cost_usd"] for r in records if r.get("event") == "response_sent" and "cost_usd" in r]
    tin = sum(r.get("tokens_in", 0) for r in records if r.get("event") == "response_sent")
    tout = sum(r.get("tokens_out", 0) for r in records if r.get("event") == "response_sent")
    qs = [r["quality_score"] for r in records if r.get("event") == "response_sent" and "quality_score" in r]
    traffic = sum(1 for r in records if r.get("event") == "request_received")
    errors = Counter(r.get("error_type") for r in records if r.get("event") == "request_failed")
    total_errors = sum(errors.values())
    total_requests = traffic + total_errors
    error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0.0

    # traffic theo phút
    per_min: Counter[str] = Counter()
    for r in records:
        if r.get("event") == "request_received" and r.get("ts"):
            try:
                per_min[datetime.fromisoformat(r["ts"]).strftime("%H:%M")] += 1
            except (ValueError, TypeError):
                pass

    return {
        "lat_p50": percentile(latencies, 50),
        "lat_p95": percentile(latencies, 95),
        "lat_p99": percentile(latencies, 99),
        "traffic": traffic,
        "per_min": dict(sorted(per_min.items())),
        "error_rate": error_rate,
        "error_breakdown": dict(errors),
        "total_cost": sum(costs),
        "avg_cost": mean(costs) if costs else 0.0,
        "tokens_in": tin,
        "tokens_out": tout,
        "quality_avg": mean(qs) if qs else 0.0,
    }


def render(s: dict, out: Path) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    fig.suptitle("Day 13 AI Observability — 6 panels (time range 60m, refresh 30s)", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])

    # 1. Latency percentiles
    ax = axes[0][0]
    names = ["P50", "P95", "P99"]
    vals = [s["lat_p50"], s["lat_p95"], s["lat_p99"]]
    ax.bar(names, vals, color=["#4caf50", "#ff9800", "#f44336"])
    ax.axhline(THRESHOLDS["latency"], color="black", ls="--", lw=1, label=f"SLO P95 ≤ {THRESHOLDS['latency']}ms")
    ax.set_title("1. Latency percentiles"); ax.set_ylabel("ms"); ax.legend(fontsize=8)
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.0f}", ha="center", va="bottom", fontsize=9)

    # 2. Traffic
    ax = axes[0][1]
    minutes = list(s["per_min"].keys()); counts = list(s["per_min"].values())
    if minutes:
        ax.bar(minutes, counts, color="#2196f3")
        ax.set_title(f"2. Request traffic (total {s['traffic']})"); ax.set_ylabel("requests/min")
        ax.tick_params(axis="x", rotation=45, labelsize=8)
    else:
        ax.text(0.5, 0.5, f"total = {s['traffic']}", ha="center")

    # 3. Error
    ax = axes[0][2]
    eb = s["error_breakdown"] or {"no_error": 0}
    ax.bar(list(eb.keys()), list(eb.values()), color="#e91e63")
    ax.axhline(THRESHOLDS["errors"], color="black", ls="--", lw=1, label=f"SLO ≤ {THRESHOLDS['errors']}%")
    ax.set_title(f"3. Error rate {s['error_rate']:.2f}%"); ax.set_ylabel("count"); ax.legend(fontsize=8)
    ax.tick_params(axis="x", rotation=20, labelsize=8)

    # 4. Cost
    ax = axes[1][0]
    ax.bar(["total", "avg"], [s["total_cost"], s["avg_cost"]], color=["#9c27b0", "#ce93d8"])
    ax.axhline(THRESHOLDS["cost"], color="black", ls="--", lw=1, label=f"budget ≤ ${THRESHOLDS['cost']}")
    ax.set_title(f"4. Cost (total ${s['total_cost']:.4f})"); ax.set_ylabel("USD"); ax.legend(fontsize=8)
    for i, v in enumerate([s["total_cost"], s["avg_cost"]]):
        ax.text(i, v, f"${v:.4f}", ha="center", va="bottom", fontsize=9)

    # 5. Tokens
    ax = axes[1][1]
    ax.bar(["in", "out"], [s["tokens_in"], s["tokens_out"]], color=["#009688", "#80cbc4"])
    ax.set_title(f"5. Tokens (in {s['tokens_in']} / out {s['tokens_out']})"); ax.set_ylabel("tokens")
    for i, v in enumerate([s["tokens_in"], s["tokens_out"]]):
        ax.text(i, v, str(v), ha="center", va="bottom", fontsize=9)

    # 6. Quality
    ax = axes[1][2]
    ax.bar(["quality"], [s["quality_avg"]], color="#ffc107")
    ax.axhline(THRESHOLDS["quality"], color="black", ls="--", lw=1, label=f"SLO ≥ {THRESHOLDS['quality']}")
    ax.set_title(f"6. Quality proxy (mean {s['quality_avg']:.2f})"); ax.set_ylabel("score 0-1"); ax.legend(fontsize=8)
    ax.set_ylim(0, 1)
    ax.text(0, s["quality_avg"], f"{s['quality_avg']:.2f}", ha="center", va="bottom", fontsize=10)

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"Dashboard saved: {out}")


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Sinh dashboard 6 panel từ data/logs.jsonl")
    parser.add_argument("--out", type=Path, default=Path("submission/evidence/dashboard.png"))
    parser.add_argument("--json", action="store_true", help="In ra số liệu JSON thay vì render ảnh")
    args = parser.parse_args()

    records = load_records()
    s = summarize(records)
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0
    render(s, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())