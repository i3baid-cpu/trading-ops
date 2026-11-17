"""Replay and ridge panels for the Freqtrade tab. Read only: no exchange client, no orders, no model in the loop.

replay: walks the last completed 4h candles of one pair and prints, candle by candle, what MemeSleeveV4's rules
        decide (WAIT with the missing piece, ENTER, HOLD, EXIT, STOP). Same answer every time for the same candles.
ridge:  one glowing ridge per pair: how far each 4h close was from its entry trigger (the higher of EMA50 and the
        prior 20 bar high), plus the BTC daily gate. It shows distance to a rule, not performance of parameters.

Simplifications, stated in the panel: candles come from Yahoo (the bot uses Binance); the 10% trailing stop and the
cooldown are not replayed; an entry is shown on the signal candle and priced at the next open, as the bot does.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import charts as C

STOP = 0.15
TAG_COLOR = {"WAIT": "#c98500", "ENTER": "#19c37d", "HOLD": "#3987e5", "EXIT": "#e66767", "STOP": "#e66767"}
NEON = ["#7c5cff", "#3987e5", "#22b8cf", "#19c37d", "#8bd450", "#ffd166"]
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"


def to_4h(h1: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """1h bars to completed 4h candles, indexed by candle open time (UTC)."""
    w = h1.set_index("date").resample("4h").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    return w[w.index + pd.Timedelta(hours=4) <= now]


def gate_series(btc_daily: pd.DataFrame, now: pd.Timestamp) -> pd.DataFrame:
    """Completed BTC daily candles with the gate value and the time from which the bot may use it (the daily close)."""
    d = btc_daily.sort_values("date").copy()
    d["ema100"] = d["close"].ewm(span=100, adjust=False).mean()
    d["gap_pct"] = (d["close"] / d["ema100"] - 1) * 100
    d["btc_up"] = d["close"] > d["ema100"]
    d["avail"] = d["date"].dt.normalize() + pd.Timedelta(days=1)
    return d[d["avail"] <= now][["avail", "btc_up", "gap_pct"]]


def v4_decisions(w: pd.DataFrame, gate: pd.DataFrame) -> pd.DataFrame:
    """MemeSleeveV4's rules on completed 4h candles. Every value on a row uses data up to that candle's close only."""
    d = w.copy()
    d["ema50"] = d["close"].ewm(span=50, adjust=False).mean()
    d["hh20"] = d["high"].rolling(20).max().shift(1)                  # prior 20 candles, current one excluded
    d["vol_mean"] = d["volume"].rolling(20).mean()
    d["t_close"] = d.index + pd.Timedelta(hours=4)
    g = pd.merge_asof(d[["t_close"]].reset_index(), gate.sort_values("avail"), left_on="t_close", right_on="avail")
    d["btc_up"] = g["btc_up"].values
    d["gap_pct"] = g["gap_pct"].values
    d["trigger"] = d[["ema50", "hh20"]].max(axis=1)
    d["dist_pct"] = (d["close"] / d["trigger"] - 1) * 100
    tags, why, entry_px = [], [], []
    in_pos, entry = False, None
    opens = d["open"].shift(-1)
    for i, (t, r) in enumerate(d.iterrows()):
        if pd.isna(r["hh20"]) or pd.isna(r["vol_mean"]) or pd.isna(r["btc_up"]):
            tags.append("WARMUP"); why.append("not enough history yet"); entry_px.append(None); continue
        gate_open = bool(r["btc_up"])
        vol_known = r["vol_mean"] > 0
        vol_ok = (r["volume"] > r["vol_mean"]) if vol_known else False
        if in_pos:
            if entry is not None and r["low"] <= entry * (1 - STOP):
                tags.append("STOP"); why.append(f"15% stop hit (low {r['low']:.4g})"); in_pos, entry = False, None
            elif not gate_open:
                tags.append("EXIT"); why.append(f"BTC gate shut ({r['gap_pct']:+.1f}% vs EMA100)"); in_pos, entry = False, None
            elif r["close"] < r["ema50"]:
                tags.append("EXIT"); why.append(f"close {(r['close'] / r['ema50'] - 1) * 100:+.1f}% under EMA50"); in_pos, entry = False, None
            else:
                tags.append("HOLD"); why.append(f"above EMA50 by {(r['close'] / r['ema50'] - 1) * 100:.1f}%, gate open")
            entry_px.append(None)
            continue
        if not gate_open:
            tags.append("WAIT"); why.append(f"BTC gate shut ({r['gap_pct']:+.1f}% vs EMA100)")
        elif r["close"] <= r["ema50"]:
            tags.append("WAIT"); why.append(f"close {(r['close'] / r['ema50'] - 1) * 100:+.1f}% under EMA50")
        elif r["close"] <= r["hh20"]:
            tags.append("WAIT"); why.append(f"{(1 - r['close'] / r['hh20']) * 100:.1f}% below the 20 bar high")
        elif not vol_ok:
            tags.append("WAIT"); why.append("breakout, volume " + (f"{r['volume'] / r['vol_mean']:.2f}x of average" if vol_known else "not available"))
        else:
            nxt = opens.iloc[i]
            tags.append("ENTER"); why.append(f"breakout, vol {r['volume'] / r['vol_mean']:.2f}x, buy next open")
            in_pos, entry = True, (float(nxt) if pd.notna(nxt) else float(r["close"]))
            entry_px.append(entry); continue
        entry_px.append(None)
    d["tag"], d["why"], d["entry_px"] = tags, why, entry_px
    return d


def _log_text(d: pd.DataFrame, i: int, lines: int = 7) -> str:
    out = []
    for j in range(i, max(-1, i - lines), -1):
        r = d.iloc[j]
        out.append(f"<span style='color:{TAG_COLOR[r['tag']]}'><b>{r['tag']:<5}</b></span> <span style='color:{C.MUTED}'>{d.index[j]:%d %b %H}h</span>  {r['why']}")
    return "<br>".join(out)


def _counter(d: pd.DataFrame, i: int, n: int) -> str:
    c = d["tag"].iloc[: i + 1].value_counts()
    parts = [f"<span style='color:{TAG_COLOR[k]}'>{k} {int(c.get(k, 0))}</span>" for k in ("WAIT", "ENTER", "HOLD", "EXIT", "STOP") if c.get(k, 0)]
    return f"candle {i + 1} / {n} · " + " · ".join(parts)


def replay_fig(name: str, dec: pd.DataFrame, n: int = 90, start: int = 8) -> go.Figure | None:
    d = dec[dec["tag"] != "WARMUP"].tail(n)
    if len(d) < start + 2:
        return None
    n = len(d)
    x = list(d.index)
    ent = d["tag"] == "ENTER"
    out = d["tag"].isin(["EXIT", "STOP"])

    def traces(i: int) -> list:
        s = slice(0, i + 1)
        e, o = ent.values[s], out.values[s]
        xs = np.array(x[s])
        return [
            go.Candlestick(x=x[s], open=d["open"].values[s], high=d["high"].values[s], low=d["low"].values[s], close=d["close"].values[s],
                           increasing_line_color=C.POS, decreasing_line_color=C.NEG, increasing_fillcolor=C.POS, decreasing_fillcolor=C.NEG,
                           name=name, showlegend=False),
            go.Scatter(x=x[s], y=d["ema50"].values[s], mode="lines", line=dict(color="#22b8cf", width=1.6), name="EMA50"),
            go.Scatter(x=x[s], y=d["hh20"].values[s], mode="lines", line=dict(color="#c98500", width=1.2, dash="dot", shape="hv"), name="Prior 20 bar high"),
            go.Scatter(x=xs[e], y=d["low"].values[s][e] * 0.985, mode="markers", marker=dict(symbol="triangle-up", size=13, color=TAG_COLOR["ENTER"], line=dict(color="#fff", width=1)), name="ENTER"),
            go.Scatter(x=xs[o], y=d["high"].values[s][o] * 1.015, mode="markers", marker=dict(symbol="triangle-down", size=13, color=TAG_COLOR["EXIT"], line=dict(color="#fff", width=1)), name="EXIT"),
        ]

    def notes(i: int) -> list:
        return [
            dict(xref="paper", yref="paper", x=0, y=0.30, xanchor="left", yanchor="top", align="left", showarrow=False,
                 text=_log_text(d, i), font=dict(family=MONO, size=11, color=C.TEXT)),
            dict(xref="paper", yref="paper", x=0, y=0.335, xanchor="left", yanchor="middle", showarrow=False,
                 text=_counter(d, i, n), font=dict(family=MONO, size=11, color=C.MUTED)),
            dict(xref="paper", yref="paper", x=0, y=0.37, xanchor="left", yanchor="middle", showarrow=False,
                 text="DECISION LOG · newest first", font=dict(family=MONO, size=10, color=C.MUTED)),
        ]

    fig = go.Figure(data=traces(n - 1))
    fig.frames = [go.Frame(name=str(i), data=traces(i), layout=dict(annotations=notes(i))) for i in range(start, n)]
    lo, hi = float(d["low"].min()), float(d["high"].max())
    pad = (hi - lo) * 0.08
    C.base_layout(fig, height=600, hovermode="x")
    fig.update_layout(
        annotations=notes(n - 1), margin=dict(l=8, r=8, t=50, b=8), showlegend=False,
        xaxis=dict(range=[x[0] - pd.Timedelta(hours=4), x[-1] + pd.Timedelta(hours=8)], rangeslider=dict(visible=False), domain=[0, 1], tickformat="%d %b"),
        yaxis=dict(range=[lo - pad, hi + pad], domain=[0.44, 1], side="right", tickformat=".4g"),
        updatemenus=[dict(type="buttons", direction="left", x=0, y=1.0, xanchor="left", yanchor="bottom", pad=dict(b=6, l=0), showactive=False,
                          bgcolor=C.PANEL, bordercolor=C.GRID, font=dict(color=C.TEXT, size=11),
                          buttons=[dict(label="▶ Replay", method="animate",
                                        args=[None, dict(frame=dict(duration=130, redraw=True), transition=dict(duration=0), fromcurrent=False, mode="immediate")]),
                                   dict(label="❚❚ Pause", method="animate", args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
    )
    return fig


def ridge_fig(series: dict[str, pd.Series], floor: float = -20.0, cap: float = 10.0, step: int = 2) -> go.Figure | None:
    """series: name -> distance to the trigger in percent, one value per completed 4h candle (same length each).
    Height 0 is `floor` percent below the trigger; the dashed line on every ridge is the trigger itself."""
    series = {k: v.dropna() for k, v in series.items() if v is not None and len(v.dropna()) >= 20}
    if not series:
        return None
    n = min(len(v) for v in series.values())
    names = list(series)
    K = len(names)
    sx, sy = n * 0.045, 9.0                    # perspective: each ridge further back sits right and up
    base_h = -floor                            # height of the trigger line above the ridge floor

    def geom(k: int, i: int):
        v = series[names[k]].values[-n:][: i + 1]
        h = np.clip(v, floor, cap) - floor
        depth = K - 1 - k                      # k = 0 is drawn first (back)
        xs = np.arange(len(h)) + depth * sx
        return xs, h + depth * sy, depth

    def traces(i: int) -> list:
        out = []
        for k in range(K):
            xs, ys, depth = geom(k, i)
            col = NEON[k % len(NEON)]
            y0 = depth * sy
            out.append(go.Scatter(x=np.r_[xs, xs[-1], xs[0]], y=np.r_[ys, y0, y0], mode="lines", fill="toself", fillcolor="rgba(21,23,28,0.94)",
                                  line=dict(color="rgba(0,0,0,0)", width=0), hoverinfo="skip", showlegend=False))
            out.append(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=col, width=7), opacity=0.16, hoverinfo="skip", showlegend=False))
            out.append(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=col, width=1.8), hoverinfo="skip", showlegend=False))
            out.append(go.Scatter(x=[depth * sx, depth * sx + n - 1], y=[y0 + base_h, y0 + base_h], mode="lines",
                                  line=dict(color=col, width=0.8, dash="dot"), opacity=0.55, hoverinfo="skip", showlegend=False))
        return out

    def notes(i: int) -> list:
        a = []
        for k in range(K):
            depth = K - 1 - k
            v = float(series[names[k]].values[-n:][i])
            tone = TAG_COLOR["ENTER"] if v > 0 else C.TEXT
            a.append(dict(x=depth * sx + n - 1 + n * 0.015, y=depth * sy + base_h, xanchor="left", yanchor="middle", showarrow=False,
                          text=f"<b>{names[k]}</b> <span style='color:{tone}'>{v:+.1f}%</span>", font=dict(family=MONO, size=11, color=NEON[k % len(NEON)]), bgcolor="rgba(21,23,28,0.85)"))
        return a

    fig = go.Figure(data=traces(n - 1))
    fig.frames = [go.Frame(name=str(i), data=traces(i), layout=dict(annotations=notes(i))) for i in list(range(6, n - 1, step)) + [n - 1]]
    C.base_layout(fig, height=400, hovermode=False)
    fig.update_layout(
        annotations=notes(n - 1), margin=dict(l=8, r=8, t=44, b=8), showlegend=False,
        xaxis=dict(visible=False, range=[-2, n - 1 + (K - 1) * sx + n * 0.42]),
        yaxis=dict(visible=False, range=[-2, (K - 1) * sy + (cap - floor) + 4]),
        updatemenus=[dict(type="buttons", direction="left", x=0, y=1.12, xanchor="left", yanchor="top", showactive=False,
                          bgcolor=C.PANEL, bordercolor=C.GRID, font=dict(color=C.TEXT, size=11),
                          buttons=[dict(label="▶ Sweep", method="animate",
                                        args=[None, dict(frame=dict(duration=70, redraw=True), transition=dict(duration=0), fromcurrent=False, mode="immediate")])])],
    )
    return fig


TF_TAG = {"BUY": ("BUY", "#19c37d"), "SELL": ("SELL", "#e66767"), "HOLD (in)": ("HOLD", "#3987e5"), "STAY OUT": ("OUT", "#c98500")}


def _tf_line(r, sma: int) -> str:
    tag, col = TF_TAG.get(r["action"], (str(r["action"])[:5], C.MUTED))
    d = float(r["distance_pct"])
    why = {"BUY": f"close {d:+.1f}% vs SMA{sma}: buy", "SELL": f"close {d:+.1f}% vs SMA{sma}: sell",
           "HOLD (in)": f"held, close {d:+.1f}% vs SMA{sma}", "STAY OUT": f"not held, close {d:+.1f}% vs SMA{sma}"}.get(r["action"], "")
    return f"<span style='color:{col}'><b>{tag:<5}</b></span> <span style='color:{C.MUTED}'>{pd.Timestamp(r['check_day']):%d %b %y}</span>  {why}"


def tf_replay_fig(hs: pd.DataFrame, sym: str, sma: int, band: float, checks: pd.DataFrame, step: int = 3, lines: int = 7) -> go.Figure | None:
    """TrendFilter replay: daily closes against the SMA band, one decision per monthly check.
    hs: date, close, sma, upper, lower (completed sessions). checks: check_day, action, close, distance_pct."""
    hs = hs.dropna(subset=["sma"]).reset_index(drop=True)
    if len(hs) < 40 or checks is None or checks.empty:
        return None
    ck = checks[checks["check_day"] >= hs["date"].iloc[0]].sort_values("check_day").reset_index(drop=True)
    if ck.empty:
        return None
    x = [pd.Timestamp(d) for d in hs["date"]]
    cx = [pd.Timestamp(d) for d in ck["check_day"]]
    n = len(hs)

    def traces(i: int) -> list:
        s = slice(0, i + 1)
        seen = [j for j, d in enumerate(cx) if d <= x[i]]
        out = [
            go.Scatter(x=x[s], y=hs["upper"].values[s], mode="lines", line=dict(color="rgba(34,184,207,0.55)", width=1, dash="dot"), hoverinfo="skip"),
            go.Scatter(x=x[s], y=hs["lower"].values[s], mode="lines", line=dict(color="rgba(34,184,207,0.55)", width=1, dash="dot"),
                       fill="tonexty", fillcolor="rgba(34,184,207,0.16)", hoverinfo="skip"),
            go.Scatter(x=x[s], y=hs["sma"].values[s], mode="lines", line=dict(color="#22b8cf", width=1.6), name=f"SMA{sma}"),
            go.Scatter(x=x[s], y=hs["close"].values[s], mode="lines", line=dict(color=C.TEXT, width=1.8), name=sym),
            go.Scatter(x=[cx[j] for j in seen], y=[float(ck["close"].iloc[j]) for j in seen], mode="markers",
                       marker=dict(size=11, color=[TF_TAG.get(ck["action"].iloc[j], ("", C.MUTED))[1] for j in seen], line=dict(color="#fff", width=1)),
                       text=[ck["action"].iloc[j] for j in seen], hovertemplate="%{x|%d %b %Y}: %{text}<extra></extra>"),
        ]
        return out

    def notes(i: int) -> list:
        seen = [j for j, d in enumerate(cx) if d <= x[i]]
        log = "<br>".join(_tf_line(ck.iloc[j], sma) for j in reversed(seen[-lines:])) or f"<span style='color:{C.MUTED}'>no monthly check yet</span>"
        c = ck["action"].iloc[seen].map(lambda a: TF_TAG.get(a, (a, ""))[0]).value_counts() if seen else {}
        counter = f"{x[i]:%d %b %y} · checks {len(seen)}" + "".join(f" · <span style='color:{col}'>{tag} {int(c.get(tag, 0))}</span>" for tag, col in TF_TAG.values() if c.get(tag, 0))
        return [
            dict(xref="paper", yref="paper", x=0, y=0.30, xanchor="left", yanchor="top", align="left", showarrow=False, text=log, font=dict(family=MONO, size=11, color=C.TEXT)),
            dict(xref="paper", yref="paper", x=0, y=0.335, xanchor="left", yanchor="middle", showarrow=False, text=counter, font=dict(family=MONO, size=11, color=C.MUTED)),
            dict(xref="paper", yref="paper", x=0, y=0.37, xanchor="left", yanchor="middle", showarrow=False, text="MONTHLY CHECKS · newest first", font=dict(family=MONO, size=10, color=C.MUTED)),
        ]

    idx = list(range(20, n - 1, step)) + [n - 1]
    fig = go.Figure(data=traces(n - 1))
    fig.frames = [go.Frame(name=str(i), data=traces(i), layout=dict(annotations=notes(i))) for i in idx]
    lo = float(min(hs["close"].min(), hs["lower"].min())); hi = float(max(hs["close"].max(), hs["upper"].max()))
    pad = (hi - lo) * 0.06
    C.base_layout(fig, height=600, hovermode="closest")
    fig.update_layout(
        annotations=notes(n - 1), margin=dict(l=8, r=8, t=50, b=8), showlegend=False,
        xaxis=dict(range=[x[0], x[-1] + pd.Timedelta(days=6)], domain=[0, 1], tickformat="%b %y"),
        yaxis=dict(range=[lo - pad, hi + pad], domain=[0.44, 1], side="right"),
        updatemenus=[dict(type="buttons", direction="left", x=0, y=1.0, xanchor="left", yanchor="bottom", pad=dict(b=6, l=0), showactive=False,
                          bgcolor=C.PANEL, bordercolor=C.GRID, font=dict(color=C.TEXT, size=11),
                          buttons=[dict(label="▶ Replay", method="animate",
                                        args=[None, dict(frame=dict(duration=90, redraw=True), transition=dict(duration=0), fromcurrent=False, mode="immediate")]),
                                   dict(label="❚❚ Pause", method="animate", args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
    )
    return fig


def render_tf(st, hs: pd.DataFrame, sym: str, sma: int, band: float, checks: pd.DataFrame):
    """Replay block for one TrendFilter symbol, shown inside the stock bot tab."""
    st.markdown("<style>div[class*='st-key-replay_'] .js-plotly-plot { max-height: none !important; }</style>", unsafe_allow_html=True)
    fig = tf_replay_fig(hs, sym, sma, band, checks)
    if fig is None:
        st.caption(f"{sym} replay: not enough history yet.")
        return
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "displayModeBar": False}, key=f"replay_tf_{sym}")
    st.markdown(f"<div class='src'>White line: {sym} daily close · <span style='color:#22b8cf'>━</span> SMA{sma} with its ±{band:.0%} band · dots: the monthly check "
                "(<span style='color:#19c37d'>buy</span>, <span style='color:#3987e5'>hold</span>, <span style='color:#c98500'>stay out</span>, <span style='color:#e66767'>sell</span>). "
                "Between dots the bot does nothing. Same decisions as the table below: the bot's own where its journal has them, otherwise the rule replayed on Yahoo closes.</div>", unsafe_allow_html=True)


VERDICT_TAG = {"BUY ZONE AT LAST PRICE": ("BUY", "#19c37d"), "WAIT FOR PULLBACK": ("WAIT", "#c98500"),
               "RANGE: BUY LOW END ONLY": ("RANGE", "#3987e5"), "AVOID FOR NOW": ("AVOID", "#e66767")}


def read_history(df: pd.DataFrame, market: str, capital: float = 1000.0, risk_pct: float = 1.0, n: int = 120) -> pd.DataFrame:
    """The Stock read verdict for each of the last n completed sessions, each computed from the candles up to and
    including that session only (the same function the tab uses, given a shortened history)."""
    import crt
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"]).dt.date
    d = d.sort_values("date").reset_index(drop=True)
    e21, e50 = crt.ema(d["close"], 21), crt.ema(d["close"], 50)
    rows = []
    for i in range(max(60, len(d) - n), len(d)):
        day = d["date"].iloc[i]
        sr = crt.stock_read(d.iloc[: i + 1], market, capital=capital, risk_pct=risk_pct, today=day + pd.Timedelta(days=1))
        if sr.get("verdict") in (None, "NOT ENOUGH DATA"):
            continue
        rows.append({"date": day, "open": float(d["open"].iloc[i]), "high": float(d["high"].iloc[i]), "low": float(d["low"].iloc[i]),
                     "close": float(d["close"].iloc[i]), "ema21": float(e21.iloc[i]), "ema50": float(e50.iloc[i]), "verdict": sr["verdict"],
                     "trend": sr.get("trend", ""), "rsi": float(sr.get("rsi", float("nan"))), "ret20": float(sr.get("ret20", float("nan")))})
    return pd.DataFrame(rows)


def read_replay_fig(name: str, h: pd.DataFrame, lines: int = 7) -> go.Figure | None:
    """Daily candles with EMA21 and EMA50, a verdict strip under the price, and a log of every change of verdict."""
    if h is None or len(h) < 20:
        return None
    h = h.reset_index(drop=True)
    n = len(h)
    x = [pd.Timestamp(d) for d in h["date"]]
    tag = h["verdict"].map(lambda v: VERDICT_TAG.get(v, (str(v)[:5], C.MUTED)))
    cols = [t[1] for t in tag]
    lo, hi = float(h["low"].min()), float(h["high"].max())
    pad = (hi - lo) * 0.08
    strip_y = lo - pad * 0.55
    changes = [i for i in range(n) if i == 0 or h["verdict"].iloc[i] != h["verdict"].iloc[i - 1]]

    def traces(i: int) -> list:
        s = slice(0, i + 1)
        return [
            go.Candlestick(x=x[s], open=h["open"].values[s], high=h["high"].values[s], low=h["low"].values[s], close=h["close"].values[s],
                           increasing_line_color=C.POS, decreasing_line_color=C.NEG, increasing_fillcolor=C.POS, decreasing_fillcolor=C.NEG, showlegend=False),
            go.Scatter(x=x[s], y=h["ema21"].values[s], mode="lines", line=dict(color="#22b8cf", width=1.5), hoverinfo="skip"),
            go.Scatter(x=x[s], y=h["ema50"].values[s], mode="lines", line=dict(color="#9085e9", width=1.5), hoverinfo="skip"),
            go.Scatter(x=x[s], y=[strip_y] * (i + 1), mode="markers", marker=dict(symbol="square", size=7, color=cols[: i + 1]),
                       text=list(h["verdict"].values[s]), hovertemplate="%{x|%d %b %Y}: %{text}<extra></extra>"),
        ]

    def notes(i: int) -> list:
        seen = [j for j in changes if j <= i][-lines:]
        log = "<br>".join(f"<span style='color:{tag.iloc[j][1]}'><b>{tag.iloc[j][0]:<5}</b></span> <span style='color:{C.MUTED}'>{x[j]:%d %b %y}</span>  "
                          f"{str(h['trend'].iloc[j]).split(' ')[0].lower()}, RSI {h['rsi'].iloc[j]:.0f}, 20d {h['ret20'].iloc[j]:+.1f}%" for j in reversed(seen))
        c = tag.iloc[: i + 1].map(lambda t: t[0]).value_counts()
        counter = f"{x[i]:%d %b %y}" + "".join(f" · <span style='color:{col}'>{t} {int(c.get(t, 0))}d</span>" for t, col in VERDICT_TAG.values() if c.get(t, 0))
        return [
            dict(xref="paper", yref="paper", x=0, y=0.30, xanchor="left", yanchor="top", align="left", showarrow=False, text=log, font=dict(family=MONO, size=11, color=C.TEXT)),
            dict(xref="paper", yref="paper", x=0, y=0.335, xanchor="left", yanchor="middle", showarrow=False, text=counter, font=dict(family=MONO, size=11, color=C.MUTED)),
            dict(xref="paper", yref="paper", x=0, y=0.37, xanchor="left", yanchor="middle", showarrow=False, text="CHANGES OF VERDICT · newest first", font=dict(family=MONO, size=10, color=C.MUTED)),
        ]

    fig = go.Figure(data=traces(n - 1))
    fig.frames = [go.Frame(name=str(i), data=traces(i), layout=dict(annotations=notes(i))) for i in range(5, n)]
    C.base_layout(fig, height=600, hovermode="x")
    fig.update_layout(
        annotations=notes(n - 1), margin=dict(l=8, r=8, t=50, b=8), showlegend=False,
        xaxis=dict(range=[x[0] - pd.Timedelta(days=1), x[-1] + pd.Timedelta(days=3)], rangeslider=dict(visible=False), domain=[0, 1], tickformat="%d %b"),
        yaxis=dict(range=[lo - pad, hi + pad], domain=[0.44, 1], side="right", tickformat=".4g"),
        updatemenus=[dict(type="buttons", direction="left", x=0, y=1.0, xanchor="left", yanchor="bottom", pad=dict(b=6, l=0), showactive=False,
                          bgcolor=C.PANEL, bordercolor=C.GRID, font=dict(color=C.TEXT, size=11),
                          buttons=[dict(label="▶ Replay", method="animate",
                                        args=[None, dict(frame=dict(duration=110, redraw=True), transition=dict(duration=0), fromcurrent=False, mode="immediate")]),
                                   dict(label="❚❚ Pause", method="animate", args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
    )
    return fig


def metal_history(df: pd.DataFrame) -> pd.DataFrame:
    """Weekly closes with the running high and the fall from it, for the long history replay."""
    c = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["date"])).sort_index()
    w = c.resample("W-FRI").last().dropna()
    out = pd.DataFrame({"close": w, "peak": w.cummax()})
    out["dd_pct"] = (out["close"] / out["peak"] - 1) * 100
    out["record"] = out["close"] >= out["peak"]
    return out


def metal_replay_fig(name: str, mh: pd.DataFrame, step: int = 4) -> go.Figure | None:
    """Price against its running record high; the red area is the fall from the high. Facts only, no signal."""
    if mh is None or len(mh) < 60:
        return None
    x = list(mh.index)
    n = len(mh)

    def traces(i: int) -> list:
        s = slice(0, i + 1)
        return [
            go.Scatter(x=x[s], y=mh["peak"].values[s], mode="lines", line=dict(color="rgba(230,103,103,0.55)", width=1, dash="dot", shape="hv"), hoverinfo="skip"),
            go.Scatter(x=x[s], y=mh["close"].values[s], mode="lines", line=dict(color="#ffd166", width=1.8), fill="tonexty", fillcolor="rgba(230,103,103,0.18)",
                       hovertemplate="%{x|%d %b %Y}: %{y:.3f}<extra></extra>"),
            go.Scatter(x=[x[i]], y=[float(mh["close"].iloc[i])], mode="markers", marker=dict(size=9, color="#ffd166", line=dict(color="#fff", width=1)), hoverinfo="skip"),
        ]

    def notes(i: int) -> list:
        part = mh.iloc[: i + 1]
        worst = part["dd_pct"].idxmin()
        now, dd = float(part["close"].iloc[-1]), float(part["dd_pct"].iloc[-1])
        t1 = f"{x[i]:%d %b %Y} · <span style='color:#ffd166'>{now:.3f}</span> · " + (f"<span style='color:{TAG_COLOR['ENTER']}'>record high</span>" if dd > -0.05 else f"<span style='color:{TAG_COLOR['EXIT']}'>{dd:+.1f}% from its high</span>")
        t2 = f"worst fall so far {float(part['dd_pct'].min()):.0f}% ({worst:%b %Y})"
        return [
            dict(xref="paper", yref="paper", x=0.01, y=0.98, xanchor="left", yanchor="top", align="left", showarrow=False, text=t1 + "<br>" + t2,
                 font=dict(family=MONO, size=11, color=C.MUTED), bgcolor="rgba(21,23,28,0.80)"),
        ]

    idx = list(range(26, n - 1, step)) + [n - 1]
    fig = go.Figure(data=traces(n - 1))
    fig.frames = [go.Frame(name=str(i), data=traces(i), layout=dict(annotations=notes(i))) for i in idx]
    hi = float(mh["peak"].max()); lo = float(mh["close"].min())
    C.base_layout(fig, height=420, hovermode="closest")
    fig.update_layout(
        annotations=notes(n - 1), margin=dict(l=8, r=8, t=50, b=8), showlegend=False,
        xaxis=dict(range=[x[0], x[-1] + pd.Timedelta(days=60)], tickformat="%Y"),
        yaxis=dict(range=[lo * 0.9, hi * 1.06], side="right"),
        updatemenus=[dict(type="buttons", direction="left", x=0, y=1.0, xanchor="left", yanchor="bottom", pad=dict(b=6, l=0), showactive=False,
                          bgcolor=C.PANEL, bordercolor=C.GRID, font=dict(color=C.TEXT, size=11),
                          buttons=[dict(label="▶ Replay", method="animate",
                                        args=[None, dict(frame=dict(duration=60, redraw=True), transition=dict(duration=0), fromcurrent=False, mode="immediate")]),
                                   dict(label="❚❚ Pause", method="animate", args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
    )
    return fig


_NO_CAP = "<style>div[class*='st-key-replay_'] .js-plotly-plot { max-height: none !important; }</style>"


def render_read(st, name: str, hist: pd.DataFrame):
    """Replay block under the Stock read: what the read said on each of the last sessions."""
    st.markdown(_NO_CAP, unsafe_allow_html=True)
    fig = read_replay_fig(name, hist)
    if fig is None:
        st.caption("Replay: not enough completed sessions yet.")
        return
    st.markdown("#### Replay of the read <span class='src'>what this check would have said at each of the last sessions, each from the candles up to that day only</span>", unsafe_allow_html=True)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "displayModeBar": False}, key=f"replay_read_{name}")
    st.markdown("<div class='src'><span style='color:#22b8cf'>━</span> EMA21 · <span style='color:#9085e9'>━</span> EMA50 · squares under the price: the verdict that day "
                "(<span style='color:#19c37d'>buy zone</span>, <span style='color:#c98500'>wait for pullback</span>, <span style='color:#3987e5'>range</span>, <span style='color:#e66767'>avoid</span>). "
                "This shows how the read changed, not whether following it made money: no trades and no outcomes are measured here. The signal log below is the track record.</div>", unsafe_allow_html=True)


def render_metal(st, name: str, df: pd.DataFrame):
    """Long history replay for gold or silver in KWD per gram."""
    st.markdown(_NO_CAP, unsafe_allow_html=True)
    fig = metal_replay_fig(name, metal_history(df))
    if fig is None:
        return
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "displayModeBar": False}, key=f"replay_metal_{name}")
    st.markdown(f"<div class='src'>{name} at weekly closes over the loaded history. Dotted line: the highest price reached so far. Red area: how far below that high the price sat. "
                "History only; it says nothing about what comes next.</div>", unsafe_allow_html=True)


def build(yahoo, pairs: dict[str, str], now: pd.Timestamp | None = None) -> dict:
    """Fetch through the panel's cached Yahoo reader and compute everything both figures need."""
    now = now or pd.Timestamp.now(tz="UTC")
    btc = yahoo("BTC-USD", "1y", "1d")
    if btc is None or len(btc) < 110:
        return {"ok": False, "note": "BTC daily data not available from Yahoo"}
    gate = gate_series(btc, now)
    dec = {}
    for name, sym in pairs.items():
        h = yahoo(sym, "60d", "1h")
        if h is None or len(h) < 240:
            continue
        w = to_4h(h, now)
        if len(w) >= 80:
            dec[name] = v4_decisions(w, gate)
    if not dec:
        return {"ok": False, "note": "pair data not available from Yahoo"}
    return {"ok": True, "dec": dec, "gate": gate}


