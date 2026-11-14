#!/usr/bin/env python3
"""
Stress test and context lines for docs/RESEARCH_GRID_PLAN.md. Read only; reuses scripts/grid_backtest.py unchanged.

  python3 scripts/grid_stress.py --pair BTCUSDT --range R1 --levels 20 --break K1 --out results/grid/stress.json

Runs the chosen variant on windows A and B, then on A: fee 0.002, levels x0.5 and x1.5, range width x0.75 and x1.25.
For each run it reports per calendar year, worst 90 days, and equity at the coin's 2022 low. Context: holding BTC, ETH,
USDT and SPY per window and per year (SPY daily closes from Yahoo's public chart endpoint; price return and, from the
adjusted close, total return).

grid_backtest.run() keeps its equity curve local, so this script loads the simulator source and adds two lines that
return the curve (equity and inventory value per hour). The trading logic is not touched; the patch asserts its
anchors exist so it fails loudly if the simulator changes.
"""
from __future__ import annotations

import argparse, json, os, sys, types, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "grid_backtest.py")
DAY = 86_400_000


def load_sim():
    src = open(SRC).read()
    patches = [
        ("    eq_curve, peak, max_dd = [], 0.0, 0.0\n", "    eq_curve, peak, max_dd = [], 0.0, 0.0\n    inv_curve = []\n"),
        ('        eq_curve.append((k["t"], eq))\n',
         '        eq_curve.append((k["t"], eq)); inv_curve.append(grid.inventory() * p if grid is not None else 0.0)\n'),
        ('        "quarters": {k: round(v, 2) for k, v in qpnl.items()},\n',
         '        "quarters": {k: round(v, 2) for k, v in qpnl.items()},\n        "_curve": eq_curve, "_inv": inv_curve,\n'),
    ]
    for old, new in patches:
        assert src.count(old) == 1, f"simulator changed, patch anchor not found: {old!r}"
        src = src.replace(old, new)
    mod = types.ModuleType("grid_backtest_curve")
    mod.__file__ = SRC
    exec(compile(src, SRC, "exec"), mod.__dict__)
    return mod


G = load_sim()


def with_width(scale: float):
    """Wrap range_for so every range is scaled around its midpoint (range width stress)."""
    base = G.range_for

    def rf(rule, kl, i, closes):
        r = base(rule, kl, i, closes)
        if r is None or scale == 1.0:
            return r
        mid, half = (r[0] + r[1]) / 2, (r[1] - r[0]) / 2 * scale
        return mid - half, mid + half
    return base, rf


