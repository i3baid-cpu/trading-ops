"""Metals (KWD per gram) tests on synthetic series, no network. Run: python tests/test_metals.py"""
import os
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import crt  # noqa: E402
import metals  # noqa: E402


def ohlc(closes, start=date(2016, 1, 4)):
    d = [start + timedelta(days=i) for i in range(len(closes))]
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"date": d, "open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1.0})


def test_conversion_usd_oz_to_kwd_gram():
    usd = ohlc([metals.TROY_OZ_G * 100] * 3)  # 100 USD per gram
    fx = ohlc([0.30, 0.30, 0.31])
    out = metals.to_kwd_gram(usd, fx)
    assert np.allclose(out["close"].values, [30.0, 30.0, 31.0])
    assert np.isclose(out["high"].iloc[0], 30.0 * 1.01)


def test_bad_fx_quote_is_not_used():
    usd = ohlc([metals.TROY_OZ_G * 100] * 3)
    fx = ohlc([0.30, 3.25, 0.30])  # an inverted quote on day 2 must be skipped, the day before carried forward
    out = metals.to_kwd_gram(usd, fx)
    assert np.allclose(out["close"].values, [30.0, 30.0, 30.0])
    assert len(metals.to_kwd_gram(usd, ohlc([3.25] * 3))) == 0  # no valid rate at all: no price, not an estimate


def test_relabel_and_tick():
    assert metals.relabel("size 12 shares, 0.5 per share") == "size 12 grams, 0.5 per gram"
    assert "dividend" not in metals.relabel("one on a weekly close above the 52 week high (40) or after the next dividend date, whichever comes first.")
    assert crt.tick_size(38.5, "Metals") == 0.001


def test_context_facts():
    n = 3000
    gold = ohlc(np.concatenate([np.linspace(20, 40, n // 2), np.linspace(40, 30, n // 4), np.linspace(30, 45, n - n // 2 - n // 4)]))
    silver = ohlc(gold["close"].values / 80)
    cx = metals.context(gold, "Gold", silver, karat="21K", shop_price=45 * 21 / 24 * 1.08)
    assert np.isclose(cx["price"], 45) and np.isclose(cx["karat_prices"]["21K"], 45 * 21 / 24)
    assert np.isclose(cx["off_high"], 0.0) and np.isclose(cx["ratio"], 80)
    assert np.isclose(cx["premium"], 8.0) and np.isclose(cx["max_dd"], -25.0)
    assert any("back above that high" in l for l in cx["lines"])
    assert metals.context(gold, "Gold")["ratio"] is None


def test_moci_reference_and_premium():
    gold = ohlc(np.linspace(30, 45, 600))
    ref = {"date": "2026-11-02", "karat": {"24K": 44.0, "22K": 40.333, "21K": 38.5, "18K": 33.0},
           "ounce": {"gold": 44.0 * metals.TROY_OZ_G, "silver": 0.55 * metals.TROY_OZ_G}, "silver_gram": 0.55}
    cx = metals.context(gold, "Gold", karat="21K", shop_price=38.5 * 1.05, moci=ref)
    assert np.isclose(cx["moci_ref"], 44.0) and np.isclose(cx["moci_gap"], (45 / 44 - 1) * 100)
    assert np.isclose(cx["premium"], 5.0) and cx["premium_src"] == "MOCI 2026-11-02"  # premium is over MOCI's 21K
    sv = metals.context(ohlc(np.linspace(0.4, 0.5, 600)), "Silver", moci=ref)
    assert np.isclose(sv["moci_ref"], 0.55)
    no = metals.context(gold, "Gold", karat="24K", shop_price=45 * 1.02)
    assert no["moci_ref"] is None and no["premium_src"] == "international" and np.isclose(no["premium"], 2.0)
    assert any("MOCI reference price: Not available" in l for l in no["lines"])


def test_metal_series_runs_through_the_engine():
    rng = np.random.default_rng(5)
    g = ohlc(38 + np.cumsum(rng.normal(0, 0.3, 400)))
    last = g["date"].iloc[-1]
    assert crt.stock_read(g, "Metals", capital=3000, today=last)["verdict"]
    assert crt.long_term_read(g, "Metals", capital=3000, today=last)["verdict"]
    crt.analyze(g, "GOLD" + metals.LOG_SUFFIX, "Metals", capital=3000)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"[OK] {name}")
    print("All metals tests passed.")
