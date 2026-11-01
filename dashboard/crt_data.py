"""
Price data for the CRT stock check. Read only, daily candles.

Sources, in the order the tab offers them:
  1. CSV upload: an export from TickerChart, Boursa Kuwait or any charting app. Columns are detected by name
     (English or Arabic) and the rows are normalised to date, open, high, low, close, volume.
  2. Yahoo Finance via yfinance: Boursa Kuwait tickers use the .KW suffix (KFH.KW, NBK.KW, BOURSA.KW);
     US tickers as is. Daily bars only; intraday for Kuwait is not available there.
TickerChart has no documented public API, so it is supported through its export files, not scraped.
"""
from __future__ import annotations

import io
import re

import pandas as pd

COLMAP = {
    "date": ["date", "time", "datetime", "day", "التاريخ", "تاريخ"],
    "open": ["open", "o", "الافتتاح", "افتتاح", "فتح"],
    "high": ["high", "h", "max", "الأعلى", "اعلى", "أعلى"],
    "low": ["low", "l", "min", "الأدنى", "ادنى", "أدنى"],
    "close": ["close", "c", "last", "adj close", "الإغلاق", "اغلاق", "إغلاق", "الاغلاق"],
    "volume": ["volume", "vol", "v", "الكمية", "كمية", "حجم", "الحجم"],
}


def _match(col: str) -> str | None:
    c = col.strip().lower()
    for key, names in COLMAP.items():
        if c in names or any(c.startswith(n) for n in names if len(n) > 2):
            return key
    return None


def parse_csv(content: bytes | str) -> pd.DataFrame:
    text = content.decode("utf-8-sig", errors="replace") if isinstance(content, bytes) else content
    sep = ";" if text.count(";") > text.count(",") else ("\t" if text.count("\t") > text.count(",") else ",")
    raw = pd.read_csv(io.StringIO(text), sep=sep)
    cols = {}
    for c in raw.columns:
        k = _match(str(c))
        if k and k not in cols:
            cols[k] = c
    missing = [k for k in ("date", "open", "high", "low", "close") if k not in cols]
    if missing:
        raise ValueError(f"Could not find columns {missing}; found {list(raw.columns)}")
    df = pd.DataFrame({k: raw[v] for k, v in cols.items()})
    if "volume" not in df:
        df["volume"] = 0
    for k in ("open", "high", "low", "close", "volume"):
        df[k] = pd.to_numeric(df[k].astype(str).str.replace(",", "").str.replace("٬", ""), errors="coerce")
    raw_dates = df["date"].astype(str).str.strip()
    parsed = pd.to_datetime(raw_dates, errors="coerce", format="ISO8601")
    if parsed.isna().mean() > 0.5:  # not ISO: try day-first (common in GCC exports), then month-first
        parsed = pd.to_datetime(raw_dates, errors="coerce", dayfirst=True)
        if parsed.isna().mean() > 0.5:
            parsed = pd.to_datetime(raw_dates, errors="coerce", dayfirst=False)
    df["date"] = parsed
    df = df.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").reset_index(drop=True)
    df["date"] = df["date"].dt.date
    return df


def yahoo_symbol(ticker: str, market: str) -> str:
    t = ticker.strip().upper()
    if market == "KW" and not t.endswith(".KW"):
        t += ".KW"
    return t


def fetch_yahoo(ticker: str, market: str, period: str = "2y") -> tuple[pd.DataFrame | None, str]:
    try:
        import yfinance as yf
    except ImportError:
        return None, "yfinance is not installed"
    sym = yahoo_symbol(ticker, market)
    try:
        h = yf.Ticker(sym).history(period=period, interval="1d", auto_adjust=False, timeout=8)
    except Exception as e:  # network, symbol
        return None, f"Yahoo fetch failed for {sym}: {e}"
    if h is None or h.empty:
        return None, f"Yahoo returned no data for {sym}"
    df = h.reset_index().rename(columns={"Date": "date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df[["date", "open", "high", "low", "close", "volume"]], f"Yahoo Finance {sym}, daily, fetched now"


def fetch_fundamentals(ticker: str, market: str) -> dict:
    """A few valuation figures from Yahoo, each marked Not available when missing. Read only."""
    keys = {"trailingPE": "P/E (trailing)", "forwardPE": "P/E (forward)", "dividendYield": "Dividend yield",
            "trailingAnnualDividendYield": "Trailing dividend yield", "priceToBook": "Price to book",
            "marketCap": "Market cap", "returnOnEquity": "Return on equity", "revenueGrowth": "Revenue growth (yoy)",
            "payoutRatio": "Payout ratio", "fiftyTwoWeekHigh": "52w high", "fiftyTwoWeekLow": "52w low"}
    out = {v: "Not available" for v in keys.values()}
    try:
        import yfinance as yf
        info = yf.Ticker(yahoo_symbol(ticker, market)).info or {}
    except Exception:
        return out
    for k, label in keys.items():
        v = info.get(k)
        if v is None:
            continue
        if k in ("dividendYield", "trailingAnnualDividendYield", "returnOnEquity", "revenueGrowth", "payoutRatio"):
            out[label] = f"{float(v) * (100 if float(v) < 1 else 1):.1f}%"
        elif k == "marketCap":
            out[label] = f"{float(v) / 1e6:,.0f} M"
        else:
            out[label] = f"{float(v):.4g}"
    return out
