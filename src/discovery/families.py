"""Discovery V1: economically sensible hypothesis families.

Each family starts from a market-structure question. Grids are deliberately
small and centered on plausible values (anti combinatorial explosion).
Total budget: ~200-250 candidates, all registered for multiple-testing
accounting.
"""
from __future__ import annotations

import itertools


def _h(name, family, obs, direction, filters, stop_mult=1.0, rr=1.5,
       time_stop=240):
    return {
        "name": name, "family": family, "market": "NQ",
        "obs_minute": obs, "direction": direction,
        "filters": filters,
        "stop": {"type": "atr", "mult": stop_mult},
        "target": {"type": "rr", "rr": rr},
        "time_stop_min": time_stop,
    }


def generate_all() -> list[dict]:
    hyps = []

    # ---- 1. Gap behavior: does a gap continue or fade? ----
    for g in [0.3, 0.5]:
        for obs in [30, 90]:
            # gap up + above vwap -> continuation long
            hyps.append(_h(f"gap_cont_up_g{g}_{obs}", "gap", obs, "long",
                           [["gap_atr", ">", g], ["above_vwap", "==", 1]]))
            # gap up but trading below vwap -> fade the gap (short)
            hyps.append(_h(f"gap_fade_up_g{g}_{obs}", "gap", obs, "short",
                           [["gap_atr", ">", g], ["above_vwap", "==", 0]]))
            # gap down + below vwap -> continuation short
            hyps.append(_h(f"gap_cont_dn_g{g}_{obs}", "gap", obs, "short",
                           [["gap_atr", "<", -g], ["above_vwap", "==", 0]]))
            # gap down but reclaiming vwap -> reversal long
            hyps.append(_h(f"gap_rev_dn_g{g}_{obs}", "gap", obs, "long",
                           [["gap_atr", "<", -g], ["above_vwap", "==", 1]]))

    # ---- 2. Overnight position extremes ----
    for p in [0.8, 0.9]:
        for obs in [30, 90]:
            for sm in [0.75, 1.0]:
                hyps.append(_h(f"onpos_high_{p}_{obs}_sm{sm}", "overnight",
                               obs, "long",
                               [["on_position", ">", p]], stop_mult=sm))
                hyps.append(_h(f"onpos_low_{p}_{obs}_sm{sm}", "overnight",
                               obs, "short",
                               [["on_position", "<", 1 - p]], stop_mult=sm))

    # ---- 3. VWAP reclaim / rejection ----
    for obs in [30, 60, 90]:
        # reclaim: recently above, positive 15m push
        hyps.append(_h(f"vwap_reclaim_{obs}", "vwap", obs, "long",
                       [["above_vwap", "==", 1], ["ret_15m", ">", 0.001],
                        ["d_vwap", "between", [-0.15, 0.35]]]))
        # rejection: below vwap, negative push
        hyps.append(_h(f"vwap_reject_{obs}", "vwap", obs, "short",
                       [["above_vwap", "==", 0], ["ret_15m", "<", -0.001],
                        ["d_vwap", "between", [-0.35, 0.15]]]))
        # extension mean reversion: stretched far from vwap -> fade
        for ext in [1.5, 2.0]:
            hyps.append(_h(f"vwap_ext_long_e{ext}_{obs}", "vwap", obs, "long",
                           [["d_vwap", "<", -ext]]))
            hyps.append(_h(f"vwap_ext_short_e{ext}_{obs}", "vwap", obs, "short",
                           [["d_vwap", ">", ext]]))

    # ---- 4. Initial balance compression -> expansion ----
    # ib_ratio = ib_range / atr_prev (derived column, causal)
    for q in [0.4, 0.6]:
        hyps.append(_h(f"ib_compress_up_q{q}", "ib", 90, "long",
                       [["ib_ratio", "<", q], ["or30_broke_up", "==", 1]]))
        hyps.append(_h(f"ib_compress_dn_q{q}", "ib", 90, "short",
                       [["ib_ratio", "<", q], ["or30_broke_dn", "==", 1]]))
    for q in [1.2, 1.5]:
        hyps.append(_h(f"ib_wide_up_q{q}", "ib", 90, "long",
                       [["ib_ratio", ">", q], ["above_vwap", "==", 1]]))
        hyps.append(_h(f"ib_wide_dn_q{q}", "ib", 90, "short",
                       [["ib_ratio", ">", q], ["above_vwap", "==", 0]]))

    # ---- 5. PDH/PDL tests ----
    for obs in [30, 60, 90]:
        # approach PDH from below and stall -> short the rejection
        hyps.append(_h(f"pdh_reject_{obs}", "levels", obs, "short",
                       [["d_pdh", "between", [0.0, 0.3]], ["ret_5m", "<", 0]]))
        # accept above PDH -> continuation
        hyps.append(_h(f"pdh_accept_{obs}", "levels", obs, "long",
                       [["px_vs_pdh", "==", 1], ["ret_5m", ">", 0]]))
        hyps.append(_h(f"pdl_reject_{obs}", "levels", obs, "long",
                       [["d_pdl", "between", [-0.3, 0.0]], ["ret_5m", ">", 0]]))
        hyps.append(_h(f"pdl_accept_{obs}", "levels", obs, "short",
                       [["px_vs_pdl", "==", 1], ["ret_5m", "<", 0]]))

    # ---- 6. Momentum continuation ----
    for m in [0.002, 0.003, 0.004]:
        for obs in [30, 60]:
            hyps.append(_h(f"mom_up_m{m}_{obs}", "momentum", obs, "long",
                           [["ret_30m", ">", m], ["above_vwap", "==", 1]]))
            hyps.append(_h(f"mom_dn_m{m}_{obs}", "momentum", obs, "short",
                           [["ret_30m", "<", -m], ["above_vwap", "==", 0]]))

    # ---- 7. Failed opening-range breakout ----
    for obs in [30, 90]:
        hyps.append(_h(f"fail_brk_up_{obs}", "failed_breakout", obs, "short",
                       [["or30_broke_up", "==", 1], ["above_vwap", "==", 0],
                        ["ret_5m", "<", 0]]))
        hyps.append(_h(f"fail_brk_dn_{obs}", "failed_breakout", obs, "long",
                       [["or30_broke_dn", "==", 1], ["above_vwap", "==", 1],
                        ["ret_5m", ">", 0]]))

    # ---- 8. Trend pullback to VWAP ----
    for obs in [30, 60, 90]:
        hyps.append(_h(f"pullback_up_{obs}", "pullback", obs, "long",
                       [["ret_30m", ">", 0.001], ["d_vwap", "between", [-0.6, 0.1]],
                        ["above_vwap", "==", 1]]))
        hyps.append(_h(f"pullback_dn_{obs}", "pullback", obs, "short",
                       [["ret_30m", "<", -0.001], ["d_vwap", "between", [-0.1, 0.6]],
                        ["above_vwap", "==", 0]]))

    # ---- 9. Volatility regime conditioning on breakouts ----
    for lo, hi in [(0.2, 0.6), (0.6, 0.95)]:
        hyps.append(_h(f"volorb_up_{lo}_{hi}", "volatility", 30, "long",
                       [["or30_broke_up", "==", 1],
                        ["atr_pctile", "between", [lo, hi]]]))
        hyps.append(_h(f"volorb_dn_{lo}_{hi}", "volatility", 30, "short",
                       [["or30_broke_dn", "==", 1],
                        ["atr_pctile", "between", [lo, hi]]]))

    # ---- 10. RR / stop variations on the strongest structural ideas ----
    for rr in [1.0, 1.5, 2.0]:
        for sm in [0.75, 1.0]:
            hyps.append(_h(f"onpos_high_0.8_30_rr{rr}_sm{sm}", "overnight",
                           30, "long", [["on_position", ">", 0.8]],
                           stop_mult=sm, rr=rr))
            hyps.append(_h(f"vwap_reclaim_90_rr{rr}_sm{sm}", "vwap",
                           90, "long",
                           [["above_vwap", "==", 1], ["ret_15m", ">", 0.001],
                            ["d_vwap", "between", [-0.15, 0.35]]],
                           stop_mult=sm, rr=rr))
            hyps.append(_h(f"pullback_up_90_rr{rr}_sm{sm}", "pullback",
                           90, "long",
                           [["ret_30m", ">", 0.001],
                            ["d_vwap", "between", [-0.6, 0.1]],
                            ["above_vwap", "==", 1]],
                           stop_mult=sm, rr=rr))

    return hyps


def add_derived_columns(events):
    """Derived causal columns used by some families."""
    ev = events.copy()
    if "atr_prev" in ev.columns:
        ev["ib_ratio"] = ev["ib_range"] / ev["atr_prev"]
    return ev
