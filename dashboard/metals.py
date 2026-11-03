"""Gold and silver for the Stock Check tab, priced in KWD per gram. Read only, Yahoo daily data.

Yahoo has no KWD gold quote, so the price is built from two series joined by date: the COMEX front month future in
USD per troy ounce (GC=F gold, SI=F silver) and USD/KWD (KWD=X, KWD per 1 USD). The result is the international
(spot equivalent) price of 24K; Kuwaiti shops add a premium and, for jewellery, making charges. The shop check
measures that premium. Futures roll monthly, so the series can show small jumps on roll days.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

import crt_data

METALS = {"Gold": "GC=F", "Silver": "SI=F"}
FX_SYMBOL = "KWD=X"
TROY_OZ_G = 31.1034768
KARATS = {"24K": 24, "22K": 22, "21K": 21, "18K": 18}
FX_RANGE = (0.25, 0.35)  # KWD per USD; outside this band a quote is treated as bad data, never as a rate
PERIOD = "10y"
LOG_SUFFIX = "_KWDG"  # signal log name, e.g. GOLD_KWDG, so it never collides with a stock ticker (GOLD is Barrick)


def to_kwd_gram(usd_oz: pd.DataFrame, fx: pd.DataFrame) -> pd.DataFrame:
    """OHLC in USD per ounce x KWD per USD (same day, else the last valid rate before it) / grams per ounce."""
    m = usd_oz.copy()
    m["date"] = pd.to_datetime(m["date"])
    r = fx[["date", "close"]].rename(columns={"close": "kwd_per_usd"}).copy()
    r["date"] = pd.to_datetime(r["date"])
    r = r[(r["kwd_per_usd"] > FX_RANGE[0]) & (r["kwd_per_usd"] < FX_RANGE[1])]
    m = pd.merge_asof(m.sort_values("date"), r.sort_values("date"), on="date", direction="backward")
    m = m.dropna(subset=["kwd_per_usd"])
    for col in ("open", "high", "low", "close"):
        m[col] = m[col] * m["kwd_per_usd"] / TROY_OZ_G
    m["date"] = m["date"].dt.date
    return m.reset_index(drop=True)


def fetch_kwd_gram(metal: str, period: str = PERIOD) -> tuple[pd.DataFrame | None, str]:
    sym = METALS.get(metal)
    if sym is None:
        return None, f"Unknown metal {metal}"
    m, note = crt_data.fetch_yahoo(sym, "US", period)
    if m is None:
        return None, note
    fx, fx_note = crt_data.fetch_yahoo(FX_SYMBOL, "US", period)
    if fx is None:
        return None, f"USD/KWD rate not available ({fx_note}); no KWD price is shown rather than an estimate"
    out = to_kwd_gram(m, fx)
    if len(out) < 0.9 * len(m):
        return None, f"USD/KWD rate missing or outside {FX_RANGE[0]}-{FX_RANGE[1]} for too many days; no KWD price is shown"
    return (out[["date", "open", "high", "low", "close", "volume"]],
            f"Yahoo Finance {sym} (USD per ounce) x {FX_SYMBOL} ({out['kwd_per_usd'].iloc[-1]:.4f} KWD per USD on the last day), "
            f"KWD per gram of 24K, daily, fetched now")


def relabel(text: str) -> str:
    """The CRT engine writes for shares; for a metal the unit is a gram and there are no dividends or earnings."""
    for a, b in ((" per share", " per gram"), (" shares", " grams"),
                 (" or after the next dividend date, whichever comes first", ""),
                 (", which is stretched for a slow stock", ", which is stretched")):
        text = text.replace(a, b)
    return text


def _fmt(v: float, spec: str = "+.1f", suffix: str = "%") -> str:
    return "Not available" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:{spec}}{suffix}"


def context(d: pd.DataFrame, metal: str, other: pd.DataFrame | None = None, karat: str = "24K", shop_price: float = 0.0,
            moci: dict | None = None) -> dict:
    """Facts a buyer needs besides the chart rules: karat prices, the MOCI reference and the gap to it, returns, distance
    from the high, how much it swings, the worst past fall, the gold/silver ratio and, if given, the shop's premium
    over MOCI (over the international price when MOCI is not available)."""
    c = pd.Series(d["close"].astype(float).values, index=pd.to_datetime(d["date"]))
    px, last = float(c.iloc[-1]), c.index[-1]
    yrs = (last - c.index[0]).days / 365.25

    def ret(days: int) -> float:
        past = c[c.index <= last - pd.Timedelta(days=days)]
        return (px / float(past.iloc[-1]) - 1) * 100 if len(past) else float("nan")

    rets = {"1 month": ret(30), "3 months": ret(91), "1 year": ret(365), "3 years": ret(1095), "5 years": ret(1826), "10 years": ret(3652)}
    hi, hi_date = float(c.max()), c.idxmax()
    off_hi = (px / hi - 1) * 100
    lr = np.log(c[c.index > last - pd.Timedelta(days=365)]).diff().dropna()
    vol = float(lr.std() * math.sqrt(252) * 100) if len(lr) > 100 else float("nan")
    dd = c / c.cummax() - 1
    trough = dd.idxmin()
    peak = c[:trough].idxmax()
    rec = c[trough:][c[trough:] >= c[peak]]
    k_px = {k: px * n / 24 for k, n in KARATS.items()}
    ref = (moci["karat"].get("24K") if metal == "Gold" else moci.get("silver_gram")) if moci else None
    gap = (px / ref - 1) * 100 if ref else None

    lines = [
        f"{metal}: {px:.3f} KWD per gram of 24K at the last daily close ({last:%Y-%m-%d}), the international price. By purity: "
        + ", ".join(f"{k} {v:.3f}" for k, v in k_px.items() if k != "24K") + ". Shops charge more (premium, and making charges on jewellery).",
        "Change in KWD: " + ", ".join(f"{k} {_fmt(v)}" for k, v in rets.items()) + ".",
        f"Highest close in the last {yrs:.0f} years: {hi:.3f} on {hi_date:%Y-%m-%d}; the price is {off_hi:+.1f}% from it."
        + (" Buying near a record is not wrong in itself, but a fall like the one below has to be acceptable to you." if off_hi > -5 else ""),
        f"How much it swings: about {_fmt(vol, '.0f')} a year over the last 12 months (annualised volatility). A normal year, one standard "
        f"deviation, spans roughly {px * (1 - vol / 100):.3f} to {px * (1 + vol / 100):.3f} KWD per gram." if not math.isnan(vol) else "Volatility: Not available.",
        f"Worst fall in this data: {dd.min() * 100:.0f}% from {peak:%Y-%m-%d} to {trough:%Y-%m-%d}; "
        + (f"back above that high by {rec.index[0]:%Y-%m-%d}." if len(rec) else "not yet back above that high."),
    ]
    if ref:
        lines.insert(1, f"MOCI reference for {moci['date']}: {ref:.3f} KWD per gram"
                     + (" of 24K, " + ", ".join(f"{k} {v:.3f}" for k, v in moci["karat"].items() if k != "24K") if metal == "Gold" else "")
                     + f". The price above is {gap:+.1f}% from it. MOCI is one Central Bank of Kuwait price per business day and the "
                     "price above is the US futures close, so a gap of a percent or two is timing, not an error.")
    else:
        lines.insert(1, "MOCI reference price: Not available.")
    ratio = None
    if other is not None and len(other):
        o = pd.Series(other["close"].astype(float).values, index=pd.to_datetime(other["date"]))
        j = pd.concat([c, o], axis=1, join="inner").dropna()
        if len(j) > 250:
            g, s = (j.iloc[:, 0], j.iloc[:, 1]) if metal == "Gold" else (j.iloc[:, 1], j.iloc[:, 0])
            rs = g / s
            ratio = float(rs.iloc[-1])
            lines.append(f"Gold/silver ratio {ratio:.0f} (range in this data {rs.min():.0f} to {rs.max():.0f}, median {rs.median():.0f}). "
                         "Above the median, silver is cheap relative to gold by its own history; below it, gold is. Context, not a timing signal.")
    if ratio is None:
        lines.append("Gold/silver ratio: Not available.")
    prem, src = None, None
    if shop_price and shop_price > 0:
        if ref:
            base, src = (moci["karat"].get(karat) if metal == "Gold" else None) or ref * KARATS[karat] / 24, f"MOCI {moci['date']}"
        else:
            base, src = k_px[karat], "international"
        prem = (shop_price / base - 1) * 100
        lines.append(f"Shop check: {shop_price:.3f} KWD per gram of {karat} against {base:.3f} ({src}) = {prem:+.1f}% premium. "
                     "You pay it on the way in and usually do not get it back when selling; compare shops on this number.")
    lines.append("Known history, not from this data: gold took about 9 years (2011 to 2020) to regain its 2011 high in USD, and silver's "
                 "2011 high stood for well over a decade. Metals pay no income, so the whole return is the price; staged buying "
                 "protects you more than picking the exact day.")
    return {"price": px, "karat_prices": k_px, "off_high": off_hi, "ret_1y": rets["1 year"], "vol": vol,
            "max_dd": float(dd.min() * 100), "ratio": ratio, "premium": prem, "premium_src": src,
            "moci_ref": ref, "moci_gap": gap, "lines": lines}
