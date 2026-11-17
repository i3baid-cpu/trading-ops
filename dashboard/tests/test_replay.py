"""Tests for dashboard/replay.py: the replayed decisions are MemeSleeveV4's rules and use no future data.
Run: python tests/test_replay.py   (synthetic candles, no network)"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np
import pandas as pd
import replay as R

T0 = pd.Timestamp("2026-08-01", tz="UTC")


def candles(closes, vol=None, t0=T0):
    c = np.asarray(closes, dtype=float)
    idx = pd.date_range(t0, periods=len(c), freq="4h")
    o = np.r_[c[0], c[:-1]]
    v = np.full(len(c), 100.0) if vol is None else np.asarray(vol, dtype=float)
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.002, "low": np.minimum(o, c) * 0.998, "close": c, "volume": v}, index=idx)


def gate(up=True, days=400, flip_at=None):
    dates = pd.date_range(T0 - pd.Timedelta(days=days - 60), periods=days, freq="1D")
    close = np.full(days, 110.0 if up else 90.0)
    if flip_at is not None:
        close[dates >= flip_at] = 90.0 if up else 110.0
    close = np.r_[np.full(1, 100.0), close[1:]]
    d = pd.DataFrame({"date": dates, "close": close})
    d.loc[: days // 2, "close"] = 100.0            # history at 100 so the EMA sits near 100
    return R.gate_series(d, dates[-1] + pd.Timedelta(days=2))


def breakout_series():
    flat = [100 + (0.3 if i % 2 else -0.3) for i in range(70)]
    return flat + [103, 106, 109, 112, 114, 116] + [112, 106, 100, 96, 95, 95]


def test_enter_then_exit_follow_the_rules():
    c = breakout_series()
    vol = [100.0] * len(c); vol[70] = 300.0
    d = R.v4_decisions(candles(c, vol), gate(True))
    tags = d["tag"].tolist()
    assert tags[70] == "ENTER", tags[60:]
    assert all(t == "WAIT" for t in tags[20:70]), set(tags[20:70])
    assert "HOLD" in tags[71:76]
    first_out = next(i for i, t in enumerate(tags) if t in ("EXIT", "STOP"))
    assert d["close"].iloc[first_out] < d["ema50"].iloc[first_out]            # a single close under EMA50 exits
    assert abs(d["entry_px"].iloc[70] - d["open"].iloc[71]) < 1e-9            # priced at the next open
    print("[OK] ENTER on the breakout candle, HOLD, then EXIT on one close under EMA50; entry priced at the next open")


def test_each_missing_piece_is_named():
    c = breakout_series()
    d = R.v4_decisions(candles(c), gate(False))
    assert set(d["tag"]) <= {"WARMUP", "WAIT"} and d["why"].iloc[70].startswith("BTC gate shut")
    d = R.v4_decisions(candles(c, [100.0] * len(c)), gate(True))              # breakout without a volume rise
    assert d["tag"].iloc[70] == "WAIT" and "volume" in d["why"].iloc[70]
    d = R.v4_decisions(candles([100.0] * 60 + [99.0, 98.0, 97.0]), gate(True))
    assert d["tag"].iloc[-1] == "WAIT" and "under EMA50" in d["why"].iloc[-1]
    print("[OK] WAIT names the missing piece: gate, EMA50, 20 bar high, volume")


def test_no_future_data():
    c = breakout_series()
    vol = [100.0] * len(c); vol[70] = 300.0
    full = R.v4_decisions(candles(c, vol), gate(True))
    for cut in (30, 60, 70, 71, 75, len(c) - 1):
        part = R.v4_decisions(candles(c[: cut + 1], vol[: cut + 1]), gate(True))
        assert part["tag"].tolist() == full["tag"].tolist()[: cut + 1], cut
        assert np.allclose(part["dist_pct"].dropna().values, full["dist_pct"].iloc[: cut + 1].dropna().values)
    w = candles(c, vol)
    assert abs(full["hh20"].iloc[70] - w["high"].iloc[50:70].max()) < 1e-9      # prior 20 candles, not the current one
    print("[OK] decisions on candle i do not change when later candles are added; the 20 bar high excludes candle i")


def test_daily_gate_is_used_only_after_its_close():
    flip = pd.Timestamp("2026-08-10", tz="UTC")                                 # BTC closes below EMA100 from the 10 Aug candle on
    g = gate(True, flip_at=flip)
    d = R.v4_decisions(candles([100.0] * 80), g)
    seen_down = d.index[d["btc_up"] == False][0]                                # noqa: E712
    assert seen_down + pd.Timedelta(hours=4) == flip + pd.Timedelta(days=1), seen_down   # the 20:00 candle, closing at 00:00 on 11 Aug
    print(f"[OK] the daily candle of {flip:%d %b} first counts on the 4h candle that closes at its end ({seen_down:%d %b %H:%M} open)")


def test_figures_build_and_are_bounded():
    c = breakout_series()
    vol = [100.0] * len(c); vol[70] = 300.0
    d = R.v4_decisions(candles(c, vol), gate(True))
    f = R.replay_fig("DOGE", d)
    assert f is not None and len(f.frames) > 20 and len(f.data) == 5
    r = R.ridge_fig({"DOGE": d["dist_pct"].tail(60).reset_index(drop=True), "BTC gate": d["gap_pct"].tail(60).reset_index(drop=True)})
    assert r is not None and len(r.frames) > 10
    assert R.replay_fig("X", d.head(5)) is None and R.ridge_fig({}) is None
    assert R.build(lambda *a: None, {"DOGE": "DOGE-USD"})["ok"] is False        # Yahoo down: a note, not a crash
    print("[OK] figures build; missing data gives a note")


def test_trendfilter_replay_shows_only_checks_already_made():
    import datetime as dt
    days = [dt.date(2025, 11, 3) + dt.timedelta(days=i) for i in range(260)]
    close = [100 + i * 0.1 for i in range(260)]
    hs = pd.DataFrame({"date": days, "close": close}); hs["sma"] = hs["close"] - 3; hs["upper"] = hs["sma"] * 1.01; hs["lower"] = hs["sma"] * 0.99
    ck = pd.DataFrame({"check_day": [days[30], days[120], days[200]], "action": ["BUY", "HOLD (in)", "SELL"], "close": [103.0, 112.0, 120.0],
                       "distance_pct": [3.1, 2.7, -1.4]})
    f = R.tf_replay_fig(hs, "SPY", 200, 0.01, ck)
    assert f is not None and len(f.frames) > 50 and len(f.data[4].x) == 3
    early = next(fr for fr in f.frames if int(fr.name) < 30)
    assert len(early.data[4].x) == 0 and "no monthly check yet" in early.layout.annotations[0].text      # nothing shown before it happened
    mid = next(fr for fr in f.frames if 120 <= int(fr.name) < 200)
    assert len(mid.data[4].x) == 2 and "SELL" not in mid.layout.annotations[0].text
    assert "SELL" in f.layout.annotations[0].text and ": sell" in f.layout.annotations[0].text
    assert R.tf_replay_fig(hs.head(10), "SPY", 200, 0.01, ck) is None and R.tf_replay_fig(hs, "SPY", 200, 0.01, ck.head(0)) is None
    print("[OK] TrendFilter replay: a check appears only once its day is reached; empty inputs give no figure")


def test_module_stays_read_only():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "replay.py")).read().lower()
    for bad in ("ccxt", "alpaca", "binance.client", "create_order", "requests.post", "api_key", "anthropic", "openai"):
        assert bad not in src, bad
    print("[OK] no exchange client, order call, key or model call in replay.py")


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
    print("All replay tests passed.")
