# Research cycle 2026-11: five pre-registered improvements to V4

Pre-registered 2026-11-14 at Abdullah's request. Baseline: MemeSleeveV4 (V3's rules, DOGE PEPE SHIB FLOKI SOL,
3 slots), figures in `results/research_v4_sol.md` (A: 140 trades, +79.36 USDT, PF 1.64; B: 253 trades, +82.64 USDT,
PF 1.38). Each candidate is V4 with exactly one change; combinations are not tested this cycle.

## Candidates (fixed)
1. **Gate hysteresis.** BTC gate opens at close > EMA100 × 1.01 and shuts at close < EMA100 × 0.99 (V4: a single
   line, which flicked open on 4 Nov and shut on 5 Nov). File `MemeSleeveV4a.py`.
2. **Volume filter 0.8×.** Entry volume condition relaxed from above the 20 bar mean to above 0.8× the mean
   (V4 may be missing breakouts on ordinary volume). `MemeSleeveV4b.py`.
3. **Wider universe.** V4 unchanged on DOGE PEPE SHIB FLOKI SOL plus AVAX and LINK (two more large coins; the SOL
   study found SOL helped and ETH/BTC did not). Config only, `--pairs`.
4. **2h timeframe.** V4's rules on 2h candles with the breakout length doubled to 40 bars and startup candles
   doubled, so the lookback covers the same hours. `MemeSleeveV4c.py`.
5. **Two stage exit.** Take half the position at +10% (custom_exit), let the rest run with V4's trailing stop.
   `MemeSleeveV4d.py`.

## Windows and data
A: 2020-08-15 to 2023-10-30 (PEPE and FLOKI not listed; AVAX from 2020-09-22, LINK available). B: 2023-10-30 to
2026-11-14. Download from 2020-01-01. 4h and 1d (and 2h for candidate 4) from Binance via the backtest config.

## Bar
As in docs/RESEARCH_PROTOCOL.md section 5, against the V4 baseline on the same windows and pairs. The stress test
runs on the single best candidate by profit factor on window A among those that pass.

## Output
`results/research_2026-11.md`. If a candidate passes, it is proposed as MemeSleeveV5 for Abdullah's decision; it
would start its own forward test after the V4 review on 1 December unless V4 is losing against its study by then.
