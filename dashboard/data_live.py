"""
Live loaders for the Trading Command Center (DASH_MODE=live, see docs/LIVE_LOADER_SPEC.md).

READ ONLY. The Freqtrade sqlite is opened with ?mode=ro, the JSON files are only
read, and the optional Freqtrade API call is a GET on /api/v1/profit. No broker
SDK is imported and nothing here can place, change or cancel an order.

Sources (paths from the environment, mounted read only by deploy/docker-compose.dashboard.yml):
  FT_DB           Freqtrade 2026.9 sqlite (WAL mode, so its directory is mounted, not the file)
  FT_CONFIG       secrets-free Freqtrade config (backtest_config.json)
  LUMIBOT_STATE   sleeve ledger written by trend_filter.py: {"realized": float, "pos": {sym: {"qty", "cost"}}}
  LUMIBOT_CONFIG  Lumibot runner config (capital_usd, symbols, params)
  FT_API_URL, FT_API_USERNAME, FT_API_PASSWORD   optional, only for the /profit reconciliation check

trades schema used (PRAGMA table_info(trades), Freqtrade 2026.9): id, pair, is_open, open_date, close_date
(naive UTC), open_rate, close_rate, amount, stake_amount, close_profit (ratio), close_profit_abs,
fee_open_cost, fee_close_cost (stake currency), initial_stop_loss, exit_reason, strategy, enter_tag,
timeframe (minutes, integer).
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import urllib.request
from contextlib import closing

import numpy as np
import pandas as pd

import data as D

FT_DB = os.environ.get("FT_DB", "/live/freqtrade/user_data/tradesv3.dryrun.sqlite")
FT_CONFIG = os.environ.get("FT_CONFIG", "/live/freqtrade/user_data/backtest_config.json")
LUMIBOT_STATE = os.environ.get("LUMIBOT_STATE", "/live/lumibot/strategies/trend_filter_state.json")
LUMIBOT_CONFIG = os.environ.get("LUMIBOT_CONFIG", "/live/lumibot/config.json")

# MemeSleeveV3 replaced V1 on the bot at this time. Trades are labelled by the strategy recorded at entry,
# so V1 trades opened before the switch stay V1 even when V3 closed them (ids 24 and 25, exit trend_lost_4h).
V3_START = pd.Timestamp("2026-10-30 21:26", tz="UTC")
V3_NOTE = "forward test; backtest positive but not statistically significant (PF 1.34 in sample, 26 trades held out)"
# MemeSleeveV4 (V3's rules, SOL added, 3 open trades) replaced V3 at this time; V3 made no trades.
V4_START = pd.Timestamp("2026-11-03 12:06", tz="UTC")
V4_NOTE = "forward test of study variant 5; profitable on unseen 2020-23 data (PF 1.64) and on 2023-26 (PF 1.38)"
ALPACA_STRATEGY = "TrendFilter (daily, paper)"
NO_PAPER_TRADES = "no paper trades yet"

V1_ENTRY = "MemeSleeveV1 entry signal (EMA9 > EMA21, RSI 45-75, volume > 0.8x 20-bar mean, close > EMA9)"
V1_EXIT_SIGNAL = "Exit signal: EMA9 crossed below EMA21 or RSI > 80"
EXIT_TEXT = {
    "stop_loss": "Stoploss hit (market order)",
    "trailing_stop_loss": "Trailing stoploss hit",
    "force_exit": "Forced exit from the bot UI or API",
    "emergency_exit": "Emergency exit",
    "liquidation": "Liquidation",
}

try:
    import streamlit as st
    _cache = st.cache_data(ttl=60, show_spinner=False)
except ImportError:  # pragma: no cover - streamlit is always installed in the container
    def _cache(fn):
        return fn


def _mtime(path: str) -> pd.Timestamp | None:
    try:
        return pd.Timestamp(os.path.getmtime(path), unit="s", tz="UTC")
    except OSError:
        return None


def _read_json_file(path: str) -> dict | None:
    """Parsed JSON, or None when the file is missing, empty or not valid JSON."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _tf_label(minutes) -> str:
    if minutes is None or pd.isna(minutes):
        return "?"
    m = int(minutes)
    if m % 1440 == 0:
        return f"{m // 1440}d"
    if m % 60 == 0:
        return f"{m // 60}h"
    return f"{m}m"


# --------------------------------------------------------------------------- #
# Freqtrade sqlite
# --------------------------------------------------------------------------- #
def _connect_ro() -> sqlite3.Connection:
    try:
        con = sqlite3.connect(f"file:{FT_DB}?mode=ro", uri=True)
        con.execute("SELECT 1 FROM trades LIMIT 1")
        return con
    except sqlite3.OperationalError:
        # A read-only mount cannot create the -shm file. Without a -wal file (bot stopped cleanly) the main
        # file is complete, so it can be opened as immutable; with one, re-raise rather than hide WAL data.
        if os.path.exists(FT_DB + "-wal"):
            raise
        return sqlite3.connect(f"file:{FT_DB}?mode=ro&immutable=1", uri=True)


