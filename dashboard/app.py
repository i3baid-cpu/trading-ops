"""
Trading Command Center: read-only analytics dashboard for Abdullah's four trading setups.

Run:   streamlit run app.py
Docker: docker compose up

READ ONLY. This app opens no broker, exchange or bot connection and has no
order controls. It reads the files in ./data only, or with DASH_MODE=live the read-only
mounted Freqtrade sqlite and Lumibot ledger (see data_live.py).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

import charts as C
import data as D

if D.LIVE:
    import data_live as DL

st.set_page_config(page_title="Trading Command Center", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# --------------------------------------------------------------------------- #
# Styling
# --------------------------------------------------------------------------- #
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: Inter, "Segoe UI", system-ui, sans-serif; }
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1500px; }
.kpi { background: #1c1f26; border: 1px solid #2a2e38; border-radius: 10px; padding: 14px 16px; min-height: 96px; }
.kpi .l { color: #9a9c99; font-size: 11px; letter-spacing: .06em; text-transform: uppercase; font-weight: 600; }
.kpi .v { color: #e8e8e3; font-size: 19px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 600; font-family: "JetBrains Mono", ui-monospace, monospace; margin-top: 4px; }
.kpi .d { color: #9a9c99; font-size: 12px; margin-top: 4px; }
.kpi.pos .v { color: #3fbf8f; } .kpi.neg .v { color: #e66767; } .kpi.warn .v { color: #e0a93a; }
.badge { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 11px; font-weight: 600; letter-spacing: .04em; }
.b-live { background: rgba(230,103,103,.18); color: #ff8a8a; border: 1px solid rgba(230,103,103,.5); }
.b-dry { background: rgba(201,133,0,.18); color: #f0b84a; border: 1px solid rgba(201,133,0,.5); }
.b-paper { background: rgba(57,135,229,.18); color: #7fb3ff; border: 1px solid rgba(57,135,229,.5); }
.b-na { background: rgba(154,156,153,.15); color: #c3c2b7; border: 1px solid rgba(154,156,153,.4); }
.b-ok { background: rgba(25,158,112,.18); color: #4fd0a0; border: 1px solid rgba(25,158,112,.5); }
.b-bad { background: rgba(230,103,103,.18); color: #ff8a8a; border: 1px solid rgba(230,103,103,.5); }
.b-warn { background: rgba(201,133,0,.18); color: #f0b84a; border: 1px solid rgba(201,133,0,.5); }
.panel { background: #1c1f26; border: 1px solid #2a2e38; border-radius: 10px; padding: 14px 16px; }
.panel h4 { margin: 0 0 8px 0; font-size: 13px; color: #9a9c99; text-transform: uppercase; letter-spacing: .06em; }
.rule { font-family: "JetBrains Mono", ui-monospace, monospace; font-size: 12.5px; color: #e8e8e3; }
.ai { border-left: 3px solid #9085e9; padding-left: 12px; color: #c3c2b7; }
.src { color: #9a9c99; font-size: 11.5px; }
.ro { background: rgba(25,158,112,.12); border: 1px solid rgba(25,158,112,.4); color: #4fd0a0; border-radius: 8px; padding: 6px 12px; font-size: 12px; font-weight: 600; }
div[data-testid="stMetric"] { background: #1c1f26; border: 1px solid #2a2e38; border-radius: 10px; padding: 10px 14px; }
</style>
""",
    unsafe_allow_html=True,
)

NA = D.NA


def money(v, currency="$", signed=False, digits=2):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return NA
    s = f"{abs(v):,.{digits}f}"
    sign = "-" if v < 0 else ("+" if signed else "")
    if currency in ("$", ""):
        return f"{sign}{currency}{s}"
    return f"{sign}{s} {currency}"


def pct(v, signed=True, digits=2):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return NA
    return f"{v:+.{digits}f}%" if signed else f"{v:.{digits}f}%"


def num(v, digits=2):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return NA
    if isinstance(v, float) and math.isinf(v):
        return "∞ (no losses)"
    return f"{v:,.{digits}f}"


def kpi(label, value, detail="", tone=""):
    st.markdown(f'<div class="kpi {tone}"><div class="l">{label}</div><div class="v">{value}</div><div class="d">{detail}</div></div>',
                unsafe_allow_html=True)


def tone_of(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    return "pos" if v > 0 else ("neg" if v < 0 else "")


def badge(text, kind):
    return f'<span class="badge b-{kind}">{text}</span>'


def mode_badge(system):
    alpaca = "PAPER · 0 trades"
    if D.LIVE:
        al_pos = X["al_live"][0]
        alpaca = f"PAPER · {len(al_pos)} open" if al_pos is not None else "PAPER · no trades yet"
    return {"Robinhood": badge("LIVE · real money", "live"), "Freqtrade": badge("DRY-RUN · simulated", "dry"),
            "Alpaca": badge(alpaca, "paper"), "CRT skill": badge("ANALYSIS ONLY", "na")}[system]


def LUMIBOT_STATE_NOTE(al_sum):
    return f"last written {fmt_time(al_sum['state_mtime'], D.UTC)} UTC" if al_sum["state_mtime"] is not None else "file not found"


def fmt_time(ts, tz):
    if ts is None or pd.isna(ts):
        return NA
    return pd.Timestamp(ts).tz_convert(tz).strftime("%Y-%m-%d %H:%M")


# --------------------------------------------------------------------------- #
# Data (cached)
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False, ttl=60 if D.LIVE else None)
def load_everything():
    trades = D.build_all_trades()
    live = {"al_live": D.alpaca_sleeve(), "fresh": D.live_freshness()} if D.LIVE else {}
    return {
        **live,
        "trades": trades,
        "orders": D.load_robinhood_orders(),
        "ft_stats": D.load_freqtrade_stats(),
        "ft_cfg": D.load_freqtrade_config(),
        "al_cfg": D.load_alpaca_config(),
        "al_bt": D.load_alpaca_backtest(),
        "snap": D.load_robinhood_snapshot(),
        "recon": D.reconciliation(),
        "mtimes": D.file_mtimes(),
    }


X = load_everything()
ALL = X["trades"]

# --------------------------------------------------------------------------- #
# Sidebar: global filters
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown("### Trading Command Center")
    st.markdown('<div class="ro">READ ONLY · no order controls · no live connections</div>', unsafe_allow_html=True)
    st.markdown("")
    tz_name = st.radio("Display time zone", ["Asia/Kuwait", "America/New_York", "UTC"], index=0, horizontal=False)
    TZ = {"Asia/Kuwait": D.KWT, "America/New_York": D.NYC, "UTC": D.UTC}[tz_name]
    systems = st.multiselect("Systems", list(D.SYSTEMS.keys()), default=list(D.SYSTEMS.keys()))
    strategies_all = list(ALL["strategy"].unique())
    strategies = st.multiselect("Strategies", strategies_all, default=strategies_all)
    dmin = ALL["entry_time"].min().date()
    dmax = max(ALL["entry_time"].max(), ALL["exit_time"].max()).date()
    date_range = st.date_input("Date range (by exit, open trades by entry)", (dmin, dmax), min_value=dmin, max_value=dmax)
    if isinstance(date_range, tuple) and len(date_range) == 2:
        d0, d1 = date_range
    else:
        d0, d1 = dmin, dmax
    st.markdown("---")
    with st.expander("Data provenance", expanded=False):
        st.markdown(
            """
<span class="src">
<b>Robinhood</b>: 23 orders pulled read-only from the Robinhood API on Oct 30 2026 (orders_full.csv). Positions and cash from the Oct 27 dashboard snapshot, adjusted for the Oct 30 fills.<br><br>
<b>Freqtrade</b>: 21 dry-run trades and the /profit and /show_config snapshots from the bot API on Oct 30 2026.<br><br>
<b>Alpaca</b>: config.json plus the headline backtest numbers written in HISTORY.md. No paper trades exist yet.<br><br>
<b>CRT skill</b>: SKILL.md only. No trades, no signals.<br><br>
Robinhood strategy names are <i>inferred</i> from order patterns. Candle data is not in the archive, so no indicator values are shown and no numbers are estimated.
</span>""",
            unsafe_allow_html=True,
        )

