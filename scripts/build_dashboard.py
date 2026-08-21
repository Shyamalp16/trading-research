"""Builds a self-contained web dashboard (results/dashboard.html).

Open results/dashboard.html in any browser. No server required.

Contents:
  - Portfolio overview: combined book equity, stats, risk limits
  - Per-strategy pages-in-page: exact mechanical rules from the registry,
    full backtest stats, equity curve, yearly breakdown
All charts embedded as base64 PNGs; data computed fresh from raw research
data on every build.
"""
import base64
import io
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.backtest.costs import CostModel
from src.backtest.engine import PathBook, run_backtest
from src.backtest.metrics import core_stats
from src.data.instruments import INSTRUMENTS
from src.data.loaders import load_symbol
from src.discovery.families import add_derived_columns
from src.discovery.hypotheses import apply_filters, build_specs
from src.discovery.runner import load_events
from src.strategies import registry

RESULTS = Path(__file__).resolve().parents[1] / "results"
CSS = """
body{font-family:'Segoe UI',Arial,sans-serif;background:#0f1420;color:#dde3ee;margin:0;padding:24px}
h1{color:#7fb2ff} h2{color:#9fc3ff;border-bottom:2px solid #2a3550;padding-bottom:6px;margin-top:40px}
h3{color:#c8d6f0}
table{border-collapse:collapse;margin:12px 0;background:#161d2e}
th,td{padding:7px 14px;border:1px solid #2a3550;text-align:right}
th{background:#1d2740;color:#a9c1ea} td:first-child,th:first-child{text-align:left}
.pos{color:#5dd39e}.neg{color:#ff7b72}
.cards{display:flex;gap:16px;flex-wrap:wrap;margin:18px 0}
.card{background:#161d2e;border:1px solid #2a3550;border-radius:10px;padding:16px 22px;min-width:150px}
.card .v{font-size:26px;font-weight:700;color:#7fb2ff}
.card .l{font-size:12px;color:#8899bb;text-transform:uppercase;letter-spacing:1px}
.rules{background:#161d2e;border-left:4px solid #7fb2ff;padding:12px 18px;margin:10px 0;line-height:1.7}
.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:700;
background:#2d4a2f;color:#5dd39e;margin-left:8px}
img.chart{max-width:100%;border:1px solid #2a3550;border-radius:8px;margin:8px 0}
.meta{color:#8899bb;font-size:12px}
"""


def fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight",
                facecolor="#161d2e")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def equity_chart(trades, title):
    t = trades.sort_values("trade_date")
    td = pd.to_datetime(t.trade_date).dt.tz_localize(None)
    eq = t.r_net.cumsum()
    fig, ax = plt.subplots(figsize=(10, 3.2))
    ax.plot(td, eq.values, color="#7fb2ff", lw=1.4)
    ax.fill_between(td, eq.values, color="#7fb2ff", alpha=0.12)
    ax.set_title(title, color="#c8d6f0", fontsize=11)
    ax.grid(alpha=0.25)
    ax.tick_params(colors="#8899bb")
    for sp in ax.spines.values():
        sp.set_color("#2a3550")
    return fig_to_b64(fig)


def yearly_table(trades):
    td = pd.to_datetime(trades.trade_date).dt.tz_localize(None)
    t = trades.assign(year=td.dt.year)
    g = t.groupby("year").agg(n=("r_net", "size"), E_R=("r_net", "mean"),
                              total_R=("r_net", "sum"),
                              WR=("r_net", lambda x: f"{(x>0).mean():.1%}"))
    return g.round(3).to_html(classes="yt", border=0)


def stats_table(s):
    rows = [("Trades", f"{s.get('n',0)}"),
            ("Win rate", f"{s.get('win_rate',float('nan')):.1%}"),
            ("Expectancy", f"{s.get('expectancy_r',float('nan')):+.3f} R"),
            ("Avg win / loss", f"{s.get('avg_win_r',0):+.2f} / {s.get('avg_loss_r',0):+.2f} R"),
            ("Payoff ratio", f"{s.get('payoff_ratio',float('nan')):.2f}"),
            ("Profit factor", f"{s.get('profit_factor',float('nan')):.2f}"),
            ("Total", f"{s.get('total_r',0):+.1f} R"),
            ("Max drawdown", f"{s.get('max_dd_r',0):.1f} R"),
            ("Max losing streak", f"{s.get('max_losing_streak',0)}"),
            ("Sharpe (per-trade)", f"{s.get('sharpe_trade',float('nan')):.2f}")]
    body = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)
    return f"<table>{body}</table>"


