"""TrendFilter tab calculations: run with  python tests/test_trendfilter.py"""
import os
import sys
import tempfile
from datetime import date, timedelta

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import trendfilter_calc as TC  # noqa: E402

HERE = os.path.dirname(__file__)
SEED = os.path.join(HERE, "..", "..", "fixes", "alpaca", "strategies", "trend_filter_journal.seed.jsonl")


def _series(closes, start=date(2026, 1, 1)):
    days, d = [], start
    while len(days) < len(closes):
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return pd.DataFrame({"date": days, "close": closes})


def test_rule_buys_holds_inside_band_and_sells():
    # 40 day SMA, 1% band. Flat (stay out), rising (buy), flat on top (hold while the SMA catches up), falling (sell).
    closes = [100.0] * 45 + [100.0 + i for i in range(1, 46)] + [145.0] * 45 + [145.0 - 2 * i for i in range(1, 41)]
    h = _series(closes)
    r = TC.rule_history(h, 40, 0.01)
    acts = list(r["action"])
    assert acts[0] == "STAY OUT"
    assert "BUY" in acts and "SELL" in acts
    i_buy, i_sell = acts.index("BUY"), acts.index("SELL")
    assert i_buy < i_sell and all(a == "HOLD (in)" for a in acts[i_buy + 1:i_sell])
    # every check uses only closes before the check day
    assert all(row.close_date < row.check_day for row in r.itertuples())


def test_band_blocks_a_buy_just_above_the_average():
    h = _series([100] * 30 + [100.5] * 30)  # 0.5% above: inside the 1% band
    assert set(TC.rule_history(h, 3, 0.01)["action"]) == {"STAY OUT"}


def test_next_trigger_lines():
    h = _series([100.0] * 10)
    held = TC.next_trigger(h, 5, 0.01, True)
    flat = TC.next_trigger(h, 5, 0.01, False)
    assert abs(held["line"] - 99.0) < 1e-9 and held["would"] == "HOLD"
    assert abs(flat["line"] - 101.0) < 1e-9 and flat["would"] == "STAY OUT"
    assert TC.next_trigger(h, 50, 0.01, True) is None


def test_seed_matches_the_ledger_and_reads_cleanly():
    j = TC.read_journal(SEED)
    f = TC.fills(j)
    cost = dict(zip(f["symbol"], (f["qty"] * f["price"]).round(5)))
    assert cost == {"SPY": 489.78462, "QQQ": 490.07652}  # trend_filter_state.json after the 2 Nov fills
    assert set(j[j["event"] == "check"]["month"]) == {"2026-11"}
    w = TC.fill_reasons(j)
    assert all("2026-11 check" in s and "buy line" in s for s in w["why"])


def test_journal_skips_bad_lines_and_missing_file():
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
        fh.write('{"ts": "2026-11-02T14:31:03+00:00", "event": "fill", "symbol": "SPY", "side": "buy", "qty": 1, "price": 10}\n')
        fh.write("not json\n{}\n")
    try:
        assert len(TC.read_journal(fh.name)) == 1
    finally:
        os.unlink(fh.name)
    assert TC.read_journal("/nonexistent/journal.jsonl").empty


def test_sleeve_curve_from_fills():
    j = TC.read_journal(SEED)
    days = [date(2026, 11, 2), date(2026, 11, 3)]
    closes = {"SPY": pd.DataFrame({"date": days, "close": [760.0, 770.0]}),
              "QQQ": pd.DataFrame({"date": days, "close": [700.0, 690.0]})}
    c = TC.sleeve_curve(TC.fills(j), closes, 1000.0, lambda ts: ts.date())
    cash = 1000 - 489.78462 - 490.07652
    assert abs(c["value"].iloc[1] - (cash + 0.645 * 770 + 0.705 * 690)) < 1e-6
    # benchmark: $1,000 of SPY at the bot's SPY fill price, valued at each close
    assert abs(c["bench"].iloc[1] - 1000 / 759.356 * 770) < 1e-6


def test_sell_adds_cash_and_removes_the_position():
    j = pd.DataFrame([
        {"ts": pd.Timestamp("2026-11-02 15:00", tz="UTC"), "event": "fill", "symbol": "SPY", "side": "buy", "qty": 1.0, "price": 100.0, "pnl": 0.0, "realized": 0.0},
        {"ts": pd.Timestamp("2026-12-01 15:00", tz="UTC"), "event": "fill", "symbol": "SPY", "side": "sell", "qty": 1.0, "price": 90.0, "pnl": -10.0, "realized": -10.0},
    ])
    days = [date(2026, 11, 2), date(2026, 12, 1), date(2026, 12, 2)]
    c = TC.sleeve_curve(TC.fills(j), {"SPY": pd.DataFrame({"date": days, "close": [100.0, 90.0, 50.0]})}, 1000.0, lambda ts: ts.date())
    assert list(c["value"].round(6)) == [1000.0, 990.0, 990.0]  # after the sell the price no longer matters


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"[OK] {name}")
    print("All TrendFilter tests passed.")
