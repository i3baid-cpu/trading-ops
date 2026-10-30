# Freqtrade config changes (edit /root/freqtrade/user_data/config.json yourself; keep a copy first)

Only these keys change. Everything else (exchange block, telegram, api_server, db_url) stays as it is.

| Key | Current (from API Oct 30) | Proposed | Reason |
|---|---|---|---|
| `strategy` | `MemeSleeveV1` | `MemeSleeveV2` | new file, V1 kept on disk |
| `timeframe` | `5m` | remove from config | V2 sets 15m; a config value would override it |
| `minimal_roi` | `{0:0.12,30:0.08,60:0.04,120:0}` | remove from config | otherwise it overrides V2's ROI |
| `stoploss` | `-0.10` | remove from config | same reason |
| `trailing_stop` | `false` | remove from config | same reason |
| `max_open_trades` | `2` | `2` | unchanged |
| `stake_amount` | `25` | `25` | unchanged, V2 also caps at 25 |
| `tradable_balance_ratio` | not reported | `0.5` | dry run wallet and later live wallet never fully committed |
| `dry_run_wallet` | not reported | `200` | so dry run percentages mean something at your intended live size |
| `unfilledtimeout.entry` | `10` | `15` | one 15m candle |
| `entry_pricing.price_side` | `same` | `other` | fill at the ask; removes the adverse selection of waiting at the bid. Costs the spread, which is tiny on Binance for these pairs |
| `exit_pricing.price_side` | `same` | `other` | same logic on exit |
| `pairlists` | StaticPairList DOGE PEPE SHIB FLOKI | unchanged for now | add `VolumePairList` only after V2 proves itself on the static four |
| `stoploss_on_exchange` | `false` | `false` in dry run, **`true` before live** | exchange holds the stop if the VPS or container dies |

## Backtest and validation commands (run on the VPS, inside the container, dry run only)

```bash
cd /root/freqtrade
# 1. data: 12 months of 15m and 1h for the pairs plus BTC
docker run --rm -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable \
  download-data --exchange binance -p DOGE/USDT PEPE/USDT SHIB/USDT FLOKI/USDT BTC/USDT -t 15m 1h --days 365

# 2. backtest V1 and V2 side by side, fees 0.1%
docker run --rm -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable \
  backtesting --strategy-list MemeSleeveV1 MemeSleeveV2 --timerange 20251101-20261030 --fee 0.001 --export trades

# 3. lookahead and recursive checks (must both be clean before trusting any number)
docker run --rm -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable \
  lookahead-analysis --strategy MemeSleeveV2 --timerange 20260601-20261030
docker run --rm -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable \
  recursive-analysis --strategy MemeSleeveV2 --timerange 20260601-20261030

# 4. out of sample: optimise nothing on 20261001-20261030, just run it
docker run --rm -v "$PWD/user_data:/freqtrade/user_data" freqtradeorg/freqtrade:stable \
  backtesting --strategy MemeSleeveV2 --timerange 20261001-20261030 --fee 0.001 --breakdown day
```

## Go-live gate for V2 (all must be true)
* Backtest over 12 months: profit factor above 1.3 after 0.1% fees, max drawdown under 10%, at least 150 trades, and the last 3 months (out of sample) are not worse than the first 9.
* Lookahead and recursive analysis clean.
* Dry run: at least 100 trades or 4 weeks, profit factor above 1.2, drawdown under 10%, and the dry run profit per trade within 30% of the backtest's for the same period.
* Live start: 200 USDT, stake 25, `stoploss_on_exchange: true`, Binance key trade only, no withdrawals, IP locked.
* Kill switch: if realised loss in any calendar month exceeds 10% of the live wallet, `/stopentry` via Telegram and review before restarting.
