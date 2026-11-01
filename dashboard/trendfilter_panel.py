"""Alpaca TrendFilter panel: configuration, live signal state from Yahoo closes, next check date, positions.
Read only. Uses the Lumibot config and ledger mounted into the container plus Yahoo daily closes; no broker access."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import streamlit as st

try:
    import data_live as DL
except Exception:  # file mode
    DL = None


@st.cache_data(ttl=900, show_spinner=False)
def _yahoo_daily(sym: str) -> pd.DataFrame | None:
    try:
        import yfinance as yf
        h = yf.Ticker(sym).history(period="15mo", interval="1d", auto_adjust=False, timeout=8)
        if h is None or h.empty:
            return None
        h = h.reset_index().rename(columns={"Date": "date", "Close": "close"})
        h["date"] = pd.to_datetime(h["date"]).dt.tz_localize(None).dt.date
        return h[["date", "close"]]
    except Exception:
        return None


def _nyse_first_trading_day(year: int, month: int) -> date:
    d = date(year, month, 1)
    while d.weekday() >= 5 or (d.month == 1 and d.day == 1) or (d.month == 7 and d.day == 4) or (d.month == 12 and d.day == 25):
        d += timedelta(days=1)
    return d


def next_monthly_check(today: date | None = None) -> date:
    today = today or datetime.now(timezone.utc).date()
    first_this = _nyse_first_trading_day(today.year, today.month)
    if today <= first_this:
        return first_this
    y, m = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return _nyse_first_trading_day(y, m)


def signal_rows(symbols: list[str], sma: int, band: float) -> list[dict]:
    rows = []
    today = datetime.now(timezone.utc).date()
    for s in symbols:
        h = _yahoo_daily(s)
        if h is None or len(h) < sma + 1:
            rows.append({"Symbol": s, "Last close": None, f"SMA{sma}": None, "Distance": None, "Rule says": "Not available (Yahoo)"})
            continue
        h = h[h["date"] < today]  # completed sessions only, same as the strategy
        last, avg = float(h["close"].iloc[-1]), float(h["close"].tail(sma).mean())
        dist = (last / avg - 1) * 100
        if last > avg * (1 + band):
            says = "IN (above the average)"
        elif last < avg * (1 - band):
            says = "FLAT (below the average)"
        else:
            says = "HOLD previous state (inside the band)"
        rows.append({"Symbol": s, "Last close": round(last, 2), f"SMA{sma}": round(avg, 2), "Distance": f"{dist:+.1f}%", "Rule says": says, "As of": str(h["date"].iloc[-1])})
    return rows


def render(kpi, money, tone_of, badge, al_live, al_cfg_file: dict):
    cfg = (DL.load_lumibot_config() if DL else None) or al_cfg_file or {}
    params = cfg.get("params", {})
    symbols = cfg.get("symbols", ["SPY", "QQQ"])
    sma, band = int(params.get("sma", 200)), float(params.get("band_pct", 0.0))
    capital = float(cfg.get("capital_usd", 1000))
    al_pos, al_sum = al_live if al_live else (None, {})

    st.markdown(f"#### Alpaca TrendFilter {badge("<span class='dot paper'></span>PAPER · $" + format(capital, ',.0f') + ' sleeve', 'paper')} &nbsp; <span class='src'>{cfg.get('strategy', 'trend_filter')} · {', '.join(symbols)} · SMA{sma} with {band:.0%} band · {params.get('check', 'daily')} check · paper = {cfg.get('paper')}</span>", unsafe_allow_html=True)
    nxt = next_monthly_check()
    rows = signal_rows(symbols, sma, band)
    held = {} if al_pos is None else {r["symbol"]: r for _, r in al_pos.iterrows()}

    c = st.columns(4)
    with c[0]:
        kpi("Next monthly check", nxt.strftime("%a %d %b"), "first NYSE session of the month, after the open")
    with c[1]:
        ins = sum(1 for r in rows if str(r["Rule says"]).startswith("IN"))
        kpi("Signal now", f"{ins} of {len(symbols)} IN", "from Yahoo closes vs the 200 day average", "pos" if ins == len(symbols) else ("warn" if ins else "neg"))
    with c[2]:
        kpi("Positions held", str(len(held)), ", ".join(held) if held else "none yet", "pos" if held else "")
    with c[3]:
        realized = al_sum.get("realized")
        kpi("Realised P&L", money(realized, signed=True) if realized is not None else "$0.00", "sleeve ledger", tone_of(realized) if realized else "")

    tbl = pd.DataFrame(rows)
    if held:
        mv, unreal = [], []
        for r in rows:
            p = held.get(r["Symbol"])
            if p is not None and r["Last close"]:
                v = float(p["qty"]) * float(r["Last close"])
                mv.append(round(v, 2)); unreal.append(round(v - float(p["cost_usd"]), 2))
            else:
                mv.append(None); unreal.append(None)
        tbl["Qty held"] = [float(held[r["Symbol"]]["qty"]) if r["Symbol"] in held else 0.0 for r in rows]
        tbl["Value (Yahoo close)"] = mv
        tbl["Unrealised"] = unreal
    st.dataframe(tbl, hide_index=True, width="stretch")
    st.caption("The 'Rule says' column recomputes the bot's own rule from Yahoo daily closes so you can see what Monday's check will do. "
               "On the check day the bot buys about 49% of the sleeve per symbol that is IN and sells any held symbol that is FLAT; inside the band it keeps the previous state. "
               "Values use the last Yahoo close, not the broker; the dashboard has no broker access.")
