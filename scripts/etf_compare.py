#!/usr/bin/env python3
"""
Compare a candidate fund with SPY under the Alpaca TrendFilter bot's rule. Research only, read only, standard library.
Plan and bar: docs/RESEARCH_ISLAMIC_ETF_PLAN.md (fixed before any run).

  python3 scripts/etf_compare.py --out results/research_islamic_etf.md

Rule (fixes/alpaca/strategies/trend_filter.py, config_v2.json): on the first session of each month, from the last
COMPLETED close, buy if not held and close > SMA x (1 + band); sell if held and close < SMA x (1 - band). The trade is
priced at the close of the check day. Returns use dividend adjusted closes; signals use plain closes; cash earns 0.
"""
from __future__ import annotations

import argparse, json, os, sys, urllib.request
from datetime import date, datetime, timezone

SMA, BAND = 200, 0.01
CANDIDATE, BENCH, CONTEXT = "SPUS", "SPY", ["QQQ", "HLAL"]
DD_TOLERANCE = 3.0


def fetch(sym: str) -> list[tuple[date, float, float]]:
    """(session date, close, adjusted close) from Yahoo's public chart endpoint, completed sessions only."""
    now = int(datetime.now(timezone.utc).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1=1483228800&period2={now}&interval=1d&events=div"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
    today = datetime.now(timezone.utc).date()
    rows = []
    for t, c, a in zip(d["timestamp"], d["indicators"]["quote"][0]["close"], d["indicators"]["adjclose"][0]["adjclose"]):
        day = datetime.fromtimestamp(t, tz=timezone.utc).date()
        if c and a and day < today:
            rows.append((day, float(c), float(a)))
    return rows


def check_days(days: list[date]) -> set[date]:
    first = {}
    for d in days:
        first.setdefault((d.year, d.month), d)
    return set(first.values())


def first_ready_check(rows, sma: int = SMA) -> date | None:
    """First monthly check day that has `sma` completed closes before it."""
    days = [r[0] for r in rows]
    cd = check_days(days)
    for i, d in enumerate(days):
        if d in cd and i >= sma:
            return d
    return None


def simulate(rows, start: date, end: date, sma: int = SMA, band: float = BAND, rule: bool = True) -> dict:
    """Equity curve from `start` (a check day) to `end`, starting flat with 1.0. rule=False is buy and hold from start."""
    days = [r[0] for r in rows]
    cd = check_days(days)
    i0 = days.index(start)
    assert i0 >= sma or not rule, "not enough history before the start"
    held, eq, switches, in_days = (not rule), 1.0, 0, 0
    curve = []
    for i in range(i0, len(rows)):
        d, c, a = rows[i]
        if d > end:
            break
        if i > i0 and held:
            eq *= a / rows[i - 1][2]                      # held through this session
            in_days += 1
        if rule and d in cd:
            last = rows[i - 1][1]                         # last completed close before the check
            mean = sum(r[1] for r in rows[i - sma:i]) / sma
            if not held and last > mean * (1 + band):
                held, switches = True, switches + 1       # bought at this close; earns from the next session
            elif held and last < mean * (1 - band):
                held, switches = False, switches + 1
        curve.append((d, eq))
    return {"curve": curve, "switches": switches, "in_market": in_days / max(1, len(curve) - 1)}


def stats(curve) -> dict:
    (d0, e0), (d1, e1) = curve[0], curve[-1]
    years = (d1 - d0).days / 365.25
    peak, dd = 0.0, 0.0
    for _, e in curve:
        peak = max(peak, e); dd = max(dd, 1 - e / peak)
    tot = e1 / e0 - 1
    return {"from": d0, "to": d1, "total_pct": tot * 100, "cagr_pct": ((e1 / e0) ** (1 / years) - 1) * 100 if years > 0 else 0.0,
            "max_dd_pct": dd * 100}


def part(curve, a: date, b: date):
    return [(d, e) for d, e in curve if a <= d <= b]


def corr(x: list[float], y: list[float]) -> float:
    n = len(x); mx, my = sum(x) / n, sum(y) / n
    sx = sum((v - mx) ** 2 for v in x) ** 0.5; sy = sum((v - my) ** 2 for v in y) ** 0.5
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy) if sx and sy else float("nan")


def daily_returns(rows, start: date, end: date) -> dict[date, float]:
    return {rows[i][0]: rows[i][2] / rows[i - 1][2] - 1 for i in range(1, len(rows)) if start < rows[i][0] <= end}


