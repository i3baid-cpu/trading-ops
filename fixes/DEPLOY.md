# Deploying the fixes to the VPS (you run these; I have no access to the server)

Originals are never overwritten. New files go in beside them; the config points at the new name.

## 0. From your laptop: copy the folder up
```bash
scp -r trading_fixes user@VPS:~/trading_fixes
ssh user@VPS
```

## 1. Freqtrade (dry run stays on)
```bash
cp ~/trading_fixes/freqtrade/MemeSleeveV2.py /root/freqtrade/user_data/strategies/
cp /root/freqtrade/user_data/config.json /root/freqtrade/user_data/config.json.bak-$(date +%F)
nano /root/freqtrade/user_data/config.json      # apply the table in freqtrade/config_changes.md
docker restart <freqtrade container name>
docker logs --tail 50 <freqtrade container name>  # expect "Using strategy MemeSleeveV2" and dry_run True
```
Then run the download-data, backtesting, lookahead-analysis and recursive-analysis commands in `config_changes.md` and send me the output tables. If V2 does not beat V1 after fees in the backtest, we do not keep it just because it is newer.

## 2. Alpaca (paper stays on)
```bash
cp ~/trading_fixes/alpaca/strategies/trend_filter.py ~/lumibot/strategies/
cp ~/lumibot/config.json ~/lumibot/config.json.bak-$(date +%F)
cp ~/trading_fixes/alpaca/config_v2.json ~/lumibot/config.json
cp ~/trading_fixes/alpaca/backtest_v2.py ~/lumibot/
cd ~/lumibot && docker compose up -d --build && docker compose logs --tail 50
```
Then: `docker compose run --rm -v ./backtest_v2.py:/app/backtest_v2.py -v ./logs:/app/logs lumibot python backtest_v2.py`
and send me the two tearsheets (logs/). Also finish the Alpaca email verification; paper orders are rejected until then.

## 3. Robinhood (manual)
Read `robinhood/RULES_v2.md`, decide the ETH question in section 3, and place or cancel the FLOKI stop.

## 4. Things I still need from you
1. The live `~/lumibot/strategies/sma_cross.py` (the archived copy was truncated), so I can confirm the fractional bracket problem.
2. `/root/freqtrade/user_data/config.json` with secrets blanked, so I can check the keys the API does not return (pairlist handlers, telegram, protections, tradable_balance_ratio).
3. The backtest outputs from steps 1 and 2.
4. Your answers: is the $600 per month or in total, and over what horizon? How much capital are you willing to put at risk in each system? Is ETH a long term hold?
5. Robinhood cost basis for the ETH and BTC you held before Aug 29 (from the app's position screen), so the dashboard can show real unrealised P&L instead of "Not available".
6. If you want the dashboard live rather than file based: confirm the `ftmonitor` tunnel command you use for FreqUI, and I will add the read only API loader to `data.py`.