def ymd(t: int) -> str:
    return datetime.fromtimestamp(t / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def per_year(curve: list[tuple[int, float]], capital: float) -> dict:
    out, start, year = {}, capital, None
    for t, e in curve:
        y = datetime.fromtimestamp(t / 1000, tz=timezone.utc).year
        if year is not None and y != year:
            out[year] = (start, last); start = last
        year, last = y, e
    out[year] = (start, last)
    return {str(y): {"start": round(s, 2), "end": round(e, 2), "pct": round((e / s - 1) * 100, 2), "usd": round(e - s, 2)}
            for y, (s, e) in out.items()}


def worst_90(curve: list[tuple[int, float]]) -> dict:
    daily = [(t, e) for t, e in curve if t % DAY == 0]
    worst = (0.0, None, None)
    j = 0
    for i, (t, e) in enumerate(daily):
        while j < len(daily) and daily[j][0] < t + 90 * DAY:
            j += 1
        if j >= len(daily):
            break
        r = daily[j][1] / e - 1
        if r < worst[0]:
            worst = (r, t, daily[j][0])
    return {"pct": round(worst[0] * 100, 2), "from": ymd(worst[1]) if worst[1] else None, "to": ymd(worst[2]) if worst[2] else None}


def at_2022_low(res: dict, kl: list[dict]) -> dict | None:
    k22 = [k for k in kl if datetime.fromtimestamp(k["t"] / 1000, tz=timezone.utc).year == 2022]
    if not k22:
        return None
    low = min(k22, key=lambda k: k["c"])
    idx = {t: n for n, (t, _) in enumerate(res["_curve"])}
    if low["t"] not in idx:
        return None
    n = idx[low["t"]]
    eq, inv = res["_curve"][n][1], res["_inv"][n]
    peak = max(e for t, e in res["_curve"][:n + 1])
    w0 = res["_curve"][0][0]
    c0 = next(k["c"] for k in kl if k["t"] == w0)
    return {"date": ymd(low["t"]), "coin_close": low["c"], "equity": round(eq, 2), "inventory_value": round(inv, 2),
            "inventory_share_pct": round(inv / eq * 100, 1), "below_peak_pct": round((1 - eq / peak) * 100, 2),
            "hold_coin_equity": round(res["capital"] * low["c"] / c0, 2)}


def summarise(res: dict, kl: list[dict]) -> dict:
    out = {k: v for k, v in res.items() if not k.startswith("_")}
    out["per_year"] = per_year(res["_curve"], res["capital"])
    out["worst_90d"] = worst_90(res["_curve"])
    out["at_2022_low"] = at_2022_low(res, kl)
    return out


def run(pair, rule, n, brk, capital, fee, W, width=1.0):
    ws, we = G.WINDOWS[W]
    start = "2020-01-01" if W == "A" else "2023-01-01"     # same data files as grid_backtest.py --all
    base, rf = with_width(width)
    G.range_for = rf
    try:
        res = G.run(pair, rule, n, brk, capital, fee, start, we, ws)
    finally:
        G.range_for = base
    out = summarise(res, G.load_klines(pair, start, we))
    out.update(window_name=W, width_scale=width)
    return out


def holding(pair: str, W: str, capital: float) -> dict:
    ws, we = G.WINDOWS[W]
    kl = G.load_klines(pair, "2020-01-01" if W == "A" else "2023-01-01", we)
    kl = [k for k in kl if k["t"] >= G.ts(ws)]
    curve = [(k["t"], capital * k["c"] / kl[0]["c"]) for k in kl]
    peak, dd = 0.0, 0.0
    for _, e in curve:
        peak = max(peak, e); dd = max(dd, 1 - e / peak)
    final = curve[-1][1]
    years = (kl[-1]["t"] - kl[0]["t"]) / (365.25 * DAY)
    return {"what": f"hold {pair}", "window": W, "final": round(final, 2), "pct": round((final / capital - 1) * 100, 2),
            "annualised_pct": round(((final / capital) ** (1 / years) - 1) * 100, 2), "max_drawdown_pct": round(dd * 100, 2),
            "per_year": per_year(curve, capital)}


def spy(capital: float) -> dict:
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/SPY?period1=1577836800&period2=1793318400"
           "&interval=1d&events=div")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
    rows = [(t * 1000, c, a) for t, c, a in zip(d["timestamp"], d["indicators"]["quote"][0]["close"],
                                                 d["indicators"]["adjclose"][0]["adjclose"]) if c and a]
    out = {}
    for W, (ws, we) in G.WINDOWS.items():
        r = [x for x in rows if G.ts(ws) <= x[0] < G.ts(we) + DAY]
        years = (r[-1][0] - r[0][0]) / (365.25 * DAY)
        res = {"first": ymd(r[0][0]), "last": ymd(r[-1][0])}
        for name, col in (("price", 1), ("total", 2)):
            curve = [(x[0], capital * x[col] / r[0][col]) for x in r]
            peak, dd = 0.0, 0.0
            for _, e in curve:
                peak = max(peak, e); dd = max(dd, 1 - e / peak)
            f = curve[-1][1]
            res[name] = {"final": round(f, 2), "pct": round((f / capital - 1) * 100, 2),
                         "annualised_pct": round(((f / capital) ** (1 / years) - 1) * 100, 2),
                         "max_drawdown_pct": round(dd * 100, 2), "per_year": per_year(curve, capital)}
        out[W] = res
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True); ap.add_argument("--range", required=True)
    ap.add_argument("--levels", type=int, required=True); ap.add_argument("--break", dest="brk", required=True)
    ap.add_argument("--capital", type=float, default=3000); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    p, r, n, k, cap = a.pair, a.range, a.levels, a.brk, a.capital
    runs = [("chosen, window A", run(p, r, n, k, cap, 0.001, "A")),
            ("chosen, window B", run(p, r, n, k, cap, 0.001, "B")),
            ("A, fee 0.2% per side", run(p, r, n, k, cap, 0.002, "A")),
            (f"A, levels {round(n * 0.5)}", run(p, r, round(n * 0.5), k, cap, 0.001, "A")),
            (f"A, levels {round(n * 1.5)}", run(p, r, round(n * 1.5), k, cap, 0.001, "A")),
            ("A, range width x0.75", run(p, r, n, k, cap, 0.001, "A", 0.75)),
            ("A, range width x1.25", run(p, r, n, k, cap, 0.001, "A", 1.25))]
    for name, x in runs:
        print(f"{name:24s} total {x['total_return_pct']:+7.1f}% ann {x['annualised_pct']:+6.1f}% maxDD {x['max_drawdown_pct']:5.1f}% "
              f"worst90 {x['worst_90d']['pct']:+6.1f}% final ${x['final_equity']:,.0f}")
    context = {"holding": [holding(c, W, cap) for W in ("A", "B") for c in ("BTCUSDT", "ETHUSDT")], "spy": spy(cap)}
    for h in context["holding"]:
        print(f"{h['what']} {h['window']}: {h['pct']:+.1f}% ann {h['annualised_pct']:+.1f}% maxDD {h['max_drawdown_pct']:.1f}%")
    for W, s in context["spy"].items():
        print(f"SPY {W}: price {s['price']['pct']:+.1f}% total {s['total']['pct']:+.1f}% maxDD {s['price']['max_drawdown_pct']:.1f}%")
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump({"runs": [{"name": nm, **x} for nm, x in runs], "context": context}, fh, indent=1)


if __name__ == "__main__":
    main()
