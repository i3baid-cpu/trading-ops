# Research cycle 2026-12: three locked V4 hypotheses (PRE-REGISTERED; NOT TESTED)

Pre-registered on 2026-11-14 from a source review, before any December candidate implementation or backtest. Owner approval remains required for promotion. This file is a specification for the VPS agent, **not permission to change running services**.

Sources: `docs/RESEARCH_PROTOCOL.md`, `docs/RESEARCH_CYCLE_2026-11.md`, `results/research_2026-11.md`, `results/research_v4_sol.md`, and `fixes/freqtrade/MemeSleeveV4.py`.

## Disclosure: windows are no longer truly unseen

Window A (2020-08-15 to 2023-10-30) was used to select V4 in November and to reject five research candidates on 2026-11-14. It is a **reused historical discovery benchmark**, not untouched out-of-sample evidence for December. Window B overlaps data used to design V3 and validate V4; likewise it is not a pristine holdout. The 2h idea below follows a previously observed near miss. Report this limitation next to any result. Do not claim a December backtest establishes an unseen edge. Only subsequent untouched forward dry-run data can supply genuinely prospective evidence.

## Fair contest and fixed test contract

- Current baseline: `MemeSleeveV4` unchanged. No modifications to V4, the live or dry-run containers, root config, balances, or dry-run database.
- Same runs for Abdullah's ideas and the three ideas below: same fixed windows, same market data snapshot, same Docker image/digest, same secrets-free backtest config, same fees, same 1,000 USDT wallet and 25 USDT fixed stake, same 3 open slots, same protections, and same comparison and stress methodology.
- Window A, inclusive start/exclusive end: `20200815-20231030`; eligible pairs: `DOGE/USDT SHIB/USDT SOL/USDT` (the original V4 A convention). No PEPE or FLOKI inserted into A post hoc.
- Window B, inclusive start/exclusive end: `20231030-20261201`; eligible pairs: `DOGE/USDT PEPE/USDT SHIB/USDT FLOKI/USDT SOL/USDT`. Do not run B until the first day of December after the end boundary has passed. This locks the protocol's previously open-ended "to now" endpoint for a fair comparison.
- BTC/USDT 1d is the unchanged informative market gate for all candidates. Download warm-up data in advance; never silently truncate the window for a candidate. A later-listed coin can trade only after its required warm-up; disclose effective starts.
- Use Freqtrade 2026.9 as in the November report, but **pin the complete immutable image digest before the first December run** (do not assume the mutable `stable` tag is unchanged). Record the git commit, sanitized configuration checksum, candle-file checksums, software version, and exact commands. All candidates are evaluated with the identical pinned image and data snapshot.
- Common flags: `--config /freqtrade/user_data/backtest_config.json --fee 0.001 --breakdown month --enable-protections --export none --max-open-trades 3`, plus the pre-specified `--strategy`, `--timeframe`, `--timerange`, and `--pairs`.
- **Reproduction gate before candidates:** independently rerun unchanged V4 on A, using DOGE/SHIB/SOL 4h. Expected from 2026-11-02 and 2026-11-14 reports: **140 trades, +79.36 USDT (raw report +79.365), PF 1.64**. Require trade count exactly 140 and profit within 0.02 USDT, with matching fee, fills, and per-year totals. If mismatched, STOP: archive logs and diagnose version/data/config differences; do not run or rank candidates.
- Do not select, add, remove, or tune candidates after seeing December results; do not test combinations. If December is run from a different commit or after changing protocol rules, record that as a new, separate protocol version before testing.

## Locked candidate list — at most three

Each is a separate, research-only new strategy file. Change nothing beyond the exact stated difference(s); do not modify an existing numbered strategy. For each, the hypotheses below are **prospective mechanisms**, not claims of confirmed performance on A.

