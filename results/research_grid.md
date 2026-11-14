# Research: spot grid bot on BTC or ETH as a capital deployment

Run date: 2026-11-14, as claude-ops. Plan: `docs/RESEARCH_GRID_PLAN.md`, fixed before any test. Research only: nothing
was deployed and no container, config or strategy file was touched. All figures are on $3,000 of starting capital,
fee 0.1% per side unless stated, equity = cash + coins at the hourly close (inventory always marked to market).

## Short answer
* **No candidate passes the bar. Do not deploy a grid.** On the unseen window A, none of the six variants meets
  the bar. The best of them, BTC, 90 day range, 40 levels, stop and restart (variant 4), made +8.8% a year but had a
  29.6% drawdown (limit 25%), and one quarter (2021 Q3) supplied all of its net profit (limit: half).
* **It is fragile.** A 25% narrower range turns +31% into −11% on A. Fees of 0.2% cut it to +5.3% a year. Half the
  levels lands it at 7.9%, under the 8% line.
* **It loses in both kinds of year.** In 2022 it lost 18.8% (−$805) before its stop put it in cash, where holding USDT
  lost nothing. In bull years it trails holding BTC by 26 to 136 points.
* **An index fund does the same job with no bot.** SPY over window A: +8.3% a year total return with a 24.5% drawdown
  (the grid: 8.8%, 29.6%). Over window B: SPY +24.3% a year against the grid's +10.8%, with about the same drawdown (18.8%
  against 19.4%).
* **Dollars:** about $260 to $320 a year on $3,000. The $600 a year target would need roughly $5,600 to $6,800 in the
  grid, and a drawdown of the size seen here would be about $1,650 to $2,000 on that amount.

## Commands
```
python3 scripts/tests/test_grid.py                                   # accounting tests: 4 passed
python3 scripts/grid_backtest.py --all --out-dir results/grid        # 6 candidates x windows A and B, 1m49s
python3 scripts/grid_stress.py --pair BTCUSDT --range R1 --levels 40 --break K2 \
    --out results/grid/stress_BTCUSDT_R1_40_K2.json                  # chosen variant: A, B, stress, context lines
```
Raw results: `results/grid/*.json` (one file per candidate and window, `summary.json`, the stress file). Candles are
cached in `data/klines/` (git ignored).

`scripts/grid_stress.py` is new in this commit. It loads `grid_backtest.py` unchanged and adds only two lines that
return the hourly equity and inventory curve, which the per year, worst 90 days and 2022 low figures need. It scales
the range around its midpoint for the width stress. SPY comes from Yahoo's public chart endpoint (daily close and
adjusted close), because yfinance is not installed on the host. That makes total return available after all, so both
price and total return are shown.

## Data
* Binance spot 1h klines, public API, no keys, downloaded 2026-11-14.
  * BTCUSDT and ETHUSDT 2020-01-01 00:00 to 2023-10-30 00:00 UTC: 33,521 candles each.
  * BTCUSDT and ETHUSDT 2023-01-01 00:00 to 2026-10-30 00:00 UTC: 33,552 candles each.
  * The earlier start in each file warms up the 90 day range and the 200 day SMA before the window begins.
* **Window A (unseen, used for the choice):** 2020-08-15 to 2023-10-30.
* **Window B (seen, confirmation):** 2023-10-30 to 2026-10-30.
* SPY daily: A 2020-08-17 to 2023-10-30, B 2023-10-30 to 2026-10-29.

## Simulator caveats, checked before choosing
Reading `scripts/grid_backtest.py` turned up four problems. It was left unchanged (changing it needs Abdullah's
approval), so every number in this report comes from the committed code. To measure the first three problems, all 12
runs were repeated in a scratch copy with them fixed:
1. **On a recentre (R1 monthly, R2 and K3), the new grid is funded with the equity from before the old inventory is
   sold,** so the fee for that sale is never charged. Fixing it moves results by 0.1 to 1.6 points over a whole
   window: variant 4 goes from +31.1% to +30.6% on A and from +36.1% to +35.5% on B. It does not move any variant
   across a bar line.
2. **On R1 month changes with no restart, realised grid profit is counted twice.** This affects the "realised" column
   only, not equity: variant 4 on A shows $3,564 where the true figure is $3,000. Read the realised and inventory
   columns below as overstated by up to about $960.
3. **K3 is never applied when the range rule is R2** (`brk == "K3" and rule != "R2"`). Variant 5 therefore ran as R2
   with R2's own 24 hour recentre. A literal K3 on R2 recentres every hour to an SMA ±20% band the price is already
   outside, and fees take it to −100% in both windows. That combination is incoherent, not a real option.
4. **Fill assumptions run both ways.** Within one candle, buys are filled before sells, so a buy and a sell one level
   up can both fill in the same hour (optimistic). The level just below the previous candle's high is never bought
   (pessimistic). These were not measured.

## The six variants on window A (choice made here only)

