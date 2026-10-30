"""Plotly chart helpers with one consistent palette (dark surface)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

SURFACE = "#15171c"
PANEL = "#1c1f26"
GRID = "#2a2e38"
TEXT = "#e8e8e3"
MUTED = "#9a9c99"
POS = "#199e70"
NEG = "#e66767"
WARN = "#c98500"
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9", "#e66767", "#008300"]

# Fixed colour per entity (never cycled by rank)
SYMBOL_COLOR = {
    "DOGE": SERIES[0], "PEPE": SERIES[1], "FLOKI": SERIES[2], "SHIB": SERIES[3],
    "ETH": SERIES[4], "BTC": SERIES[5], "SOL": SERIES[6], "NVDA": SERIES[0], "QQQ": SERIES[1],
    "AMD": SERIES[2], "NFLX": SERIES[3], "SPY": SERIES[4],
}
SYSTEM_COLOR = {"Robinhood": SERIES[0], "Freqtrade": SERIES[1], "Alpaca": SERIES[2], "CRT skill": SERIES[6]}


def base_layout(fig: go.Figure, height=340, title=None, **kw) -> go.Figure:
    fig.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, system-ui, sans-serif", color=TEXT, size=12),
        margin=dict(l=10, r=10, t=64 if title else 36, b=10), height=height,
        title=dict(text=title, x=0, y=0.98, yanchor="top", font=dict(size=14, color=TEXT)) if title else None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=PANEL, font_color=TEXT, bordercolor=GRID),
        hovermode=kw.pop("hovermode", "x unified"),
        **kw,
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED))
    return fig


def equity_fig(ec: pd.DataFrame, label: str, currency="$") -> go.Figure:
    fig = go.Figure()
    if ec.empty:
        fig.add_annotation(text="No closed trades with known P&L in this selection", showarrow=False, font=dict(color=MUTED))
        return base_layout(fig)
    fig.add_trace(go.Scatter(x=ec["time"], y=ec["cum_pnl"], mode="lines+markers", name=f"Cumulative realised P&L ({label})",
                             line=dict(color=SERIES[0], width=2), marker=dict(size=7),
                             customdata=ec[["trade_id", "symbol", "pnl"]].values,
                             hovertemplate="%{x|%d %b %H:%M}<br>%{customdata[0]} %{customdata[1]}: %{customdata[2]:+.2f}<br>Cum: " + currency + "%{y:.2f}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=GRID, width=1))
    fig.update_yaxes(title_text=f"Realised P&L ({currency})")
    return base_layout(fig, title="Equity curve (cumulative realised P&L, by exit time)")


def drawdown_fig(ec: pd.DataFrame, currency="$") -> go.Figure:
    fig = go.Figure()
    if ec.empty:
        return base_layout(fig, height=220)
    fig.add_trace(go.Scatter(x=ec["time"], y=ec["drawdown"], mode="lines", fill="tozeroy", name="Drawdown from peak",
                             line=dict(color=NEG, width=2), fillcolor="rgba(230,103,103,0.25)",
                             hovertemplate="%{x|%d %b %H:%M}<br>Drawdown: " + currency + "%{y:.2f}<extra></extra>"))
    fig.update_yaxes(title_text=f"Drawdown ({currency})")
    return base_layout(fig, height=220, title="Drawdown over time (realised, from running peak)")


def pnl_bars_fig(df: pd.DataFrame, x: str, y: str, title: str, hover_label="P&L", currency="$", height=260) -> go.Figure:
    colors = [POS if v >= 0 else NEG for v in df[y]]
    fig = go.Figure(go.Bar(x=df[x], y=df[y], marker_color=colors, marker_line_width=0,
                           hovertemplate="%{x}<br>" + hover_label + ": " + currency + "%{y:+.2f}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=GRID, width=1))
    fig.update_traces(marker=dict(cornerradius=4))
    return base_layout(fig, height=height, title=title, hovermode="closest", bargap=0.35)


def contribution_fig(bs: pd.DataFrame, title="Profit contribution by asset", currency="$") -> go.Figure:
    bs = bs.sort_values("net_pnl")
    fig = go.Figure(go.Bar(y=bs["symbol"], x=bs["net_pnl"], orientation="h",
                           marker_color=[POS if v >= 0 else NEG for v in bs["net_pnl"]],
                           customdata=bs[["trades", "win_rate"]].values,
                           hovertemplate="%{y}<br>Net: " + currency + "%{x:+.2f}<br>Trades: %{customdata[0]}<br>Win rate: %{customdata[1]:.0f}%<extra></extra>",
                           text=[f"{v:+.2f}" for v in bs["net_pnl"]], textposition="outside", textfont=dict(color=TEXT)))
    fig.update_traces(marker=dict(cornerradius=4))
    fig.add_vline(x=0, line=dict(color=GRID, width=1))
    return base_layout(fig, height=max(220, 40 * len(bs) + 80), title=title, hovermode="closest")


def allocation_fig(pos: pd.DataFrame, cash: float, limit: float) -> go.Figure:
    labels = list(pos["symbol"]) + ["Cash"]
    values = list(pos["market_value"]) + [cash]
    colors = [SYMBOL_COLOR.get(s, SERIES[7]) for s in pos["symbol"]] + [MUTED]
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.62, marker=dict(colors=colors, line=dict(color=SURFACE, width=2)),
                           textinfo="label+percent", textfont=dict(color=TEXT), sort=False,
                           hovertemplate="%{label}<br>$%{value:,.2f}<br>%{percent}<extra></extra>"))
    fig.add_annotation(text=f"limit {limit:.0%}<br>per position", showarrow=False, font=dict(color=MUTED, size=12))
    return base_layout(fig, height=340, title="Asset allocation (Robinhood ••8275)", hovermode="closest", showlegend=False)


def concentration_fig(pos: pd.DataFrame, limit: float) -> go.Figure:
    p = pos.sort_values("weight", ascending=True)
    colors = [NEG if w > limit else (WARN if w > limit * 0.75 else POS) for w in p["weight"]]
    fig = go.Figure(go.Bar(y=p["symbol"], x=p["weight"] * 100, orientation="h", marker_color=colors,
                           text=[f"{w:.1%}" for w in p["weight"]], textposition="outside", textfont=dict(color=TEXT),
                           hovertemplate="%{y}: %{x:.1f}% of account<extra></extra>"))
    fig.update_traces(marker=dict(cornerradius=4))
    fig.add_vline(x=limit * 100, line=dict(color=NEG, width=2, dash="dash"), annotation_text=f"{limit:.0%} limit",
                  annotation_font_color=NEG, annotation_position="top")
    fig.update_xaxes(title_text="% of account value", range=[0, max(100, p["weight"].max() * 110)])
    return base_layout(fig, height=300, title="Concentration vs the 20% rule", hovermode="closest")


def loss_hist_fig(trades: pd.DataFrame, currency="$") -> go.Figure:
    c = trades[trades["pnl_usd"].notna()]
    fig = go.Figure()
    for system, grp in c.groupby("system"):
        fig.add_trace(go.Histogram(x=grp["pnl_usd"], name=system, marker_color=SYSTEM_COLOR.get(system, SERIES[7]),
                                   opacity=0.85, xbins=dict(size=0.5),
                                   hovertemplate=system + "<br>P&L bin %{x}<br>Trades: %{y}<extra></extra>"))
    fig.update_layout(barmode="overlay")
    fig.add_vline(x=0, line=dict(color=GRID, width=1))
    fig.update_xaxes(title_text=f"Trade P&L ({currency})")
    fig.update_yaxes(title_text="Trades")
    return base_layout(fig, height=280, title="Historical P&L distribution per trade", hovermode="closest")


def fill_timeline_fig(trades: pd.DataFrame, symbol: str, selected_id: str | None = None, candles: pd.DataFrame | None = None) -> go.Figure:
    """Trade markers on a price timeline. Uses real candles when present, otherwise the fill prices themselves."""
    t = trades[trades["symbol"] == symbol]
    fig = go.Figure()
    if candles is not None and not candles.empty:
        fig.add_trace(go.Candlestick(x=candles["time"], open=candles["open"], high=candles["high"], low=candles["low"],
                                     close=candles["close"], name=f"{symbol} 5m", increasing_line_color=POS, decreasing_line_color=NEG))
        fig.update_layout(xaxis_rangeslider_visible=False)
    else:
        pts = pd.concat([
            pd.DataFrame({"time": t["entry_time"], "price": t["entry_price"]}),
            pd.DataFrame({"time": t["exit_time"], "price": t["exit_price"]}),
        ]).dropna().sort_values("time")
        fig.add_trace(go.Scatter(x=pts["time"], y=pts["price"], mode="lines", name="Fill-price path (no OHLC in archive)",
                                 line=dict(color=MUTED, width=1.5, dash="dot"), hoverinfo="skip"))
    buys = t.dropna(subset=["entry_time"])
    sells = t.dropna(subset=["exit_time"])
    fig.add_trace(go.Scatter(x=buys["entry_time"], y=buys["entry_price"], mode="markers", name="Buy",
                             marker=dict(symbol="triangle-up", size=12, color=POS, line=dict(color=SURFACE, width=1.5)),
                             customdata=buys[["trade_id", "qty"]].values,
                             hovertemplate="BUY %{customdata[0]}<br>%{x|%d %b %H:%M}<br>%{y:.8g}<br>qty %{customdata[1]:,.6g}<extra></extra>"))
    fig.add_trace(go.Scatter(x=sells["exit_time"], y=sells["exit_price"], mode="markers", name="Sell",
                             marker=dict(symbol="triangle-down", size=12, color=NEG, line=dict(color=SURFACE, width=1.5)),
                             customdata=sells[["trade_id", "pnl_usd"]].values,
                             hovertemplate="SELL %{customdata[0]}<br>%{x|%d %b %H:%M}<br>%{y:.8g}<br>P&L %{customdata[1]:+.2f}<extra></extra>"))
    if selected_id is not None:
        s = t[t["trade_id"] == selected_id]
        if len(s) and pd.notna(s["entry_time"].iloc[0]) and pd.notna(s["exit_time"].iloc[0]):
            r = s.iloc[0]
            fig.add_shape(type="rect", x0=r["entry_time"], x1=r["exit_time"], y0=min(r["entry_price"], r["exit_price"]),
                          y1=max(r["entry_price"], r["exit_price"]), line=dict(color=SERIES[0], width=1),
                          fillcolor="rgba(57,135,229,0.15)")
            if pd.notna(r.get("stop_price")):
                fig.add_hline(y=r["stop_price"], line=dict(color=WARN, dash="dash", width=1), annotation_text="stop", annotation_font_color=WARN)
    fig.update_yaxes(title_text="Price (USD / USDT)", tickformat=".8g")
    return base_layout(fig, height=380, title=f"{symbol}: trades on price timeline", hovermode="closest")


def strategy_compare_fig(tbl: pd.DataFrame, metric: str) -> go.Figure:
    d = tbl[tbl[metric].notna()].copy()
    d["label"] = d["System"] + " / " + d["Strategy"].str.replace(" (inferred)", "", regex=False)
    if metric in ("Net P&L ($)", "Return on stake (%)", "Expectancy ($/trade)"):
        colors = [POS if v >= 0 else NEG for v in d[metric]]
    else:
        colors = [SYSTEM_COLOR.get(s, SERIES[7]) for s in d["System"]]
    fig = go.Figure(go.Bar(y=d["label"], x=d[metric], orientation="h", marker_color=colors,
                           text=[f"{v:,.2f}" for v in d[metric]], textposition="outside", textfont=dict(color=TEXT),
                           hovertemplate="%{y}<br>" + metric + ": %{x:,.2f}<extra></extra>"))
    fig.update_traces(marker=dict(cornerradius=4))
    fig.add_vline(x=0, line=dict(color=GRID, width=1))
    return base_layout(fig, height=max(240, 44 * len(d) + 80), title=metric, hovermode="closest")


def duration_scatter_fig(trades: pd.DataFrame) -> go.Figure:
    c = trades[trades["pnl_usd"].notna() & trades["duration"].notna()].copy()
    c["hours"] = c["duration"].dt.total_seconds() / 3600
    fig = go.Figure()
    for system, grp in c.groupby("system"):
        fig.add_trace(go.Scatter(x=grp["hours"], y=grp["pnl_pct"], mode="markers", name=system,
                                 marker=dict(size=10, color=SYSTEM_COLOR.get(system, SERIES[7]), line=dict(color=SURFACE, width=1.5)),
                                 customdata=grp[["trade_id", "symbol", "exit_reason_code"]].values,
                                 hovertemplate="%{customdata[0]} %{customdata[1]}<br>%{x:.1f} h, %{y:+.2f}%<br>exit: %{customdata[2]}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=GRID, width=1))
    fig.update_xaxes(title_text="Holding time (hours, log)", type="log")
    fig.update_yaxes(title_text="Trade return (%)")
    return base_layout(fig, height=320, title="Holding time vs trade return", hovermode="closest")


def exit_reason_fig(trades: pd.DataFrame) -> go.Figure:
    c = trades[trades["pnl_usd"].notna()]
    g = c.groupby("exit_reason_code")["pnl_usd"].agg(["count", "sum", "mean"]).reset_index()
    fig = go.Figure(go.Bar(x=g["exit_reason_code"], y=g["sum"], marker_color=[POS if v >= 0 else NEG for v in g["sum"]],
                           customdata=g[["count", "mean"]].values,
                           text=[f"{n} trades" for n in g["count"]], textposition="outside", textfont=dict(color=TEXT),
                           hovertemplate="%{x}<br>Net: %{y:+.2f}<br>Trades: %{customdata[0]}<br>Avg: %{customdata[1]:+.3f}<extra></extra>"))
    fig.update_traces(marker=dict(cornerradius=4))
    fig.add_hline(y=0, line=dict(color=GRID, width=1))
    return base_layout(fig, height=280, title="Net P&L by exit reason", hovermode="closest")


def hour_heat_fig(trades: pd.DataFrame, tz) -> go.Figure:
    c = trades[trades["pnl_usd"].notna() & trades["entry_time"].notna()].copy()
    c["hour"] = c["entry_time"].dt.tz_convert(tz).dt.hour
    g = c.groupby("hour")["pnl_usd"].agg(["sum", "count"]).reindex(range(24), fill_value=0).reset_index()
    fig = go.Figure(go.Bar(x=g["hour"], y=g["sum"], marker_color=[POS if v >= 0 else NEG for v in g["sum"]],
                           customdata=g[["count"]].values,
                           hovertemplate="Entry hour %{x}:00<br>Net %{y:+.2f}<br>%{customdata[0]} trades<extra></extra>"))
    fig.update_traces(marker=dict(cornerradius=3))
    fig.update_xaxes(title_text=f"Entry hour ({tz.key})", dtick=2)
    return base_layout(fig, height=240, title="Net P&L by entry hour", hovermode="closest")