@_cache
def read_ft_trades() -> pd.DataFrame:
    with closing(_connect_ro()) as con:
        df = pd.read_sql_query(
            "SELECT id, pair, stake_currency, is_open, open_rate, close_rate, amount, stake_amount, close_profit, "
            "close_profit_abs, fee_open_cost, fee_close_cost, open_date, close_date, initial_stop_loss, exit_reason, "
            "strategy, enter_tag, timeframe FROM trades ORDER BY id", con)
    df["is_open"] = df["is_open"].astype(bool)
    df["open_date"] = pd.to_datetime(df["open_date"], utc=True, format="ISO8601")
    df["close_date"] = pd.to_datetime(df["close_date"], utc=True, format="ISO8601")
    return df


def _exit_text(code: str, strategy: str, minutes: float, roi: dict) -> str:
    if strategy == "MemeSleeveV1" and code == "roi":
        return D._roi_tier(minutes, roi)
    if strategy == "MemeSleeveV1" and code == "exit_signal":
        return V1_EXIT_SIGNAL
    if code == "roi":
        return "ROI target reached"
    return EXIT_TEXT.get(code, f"Exit signal: {code}")


def build_freqtrade_trades() -> pd.DataFrame:
    t = read_ft_trades()
    roi = D._read_json("freqtrade_config.json")["minimal_roi"]  # V1's ROI table; not in FT_CONFIG
    is_open = t["is_open"].to_numpy()
    pnl = t["close_profit_abs"].where(~t["is_open"])
    df = pd.DataFrame({
        "trade_id": ["FT-%d" % i for i in t["id"]],
        "system": "Freqtrade",
        "strategy": [f"{s} ({_tf_label(tf)}, dry-run)" for s, tf in zip(t["strategy"], t["timeframe"])],
        "asset_class": "crypto",
        "symbol": t["pair"].str.split("/").str[0],
        "entry_time": t["open_date"].dt.tz_convert(D.KWT),
        "exit_time": t["close_date"].where(~t["is_open"]).dt.tz_convert(D.KWT),
        "entry_price": t["open_rate"],
        "exit_price": t["close_rate"].where(~t["is_open"]),
        "qty": t["amount"], "stake_usd": t["stake_amount"],
        "proceeds_usd": t["stake_amount"] + pnl,
        "pnl_usd": pnl, "pnl_pct": t["close_profit"].where(~t["is_open"]) * 100.0,
        "fees_usd": t["fee_open_cost"].fillna(0.0) + t["fee_close_cost"].fillna(0.0),
        "entry_reason": [V1_ENTRY if s == "MemeSleeveV1" else f"{s} entry signal" + (f" (tag {tag})" if tag else "")
                         for s, tag in zip(t["strategy"], t["enter_tag"].fillna(""))],
        "status": np.where(is_open, "open", "closed"),
        "stop_price": t["initial_stop_loss"],
        "note": [{"MemeSleeveV3": f"MemeSleeveV3 {V3_NOTE}", "MemeSleeveV4": f"MemeSleeveV4 {V4_NOTE}"}.get(s, "") for s in t["strategy"]],
        "source_label": "DRY-RUN (simulated fills)",
    })
    df["duration"] = df["exit_time"] - df["entry_time"]
    dur_min = df["duration"].dt.total_seconds() / 60
    codes = t["exit_reason"].fillna("").where(~t["is_open"], "")
    df["exit_reason"] = ["" if not c else _exit_text(c, s, m, roi) for c, s, m in zip(codes, t["strategy"], dur_min)]
    df["exit_reason_code"] = codes.values
    return df


def _drawdown_abs(closed: pd.DataFrame) -> float:
    cum = closed.sort_values("close_date")["close_profit_abs"].cumsum()
    return float(-(cum - cum.cummax().clip(lower=0)).min()) if len(cum) else 0.0


