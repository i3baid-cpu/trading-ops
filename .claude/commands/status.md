Give Abdullah the current state in plain language, read only:
1. Containers: `docker ps` for freqtrade, lumibot, trading-dashboard (up, since when, healthy).
2. Freqtrade: open trades and the last 5 closed trades from /root/freqtrade/user_data/tradesv3.dryrun.sqlite (read only, strategy column, exit reason, P&L). State whether MemeSleeveV3 has traded since 2026-10-30 21:26 UTC.
3. Alpaca: positions and realised P&L from /root/lumibot/strategies/trend_filter_state.json; last 10 lumibot log lines mentioning TrendFilter, BUY, SELL, FILL, rejected or error.
4. Errors: any ERROR or Traceback in the last 24 h of all three containers' logs.
5. The open items from docs/HANDOVER.md, in order, with one line each on whether anything moved.
Do not change anything. Keep it under 250 words.
