"""Tests for scripts/sleeve_compare.py. Synthetic sessions, no network. Run: python3 scripts/tests/test_sleeve_compare.py"""
import os, random, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sleeve_compare as S


def sessions(closes, start=date(2005, 1, 3)):
    rows, d = [], start
    for c in closes:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        rows.append((d, float(c), float(c))); d += timedelta(days=1)
    return rows


def test_sleeve_is_the_average_without_rebalancing():
    d = [date(2020, 1, i) for i in (2, 3, 6)]
    a = list(zip(d, [1.0, 2.0, 4.0])); b = list(zip(d, [1.0, 1.0, 1.0]))
    assert [e for _, e in S.sleeve([a, b])] == [1.0, 1.5, 2.5]
    try:
        S.sleeve([a, b[:2]]); raise SystemExit("expected a failure")
    except AssertionError:
        pass
    print("[OK] sleeve = average of equal starting shares, never rebalanced; mismatched sessions are refused")


def test_verdict_needs_all_three():
    T = lambda dd, cagr=10.0: {"max_dd_pct": dd, "cagr_pct": cagr}
    base = {"whole": T(20), "p1": T(20), "p2": T(15)}
    ok = lambda c: all(p for _, p, _ in S.verdict(c, base))
    assert ok({"whole": T(18, 9.0), "p1": T(18), "p2": T(15)})
    assert not ok({"whole": T(18.1, 9.0), "p1": T(18), "p2": T(15)})        # only 1.9 points lower
    assert not ok({"whole": T(17, 9.0), "p1": T(17), "p2": T(15.1)})        # worse in one part
    assert not ok({"whole": T(17, 8.9), "p1": T(17), "p2": T(14)})          # gives up 1.1 points a year
    print("[OK] pass needs 2 points less drawdown, no part worse, and no more than 1 point of return given up")


def test_analyse_end_to_end_and_selection():
    rnd = random.Random(11)
    n = 5600
    def walk(drift, vol, crash=None):
        p, out = 100.0, []
        for i in range(n):
            shock = -0.02 if crash and crash[0] <= i < crash[1] else 0.0
            p *= 1 + drift + shock + rnd.gauss(0, vol); out.append(p)
        return sessions(out)
    crash = (900, 930)                                                       # a 2008 style fall in the first part
    data = {"SPY": walk(0.0004, 0.010, crash), "QQQ": walk(0.0005, 0.013, crash), "GLD": walk(0.0004, 0.004),
            "EFA": walk(0.0002, 0.011, crash), "IWM": walk(0.0003, 0.013, crash), "IEF": walk(0.0002, 0.003)}
    res = S.analyse(data)
    assert res["start"].year == 2007 and res["start"] == min(d for d in S.E.check_days([r[0] for r in data["SPY"]]) if d.year >= 2007)
    assert set(res["cands"]) == set(S.CANDIDATES)
    for c, v in res["cands"].items():
        assert len(v["verdict"]) == 3
    if res["passed"]:
        gains = [round(res["base"]["whole"]["max_dd_pct"] - res["cands"][c]["stats"]["whole"]["max_dd_pct"], 1) for c in res["passed"]]
        assert gains == sorted(gains, reverse=True) and res["proposed"] == res["passed"][0]
    text = S.report(res, "test")
    assert "## Verdict:" in text and "baseline" in text and "Not financial advice" in text
    print(f"[OK] end to end on synthetic funds: start {res['start']}, passed {res['passed'] or 'none'}; at most one proposed, largest drawdown cut first")


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
    print("All sleeve comparison tests passed.")
