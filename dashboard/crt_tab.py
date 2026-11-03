"""Tab H: CRT stock check. Rule based, read only, logs every call."""
from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import charts as C
import crt
import crt_data
import metals

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


@st.cache_data(ttl=900, show_spinner=False)
def _metal(name: str):
    return metals.fetch_kwd_gram(name)


def _metal_panel(df: pd.DataFrame, metal: str, karat: str, shop_price: float) -> None:
    other = next(m for m in metals.METALS if m != metal)
    cx = metals.context(df, metal, _metal(other)[0], karat, shop_price)
    st.markdown(f"#### {metal} in KWD per gram <span class='src'>international price from Yahoo, converted with USD/KWD; completed days only</span>", unsafe_allow_html=True)
    k = st.columns(4)
    with k[0]:
        st.markdown(f"<div class='kpi'><div class='l'>{karat} per gram</div><div class='v' style='font-size:16px'>{cx['karat_prices'][karat]:.3f} KWD</div><div class='d'>24K {cx['price']:.3f}</div></div>", unsafe_allow_html=True)
    with k[1]:
        st.markdown(f"<div class='kpi'><div class='l'>From 10 year high</div><div class='v' style='font-size:16px'>{cx['off_high']:+.1f}%</div><div class='d'>1 year {metals._fmt(cx['ret_1y'])}</div></div>", unsafe_allow_html=True)
    with k[2]:
        st.markdown(f"<div class='kpi'><div class='l'>Swings a year</div><div class='v' style='font-size:16px'>{metals._fmt(cx['vol'], '.0f')}</div><div class='d'>worst fall {cx['max_dd']:.0f}%</div></div>", unsafe_allow_html=True)
    with k[3]:
        if cx["premium"] is not None:
            st.markdown(f"<div class='kpi {'neg' if cx['premium'] > 10 else ''}'><div class='l'>Shop premium</div><div class='v' style='font-size:16px'>{cx['premium']:+.1f}%</div><div class='d'>over international {karat}</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='kpi'><div class='l'>Gold/silver ratio</div><div class='v' style='font-size:16px'>{'Not available' if cx['ratio'] is None else format(cx['ratio'], '.0f')}</div><div class='d'>enter a shop price for the premium</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='panel'><div class='rule' style='white-space:pre-wrap'>" + "\n".join(cx["lines"]) + "</div></div>", unsafe_allow_html=True)