1. **DEC-01 / `MemeSleeveV4e` — 2h, with equivalent lookback *time* to V4.** Use 2h candles; EMA **100** bars (200 hours), prior-high breakout **40** bars (80 hours; use `.shift(1)`), rolling volume mean **40** bars (80 hours), CooldownPeriod **12** candles (24 hours), startup **1,400** candles. BTC daily EMA100, volume threshold 1.0× its 40-bar mean, fixed stake, stoploss −15%, trailing +10% after +20%, ROI rule and all other logic remain V4's. **Why it might generalize:** react to trend changes every two hours while retaining the same trend, breakout, volume and cooldown horizons as 4h V4; this is a cleaner test than November's 2h variant, which inadvertently halved those horizons. **Disclosure:** related to November candidate V4c (PF 1.80, DD 2.61% on A); its design is therefore NOT independent of A.
2. **DEC-02 / `MemeSleeveV4f` — volatility-sized breakout confirmation.** Stay on V4 4h. Compute ATR(14) with TA-Lib on each pair's *completed* 4h candles. In addition to every original entry condition, require `close > hh20 + 0.25 * ATR14`, where `hh20 = high.rolling(20).max().shift(1)`. Exit logic, BTC gate, volume rule, cooldown and stops are unchanged. **Why it might generalize:** rejects tiny nominal breaches of the prior high in high-volatility conditions, potentially reducing false breakouts and execution-sensitive trades across bull, crash, and range regimes. The 0.25 ATR threshold is locked as a mechanism test, not chosen from a backtest.
3. **DEC-03 / `MemeSleeveV4g` — rising trend requirement at entry.** Stay on V4 4h. In addition to every original entry condition, require `ema50 > ema50.shift(8)` (EMA50 rising over 8 completed 4h candles = 32 hours). Exit logic and all other parameters unchanged. **Why it might generalize:** breakout systems can trigger while their intermediate trend is flattening; requiring a rising EMA may exclude choppy late breakouts while preserving genuine sustained moves across multiple regimes. The 8-bar lag is fixed up front.

## Binding acceptance bar and ranking: identical for all participants

**Do not relax the November bar after seeing its 0.06 percentage-point near miss.** Keep `docs/RESEARCH_PROTOCOL.md` section 5 as the *binding* December bar for both Abdullah's candidates and DEC-01..03:

1. On window A, profit factor at least **baseline A PF + 0.10** (against 1.64 baseline this is 1.74); total profit positive.
2. On both windows, positive net profit, profit factor strictly above 1.2.
3. On both windows, maximum drawdown **no worse than the same-window V4 baseline**. Use Freqtrade's **account-underwater** maximum-drawdown metric (the November protocol's operational interpretation), never switch after the result to the balance-based metric. No tolerance.
4. On both windows, profit remains positive after subtracting the best **two calendar months** from net monthly profit.

Run all candidates and baseline on A. Select the single qualifying A winner by highest A PF, then A profit excluding best two months, then lowest A account-underwater drawdown. Run **only that winner** once on B, alongside V4 baseline on B. If none qualifies, stop, document all losing candidates, and keep V4 unchanged. Under no circumstances cherry-pick the variant after viewing B.

**Report additional diagnostics but DO NOT use them as unregistered replacement gates:** full-wallet vs 75-USDT maximum deployed-capital returns, position-adjusted drawdown, exposure/occupancy, dollars per year, turnover and fee burden, per-asset and per-year results, concentration, limit-fill sensitivity, gap/slippage sensitivity, and sample size. The tiny maximum wallet drawdown may hide meaningful risk relative to the maximum 75 USDT committed.

## Winner stress and research outputs

Only a candidate passing the binding bar on A and B qualifies for the pre-registered winner stress: fee **0.002** per side, 15m detail (on both 4h and 2h candidates), `lookahead-analysis`, `recursive-analysis`, and the same single-parameter ±25% neighbor methodology as the protocol. DEC-01 time-length integer neighbors: ±25% of 100/40/40/12 as feasible, disclosed exact rounding; DEC-02 ATR threshold 0.1875 and 0.3125; DEC-03 slope lag 6 and 10 bars. Apply unchanged parameters to both windows and report all results. Stress failure means no promotion; do not re-tune or pick the best neighbor.

Commit and publish `results/research_2026-12.md` with full commands, original/candidate data hashes, all A results including losers, B confirmation if eligible, stress tables if eligible, observed vs hypothesized effects, accounting and execution caveats, and a clear pass/fail. Store logs and sanitized metadata only: **no credentials, API keys, real account data, or secret configuration**.

A passing historical research candidate earns consideration for a new forward *dry run* only after Abdullah's explicit written approval and the current V4 weekly-review condition. This document authorizes **no backtests in this session and no deployment**.
