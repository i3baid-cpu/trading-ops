# Handover: state of the trading setup as of 3 November 2026

Read this first in every Claude Code session on the VPS. It is the memory of the audit and build work done on
30 and 31 October 2026 with Claude in the chat. Abdullah talks to you directly now; the rules below are his.

## Who and what
* Abdullah AlOmran, Kuwait (UTC+3). IT project manager, not a professional trader. Human in the loop: you
  analyse, propose and prepare; he approves anything that changes a running bot or moves money.
* Goals he stated: income from crypto (originally $600/month, which the data does not support), and a stock bot
  that tracks or beats the S&P 500. The evidence so far: no strategy here beats SPY; TrendFilter halves the
  drawdown for about SPY's return. Say this plainly whenever expectations drift.
* Hard rules: Freqtrade stays dry run and Lumibot stays paper until he approves a go live in writing. The
  dashboard is read only. No secrets in chat, logs, reports or the repository. New strategies are new files.

## What runs on this VPS (Hetzner, Ubuntu, 4 GB)
| Container | What | State | How to change |
|---|---|---|---|
| freqtrade | MemeSleeveV4 (V3's rules, SOL added), 4h, DOGE PEPE SHIB FLOKI SOL /USDT, Binance spot, stake 25 USDT, max 3 | DRY RUN; V3 ran 2026-10-30 21:26 to 2026-11-03 12:06 UTC with 0 trades; V4 since 2026-11-03 12:06 UTC (log: strategy V4, max_open_trades 3, whitelist 5 pairs, no errors); Telegram alerts on | Strategy, pairs and max_open_trades are in `/root/freqtrade/config.json` (root only; backup before V4: `config.json.bak-20261103-pre-v4`). `sudo ft-swap-strategy` allows only V1/2/3, so V4 was set as root. `user_data/backtest_config.json` is the secrets free mirror (V4, 5 pairs, max 3 since 3 Nov; previous copy `~claude-ops/backtest_config.bak-20261103-pre-v4.json`); to reproduce V3 runs pass `--strategy MemeSleeveV3 --pairs DOGE/USDT PEPE/USDT SHIB/USDT FLOKI/USDT --max-open-trades 2`. |
| lumibot | TrendFilter: SPY and QQQ, hold while last completed close > SMA200 (1% band), monthly check, fractional shares, $1,000 sleeve inside a $100k paper account, Telegram alerts | PAPER since 2026-10-30 21:54 UTC; rebuilt 2026-11-01 10:43 UTC with the state file fix (d47dd0b), restarts 0, ledger loaded `{'realized': 0.0, 'pos': {}}`, first check 2026-11-02 14:31 UTC: ledger reconciled at 0/0, both above SMA200, bought 0.645 SPY @ 759.36 and 0.705 QQQ @ 695.14 (both filled, no rejects, no `.invalid` file) | config `/root/lumibot/config.json` (root), strategy `/root/lumibot/strategies/trend_filter.py` (repo copy `fixes/alpaca/strategies/trend_filter.py`, in sync since 327a318), ledger `strategies/trend_filter_state.json`; `docker compose up -d --build` as root |
| trading-dashboard | Streamlit dashboard, 10 tabs (Freqtrade, Alpaca, Stock Check, Robinhood, Risk, Performance, Strategies, Trades, Health, Signals; deployed 2026-11-01 10:53 UTC from 8c845bd, data and CRT tests passed in the image, rollback image deploy-dashboard:pre-20261101), reads the dry run sqlite, the Lumibot ledger and config, Yahoo daily data for the Stock Check tab | on 127.0.0.1:8501 and 100.99.81.45:8501 (Tailscale) | `cd /root/trading-ops && git pull --ff-only origin main && docker compose -f deploy/docker-compose.dashboard.yml up -d --build` as root |
| weekly-audit (cron, Sunday 06:17 UTC) | read only audit by `claude -p`, report to Telegram and `~/trading_fixes/results/weekly/` | first run verified 2026-11-01 06:17 UTC: report `~/trading_fixes/results/weekly/2026-11-01.md` written, Telegram message arrived (Abdullah confirmed) | `/usr/local/sbin/weekly-audit` as root |

Users: root for config, .env, compose and sudo rules; `claude-ops` for Claude Code (ACLs deny it the secret files;
sudo allows only `docker restart freqtrade`, `docker logs --tail 200 freqtrade`, `ft-swap-strategy MemeSleeveV1/2/3`).
Found 1 Nov: claude-ops is also in the `docker` group, which is root equivalent and bypasses the sudo list and
the ACLs (see open item 2). Until Abdullah decides, use docker only for read only `ps`, `inspect` and `logs`.
Repository: `github.com/i3baid-cpu/trading-ops` (private), cloned at `/root/trading-ops`; deploy key on the VPS.

## Decisions taken, with the evidence
* MemeSleeveV1 (5m): −45% over 12 months, 7,836 trades, fees ate it. Retired. `results/freqtrade_v2.md`.
* MemeSleeveV2 (15m): −7.7% over 12 months and loses in both rising and falling regimes; the 15m exit shakes
  it out of moves. Rejected. `results/freqtrade_v2_regimes.md`.
* MemeSleeveV3 (4h breakout, BTC daily EMA100 gate, trailing 10% after +20%): +4.8% in sample (PF 1.34,
  152 trades), +0.4% in the not truly held out year (PF 1.19, 26 trades), p values 0.16 and 0.75. In position
  18 of 18 full rising months, out of 8 of 9 falling months. Ran as a forward test from 30 Oct to 3 Nov and made
  no trades; replaced by V4 (below). `results/freqtrade_v3.md`. Why no V3 trades: the gate was shut on the 30 and
  31 Oct closes (−0.57%, −0.29%) and reopened on the 1 Nov close (+0.69%, 78,354 vs EMA100 77,819); as of the
  2 Nov 08:00 4h candle no pair is above its 20 bar high, and DOGE, SHIB, FLOKI are below EMA50.
  `results/v3_gate_check_2026-11-02.md`, rerun with `python3 -I scripts/v3_gate_check.py`.
* Alpaca SmaCross 20/50 with 5%/10% brackets: +2% vs SPY +123% over 2021 to 2026; brackets and 15% max
  exposure made it uninvestable; bracket orders also reject fractional shares. Replaced.
* TrendFilter SMA200 monthly: picked on 2007 to 2016, run once on 2017 to 2026: CAGR 13.8% vs SPY 13.4%
  (price), max drawdown −19.9% vs −34.1%. 50/50 SPY/QQQ buy and hold made 17.5%; the filter buys drawdown
  protection with return. `results/alpaca_trendfilter.md`. Capital ladder he stated: $1,000 paper now, $2,000 if it proves out.
* TrendFilter state file fix (1 Nov, approved by Abdullah): the weekly audit found the ledger file empty, and
  `json.load` in `initialize()` would have crashed the bot on the next restart. An empty, missing or invalid file is
  now treated as no state: log and Telegram warning, the bad file kept as `trend_filter_state.json.invalid`, the
  ledger reseeded from broker positions on the first trading iteration. If that happens after trades, realized P&L
  resets to 0 and sizing returns to the $1,000 base. Trading rule unchanged, so edited in place (the same file was
  edited on 30 Oct). Commits 327a318 (repo copy was the 30 Oct original; synced with the deployed file, notify.py
  added) and d47dd0b. Evidence: `~/trading_fixes/results/weekly/2026-11-01.md` section 3.
* Robinhood (real money, about $1,120): ETH is 66% of the account against a 20% rule; manual meme sleeve lost
  −$5.11 on five $22 trades; FLOKI bought 30 Oct with no stop. Proposed rules in `fixes/robinhood/RULES_v2.md`.
  Open decisions for Abdullah: ETH (long term hold outside the rule, or reduce in steps), the FLOKI stop,
  closing the manual meme sleeve. Nothing on Robinhood is automated.
* CRT skill: the discretionary `crt-ict-trading-analyzer` was replaced by dashboard tab 3 · Stock Check (was tab H): deterministic rules on
  closed candles, NO SETUP veto on reward to risk, sizing in fils for Kuwaiti prices, a swing Stock read, a long
  term weekly read with a 3 tranche plan, Yahoo fundamentals, and a signal log (`results/crt/crt_log.csv`) that
  must reach 30 resolved signals before any rule is changed. Rules in `docs/CRT_RULES_v2.md`.
* SOL / V4 study (2 Nov, run as claude-ops with `docker run`, which Abdullah approved for this study; plan
  `docs/RESEARCH_V4_PLAN.md`): V3 unchanged is profitable on the unseen 2020-08 to 2023-10 window on every coin and
  as a basket (+58 USDT, PF 1.46), but far below holding the coins. Of the 6 pre-declared variants, variant 5 (memes
  + SOL, max 3 open trades) won on window A (+79.4 USDT, PF 1.64) and held on B (+82.6, PF 1.38 vs V3's +52.1, PF 1.32);
  it passed fee 0.2%, 15m detail, ±25% neighbours and lookahead. Most of the gain is SOL; the third slot only adds
  capital. Profit comes from bull years (2021, 2024); about +25 USDT a year at 25 USDT stakes. It is a `config.json`
  change (SOL in the whitelist, max_open_trades 3), not new code, so no `MemeSleeveV4.py` was written.
  `results/research_v4_sol.md`.
* MemeSleeveV4 (3 Nov, Abdullah's decision): the dry run moved to variant 5 now instead of after 4 weekly reports,
  because V3 had no trades to review. `fixes/freqtrade/MemeSleeveV4.py` is V3's code with only the class name and
  header changed, so its trades are labelled V4; SOL and max_open_trades 3 are in `config.json`. Dashboard, gate
  script and /gate /status commands follow V4. Real money still needs his written approval.

## Open items, in order
1. TrendFilter's first check ran 2 Nov 14:31 UTC and both buys filled (logs). Abdullah to confirm the Telegram alert
   arrived; then this item closes.
2. claude-ops is in the `docker` group (gid 983, found 1 Nov), which is root equivalent. Decision for Abdullah:
   remove it (`gpasswd -d claude-ops docker` as root, then add sudo rules for the read only lumibot commands
   Claude Code needs: `docker ps`, `docker logs --tail 200 lumibot`) or accept it knowingly.
3. Find what wrote the empty `trend_filter_state.json` (kept as `strategies/trend_filter_state.json.empty-bak`,
   it was already empty at the 06:17 UTC audit on 1 Nov; when it was created is not known). Still unknown.
4. Drift check: the repo copy of TrendFilter had fallen behind the VPS. Compare the other deployed files with the repo
   (`/root/lumibot/config_v2.json`, `backtest_v2.py`) and copy the weekly reports into `results/weekly/`.
5. BOURSA long term read for Abdullah (he is considering buying at 2698 fils for a 1 to 2 year hold): run tab
   3 · Stock Check with Horizon = Long term; the swing read on 29 Oct said DOWNTREND, RSI 29, support 2671.
6. Nice to have: watchlist mode in tab 3 · Stock Check (his Kuwaiti holdings KFH, BOURSA, WARBABANK, AZNOULA, ALG, BPCC);
   fill times in the Lumibot ledger; cancelled order alerts for Alpaca.
7. V4 forward test (since 2026-11-03 12:06 UTC): review after 4 weekly reports (first possible about 1 Dec), against
   the study's numbers in `results/research_v4_sol.md`. Optional root change: add MemeSleeveV4 to the sudo swap rule
   so a later swap does not need root. Rollback to V3 meanwhile: restore `config.json.bak-20261103-pre-v4` as root
   and restart.
8. On 2 Nov a Claude Code session ran as root, not claude-ops (git had no root identity; files it created in
   `/root/trading-ops` are root owned). Start sessions with `su - claude-ops`, then `cd ~/trading-ops && claude`.

## How to work with Abdullah
* He is often on an iPad: give commands he can paste, one block at a time, and say which user runs them.
  `su - claude-ops` swallows any lines pasted after it; send it alone.
* Show diffs before applying; never restart or rebuild unless the current message asks for it.
* Report numbers with their source and date. "Not available" beats an estimate.
* Be direct about what the data shows, including when it contradicts what he hopes.
