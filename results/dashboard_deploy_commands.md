# Dashboard deploy commands (live loaders), 2026-10-31

Run as **root** on the VPS. The repository is checked out at `/root/trading-ops`. Nothing below has been run;
the container was not started by the agent.

## Build and start

```bash
cd /root/trading-ops
git pull --ff-only origin main
docker compose -f deploy/docker-compose.dashboard.yml config --quiet
docker compose -f deploy/docker-compose.dashboard.yml build
docker compose -f deploy/docker-compose.dashboard.yml up -d
```

## Check it

```bash
docker ps --filter name=trading-dashboard
docker logs --tail 20 trading-dashboard
curl -fsS http://127.0.0.1:8501/_stcore/health
docker inspect trading-dashboard --format '{{range .Mounts}}{{.Source}} -> {{.Destination}} rw={{.RW}}{{"\n"}}{{end}}'
```

`curl` should print `ok`, and every mount should show `rw=false`. Then open http://100.99.81.45:8501 from a
Tailscale device (or http://127.0.0.1:8501 through an SSH tunnel).

## Update later

```bash
cd /root/trading-ops
git pull --ff-only origin main
docker compose -f deploy/docker-compose.dashboard.yml up -d --build
```

## Stop

```bash
docker compose -f deploy/docker-compose.dashboard.yml down
```

## What the container reads (all read only)

| Mount | Used for |
|---|---|
| `/root/freqtrade/user_data` -> `/live/freqtrade/user_data` | `tradesv3.dryrun.sqlite` (+ `-wal`, `-shm`) and `backtest_config.json` |
| `/root/lumibot/strategies` -> `/live/lumibot/strategies` | `trend_filter_state.json` (sleeve ledger) |
| `/root/lumibot/config.json` -> `/live/lumibot/config.json` | sleeve capital, symbols, SMA params |
| `dashboard/data` -> `/app/data` | Oct 30 exports (Robinhood, snapshot fields, archive checks) |

Directory mounts are required. The sqlite is in WAL mode: a read-only single-file mount in the read-only
container failed with `unable to open database file`, and a file copy without the `-wal` showed the newest
close as 2026-10-30 18:05 UTC instead of 21:27 UTC. trend_filter.py writes its state with `os.replace`, which a
single-file bind mount does not follow.

The "/profit vs sqlite" reconciliation row shows Not available unless `FT_API_URL`, `FT_API_USERNAME` and
`FT_API_PASSWORD` are set for the container (for example in an untracked env file). They are deliberately
not in the compose file.

## Verification before commit

Data range: Freqtrade `tradesv3.dryrun.sqlite` trades 1 to 25 (23 rows, ids 6 and 9 absent), open dates
2026-10-29 12:30 UTC to 2026-10-30 20:00 UTC, newest close 2026-10-30 21:27 UTC; `trend_filter_state.json`
empty (0 bytes); Oct 30 2026 exports in dashboard/data.

```bash
cd /root/trading-ops/dashboard && python tests/test_data.py       # DASH_MODE unset (file mode)
```
Result: all 5 tests pass (`test_no_live_trading_surface` now also scans data_live.py).

Live mode was exercised on the host against the real files (`DASH_MODE=live`, FT_DB, FT_CONFIG,
LUMIBOT_STATE, LUMIBOT_CONFIG pointing at the paths above) with Streamlit's AppTest on every tab:
23 closed MemeSleeveV1 trades, net +1.1392 USDT, PF 1.314, max drawdown 2.339 USDT; Alpaca "no paper trades
yet"; reconciliation 21 PASS, 1 INFO, 1 N/A (API credentials not set), 0 FAIL. A synthetic ledger and a scratch
copy of the sqlite with added MemeSleeveV3 trades (one closed, one open) also rendered without exceptions.
