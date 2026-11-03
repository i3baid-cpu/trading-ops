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


def price_unit_factor(price: float, market: str) -> float:
    """Yahoo and most exports quote Boursa Kuwait in fils while capital is in KWD. If a KW price is above 20
    it is in fils, so money amounts (capital x risk%) are converted to fils before sizing."""
    return 1000.0 if (market == "KW" and price > 20) else 1.0


def tick_size(price: float, market: str) -> float:
    if market == "Metals":  # KWD per gram, priced to the fils
        return 0.001
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
        A.reasons.append(f"No CRT sweep in the last {crt_lookback} closed candles (a close back inside the prior candle's range after taking its high or low by >= 1 tick). NO SETUP by rule: no entry price exists.")
        A.reasons.append(f"What would create a setup next session: a trade below {float(last['low']):.4g} (yesterday's low) that closes back above it -> bullish; or a trade above {float(last['high']):.4g} (yesterday's high) that closes back below it -> bearish. Run the check again after that session closes.")
        A.levels += [Level("Watch: bullish trigger", float(last["low"]), "sweep below, close back above"), Level("Watch: bearish trigger", float(last["high"]), "sweep above, close back below")]
        bias = None
    else:
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
        A.levels.append(Level("Fib 0.5 to 0.618", float((f50 + f618) / 2), f"{min(f50, f618):.4g} to {max(f50, f618):.4g} of last impulse"))

    if bias is None:
        return A

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
    unit = price_unit_factor(px, market)
    A.shares = int(math.floor(A.risk_amount * unit / risk_per_share / lot) * lot) if risk_per_share > 0 else 0
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
    A.reasons.append(f"Size: risk {A.risk_amount:.2f} ({risk_pct:.1f}% of {capital:,.0f}){' = ' + format(A.risk_amount * unit, ',.0f') + ' fils' if unit != 1 else ''} / {risk_per_share:.4g} per share = {A.shares} shares.")
    return A


# --------------------------------------------------------------------------- #
# Signal log and outcome evaluation
# --------------------------------------------------------------------------- #
LOG_COLS = ["logged_at", "ticker", "market", "as_of", "bias", "entry", "stop", "target1", "target2", "rr", "shares",
            "risk_amount", "confluence_n", "data_source", "outcome", "outcome_date", "r_multiple",
            "read_verdict", "read_trend", "read_last", "read_support", "read_resistance", "read_rsi"]


def append_log(path: str, a: Analysis, read: dict | None = None) -> None:
    row = {c: None for c in LOG_COLS}
    row.update({k: v for k, v in a.to_row().items() if k in LOG_COLS})
    if read:
        row.update({"read_verdict": read.get("verdict"), "read_trend": read.get("trend"), "read_last": read.get("last"),
                    "read_support": read.get("support"), "read_resistance": read.get("resistance"),
                    "read_rsi": (round(read["rsi"], 1) if read.get("rsi") is not None else None)})
    row["logged_at"] = datetime.utcnow().isoformat(timespec="seconds")
    row["outcome"] = "pending" if a.bias != "NO SETUP" else "no setup"
    try:
        log = pd.read_csv(path)
        for c in LOG_COLS:
            if c not in log.columns:
                log[c] = None
    except FileNotFoundError:
        log = pd.DataFrame(columns=LOG_COLS)
    log = pd.concat([log[LOG_COLS], pd.DataFrame([row])[LOG_COLS]], ignore_index=True)
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


# --------------------------------------------------------------------------- #
# Stock read: trend, momentum, price location, and a buy-now / wait / avoid verdict
# --------------------------------------------------------------------------- #
def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up, dn = d.clip(lower=0), -d.clip(upper=0)
    rs = up.ewm(alpha=1 / n, adjust=False).mean() / dn.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + rs)


