"""Tests for scripts/etf_compare.py. Synthetic sessions, no network. Run: python3 scripts/tests/test_etf_compare.py"""
import os, sys
from datetime import date, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import etf_compare as E


def sessions(closes, start=date(2019, 12, 18)):
    rows, d = [], start
    for c in closes:
        while d.weekday() >= 5:
            d += timedelta(days=1)
        rows.append((d, float(c), float(c))); d += timedelta(days=1)
    return rows


def test_rule_buys_above_and_sells_below_with_the_band():
    up = sessions([100.0] * 210 + [103.0] * 60 + [96.0] * 60 + [100.0] * 40)
    start = E.first_ready_check(up)
    r = E.simulate(up, start, up[-1][0])
    assert r["switches"] == 2, r["switches"]                      # in above 101, out below 99, stays out at 100 (inside the band)
    s = E.stats(r["curve"])
    assert s["total_pct"] < 0 and s["max_dd_pct"] > 0             # bought at 103, sold at 96
    print(f"[OK] buys above SMA x 1.01, sells below SMA x 0.99, stays put inside the band; total {s['total_pct']:+.1f}%")


def test_no_future_data_and_monthly_only():
    base = [100.0] * 210 + [103.0] * 25
    a = sessions(base + [103.0] * 30); b = sessions(base + [50.0] * 30)   # different futures
    start = E.first_ready_check(a)
    cut = a[234][0]
    ca = [e for d, e in E.simulate(a, start, a[-1][0])["curve"] if d <= cut]
    cb = [e for d, e in E.simulate(b, start, b[-1][0])["curve"] if d <= cut]
    assert ca == cb
    crash = sessions([100.0] * 210 + [103.0] * 30 + [60.0] * 5)          # a crash between two checks is not sold until the next check
    r = E.simulate(crash, E.first_ready_check(crash), crash[-1][0])
    assert E.stats(r["curve"])["max_dd_pct"] > 35
    print("[OK] the curve up to a day does not depend on later prices; the rule acts on check days only")


def test_buy_and_hold_and_stats():
    rows = sessions([100.0 + i * 0.1 for i in range(400)])
    start = E.first_ready_check(rows)
    h = E.simulate(rows, start, rows[-1][0], rule=False)
    i0 = [r[0] for r in rows].index(start)
    assert abs(h["curve"][-1][1] - rows[-1][2] / rows[i0][2]) < 1e-12
    assert E.stats(h["curve"])["max_dd_pct"] == 0
    print("[OK] buy and hold equals the adjusted price ratio; drawdown of a rising line is zero")


def test_verdict_needs_all_three():
    S = lambda t, dd=10.0: {"total_pct": t, "max_dd_pct": dd}
    bench = {"whole": S(50), "h1": S(20), "h2": S(25)}
    assert all(p for _, p, _ in E.verdict({"whole": S(60, 12.9), "h1": S(21), "h2": S(30)}, bench))
    assert not all(p for _, p, _ in E.verdict({"whole": S(60), "h1": S(19), "h2": S(40)}, bench))        # one half behind
    assert not all(p for _, p, _ in E.verdict({"whole": S(60, 13.1), "h1": S(21), "h2": S(30)}, bench))  # drawdown 3.1 worse
    assert not all(p for _, p, _ in E.verdict({"whole": S(50), "h1": S(21), "h2": S(30)}, bench))        # equal is not higher
    print("[OK] pass needs a higher return overall and in each half and a drawdown within 3 points")


def test_analyse_and_report_end_to_end():
    import random
    rnd = random.Random(3)
    def walk(n, drift, start):
        p, out = 100.0, []
        for _ in range(n):
            p *= 1 + drift + rnd.gauss(0, 0.01); out.append(p)
        return sessions(out, start)
    data = {"SPUS": walk(1700, 0.0006, date(2019, 12, 18)), "SPY": walk(2400, 0.0004, date(2017, 1, 3)),
            "QQQ": walk(2400, 0.0006, date(2017, 1, 3)), "HLAL": walk(1800, 0.0004, date(2019, 7, 16))}
    res = E.analyse(data)
    assert res["start"] == E.first_ready_check(data["SPUS"]) and set(res["rows"]) == {"SPUS", "SPY", "QQQ", "HLAL"}
    for s, r in res["rows"].items():
        assert r["rule"]["whole"]["from"] == res["start"], s          # everyone starts flat on the same day
    text = E.report(res, "test")
    assert "## Verdict:" in text and "In sample" in text and "Not financial advice" in text
    print("[OK] analyse and report run end to end on synthetic funds; all start on the candidate's first ready check")


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
    print("All ETF comparison tests passed.")
