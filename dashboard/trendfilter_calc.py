"""TrendFilter calculations for the Alpaca tab: the bot's rule replayed on daily closes, the sell or buy line for the
next check, and the sleeve value over time from the journal's fills. Pure pandas: no Streamlit, no network, no broker.

Rule (fixes/alpaca/strategies/trend_filter.py): on the first session of each month, using the last COMPLETED close,
buy if not held and close > SMA x (1 + band); sell if held and close < SMA x (1 - band); otherwise keep the state.
"""
from __future__ import annotations

import json
import os

import pandas as pd

# Written by trend_filter.py next to its state file; the dashboard mounts that directory read only.
JOURNAL = os.environ.get("LUMIBOT_JOURNAL", "/live/lumibot/strategies/trend_filter_journal.jsonl")


def read_journal(path: str) -> pd.DataFrame:
    """Journal events as a frame with a UTC `ts` column. Unreadable lines are skipped; a missing file gives an empty frame."""
    rows = []
    if path and os.path.exists(path):
        with open(path) as f:
            for line in f:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and "event" in r and "ts" in r:
                    rows.append(r)
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["ts", "event", "symbol"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    return df.dropna(subset=["ts"]).sort_values("ts", kind="stable").reset_index(drop=True)


def with_sma(h: pd.DataFrame, sma: int, band: float) -> pd.DataFrame:
    """h has `date` and `close`, one row per completed session. Adds sma, upper and lower band lines."""
    h = h.sort_values("date").reset_index(drop=True).copy()
    h["sma"] = h["close"].rolling(sma).mean()
    h["upper"], h["lower"] = h["sma"] * (1 + band), h["sma"] * (1 - band)
    return h


def check_days(dates: pd.Series) -> list:
    """First session of each calendar month present in the data: the bot's monthly check day."""
    d = pd.Series(sorted(set(dates)))
    return list(d.groupby(d.map(lambda x: (x.year, x.month))).min())


def rule_history(h: pd.DataFrame, sma: int, band: float) -> pd.DataFrame:
    """Replay the rule on every check day that has a full SMA window before it. The state starts flat at the first
    replayable check, so the first rows can differ from what a bot running since then would hold."""
    h = with_sma(h, sma, band)
    rows, held = [], False
    for d in check_days(h["date"]):
        prior = h[h["date"] < d]
        if len(prior) < sma:
            continue
        last = prior.iloc[-1]
        close, avg = float(last["close"]), float(last["sma"])
        up, lo = avg * (1 + band), avg * (1 - band)
        if not held and close > up:
            action, why = "BUY", f"not held and close {close:,.2f} above the buy line {up:,.2f}"
        elif held and close < lo:
            action, why = "SELL", f"held and close {close:,.2f} below the sell line {lo:,.2f}"
        elif held:
            action, why = "HOLD (in)", f"held and close {close:,.2f} not below the sell line {lo:,.2f}"
        else:
            action, why = "STAY OUT", f"not held and close {close:,.2f} not above the buy line {up:,.2f}"
        rows.append({"check_day": d, "close_date": last["date"], "close": close, "sma": avg, "distance_pct": (close / avg - 1) * 100,
                     "buy_line": up, "sell_line": lo, "held_before": held, "action": action, "why": why})
        held = action in ("BUY", "HOLD (in)")
    return pd.DataFrame(rows, columns=["check_day", "close_date", "close", "sma", "distance_pct", "buy_line", "sell_line",
                                       "held_before", "action", "why"])


def next_trigger(h: pd.DataFrame, sma: int, band: float, held: bool) -> dict | None:
    """The line the next check compares with, at today's SMA. The SMA moves a little each day until the check."""
    h = with_sma(h, sma, band)
    if len(h) < sma:
        return None
    last = h.iloc[-1]
    return trigger(float(last["close"]), float(last["sma"]), band, held, last["date"], "Yahoo")


def trigger(close: float, avg: float, band: float, held: bool, as_of, source: str) -> dict:
    line = avg * (1 - band) if held else avg * (1 + band)
    return {"as_of": as_of, "close": close, "sma": avg, "line": line, "cushion_pct": (close / line - 1) * 100, "source": source,
            "would": ("SELL" if close < line else "HOLD") if held else ("BUY" if close > line else "STAY OUT")}


def bot_signals(journal: pd.DataFrame) -> dict:
    """{symbol: (day, close, sma)} from the latest daily journal line: the numbers the bot itself compares."""
    if journal.empty or "signals" not in journal:
        return {}
    d = journal[journal["event"] == "daily"]
    if d.empty:
        return {}
    last = d.iloc[-1]
    out = {}
    for s, v in (last["signals"] or {}).items():
        if isinstance(v, dict) and v.get("close") is not None and v.get("sma") is not None:
            out[s] = (pd.to_datetime(last["day"]).date(), float(v["close"]), float(v["sma"]))
    return out


def fills(journal: pd.DataFrame) -> pd.DataFrame:
    f = journal[journal["event"] == "fill"].copy() if "event" in journal else pd.DataFrame()
    if f.empty:
        return pd.DataFrame(columns=["ts", "symbol", "side", "qty", "price", "pnl", "realized"])
    f["side"] = f["side"].astype(str).str.lower().map(lambda s: "buy" if s.startswith("buy") else "sell")
    for c in ("qty", "price", "pnl", "realized"):
        f[c] = pd.to_numeric(f.get(c), errors="coerce")
    return f[["ts", "symbol", "side", "qty", "price", "pnl", "realized"]].reset_index(drop=True)


def sleeve_curve(fl: pd.DataFrame, closes: dict, capital: float, day_of, bench_symbol: str = "SPY") -> pd.DataFrame:
    """Daily sleeve value from the first fill on: cash + held qty x that day's close. Also a benchmark: the same capital
    in bench_symbol alone, bought at the bot's first fill price for it (that day's close if it has none) and held.
    closes: {symbol: frame(date, close)}; day_of maps a fill timestamp to its exchange date."""
    if fl.empty or not closes:
        return pd.DataFrame(columns=["date", "value", "pnl", "bench"])
    fl = fl.assign(day=fl["ts"].map(day_of))
    start = fl["day"].min()
    px = pd.DataFrame({s: c.set_index("date")["close"] for s, c in closes.items()}).sort_index()
    px = px[px.index >= start].ffill()
    if px.empty:
        return pd.DataFrame(columns=["date", "value", "pnl", "bench"])
    sign = fl["side"].map({"buy": 1.0, "sell": -1.0})
    out = []
    bf = fl[(fl["symbol"] == bench_symbol) & (fl["side"] == "buy")]
    entry = float(bf["price"].iloc[0]) if len(bf) else (float(px[bench_symbol].iloc[0]) if bench_symbol in px else None)
    units = capital / entry if entry else None
    for d, row in px.iterrows():
        done = fl[fl["day"] <= d]
        sg = sign[done.index]
        cash = capital - float((sg * done["qty"] * done["price"]).sum())
        qty = (sg * done["qty"]).groupby(done["symbol"]).sum()
        value = cash + sum(float(q) * float(row[s]) for s, q in qty.items() if s in row and pd.notna(row[s]))
        bench = units * float(row[bench_symbol]) if units and pd.notna(row.get(bench_symbol)) else None
        out.append({"date": d, "value": value, "pnl": value - capital, "bench": bench})
    return pd.DataFrame(out)


def fill_reasons(journal: pd.DataFrame) -> pd.DataFrame:
    """Each fill with the check decision that caused it (same symbol, latest check at or before the fill)."""
    fl = fills(journal)
    chk = journal[journal["event"] == "check"] if "event" in journal else pd.DataFrame()
    reasons = []
    for _, f in fl.iterrows():
        c = chk[(chk["symbol"] == f["symbol"]) & (chk["ts"] <= f["ts"])] if not chk.empty else chk
        if c.empty:
            reasons.append("No check event in the journal for this fill")
            continue
        c = c.iloc[-1]
        close, avg, band = float(c["close"]), float(c["sma"]), float(c.get("band", 0) or 0)
        line = avg * (1 + band) if f["side"] == "buy" else avg * (1 - band)
        reasons.append(f"{c['month']} check: close {close:,.2f} vs SMA {avg:,.2f} ({(close / avg - 1) * 100:+.1f}%), "
                       f"{'buy' if f['side'] == 'buy' else 'sell'} line {line:,.2f}: {c['reason']}")
    return fl.assign(why=reasons)