ref_time = ALL["exit_time"].max() if pd.notna(ALL["exit_time"].max()) else pd.Timestamp.now(tz=D.KWT)


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    f = df[df["system"].isin(systems) & df["strategy"].isin(strategies)]
    stamp = f["exit_time"].fillna(f["entry_time"])
    key = stamp.dt.tz_convert(TZ).dt.date
    # rows with no time at all (Alpaca ledger positions) are not dropped by the date filter
    return f[stamp.isna() | ((key >= d0) & (key <= d1))]


T = apply_filters(ALL)

st.markdown("## Trading Command Center")
st.caption(f"Four separate setups, one read-only view. Times shown in {tz_name}. Latest record in the archive: {fmt_time(ref_time, TZ)}.")

tab_names = ["A · Executive Overview", "B · Performance", "C · Strategy Comparison", "D · Trade Explorer",
             "E · Risk", "F · System Health", "G · Signal Explanation"]
tabs = st.tabs(tab_names)

# =========================================================================== #
# A. EXECUTIVE OVERVIEW
# =========================================================================== #
with tabs[0]:
    pos, acct = D.positions_table()
    snap = X["snap"]
    rh_all = ALL[ALL["system"] == "Robinhood"]
    ft_all = ALL[ALL["system"] == "Freqtrade"]
    m_rh, m_ft = D.compute_metrics(rh_all), D.compute_metrics(ft_all)
    unreal_known = pos["unrealized_known_basis"].sum()
    day_chg = pos["day_change"].sum()

    st.markdown(f"#### Robinhood ••8275 {mode_badge('Robinhood')} &nbsp; <span class='src'>positions priced at the Oct 27 snapshot, cash adjusted for Oct 30 fills</span>", unsafe_allow_html=True)
    c = st.columns(6)
    with c[0]:
        kpi("Account equity", money(acct["total"]), f"Reported Oct 29: {money(snap['reported']['value_oct29'])}")
    with c[1]:
        kpi("Available cash", money(acct["cash"]), "Derived from snapshot + fills")
    with c[2]:
        kpi("Invested capital", money(acct["invested"]), f"{len(pos)} positions")
    with c[3]:
        kpi("Realised P&L (FIFO)", money(m_rh.net_pnl, signed=True), f"{m_rh.closed} exits, {m_rh.unknown_basis} with unknown basis", tone_of(m_rh.net_pnl))
    with c[4]:
        kpi("Unrealised (known basis only)", money(unreal_known, signed=True), "ETH/BTC basis is partial", tone_of(unreal_known))
    with c[5]:
        kpi("Day change (snapshot)", money(day_chg, signed=True), "vs previous close on Oct 27", tone_of(day_chg))

    # period returns
    def period_pnl(trades, days):
        c_ = trades[trades["pnl_usd"].notna() & trades["exit_time"].notna()]
        if days is None:
            return c_["pnl_usd"].sum() if len(c_) else None
        cutoff = ref_time - pd.Timedelta(days=days)
        s = c_[c_["exit_time"] >= cutoff]
        return s["pnl_usd"].sum() if len(s) else 0.0

    st.markdown("#### Realised return by period <span class='src'>(realised only; equity history is not in the archive, so time-weighted returns are Not available)</span>", unsafe_allow_html=True)
    c = st.columns(8)
    for i, (label, days) in enumerate([("Daily", 1), ("Weekly", 7), ("Monthly", 30), ("All-time", None)]):
        v = period_pnl(rh_all, days)
        with c[i]:
            kpi(f"RH {label}", money(v, signed=True), "live, FIFO", tone_of(v))
        v2 = period_pnl(ft_all, days)
        with c[i + 4]:
            kpi(f"FT {label}", money(v2, currency="", signed=True), "dry-run, USDT", tone_of(v2))

    st.markdown("")
    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("#### Active strategies")
        ft_snap = " (Oct 30 snapshot)" if D.LIVE and "strategy" in X["ft_cfg"].get("_snapshot_keys", []) else ""
        al_desc = f"{X['al_cfg']['strategy']} {X['al_cfg']['params']['fast']}/{X['al_cfg']['params']['slow']} daily · {', '.join(X['al_cfg']['symbols'])}"
        al_meta = "backtest +2% vs SPY +123% · no paper trades"
        if D.LIVE:
            al_pos, al_sum = X["al_live"]
            al_desc = f"{DL.ALPACA_STRATEGY} · SMA{al_sum['params'].get('sma', '?')} · {', '.join(al_sum['symbols'])} · ${al_sum['capital']:,.0f} sleeve"
            al_meta = al_sum["status"]
        rows = [
            ("Robinhood", "Agent stock rebalance + crypto core + manual meme sleeve (inferred)", mode_badge("Robinhood"),
             f"{len(rh_all)} lots · last fill {fmt_time(X['orders']['last_update'].max(), TZ)}"),
            ("Freqtrade", f"{X['ft_cfg']['strategy']} · {X['ft_cfg']['timeframe']}{ft_snap} · stake {X['ft_cfg']['stake_amount']} USDT · max {int(X['ft_cfg']['max_open_trades'])} open",
             mode_badge("Freqtrade"), f"{m_ft.closed} closed · bot state {X['ft_cfg']['state']} (snapshot)"),
            ("Alpaca", al_desc, mode_badge("Alpaca"), al_meta),
            ("CRT skill", "crt-ict-trading-analyzer (discretionary stock check)", mode_badge("CRT skill"), "no trades, no signal log"),
        ]
        html = "<div class='panel'><table style='width:100%;font-size:13px;border-collapse:collapse'>"
        for s, desc, b, meta in rows:
            html += f"<tr style='border-bottom:1px solid #2a2e38'><td style='padding:8px 4px;font-weight:600;white-space:nowrap'>{s}</td><td style='padding:8px 4px'>{desc}<br><span class='src'>{meta}</span></td><td style='padding:8px 4px;text-align:right'>{b}</td></tr>"
        html += "</table></div>"
        st.markdown(html, unsafe_allow_html=True)

        st.markdown("#### Bot status and last successful update")
        mt = X["mtimes"]
        rh_last = X["orders"]["last_update"].max()
        ft_last = D._kwt(X["ft_stats"]["profit"]["latest_trade_date"]).tz_localize(None).tz_localize(D.UTC)
        status_rows = [
            ("Robinhood MCP connector", "Read-only pull Oct 30 2026", fmt_time(rh_last, TZ), badge("snapshot", "warn")),
            ("Freqtrade meme-sleeve", f"state={X['ft_cfg']['state']}, dry_run={X['ft_cfg']['dry_run']}", fmt_time(ft_last, TZ), badge("live sqlite" if D.LIVE else "snapshot", "ok" if D.LIVE else "warn")),
            ("Alpaca lumibot", (f"paper={X['al_live'][1]['paper']}, {X['al_live'][1]['status']}" if D.LIVE else "paper=true, email verification pending (Oct 30)"),
             fmt_time(X["al_live"][1]["state_mtime"], TZ) if D.LIVE else NA, badge("live ledger" if D.LIVE else "no trades", "ok" if D.LIVE else "na")),
            ("CRT skill", "skill file present", NA, badge("n/a", "na")),
        ]
        html = "<div class='panel'><table style='width:100%;font-size:13px;border-collapse:collapse'><tr style='color:#9a9c99'><td>Component</td><td>State</td><td>Last record</td><td></td></tr>"
        for a, b, c_, d_ in status_rows:
            html += f"<tr style='border-top:1px solid #2a2e38'><td style='padding:7px 4px;font-weight:600'>{a}</td><td style='padding:7px 4px'>{b}</td><td style='padding:7px 4px' class='rule'>{c_}</td><td style='text-align:right'>{d_}</td></tr>"
        foot = ("Freqtrade and Alpaca are read live from the mounted sqlite and ledger (refreshed every 60 s); Robinhood is still the archived pull. Times are last records, not a heartbeat."
                if D.LIVE else "This dashboard reads exported files, so these are the last records in the archive, not a live heartbeat. Wire the loaders in data.py to the Freqtrade REST API (read-only user) and the Robinhood connector to make them live.")
        html += f"</table><div class='src' style='margin-top:8px'>{foot}</div></div>"
        st.markdown(html, unsafe_allow_html=True)

    with right:
        st.markdown("#### Open positions (Robinhood)")
        show = pos[["symbol", "type", "qty", "price", "market_value", "weight", "unrealized_known_basis", "basis_coverage", "price_asof"]].copy()
        show["weight"] = (show["weight"] * 100).round(1)
        show["basis_coverage"] = (show["basis_coverage"] * 100).round(0)
        show.columns = ["Symbol", "Type", "Qty", "Price", "Value $", "Weight %", "Unreal. $ (known basis)", "Basis known %", "Price as of"]
        st.dataframe(show, hide_index=True, width="stretch",
                     column_config={"Qty": st.column_config.NumberColumn(format="%.6g"), "Price": st.column_config.NumberColumn(format="%.6g"),
                                    "Value $": st.column_config.NumberColumn(format="%.2f"), "Unreal. $ (known basis)": st.column_config.NumberColumn(format="%+.2f")})
        breaches = pos[pos["breach"]]
        st.markdown("#### Current portfolio risk")
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi("Largest position", f"{pos.loc[pos['weight'].idxmax(), 'symbol']} {pos['weight'].max():.0%}", "limit 20% per position", "neg" if len(breaches) else "pos")
        with c2:
            kpi("Limit breaches", str(len(breaches)), ", ".join(breaches["symbol"]) if len(breaches) else "none", "neg" if len(breaches) else "pos")
        with c3:
            open_meme = pos[pos["symbol"].isin(D.MEME_COINS)]["market_value"].sum()
            kpi("Meme-coin exposure", money(open_meme), f"{open_meme / acct['total']:.1%} of account, no stop on file", "warn" if open_meme > 0 else "")
        st.markdown("#### Freqtrade dry-run at a glance")
        c1, c2, c3 = st.columns(3)
        with c1:
            kpi("Net after fees", money(m_ft.net_pnl, currency="USDT", signed=True), f"{m_ft.closed} trades · PF {num(m_ft.profit_factor)}", tone_of(m_ft.net_pnl))
        with c2:
            kpi("Win rate", pct(m_ft.win_rate, signed=False, digits=1), f"max {m_ft.max_consec_losses} losses in a row")
        with c3:
            kpi("Max drawdown", money(m_ft.max_drawdown, currency="USDT"), f"avg hold {D.fmt_td(m_ft.avg_duration)}", "warn")
        if D.LIVE:
            v3 = ft_all[ft_all["entry_time"] >= DL.V3_START]
            st.caption(f"MemeSleeveV3 (4h, dry-run) since {DL.V3_START:%Y-%m-%d %H:%M} UTC: {DL.V3_NOTE}. "
                       f"{len(v3)} V3 trade(s) so far; V1 trades opened before the switch stay labelled V1.")
            st.markdown("#### Alpaca TrendFilter sleeve (paper)")
            al_pos, al_sum = X["al_live"]
            if al_pos is None:
                st.info(f"{al_sum['status'].capitalize()}. Ledger {LUMIBOT_STATE_NOTE(al_sum)}.", icon="ℹ️")
            else:
                c1, c2, c3 = st.columns(3)
                with c1:
                    kpi("Invested at cost", money(al_sum["invested"]), f"of {money(al_sum['capital'], digits=0)} sleeve")
                with c2:
                    kpi("Sleeve cash", money(al_sum["cash"]), "capital + realised − cost")
                with c3:
                    kpi("Realised P&L", money(al_sum["realized"], signed=True), "from the ledger", tone_of(al_sum["realized"]))
                show = al_pos.rename(columns={"symbol": "Symbol", "qty": "Qty", "cost_usd": "Cost $", "avg_cost": "Avg cost", "weight_at_cost": "Weight at cost"})
                show["Weight at cost"] = (show["Weight at cost"] * 100).round(1)
                st.dataframe(show, hide_index=True, width="stretch",
                             column_config={"Qty": st.column_config.NumberColumn(format="%.3f"), "Cost $": st.column_config.NumberColumn(format="%.2f"),
                                            "Avg cost": st.column_config.NumberColumn(format="%.2f")})
                st.caption(f"Market value and unrealised P&L: {NA} (the dashboard has no price feed or broker access). Ledger {LUMIBOT_STATE_NOTE(al_sum)}.")

