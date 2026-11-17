#!/usr/bin/env python3
"""
Does a third fund make the TrendFilter sleeve fall less? Research only, read only, standard library.
Plan and bar: docs/RESEARCH_DIVERSIFIER_PLAN.md (fixed before any run).

  python3 scripts/sleeve_compare.py --out results/research_diversifier.md

Reuses the rule simulation of scripts/etf_compare.py unchanged. A sleeve is the average of its funds' rule curves,
each starting with an equal share and never rebalanced.
"""
from __future__ import annotations

import argparse, json, os, sys, urllib.request
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import etf_compare as E

BASE = ["SPY", "QQQ"]
CANDIDATES = ["GLD", "EFA", "IWM", "IEF"]
FIRST_YEAR, SPLIT = 2007, date(2017, 1, 1)
DD_GAIN, RETURN_GIVE = 2.0, 1.0


def fetch(sym: str) -> list[tuple[date, float, float]]:
    """(session date, close, adjusted close) from 2004 on, completed sessions only."""
    now = int(datetime.now(timezone.utc).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1=1072915200&period2={now}&interval=1d&events=div"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30))["chart"]["result"][0]
    today = datetime.now(timezone.utc).date()
    rows = []
    for t, c, a in zip(d["timestamp"], d["indicators"]["quote"][0]["close"], d["indicators"]["adjclose"][0]["adjclose"]):
        day = datetime.fromtimestamp(t, tz=timezone.utc).date()
        if c and a and day < today:
            rows.append((day, float(c), float(a)))
    return rows


def sleeve(curves: list[list[tuple[date, float]]]) -> list[tuple[date, float]]:
    """Average of equal starting shares, no rebalancing. All curves must cover the same sessions."""
    days = [d for d, _ in curves[0]]
    for c in curves[1:]:
        assert [d for d, _ in c] == days, "funds do not share the same sessions"
    return [(d, sum(c[i][1] for c in curves) / len(curves)) for i, d in enumerate(days)]


def three(curve, split: date) -> dict:
    return {"whole": E.stats(curve), "p1": E.stats([x for x in curve if x[0] < split]), "p2": E.stats([x for x in curve if x[0] >= split])}


def verdict(cand: dict, base: dict) -> list[tuple[str, bool, str]]:
    gain = base["whole"]["max_dd_pct"] - cand["whole"]["max_dd_pct"]
    out = [(f"1. drawdown at least {DD_GAIN:.0f} points lower over the whole window", gain >= DD_GAIN,
            f"{cand['whole']['max_dd_pct']:.1f}% against {base['whole']['max_dd_pct']:.1f}% ({gain:+.1f})")]
    ok = all(cand[p]["max_dd_pct"] <= base[p]["max_dd_pct"] for p in ("p1", "p2"))
    out.append(("2. drawdown not worse in each part", ok,
                "; ".join(f"{p}: {cand[p]['max_dd_pct']:.1f}% against {base[p]['max_dd_pct']:.1f}%" for p in ("p1", "p2"))))
    give = base["whole"]["cagr_pct"] - cand["whole"]["cagr_pct"]
    out.append((f"3. return per year not more than {RETURN_GIVE:.1f} point below", give <= RETURN_GIVE,
                f"{cand['whole']['cagr_pct']:+.2f}% against {base['whole']['cagr_pct']:+.2f}% (gives up {give:+.2f})"))
    return out


def analyse(data: dict[str, list]) -> dict:
    common = set.intersection(*[{r[0] for r in rows} for rows in data.values()])
    data = {s: [r for r in rows if r[0] in common] for s, rows in data.items()}          # same sessions for every fund
    days = [r[0] for r in data[BASE[0]]]
    start = min(d for d in E.check_days(days) if d.year >= FIRST_YEAR)
    assert days.index(start) >= E.SMA, "not enough history before the first check"
    end = days[-1]
    rule = {s: E.simulate(rows, start, end) for s, rows in data.items()}
    hold = {s: E.simulate(rows, start, end, rule=False) for s, rows in data.items()}
    base = three(sleeve([rule[s]["curve"] for s in BASE]), SPLIT)
    res = {"start": start, "end": end, "base": base, "cands": {}, "funds": {}}
    for s in data:
        res["funds"][s] = {"rule": E.stats(rule[s]["curve"]), "hold": E.stats(hold[s]["curve"]), "in_market": rule[s]["in_market"],
                           "corr": {b: E.corr(*zip(*[(x, y) for x, y in zip(_ret(data[s]), _ret(data[b]))])) for b in BASE if b != s}}
    for c in CANDIDATES:
        st = three(sleeve([rule[s]["curve"] for s in BASE + [c]]), SPLIT)
        res["cands"][c] = {"stats": st, "verdict": verdict(st, base)}
    passed = [c for c, v in res["cands"].items() if all(p for _, p, _ in v["verdict"])]
    passed.sort(key=lambda c: (-round(base["whole"]["max_dd_pct"] - res["cands"][c]["stats"]["whole"]["max_dd_pct"], 1),
                               -res["cands"][c]["stats"]["whole"]["cagr_pct"]))
    res["passed"], res["proposed"] = passed, (passed[0] if passed else None)
    return res


def _ret(rows) -> list[float]:
    return [rows[i][2] / rows[i - 1][2] - 1 for i in range(1, len(rows))]


def report(res: dict, command: str) -> str:
    b = res["base"]
    L = ["# A third fund for the TrendFilter sleeve: does it fall less?", "",
         f"Plan and bar: `docs/RESEARCH_DIVERSIFIER_PLAN.md`. Command: `{command}`. Run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.",
         f"Data: Yahoo daily closes and adjusted closes, sessions common to all funds. Window {res['start']} to {res['end']}; parts split at {SPLIT}.",
         f"Rule: SMA{E.SMA}, band {E.BAND:.0%}, first session of each month, cash earns 0. Sleeves are equal starting shares, not rebalanced. In sample: one window.", "",
         f"## Verdict: {'propose ' + res['proposed'] if res['proposed'] else 'no candidate passes'}", "",
         f"Passed: {', '.join(res['passed']) if res['passed'] else 'none'}.", "",
         "## Sleeves under the rule", "", "| Sleeve | Per year | Total | Max drawdown | Drawdown 2007 to 2016 | Drawdown 2017 on | Result |", "|---|---|---|---|---|---|---|",
         f"| {' + '.join(BASE)} (baseline) | {b['whole']['cagr_pct']:+.2f}% | {b['whole']['total_pct']:+.0f}% | {b['whole']['max_dd_pct']:.1f}% | {b['p1']['max_dd_pct']:.1f}% | {b['p2']['max_dd_pct']:.1f}% | |"]
    for c, v in res["cands"].items():
        s = v["stats"]; ok = all(p for _, p, _ in v["verdict"])
        L.append(f"| {' + '.join(BASE + [c])} | {s['whole']['cagr_pct']:+.2f}% | {s['whole']['total_pct']:+.0f}% | {s['whole']['max_dd_pct']:.1f}% | {s['p1']['max_dd_pct']:.1f}% | {s['p2']['max_dd_pct']:.1f}% | {'PASS' if ok else 'FAIL'} |")
    for c, v in res["cands"].items():
        L += ["", f"### {c}", "", "| Criterion | Result | Detail |", "|---|---|---|"] + [f"| {k} | {'pass' if p else 'fail'} | {d} |" for k, p, d in v["verdict"]]
    L += ["", "## Each fund alone (context, not part of the bar)", "", "| Fund | Rule: per year | Rule: max drawdown | Held: per year | Held: max drawdown | In market | Correlation with SPY, QQQ |", "|---|---|---|---|---|---|---|"]
    for s, f in res["funds"].items():
        L.append(f"| {s} | {f['rule']['cagr_pct']:+.2f}% | {f['rule']['max_dd_pct']:.1f}% | {f['hold']['cagr_pct']:+.2f}% | {f['hold']['max_dd_pct']:.1f}% | {f['in_market']:.0%} | "
                 + ", ".join(f"{k} {v:.2f}" for k, v in f["corr"].items()) + " |")
    L += ["", "Not financial advice. One historical window; a pass is eligibility for a paper proposal, not a promise about the future."]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="results/research_diversifier.md")
    a = ap.parse_args()
    res = analyse({s: fetch(s) for s in BASE + CANDIDATES})
    text = report(res, "python3 " + " ".join(sys.argv))
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