def ridge_inputs(b: dict, n: int = 90) -> dict[str, pd.Series]:
    out = {name: d["dist_pct"].tail(n).reset_index(drop=True) for name, d in b["dec"].items()}
    first = next(iter(b["dec"].values()))
    out["BTC gate"] = first["gap_pct"].tail(n).reset_index(drop=True)      # daily gap, as each 4h candle saw it
    return out


def render(st, yahoo, pairs: dict[str, str]):
    st.markdown("<style>div[class*='st-key-replay_'] .js-plotly-plot, div.st-key-ridge .js-plotly-plot { max-height: none !important; }</style>", unsafe_allow_html=True)
    st.markdown("#### Replay <span class='src'>MemeSleeveV4's rules walking the last 15 days of 4h candles, one decision per candle with the missing piece. "
                "Fixed rules, no model: the same candles always give the same log.</span>", unsafe_allow_html=True)
    b = build(yahoo, pairs)
    if not b["ok"]:
        st.caption(f"Replay: {b['note']}.")
        return
    name = st.radio("Pair", list(b["dec"]), horizontal=True, label_visibility="collapsed", key="replay_pair")
    fig = replay_fig(name, b["dec"][name])
    if fig is None:
        st.caption("Replay: not enough completed candles yet.")
    else:
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "displayModeBar": False}, key=f"replay_{name}")
    st.markdown("<div class='src'><span style='color:#22b8cf'>━</span> EMA50 · <span style='color:#c98500'>┅</span> prior 20 bar high · "
                "<span style='color:#19c37d'>▲</span> enter · <span style='color:#e66767'>▼</span> exit or stop</div>", unsafe_allow_html=True)
    st.markdown("<div class='src'>Yahoo candles, so small differences from the bot's Binance candles are normal. Not replayed: the 10% trailing stop after +20% and the "
                "6 candle cooldown. The bot's real dry run trades are in the table below; this panel explains the rules, it is not a backtest.</div>", unsafe_allow_html=True)

    st.markdown("#### Distance to the entry trigger <span class='src'>one ridge per pair: each 4h close against the higher of its EMA50 and prior 20 bar high. "
                "The dotted line is the trigger; a ridge above it is a breakout. The front ridge is the BTC daily gate (gap to EMA100).</span>", unsafe_allow_html=True)
    rf = ridge_fig(ridge_inputs(b))
    if rf is not None:
        st.plotly_chart(rf, width="stretch", config={"displaylogo": False, "displayModeBar": False, "staticPlot": False}, key="ridge")
    st.markdown("<div class='src'>This shows where price is against a fixed rule. It is not a parameter search and it does not rank settings by past profit.</div>", unsafe_allow_html=True)