# =========================================================================== #
# B. PERFORMANCE ANALYTICS
# =========================================================================== #
with tabs[1]:
    st.markdown("#### Performance analytics <span class='src'>filtered by the sidebar; realised P&L only, by exit time</span>", unsafe_allow_html=True)
    sys_choice = st.radio("Series", ["Freqtrade only", "Robinhood only", "Selected systems combined"], horizontal=True)
    P = T if sys_choice.startswith("Selected") else T[T["system"] == sys_choice.split()[0]]
    if sys_choice.startswith("Selected") and P["system"].nunique() > 1:
        st.warning("Combined view mixes LIVE Robinhood dollars with DRY-RUN Freqtrade USDT. Use it for shape only; the per-system views keep the sources separate.", icon="⚠️")
    m = D.compute_metrics(P)
    cur = "$" if (P["system"] == "Robinhood").all() else ("USDT" if (P["system"] == "Freqtrade").all() else "$ / USDT")
    c = st.columns(7)
    vals = [("Net realised", money(m.net_pnl, cur, True), tone_of(m.net_pnl)), ("Return on stake", pct(m.return_on_stake), tone_of(m.return_on_stake)),
            ("Win rate", pct(m.win_rate, False, 1), ""), ("Profit factor", num(m.profit_factor), ""),
            ("Expectancy / trade", money(m.expectancy, cur, True), tone_of(m.expectancy)), ("Max drawdown", money(m.max_drawdown, cur), "warn"),
            ("Avg holding", D.fmt_td(m.avg_duration), "")]
    for col, (l, v, t) in zip(c, vals):
        with col:
            kpi(l, v, "", t)
    ec = D.equity_curve(P)
    st.plotly_chart(C.equity_fig(ec, sys_choice, cur), width="stretch", config={"displaylogo": False})
    cA, cB = st.columns(2)
    with cA:
        st.plotly_chart(C.drawdown_fig(ec, cur), width="stretch", config={"displaylogo": False})
        dp = D.daily_pnl(P, TZ)
        dp["day"] = dp["day"].astype(str)
        st.plotly_chart(C.pnl_bars_fig(dp, "day", "pnl", "Daily realised P&L", currency=cur), width="stretch", config={"displaylogo": False})
    with cB:
        # rolling returns by trade
        if not ec.empty:
            w = st.slider("Rolling window (trades)", 3, max(3, min(10, len(ec))), 5)
            roll = pd.DataFrame({"time": ec["time"], "rolling": pd.Series(ec["pnl"]).rolling(w).sum().values})
            import plotly.graph_objects as go
            fig = go.Figure(go.Scatter(x=roll["time"], y=roll["rolling"], mode="lines+markers", line=dict(color=C.SERIES[6], width=2),
                                       name=f"Rolling {w}-trade P&L", hovertemplate="%{x|%d %b %H:%M}<br>%{y:+.2f}<extra></extra>"))
            fig.add_hline(y=0, line=dict(color=C.GRID, width=1))
            st.plotly_chart(C.base_layout(fig, height=220, title=f"Rolling {w}-trade realised P&L"), width="stretch", config={"displaylogo": False})
        bs = D.by_symbol(P)
        if not bs.empty:
            st.plotly_chart(C.contribution_fig(bs, currency=cur), width="stretch", config={"displaylogo": False})

    st.markdown("#### Benchmark comparison")
    b1, b2 = st.columns(2)
    with b1:
        bt = X["al_bt"]
        st.markdown(
            f"""<div class='panel'><h4>Alpaca SmaCross vs SPY (reported backtest, {bt['period']}, ${bt['budget_usd']:,})</h4>
<table style='width:100%;font-size:13px'><tr style='color:#9a9c99'><td></td><td>Strategy</td><td>SPY buy &amp; hold</td></tr>
<tr><td>Total return</td><td class='rule'>{bt['strategy_total_return_pct']:+.1f}%</td><td class='rule'>{bt['benchmark_total_return_pct']:+.1f}%</td></tr>
<tr><td>CAGR</td><td class='rule'>{bt['strategy_cagr_pct']:.2f}%</td><td class='rule'>{bt['benchmark_cagr_pct']:.2f}%</td></tr>
<tr><td>Max drawdown</td><td class='rule'>{bt['strategy_max_drawdown_pct']:.1f}%</td><td class='rule'>{bt['benchmark_max_drawdown_pct']:.1f}%</td></tr>
<tr><td>Sharpe</td><td class='rule'>{bt['strategy_sharpe']}</td><td class='rule'>{NA}</td></tr>
<tr><td>Time in market</td><td class='rule'>{bt['strategy_time_in_market_pct']}%</td><td class='rule'>100%</td></tr></table>
<div class='src' style='margin-top:6px'>Source: HISTORY.md headline figures. The tearsheet and trade list were not in the archive. Verdict recorded by the Alpaca bot: "doesn't work as set up".</div></div>""",
            unsafe_allow_html=True)
    with b2:
        # Pair drift over the trading window, from fill prices only
        ft = ALL[ALL["system"] == "Freqtrade"]
        rows = []
        for sym, g in ft.groupby("symbol"):
            g = g.sort_values("entry_time")
            first, last = g["entry_price"].iloc[0], g["exit_price"].iloc[-1]
            rows.append({"Pair": sym + "/USDT", "First entry": first, "Last exit": last, "Pair drift %": (last / first - 1) * 100,
                         "Strategy net %": g["pnl_usd"].sum() / g["stake_usd"].mean() * 100, "Trades": len(g)})
        drift = pd.DataFrame(rows)
        st.markdown("<div class='panel'><h4>Freqtrade: strategy vs holding the pair across the dry-run window</h4>", unsafe_allow_html=True)
        st.dataframe(drift, hide_index=True, width="stretch",
                     column_config={"First entry": st.column_config.NumberColumn(format="%.6g"), "Last exit": st.column_config.NumberColumn(format="%.6g"),
                                    "Pair drift %": st.column_config.NumberColumn(format="%+.2f"), "Strategy net %": st.column_config.NumberColumn(format="%+.2f")})
        st.markdown("<div class='src'>Computed from fill prices in trades_full.csv only (no OHLC in the archive). 'Strategy net %' is net USDT divided by one 25 USDT stake. A 1.4-day window is far too short for any conclusion.</div></div>", unsafe_allow_html=True)

    st.markdown("#### Risk-adjusted performance")
    r1, r2, r3, r4 = st.columns(4)
    with r1:
        kpi("Per-trade Sharpe (mean/sd of trade %)", num(m.sharpe_per_trade, 3), f"n = {m.closed - m.unknown_basis}; not annualised", "")
    with r2:
        kpi("Per-trade Sortino", num(m.sortino_per_trade, 3), "downside deviation of trade %", "")
    with r3:
        kpi("Freqtrade API Sharpe", num(X["ft_stats"]["profit"]["sharpe"], 1), "annualised from ~1.4 days: not meaningful", "warn")
    with r4:
        kpi("Freqtrade API Calmar / CAGR", f"{X['ft_stats']['profit']['calmar']:.0f} / {X['ft_stats']['profit']['cagr']:.0%}", "extrapolated: ignore until ≥ 50 trades", "warn")
    st.plotly_chart(C.duration_scatter_fig(P), width="stretch", config={"displaylogo": False})