def load_freqtrade_stats() -> dict:
    """The /profit snapshot shape, with every field derivable from the sqlite replaced by live values."""
    snap = D._read_json("freqtrade_stats.json")
    t = read_ft_trades()
    closed = t[~t["is_open"]]
    pnl = closed["close_profit_abs"]
    gp, gl = float(pnl[pnl > 0].sum()), float(-pnl[pnl < 0].sum())
    first, last = t["open_date"].min(), t["open_date"].max()
    perf = []
    for pair, g in closed.groupby("pair"):
        perf.append({"pair": pair, "profit_abs": float(g["close_profit_abs"].sum()), "count": len(g),
                     "profit_ratio": float(g["close_profit_abs"].sum() / g["stake_amount"].sum())})
    perf.sort(key=lambda p: p["profit_abs"], reverse=True)
    derived = {
        "trade_count": len(t), "closed_trade_count": len(closed),
        "profit_closed_coin": float(pnl.sum()),
        "winning_trades": int((pnl > 0).sum()), "losing_trades": int((pnl < 0).sum()),
        "profit_factor": (gp / gl) if gl > 0 else None,
        "winrate": float((pnl > 0).mean()) if len(pnl) else None,
        "expectancy": float(pnl.mean()) if len(pnl) else None,
        "max_drawdown_abs": _drawdown_abs(closed),
        "first_trade_date": first.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(first) else None,
        "latest_trade_date": last.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(last) else None,
        "best_pair": perf[0]["pair"] if perf else None,
        "best_pair_profit_abs": perf[0]["profit_abs"] if perf else None,
    }
    profit = dict(snap["profit"], **derived)
    cfg = _read_json_file(FT_CONFIG) or {}
    count = dict(snap["count"], current=int(t["is_open"].sum()),
                 total_stake=float(t.loc[t["is_open"], "stake_amount"].sum()))
    if "max_open_trades" in cfg:
        count["max"] = int(cfg["max_open_trades"])
    return {"profit": profit, "performance": perf, "count": count,
            "_snapshot_keys": sorted(set(snap["profit"]) - set(derived))}


def load_freqtrade_config() -> dict:
    """show_config snapshot, overridden by FT_CONFIG where the file has the field."""
    snap = D._read_json("freqtrade_config.json")
    cfg = _read_json_file(FT_CONFIG) or {}
    live = {k: cfg[k] for k in ("strategy", "timeframe", "dry_run", "stake_currency", "stake_amount", "max_open_trades", "trading_mode",
                                "margin_mode", "unfilledtimeout", "entry_pricing", "exit_pricing", "bot_name") if k in cfg}
    if isinstance(cfg.get("exchange"), dict) and cfg["exchange"].get("name"):
        live["exchange"] = cfg["exchange"]["name"]
    out = dict(snap, **live)
    out["_snapshot_keys"] = sorted(set(snap) - set(live))
    return out


# --------------------------------------------------------------------------- #
# Alpaca / Lumibot sleeve ledger
# --------------------------------------------------------------------------- #
@_cache
def read_lumibot_state() -> dict | None:
    return _read_json_file(LUMIBOT_STATE)


def load_lumibot_config() -> dict | None:
    return _read_json_file(LUMIBOT_CONFIG)


def _held(state: dict | None) -> dict:
    if not state:
        return {}
    return {s: p for s, p in (state.get("pos") or {}).items() if float(p.get("qty") or 0) > 1e-9}


def build_alpaca_trades() -> pd.DataFrame:
    """Open sleeve positions as trade rows. The ledger keeps no fill times, so entry_time is unknown."""
    rows = []
    for sym, p in _held(read_lumibot_state()).items():
        qty, cost = float(p["qty"]), float(p["cost"])
        rows.append({
            "trade_id": f"AL-{sym}", "system": "Alpaca", "strategy": ALPACA_STRATEGY, "asset_class": "stock",
            "symbol": sym, "entry_time": pd.NaT, "exit_time": pd.NaT, "entry_price": cost / qty, "exit_price": np.nan,
            "qty": qty, "stake_usd": cost, "proceeds_usd": np.nan, "pnl_usd": np.nan, "pnl_pct": np.nan,
            "fees_usd": np.nan, "entry_reason": "TrendFilter: last completed daily close above its 200-day SMA",
            "exit_reason": "", "exit_reason_code": "", "status": "open", "stop_price": np.nan,
            "note": "From the sleeve ledger: average cost of the paper fills; fill times are not stored",
            "source_label": "PAPER (simulated fills)",
        })
    df = pd.DataFrame(rows, columns=["trade_id", "system", "strategy", "asset_class", "symbol", "entry_time", "exit_time",
                                     "entry_price", "exit_price", "qty", "stake_usd", "proceeds_usd", "pnl_usd", "pnl_pct",
                                     "fees_usd", "entry_reason", "exit_reason", "exit_reason_code", "status", "stop_price",
                                     "duration", "note", "source_label"])
    for c in ("entry_time", "exit_time"):
        df[c] = pd.to_datetime(df[c], utc=True).dt.tz_convert(D.KWT)
    df["duration"] = pd.Series(pd.NaT, index=df.index, dtype="timedelta64[ns]")  # no fill times, so no holding time
    return df


