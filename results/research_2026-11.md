# Research cycle 2026-11: five single-change candidates against MemeSleeveV4

Run date: 2026-11-14, as claude-ops. Pre-registration: `docs/RESEARCH_CYCLE_2026-11.md`. Method:
`docs/RESEARCH_PROTOCOL.md`. Freqtrade 2026.9 (`freqtradeorg/freqtrade:stable`, image 9d67afb8eb5f), Binance spot,
`backtest_config.json` (stake 25 USDT, wallet 1000 USDT, max_open_trades 3).
Research only: V4, `config.json`, the containers and the dry run database were not touched. The only change on the
VPS is four new strategy files in `user_data/strategies`, copied from `fixes/freqtrade/`.

## Short answer
* **No candidate passes the bar on window A. V4 stays as it is.**
* **The closest is candidate 4 (2h candles).**
  * It passes profit factor, profit and profit without the best two months: PF 1.80 against 1.64, +104.88 against
    +79.36 USDT, and +54.23 USDT without the best two months.
  * It fails "drawdown no worse than the baseline" by 0.06 points: 2.61% against 2.55%.
  * The bar is applied as written. A near miss after the results are known is not a reason to bend it.
* **The other four miss the profit factor test, which needs at least 1.74:**
  * gate hysteresis 1.63
  * volume 0.8× 1.68
  * AVAX and LINK added 1.34; this one also fails on drawdown and profit without the best two months
  * two stage exit 1.60
* **Not run, as the protocol says:** with no passing candidate there is no stress test and no window B run this cycle.
* **Compute:** the whole cycle fit easily. Six backtests took 48 seconds, so candidate 4 was not dropped.

## Commands
Downloads, 2026-11-14 (log in `results/cycle_2026-11/download.log`):
```
FT="docker run --rm -v /root/freqtrade/user_data:/freqtrade/user_data freqtradeorg/freqtrade:stable"
CFG="--config /freqtrade/user_data/backtest_config.json"
PAIRS="BTC/USDT DOGE/USDT SHIB/USDT SOL/USDT PEPE/USDT FLOKI/USDT AVAX/USDT LINK/USDT"
$FT download-data $CFG --pairs $PAIRS --timeframes 4h 1d --timerange 20200101-
$FT download-data $CFG --pairs $PAIRS --timeframes 4h 1d --timerange 20200101- --prepend
$FT download-data $CFG --pairs $PAIRS --timeframes 2h --timerange 20200101-
```
Backtests: each full log, starting with the exact command, is in `results/cycle_2026-11/backtests/`. All share
`--timerange 20200815-20231030 --fee 0.001 --breakdown month --enable-protections --export none`.
```
$FT backtesting $CFG --strategy MemeSleeveV4  --timeframe 4h <common> --pairs DOGE/USDT SHIB/USDT SOL/USDT                         # baseline
$FT backtesting $CFG --strategy MemeSleeveV4a --timeframe 4h <common> --pairs DOGE/USDT SHIB/USDT SOL/USDT                         # 1
$FT backtesting $CFG --strategy MemeSleeveV4b --timeframe 4h <common> --pairs DOGE/USDT SHIB/USDT SOL/USDT                         # 2
$FT backtesting $CFG --strategy MemeSleeveV4  --timeframe 4h <common> --pairs DOGE/USDT SHIB/USDT SOL/USDT AVAX/USDT LINK/USDT     # 3
$FT backtesting $CFG --strategy MemeSleeveV4c --timeframe 2h <common> --pairs DOGE/USDT SHIB/USDT SOL/USDT                         # 4
$FT backtesting $CFG --strategy MemeSleeveV4d --timeframe 4h <common> --pairs DOGE/USDT SHIB/USDT SOL/USDT                         # 5
```
Profit without the best two months and the per year figures are summed from each log's MONTH BREAKDOWN table.

## Data
Binance spot, downloaded through 2026-11-14:

| Pair | Data starts | Notes |
|---|---|---|
| BTC 1d | 2020-01-01 | the gate |
| DOGE, LINK | 2020-01-01 | |
| SOL | 2020-08-11 | |
| AVAX | 2020-09-22 | |
| SHIB | 2021-05-10 | |
| PEPE, FLOKI | 2023-05-05 | |

Timeframes are 4h, 1d and 2h for all of these.
* **Window A:** 2020-08-15 to 2023-10-30.
* **Window B (not run):** 2023-10-30 to 2026-11-14.
* **Pairs on A:** DOGE, SHIB and SOL, the same convention as the V4 study.
  * PEPE and FLOKI only exist for A's last 6 months; the pre-registration treats them as not listed on A.
  * SHIB and AVAX trade once their data and warm-up allow.
* **Setup check:** the baseline reproduces the V4 study exactly: 140 trades, +79.365 USDT, PF 1.64, 2.55% underwater,
  and the same per year figures.

## What each candidate changes (one change each; files in `fixes/freqtrade/`)
1. **MemeSleeveV4a:** the BTC gate opens at a daily close above EMA100 × 1.01, shuts below EMA100 × 0.99, and keeps
   its last state in between. Checked on a toy series inside the freqtrade image.
2. **MemeSleeveV4b:** the entry needs volume above 0.8× the 20 bar mean instead of 1.0×.
3. **MemeSleeveV4 with AVAX/USDT and LINK/USDT added:** pairs only (`--pairs`), no new file.
4. **MemeSleeveV4c:**
   * 2h candles, breakout 40 bars, startup 1,400 candles.
   * Exactly as pre-registered, everything else stays in bars: EMA50, the 20 bar volume mean and the 6 candle cooldown
     now cover half the hours they cover on 4h. The plan only adjusted the breakout length to keep the same hours.