# =========================================================================== #
# C. STRATEGY COMPARISON
# =========================================================================== #
with tabs[2]:
    st.markdown("#### Strategy comparison <span class='src'>metrics recomputed from the trade records in the current filter; Alpaca and CRT rows come from reported figures or have no trades</span>", unsafe_allow_html=True)
    if D.LIVE:
        st.caption(f"MemeSleeveV3 (4h, dry-run): {DL.V3_NOTE}. Its row only counts trades it opened after "
                   f"{DL.V3_START:%Y-%m-%d %H:%M} UTC; V1 trades it closed stay in the V1 row.")
    tbl = D.strategy_table(T)
    tbl_show = tbl.copy()
    tbl_show["Avg hold"] = tbl_show["Avg hold"].map(D.fmt_td)
    tbl_show["Profit factor"] = tbl_show["Profit factor"].map(lambda v: num(v))
    st.dataframe(tbl_show, hide_index=True, width="stretch",
                 column_config={"Net P&L ($)": st.column_config.NumberColumn(format="%+.2f"), "Return on stake (%)": st.column_config.NumberColumn(format="%+.2f"),
                                "Win rate (%)": st.column_config.NumberColumn(format="%.1f"), "Expectancy ($/trade)": st.column_config.NumberColumn(format="%+.3f"),
                                "Max DD ($)": st.column_config.NumberColumn(format="%.2f"), "Fees ($)": st.column_config.NumberColumn(format="%.2f")})
    st.caption("Blank cells mean Not available: either no trades (Alpaca paper, CRT), the cost basis is missing (NFLX sale), or the archive only has headline numbers (Alpaca backtest). Alpaca dollar figures are omitted because its only result is a $10k backtest; its return (+2.0%) and max drawdown (−2.6%) are in the Performance tab benchmark panel.")
    metric = st.selectbox("Compare on", ["Net P&L ($)", "Return on stake (%)", "Win rate (%)", "Profit factor", "Expectancy ($/trade)", "Max DD ($)", "Trades", "Max consec. losses"])
    cmp_tbl = tbl.copy()
    cmp_tbl["Profit factor"] = cmp_tbl["Profit factor"].replace([math.inf], float("nan"))
    cmp_tbl = cmp_tbl[cmp_tbl["System"].isin(systems)]
    st.plotly_chart(C.strategy_compare_fig(cmp_tbl, metric), width="stretch", config={"displaylogo": False})
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(C.exit_reason_fig(T), width="stretch", config={"displaylogo": False})
    with c2:
        st.plotly_chart(C.hour_heat_fig(T, TZ), width="stretch", config={"displaylogo": False})
    st.markdown("#### Paper / live / backtest status")
    s1, s2, s3, s4 = st.columns(4)
    for col, (sysname, lines) in zip([s1, s2, s3, s4], [
        ("Robinhood", ["Live since Aug 25 2026 (agent trades)", "5 meme-sleeve round trips: 1 win, 4 stop-outs", "No backtest exists for the manual rules", "Mock ledger: not created"]),
        ("Freqtrade", ["Dry-run since Oct 29 15:15 KWT", "21 closed, 1.4 days of history", "Earlier 6 to 8 trades lost on container recreate", "Backtest vs dry-run agreement: not checked yet"]),
        ("Alpaca", ["Paper account Oct 29, 0 trades", "Backtest 2021 to 2026: +2% vs SPY +123%", "Buy branch of strategy file truncated in archive", "Go-live: needs weeks of paper first"]),
        ("CRT skill", ["Skill text present (crt-ict-trading-analyzer)", "No signal log, no trades", "Discretionary, not automatable as written", "Needs non-repainting rule spec"]),
    ]):
        with col:
            st.markdown(f"<div class='panel'><h4>{sysname}</h4>{mode_badge(sysname)}<ul style='font-size:13px;margin-top:8px;padding-left:18px'>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul></div>", unsafe_allow_html=True)