| # | Variant | Total | Annualised | Max DD | Best quarter share | Realised (gross) | Inventory, net | Fees | Final on $3,000 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | BTC, R1, N=20, K1 | −1.7% | −0.6% | 50.5% | n/a (loss) | +$3,143 | −$2,963 | $231 | $2,948 |
| 2 | BTC, R2, N=20, K2 | +11.7% | +3.5% | **14.3%** | 1.37 | +$1,553 | −$1,045 | $156 | $3,352 |
| 3 | ETH, R1, N=20, K1 | +72.0% | **+18.4%** | 61.5% | 0.70 | +$6,972 | −$4,475 | $339 | $5,159 |
| 4 | BTC, R1, N=40, K2 | +31.1% | **+8.8%** | 29.6% | 1.06 | +$3,564 | −$2,068 | $563 | $3,932 |
| 5 | BTC, R2, N=20, K3 (ran as R2, see caveat 3) | −9.6% | −3.1% | 69.4% | n/a (loss) | +$4,226 | −$3,621 | $893 | $2,712 |
| 6 | ETH, R2, N=20, K2 | +3.7% | +1.1% | **21.2%** | 3.03 | +$1,051 | −$828 | $114 | $3,110 |

Over the same window, holding BTC returned +189.2% and holding ETH +308.9%. "Best quarter share" is the best
quarter's profit divided by the window's net profit; the bar requires 0.5 or less. "Inventory, net" is what is left
after realised profit and fees: coins bought high and still held or sold lower, plus losses on recentres and stops.
Bold marks a number that clears its bar line.

**Selection rule (fixed before window B was looked at):** no variant passes all four of the bar's window A tests
(positive, at least 8% a year, drawdown under 25%, best quarter at most half). Rank by how many of the four each
passes, then break ties by the smallest total shortfall, measured relative to each line.
* Variants 2, 3, 4 and 6 each pass two tests. Variants 1 and 5 pass none.
* Total shortfalls:
  * variant 4: drawdown 0.18 over, quarter 1.12 over, total 1.30.
  * variant 3: drawdown 1.46 over, quarter 0.40 over, total 1.86.
  * variant 2: return 0.56 under, quarter 1.74 over, total 2.30.
  * variant 6: total 5.9.
* **Chosen: variant 4 (BTC, R1, N=40, K2).** Variant 3 has the highest return, but its equity fell 61.5% from its
  peak at one point.

## The chosen variant on window B, run once

| Window | Total | Annualised | Max DD | Best quarter share | Final on $3,000 | Hold BTC |
|---|---|---|---|---|---|---|
| A | +31.1% | +8.8% | 29.6% | 1.06 (2021 Q3 +$991 of $932 net) | $3,932 | +189.2% |
| B | +36.1% | +10.8% | 19.4% | 0.56 (2025 Q2 +$612 of $1,084 net) | $4,084 | +124.2% |

`--all` also ran the other five variants on B; their rows are in `results/grid/summary.json` and the run log. They
played no part in the choice.

## Against the bar

| Test | Result | Pass |
|---|---|---|
| Positive total return in both windows, after fees and inventory | A +31.1%, B +36.1% | yes |
| Annualised at least 8% on A | 8.8% (7.9% with 20 levels, 5.3% at 0.2% fee) | yes, barely |
| Max drawdown under 25% | A 29.6% ($4,715 on 2021-12-01 to $3,320 on 2023-03-10), B 19.4% | **no** |
| No quarter more than half the profit | A 1.06, B 0.56 | **no** |
| Beats USDT by more than it trails the coin in bull years | 2022: −18.8% against USDT's 0%. Bull years: −26 to −136 points against BTC | **no** (Abdullah's written acceptance not asked, since tests 3 and 4 already fail) |

## Stress test (chosen variant, window A)

| Run | Total | Annualised | Max DD | Worst 90 days | Equity at the 2022 low (2022-11-21) | Final on $3,000 |
|---|---|---|---|---|---|---|
| As chosen | +31.1% | +8.8% | 29.6% | −25.8% (2021-12-01 to 2022-03-01) | $3,474, all cash | $3,932 |
| Fee 0.2% per side | +17.9% | +5.3% | 30.5% | −26.4% | $3,247, all cash | $3,537 |
| Levels −50% (N=20) | +27.6% | +7.9% | 25.5% | −23.0% | $3,454, all cash | $3,828 |
| Levels +50% (N=60) | +24.8% | +7.2% | 29.8% | −25.9% | $3,355, all cash | $3,744 |
| Range width ×0.75 | **−10.6%** | −3.4% | 34.3% | −22.2% (2021-05-12 to 2021-08-10) | $2,446, all cash | $2,683 |
| Range width ×1.25 | +30.8% | +8.7% | 31.2% | −29.2% (2021-11-15 to 2022-02-13) | $3,393, all cash | $3,923 |
| Chosen, window B | +36.1% | +10.8% | 19.4% | −16.7% (2025-10-10 to 2026-01-08) | n/a | $4,084 |

