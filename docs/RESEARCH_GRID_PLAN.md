# Research plan: spot grid bot as a capital deployment

Agreed with Abdullah on 2026-11-14. Fixed before any test is run; do not add variants after seeing results.
Research only: nothing on the live containers changes. Purpose: decide whether a spot grid on BTC or ETH is a
sound place for new capital (he has a $600 a year target; at a realistic 10 to 20% that means $3,000 to $6,000
deployed, so the study reports returns in percent and in dollars on $3,000).

## Question
Does a spot grid, with a range rule and a range break rule fixed in advance, earn a positive return after fees AND
after marking the leftover inventory to market, on data nobody chose, with a drawdown a $3,000 account can live
with? "No" is a valid answer and must be reported plainly. Grids show realised profit while hiding inventory
losses; this study counts both, always.

## Instruments
BTC/USDT and ETH/USDT only. Meme coins trend too violently for grids; they are V4's job. 1h candles from Binance's
public market data (no keys), same source as `scripts/v3_gate_check.py`.

## Windows
* **A, unseen: 2020-08-15 to 2023-10-30** (2021 bull run, 2022 crash, the 2023 range). Choose on A only.
* **B, seen: 2023-10-30 to 2026-10-30.** Run the chosen variant once on B to confirm.
* Download from 2020-01-01 so the 200 day average is warm at the start of A.

## Mechanics (the simulator, `scripts/grid_backtest.py`)
Arithmetic spot grid, N levels between a lower and an upper bound, equal USDT per level. At grid start the bot holds
coins for every level above price and cash for every level below (so it can sell up and buy down immediately).
Each hour, every level crossed by the candle's low triggers a buy and every level crossed by the high triggers a
sell of the lot bought one level below. Fee 0.1% per side (Binance spot without BNB discount). Equity = cash +
inventory at the candle close. Returns are on total capital, including inventory, never "grid profit" alone.

## Range rules (R) and break rules (K), fixed
* R1: last 90 days high and low, recentred on the first hour of each month.
* R2: 200 day SMA ±20%, recentred only when price closes outside the band for 24 hours.
* R3: static range set once at window start (shows what a set and forget grid does; expected to fail).
* K1: hold. Outside the range the grid pauses with whatever inventory it holds and resumes when price re-enters.
* K2: stop and restart. Close all inventory at 10% below the lower bound, stay in cash until price has closed
  above the 200 day SMA for 5 days, then restart the grid with the current range rule.
* K3: recentre at once. When price leaves the range, sell or buy to the new grid's starting inventory immediately.

## Candidates, at most 6, fixed here
1. BTC, R1, N=20, K1
2. BTC, R2, N=20, K2
3. ETH, R1, N=20, K1
4. BTC, R1, N=40, K2
5. BTC, R2, N=20, K3
6. ETH, R2, N=20, K2
Also run, for context on both windows: holding BTC, holding ETH, holding USDT (0%), holding SPY (daily closes via
yfinance, total return not available offline so price return), and V4's result if available. Stocks are not grid
candidates: an index moves a third to a fifth as much as BTC, so a grid earns proportionally less, and overnight gaps
jump across levels; the index line is there because for a steady dollar target an index position is the benchmark
any grid must justify itself against.

## Stress test on the chosen variant
Fee 0.2% per side; N ±50%; range width ±25%; results per calendar year; worst 90 day stretch; what the equity looked
like at the 2022 low (the inventory question).

## Bar to deploy capital
All of: positive total return in BOTH windows after fees and inventory; annualised return at least 8% in window A;
maximum drawdown of equity under 25%; no single quarter contributing more than half of the profit; and it must beat
holding USDT by more than it loses to holding the coin in bull years in a way Abdullah accepts in writing (a grid
will trail a bull market; the question is by how much).

## Output
* `results/research_grid.md`: every command, data range, the 6 variant table on A, the chosen one on B, stress
  table, per year table, verdict, and the dollar figures on $3,000.
* If it passes: a deployment note comparing Binance's built in spot grid (no code to maintain, parameters only) with
  a Freqtrade implementation, and a one month dry run before any capital. Capital decision stays Abdullah's.