5. **MemeSleeveV4d:**
   * Sells half the position once the trade is up 10%; the rest runs on V4's trailing stop and exit signal.
   * **Deviation:** the plan names `custom_exit`, which can only close a whole trade. The half exit uses Freqtrade's
     partial exit instead (`adjust_trade_position` returning a negative stake, `position_adjustment_enable`).
   * **Confirmed active:** trailing stop winners fell from +188.50 to +166.70 USDT and trend-lost losers improved from
     −78.27 to −64.31.
   * Average stake fell from 24.97 to 21.41 USDT, because half of each winning position leaves early.

## Window A results

| # | Candidate | Trades | Profit USDT | PF | DD, account underwater | DD, balance | Without best 2 months | Market (hold) | Passes the bar |
|---|---|---|---|---|---|---|---|---|---|
| | **Baseline: V4** | 140 | 79.36 | 1.64 | 2.55% | 2.81% | 24.57 | +888.7% | (reference) |
| 1 | Gate hysteresis (V4a) | 135 | 77.71 | 1.63 | 2.54% | 2.54% | 26.02 | +888.7% | no: PF |
| 2 | Volume 0.8× (V4b) | 140 | 82.97 | 1.68 | 2.46% | 2.72% | 28.17 | +888.7% | no: PF |
| 3 | Add AVAX, LINK (V4) | 227 | 69.00 | 1.34 | 4.57% | 4.43% | −0.64 | +552.3% | no: PF, DD, without best 2 |
| 4 | 2h candles (V4c) | 170 | **104.88** | **1.80** | 2.61% | 2.62% | **54.23** | +896.6% | **no: DD by 0.06 points** |
| 5 | Two stage exit (V4d) | 140 | 71.61 | 1.60 | 2.44% | 2.44% | 24.80 | +888.7% | no: PF |

Columns:
* **Market (hold):** Freqtrade's market change, the average price change of the pairs over the window. It stands for
  holding the same coins. Holding beat every candidate by a wide margin, as it did in the V4 study.
* **DD, account underwater:** the measure in the V4 study's DD column, which is where the baseline's 2.55% in the
  pre-registration comes from. The bar is applied to this column.
* **DD, balance:** a second, balance-based measure Freqtrade also reports, shown for information. On it, candidate 4's
  2.62% is below the baseline's 2.81%. The two measures disagree on candidate 4. The bar names one, so this does not
  change the result.

**The bar (protocol section 5), tested on A:** PF at least 1.64 + 0.1 = 1.74; profit positive; PF above 1.2;
drawdown at most 2.55%; profit without the best two months positive.
* Positive and above 1.2 on window B are also required. B was not run because nothing passed A.
* Only candidate 4 clears PF; it then fails drawdown.

### Per calendar year, window A (USDT)

| Run | 2020 (from 15 Aug) | 2021 | 2022 | 2023 (to 30 Oct) |
|---|---|---|---|---|
| Baseline V4 | −0.85 | +86.51 | −1.19 | −5.11 |
| 1 V4a | −0.85 | +80.87 | +2.71 | −5.02 |
| 2 V4b | −0.85 | +89.20 | −1.19 | −4.19 |
| 3 + AVAX, LINK | −7.63 | +88.99 | −6.23 | −6.14 |
| 4 V4c (2h) | −2.60 | +103.12 | +7.79 | −3.42 |
| 5 V4d | −0.84 | +74.81 | +2.50 | −4.88 |

As with V4 itself, every candidate makes its money in the 2021 bull run, and the BTC gate keeps the other years near
flat. Candidate 4's extra profit is mostly more 2021 (+16.6 over the baseline) and a better 2022 (+9.0).

## Reading
* **Gate hysteresis** removed 5 trades and turned 2022 slightly positive. It also cost 5.6 USDT of 2021 by entering
  later, so it is a wash.
* **The looser volume filter** changed which trades were taken without changing how many. It improved slightly, but
  not by 0.1 PF.
* **AVAX and LINK** add trades but no edge: PF falls to 1.34, drawdown almost doubles, and without the best two months
  the result is a small loss. This agrees with the SOL study, where the large non-meme coins did not help either.
* **The two stage exit** improves the losers and the win rate (42% against 39%), but it gives away more on the big
  winners than it saves. That is what V4's profile predicts: its profit comes from a few long trailing-stop runs.
* **2h candles** show the strongest result: more trades, the best profit, double the profit without the best two
  months, and the best 2022.
  * Its drawdown is a hair worse on the pre-registered measure.
  * Its EMA, volume mean and cooldown cover half the hours of V4's, so it is more than a pure change of timeframe.
  * It is not tested further here; it remains untested on window B.

## Verdict
**No candidate passes. Nothing is proposed as MemeSleeveV5. V4 continues its dry run unchanged.**

**For the December cycle (Abdullah's call, to be pre-registered before any test):**
* Candidate 4 is the only one worth carrying forward.
* Decide before testing which drawdown measure the bar uses and whether it allows a tolerance. The two measures
  disagree on this candidate.
* Consider whether the EMA, volume mean and cooldown should also be doubled, so that 2h covers the same hours as 4h.
* Its window B result has not been seen, so B is still a valid confirmation window for it.
