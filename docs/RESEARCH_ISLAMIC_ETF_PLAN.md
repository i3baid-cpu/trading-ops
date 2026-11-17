# Research plan: a Shariah compliant S&P 500 fund in the Alpaca TrendFilter bot

Asked for by Abdullah on 2026-11-17: "lets add the islamic spy and back test it so we can add it if it beats the spy".
Fixed before any price was downloaded or any test was run. Research only: nothing on the running Lumibot container,
its config or its paper account changes because of this file.

## Question
Under the bot's own rule, did SPUS beat SPY, and did it do so in more than one stretch of time?

## Instruments
* Candidate, one only: **SPUS** (SP Funds S&P 500 Sharia Industry Exclusions ETF, US listed, first traded December 2019).
* Benchmark: **SPY**. Context only, not candidates: QQQ (already in the bot) and HLAL (another US Shariah fund).
* Daily closes and dividend adjusted closes from Yahoo's public chart endpoint, the source used in `scripts/grid_stress.py`.

## Rule tested, unchanged from the bot
`fixes/alpaca/strategies/trend_filter.py` with `config_v2.json`: on the first session of each month, from the last
completed close, buy if not held and close > SMA200 x 1.01; sell if held and close < SMA200 x 0.99; otherwise keep the
state. Cash earns nothing. No parameter is changed or tried.

## Window
From the first monthly check on which SPUS has 200 completed closes (about October 2020) to the last completed
session at run time. Every symbol starts flat on that same day. Two halves split at the midpoint date.
This is one window of about six years chosen by the fund's age, not by its results. It contains one bear market
(2022) and no 2008 or 2020 style crash.

## Bar: what "beats SPY" means here
All three, under the rule, on dividend adjusted prices:
1. SPUS total return is higher than SPY's over the whole window.
2. SPUS total return is higher than SPY's in **each** half.
3. SPUS maximum drawdown is not more than 3 percentage points worse than SPY's over the whole window.

Reported but not used to pass or fail: buy and hold figures, QQQ and HLAL under the same rule, time in the market,
number of switches, daily return correlation of SPUS with SPY and with QQQ, and the funds' expense ratios.

## What a pass would and would not mean
* A pass makes SPUS eligible to be **proposed** as a third symbol in the paper bot. It still needs Abdullah's written
  approval, a root change to the Lumibot config, and a check that Alpaca offers SPUS as a fractional share.
* It would not be evidence of an edge. SPUS is the S&P 500 without banks and other excluded industries, which leaves
  it heavier in technology. Over 2020 to 2026 that tilt was rewarded. The expected finding is that SPUS behaves like
  a blend of SPY and QQQ, and the bot already holds QQQ.
* If the reason to hold it is Shariah compliance, that is Abdullah's decision and does not depend on this bar. The
  numbers then show what the choice has cost or earned against SPY, nothing more.

## Command and output
```
python3 scripts/tests/test_etf_compare.py
python3 scripts/etf_compare.py --out results/research_islamic_etf.md
```
The script writes `results/research_islamic_etf.md` with the command, the data range, every table and the pass or
fail line by line. No rerun with different settings after the result is seen.
