"""CRT engine tests on a synthetic daily series with a known low sweep. Run: python tests/test_crt.py"""
import os
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import crt  # noqa: E402
import crt_data  # noqa: E402


def make_series(n=120, seed=3):
    """Flat-ish random walk around 500 fils, then a two-candle CRT low sweep at the end, plus a future candle."""
    rng = np.random.default_rng(seed)
    close = 500 + np.cumsum(rng.normal(0, 2, n))
    o = close + rng.normal(0, 1, n)
    h = np.maximum(o, close) + rng.uniform(1, 4, n)
    l = np.minimum(o, close) - rng.uniform(1, 4, n)
    start = date(2026, 1, 1)
    dates = [start + timedelta(days=i) for i in range(n)]
    df = pd.DataFrame({"date": dates, "open": o, "high": h, "low": l, "close": close, "volume": 1000})
    # range candle at -3, sweep candle at -2 (takes the low by 3 ticks, closes inside), -1 is "today" (ignored)
    r = df.index[-3]
    df.loc[r, ["open", "high", "low", "close"]] = [500, 508, 494, 503]
    s = df.index[-2]
    df.loc[s, ["open", "high", "low", "close"]] = [502, 505, 491, 500]   # low 491 < 494 - tick, close 500 inside
    return df


def test_low_sweep_gives_bullish_or_rr_veto():
    df = make_series()
    today = df["date"].iloc[-1]  # last row is "today", must be dropped
    a = crt.analyze(df, "TEST", "KW", capital=3000, risk_pct=1.0, today=today)
    assert a.as_of == str(df["date"].iloc[-2])  # used the closed candle, not today's
    assert any("took the prior low" in r for r in a.reasons), a.reasons
    assert a.bias in ("bullish", "NO SETUP")
    if a.bias == "bullish":
        assert a.stop < a.entry < a.target1
        assert a.rr >= 2.0 and a.shares >= 1
    else:
        assert any("Reward to risk" in r or "fewer than one lot" in r for r in a.reasons)


def test_no_sweep_is_no_setup():
    df = make_series().iloc[:-3].reset_index(drop=True)  # remove the engineered candles
    # make the last four closed candles strict inside bars so no candle takes the prior high or low
    for k, i in enumerate(df.index[-4:]):
        w = 8 - 1.5 * k
        df.loc[i, ["open", "high", "low", "close"]] = [500, 500 + w, 500 - w, 500 + (w / 2 if k % 2 else -w / 2)]
    a = crt.analyze(df, "TEST", "KW", today=df["date"].iloc[-1] + timedelta(days=1))
    assert a.bias == "NO SETUP" and "No CRT sweep" in a.reasons[0]


def test_deterministic():
    df = make_series()
    t = df["date"].iloc[-1]
    assert crt.analyze(df, "T", "KW", today=t).to_row() == crt.analyze(df, "T", "KW", today=t).to_row()


def test_tick_schedule():
    assert crt.tick_size(80, "KW") == 0.1 and crt.tick_size(300, "KW") == 1.0 and crt.tick_size(2500, "KW") == 10.0
    assert crt.tick_size(300, "US") == 0.01


def test_csv_parser_arabic_and_english():
    en = "Date,Open,High,Low,Close,Volume\n01/03/2026,500,505,495,502,1000\n02/03/2026,502,506,498,504,1200\n"
    ar = "التاريخ;الافتتاح;الأعلى;الأدنى;الإغلاق;الكمية\n01/03/2026;500;505;495;502;1000\n02/03/2026;502;506;498;504;1200\n"
    for text in (en, ar):
        df = crt_data.parse_csv(text)
        assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"] and len(df) == 2
        assert df["close"].iloc[-1] == 504


def test_outcome_evaluation():
    log = pd.DataFrame([{**{c: None for c in crt.LOG_COLS}, "ticker": "T", "as_of": "2026-03-01", "bias": "bullish",
                         "entry": 100.0, "stop": 95.0, "target1": 110.0, "rr": 2.0, "outcome": "pending"}])
    fut = pd.DataFrame({"date": [date(2026, 3, 2), date(2026, 3, 3)], "open": [101, 104], "high": [103, 111], "low": [99, 102], "close": [102, 110], "volume": [1, 1]})
    out = crt.evaluate_outcomes(log, lambda t: fut)
    assert out["outcome"].iloc[0] == "target1" and out["r_multiple"].iloc[0] == 2.0


def test_stock_read_verdicts():
    df = make_series()
    r = crt.stock_read(df, "KW", capital=3000, today=df["date"].iloc[-1])
    assert r["verdict"] in ("BUY ZONE AT LAST PRICE", "WAIT FOR PULLBACK", "AVOID FOR NOW", "RANGE: BUY LOW END ONLY")
    assert r["support"] < r["last"] < r["resistance"] and len(r["lines"]) >= 4
    # a steadily falling series must be AVOID
    down = df.copy(); down[["open", "high", "low", "close"]] = down[["open", "high", "low", "close"]].values[::-1] * 1.0
    down["close"] = np.linspace(600, 400, len(down)); down["open"] = down["close"] + 1; down["high"] = down["close"] + 3; down["low"] = down["close"] - 3
    assert crt.stock_read(down, "KW", today=df["date"].iloc[-1])["verdict"] == "AVOID FOR NOW"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"[OK] {name}")
    print("All CRT tests passed.")