# =========================================================================== #
# D. TRADE EXPLORER
# =========================================================================== #
with tabs[3]:
    st.markdown("#### Trade explorer")
    f1, f2, f3, f4, f5 = st.columns([1, 1, 1, 1, 2])
    with f1:
        sym_f = st.multiselect("Asset", sorted(T["symbol"].unique()), default=sorted(T["symbol"].unique()))
    with f2:
        out_f = st.multiselect("Outcome", ["win", "loss", "flat", "open", "unknown basis"], default=["win", "loss", "flat", "open", "unknown basis"])
    with f3:
        ex_f = st.multiselect("Exit reason", sorted(T["exit_reason_code"].replace("", "open").unique()), default=sorted(T["exit_reason_code"].replace("", "open").unique()))
    with f4:
        sort_by = st.selectbox("Sort by", ["exit_time", "entry_time", "pnl_usd", "pnl_pct", "duration", "symbol"])
    with f5:
        q = st.text_input("Search (id, symbol, reason, note)", "")

    E = T.copy()
    E["outcome"] = E.apply(lambda r: "open" if r["status"] == "open" else ("unknown basis" if pd.isna(r["pnl_usd"]) else ("win" if r["pnl_usd"] > 0 else ("loss" if r["pnl_usd"] < 0 else "flat"))), axis=1)
    E = E[E["symbol"].isin(sym_f) & E["outcome"].isin(out_f) & E["exit_reason_code"].replace("", "open").isin(ex_f)]
    if q:
        ql = q.lower()
        E = E[E.apply(lambda r: ql in " ".join(str(r[c]) for c in ["trade_id", "symbol", "strategy", "entry_reason", "exit_reason", "note"]).lower(), axis=1)]
    E = E.sort_values(sort_by, ascending=sort_by in ("symbol",))
    view = pd.DataFrame({
        "ID": E["trade_id"], "System": E["system"], "Source": E["source_label"], "Asset": E["symbol"], "Strategy": E["strategy"],
        "Entry": E["entry_time"].map(lambda t: fmt_time(t, TZ)), "Entry px": E["entry_price"],
        "Exit": E["exit_time"].map(lambda t: fmt_time(t, TZ)), "Exit px": E["exit_price"],
        "Qty": E["qty"], "Stake": E["stake_usd"], "Net P&L": E["pnl_usd"], "P&L %": E["pnl_pct"], "Fees": E["fees_usd"],
        "Hold": E["duration"].map(D.fmt_td), "Exit reason": E["exit_reason"], "Outcome": E["outcome"],
    })
    st.caption(f"{len(view)} of {len(ALL)} trade records. Fees: Freqtrade reports them; the Robinhood API returns none (crypto spread is embedded in fill prices).")
    sel = st.dataframe(view, hide_index=True, width="stretch", height=380, on_select="rerun", selection_mode="single-row",
                       column_config={"Entry px": st.column_config.NumberColumn(format="%.8g"), "Exit px": st.column_config.NumberColumn(format="%.8g"),
                                      "Qty": st.column_config.NumberColumn(format="%.6g"), "Stake": st.column_config.NumberColumn(format="%.2f"),
                                      "Net P&L": st.column_config.NumberColumn(format="%+.3f"), "P&L %": st.column_config.NumberColumn(format="%+.2f"),
                                      "Fees": st.column_config.NumberColumn(format="%.4f")})
    picked = None
    if sel and sel.selection and sel.selection.rows:
        picked = view.iloc[sel.selection.rows[0]]["ID"]
    elif len(view):
        picked = view.iloc[0]["ID"]
    if picked:
        r = ALL[ALL["trade_id"] == picked].iloc[0]
        dcol, ccol = st.columns([1, 1.6])
        with dcol:
            unit = "USDT" if r["system"] == "Freqtrade" else "USD"
            st.markdown(f"""<div class='panel'><h4>Trade detail · {r['trade_id']}</h4>
{mode_badge(r['system'])}<br><br>
<table style='width:100%;font-size:13px'>
<tr><td style='color:#9a9c99'>Asset / strategy</td><td><b>{r['symbol']}</b> · {r['strategy']}</td></tr>
<tr><td style='color:#9a9c99'>Entry</td><td class='rule'>{fmt_time(r['entry_time'], TZ)} @ {num(r['entry_price'], 8) if pd.notna(r['entry_price']) else NA}</td></tr>
<tr><td style='color:#9a9c99'>Exit</td><td class='rule'>{fmt_time(r['exit_time'], TZ)} @ {num(r['exit_price'], 8) if pd.notna(r['exit_price']) else NA}</td></tr>
<tr><td style='color:#9a9c99'>Size</td><td class='rule'>{r['qty']:,.6g} units · stake {money(r['stake_usd'])} {unit}</td></tr>
<tr><td style='color:#9a9c99'>Net P&amp;L</td><td class='rule' style='color:{"#3fbf8f" if (pd.notna(r["pnl_usd"]) and r["pnl_usd"]>0) else ("#e66767" if pd.notna(r["pnl_usd"]) and r["pnl_usd"]<0 else "#e8e8e3")}'>{money(r['pnl_usd'], signed=True)} {unit if pd.notna(r['pnl_usd']) else ''} ({pct(r['pnl_pct'])})</td></tr>
<tr><td style='color:#9a9c99'>Fees</td><td class='rule'>{money(r['fees_usd'], digits=4) if pd.notna(r['fees_usd']) else NA}</td></tr>
<tr><td style='color:#9a9c99'>Holding</td><td class='rule'>{D.fmt_td(r['duration'])}</td></tr>
<tr><td style='color:#9a9c99'>Stop level</td><td class='rule'>{num(r['stop_price'], 8) if pd.notna(r['stop_price']) else 'none on file'}</td></tr>
<tr><td style='color:#9a9c99'>Entry reason</td><td>{r['entry_reason']}</td></tr>
<tr><td style='color:#9a9c99'>Exit reason</td><td>{r['exit_reason'] or 'still open'}</td></tr>
<tr><td style='color:#9a9c99'>Indicators at signal</td><td>{NA} (no candle data in the archive)</td></tr>
<tr><td style='color:#9a9c99'>Note</td><td>{r['note'] or ''}</td></tr>
</table></div>""", unsafe_allow_html=True)
        with ccol:
            candles = D.load_candles(r["symbol"])
            st.plotly_chart(C.fill_timeline_fig(ALL[ALL["system"] == r["system"]], r["symbol"], picked, candles), width="stretch", config={"displaylogo": False})
            if candles is None:
                st.caption("No OHLC data was in the archive, so the dotted line joins actual fill prices. Run `python fetch_candles.py` (Binance public klines, read-only) to draw real 5m candlesticks for the Freqtrade pairs.")