def rules_block(defn):
    dsl = defn["dsl"]
    lines = [f"<b>Market:</b> {defn['markets'][0]}",
             f"<b>Signal time:</b> {9*60+30+dsl['obs_minute']//60}:{dsl['obs_minute']%60:02d} ET"
             if False else f"<b>Signal time:</b> {(570+dsl['obs_minute'])//60:02d}:{(570+dsl['obs_minute'])%60:02d} ET",
             f"<b>Direction:</b> {dsl['direction'].upper()}"]
    for col, op, val in dsl["filters"]:
        if op == "between":
            lines.append(f"<b>Condition:</b> {val[0]:g} ≤ {col} ≤ {val[1]:g}")
        else:
            v = f"{val:g}" if isinstance(val, (int, float)) else str(val)
            lines.append(f"<b>Condition:</b> {col} {op} {v}")
    sm = dsl["stop"]["mult"]
    lines.append(f"<b>Stop:</b> {sm:g} × ATR(14d) ({sm*100:.0f}% of average daily range)")
    tgt = dsl.get("target")
    if tgt and tgt.get("type") == "rr" and tgt["rr"] < 50:
        lines.append(f"<b>Target:</b> {tgt['rr']:g} × risk")
    else:
        lines.append("<b>Target:</b> none — exit at session end")
    ts = dsl.get("time_stop_min")
    lines.append(f"<b>Time stop:</b> {ts if ts else '—'}")
    lines.append(f"<b>Hard flatten:</b> {defn.get('flatten_by_et','16:00')} ET")
    return "<div class='rules'>" + "<br>".join(lines) + "</div>"


def main():
    registry_defs = registry.load_all()
    # latest version per strategy id
    latest = {}
    for d in registry_defs:
        sid = d["strategy_id"]
        if sid not in latest or d["version"] > latest[sid]["version"]:
            latest[sid] = d

    pb_cache, ev_cache = {}, {}
    strat_sections = []
    for sid in sorted(latest):
        defn = latest[sid]
        sym = defn["markets"][0]
        if sym not in pb_cache:
            pb_cache[sym] = PathBook(load_symbol(sym, research_only=True))
            ev_cache[sym] = add_derived_columns(load_events(sym, research_only=True)[0])
        dsl = defn["dsl"]
        sel = apply_filters(ev_cache[sym], dsl["filters"],
                            obs_minute=dsl["obs_minute"])
        tgt = dsl.get("target") or {"type": "rr", "rr": 99}
        specs = build_specs({"obs_minute": dsl["obs_minute"],
                             "direction": dsl["direction"],
                             "stop": dsl["stop"], "target": tgt,
                             "time_stop_min": dsl.get("time_stop_min") or 100000},
                            sel)
        cost = CostModel(INSTRUMENTS[sym])
        trades = run_backtest(pb_cache[sym], specs,
                              cost_points=cost.cost_in_points(),
                              slippage_points=cost.slippage_points)
        s = core_stats(trades.r_net.values) if len(trades) else {"n": 0}
        chart = equity_chart(trades, f"{sid} — {defn['name']} (cumulative R, net of costs)")
        status_badge = f"<span class='badge'>{defn.get('status','REGISTERED')}</span>"
        strat_sections.append(f"""
<h2 id="{sid}">{sid} — {defn['name']} <span class="meta">v{defn['version']} · hash {defn['version_hash']}</span>{status_badge}</h2>
{rules_block(defn)}
<div style="display:flex;gap:24px;flex-wrap:wrap">
<div>{stats_table(s)}</div>
<div>{yearly_table(trades)}</div>
</div>
<img class="chart" src="data:image/png;base64,{chart}">
<p class="meta">Backtest: entry next-bar open after signal, conservative same-bar stop-first rule,
gap-through fills at worse price, costs = commissions + 1 tick slippage per fill.
Research period only (holdout excluded).</p>
""")

    # ---- combined book ----
    from scripts.portfolio_analysis import build_book
    B = build_book()
    Bt = pd.DataFrame({"trade_date": B.td, "r_net": B.r}).sort_values("trade_date")
    sB = core_stats(Bt.r_net.values)
    chartB = equity_chart(Bt, "Combined reversion book (NQ+ES, 4 slots × 2 sides)")
    yearlyB = yearly_table(Bt)

    jump = " · ".join(
        f'<a href="#{sid}" style="color:#7fb2ff">{sid}</a>'
        for sid in sorted(latest))

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Futures Strategy Portfolio</title><style>{CSS}</style></head><body>
<h1>Futures Strategy Portfolio Dashboard</h1>
<p class="meta">Generated from frozen registry definitions · research data only
(holdout vault excluded) · rebuild: python -m scripts.build_dashboard</p>

<h2>Portfolio overview — Session-Wide Overnight-Range Reversion Book</h2>
<div class="cards">
<div class="card"><div class="v">{sB.get('n')}</div><div class="l">trades</div></div>
<div class="card"><div class="v">{sB.get('win_rate'):.0%}</div><div class="l">win rate</div></div>
<div class="card"><div class="v">{sB.get('expectancy_r'):+.3f}R</div><div class="l">expectancy</div></div>
<div class="card"><div class="v">{sB.get('total_r'):.0f}R</div><div class="l">total (9.6y)</div></div>
<div class="card"><div class="v">{sB.get('max_dd_r'):.1f}R</div><div class="l">max DD</div></div>
</div>
<img class="chart" src="data:image/png;base64,{chartB}">
{yearlyB}
<div class="rules"><b>Risk limits:</b> max 2 concurrent positions (1/symbol) ·
both-symbols day counts as ~1.6× risk (corr 0.91) · book daily stop 2R ·
weekly stop 5R · ATR-based sizing only, never scale after wins.</div>

<h2>Strategies</h2>
<p class="meta">Jump to: {jump}</p>
{''.join(strat_sections)}
</body></html>"""

    out = RESULTS / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"dashboard -> {out} ({out.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
