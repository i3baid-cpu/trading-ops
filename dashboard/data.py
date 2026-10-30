"""
Data layer for the Trading Command Center dashboard.

Everything here is READ ONLY. It loads the files exported from the audit pack,
builds one unified trade table across the systems, and computes performance
metrics. No broker or exchange connection is opened, and nothing can place,
change or cancel an order.

Source files (all copied unchanged from the audit ZIP, see data/):
  robinhood_orders.csv     23 orders from the Robinhood API (Kuwait time)
  freqtrade_trades.csv     21 dry-run trades from the Freqtrade API (Kuwait time)
  freqtrade_stats.json     /api/v1/profit snapshot of Oct 30 2026 (UTC times)
  freqtrade_config.json    /api/v1/show_config snapshot
  alpaca_config.json       Lumibot runner config (paper)
  alpaca_backtest.json     headline backtest figures reported in HISTORY.md
  robinhood_snapshot.json  positions/cash from the Oct 27 dashboard source
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
KWT = ZoneInfo("Asia/Kuwait")
NYC = ZoneInfo("America/New_York")
UTC = timezone.utc
NA = "Not available"

# Strategy labels for Robinhood are INFERRED from the order pattern (the API
# returns no strategy or reason field). They are clearly marked as inferred in
# the UI.
MEME_COINS = {"DOGE", "PEPE", "SHIB", "FLOKI"}
CORE_CRYPTO = {"BTC", "ETH", "SOL"}

SYSTEMS = {
    "Robinhood": {"mode": "LIVE (real money)", "venue": "Robinhood US stocks + crypto", "short": "RH"},
    "Freqtrade": {"mode": "DRY-RUN (simulated)", "venue": "Binance spot, meme coins", "short": "FT"},
    "Alpaca": {"mode": "PAPER (no trades yet)", "venue": "Alpaca US stocks (Lumibot)", "short": "AL"},
    "CRT skill": {"mode": "ANALYSIS ONLY", "venue": "Boursa Kuwait (KWD)", "short": "CRT"},
}


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _read_json(name: str) -> dict:
    with open(os.path.join(DATA_DIR, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def _kwt(ts: str | pd.Timestamp) -> pd.Timestamp:
    """Parse a naive 'YYYY-MM-DD HH:MM' Kuwait-time string into a tz-aware stamp."""
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize(KWT)
    return t


def load_robinhood_orders() -> pd.DataFrame:
    df = pd.read_csv(os.path.join(DATA_DIR, "robinhood_orders.csv"))
    df["created"] = df["created_kwt"].map(_kwt)
    df["last_update"] = df["last_update_kwt"].map(_kwt)
    df["account"] = df["account_last4"].str.extract(r"(\d{4})")[0]
    df["crypto_account"] = df["account_last4"].str.contains("crypto")
    for c in ["qty_ordered", "qty_filled", "limit_price", "stop_price", "avg_fill_price", "total_usd_filled"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def load_freqtrade_trades() -> pd.DataFrame:
    df = pd.read_csv(os.path.join(DATA_DIR, "freqtrade_trades.csv"))
    df["open"] = df["open_kwt"].map(_kwt)
    df["close"] = df["close_kwt"].map(_kwt)
    return df


def load_freqtrade_stats() -> dict:
    return _read_json("freqtrade_stats.json")


def load_freqtrade_config() -> dict:
    return _read_json("freqtrade_config.json")


def load_alpaca_config() -> dict:
    return _read_json("alpaca_config.json")


def load_alpaca_backtest() -> dict:
    return _read_json("alpaca_backtest.json")


def load_robinhood_snapshot() -> dict:
    return _read_json("robinhood_snapshot.json")


def file_mtimes() -> dict[str, datetime]:
    out = {}
    for f in sorted(os.listdir(DATA_DIR)):
        p = os.path.join(DATA_DIR, f)
        if os.path.isfile(p):
            out[f] = datetime.fromtimestamp(os.path.getmtime(p), tz=UTC)
    return out


# --------------------------------------------------------------------------- #
# Robinhood: FIFO round trips from raw orders
# --------------------------------------------------------------------------- #
def _rh_strategy(asset: str, symbol: str) -> str:
    if asset == "stock":
        return "RH agent stock rebalance (inferred)"
    if symbol in MEME_COINS:
        return "RH meme sleeve, manual via agent (inferred)"
    return "RH crypto core (inferred)"


def _rh_exit_reason(order_type: str) -> str:
    if order_type == "stop_loss":
        return "Protective stop (GTC stop order) filled"
    if order_type == "limit":
        return "Limit sell filled (reason not returned by API)"
    return "Market sell (reason not returned by API)"


def build_robinhood_trades() -> pd.DataFrame:
    """
    Pair buys and sells per symbol with FIFO lots using ONLY the orders in the
    archive. Sells that exceed known lots (e.g. the NFLX sale on Aug 25, or ETH
    held before Aug 29) are kept as rows with pnl = NaN and a note, never
    estimated.
    """
    orders = load_robinhood_orders()
    filled = orders[(orders["state"] == "filled") & (orders["initiator"] != "user")].copy()
    filled = filled.sort_values("last_update")
    rows = []
    lots: dict[str, list[dict]] = {}
    for _, o in filled.iterrows():
        sym = o["symbol"]
        if o["side"] == "buy":
            lots.setdefault(sym, []).append({
                "qty": o["qty_filled"], "price": o["avg_fill_price"], "time": o["last_update"],
                "cost": o["total_usd_filled"], "order_type": o["order_type"], "limit": o["limit_price"],
            })
            continue
        # sell: consume FIFO
        remaining = o["qty_filled"]
        proceeds_total = o["total_usd_filled"]
        sell_px = o["avg_fill_price"]
        while remaining > 1e-12:
            if not lots.get(sym):
                rows.append({
                    "system": "Robinhood", "strategy": _rh_strategy(o["asset"], sym), "asset_class": o["asset"],
                    "symbol": sym, "entry_time": pd.NaT, "exit_time": o["last_update"],
                    "entry_price": np.nan, "exit_price": sell_px, "qty": remaining,
                    "stake_usd": np.nan, "proceeds_usd": remaining * sell_px, "pnl_usd": np.nan, "pnl_pct": np.nan,
                    "fees_usd": np.nan, "entry_reason": "Lot predates archived orders",
                    "exit_reason": _rh_exit_reason(o["order_type"]), "status": "closed (basis unknown)",
                    "stop_price": o["stop_price"], "note": "Cost basis not in orders_full.csv; P&L not estimated.",
                })
                remaining = 0
                break
            lot = lots[sym][0]
            take = min(remaining, lot["qty"])
            cost = lot["cost"] * (take / lot["qty"]) if lot["qty"] else np.nan
            proceeds = proceeds_total * (take / o["qty_filled"])
            pnl = proceeds - cost
            rows.append({
                "system": "Robinhood", "strategy": _rh_strategy(o["asset"], sym), "asset_class": o["asset"],
                "symbol": sym, "entry_time": lot["time"], "exit_time": o["last_update"],
                "entry_price": lot["price"], "exit_price": sell_px, "qty": take,
                "stake_usd": cost, "proceeds_usd": proceeds, "pnl_usd": pnl,
                "pnl_pct": (pnl / cost * 100.0) if cost else np.nan,
                "fees_usd": np.nan, "entry_reason": f"{lot['order_type']} buy (reason not returned by API)",
                "exit_reason": _rh_exit_reason(o["order_type"]), "status": "closed",
                "stop_price": o["stop_price"],
                "note": "Partial lot" if take < lot["qty"] - 1e-12 else "",
            })
            lot["qty"] -= take
            lot["cost"] -= cost
            remaining -= take
            if lot["qty"] <= 1e-12:
                lots[sym].pop(0)
    # open lots
    for sym, ls in lots.items():
        for lot in ls:
            if lot["qty"] > 1e-12:
                rows.append({
                    "system": "Robinhood", "strategy": _rh_strategy("crypto" if sym in MEME_COINS | CORE_CRYPTO else "stock", sym),
                    "asset_class": "crypto" if sym in MEME_COINS | CORE_CRYPTO else "stock",
                    "symbol": sym, "entry_time": lot["time"], "exit_time": pd.NaT,
                    "entry_price": lot["price"], "exit_price": np.nan, "qty": lot["qty"],
                    "stake_usd": lot["cost"], "proceeds_usd": np.nan, "pnl_usd": np.nan, "pnl_pct": np.nan,
                    "fees_usd": np.nan, "entry_reason": f"{lot['order_type']} buy (reason not returned by API)",
                    "exit_reason": "", "status": "open", "stop_price": np.nan, "note": "Still held",
                })
    df = pd.DataFrame(rows)
    df["duration"] = df["exit_time"] - df["entry_time"]
    df["trade_id"] = ["RH-%02d" % (i + 1) for i in range(len(df))]
    df["source_label"] = "LIVE (real money)"
    return df


# --------------------------------------------------------------------------- #
# Freqtrade: unify
# --------------------------------------------------------------------------- #
def _roi_tier(minutes: float, roi: dict) -> str:
    tiers = sorted(((int(k), v) for k, v in roi.items()), key=lambda kv: kv[0])
    active = tiers[0]
    for k, v in tiers:
        if minutes >= k:
            active = (k, v)
    return f"ROI tier reached: >= {active[0]} min -> target {active[1] * 100:.0f}%"


def build_freqtrade_trades() -> pd.DataFrame:
    ft = load_freqtrade_trades()
    cfg = load_freqtrade_config()
    roi = cfg["minimal_roi"]
    df = pd.DataFrame({
        "trade_id": ["FT-%d" % i for i in ft["trade_id"]],
        "system": "Freqtrade",
        "strategy": "MemeSleeveV1 (5m, dry-run)",
        "asset_class": "crypto",
        "symbol": ft["pair"].str.replace("/USDT", "", regex=False),
        "entry_time": ft["open"], "exit_time": ft["close"],
        "entry_price": ft["open_rate"], "exit_price": ft["close_rate"],
        "qty": ft["amount"], "stake_usd": ft["stake_usdt"],
        "proceeds_usd": ft["stake_usdt"] + ft["profit_abs_usdt"],
        "pnl_usd": ft["profit_abs_usdt"], "pnl_pct": ft["profit_pct"], "fees_usd": ft["fees_usdt"],
        "entry_reason": "MemeSleeveV1 entry signal (EMA9 > EMA21, RSI 45-75, volume > 0.8x 20-bar mean, close > EMA9)",
        "status": np.where(ft["is_open"], "open", "closed"),
        "stop_price": ft["open_rate"] * (1 + cfg["stoploss"]),
        "note": "",
        "source_label": "DRY-RUN (simulated fills)",
    })
    dur_min = (df["exit_time"] - df["entry_time"]).dt.total_seconds() / 60
    df["exit_reason"] = [
        _roi_tier(m, roi) if r == "roi" else "Exit signal: EMA9 crossed below EMA21 or RSI > 80"
        for r, m in zip(ft["exit_reason"], dur_min)
    ]
    df["exit_reason_code"] = ft["exit_reason"].values
    df["duration"] = df["exit_time"] - df["entry_time"]
    return df


def build_all_trades() -> pd.DataFrame:
    rh = build_robinhood_trades()
    ft = build_freqtrade_trades()
    cols = ["trade_id", "system", "strategy", "asset_class", "symbol", "entry_time", "exit_time", "entry_price",
            "exit_price", "qty", "stake_usd", "proceeds_usd", "pnl_usd", "pnl_pct", "fees_usd", "entry_reason",
            "exit_reason", "status", "stop_price", "duration", "note", "source_label"]
    rh["exit_reason_code"] = np.where(rh["exit_reason"].str.startswith("Protective"), "stop_loss",
                                      np.where(rh["status"] == "open", "", "manual_exit"))
    cols.append("exit_reason_code")
    allt = pd.concat([rh[cols], ft[cols]], ignore_index=True)
    allt["entry_time"] = pd.to_datetime(allt["entry_time"], utc=True).dt.tz_convert(KWT)
    allt["exit_time"] = pd.to_datetime(allt["exit_time"], utc=True).dt.tz_convert(KWT)
    return allt


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
@dataclass
class Metrics:
    trades: int
    closed: int
    net_pnl: float | None
    gross_profit: float
    gross_loss: float
    win_rate: float | None
    profit_factor: float | None
    expectancy: float | None
    max_drawdown: float | None
    max_consec_losses: int
    avg_duration: timedelta | None
    avg_win: float | None
    avg_loss: float | None
    best: float | None
    worst: float | None
    total_stake: float | None
    return_on_stake: float | None
    sharpe_per_trade: float | None
    sortino_per_trade: float | None
    fees: float | None
    unknown_basis: int


def _consec_losses(pnl: pd.Series) -> int:
    best = cur = 0
    for v in pnl:
        if v < 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def equity_curve(trades: pd.DataFrame) -> pd.DataFrame:
    """Cumulative realised P&L ordered by exit time (closed trades with known P&L)."""
    c = trades[(trades["status"].str.startswith("closed")) & trades["pnl_usd"].notna()].sort_values("exit_time")
    if c.empty:
        return pd.DataFrame(columns=["time", "cum_pnl", "drawdown", "pnl"])
    cum = c["pnl_usd"].cumsum()
    peak = cum.cummax().clip(lower=0)
    dd = cum - peak
    return pd.DataFrame({"time": c["exit_time"].values, "pnl": c["pnl_usd"].values,
                         "cum_pnl": cum.values, "drawdown": dd.values, "symbol": c["symbol"].values,
                         "trade_id": c["trade_id"].values})


def compute_metrics(trades: pd.DataFrame) -> Metrics:
    closed = trades[trades["status"].str.startswith("closed")]
    known = closed[closed["pnl_usd"].notna()]
    pnl = known["pnl_usd"]
    n = len(known)
    if n == 0:
        return Metrics(len(trades), len(closed), None, 0.0, 0.0, None, None, None, None, 0, None, None, None,
                       None, None, None, None, None, None, None, int(closed["pnl_usd"].isna().sum()))
    wins, losses = pnl[pnl > 0], pnl[pnl < 0]
    gp, gl = float(wins.sum()), float(-losses.sum())
    ec = equity_curve(known)
    mdd = float(-ec["drawdown"].min()) if not ec.empty else None
    stake = float(known["stake_usd"].sum()) if known["stake_usd"].notna().any() else None
    pct = known["pnl_pct"].dropna()
    sharpe = sortino = None
    if len(pct) >= 2 and pct.std(ddof=1) > 0:
        sharpe = float(pct.mean() / pct.std(ddof=1))
        downside = pct[pct < 0]
        if len(downside) >= 1 and downside.std(ddof=0) > 0:
            sortino = float(pct.mean() / math.sqrt((downside ** 2).mean()))
    dur = known["duration"].dropna()
    fees = float(known["fees_usd"].sum()) if known["fees_usd"].notna().any() else None
    return Metrics(
        trades=len(trades), closed=len(closed), net_pnl=float(pnl.sum()), gross_profit=gp, gross_loss=gl,
        win_rate=len(wins) / n * 100.0, profit_factor=(gp / gl) if gl > 0 else (math.inf if gp > 0 else None),
        expectancy=float(pnl.mean()), max_drawdown=mdd, max_consec_losses=_consec_losses(pnl),
        avg_duration=(dur.mean() if len(dur) else None),
        avg_win=(float(wins.mean()) if len(wins) else None), avg_loss=(float(losses.mean()) if len(losses) else None),
        best=float(pnl.max()), worst=float(pnl.min()), total_stake=stake,
        return_on_stake=(float(pnl.sum()) / stake * 100.0) if stake else None,
        sharpe_per_trade=sharpe, sortino_per_trade=sortino, fees=fees,
        unknown_basis=int(closed["pnl_usd"].isna().sum()),
    )


def by_symbol(trades: pd.DataFrame) -> pd.DataFrame:
    closed = trades[trades["status"].str.startswith("closed") & trades["pnl_usd"].notna()]
    if closed.empty:
        return pd.DataFrame(columns=["symbol", "trades", "net_pnl", "win_rate", "avg_pnl"])
    g = closed.groupby("symbol")["pnl_usd"]
    out = pd.DataFrame({
        "trades": g.size(), "net_pnl": g.sum(), "win_rate": g.apply(lambda s: (s > 0).mean() * 100.0),
        "avg_pnl": g.mean(),
    }).reset_index().sort_values("net_pnl", ascending=False)
    return out


def daily_pnl(trades: pd.DataFrame, tz=KWT) -> pd.DataFrame:
    closed = trades[trades["status"].str.startswith("closed") & trades["pnl_usd"].notna()].copy()
    if closed.empty:
        return pd.DataFrame(columns=["day", "pnl", "trades"])
    closed["day"] = closed["exit_time"].dt.tz_convert(tz).dt.date
    g = closed.groupby("day")["pnl_usd"]
    return pd.DataFrame({"pnl": g.sum(), "trades": g.size()}).reset_index()


def strategy_table(trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (system, strat), grp in trades.groupby(["system", "strategy"], sort=False):
        m = compute_metrics(grp)
        rows.append({
            "System": system, "Strategy": strat, "Status": grp["source_label"].iloc[0],
            "Trades": m.trades, "Closed": m.closed, "Net P&L ($)": m.net_pnl,
            "Return on stake (%)": m.return_on_stake, "Win rate (%)": m.win_rate,
            "Profit factor": m.profit_factor, "Expectancy ($/trade)": m.expectancy,
            "Max DD ($)": m.max_drawdown, "Avg hold": m.avg_duration, "Max consec. losses": m.max_consec_losses,
            "Fees ($)": m.fees, "Unknown-basis exits": m.unknown_basis,
        })
    bt = load_alpaca_backtest()
    rows.append({
        "System": "Alpaca", "Strategy": bt["strategy"], "Status": "BACKTEST ONLY (reported) / paper: 0 trades",
        "Trades": bt["trade_count"], "Closed": None, "Net P&L ($)": None,  # $10k backtest budget, not comparable to live dollars
        "Return on stake (%)": bt["strategy_total_return_pct"], "Win rate (%)": None, "Profit factor": None,
        "Expectancy ($/trade)": None, "Max DD ($)": None,
        "Avg hold": None, "Max consec. losses": None, "Fees ($)": None, "Unknown-basis exits": None,
    })
    rows.append({
        "System": "CRT skill", "Strategy": "crt-ict-trading-analyzer", "Status": "ANALYSIS ONLY, no trades",
        "Trades": 0, "Closed": 0, "Net P&L ($)": None, "Return on stake (%)": None, "Win rate (%)": None,
        "Profit factor": None, "Expectancy ($/trade)": None, "Max DD ($)": None, "Avg hold": None,
        "Max consec. losses": None, "Fees ($)": None, "Unknown-basis exits": None,
    })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Positions and risk (Robinhood snapshot)
# --------------------------------------------------------------------------- #
def positions_table() -> tuple[pd.DataFrame, dict]:
    snap = load_robinhood_snapshot()
    pos = pd.DataFrame(snap["positions"])
    pos["market_value"] = pos["qty"] * pos["price"]
    pos["known_cost_value"] = pos["basis_qty"] * pos["price"]
    pos["unrealized_known_basis"] = pos["known_cost_value"] - pos["basis_usd"]
    pos["unrealized_known_basis_pct"] = pos["unrealized_known_basis"] / pos["basis_usd"] * 100
    pos["day_change"] = np.where(pos["prev_close"].notna(), pos["qty"] * (pos["price"] - pos["prev_close"].fillna(0)), np.nan)
    total = pos["market_value"].sum() + snap["cash_usd"]
    pos["weight"] = pos["market_value"] / total
    pos["breach"] = pos["weight"] > snap["concentration_limit"]
    pos["basis_coverage"] = pos["basis_qty"] / pos["qty"]
    return pos, {"total": total, "cash": snap["cash_usd"], "invested": pos["market_value"].sum(), "snapshot": snap}


# --------------------------------------------------------------------------- #
# Reconciliation checks (real cross-checks between files in the archive)
# --------------------------------------------------------------------------- #
def reconciliation() -> pd.DataFrame:
    checks = []
    ft = load_freqtrade_trades()
    st = load_freqtrade_stats()["profit"]
    perf = {p["pair"]: p for p in load_freqtrade_stats()["performance"]}

    def add(system, check, expected, actual, tol=0.0):
        try:
            ok = abs(float(expected) - float(actual)) <= tol
        except (TypeError, ValueError):
            ok = str(expected) == str(actual)
        checks.append({"System": system, "Check": check, "Expected": expected, "Actual": actual,
                       "Result": "PASS" if ok else "FAIL"})

    add("Freqtrade", "Closed trade count: trades_full.csv vs API profit snapshot", st["closed_trade_count"], len(ft))
    add("Freqtrade", "Net profit USDT: sum of trades vs API profit_closed_coin", round(st["profit_closed_coin"], 4),
        round(ft["profit_abs_usdt"].sum(), 4), tol=0.001)
    add("Freqtrade", "Winning trades: trades vs API", st["winning_trades"], int((ft["profit_abs_usdt"] > 0).sum()))
    add("Freqtrade", "Losing trades: trades vs API", st["losing_trades"], int((ft["profit_abs_usdt"] < 0).sum()))
    gp = ft.loc[ft["profit_abs_usdt"] > 0, "profit_abs_usdt"].sum()
    gl = -ft.loc[ft["profit_abs_usdt"] < 0, "profit_abs_usdt"].sum()
    add("Freqtrade", "Profit factor: recomputed vs API", round(st["profit_factor"], 3), round(gp / gl, 3), tol=0.005)
    for pair, p in perf.items():
        add("Freqtrade", f"Per-pair profit {pair}: trades vs API performance", round(p["profit_abs"], 4),
            round(ft.loc[ft["pair"] == pair, "profit_abs_usdt"].sum(), 4), tol=0.001)
    ec = equity_curve(build_freqtrade_trades())
    add("Freqtrade", "Max drawdown USDT: recomputed from trade sequence vs API", round(st["max_drawdown_abs"], 3),
        round(-ec["drawdown"].min(), 3), tol=0.01)
    add("Freqtrade", "Trade IDs missing from sequence (6, 9 lost or never opened)", "ids 1-23 minus 6, 9",
        "ids 1-23 minus " + ", ".join(str(i) for i in sorted(set(range(1, 24)) - set(ft["trade_id"]))))

    rh = load_robinhood_orders()
    add("Robinhood", "Total orders in file vs README (23)", 23, len(rh))
    add("Robinhood", "Filled crypto orders vs README (16)", 16, int(((rh["asset"] == "crypto") & (rh["state"] == "filled")).sum()))
    add("Robinhood", "Canceled crypto orders vs README (2)", 2, int(((rh["asset"] == "crypto") & (rh["state"] == "canceled")).sum()))
    rht = build_robinhood_trades()
    reported = {"SHIB": -2.22, "FLOKI": -2.22, "PEPE": -2.21, "SOL": 1.18, "DOGE": 3.79}  # dashboard_page_source.tsx REALIZED
    for sym, val in reported.items():
        sub = rht[(rht["symbol"] == sym) & (rht["status"] == "closed")].sort_values("exit_time")
        actual = round(float(sub["pnl_usd"].iloc[0]), 2) if len(sub) else None
        add("Robinhood", f"Realized {sym} (first round trip): FIFO from orders vs Oct 27 dashboard", val, actual, tol=0.011)
    pre = rht[(rht["asset_class"] == "crypto") & (rht["status"] == "closed") & (rht["exit_time"] <= _kwt("2026-10-27 12:44"))]
    add("Robinhood", "Crypto realized to Oct 27 excluding ETH: FIFO vs dashboard -1.68",
        -1.68, round(float(pre[pre["symbol"] != "ETH"]["pnl_usd"].sum()), 2), tol=0.011)
    add("Robinhood", "ETH Sep 18 partial sale: dashboard shows 'Not available'; FIFO against the Aug 29 lot gives",
        "Not available (dashboard)", f"+{float(pre[pre['symbol'] == 'ETH']['pnl_usd'].sum()):.2f} (FIFO, Aug 29 lot only)")
    checks[-1]["Result"] = "INFO"
    return pd.DataFrame(checks)


# --------------------------------------------------------------------------- #
# Candles (optional, only if the user fetched them locally)
# --------------------------------------------------------------------------- #
def load_candles(symbol: str) -> pd.DataFrame | None:
    p = os.path.join(DATA_DIR, "candles", f"{symbol}USDT_5m.csv")
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p)
    df["time"] = pd.to_datetime(df["open_time"], utc=True).dt.tz_convert(KWT)
    return df


def fmt_td(td) -> str:
    if td is None or (isinstance(td, float) and math.isnan(td)) or pd.isna(td):
        return NA
    s = int(pd.Timedelta(td).total_seconds())
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"
