"""
CRT / ICT stock check, rule based and deterministic.

Replaces the discretionary `crt-ict-trading-analyzer` skill with code: every concept has a numeric
definition, only CLOSED candles are used, the same data always gives the same answer, "NO SETUP" is a
first class outcome, and every call can be logged so the method can be judged after N signals.

Inputs: a daily OHLC DataFrame with columns date, open, high, low, close, volume (date ascending).
Outputs: an Analysis dataclass (bias, levels, size, confluence list, reasons) plus a plain-language
explanation built only from the rules below. No AI commentary is generated here.

Definitions (all on closed candles):
  Range candle (CRT)     the previous completed HTF candle (daily by default; weekly optional).
  Sweep                  a later closed candle trades beyond the range high (or low) by >= 1 tick and CLOSES back
                         inside the range. High sweep -> bearish bias, low sweep -> bullish bias.
                         Valid only if it happened within the last `crt_lookback` closed candles.
  Liquidity (BSL/SSL)    equal highs / equal lows: two or more swing highs (lows) within `eq_tol` of each other
                         in the last `liq_lookback` candles. Levels not yet traded through are "resting".
  FVG                    three candle gap: c1.high < c3.low (bullish) or c1.low > c3.high (bearish), gap size >=
                         `fvg_min_pct` of price; unfilled if no later candle traded fully through it.
  Displacement           a move of >= `disp_atr` x ATR(14) over at most 3 candles.
  Order block            the last candle of the opposite colour before a displacement; valid until traded through.
  PDH / PDL              previous completed session high and low.
  EMA alignment          EMA9 > EMA21 > EMA50 bullish, the reverse bearish, otherwise mixed.
  Fib zone               0.5 to 0.618 retracement of the last impulse (swing pivot to swing pivot).
Decision:
  bias requires a valid CRT sweep. Without it the answer is NO SETUP, whatever the other concepts say.
  entry   bullish: top of the nearest unfilled bullish FVG inside the range, else range low + 1 tick;
          bearish: mirror.
  stop    one tick beyond the sweep extreme.
  target1 opposite side of the range; target2 nearest resting liquidity beyond target1 (if any).
  reward to risk to target1 must be >= `min_rr`, otherwise NO SETUP.
  size    floor(risk_amount / (entry - stop) / lot) * lot.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import date, datetime

import numpy as np
import pandas as pd

# Boursa Kuwait price tick schedule in fils (verify against the current rulebook before relying on it).
KW_TICKS = [(100, 0.1), (250, 0.5), (500, 1.0), (1000, 2.0), (2000, 5.0), (float("inf"), 10.0)]


def tick_size(price: float, market: str) -> float:
    if market == "KW":
        for ceiling, tick in KW_TICKS:
            if price < ceiling:
                return tick
    return 0.01


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def swing_points(df: pd.DataFrame, k: int = 2):
    """Fractal pivots: a high higher than k candles each side (same for lows). Index positions."""
    highs, lows = [], []
    h, l = df["high"].values, df["low"].values
    for i in range(k, len(df) - k):
        if h[i] == max(h[i - k:i + k + 1]) and (h[i] > h[i - k:i]).all():
            highs.append(i)
        if l[i] == min(l[i - k:i + k + 1]) and (l[i] < l[i - k:i]).all():
            lows.append(i)
    return highs, lows


@dataclass
class Level:
    name: str
    price: float
    note: str = ""


@dataclass
class Analysis:
    ticker: str
    market: str
    as_of: str
    last_close: float
    tick: float
    bias: str                      # "bullish" | "bearish" | "NO SETUP"
    reasons: list[str] = field(default_factory=list)
    confluence: list[str] = field(default_factory=list)
    levels: list[Level] = field(default_factory=list)
    entry: float | None = None
    stop: float | None = None
    target1: float | None = None
    target2: float | None = None
    rr: float | None = None
    shares: int | None = None
    risk_amount: float | None = None
    ema_state: str = ""
    data_source: str = ""
    params: dict = field(default_factory=dict)

    def to_row(self) -> dict:
        d = asdict(self)
        d.pop("levels"); d.pop("reasons"); d.pop("confluence"); d.pop("params")
        d["confluence_n"] = len(self.confluence)
        return d


def closed_only(df: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    """Drop a candle dated today: the session may still be open. Daily data only."""
    today = today or datetime.utcnow().date()
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"]).dt.date
    return d[d["date"] < today].reset_index(drop=True)


def analyze(df: pd.DataFrame, ticker: str, market: str = "KW", capital: float = 1000.0, risk_pct: float = 1.0,
            lot: int = 1, crt_lookback: int = 3, liq_lookback: int = 40, eq_tol: float = 0.002,
            fvg_min_pct: float = 0.002, disp_atr: float = 1.5, min_rr: float = 2.0, data_source: str = "",
            today: date | None = None) -> Analysis:
    d = closed_only(df, today)
    if len(d) < 60:
        return Analysis(ticker, market, "", float("nan"), 0.0, "NO SETUP", reasons=[f"Only {len(d)} closed daily candles; need 60."], data_source=data_source)
    d["ema9"], d["ema21"], d["ema50"] = ema(d["close"], 9), ema(d["close"], 21), ema(d["close"], 50)
    d["atr"] = atr(d)
    last = d.iloc[-1]
    px = float(last["close"])
    tk = tick_size(px, market)
    A = Analysis(ticker, market, str(last["date"]), px, tk, "NO SETUP", data_source=data_source,
                 params=dict(crt_lookback=crt_lookback, liq_lookback=liq_lookback, eq_tol=eq_tol, fvg_min_pct=fvg_min_pct,
                             disp_atr=disp_atr, min_rr=min_rr, capital=capital, risk_pct=risk_pct))

    # EMA state
    if last["ema9"] > last["ema21"] > last["ema50"]:
        A.ema_state = "bullish (EMA9 > EMA21 > EMA50)"
    elif last["ema9"] < last["ema21"] < last["ema50"]:
        A.ema_state = "bearish (EMA9 < EMA21 < EMA50)"
    else:
        A.ema_state = "mixed"

    # PDH / PDL
    A.levels += [Level("PDH", float(last["high"]), "previous completed session high"), Level("PDL", float(last["low"]), "previous completed session low")]

    # CRT: for each of the last `crt_lookback` closed candles, check a sweep of the candle before it.
    sweep = None
    for i in range(len(d) - crt_lookback, len(d)):
        rng, c = d.iloc[i - 1], d.iloc[i]
        if c["high"] >= rng["high"] + tk and rng["low"] <= c["close"] <= rng["high"]:
            sweep = dict(kind="high", idx=i, range_high=float(rng["high"]), range_low=float(rng["low"]), extreme=float(c["high"]), date=str(c["date"]))
        elif c["low"] <= rng["low"] - tk and rng["low"] <= c["close"] <= rng["high"]:
            sweep = dict(kind="low", idx=i, range_high=float(rng["high"]), range_low=float(rng["low"]), extreme=float(c["low"]), date=str(c["date"]))
    if sweep is None:
        A.reasons.append(f"No CRT sweep in the last {crt_lookback} closed candles (a close back inside the prior candle's range after taking its high or low by >= 1 tick). NO SETUP by rule.")
        return A
    A.levels += [Level("CRT range high", sweep["range_high"]), Level("CRT range low", sweep["range_low"]), Level("Sweep extreme", sweep["extreme"], sweep["date"])]
    bias = "bearish" if sweep["kind"] == "high" else "bullish"
    A.reasons.append(f"CRT: candle of {sweep['date']} took the prior {sweep['kind']} ({sweep['extreme']:.4g}) and closed back inside {sweep['range_low']:.4g} to {sweep['range_high']:.4g}: {bias} bias.")

    # Liquidity: equal highs / lows among swing points
    hs, ls = swing_points(d.tail(liq_lookback).reset_index(drop=True))
    tail = d.tail(liq_lookback).reset_index(drop=True)
    def equal_levels(idx, col):
        vals = [float(tail[col].iloc[i]) for i in idx]
        out = []
        for i, v in enumerate(vals):
            if any(abs(v - w) / v <= eq_tol for j, w in enumerate(vals) if j != i):
                out.append(v)
        return sorted(set(round(v, 6) for v in out))
    bsl = [v for v in equal_levels(hs, "high") if v > px]
    ssl = [v for v in equal_levels(ls, "low") if v < px]
    for v in bsl[:2]:
        A.levels.append(Level("BSL (equal highs)", v, "resting buy side liquidity"))
    for v in ssl[-2:]:
        A.levels.append(Level("SSL (equal lows)", v, "resting sell side liquidity"))

    # FVGs (unfilled), scanned over the last liq_lookback candles
    fvgs = []
    for i in range(len(d) - liq_lookback, len(d) - 2):
        c1, c3 = d.iloc[i], d.iloc[i + 2]
        if c1["high"] < c3["low"] and (c3["low"] - c1["high"]) / px >= fvg_min_pct:
            lo, hi = float(c1["high"]), float(c3["low"])
            if not (d["low"].iloc[i + 3:] <= lo).any():
                fvgs.append(("bullish", lo, hi))
        elif c1["low"] > c3["high"] and (c1["low"] - c3["high"]) / px >= fvg_min_pct:
            lo, hi = float(c3["high"]), float(c1["low"])
            if not (d["high"].iloc[i + 3:] >= hi).any():
                fvgs.append(("bearish", lo, hi))
    for kind, lo, hi in fvgs[-3:]:
        A.levels.append(Level(f"{kind} FVG", (lo + hi) / 2, f"{lo:.4g} to {hi:.4g}, unfilled"))

    # Order block before the last displacement
    ob = None
    for i in range(len(d) - 2, max(len(d) - liq_lookback, 3), -1):
        move = d["close"].iloc[i] - d["close"].iloc[i - 3]
        if abs(move) >= disp_atr * d["atr"].iloc[i]:
            direction = "bullish" if move > 0 else "bearish"
            for j in range(i - 3, max(i - 10, 0), -1):
                c = d.iloc[j]
                if (direction == "bullish" and c["close"] < c["open"]) or (direction == "bearish" and c["close"] > c["open"]):
                    ob = (direction, float(c["low"]), float(c["high"]))
                    break
            break
    if ob:
        A.levels.append(Level(f"{ob[0]} order block", (ob[1] + ob[2]) / 2, f"{ob[1]:.4g} to {ob[2]:.4g}"))

    # Fib zone of the last impulse
    hs_all, ls_all = swing_points(d)
    if hs_all and ls_all:
        hi_i, lo_i = hs_all[-1], ls_all[-1]
        a, b = (d["low"].iloc[lo_i], d["high"].iloc[hi_i]) if lo_i < hi_i else (d["high"].iloc[hi_i], d["low"].iloc[lo_i])
        f50, f618 = b - 0.5 * (b - a), b - 0.618 * (b - a)
        A.levels.append(Level("Fib 0.5 to 0.618", (f50 + f618) / 2, f"{min(f50, f618):.4g} to {max(f50, f618):.4g} of last impulse"))

    # Confluence (informational; the decision rests on CRT + reward to risk)
    if (bias == "bullish" and A.ema_state.startswith("bullish")) or (bias == "bearish" and A.ema_state.startswith("bearish")):
        A.confluence.append("EMA alignment agrees with bias")
    if any(k == bias for k, _, _ in fvgs):
        A.confluence.append(f"unfilled {bias} FVG present")
    if ob and ob[0] == bias:
        A.confluence.append(f"{bias} order block present")
    if (bias == "bullish" and ssl) or (bias == "bearish" and bsl):
        A.confluence.append("liquidity was resting on the swept side")

    # Levels and size
    rh, rl, ext = sweep["range_high"], sweep["range_low"], sweep["extreme"]
    same_fvg = [(lo, hi) for k, lo, hi in fvgs if k == bias and rl <= (lo + hi) / 2 <= rh]
    if bias == "bullish":
        entry = same_fvg[-1][1] if same_fvg else rl + tk
        stop, t1 = ext - tk, rh
        t2 = bsl[0] if bsl else None
    else:
        entry = same_fvg[-1][0] if same_fvg else rh - tk
        stop, t1 = ext + tk, rl
        t2 = ssl[-1] if ssl else None
    risk_per_share = abs(entry - stop)
    rr = abs(t1 - entry) / risk_per_share if risk_per_share > 0 else 0.0
    A.entry, A.stop, A.target1, A.target2, A.rr = entry, stop, t1, t2, rr
    A.risk_amount = capital * risk_pct / 100.0
    A.shares = int(math.floor(A.risk_amount / risk_per_share / lot) * lot) if risk_per_share > 0 else 0
    if rr < min_rr:
        A.reasons.append(f"Reward to risk to target 1 is {rr:.2f}, below the {min_rr:.1f} minimum. NO SETUP by rule.")
        A.bias = "NO SETUP"
        return A
    if A.shares < lot:
        A.reasons.append(f"Risk {A.risk_amount:.2f} buys fewer than one lot at {risk_per_share:.4g} risk per share. NO SETUP by rule.")
        A.bias = "NO SETUP"
        return A
    A.bias = bias
    A.reasons.append(f"Entry {entry:.4g}, stop {stop:.4g} (one tick beyond the sweep extreme), target 1 {t1:.4g} (other side of the range), R:R {rr:.2f}.")
    A.reasons.append(f"Size: risk {A.risk_amount:.2f} ({risk_pct:.1f}% of {capital:,.0f}) / {risk_per_share:.4g} per share = {A.shares} shares.")
    return A


# --------------------------------------------------------------------------- #
# Signal log and outcome evaluation
# --------------------------------------------------------------------------- #
LOG_COLS = ["logged_at", "ticker", "market", "as_of", "bias", "entry", "stop", "target1", "target2", "rr", "shares",
            "risk_amount", "confluence_n", "data_source", "outcome", "outcome_date", "r_multiple"]


def append_log(path: str, a: Analysis) -> None:
    row = {c: None for c in LOG_COLS}
    row.update({k: v for k, v in a.to_row().items() if k in LOG_COLS})
    row["logged_at"] = datetime.utcnow().isoformat(timespec="seconds")
    row["outcome"] = "pending" if a.bias != "NO SETUP" else "no setup"
    try:
        log = pd.read_csv(path)
    except FileNotFoundError:
        log = pd.DataFrame(columns=LOG_COLS)
    log = pd.concat([log, pd.DataFrame([row])[LOG_COLS]], ignore_index=True)
    log.to_csv(path, index=False)


def evaluate_outcomes(log: pd.DataFrame, fetch_ohlc, horizon_sessions: int = 10) -> pd.DataFrame:
    """For pending signals, fetch later sessions and record which of stop / target1 was hit first (by high/low).
    Both in the same session counts as a stop (conservative). Expired after `horizon_sessions` -> 'expired'."""
    out = log.copy()
    for i, r in out[out["outcome"] == "pending"].iterrows():
        df = fetch_ohlc(r["ticker"])
        if df is None:
            continue
        d = df[pd.to_datetime(df["date"]).dt.date > pd.to_datetime(r["as_of"]).date()].head(horizon_sessions)
        res, when, rm = None, None, None
        for _, c in d.iterrows():
            bull = r["bias"] == "bullish"
            hit_stop = c["low"] <= r["stop"] if bull else c["high"] >= r["stop"]
            hit_t1 = c["high"] >= r["target1"] if bull else c["low"] <= r["target1"]
            if hit_stop:
                res, when, rm = "stop", c["date"], -1.0
                break
            if hit_t1:
                res, when, rm = "target1", c["date"], float(r["rr"])
                break
        if res is None and len(d) >= horizon_sessions:
            res, when = "expired", d["date"].iloc[-1]
            last = float(d["close"].iloc[-1])
            rm = (last - r["entry"]) / abs(r["entry"] - r["stop"]) * (1 if r["bias"] == "bullish" else -1)
        if res:
            out.loc[i, ["outcome", "outcome_date", "r_multiple"]] = [res, str(when), rm]
    return out


def explain(a: Analysis) -> str:
    lines = [f"{a.ticker} ({a.market}) as of close {a.as_of}: last {a.last_close:.4g}, tick {a.tick:g}.",
             f"EMA state: {a.ema_state}."]
    lines += a.reasons
    if a.confluence:
        lines.append("Confluence: " + "; ".join(a.confluence) + ".")
    lines.append("All candles used are completed sessions. Rules and parameters are fixed in crt.py; the same data gives the same answer.")
    lines.append("Educational pattern analysis, not financial advice. ICT/CRT concepts are hypotheses; the signal log is what tests them.")
    return "\n".join(lines)