# =========================================================================== #
# E. RISK MANAGEMENT
# =========================================================================== #
with tabs[4]:
    st.markdown("#### Risk management")
    pos, acct = D.positions_table()
    limit = X["snap"]["concentration_limit"]
    breaches = pos[pos["breach"]]
    if len(breaches):
        st.error(f"Concentration limit breached: {', '.join(f'{s} {w:.0%}' for s, w in zip(breaches['symbol'], breaches['weight']))} vs the {limit:.0%} rule. Exposure above the limit: {money((breaches['weight'] - limit).sum() * acct['total'])}.", icon="🚨")
    near = pos[(~pos["breach"]) & (pos["weight"] > limit * 0.75)]
    if len(near):
        st.warning(f"Approaching limit: {', '.join(f'{s} {w:.0%}' for s, w in zip(near['symbol'], near['weight']))} (above 15%).", icon="⚠️")
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(C.allocation_fig(pos, acct["cash"], limit), width="stretch", config={"displaylogo": False})
    with c2:
        st.plotly_chart(C.concentration_fig(pos, limit), width="stretch", config={"displaylogo": False})

    st.markdown("#### Exposure, position sizes and stop distance")
    k = st.columns(5)
    crypto_w = pos[pos["type"] == "Crypto"]["market_value"].sum() / acct["total"]
    with k[0]:
        kpi("Open exposure", money(acct["invested"]), f"{acct['invested'] / acct['total']:.1%} invested, {acct['cash'] / acct['total']:.1%} cash")
    with k[1]:
        kpi("Crypto vs stocks", f"{crypto_w:.0%} / {1 - crypto_w - acct['cash'] / acct['total']:.0%}", "sector concentration: crypto-heavy", "warn")
    with k[2]:
        kpi("Positions with a stop", "0 of 6", "FLOKI (Oct 30) has no stop order on file", "neg")
    with k[3]:
        ft_cfg = X["ft_cfg"]
        kpi("Freqtrade max exposure", f"{int(ft_cfg['max_open_trades']) * float(ft_cfg['stake_amount']):.0f} USDT", f"{int(ft_cfg['max_open_trades'])} × {ft_cfg['stake_amount']} USDT, stop {ft_cfg['stoploss']:.0%} (not on exchange)")
    with k[4]:
        kpi("Freqtrade worst case per trade", f"-{float(ft_cfg['stake_amount']) * -ft_cfg['stoploss']:.2f} USDT", "before slippage; market stop fires on next candle", "warn")

    st.markdown("#### Risk budget consumption")
    rb = pd.DataFrame([
        {"Rule": "Robinhood: single position ≤ 20%", "Used": f"{pos['weight'].max():.0%} (ETH)", "Budget": "20%", "Status": "BREACHED"},
        {"Rule": "Robinhood: meme sleeve size per trade", "Used": "$22.00", "Budget": "not defined in rules", "Status": "UNDEFINED"},
        {"Rule": "Robinhood: max daily / monthly loss", "Used": NA, "Budget": "not defined", "Status": "MISSING"},
        {"Rule": "Freqtrade: open trades", "Used": f"{X['ft_stats']['count']['current']} of {X['ft_stats']['count']['max']}", "Budget": str(X["ft_stats"]["count"]["max"]), "Status": "OK"},
        {"Rule": "Freqtrade: max drawdown rule / kill switch", "Used": f"{X['ft_stats']['profit']['max_drawdown_abs']:.2f} USDT observed", "Budget": "not defined", "Status": "MISSING"},
        {"Rule": "Alpaca: max open positions", "Used": "0 of 3", "Budget": "3 × 5% stake, bracket 5% stop / 10% TP", "Status": "OK"},
        {"Rule": "Alpaca: daily loss limit", "Used": NA, "Budget": "not defined", "Status": "MISSING"},
    ])
    def _style(v):
        return {"BREACHED": "color:#ff8a8a;font-weight:700", "MISSING": "color:#f0b84a;font-weight:600", "UNDEFINED": "color:#f0b84a", "OK": "color:#4fd0a0"}.get(v, "")
    st.dataframe(rb.style.map(_style, subset=["Status"]), hide_index=True, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(C.loss_hist_fig(T), width="stretch", config={"displaylogo": False})
    with c2:
        ec_rh = D.equity_curve(ALL[ALL["system"] == "Robinhood"])
        st.plotly_chart(C.drawdown_fig(ec_rh, "$").update_layout(title_text="Robinhood realised drawdown (live, FIFO)"), width="stretch", config={"displaylogo": False})
    st.markdown("#### Correlation between holdings")
    st.info("Not available. The archive has no price history for ETH, BTC, NVDA, QQQ, AMD or FLOKI, so a correlation matrix cannot be computed without estimating. Add daily closes to data/ (or run fetch_candles.py for the Binance pairs) and this panel will populate.", icon="ℹ️")

# =========================================================================== #
# F. SYSTEM HEALTH
# =========================================================================== #
with tabs[5]:
    st.markdown("#### System health and diagnostics <span class='src'>from exported snapshots; a live heartbeat needs the read-only API loaders described in README</span>", unsafe_allow_html=True)
    now = pd.Timestamp.now(tz=D.UTC)
    rh_last = X["orders"]["last_update"].max()
    ft_last = D._kwt(X["ft_stats"]["profit"]["latest_trade_date"]).tz_localize(None).tz_localize(D.UTC)
    def age(ts):
        return D.fmt_td(now - pd.Timestamp(ts).tz_convert(D.UTC))
    h = st.columns(4)
    if D.LIVE:
        fresh_card = ("Data freshness (live)", badge("read-only mounts", "ok"),
                      [f"{label}: {fmt_time(ts, D.UTC)} UTC ({age(ts)} ago)" if ts is not None else f"{label}: {NA}" for label, ts in X["fresh"]]
                      + [f"Still from the Oct 30 snapshot: {', '.join(DL.snapshot_note(X['ft_cfg'], X['ft_stats']))}"])
    else:
        fresh_card = ("Data freshness (this app)", badge("files", "na"), [f"{k}: {v.strftime('%Y-%m-%d %H:%M')} UTC" for k, v in list(X["mtimes"].items())[:4]])
    cards = [
        ("Robinhood MCP connector", badge("read-only pull", "ok"), [f"Last order update: {fmt_time(rh_last, TZ)}", f"Data age: {age(rh_last)}", "Orders: 23 (16 crypto filled, 2 canceled, 5 stock)", "Fees / reasons: not returned by API"]),
        ("Freqtrade meme-sleeve", badge(f"state {X['ft_cfg']['state']} · dry_run", "dry"), [f"Last trade close: {fmt_time(ft_last, TZ)}", f"Data age: {age(ft_last)}", f"Version {X['ft_cfg']['version']} · {X['ft_cfg']['exchange']} {X['ft_cfg']['trading_mode']}", "API: 127.0.0.1 + Tailscale only (fixed Oct 29)"]),
        ("Alpaca lumibot", badge("paper · idle", "paper"), ["No fills, no orders yet", "Email verification pending (Oct 30)", "Telegram alerts: not set up", "Strategy buy branch truncated in archive"]),
        fresh_card,
    ]
    for col, (title, b, lines) in zip(h, cards):
        with col:
            st.markdown(f"<div class='panel'><h4>{title}</h4>{b}<ul style='font-size:12.5px;margin-top:8px;padding-left:18px'>" + "".join(f"<li>{l}</li>" for l in lines) + "</ul></div>", unsafe_allow_html=True)

    st.markdown("#### Order reconciliation")
    rec = X["recon"]
    npass, nfail = int((rec["Result"] == "PASS").sum()), int((rec["Result"] == "FAIL").sum())
    st.caption(f"{npass} checks pass, {nfail} fail, {int((rec['Result']=='INFO').sum())} informational, {int((rec['Result']=='N/A').sum())} not available. Each check compares two independent records in the archive (trade list vs API profit snapshot, FIFO vs the Oct 27 dashboard).")
    # Expected/Actual mix numbers and text; cast to str so Arrow does not have to guess a column type.
    st.dataframe(rec.astype({"Expected": str, "Actual": str}).style.map(lambda v: {"PASS": "color:#4fd0a0;font-weight:600", "FAIL": "color:#ff8a8a;font-weight:700", "INFO": "color:#9a9c99", "N/A": "color:#9a9c99"}.get(v, ""), subset=["Result"]),
                 hide_index=True, width="stretch", height=min(640, 38 * len(rec) + 40))

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Failed, rejected and canceled orders")
        canc = X["orders"][X["orders"]["state"] != "filled"]
        cv = pd.DataFrame({"Time": canc["created"].map(lambda t: fmt_time(t, TZ)), "Symbol": canc["symbol"], "Side": canc["side"], "Type": canc["order_type"],
                           "Qty": canc["qty_ordered"], "Limit/stop": canc["limit_price"].fillna(canc["stop_price"]), "State": canc["state"]})
        st.dataframe(cv, hide_index=True, width="stretch", column_config={"Limit/stop": st.column_config.NumberColumn(format="%.8g"), "Qty": st.column_config.NumberColumn(format="%.6g")})
        st.caption("Freqtrade entry timeouts (10 min limit orders) were observed on Oct 29 but are not in the exported trade list, so their count is Not available. Log errors: no log files were in the archive.")
    with c2:
        st.markdown("#### Strategy execution timing (Freqtrade)")
        ft = ALL[ALL["system"] == "Freqtrade"].copy()
        ft["entry_min"] = ft["entry_time"].dt.minute % 5
        ft["exit_min"] = ft["exit_time"].dt.minute % 5
        on_candle = int((ft["entry_min"] == 0).sum())
        st.markdown(f"""<div class='panel'><table style='width:100%;font-size:13px'>
<tr><td style='color:#9a9c99'>Entries on a 5m candle boundary</td><td class='rule'>{on_candle} of {len(ft)}</td></tr>
<tr><td style='color:#9a9c99'>Exits on a 5m candle boundary</td><td class='rule'>{int((ft['exit_min']==0).sum())} of {len(ft)} (others are ROI checks between candles)</td></tr>
<tr><td style='color:#9a9c99'>Shortest / longest hold</td><td class='rule'>{D.fmt_td(ft['duration'].min())} / {D.fmt_td(ft['duration'].max())}</td></tr>
<tr><td style='color:#9a9c99'>Trades per 24h (dry-run window)</td><td class='rule'>{len(ft) / ((ft['exit_time'].max() - ft['entry_time'].min()).total_seconds() / 86400):.1f}</td></tr>
<tr><td style='color:#9a9c99'>Bot start (API)</td><td class='rule'>{X['ft_stats']['profit']['bot_start_date']} UTC</td></tr>
<tr><td style='color:#9a9c99'>History gap</td><td>Trades before the 15:15 KWT restart on Oct 29 were lost (container recreate before db_url was made persistent).</td></tr>
</table></div>""", unsafe_allow_html=True)
    st.markdown("#### Known incidents and open items (from HISTORY.md files)")
    inc = pd.DataFrame([
        ("2026-10-28", "Freqtrade", "API on default password and port 8080 open to 0.0.0.0", "Fixed Oct 29: bound to 127.0.0.1 + Tailscale, password changed", "closed"),
        ("2026-10-29", "Freqtrade", "New API password pasted in chat", "Rotate the password again; never paste secrets in chat", "open"),
        ("2026-10-29", "Freqtrade", "Trade history lost on container recreate", "Fixed with persistent db_url; ~6 to 8 trades unrecoverable", "closed"),
        ("2026-10-29", "Robinhood", "Dashboard live refresh fails on iOS/browser", "Not resolved; scheduled refresh declined", "open"),
        ("2026-10-29", "Robinhood", "Portfolio bot says it does not manage the account while rules say 'AI-managed'", "Clarify who places orders and under which rule", "open"),
        ("2026-10-30", "Robinhood", "FLOKI bought with no protective stop on file", "Place GTC stop or document why not", "open"),
        ("2026-10-30", "Alpaca", "Email verification required before trading", "Pending", "open"),
        ("2026-10-30", "Alpaca", "sma_cross.py buy branch truncated in archive", "Pull the live file from the VPS to audit", "open"),
        ("ongoing", "All", "No kill switch, daily loss cap or alert routine implemented", "Define unified rules (see roadmap)", "open"),
    ], columns=["Date", "System", "Incident", "Action", "Status"])
    st.dataframe(inc.style.map(lambda v: {"open": "color:#f0b84a;font-weight:600", "closed": "color:#4fd0a0"}.get(v, ""), subset=["Status"]), hide_index=True, width="stretch")

# =========================================================================== #
# G. SIGNAL EXPLANATION
# =========================================================================== #
with tabs[6]:
    st.markdown("#### Why did the system buy, sell or hold?")
    st.caption("Rule-based explanations are derived mechanically from the strategy code and the order records. AI commentary is written separately and labelled. Indicator values at signal time are Not available because the archive has no candle data.")
    options = ALL[ALL["entry_time"].notna()].sort_values("entry_time", ascending=False)
    labels = {r["trade_id"]: f"{r['trade_id']} · {r['system']} · {r['symbol']} · {fmt_time(r['entry_time'], TZ)} · {money(r['pnl_usd'], signed=True) if pd.notna(r['pnl_usd']) else r['status']}" for _, r in options.iterrows()}
    pick = st.selectbox("Trade or signal", list(labels.keys()), format_func=lambda k: labels[k])
    r = ALL[ALL["trade_id"] == pick].iloc[0]
    cfg = X["ft_cfg"]
    left, right = st.columns([1.1, 1])
    with left:
        if r["system"] == "Freqtrade":
            minutes = r["duration"].total_seconds() / 60 if pd.notna(r["duration"]) else None
            entry_rules = [
                ("EMA(9) > EMA(21)", "trend filter: short EMA above long EMA on the 5m close"),
                ("45 < RSI(14) < 75", "momentum present but not overbought"),
                ("volume > 0.8 × 20-bar mean volume", "activity filter"),
                ("close > EMA(9)", "price above the fast average"),
            ]
            risk_checks = [
                (f"max_open_trades = {int(cfg['max_open_trades'])}", "slot available at entry"),
                (f"stake_amount = {cfg['stake_amount']} USDT", f"actual stake {r['stake_usd']:.4f} USDT"),
                (f"stoploss = {r['stop_price'] / r['entry_price'] - 1:.0%} (market order, not on exchange)", f"stop level {r['stop_price']:.8f}"),
                ("entry order: limit, 10-minute timeout, order-book top", "fill is simulated in dry-run"),
            ]
            exit_text = r["exit_reason"] or "still open"
            is_v1 = r["strategy"].startswith("MemeSleeveV1")
            if r["status"] == "open":
                decision = f"HOLD: trade still open, stop level {r['stop_price']:.8f}."
            elif not is_v1:
                decision = f"SELL: {r['exit_reason']} after {D.fmt_td(r['duration'])}. Result {r['pnl_pct']:+.2f}% after fees {r['fees_usd']:.4f} USDT."
            elif r["exit_reason_code"] == "roi":
                decision = f"SELL: held {D.fmt_td(r['duration'])}, profit {r['pnl_pct']:+.2f}% reached the ROI tier in force, so Freqtrade closed with a limit order."
            else:
                decision = f"SELL: strategy exit signal fired after {D.fmt_td(r['duration'])} (EMA9 crossed under EMA21 or RSI > 80). Result {r['pnl_pct']:+.2f}% after fees {r['fees_usd']:.4f} USDT."
            if not is_v1:
                entry_rules = [(r["entry_reason"], f"rules in {r['strategy'].split()[0]}.py; this panel only spells out V1's")]
            html = f"<div class='panel'><h4>Rule-based explanation · {r['strategy'].split()[0]}</h4><b>BUY {r['symbol']}/USDT at {r['entry_price']:.8f}</b> on {fmt_time(r['entry_time'], TZ)}<br><span class='src'>All four conditions below were true on the signal candle (the bot cannot enter otherwise). Their numeric values are Not available in the archive.</span><ul class='rule' style='margin-top:8px'>"
            html += "".join(f"<li>{a} <span style='color:#9a9c99'>· {b}</span></li>" for a, b in entry_rules)
            html += "</ul><b>Risk checks at entry</b><ul class='rule'>" + "".join(f"<li>{a} <span style='color:#9a9c99'>· {b}</span></li>" for a, b in risk_checks) + "</ul>"
            html += f"<b>Exit rule</b><div class='rule' style='margin:4px 0 8px'>{exit_text}</div><b>Final decision</b><div style='margin-top:4px'>{decision}</div></div>"
            st.markdown(html, unsafe_allow_html=True)
        else:
            stop_rule = "A GTC stop-loss sell was placed at roughly −10% from entry on the same day as the buy." if r["symbol"] in D.MEME_COINS and r["trade_id"] != "RH-14" else "No protective stop order appears in the order history."
            if r["status"] == "open":
                decision = f"HOLD: position still open as of the Oct 30 pull. {stop_rule}"
            elif r["exit_reason_code"] == "stop_loss":
                decision = f"SELL (stop): the GTC stop at {r['stop_price']:.8f} was triggered on {fmt_time(r['exit_time'], TZ)}. Loss {money(r['pnl_usd'], signed=True)} ({r['pnl_pct']:+.1f}%)."
            else:
                decision = f"SELL (limit/market): the agent sold on {fmt_time(r['exit_time'], TZ)}. The API returns no reason; result {money(r['pnl_usd'], signed=True) if pd.notna(r['pnl_usd']) else NA}."
            html = f"""<div class='panel'><h4>Rule-based explanation · Robinhood (agent placed)</h4>
<b>{'BUY' if pd.notna(r['entry_time']) else 'SELL'} {r['symbol']}</b> on {fmt_time(r['entry_time'] if pd.notna(r['entry_time']) else r['exit_time'], TZ)}<br>
<span class='src'>Robinhood's API returns no strategy, signal or reason. What follows is what the order records themselves establish.</span>
<ul class='rule' style='margin-top:8px'>
<li>Order type: {r['entry_reason']}</li>
<li>Size: {money(r['stake_usd']) if pd.notna(r['stake_usd']) else NA} ({(r['stake_usd'] / 1118 * 100):.1f}% of account) <span style='color:#9a9c99'>· within the 20% rule</span></li>
<li>Stop: {stop_rule}</li>
<li>Documented rule set: "24h +4% to +15% momentum, stop ~−10%, target ~+12%" is referenced by MemeSleeveV1's docstring, but the source rule document was not found.</li>
</ul><b>Final decision</b><div style='margin-top:4px'>{decision}</div></div>"""
            st.markdown(html, unsafe_allow_html=True)
    with right:
        if r["system"] == "Freqtrade":
            commentary = """<ul style='font-size:13px;padding-left:18px'><li>The entry is a generic 5m trend filter; nothing in it measures the "24h +4% to +15%" momentum the docstring promises. The strategy name and its rules do not match.</li><li>13 of 21 exits came from the exit signal and 11 of those were losses averaging about −1%: EMA9 dipping under EMA21 on a 5m chart happens constantly in choppy meme pairs, so the bot pays round-trip fees for noise.</li><li>The ROI table drops to 0% at 120 minutes, which forces a sale of any trade held two hours even when the trend is intact. Combined with a −10% stop, reward is capped while risk is not.</li><li>Fees are 0.05 USDT per 25 USDT trade (0.2% round trip). Expectancy is 0.056 USDT per trade, barely above fees. One slippage event erases a day.</li><li>1.4 days and 21 trades prove nothing either way. The annualised Sharpe of 41 in the API snapshot is an artefact of the window.</li></ul>"""
        elif r["symbol"] in D.MEME_COINS:
            commentary = """<ul style='font-size:13px;padding-left:18px'><li>The manual meme sleeve has a fixed pattern: buy about $22, place a −10% GTC stop. Four of five round trips stopped out; the one winner (DOGE, Sep 18 to 22) was sold at a limit, not a target rule.</li><li>No take-profit order exists, so winners depend on a discretionary sale while losers are automatic. That asymmetry explains the −$5.11 result.</li><li>The Oct 30 FLOKI buy has no stop order in the record, which breaks the sleeve's own pattern.</li><li>Fees are invisible in Robinhood crypto (spread based) and are not in the data, so the real result is slightly worse than shown.</li></ul>"""
        else:
            commentary = """<ul style='font-size:13px;padding-left:18px'><li>The Aug 25 stock rebalance (sell NFLX, buy NVDA, QQQ, AMD) is the only stock action in nine weeks; it reads as a one-off reallocation rather than a strategy with rules.</li><li>The ETH and BTC lots bought Aug 29 sit inside much larger holdings whose cost is unknown, so unrealised P&L for the account cannot be stated honestly.</li><li>With ETH at about 65% of the account, every rule about stops and sizing on $22 meme trades is dominated by one unmanaged position.</li></ul>"""
        st.markdown("<div class='panel'><h4>AI commentary · written by Claude during the Oct 30 2026 audit, not by the trading system</h4><div class='ai'>" + commentary + "</div></div>", unsafe_allow_html=True)

    st.markdown("#### Strategy rule sheets")
    r1, r2, r3 = st.columns(3)
    with r1:
        st.markdown(f"""<div class='panel'><h4>MemeSleeveV1 (Freqtrade)</h4><div class='rule'>
timeframe 5m · pairs DOGE PEPE SHIB FLOKI /USDT<br>
ENTER if EMA9&gt;EMA21 and 45&lt;RSI&lt;75 and vol&gt;0.8×mean20 and close&gt;EMA9<br>
EXIT if EMA9&lt;EMA21 or RSI&gt;80<br>
ROI {cfg['minimal_roi']}<br>
stop {cfg['stoploss']:.0%} market, no trailing<br>
stake {cfg['stake_amount']} USDT, max open {int(cfg['max_open_trades'])}<br>
orders limit/limit, timeout 10 min</div></div>""", unsafe_allow_html=True)
    with r2:
        a = X["al_cfg"]
        st.markdown(f"""<div class='panel'><h4>SmaCross (Alpaca / Lumibot)</h4><div class='rule'>
symbols {', '.join(a['symbols'])} · daily bars, 1 iteration/day<br>
ENTER on SMA{a['params']['fast']} crossing above SMA{a['params']['slow']}<br>
EXIT on SMA{a['params']['fast']} crossing below SMA{a['params']['slow']}<br>
bracket: stop {a['stoploss_pct']:.0%}, take-profit {a['takeprofit_pct']:.0%}<br>
stake {a['stake_pct']:.0%} of portfolio, max {a['max_open_positions']} positions<br>
paper = {a['paper']}<br>
<span style='color:#f0b84a'>buy branch truncated in archived file</span></div></div>""", unsafe_allow_html=True)
    with r3:
        st.markdown("""<div class='panel'><h4>Robinhood meme sleeve (inferred from orders)</h4><div class='rule'>
BUY ≈ $22 via limit order<br>
STOP: GTC stop-loss ≈ −10% placed same minute<br>
TARGET: none on file (docstring elsewhere says ~+12%)<br>
EXIT: stop fill or discretionary limit sell<br>
5 round trips: 1 win (+3.79), 4 stops (−2.21 to −2.25)<br>
<span style='color:#f0b84a'>no written rule document found</span></div></div>""", unsafe_allow_html=True)

st.markdown("---")
st.markdown("<span class='src'>Read-only analytics. No broker, exchange or bot connection is opened by this application and no order can be placed from it. Sources: audit pack of Oct 30 2026. Nothing shown here is estimated; where a figure cannot be derived from the records it is marked Not available.</span>", unsafe_allow_html=True)