def stock_read(df: pd.DataFrame, market: str = "KW", capital: float = 1000.0, risk_pct: float = 1.0,
               today: date | None = None) -> dict:
    """Rule based read on completed daily candles. Returns a dict with trend, momentum, location, verdict, levels."""
    d = closed_only(df, today)
    n = len(d)
    if n < 60:
        return {"verdict": "NOT ENOUGH DATA", "lines": [f"{n} closed candles; need 60."]}
    c = d["close"]
    px = float(c.iloc[-1]); tk = tick_size(px, market)
    e21, e50 = ema(c, 21), ema(c, 50)
    s200 = c.rolling(200).mean() if n >= 200 else None
    r = rsi(c)
    a14 = atr(d)
    hi20, lo20 = d["high"].tail(20).max(), d["low"].tail(20).min()
    ret20 = (px / c.iloc[-21] - 1) * 100
    slope50 = (e50.iloc[-1] / e50.iloc[-11] - 1) * 100
    above200 = (px > s200.iloc[-1]) if s200 is not None else None

    # Trend classification
    if px > e21.iloc[-1] > e50.iloc[-1] and slope50 > 0 and (above200 in (True, None)):
        trend = "UPTREND"
    elif px < e21.iloc[-1] < e50.iloc[-1] and slope50 < 0 and (above200 in (False, None)):
        trend = "DOWNTREND"
    else:
        trend = "SIDEWAYS / MIXED"

    # Support and resistance from swing pivots, order of nearness
    hs, ls = swing_points(d.tail(120).reset_index(drop=True))
    tail = d.tail(120).reset_index(drop=True)
    gap = 0.5 * float(a14.iloc[-1])  # ignore pivots sitting within half an ATR of price: too close to act on
    supports = sorted({float(tail["low"].iloc[i]) for i in ls if tail["low"].iloc[i] < px - gap}, reverse=True)
    resist = sorted({float(tail["high"].iloc[i]) for i in hs if tail["high"].iloc[i] > px + gap})
    sup = supports[0] if supports else float(lo20)
    res = resist[0] if resist else float(hi20)
    ema21 = float(e21.iloc[-1])
    ext_pct = (px / ema21 - 1) * 100
    loc_pct = (px - lo20) / (hi20 - lo20) * 100 if hi20 > lo20 else 50.0
    rsi_v = float(r.iloc[-1])

    lines = [
        f"Trend: {trend}. Close {px:.4g} vs EMA21 {ema21:.4g} and EMA50 {float(e50.iloc[-1]):.4g}; EMA50 slope over 10 sessions {slope50:+.1f}%"
        + (f"; {'above' if above200 else 'below'} the 200 day average {float(s200.iloc[-1]):.4g}." if s200 is not None else "; 200 day average needs more history."),
        f"Momentum: RSI(14) {rsi_v:.0f}, 20 session return {ret20:+.1f}%, price sits at {loc_pct:.0f}% of the 20 session range ({float(lo20):.4g} to {float(hi20):.4g}).",
        f"Nearest support {sup:.4g} ({(px / sup - 1) * 100:+.1f}% below price), nearest resistance {res:.4g} ({(res / px - 1) * 100:+.1f}% above).",
    ]

    # Verdict rules
    stop = sup - tk
    risk_ps = px - stop
    rr_now = (res - px) / risk_ps if risk_ps > 0 else 0.0
    risk_amt = capital * risk_pct / 100
    unit = price_unit_factor(px, market)
    shares_now = int(math.floor(risk_amt * unit / risk_ps)) if risk_ps > 0 else 0
    wait_px = max(ema21, sup) if trend == "UPTREND" else sup
    if trend == "DOWNTREND":
        verdict = "AVOID FOR NOW"
        lines.append(f"Verdict: the chart leans down. Do not buy at the last price. The first sign of change is a daily close back above EMA50 ({float(e50.iloc[-1]):.4g}); re-check then.")
    elif trend == "UPTREND" and ext_pct <= 3.0 and rsi_v < 70 and rr_now >= 1.5:
        verdict = "BUY ZONE AT LAST PRICE"
        lines.append(f"Verdict: uptrend and price is close to support, so the last price {px:.4g} is an acceptable buy. Stop {stop:.4g} (one tick under support), first resistance {res:.4g}, reward to risk {rr_now:.1f}, size {shares_now} shares for {risk_amt:.2f} risk.")
    elif trend == "UPTREND":
        verdict = "WAIT FOR PULLBACK"
        why = "extended above EMA21" if ext_pct > 3.0 else ("RSI above 70" if rsi_v >= 70 else f"reward to risk only {rr_now:.1f} to the next resistance")
        lines.append(f"Verdict: the chart leans up but it is {why}. Wait for a pullback toward {wait_px:.4g} (EMA21 / support) rather than buying at {px:.4g}. If it never pulls back, let it go.")
    else:
        verdict = "RANGE: BUY LOW END ONLY"
        lines.append(f"Verdict: no clear trend. Buying is only reasonable near the range low {float(lo20):.4g} with a stop below it; at {px:.4g} ({loc_pct:.0f}% of the range) the edge is thin. Watch for a daily close above {float(hi20):.4g} (breakout) or below {float(lo20):.4g} (breakdown).")
    lines.append("This read is from completed daily candles. If the market is open, the live price can differ from the last close shown; the rules do not change.")
    return {"verdict": verdict, "trend": trend, "rsi": rsi_v, "ret20": ret20, "support": sup, "resistance": res,
            "ema21": ema21, "ema50": float(e50.iloc[-1]), "sma200": (float(s200.iloc[-1]) if s200 is not None else None),
            "last": px, "stop_now": stop, "rr_now": rr_now, "shares_now": shares_now, "wait_price": wait_px, "lines": lines}


# --------------------------------------------------------------------------- #
# Long term read: weekly trend, distance from the 52 week extremes, staged entry plan
# --------------------------------------------------------------------------- #
def to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    w = d.set_index("date").resample("W-THU").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    return w.reset_index()