**The inventory question, at the 2022 low:** BTC closed at 15,650 on 2022-11-21. The grid held no coins then because
the K2 stop had fired on 2022-01-21. It sat in cash at about $3,474 until it restarted on 2023-01-17.
* The stop did its job: it avoided the rest of the 2022 crash.
* But the grid had already given back $805 in 2022 Q1. From its December 2021 peak of $4,715, equity was 26% down at the low.
* Holding BTC from the window start was still worth $3,940 at the same date.
* Window B behaved the same way: the stop fired in 2025 Q4 after a −$672 quarter, and the grid sat in cash from
  2025-11-17 to 2026-08-23.
* The grid also holds no coins for long stretches in rallies, because price runs above the range until the next
  monthly recentre. It held no coins in about half the hours of A and 45% of B. That is why it trails bull markets so
  far.

## Per calendar year

Percent change over the year, or the part of the year inside the window. Dollars are the grid's change on its own
running equity, which starts at $3,000.

| Year | Grid (variant 4) | Grid $ | Hold BTC | Hold ETH | Hold USDT | SPY price | SPY total |
|---|---|---|---|---|---|---|---|
| A 2020 (from 15 Aug) | +6.7% | +$202 | +142.7% | +67.9% | 0% | +10.6% | +11.6% |
| A 2021 | +33.6% | +$1,077 | +59.8% | +399.2% | 0% | +27.0% | +28.7% |
| A 2022 | −18.8% | −$805 | −64.2% | −67.5% | 0% | −19.5% | −18.2% |
| A 2023 (to 30 Oct) | +13.2% | +$459 | +108.3% | +49.9% | 0% | +8.7% | +9.9% |
| B 2023 (from 30 Oct) | +0.5% | +$15 | +22.7% | +27.2% | 0% | +14.4% | +14.8% |
| B 2024 | +26.1% | +$785 | +121.3% | +46.3% | 0% | +23.3% | +24.9% |
| B 2025 | +6.6% | +$251 | −6.3% | −11.0% | 0% | +16.4% | +17.7% |
| B 2026 (to 30 Oct) | +0.8% | +$32 | −11.9% | −25.2% | 0% | +12.8% | +13.7% |

## Holding lines (context, same windows, $3,000)

| Line | A total | A annualised | A max DD | B total | B annualised | B max DD |
|---|---|---|---|---|---|---|
| Grid, variant 4 | +31.1% ($3,932) | +8.8% | 29.6% | +36.1% ($4,084) | +10.8% | 19.4% |
| Hold BTC | +189.2% ($8,676) | +39.3% | 77.2% | +124.2% ($6,726) | +30.9% | 53.7% |
| Hold ETH | +308.9% ($12,267) | +55.2% | 81.3% | +23.9% ($3,717) | +7.4% | 69.2% |
| Hold USDT | 0% ($3,000) | 0% | 0% | 0% ($3,000) | 0% | 0% |
| Hold SPY, price return | +23.0% ($3,690) | +6.7% | 25.4% | +85.1% ($5,553) | +22.8% | 19.0% |
| Hold SPY, total return (adjusted close) | +29.1% ($3,873) | +8.3% | 24.5% | +92.0% ($5,760) | +24.3% | 18.8% |
| V4 (variant 5, `results/research_v4_sol.md`) | +79.36 USDT | about +106% on the 75 USDT in play | 2.55% of a 1,000 USDT wallet | +82.64 USDT | about +110% on capital in play | 2.38% |

V4's line is on a different capital basis: stakes of 25 USDT, at most 75 USDT in play. It cannot be scaled to $3,000
by multiplication, because it only trades when its gate opens.

## Dollar figures on $3,000 (chosen variant)
* **Window A** (3.2 years): +$932, about $264 a year at 8.8%.
  * Best year: 2021, +$1,077. Worst year: 2022, −$805.
  * Deepest fall: −$1,396, from $4,715 to $3,320. Lowest equity: $2,872.
* **Window B** (3 years): +$1,084, about $324 a year at 10.8%.
  * Worst quarter: 2025 Q4, −$672. Deepest fall: −$829.
* **Holding SPY instead:** +$873 on A and +$2,760 on B, with no bot, no exchange and no range rule to get wrong.
* **The $600 a year target** would need about $6,800 at A's rate or $5,600 at B's. A 29.6% drawdown on that amount is
  about $1,650 to $2,000, even if the rates held. The stress tests say they may not: a 25% narrower range made A a loss.

## Verdict
**Fails the bar. Do not put capital into a spot grid on BTC or ETH.**
* The best of the six pre-declared variants is positive in both windows and just clears 8% a year on A.
* It fails on drawdown (29.6% against 25%) and on concentration (one quarter supplied all the net profit on A).
* It lost money in the crash year, where cash lost nothing, and trailed holding BTC by a wide margin in every bull year.
* Its return depends on the range setting: 25% narrower turns +31% into −11%.
* An S&P 500 index position matched it on window A, with a smaller drawdown, and more than doubled its return on window B.
* The simulator problems listed above flatter the grid slightly, if anything; fixing them does not change this verdict.

As the plan says, a failed bar means no deployment note and no dry run. For a steady dollar target, the benchmark the
data supports is an index position. The capital decision remains Abdullah's.