def verdict(cand: dict, bench: dict) -> list[tuple[str, bool, str]]:
    """cand and bench: {'whole': stats, 'h1': stats, 'h2': stats} under the rule. Returns (criterion, passed, detail)."""
    out = [("1. higher total return over the whole window", cand["whole"]["total_pct"] > bench["whole"]["total_pct"],
            f"{cand['whole']['total_pct']:+.1f}% against {bench['whole']['total_pct']:+.1f}%")]
    both = all(cand[h]["total_pct"] > bench[h]["total_pct"] for h in ("h1", "h2"))
    out.append(("2. higher total return in each half", both,
                "; ".join(f"{h}: {cand[h]['total_pct']:+.1f}% against {bench[h]['total_pct']:+.1f}%" for h in ("h1", "h2"))))
    gap = cand["whole"]["max_dd_pct"] - bench["whole"]["max_dd_pct"]
    out.append((f"3. drawdown not more than {DD_TOLERANCE:.0f} points worse", gap <= DD_TOLERANCE,
                f"{cand['whole']['max_dd_pct']:.1f}% against {bench['whole']['max_dd_pct']:.1f}% (gap {gap:+.1f})"))
    return out


def analyse(data: dict[str, list]) -> dict:
    start = first_ready_check(data[CANDIDATE])
    assert start is not None, "candidate has fewer than 200 sessions"
    end = min(rows[-1][0] for rows in data.values())
    syms = [s for s in data if data[s][0][0] < start and start in {r[0] for r in data[s]} and first_ready_check(data[s]) and first_ready_check(data[s]) <= start]
    mid = start + (end - start) / 2
    res = {"start": start, "end": end, "mid": mid, "rows": {}}
    for s in syms:
        r, h = simulate(data[s], start, end), simulate(data[s], start, end, rule=False)
        res["rows"][s] = {"rule": {"whole": stats(r["curve"]), "h1": stats(part(r["curve"], start, mid)), "h2": stats(part(r["curve"], mid, end)),
                                   "switches": r["switches"], "in_market": r["in_market"]},
                          "hold": {"whole": stats(h["curve"]), "h1": stats(part(h["curve"], start, mid)), "h2": stats(part(h["curve"], mid, end))}}
    res["verdict"] = verdict(res["rows"][CANDIDATE]["rule"], res["rows"][BENCH]["rule"])
    rc = daily_returns(data[CANDIDATE], start, end)
    res["corr"] = {}
    for s in syms:
        if s != CANDIDATE:
            rs = daily_returns(data[s], start, end)
            common = sorted(set(rc) & set(rs))
            res["corr"][s] = corr([rc[d] for d in common], [rs[d] for d in common])
    return res


def report(res: dict, command: str) -> str:
    L = [f"# {CANDIDATE} against {BENCH} under the TrendFilter rule", "",
         f"Plan and bar: `docs/RESEARCH_ISLAMIC_ETF_PLAN.md`. Command: `{command}`. Run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.",
         f"Data: Yahoo daily closes and adjusted closes. Window {res['start']} to {res['end']}, halves split at {res['mid']}.",
         f"Rule: SMA{SMA}, band {BAND:.0%}, checked on the first session of each month, cash earns 0. In sample: one window, chosen by the fund's age.", ""]
    ok = all(p for _, p, _ in res["verdict"])
    L += [f"## Verdict: {'PASS' if ok else 'FAIL'}", "", "| Criterion | Result | Detail |", "|---|---|---|"]
    L += [f"| {c} | {'pass' if p else 'fail'} | {d} |" for c, p, d in res["verdict"]]
    for key, title in (("rule", "Under the bot's rule"), ("hold", "Buy and hold, same window")):
        L += ["", f"## {title}", "", "| Fund | Total | Per year | Max drawdown | First half | Second half |" + (" Switches | In market |" if key == "rule" else ""),
              "|---|---|---|---|---|---|" + ("---|---|" if key == "rule" else "")]
        for s, r in res["rows"].items():
            x = r[key]
            line = f"| {s} | {x['whole']['total_pct']:+.1f}% | {x['whole']['cagr_pct']:+.1f}% | {x['whole']['max_dd_pct']:.1f}% | {x['h1']['total_pct']:+.1f}% | {x['h2']['total_pct']:+.1f}% |"
            if key == "rule":
                line += f" {x['switches']} | {x['in_market']:.0%} |"
            L.append(line)
    L += ["", f"## Daily return correlation with {CANDIDATE}", ""] + [f"* {s}: {v:.3f}" for s, v in res["corr"].items()]
    L += ["", "Not financial advice. One historical window; a pass is eligibility for a paper proposal, not evidence of an edge."]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="results/research_islamic_etf.md")
    a = ap.parse_args()
    data = {s: fetch(s) for s in [CANDIDATE, BENCH] + CONTEXT}
    res = analyse(data)
    text = report(res, "python3 " + " ".join(sys.argv))
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