def long_term_read(df: pd.DataFrame, market: str = "KW", capital: float = 1000.0, max_position_pct: float = 10.0,
                   today: date | None = None) -> dict:
    """Weekly chart read for a 1 to 2 year holder. Completed weeks only (the current week is dropped)."""
    d = closed_only(df, today)
    w = to_weekly(d)
    w = w.iloc[:-1] if len(w) and pd.Timestamp(w["date"].iloc[-1]).date() >= (today or datetime.utcnow().date()) else w
    n = len(w)
    if n < 30:
        return {"verdict": "NOT ENOUGH HISTORY", "lines": [f"{n} completed weeks; need 30 (about 7 months) for a long term read."]}
    c = w["close"]
    px = float(c.iloc[-1])
    ma40 = c.rolling(40).mean() if n >= 40 else c.rolling(n).mean()
    e10, e30 = ema(c, 10), ema(c, 30)
    hi52, lo52 = float(w["high"].tail(52).max()), float(w["low"].tail(52).min())
    off_high = (px / hi52 - 1) * 100
    off_low = (px / lo52 - 1) * 100
    ma40v = float(ma40.iloc[-1])
    slope = (ma40.iloc[-1] / ma40.iloc[-9] - 1) * 100 if n >= 48 else float("nan")
    ret52 = (px / c.iloc[-53] - 1) * 100 if n >= 53 else float("nan")
    if px > ma40v and e10.iloc[-1] > e30.iloc[-1] and (math.isnan(slope) or slope > 0):
        trend = "LONG TERM UPTREND"
    elif px < ma40v and e10.iloc[-1] < e30.iloc[-1] and (math.isnan(slope) or slope < 0):
        trend = "LONG TERM DOWNTREND"
    else:
        trend = "LONG TERM SIDEWAYS / TURNING"
    dist_ma = (px / ma40v - 1) * 100
    lines = [
        f"Weekly trend: {trend}. Last weekly close {px:.4g} vs 40 week average {ma40v:.4g} ({dist_ma:+.1f}%); 10 week EMA {'above' if e10.iloc[-1] > e30.iloc[-1] else 'below'} 30 week EMA"
        + (f"; 40 week average slope over 8 weeks {slope:+.1f}%." if not math.isnan(slope) else "."),
        f"52 week range {lo52:.4g} to {hi52:.4g}: price is {off_high:+.1f}% from the high and {off_low:+.1f}% above the low"
        + (f"; 52 week return {ret52:+.1f}%." if not math.isnan(ret52) else "."),
    ]
    unit = price_unit_factor(px, market)
    max_pos_money = capital * max_position_pct / 100
    total_shares = int(max_pos_money * unit / px)
    tranche = total_shares // 3
    if trend == "LONG TERM DOWNTREND":
        verdict = "WAIT: DOWNTREND ON THE WEEKLY"
        lines.append(f"Verdict: the weekly chart is in a downtrend. For a 1 to 2 year hold, waiting costs little: the first evidence of a turn is a weekly close above the 40 week average ({ma40v:.4g}). Start the first tranche only after that.")
    elif dist_ma > 15:
        verdict = "EXTENDED: STAGE IN SLOWLY"
        lines.append(f"Verdict: uptrend but {dist_ma:.0f}% above the 40 week average, which is stretched for a slow stock. Buy one tranche now and the rest only on pullbacks toward {ma40v:.4g}.")
    elif trend == "LONG TERM UPTREND":
        verdict = "ACCUMULATION ZONE"
        lines.append(f"Verdict: uptrend and within {dist_ma:.0f}% of the 40 week average, a reasonable zone to accumulate for a long hold. Price being {abs(off_high):.0f}% below the 52 week high is normal here.")
    else:
        verdict = "NEUTRAL: STAGE IN, DO NOT RUSH"
        lines.append(f"Verdict: no clear weekly trend. A staged entry is sensible; a single lump at any price is a bet on timing you do not need to make for a 2 year hold.")
    lines.append(f"Staged plan for a maximum position of {max_position_pct:.0f}% of capital ({max_pos_money:,.0f}): about {total_shares} shares in three tranches of {tranche}: one now or at the next weekly close, one if price reaches the 40 week average ({ma40v:.4g}), one on a weekly close above the 52 week high ({hi52:.4g}) or after the next dividend date, whichever comes first.")
    lines.append(f"Long term invalidation: a weekly close {(lo52):.4g} or below (the 52 week low) means the thesis is wrong; review rather than add.")
    lines.append("The chart cannot judge value. Check the dividend yield and price to earnings in the fundamentals panel before buying; a 2% better entry matters less over two years than whether profits and dividends grow.")
    return {"verdict": verdict, "trend": trend, "last_weekly": px, "ma40": ma40v, "hi52": hi52, "lo52": lo52,
            "off_high": off_high, "dist_ma": dist_ma, "shares_total": total_shares, "tranche": tranche, "lines": lines}
