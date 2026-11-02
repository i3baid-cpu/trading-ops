# Research plan: V3 on SOL and a possible MemeSleeveV4

Agreed with Abdullah on 2026-11-02. Fixed before any test is run; do not add variants after seeing results.
Research only: the live freqtrade container, `config.json` and `MemeSleeveV3.py` stay unchanged.

## Question
Does adding SOL (or other large coins) to V3, or a small pre-declared change to V3, give a strategy that holds up on
data nobody has looked at? "Nothing beats V3" and "SOL does not help" are valid answers and must be reported plainly.

## Coins
* Current: DOGE, PEPE, SHIB, FLOKI /USDT.
* Added: SOL/USDT (the question), ETH/USDT and BTC/USDT (comparison: is SOL special or just a large coin).
* Gate input: BTC/USDT 1d, as in V3.

## Windows
* **A, unseen: 2020-08-15 to 2023-10-30.** Never used for any V1 to V3 decision. Includes the 2021 bull run and the
  2022 crash. SOL, DOGE, SHIB, ETH, BTC only; PEPE and FLOKI were not listed on Binance yet.
* **B, seen: 2023-10-30 to 2026-10-30.** V3 was designed on it. Used only to confirm, never to choose.
* Warm-up: download from 2020-01-01 so the BTC EMA100 and startup candles are warm at the start of A
  (SOL data starts at its Binance listing, 2020-08-11).

## Phases
1. **Honest test.** V3 unchanged on window A (SOL, DOGE, SHIB, ETH, BTC, each pair alone and as a basket) and on
   window B for SOL, ETH, BTC. No changes allowed. Tells whether V3 works outside the data it was built on.
2. **Candidates, at most 6, fixed here:**
   1. V3 on memes + SOL (the question as asked).
   2. V3 on SOL, ETH, BTC only.
   3. V3 on memes + SOL + ETH.
   4. V3 with a trailing stop for less jumpy coins: trail 6% after +12% (SOL, ETH, BTC universe).
   5. Variant 1 with 3 open trades instead of 2.
   6. Variant 1 with `startup_candle_count` 1000 (the margin noted in `freqtrade_v3.md`).
   Choose on window A only; run the chosen one once on window B. Report every variant, not only the winner.
3. **Stress test** on the chosen variant: fee 0.2% per side, `--timeframe-detail 15m`, `lookahead-analysis`,
   neighbouring parameters (±25% on the EMA lengths, breakout length and trailing settings), results per year.
   A winner that only works with exact settings is rejected.
4. **Verdict** against V3 and against holding the same coins. Bar to replace V3: profit in both windows, profit
   factor above 1.2, and no dependence on 1 to 2 months (profit without the best two months still positive).

## Commands
Same form as `freqtrade_v3.md`: `docker run --rm -v /root/freqtrade/user_data:/freqtrade/user_data
freqtradeorg/freqtrade:stable ... --config /freqtrade/user_data/backtest_config.json`, fee 0.1% unless stated,
`--enable-protections`, `--breakdown month`. Variants that change the coin list pass `--pairs`; variants that change
code are new research files (`MemeSleeveV4a.py` ...) under `user_data/strategies/`, never edits to V3.
Downloading SOL, ETH, BTC 4h data into `user_data/data` does not affect the live bot (it only trades its whitelist).

## Output
* `results/research_v4_sol.md`: every command, data range, variant table, verdict.
* If a variant passes: `MemeSleeveV4.py` as a new file. The live bot keeps V3 until at least 4 weekly reports exist
  and Abdullah approves a swap; adding SOL to the live whitelist is a root change to `config.json`, his decision.
* Scale stays the same: 25 USDT stakes, so even a good result is a few dollars a month.
