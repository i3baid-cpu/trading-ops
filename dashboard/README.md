# Trading Command Center (read-only dashboard)

An interactive, locally runnable analytics dashboard for the four trading setups in the
Oct 30 2026 audit pack: Robinhood (live), Freqtrade meme-sleeve (dry-run), Alpaca/Lumibot
(paper) and the CRT skill (analysis only).

It is **read only by design**. The app opens no broker, exchange or bot connection, needs no
API keys, and has no order controls. A test (`tests/test_data.py::test_no_live_trading_surface`)
fails the build if any trading client or order call is ever imported.

## Why Streamlit

| Option | Fit for this setup |
|---|---|
| FreqUI enhancement | Covers only Freqtrade. Cannot show Robinhood or Alpaca, and customising the Vue app is heavy. |
| **Streamlit + Plotly (chosen)** | Pure Python like the rest of the stack (Freqtrade, Lumibot), one container on the same VPS, interactive charts, filters and tables out of the box, about 900 lines to maintain. |
| Plotly Dash | Same language, more boilerplate for the same screens. Worth it only for multi-user auth later. |
| React app | Best polish, but a second toolchain to maintain for a single user. |
| Standalone HTML | No live data path; fine for a snapshot, not for a command center. |

Deployment matches the existing pattern: Docker on the Hetzner VPS, bound to `127.0.0.1`,
reached over Tailscale or an SSH tunnel exactly like FreqUI.

## Screens

| Tab | Contents |
|---|---|
| A · Executive Overview | Equity, cash, invested, realised and unrealised P&L, daily / weekly / monthly / all-time realised returns, active strategies, open positions, risk flags, bot status and last records |
| B · Performance | Equity curve, drawdown, daily P&L, rolling P&L, contribution by asset, benchmark panels, risk-adjusted metrics, holding time vs return |
| C · Strategy Comparison | Per-strategy return, drawdown, win rate, profit factor, trade count, expectancy, holding period, paper/live/backtest status, selectable metric chart, exit-reason and entry-hour breakdowns |
| D · Trade Explorer | Searchable, filterable, sortable trade table; click a row for entry/exit, size, P&L, fees, stop, reasons and a price-timeline chart with buy/sell markers (candlesticks when candle files exist) |
| E · Risk | Allocation, concentration vs the 20% rule with breach warnings, exposure, stop coverage, risk-budget table, P&L distribution, realised drawdown |
| F · System Health | Component state cards, data freshness, 21 reconciliation checks between independent records, canceled orders, execution timing, incident log |
| G · Signal Explanation | For any trade: the rule-based reason (from strategy code and order records), the risk checks, the final decision, and clearly separated AI commentary; plus rule sheets for each strategy |

Global sidebar filters: time zone (Asia/Kuwait, America/New_York, UTC), systems, strategies, date range.

## Data used (all real, from the audit ZIP)

| File in `data/` | Origin |
|---|---|
| `robinhood_orders.csv` | `01_robinhood/orders_full.csv`, 23 orders from the Robinhood API |
| `freqtrade_trades.csv` | `02_freqtrade/trades_full.csv`, 21 dry-run trades from the Freqtrade API |
| `freqtrade_stats.json` | `02_freqtrade/dry_run_stats_2026-10-30.json` |
| `freqtrade_config.json` | `02_freqtrade/live_config_from_api.json` |
| `alpaca_config.json` | `03_alpaca/config.json` |
| `alpaca_backtest.json` | headline numbers written in `03_alpaca/HISTORY.md` |
| `robinhood_snapshot.json` | positions and cash from `dashboard_page_source.tsx` (Oct 27), adjusted for the Oct 30 DOGE stop fill and FLOKI buy |

Robinhood round trips are built with FIFO lot matching from the raw orders. Where a cost basis
is not in the archive (the NFLX sale, most of the ETH and BTC holdings) P&L is shown as
**Not available**, never estimated. Robinhood strategy names are inferred from order patterns
and labelled as such. No candle data was in the ZIP, so indicator values at signal time are
Not available and the Trade Explorer draws the fill-price path instead of candlesticks until
you run `fetch_candles.py`.

## Install and run

### Option 1: Python (any machine)

```bash
cd trading_dashboard
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
Open http://localhost:8501.

### Option 2: Docker (matches the VPS setup)

```bash
cd trading_dashboard
docker compose up -d --build
```
The container binds to `127.0.0.1:8501` only. From your laptop:
`ssh -L 8501:127.0.0.1:8501 user@vps` then open http://localhost:8501, or add the Tailscale IP
to the `ports:` line the same way you did for FreqUI.

### Optional: real candlesticks

```bash
python fetch_candles.py
```
Downloads 5m OHLC for DOGE, PEPE, SHIB and FLOKI from Binance's public market-data endpoint
(no key, read-only) into `data/candles/`. Restart the app and the Trade Explorer will draw
candlesticks with the trades on them.

## Tests

```bash
python tests/test_data.py            # data layer: FIFO, metrics, reconciliation, no-trading guard
python tests/ui_smoke.py             # headless browser: every screen, filters, selections, screenshots/
```
`ui_smoke.py` needs Playwright (`pip install playwright && playwright install chromium`). It opens
all seven tabs, asserts no Streamlit exception, runs a search in the Trade Explorer, picks a
trade in Signal Explanation, changes the system filter and time zone, and writes a screenshot
of each screen to `screenshots/`.

## Refreshing the data

Replace the files in `data/` with new exports and restart (or press R in the browser).
To make the Freqtrade panels live, add a loader in `data.py` that calls the bot's REST API
with the existing read-only `ftmonitor` tunnel (`GET /api/v1/trades`, `/profit`, `/show_config`)
and writes the same CSV/JSON shapes. Keep the API password in `.env` on the server, never in
the repository or in chat.

## Project layout

```
trading_dashboard/
├── app.py               Streamlit UI (7 screens, filters, styling)
├── data.py              loaders, FIFO matching, metrics, reconciliation
├── charts.py            Plotly figures with one fixed palette
├── fetch_candles.py     optional public-data candle download
├── data/                real records from the audit pack (see table above)
├── tests/               test_data.py, ui_smoke.py
├── .streamlit/config.toml
├── requirements.txt, Dockerfile, docker-compose.yml
```

## Limits to keep in mind

- Everything is a snapshot of the archive; there is no live heartbeat until the API loaders are wired.
- Robinhood prices are from Oct 27 (FLOKI at its Oct 30 fill). Equity history, fees and trade reasons are not provided by the Robinhood API.
- 21 dry-run trades over 1.4 days and 8 live round trips are far too few for statistical conclusions; the dashboard shows the numbers and says so.
