# Live data loaders for the dashboard (task for the VPS agent)

The dashboard currently reads the Oct 30 2026 exports in dashboard/data/. On the VPS it must read the live
sources instead when DASH_MODE=live, without changing any screen. Implement `dashboard/data_live.py` and a
small switch in `data.py`; keep the file based path working for DASH_MODE unset (tests rely on it).

## Interfaces to satisfy (see data.py)
* `build_freqtrade_trades()` must return the same columns as today, sourced from the `trades` table of
  FT_DB (Freqtrade 2026.9 sqlite). Inspect the real schema first (`PRAGMA table_info(trades)`) and map:
  open_date/close_date (UTC) to entry_time/exit_time in Asia/Kuwait, open_rate/close_rate, amount,
  stake_amount, close_profit_abs, close_profit (ratio, multiply by 100), exit_reason, fee_open+fee_close in
  stake currency, strategy, enter_tag, is_open. Include open trades with status "open".
  Strategy label: `<strategy> (<timeframe>, dry-run)`. Trades from MemeSleeveV1 before 2026-10-30 21:26 UTC
  stay labelled V1 so the forward test of V3 is reported separately.
* `load_freqtrade_stats()` and `load_freqtrade_config()`: derive from the database and FT_CONFIG where
  possible; anything not derivable keeps the exported snapshot and is marked as such in the System Health tab.
* Alpaca: parse LUMIBOT_STATE (ledger written by trend_filter.py: per symbol qty, cost basis, realized P&L,
  fills) into the unified trade frame with system "Alpaca", strategy "TrendFilter (daily, paper)", and a
  positions table for the $1,000 sleeve. If the file is empty or missing, show "no paper trades yet".
* Data freshness in System Health: use the sqlite file mtime, the newest close_date, and the state file mtime.
* Reconciliation tab: add checks that the number of closed trades in the sqlite equals what the Freqtrade API
  /profit reports, if the API is reachable from the container (it may not be; then mark Not available).

## Constraints
* Read only. Open the sqlite with `?mode=ro` (uri=True). Never write to any mounted file.
* No broker SDKs. tests/test_data.py must keep passing in file mode.
* Cache loaders with st.cache_data(ttl=60) in live mode so the page refreshes within a minute.
* Label the V3 forward test on the Overview and Strategy tabs: "forward test; backtest positive but not
  statistically significant (PF 1.34 in sample, 26 trades held out)".
