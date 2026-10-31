"""Tab H: CRT stock check. Rule based, read only, logs every call."""
from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import charts as C
import crt
import crt_data

LOG_PATH = os.environ.get("CRT_LOG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "crt_log.csv"))


def _chart(df: pd.DataFrame, a: crt.Analysis) -> go.Figure:
    d = df.tail(90)
    fig = go.Figure(go.Candlestick(x=pd.to_datetime(d["date"]), open=d["open"], high=d["high"], low=d["low"], close=d["close"],
                                   increasing_line_color=C.POS, decreasing_line_color=C.NEG, name=a.ticker))
    colors = {"CRT range high": C.SERIES[0], "CRT range low": C.SERIES[0], "Sweep extreme": C.WARN, "PDH": C.MUTED, "PDL": C.MUTED}
    for lv in a.levels:
        col = colors.get(lv.name, C.SERIES[6] if "FVG" in lv.name else C.SERIES[4])
        fig.add_hline(y=lv.price, line=dict(color=col, width=1, dash="dot"), annotation_text=lv.name, annotation_font_color=col, annotation_position="right")
    if a.bias != "NO SETUP":
        for y, name, col in [(a.entry, "entry", C.SERIES[0]), (a.stop, "stop", C.NEG), (a.target1, "target 1", C.POS)]:
            fig.add_hline(y=y, line=dict(color=col, width=2), annotation_text=name, annotation_font_color=col, annotation_position="left")
    fig.update_layout(xaxis_rangeslider_visible=False)
    return C.base_layout(fig, height=460, title=f"{a.ticker}: last 90 completed sessions with rule levels", hovermode="x")


def render():
    st.markdown("#### CRT stock check <span class='src'>rule based replacement for the crt-ict-trading-analyzer skill; completed candles only; every call is logged</span>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1, 1, 1])
    with c1:
        ticker = st.text_input("Ticker", "KFH", help="Boursa Kuwait: KFH, NBK, BOURSA, ZAIN... US: SPY, NVDA")
    with c2:
        market = st.selectbox("Market", ["KW", "US"], help="KW applies the Boursa Kuwait fils tick schedule and the .KW Yahoo suffix")
    with c3:
        capital = st.number_input("Capital", min_value=100.0, value=3000.0, step=100.0, help="KWD for KW, USD for US")
    with c4:
        risk_pct = st.number_input("Risk per trade %", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    with c5:
        min_rr = st.number_input("Min reward:risk", min_value=1.0, max_value=5.0, value=2.0, step=0.5)
    src = st.radio("Price data", ["Upload CSV (TickerChart or Boursa Kuwait export)", "Yahoo Finance (daily)"], horizontal=True)
    df, source_note = None, ""
    if src.startswith("Upload"):
        up = st.file_uploader("Daily OHLC CSV", type=["csv", "txt"])
        if up is not None:
            try:
                df = crt_data.parse_csv(up.getvalue())
                source_note = f"CSV upload {up.name}, {len(df)} rows, last {df['date'].iloc[-1]}"
            except ValueError as e:
                st.error(str(e))
    else:
        if st.button("Fetch from Yahoo Finance"):
            df, source_note = crt_data.fetch_yahoo(ticker, market)
            if df is None:
                st.error(source_note)
            st.session_state["crt_df"] = df
            st.session_state["crt_src"] = source_note
        df = st.session_state.get("crt_df", df)
        source_note = st.session_state.get("crt_src", source_note)
    if df is None:
        st.info("Load daily candles to run the check. TickerChart has no public API, so export a CSV from it (or from boursakuwait.com.kw) and upload it here; Yahoo covers Boursa Kuwait daily bars under the .KW suffix.", icon="ℹ️")
        return

    a = crt.analyze(df, ticker.upper(), market, capital=capital, risk_pct=risk_pct, min_rr=min_rr, data_source=source_note)
    left, right = st.columns([1, 1.5])
    with left:
        tone = {"bullish": "pos", "bearish": "neg"}.get(a.bias, "warn")
        st.markdown(f"<div class='kpi {tone}'><div class='l'>Decision</div><div class='v'>{a.bias.upper()}</div><div class='d'>as of close {a.as_of} · {len(a.confluence)} confluence factors</div></div>", unsafe_allow_html=True)
        if a.bias != "NO SETUP":
            k = st.columns(2)
            with k[0]:
                st.markdown(f"<div class='kpi'><div class='l'>Entry / stop</div><div class='v'>{a.entry:.4g} / {a.stop:.4g}</div><div class='d'>R:R {a.rr:.2f} to target 1</div></div>", unsafe_allow_html=True)
            with k[1]:
                st.markdown(f"<div class='kpi'><div class='l'>Targets</div><div class='v'>{a.target1:.4g}{(' / ' + format(a.target2, '.4g')) if a.target2 else ''}</div><div class='d'>size {a.shares} shares, risk {a.risk_amount:.2f}</div></div>", unsafe_allow_html=True)
        st.markdown("<div class='panel'><h4>Rule based explanation</h4><div class='rule' style='white-space:pre-wrap'>" + crt.explain(a) + "</div></div>", unsafe_allow_html=True)
        lv = pd.DataFrame([{"Level": l.name, "Price": l.price, "Note": l.note} for l in a.levels])
        if len(lv):
            st.dataframe(lv, hide_index=True, width="stretch", column_config={"Price": st.column_config.NumberColumn(format="%.5g")})
        if st.button("Log this signal"):
            crt.append_log(LOG_PATH, a)
            st.success(f"Logged to {os.path.basename(LOG_PATH)}")
    with right:
        st.plotly_chart(_chart(df, a), width="stretch", config={"displaylogo": False})

    st.markdown("#### Signal log and track record")
    try:
        log = pd.read_csv(LOG_PATH)
    except FileNotFoundError:
        log = pd.DataFrame(columns=crt.LOG_COLS)
    if len(log):
        done = log[log["outcome"].isin(["stop", "target1", "expired"])]
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"<div class='kpi'><div class='l'>Signals logged</div><div class='v'>{len(log)}</div><div class='d'>{int((log['outcome']=='no setup').sum())} no setup</div></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='kpi'><div class='l'>Resolved</div><div class='v'>{len(done)}</div><div class='d'>{int((log['outcome']=='pending').sum())} pending</div></div>", unsafe_allow_html=True)
        with m3:
            wr = (done["outcome"] == "target1").mean() * 100 if len(done) else float("nan")
            st.markdown(f"<div class='kpi'><div class='l'>Hit target 1</div><div class='v'>{wr:.0f}%</div><div class='d'>judge after 30 resolved</div></div>" if len(done) else "<div class='kpi'><div class='l'>Hit target 1</div><div class='v'>Not available</div><div class='d'>no resolved signals</div></div>", unsafe_allow_html=True)
        with m4:
            er = done["r_multiple"].mean() if len(done) else float("nan")
            st.markdown(f"<div class='kpi'><div class='l'>Avg R multiple</div><div class='v'>{er:+.2f}</div><div class='d'>including expired</div></div>" if len(done) else "<div class='kpi'><div class='l'>Avg R multiple</div><div class='v'>Not available</div><div class='d'></div></div>", unsafe_allow_html=True)
        if st.button("Update outcomes from Yahoo Finance"):
            upd = crt.evaluate_outcomes(log, lambda t: crt_data.fetch_yahoo(t, market)[0])
            upd.to_csv(LOG_PATH, index=False)
            log = upd
            st.success("Outcomes updated")
        st.dataframe(log.sort_values("logged_at", ascending=False), hide_index=True, width="stretch")
    else:
        st.caption("No signals logged yet. Log each check you act on; after 30 resolved signals the hit rate and average R tell you whether the method has value.")
