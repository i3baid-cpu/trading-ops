"""Data-layer tests: run with  python -m pytest tests/  or  python tests/test_data.py"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import data as D  # noqa: E402


def test_freqtrade_matches_api_snapshot():
    ft = D.build_freqtrade_trades()
    st = D.load_freqtrade_stats()["profit"]
    m = D.compute_metrics(ft)
    assert m.closed == st["closed_trade_count"] == 21
    assert abs(m.net_pnl - st["profit_closed_coin"]) < 1e-4  # csv rounds to 6 dp
    assert abs(m.profit_factor - st["profit_factor"]) < 1e-3
    assert abs(m.max_drawdown - st["max_drawdown_abs"]) < 1e-3
    assert abs(m.win_rate / 100 - st["winrate"]) < 1e-6


def test_robinhood_fifo_matches_dashboard_realized():
    rh = D.build_robinhood_trades()
    closed = rh[rh["status"] == "closed"].set_index("symbol")
    for sym, val in {"PEPE": -2.21, "FLOKI": -2.22, "SHIB": -2.22, "SOL": 1.18}.items():
        assert round(float(closed.loc[sym, "pnl_usd"]), 2) == val
    doge = rh[(rh["symbol"] == "DOGE") & (rh["status"] == "closed")].sort_values("exit_time")
    assert [round(v, 2) for v in doge["pnl_usd"]] == [3.79, -2.25]
    nflx = rh[rh["symbol"] == "NFLX"]
    assert len(nflx) == 1 and math.isnan(nflx["pnl_usd"].iloc[0])  # never estimated


def test_open_lots_match_snapshot():
    rh = D.build_robinhood_trades()
    open_syms = set(rh[rh["status"] == "open"]["symbol"])
    assert open_syms == {"AMD", "NVDA", "QQQ", "BTC", "ETH", "FLOKI"}
    pos, acct = D.positions_table()
    assert set(pos["symbol"]) == open_syms
    assert pos.loc[pos["symbol"] == "ETH", "breach"].iloc[0]  # ETH over the 20% rule


def test_no_live_trading_surface():
    """The app must not import any broker / exchange client."""
    for fname in ("app.py", "data.py", "data_live.py", "charts.py", "trendfilter_panel.py", "trendfilter_calc.py"):
        src = open(os.path.join(os.path.dirname(__file__), "..", fname)).read()
        for forbidden in ("import alpaca", "from alpaca", "import ccxt", "import robin_stocks", "from lumibot", "import lumibot",
                          "forceenter", "forceexit", "submit_order", "create_order", "cancel_order"):
            assert forbidden not in src, f"{forbidden} found in {fname}"


def test_reconciliation_has_no_failures():
    rec = D.reconciliation()
    assert (rec["Result"] == "FAIL").sum() == 0
    assert (rec["Result"] == "PASS").sum() >= 19


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"[OK] {name}")
    print("All data-layer tests passed.")
