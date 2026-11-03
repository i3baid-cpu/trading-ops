"""Alpaca TrendFilter panel: what the bot did and why, what the sleeve is worth, and what the next monthly check will do.
Read only. Uses the Lumibot config, ledger and journal mounted into the container plus Yahoo daily closes; no broker access."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import charts as C
import trendfilter_calc as TC

try:
    import data_live as DL
except Exception:  # file mode
    DL = None

NY = ZoneInfo("America/New_York")
KWT = ZoneInfo("Asia/Kuwait")
SRC_BOT, SRC_REPLAY = "bot journal (what the bot did)", "replayed on Yahoo closes (what the rule would have done)"


@st.cache_data(ttl=900, show_spinner=False)
def _yahoo_daily(sym: str) -> pd.DataFrame | None:
    """3 years of daily closes, so SMA200 exists for every check in the last 12 months. Includes today's bar if the
    market is open; callers that need completed sessions drop it."""
    try:
        import yfinance as yf
        h = yf.Ticker(sym).history(period="3y", interval="1d", auto_adjust=False, timeout=8)
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
    today = today or datetime.now(NY).date()
    first_this = _nyse_first_trading_day(today.year, today.month)
    if today <= first_this:
        return first_this
    y, m = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return _nyse_first_trading_day(y, m)


def _ny_day(ts) -> date:
    return pd.Timestamp(ts).tz_convert(NY).date()


def _bot_checks(journal: pd.DataFrame, sym: str) -> pd.DataFrame:
    """The bot's own check decisions for one symbol, first per month (a rerun after a restart is not a new decision)."""
    if journal.empty or "month" not in journal:
        return pd.DataFrame()
    c = journal[(journal["event"] == "check") & (journal["symbol"] == sym)].drop_duplicates("month", keep="first")
    rows = []
    for _, r in c.iterrows():
        close, avg, band = float(r["close"]), float(r["sma"]), float(r.get("band", 0) or 0)
        held = float(r.get("qty_held") or 0) > 0
        action = {"buy": "BUY", "sell": "SELL"}.get(r["action"], "HOLD (in)" if held else "STAY OUT")
        rows.append({"check_day": _ny_day(r["ts"]), "close": close, "sma": avg, "distance_pct": (close / avg - 1) * 100,
                     "buy_line": avg * (1 + band), "sell_line": avg * (1 - band), "held_before": held, "action": action,
                     "why": f"{r['reason']} (close {close:,.2f}, SMA {avg:,.2f})", "source": SRC_BOT})
    return pd.DataFrame(rows)


def _merged_checks(replay: pd.DataFrame, bot: pd.DataFrame, months: int = 12) -> pd.DataFrame:
    r = replay.assign(source=SRC_REPLAY)
    if not bot.empty:
        bot_months = {(d.year, d.month) for d in bot["check_day"]}
        r = pd.concat([r[[(d.year, d.month) not in bot_months for d in r["check_day"]]], bot], ignore_index=True)
    return r.sort_values("check_day").tail(months).reset_index(drop=True)


