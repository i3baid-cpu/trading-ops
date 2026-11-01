# Handover: state of the trading setup as of 1 November 2026

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
| freqtrade | MemeSleeveV3, 4h, DOGE PEPE SHIB FLOKI /USDT, Binance spot, stake 25 USDT, max 2 | DRY RUN since 2026-10-30 21:26 UTC; Telegram alerts on | `sudo ft-swap-strategy <Name>` (claude-ops may run it only when Abdullah asks for that specific swap). Config `/root/freqtrade/config.json` is root only; `user_data/backtest_config.json` is the secrets free copy for backtests. |
| lumibot | TrendFilter: SPY and QQQ, hold while last completed close > SMA200 (1% band), monthly check, fractional shares, $1,000 sleeve inside a $100k paper account, Telegram alerts | PAPER since 2026-10-30 21:54 UTC; first decision Monday 2 Nov after the US open | config `/root/lumibot/config.json` (root), strategy `strategies/trend_filter.py`, ledger `strategies/trend_filter_state.json`; `docker compose up -d --build` as root |
| trading-dashboard | Streamlit dashboard, 8 tabs, reads the dry run sqlite, the Lumibot ledger and config, Yahoo daily data for the CRT tab | on 127.0.0.1:8501 and 100.99.81.45:8501 (Tailscale) | `cd /root/trading-ops && git pull --ff-only origin main && docker compose -f deploy/docker-compose.dashboard.yml up -d --build` as root |
| weekly-audit (cron, Sunday 06:17 UTC) | read only audit by `claude -p`, report to Telegram and `~/trading_fixes/results/weekly/` | installed 31 Oct, first run not yet verified | `/usr/local/sbin/weekly-audit` as root |

Users: root for config, .env, compose and sudo rules; `claude-ops` for Claude Code (ACLs deny it the secret files;
sudo allows only `docker restart freqtrade`, `docker logs --tail 200 freqtrade`, `ft-swap-strategy MemeSleeveV1/2/3`).
Repository: `github.com/i3baid-cpu/trading-ops` (private), cloned at `/root/trading-ops`; deploy key on the VPS.

## Decisions taken, with the evidence
* MemeSleeveV1 (5m): −45% over 12 months, 7,836 trades, fees ate it. Retired. `results/freqtrade_v2.md`.
* MemeSleeveV2 (15m): −7.7% over 12 months and loses in both rising and falling regimes; the 15m exit shakes
  it out of moves. Rejected. `results/freqtrade_v2_regimes.md`.
* MemeSleeveV3 (4h breakout, BTC daily EMA100 gate, trailing 10% after +20%): +4.8% in sample (PF 1.34,
  152 trades), +0.4% in the not truly held out year (PF 1.19, 26 trades), p values 0.16 and 0.75. In position
  18 of 18 full rising months, out of 8 of 9 falling months. Running as a forward test only. No V4 tuning until
  at least 4 weekly reports exist. `results/freqtrade_v3.md`.
* Alpaca SmaCross 20/50 with 5%/10% brackets: +2% vs SPY +123% over 2021 to 2026; brackets and 15% max
  exposure made it uninvestable; bracket orders also reject fractional shares. Replaced.
* TrendFilter SMA200 monthly: picked on 2007 to 2016, run once on 2017 to 2026: CAGR 13.8% vs SPY 13.4%
  (price), max drawdown −19.9% vs −34.1%. 50/50 SPY/QQQ buy and hold made 17.5%; the filter buys drawdown
  protection with return. `results/alpaca_trendfilter.md`. Capital ladder he stated: $1,000 paper now, $2,000 if it proves out.
* Robinhood (real money, about $1,120): ETH is 66% of the account against a 20% rule; manual meme sleeve lost
  −$5.11 on five $22 trades; FLOKI bought 30 Oct with no stop. Proposed rules in `fixes/robinhood/RULES_v2.md`.
  Open decisions for Abdullah: ETH (long term hold outside the rule, or reduce in steps), the FLOKI stop,
  closing the manual meme sleeve. Nothing on Robinhood is automated.
* CRT skill: the discretionary `crt-ict-trading-analyzer` was replaced by dashboard tab H: deterministic rules on
  closed candles, NO SETUP veto on reward to risk, sizing in fils for Kuwaiti prices, a swing Stock read, a long
  term weekly read with a 3 tranche plan, Yahoo fundamentals, and a signal log (`results/crt/crt_log.csv`) that
  must reach 30 resolved signals before any rule is changed. Rules in `docs/CRT_RULES_v2.md`.

## Open items, in order
1. V3 gate check (why no trades yet): download 10 days of 1d BTC and 4h pairs, compute BTC close vs EMA100 and
   each pair's 4h close vs EMA50 and prior 20 bar high; write `results/v3_gate_check.md`. Expected answer:
   gate shut because BTC is below its daily EMA100.
2. Verify the weekly audit runs: `/usr/local/sbin/weekly-audit` as root; fix the `claude -p` flags if the
   version rejects `--allowedTools`.
3. Monday 2 Nov: confirm TrendFilter's first monthly check in the lumibot logs and Telegram; if orders were
   rejected, read `strategies/trend_filter.py` and the Alpaca error before changing anything.
4. BOURSA long term read for Abdullah (he is considering buying at 2698 fils for a 1 to 2 year hold): run tab
   H with Horizon = Long term; the swing read on 29 Oct said DOWNTREND, RSI 29, support 2671.
5. Nice to have: watchlist mode in tab H (his Kuwaiti holdings KFH, BOURSA, WARBABANK, AZNOULA, ALG, BPCC);
   fill times in the Lumibot ledger; cancelled order alerts for Alpaca.

## How to work with Abdullah
* He is often on an iPad: give commands he can paste, one block at a time, and say which user runs them.
  `su - claude-ops` swallows any lines pasted after it; send it alone.
* Show diffs before applying; never restart or rebuild unless the current message asks for it.
* Report numbers with their source and date. "Not available" beats an estimate.
* Be direct about what the data shows, including when it contradicts what he hopes.
