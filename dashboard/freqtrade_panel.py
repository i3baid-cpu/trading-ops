"""Freqtrade tab: MemeSleeveV3 state, the BTC gate and per pair entry conditions recomputed from Yahoo data,
recent trades and the dry run equity curve. Read only; Yahoo is used because the dashboard has no exchange access."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

import charts as C
import data as D

PAIRS = {"DOGE": "DOGE-USD", "PEPE": "PEPE24478-USD", "SHIB": "SHIB-USD", "FLOKI": "FLOKI-USD"}


@st.cache_data(ttl=900, show_spinner=False)
def _yahoo(sym: str, period: str, interval: str) -> pd.DataFrame | None:
    try:
        import yfinance as yf
        h = yf.Ticker(sym).history(period=period, interval=interval, auto_adjust=False, timeout=8)
        if h is None or h.empty:
            return None
        h = h.reset_index()
        h = h.rename(columns={h.columns[0]: "date", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
        h["date"] = pd.to_datetime(h["date"], utc=True)
        return h[["date", "open", "high", "low", "close", "volume"]]
    except Exception:
        return None


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def gate_status() -> dict:
    """BTC daily close vs EMA100 on completed days (same rule as MemeSleeveV3's informative filter)."""
    h = _yahoo("BTC-USD", "1y", "1d")
    if h is None or len(h) < 110:
        return {"ok": False, "note": "BTC daily data not available from Yahoo"}
    today = datetime.now(timezone.utc).date()
    h = h[h["date"].dt.date < today]
    close, ema = float(h["close"].iloc[-1]), float(_ema(h["close"], 100).iloc[-1])
    return {"ok": True, "open": close > ema, "close": close, "ema100": ema, "gap_pct": (close / ema - 1) * 100, "as_of": str(h["date"].iloc[-1].date())}


def pair_rows() -> list[dict]:
    """Last completed 4h candle vs EMA50, prior 20 bar high and 20 bar mean volume, from Yahoo 1h bars resampled to 4h."""
    rows = []
    now = datetime.now(timezone.utc)
    for name, sym in PAIRS.items():
        h = _yahoo(sym, "60d", "1h")
        if h is None or len(h) < 240:
            rows.append({"Pair": name, "4h close": None, "EMA50": None, "Prior 20 bar high": None, "Volume vs mean": None, "Breakout": "Not available (Yahoo)"})
            continue
        w = h.set_index("date").resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        w = w[w.index + pd.Timedelta(hours=4) <= now]  # completed 4h candles only
        if len(w) < 60:
            rows.append({"Pair": name, "4h close": None, "EMA50": None, "Prior 20 bar high": None, "Volume vs mean": None, "Breakout": "Not available"})
            continue
        ema50 = float(_ema(w["close"], 50).iloc[-1])
        hh20 = float(w["high"].iloc[-21:-1].max())
        vol_ratio = float(w["volume"].iloc[-1] / w["volume"].iloc[-21:-1].mean()) if w["volume"].iloc[-21:-1].mean() > 0 else float("nan")
        close = float(w["close"].iloc[-1])
        fired = close > ema50 and close > hh20 and vol_ratio > 1.0
        rows.append({"Pair": name, "As of": w.index[-1].strftime("%d %b %H:%M"), "4h close": f"{close:.6g}", "EMA50": f"{ema50:.6g}", "Prior 20 bar high": f"{hh20:.6g}",
                     "Volume vs mean": f"{vol_ratio:.2f}x" if vol_ratio == vol_ratio else "n/a",
                     "Breakout": "YES, entry condition met" if fired else ("above EMA50, no breakout" if close > ema50 else "below EMA50")})
    return rows


def render(X, ALL, kpi, money, num, pct, tone_of, badge, TZ, fmt_time):
    ft_all = ALL[ALL["system"] == "Freqtrade"]
    m_ft = D.compute_metrics(ft_all)
    cfg = X["ft_cfg"]
    live = D.LIVE
    st.markdown(f"#### Freqtrade {badge("<span class='dot dry'></span>DRY RUN · simulated", 'dry')} &nbsp; <span class='src'>{cfg['strategy']} · {cfg['timeframe']} · {cfg['exchange']} {cfg['trading_mode']} · stake {cfg['stake_amount']} USDT · max {int(cfg['max_open_trades'])} open · Telegram alerts on</span>", unsafe_allow_html=True)

    g = gate_status()
    c = st.columns(4)
    with c[0]:
        if g["ok"]:
            kpi("BTC gate (daily EMA100)", "OPEN" if g["open"] else "SHUT", f"BTC {g['close']:,.0f} vs {g['ema100']:,.0f} ({g['gap_pct']:+.2f}%) · daily close of {g['as_of']} · next update 00:00 UTC", "pos" if g["open"] else "neg")
        else:
            kpi("BTC gate (daily EMA100)", "Not available", g["note"], "warn")
    with c[1]:
        openers = int((ft_all["status"] == "open").sum())
        kpi("Open dry run trades", f"{openers} of {int(cfg['max_open_trades'])}", "slots in use", "warn" if openers else "")
    with c[2]:
        kpi("Net after fees", money(m_ft.net_pnl, currency="USDT", signed=True), f"{m_ft.closed} closed · PF {num(m_ft.profit_factor)}", tone_of(m_ft.net_pnl))
    with c[3]:
        kpi("Max drawdown", money(m_ft.max_drawdown, currency="USDT"), f"win rate {pct(m_ft.win_rate, signed=False, digits=1)} · avg hold {D.fmt_td(m_ft.avg_duration)}", "warn")

    if live:
        import data_live as DL
        v3 = ft_all[ft_all["entry_time"] >= DL.V3_START]
        st.markdown(f"<div class='panel'><span class='dot dry'></span> <b>MemeSleeveV3 forward test</b> since {DL.V3_START:%d %b %Y %H:%M} UTC · {len(v3)} V3 trade(s) so far · {DL.V3_NOTE}<br><span class='src'>V3 buys only while the BTC gate is open and a pair closes a 4h candle above its prior 20 bar high on above average volume; exits on two 4h closes below EMA50, the gate shutting, a 15% stop, or a 10% trailing stop after +20%. Silence while the gate is shut is the filter working.</span></div>", unsafe_allow_html=True)

    st.markdown("<div class='src'>Two clocks: the BTC gate uses the last <b>completed daily</b> candle, so it updates once a day at 00:00 UTC (03:00 Kuwait) and shows yesterday's date until then. The pair checks below use the last <b>completed 4h</b> candle and update six times a day. A trade needs both: gate open on the daily, breakout on the 4h.</div>", unsafe_allow_html=True)
    rows = pair_rows()
    asof = next((r.get("As of") for r in rows if r.get("As of")), None)
    st.markdown(f"#### Entry conditions right now <span class='src'>last completed 4h candle{(' opened ' + asof + ' UTC') if asof else ''}; recomputed from Yahoo 1h bars resampled to 4h; the bot uses Binance candles so small differences are normal</span>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(rows).drop(columns=["As of"], errors="ignore"), hide_index=True, width="stretch")

    left, right = st.columns([1.2, 1])
    with left:
        ec = D.equity_curve(ft_all)
        st.plotly_chart(C.equity_fig(ec, "Freqtrade dry run", "USDT"), width="stretch", config={"displaylogo": False})
    with right:
        recent = ft_all.sort_values("exit_time", ascending=False).head(8)
        tbl = pd.DataFrame({"ID": recent["trade_id"], "Pair": recent["symbol"], "Strategy": recent["strategy"].str.split(" ").str[0],
                            "Entry": recent["entry_time"].map(lambda t: fmt_time(t, TZ)), "Exit": recent["exit_time"].map(lambda t: fmt_time(t, TZ)),
                            "P&L": recent["pnl_usd"], "%": recent["pnl_pct"], "Exit reason": recent["exit_reason_code"]})
        st.markdown("<h4 style='margin-top:0.6rem'>Recent trades</h4>", unsafe_allow_html=True)
        st.dataframe(tbl, hide_index=True, width="stretch", column_config={"P&L": st.column_config.NumberColumn(format="%+.3f"), "%": st.column_config.NumberColumn(format="%+.2f")})