def render(kpi, money, tone_of, badge, al_live, al_cfg_file: dict):
    cfg = (DL.load_lumibot_config() if DL else None) or al_cfg_file or {}
    params = cfg.get("params", {})
    symbols = cfg.get("symbols", ["SPY", "QQQ"])
    sma, band = int(params.get("sma", 200)), float(params.get("band_pct", 0.0))
    capital = float(cfg.get("capital_usd", 1000))
    al_pos, al_sum = al_live if al_live else (None, {})
    held = {} if al_pos is None else {r["symbol"]: r for _, r in al_pos.iterrows()}
    realized = float(al_sum.get("realized") or 0.0)
    journal = TC.read_journal(TC.JOURNAL)
    fl = TC.fill_reasons(journal) if not journal.empty else TC.fills(journal).assign(why=[])
    today = datetime.now(NY).date()
    nxt = next_monthly_check(today)

    st.markdown(f"#### Alpaca TrendFilter {badge("<span class='dot paper'></span>PAPER · $" + format(capital, ',.0f') + ' sleeve', 'paper')} &nbsp; <span class='src'>{cfg.get('strategy', 'trend_filter')} · {', '.join(symbols)} · SMA{sma} with {band:.0%} band · {params.get('check', 'daily')} check · paper = {cfg.get('paper')}</span>", unsafe_allow_html=True)

    # Prices: all bars for valuation, completed sessions for the rule.
    px, done, last_px = {}, {}, {}
    for s in symbols:
        h = _yahoo_daily(s)
        if h is None or h.empty:
            continue
        px[s] = h
        done[s] = h[h["date"] < today]
        last_px[s] = (float(h["close"].iloc[-1]), h["date"].iloc[-1])

    # Sleeve value now: ledger cash + held qty x latest Yahoo price.
    invested = sum(float(p["cost_usd"]) for p in held.values())
    cash = capital + realized - invested
    priced = all(s in last_px for s in held)
    value = cash + sum(float(p["qty"]) * last_px[s][0] for s, p in held.items()) if priced else None
    pnl = value - capital if value is not None else None
    curve = TC.sleeve_curve(TC.fills(journal), px, capital, _ny_day, symbols[0]) if not journal.empty else pd.DataFrame()
    bench = float(curve["bench"].iloc[-1]) if not curve.empty else None

    # The bot's own close and SMA from its latest daily journal line; Yahoo only when the journal has none.
    # (On 3 Nov the bot's SPY SMA200 was 726.30 and Yahoo's 729.15: the two sources adjust past prices differently.)
    bot_sig = TC.bot_signals(journal)
    triggers = {s: (TC.trigger(bot_sig[s][1], bot_sig[s][2], band, s in held, bot_sig[s][0], "bot") if s in bot_sig
                    else TC.next_trigger(done[s], sma, band, s in held) if s in done else None) for s in symbols}

    # What's going on, in sentences.
    lines = []
    if held:
        buys = fl[fl["side"] == "buy"] if not fl.empty else fl
        bought = [f"{float(p['qty']):.3f} {s} at {float(p['avg_cost']):,.2f}" for s, p in held.items()]
        when = f" on {buys['ts'].max().tz_convert(KWT):%a %d %b}" if len(buys) else ""
        lines.append(f"The bot holds {' and '.join(bought)} (average cost), bought{when}.")
    else:
        lines.append("The bot holds nothing right now; the sleeve is all cash.")
    if value is not None:
        lines.append(f"The sleeve is worth <b>{money(value)}</b>, {money(pnl, signed=True)} ({pnl / capital:+.2%}) on the ${capital:,.0f} start"
                     + (f"; the same ${capital:,.0f} put into {symbols[0]} alone at the bot's price would be {money(bench)}." if bench else "."))
    for s, t in triggers.items():
        if t is None:
            continue
        if s in held:
            lines.append(f"<b>{s}</b> sells at the {nxt:%a %d %b} check only if its last close before then is below about <b>{t['line']:,.2f}</b> "
                         f"({t['source']} SMA{sma} {t['sma']:,.2f} minus {band:.0%}); the latest completed close {t['close']:,.2f} (as of {t['as_of']:%d %b}) is {t['cushion_pct']:+.1f}% from that line.")
        else:
            lines.append(f"<b>{s}</b> is bought at the {nxt:%a %d %b} check only if its last close before then is above about <b>{t['line']:,.2f}</b> "
                         f"({t['source']} SMA{sma} plus {band:.0%}); the latest completed close {t['close']:,.2f} (as of {t['as_of']:%d %b}) is {t['cushion_pct']:+.1f}% from that line.")
    lines.append("Between checks the bot does nothing, whatever the price does: it decides once a month, on the first trading day.")
    st.markdown("<div class='panel'><h4>What's going on</h4><ul style='font-size:13.5px;padding-left:18px;margin:0'>"
                + "".join(f"<li>{l}</li>" for l in lines) + "</ul></div>", unsafe_allow_html=True)

    c = st.columns(4)
    with c[0]:
        kpi("Sleeve value", money(value), f"cash {money(cash)} + positions at the last Yahoo price")
    with c[1]:
        kpi("Gain / loss", money(pnl, signed=True), f"{pnl / capital:+.2%} of ${capital:,.0f}" if pnl is not None else "price not available", tone_of(pnl))
    with c[2]:
        diff = value - bench if value is not None and bench else None
        kpi(f"vs {symbols[0]} only", money(diff, signed=True), f"${capital:,.0f} in {symbols[0]} would be {money(bench)}" if bench else "needs the journal", tone_of(diff))
    with c[3]:
        kpi("Next monthly check", nxt.strftime("%a %d %b"), f"in {(nxt - today).days} days, first NYSE session, after the open")
    c = st.columns(4)
    with c[0]:
        state = {s: ("above" if t["close"] > t["sma"] * (1 + band) else "below" if t["close"] < t["sma"] * (1 - band) else "in the band")
                 for s, t in triggers.items() if t}
        exits = [s for s in held if state.get(s) == "below"]
        kpi("Signal now", "sell line crossed" if exits else ("no change due" if state else "Not available"),
            ", ".join(f"{s} {v}" for s, v in state.items()) + f" (SMA{sma} ±{band:.0%}, last completed close)", "neg" if exits else ("pos" if state else "warn"))
    with c[1]:
        kpi("Positions held", str(len(held)), ", ".join(held) if held else "none", "pos" if held else "")
    with c[2]:
        kpi("Realised P&L", money(realized, signed=True), "from sells, sleeve ledger", tone_of(realized) if realized else "")
    with c[3]:
        last_ev = journal["ts"].max() if not journal.empty else None
        kpi("Bot journal", f"{len(journal)} events" if last_ev is not None else "not found",
            f"last {last_ev.tz_convert(KWT):%d %b %H:%M} KWT" if last_ev is not None else "fill times and reasons need it", "" if last_ev is not None else "warn")

    st.plotly_chart(C.sleeve_value_fig(curve, capital, _daily_points(journal), f"Same ${capital:,.0f} in {symbols[0]} only, held"),
                    width="stretch", config={"displaylogo": False})

    st.markdown("#### Trades the bot made")
    if not fl.empty:
        tv = pd.DataFrame({"Time (KWT)": fl["ts"].map(lambda t: t.tz_convert(KWT).strftime("%Y-%m-%d %H:%M")),
                           "Action": fl["side"].str.upper(), "Symbol": fl["symbol"], "Qty": fl["qty"], "Price": fl["price"],
                           "Amount": (fl["qty"] * fl["price"]).round(2), "P&L on this trade": fl["pnl"].where(fl["side"] == "sell"),
                           "Why": fl["why"]})
        st.dataframe(tv, hide_index=True, width="stretch",
                     column_config={"Qty": st.column_config.NumberColumn(format="%.3f"), "Price": st.column_config.NumberColumn(format="%.2f"),
                                    "Amount": st.column_config.NumberColumn(format="$%.2f"), "P&L on this trade": st.column_config.NumberColumn(format="%+.2f")})
    elif held:
        st.info("The positions are in the ledger, but the bot journal is not there yet, so fill times and reasons cannot be shown.")
    else:
        st.caption("No trades yet.")
    errs = journal[journal["event"] == "order_error"] if not journal.empty else journal
    if len(errs):
        st.error(f"{len(errs)} order error(s) in the journal")
        st.dataframe(errs.assign(ts=errs["ts"].map(lambda t: t.tz_convert(KWT).strftime("%Y-%m-%d %H:%M")))[["ts", "symbol", "side", "qty", "error"]],
                     hide_index=True, width="stretch")

    st.markdown(f"#### Why it traded or not: the monthly checks <span class='src'>one row per first trading day; {SRC_BOT} where the journal has it, otherwise {SRC_REPLAY}</span>", unsafe_allow_html=True)
    sub = st.tabs(symbols)
    for s, tab in zip(symbols, sub):
        with tab:
            if s not in done or len(done[s]) < sma:
                st.warning(f"{s}: Yahoo daily closes Not available, so the chart and the replay cannot be drawn.")
                continue
            checks = _merged_checks(TC.rule_history(done[s], sma, band), _bot_checks(journal, s))
            hs = TC.with_sma(px[s], sma, band)
            hs = hs[hs["date"] >= today - timedelta(days=380)]
            sf = TC.fills(journal)
            sf = sf[sf["symbol"] == s].assign(day=lambda d: d["ts"].map(_ny_day)) if not sf.empty else sf
            avg = float(held[s]["avg_cost"]) if s in held else None
            st.plotly_chart(C.trendfilter_price_fig(hs, s, sma, band, checks, sf, avg, nxt), width="stretch", config={"displaylogo": False})
            ct = pd.DataFrame({"Check day": checks["check_day"].astype(str), "Decision": checks["action"], "Close": checks["close"].round(2),
                               f"SMA{sma}": checks["sma"].round(2), "Distance": checks["distance_pct"].map(lambda v: f"{v:+.1f}%"),
                               "Buy line": checks["buy_line"].round(2), "Sell line": checks["sell_line"].round(2),
                               "Why": checks["why"], "Source": checks["source"]})
            st.dataframe(ct.iloc[::-1], hide_index=True, width="stretch")
    st.caption(f"The replay starts flat at the first check with {sma} sessions of history, so its earliest rows can differ from a bot that had been running then. "
               "The bot started on 30 Oct 2026; everything before its first journal row is what the rule would have done, not trades. "
               "Charts, the replay and the sleeve value use Yahoo daily closes (the latest bar can be intraday). The bot uses Alpaca's bars, whose SMA200 can differ "
               "from Yahoo's by about half a percent, so the sell and buy lines above use the bot's own numbers from its latest daily journal line when there is one. "
               "The dashboard has no broker access.")


def _daily_points(journal: pd.DataFrame) -> pd.DataFrame:
    if journal.empty or "value" not in journal:
        return pd.DataFrame()
    d = journal[journal["event"] == "daily"].drop_duplicates("day", keep="last")
    return pd.DataFrame({"date": pd.to_datetime(d["day"]).dt.date, "value": pd.to_numeric(d["value"], errors="coerce")})