def render():
    st.markdown("#### CRT stock check <span class='src'>rule based replacement for the crt-ict-trading-analyzer skill; completed candles only; every call is logged</span>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns([1.2, 1, 1, 1, 1])
    with c1:
        if st.session_state.get("crt_market") == "Metals":
            ticker = st.selectbox("Metal", list(metals.METALS), help="Priced in KWD per gram from the COMEX future and USD/KWD")
        else:
            ticker = st.text_input("Ticker", "KFH", help="Boursa Kuwait: KFH, NBK, BOURSA, ZAIN... US: SPY, NVDA")
    with c2:
        market = st.selectbox("Market", ["KW", "US", "Metals"], key="crt_market",
                              help="KW applies the Boursa Kuwait fils tick schedule and the .KW Yahoo suffix; Metals prices gold or silver in KWD per gram")
    is_metal = market == "Metals"
    with c3:
        capital = st.number_input("Capital", min_value=100.0, value=3000.0, step=100.0, help="KWD for KW and Metals, USD for US")
    with c4:
        risk_pct = st.number_input("Risk per trade %", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    with c5:
        min_rr = st.number_input("Min reward:risk", min_value=1.0, max_value=5.0, value=2.0, step=0.5)
    h1, h2 = st.columns([1, 1])
    with h1:
        horizon = st.radio("Horizon", ["Swing (days to weeks)", "Long term (1 to 2 years)"], horizontal=True)
    with h2:
        max_pos = st.number_input("Max position % of capital (long term)", min_value=1.0, max_value=50.0, value=10.0, step=1.0)
    karat, shop_price = "24K", 0.0
    if is_metal:
        s1, s2 = st.columns([1, 1])
        with s1:
            karat = st.selectbox("Karat", list(metals.KARATS), help="24K for bars and coins; 21K, 22K and 18K for jewellery")
        with s2:
            shop_price = st.number_input("Shop price, KWD per gram (0 = skip)", min_value=0.0, value=0.0, step=0.1, format="%.3f",
                                         help="The price a Kuwaiti shop quotes you; the check shows its premium over the international price")
    src = "Yahoo Finance (daily)" if is_metal else st.radio("Price data", ["Upload CSV (TickerChart or Boursa Kuwait export)", "Yahoo Finance (daily)"], horizontal=True)
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
            df, source_note = _metal(ticker) if is_metal else crt_data.fetch_yahoo(ticker, market)
            if df is None:
                st.error(source_note)
            st.session_state["crt_df"] = df
            st.session_state["crt_src"] = source_note
            st.session_state["crt_key"] = (ticker, market)
        if st.session_state.get("crt_key") == (ticker, market):  # never show one ticker's data under another's name
            df = st.session_state.get("crt_df", df)
            source_note = st.session_state.get("crt_src", source_note)
    if df is None:
        st.info("Load daily candles to run the check. TickerChart has no public API, so export a CSV from it (or from boursakuwait.com.kw) and upload it here; Yahoo covers Boursa Kuwait daily bars under the .KW suffix.", icon="ℹ️")
        return
    T = metals.relabel if is_metal else (lambda s: s)
    unit = "g" if is_metal else "sh"
    if is_metal:
        _metal_panel(df, ticker, karat, shop_price)

    if horizon.startswith("Long"):
        lt = crt.long_term_read(df, market, capital=capital, max_position_pct=max_pos)
        st.markdown("#### Long term read <span class='src'>weekly chart, completed weeks only; for a 1 to 2 year hold</span>", unsafe_allow_html=True)
        vt = {"ACCUMULATION ZONE": "pos", "WAIT: DOWNTREND ON THE WEEKLY": "neg"}.get(lt["verdict"], "warn")
        k = st.columns(4)
        with k[0]:
            st.markdown(f"<div class='kpi {vt}'><div class='l'>Verdict</div><div class='v' style='font-size:15px;white-space:normal'>{lt['verdict']}</div><div class='d'>{lt.get('trend', '')}</div></div>", unsafe_allow_html=True)
        with k[1]:
            st.markdown(f"<div class='kpi'><div class='l'>vs 40 week average</div><div class='v' style='font-size:16px'>{lt.get('dist_ma', float('nan')):+.1f}%</div><div class='d'>MA40 {lt.get('ma40', float('nan')):.4g}</div></div>", unsafe_allow_html=True)
        with k[2]:
            st.markdown(f"<div class='kpi'><div class='l'>From 52 week high</div><div class='v' style='font-size:16px'>{lt.get('off_high', float('nan')):+.1f}%</div><div class='d'>range {lt.get('lo52', float('nan')):.4g} to {lt.get('hi52', float('nan')):.4g}</div></div>", unsafe_allow_html=True)
        with k[3]:
            st.markdown(f"<div class='kpi'><div class='l'>Staged plan</div><div class='v' style='font-size:16px'>3 × {lt.get('tranche', 0)} {unit}</div><div class='d'>max {max_pos:.0f}% of capital</div></div>", unsafe_allow_html=True)
        lt_lines = [T(l) for l in lt["lines"] if not (is_metal and l.startswith("The chart cannot judge value"))]
        st.markdown("<div class='panel'><div class='rule' style='white-space:pre-wrap'>" + "\n".join(lt_lines) + "</div></div>", unsafe_allow_html=True)
        if is_metal:
            pass  # no fundamentals for a metal; the KWD per gram panel above covers it
        elif src.startswith("Yahoo"):
            f = crt_data.fetch_fundamentals(ticker, market)
            st.markdown("<div class='panel'><h4>Fundamentals (Yahoo Finance; verify against the company's filings on boursakuwait.com.kw)</h4><table style='width:100%;font-size:13px'>" + "".join(f"<tr><td style='color:#9a9c99'>{k}</td><td class='rule'>{v}</td></tr>" for k, v in f.items()) + "</table></div>", unsafe_allow_html=True)
        else:
            st.caption("Fundamentals are fetched only with the Yahoo source.")

    # ---- Stock read: trend, momentum, location, verdict ----
    sr = crt.stock_read(df, market, capital=capital, risk_pct=risk_pct)
    st.markdown("#### Stock read <span class='src'>trend, momentum and where the last price sits; rule based</span>", unsafe_allow_html=True)
    vt = {"BUY ZONE AT LAST PRICE": "pos", "AVOID FOR NOW": "neg", "WAIT FOR PULLBACK": "warn", "RANGE: BUY LOW END ONLY": "warn"}.get(sr["verdict"], "")
    k = st.columns(4)
    with k[0]:
        st.markdown(f"<div class='kpi {vt}'><div class='l'>Verdict</div><div class='v' style='font-size:16px;white-space:normal'>{sr['verdict']}</div><div class='d'>last close {sr.get('last', float('nan')):.4g}</div></div>", unsafe_allow_html=True)
    with k[1]:
        st.markdown(f"<div class='kpi'><div class='l'>Chart leaning</div><div class='v' style='font-size:16px'>{sr.get('trend', '')}</div><div class='d'>RSI {sr.get('rsi', float('nan')):.0f} · 20d {sr.get('ret20', float('nan')):+.1f}%</div></div>", unsafe_allow_html=True)
    with k[2]:
        st.markdown(f"<div class='kpi'><div class='l'>Support / resistance</div><div class='v' style='font-size:16px'>{sr.get('support', float('nan')):.4g} / {sr.get('resistance', float('nan')):.4g}</div><div class='d'>nearest swing levels</div></div>", unsafe_allow_html=True)
    with k[3]:
        if sr["verdict"] == "BUY ZONE AT LAST PRICE":
            st.markdown(f"<div class='kpi'><div class='l'>If buying now</div><div class='v' style='font-size:16px'>stop {sr['stop_now']:.4g} · {sr['shares_now']} {unit}</div><div class='d'>R:R {sr['rr_now']:.1f} to resistance</div></div>", unsafe_allow_html=True)
        elif sr["verdict"] == "WAIT FOR PULLBACK":
            st.markdown(f"<div class='kpi'><div class='l'>Price to wait for</div><div class='v' style='font-size:16px'>{sr['wait_price']:.4g}</div><div class='d'>EMA21 / support</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='kpi'><div class='l'>Levels to watch</div><div class='v' style='font-size:16px'>{sr.get('ema50', float('nan')):.4g}</div><div class='d'>EMA50 reclaim / range edges</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='panel'><div class='rule' style='white-space:pre-wrap'>" + "\n".join(T(l) for l in sr["lines"]) + "</div></div>", unsafe_allow_html=True)

    st.markdown("#### CRT setup check <span class='src'>exact entry only when a sweep exists</span>", unsafe_allow_html=True)
    a = crt.analyze(df, f"{ticker.upper()}{metals.LOG_SUFFIX}" if is_metal else ticker.upper(), market, capital=capital, risk_pct=risk_pct, min_rr=min_rr, data_source=source_note)
    left, right = st.columns([1, 1.5])
    with left:
        tone = {"bullish": "pos", "bearish": "neg"}.get(a.bias, "warn")
        st.markdown(f"<div class='kpi {tone}'><div class='l'>Decision</div><div class='v'>{a.bias.upper()}</div><div class='d'>as of close {a.as_of} · {len(a.confluence)} confluence factors</div></div>", unsafe_allow_html=True)
        if a.bias == "NO SETUP":
            st.warning("No trade and no entry price: " + (a.reasons[0] if a.reasons else "") + " The levels table lists what has to happen for a setup to exist.", icon="⛔")
        if a.bias != "NO SETUP":
            k = st.columns(2)
            with k[0]:
                st.markdown(f"<div class='kpi'><div class='l'>Entry / stop</div><div class='v'>{a.entry:.4g} / {a.stop:.4g}</div><div class='d'>R:R {a.rr:.2f} to target 1</div></div>", unsafe_allow_html=True)
            with k[1]:
                st.markdown(f"<div class='kpi'><div class='l'>Targets</div><div class='v'>{a.target1:.4g}{(' / ' + format(a.target2, '.4g')) if a.target2 else ''}</div><div class='d'>size {a.shares} {'grams' if is_metal else 'shares'}, risk {a.risk_amount:.2f}</div></div>", unsafe_allow_html=True)
        st.markdown("<div class='panel'><h4>Rule based explanation</h4><div class='rule' style='white-space:pre-wrap'>" + T(crt.explain(a)) + "</div></div>", unsafe_allow_html=True)
        lv = pd.DataFrame([{"Level": l.name, "Price": l.price, "Note": l.note} for l in a.levels])
        if len(lv):
            st.dataframe(lv, hide_index=True, width="stretch", column_config={"Price": st.column_config.NumberColumn(format="%.5g")})
        if st.button("Log this check"):
            crt.append_log(LOG_PATH, a, sr)
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
            upd = crt.evaluate_outcomes(log, lambda t: _metal(t[:-len(metals.LOG_SUFFIX)].title())[0] if t.endswith(metals.LOG_SUFFIX) else crt_data.fetch_yahoo(t, market)[0])
            upd.to_csv(LOG_PATH, index=False)
            log = upd
            st.success("Outcomes updated")
        st.dataframe(log.sort_values("logged_at", ascending=False), hide_index=True, width="stretch")
    else:
        st.caption("No signals logged yet. Log each check you act on; after 30 resolved signals the hit rate and average R tell you whether the method has value.")