def alpaca_sleeve() -> tuple[pd.DataFrame | None, dict]:
    """Positions table and summary for the $1,000 paper sleeve. Market prices are not read (no broker access)."""
    state, cfg = read_lumibot_state(), load_lumibot_config() or {}
    capital = float(cfg.get("capital_usd", 1000))
    summary = {"capital": capital, "symbols": cfg.get("symbols", []), "params": cfg.get("params", {}),
               "paper": cfg.get("paper"), "state_mtime": _mtime(LUMIBOT_STATE)}
    held = _held(state)
    if not state or (not held and not float(state.get("realized") or 0)):
        return None, dict(summary, status=NO_PAPER_TRADES, realized=None, invested=0.0, cash=capital)
    pos = pd.DataFrame([{"symbol": s, "qty": float(p["qty"]), "cost_usd": float(p["cost"]),
                         "avg_cost": float(p["cost"]) / float(p["qty"])} for s, p in held.items()],
                       columns=["symbol", "qty", "cost_usd", "avg_cost"])
    realized = float(state.get("realized") or 0.0)
    invested = float(pos["cost_usd"].sum())
    pos["weight_at_cost"] = pos["cost_usd"] / (capital + realized)
    return pos, dict(summary, status=f"{len(pos)} open position(s)", realized=realized, invested=invested,
                     cash=capital + realized - invested)


# --------------------------------------------------------------------------- #
# Freshness and reconciliation
# --------------------------------------------------------------------------- #
def freshness() -> list[tuple[str, pd.Timestamp | None]]:
    """(label, UTC time) rows for System Health. Writes land in the -wal file first, so it counts as the sqlite mtime."""
    db = [m for m in (_mtime(FT_DB), _mtime(FT_DB + "-wal")) if m is not None]
    try:
        newest_close = read_ft_trades()["close_date"].max()
    except sqlite3.Error:
        newest_close = None
    return [("Freqtrade sqlite modified", max(db) if db else None),
            ("Newest Freqtrade close_date", newest_close if pd.notna(newest_close) else None),
            ("Lumibot state file modified", _mtime(LUMIBOT_STATE))]


def _api_profit() -> tuple[dict | None, str]:
    url = os.environ.get("FT_API_URL")
    user, pw = os.environ.get("FT_API_USERNAME"), os.environ.get("FT_API_PASSWORD")
    if not url or not user or not pw:
        return None, f"{D.NA} (FT_API_URL / FT_API_USERNAME / FT_API_PASSWORD not set in the container)"
    req = urllib.request.Request(url.rstrip("/") + "/api/v1/profit", method="GET")
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.load(resp), ""
    except Exception as exc:  # unreachable from the container, auth refused, bad JSON
        return None, f"{D.NA} (API not reachable from the container: {type(exc).__name__})"


def reconciliation_rows() -> list[dict]:
    rows = []
    t = read_ft_trades()
    closed = t[~t["is_open"]]
    api, why = _api_profit()
    if api is None:
        rows.append({"System": "Freqtrade", "Check": "Closed trade count: live sqlite vs Freqtrade API /profit",
                     "Expected": why, "Actual": len(closed), "Result": "N/A"})
    else:
        rows.append({"System": "Freqtrade", "Check": "Closed trade count: live sqlite vs Freqtrade API /profit",
                     "Expected": api.get("closed_trade_count"), "Actual": len(closed),
                     "Result": "PASS" if api.get("closed_trade_count") == len(closed) else "FAIL"})
        exp, act = round(float(api.get("profit_closed_coin", float("nan"))), 4), round(float(closed["close_profit_abs"].sum()), 4)
        rows.append({"System": "Freqtrade", "Check": "Net profit USDT: live sqlite vs Freqtrade API /profit",
                     "Expected": exp, "Actual": act, "Result": "PASS" if abs(exp - act) <= 0.001 else "FAIL"})
    archived = D.load_freqtrade_trades().set_index("trade_id")["profit_abs_usdt"]
    live = closed.set_index("id")["close_profit_abs"]
    same = sum(1 for i, v in archived.items() if i in live.index and abs(live[i] - v) < 1e-5)
    rows.append({"System": "Freqtrade", "Check": "Archived Oct 30 trades found in live sqlite with the same profit",
                 "Expected": len(archived), "Actual": same, "Result": "PASS" if same == len(archived) else "FAIL"})
    return rows


def snapshot_note(ft_cfg: dict, ft_stats: dict) -> list[str]:
    """Fields still shown from the Oct 30 export because neither the sqlite nor FT_CONFIG holds them."""
    shown_cfg = [k for k in ("strategy", "timeframe", "minimal_roi", "stoploss", "state", "version") if k in ft_cfg.get("_snapshot_keys", [])]
    shown_stats = [k for k in ("sharpe", "calmar", "cagr", "bot_start_date") if k in ft_stats.get("_snapshot_keys", [])]
    return shown_cfg + shown_stats
