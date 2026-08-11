"""Tạo dashboard 6 panel từ data/logs.jsonl (khớp config/dashboard.yaml).

    python scripts/generate_dashboard.py [--out submission/evidence/dashboard.png] [--json] [--html]

Đọc các event `request_received` / `response_sent` / `request_failed` trong
data/logs.jsonl, tính 6 nhóm chỉ số và render ra PNG bằng matplotlib.
"""

from __future__ import annotations

import argparse
import html
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


def render_html(s: dict, out: Path) -> None:
    def progress(value: float, maximum: float) -> float:
        return min(100.0, max(0.0, value / maximum * 100)) if maximum else 0.0

    def meter(value: float, maximum: float, color: str) -> str:
        return f'<div class="meter"><span style="width:{progress(value, maximum):.1f}%;background:{color}"></span></div>'

    traffic = s["per_min"]
    max_traffic = max(traffic.values(), default=1)
    traffic_bars = "".join(
        f'<div class="spark-column"><i style="height:{max(8, count / max_traffic * 100):.0f}%"></i><small>{html.escape(minute)}</small></div>'
        for minute, count in traffic.items()
    ) or '<p class="muted">Chưa có request trong cửa sổ này.</p>'
    error_rows = "".join(
        f'<div class="breakdown-row"><span>{html.escape(str(name))}</span><b>{count}</b></div>'
        for name, count in s["error_breakdown"].items()
    ) or '<p class="muted">Không có request thất bại.</p>'
    latency_max = max(THRESHOLDS["latency"], s["lat_p99"], 1.0)
    quality_color = "#36d399" if s["quality_avg"] >= THRESHOLDS["quality"] else "#fb7185"
    generated_at = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")

    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Day 13 AI Observability</title>
  <style>
    :root {{ color-scheme: dark; --bg:#09111f; --panel:#111c2e; --line:#26354e; --text:#e7eefc; --muted:#93a4c2; --green:#36d399; --amber:#fbbf24; --red:#fb7185; --blue:#60a5fa; --purple:#a78bfa; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; font:14px/1.45 Inter,Segoe UI,Arial,sans-serif; background:radial-gradient(circle at top right,#193052 0,transparent 35%),var(--bg); color:var(--text); }}
    main {{ max-width:1440px; margin:auto; padding:34px; }} .top {{ display:flex; justify-content:space-between; gap:20px; align-items:start; margin-bottom:24px; }}
    h1 {{ font-size:28px; margin:0 0 6px; letter-spacing:-.03em; }} h2 {{ font-size:15px; margin:0; }} .eyebrow,.muted,small {{ color:var(--muted); }} .eyebrow {{ text-transform:uppercase; letter-spacing:.12em; font-size:11px; font-weight:700; }}
    .badge {{ border:1px solid var(--line); background:#0d1727; padding:8px 12px; border-radius:999px; color:#b9c8e5; white-space:nowrap; }}
    .kpis,.grid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; }} .kpis {{ grid-template-columns:repeat(4,minmax(0,1fr)); margin-bottom:16px; }}
    .card {{ background:linear-gradient(150deg,rgba(26,41,68,.94),rgba(15,25,43,.94)); border:1px solid var(--line); border-radius:16px; padding:20px; box-shadow:0 12px 30px rgba(0,0,0,.16); min-width:0; }}
    .kpi-value {{ font-size:28px; font-weight:800; margin-top:4px; letter-spacing:-.04em; }} .status {{ display:inline-block; margin-top:8px; padding:3px 8px; border-radius:99px; font-size:11px; font-weight:700; background:rgba(54,211,153,.14); color:var(--green); }}
    .status.warn {{ background:rgba(251,113,133,.14); color:var(--red); }} .panel-title {{ display:flex; justify-content:space-between; gap:12px; margin-bottom:18px; }} .panel-title span {{ color:var(--muted); font-size:12px; }}
    .meter {{ height:9px; overflow:hidden; background:#0a1323; border-radius:999px; border:1px solid #1d2a40; }} .meter span {{ display:block; height:100%; border-radius:inherit; }}
    .metric-row {{ display:grid; grid-template-columns:42px 1fr 58px; align-items:center; gap:10px; margin:13px 0; }} .metric-row b {{ text-align:right; }} .threshold {{ margin-top:14px; color:var(--muted); font-size:12px; }}
    .spark {{ display:flex; align-items:end; height:126px; gap:7px; border-bottom:1px solid var(--line); padding:8px 0 0; }} .spark-column {{ min-width:20px; flex:1; height:100%; display:flex; flex-direction:column; justify-content:end; align-items:center; gap:5px; }} .spark-column i {{ width:100%; min-height:8px; border-radius:5px 5px 0 0; background:linear-gradient(#60a5fa,#2563eb); }} .spark-column small {{ font-size:9px; transform:rotate(-35deg); transform-origin:top right; white-space:nowrap; }}
    .split {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }} .big-number {{ font-size:32px; font-weight:800; }} .breakdown-row {{ display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid var(--line); color:#c8d5ed; }}
    .token {{ margin:15px 0; }} .token-head {{ display:flex; justify-content:space-between; margin-bottom:7px; }} .ring {{ width:122px; height:122px; border-radius:50%; background:conic-gradient({quality_color} {progress(s['quality_avg'], 1):.1f}%,#1c2940 0); display:grid; place-items:center; margin:4px auto 12px; }} .ring div {{ width:94px; height:94px; display:grid; place-items:center; border-radius:50%; background:var(--panel); font-size:22px; font-weight:800; }}
    @media (max-width:900px) {{ .kpis,.grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }} @media (max-width:600px) {{ main {{ padding:18px; }} .top,.split {{ display:block; }} .badge {{ display:inline-block; margin-top:12px; }} .kpis,.grid {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body><main>
  <header class="top"><div><div class="eyebrow">Day 13 · AI observability</div><h1>Operational health at a glance</h1><div class="muted">Source: data/logs.jsonl · 6-panel dashboard contract</div></div><div class="badge">Last generated: {generated_at}<br>Window: 60 min · Refresh: 30 s</div></header>
  <section class="kpis">
    <article class="card"><div class="eyebrow">Requests</div><div class="kpi-value">{s['traffic']}</div><div class="status">Traffic tracked</div></article>
    <article class="card"><div class="eyebrow">P95 latency</div><div class="kpi-value">{s['lat_p95']:.0f} ms</div><div class="status {'warn' if s['lat_p95'] > THRESHOLDS['latency'] else ''}">SLO ≤ {THRESHOLDS['latency']} ms</div></article>
    <article class="card"><div class="eyebrow">Error rate</div><div class="kpi-value">{s['error_rate']:.2f}%</div><div class="status {'warn' if s['error_rate'] > THRESHOLDS['errors'] else ''}">SLO ≤ {THRESHOLDS['errors']}%</div></article>
    <article class="card"><div class="eyebrow">Total cost</div><div class="kpi-value">${s['total_cost']:.4f}</div><div class="status {'warn' if s['total_cost'] > THRESHOLDS['cost'] else ''}">Budget ≤ ${THRESHOLDS['cost']}</div></article>
  </section>
  <section class="grid">
    <article class="card" data-panel="latency"><div class="panel-title"><h2>1. Latency percentiles</h2><span>milliseconds</span></div>
      <div class="metric-row"><span>P50</span>{meter(s['lat_p50'], latency_max, '#60a5fa')}<b>{s['lat_p50']:.0f}</b></div>
      <div class="metric-row"><span>P95</span>{meter(s['lat_p95'], latency_max, '#fbbf24')}<b>{s['lat_p95']:.0f}</b></div>
      <div class="metric-row"><span>P99</span>{meter(s['lat_p99'], latency_max, '#fb7185')}<b>{s['lat_p99']:.0f}</b></div><div class="threshold">SLO line: P95 ≤ {THRESHOLDS['latency']} ms</div></article>
    <article class="card" data-panel="traffic"><div class="panel-title"><h2>2. Request traffic</h2><span>requests/min</span></div><div class="spark">{traffic_bars}</div><div class="threshold">Threshold: ≥ 1 request/min · total {s['traffic']} requests</div></article>
    <article class="card" data-panel="errors"><div class="panel-title"><h2>3. Error rate &amp; breakdown</h2><span>percent</span></div><div class="split"><div><div class="big-number">{s['error_rate']:.2f}%</div>{meter(s['error_rate'], max(THRESHOLDS['errors'], 1), '#fb7185')}<div class="threshold">SLO line: ≤ {THRESHOLDS['errors']}%</div></div><div>{error_rows}</div></div></article>
    <article class="card" data-panel="cost"><div class="panel-title"><h2>4. Cost over time</h2><span>USD</span></div><div class="big-number">${s['total_cost']:.4f}</div>{meter(s['total_cost'], THRESHOLDS['cost'], '#a78bfa')}<div class="split"><div class="threshold">Total window<br><b>${s['total_cost']:.4f}</b></div><div class="threshold">Average/request<br><b>${s['avg_cost']:.4f}</b></div></div><div class="threshold">Budget line: ≤ ${THRESHOLDS['cost']}</div></article>
    <article class="card" data-panel="tokens"><div class="panel-title"><h2>5. Input &amp; output tokens</h2><span>tokens</span></div><div class="token"><div class="token-head"><span>Input</span><b>{s['tokens_in']:,}</b></div>{meter(s['tokens_in'], THRESHOLDS['tokens'], '#2dd4bf')}</div><div class="token"><div class="token-head"><span>Output</span><b>{s['tokens_out']:,}</b></div>{meter(s['tokens_out'], THRESHOLDS['tokens'], '#60a5fa')}</div><div class="threshold">Window threshold: ≤ {THRESHOLDS['tokens']:,}</div></article>
    <article class="card" data-panel="quality"><div class="panel-title"><h2>6. Quality proxy</h2><span>score 0–1</span></div><div class="ring"><div>{s['quality_avg']:.2f}</div></div><div class="threshold" style="text-align:center">SLO line: ≥ {THRESHOLDS['quality']:.2f}</div></article>
  </section>
</main></body></html>"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"HTML dashboard saved: {out}")


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Sinh dashboard 6 panel từ data/logs.jsonl")
    parser.add_argument("--out", type=Path, default=Path("submission/evidence/dashboard.png"))
    parser.add_argument("--json", action="store_true", help="In ra số liệu JSON thay vì render ảnh")
    parser.add_argument("--html", action="store_true", help="Xuất dashboard HTML tĩnh, self-contained")
    args = parser.parse_args()

    records = load_records()
    s = summarize(records)
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0
    if args.html:
        render_html(s, args.out)
        return 0
    render(s, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
