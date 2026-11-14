# Independent technical review of the 14 November audit findings

Reviewer: Claude (Fable 5.2), 2026-11-14. Subject: `docs/INDEPENDENT_AUDIT_FINDINGS_2026-11-14.md` at commit `c34433e`.
Nothing in V4, the live configuration, the containers or the existing research results was changed. No December
candidate was implemented or backtested. Proposed patches sit on the branch `proposal/fable-review-2026-11-14`
(commit `3f2d984`), unmerged, waiting for Abdullah's approval.

## Bottom line

* **V4: no lookahead, confirmed against the Freqtrade 2026.9 engine source.** The signal is computed on a closed 4h
  candle and the order is placed at the next open. The audit's execution concerns are real but apply to live trading,
  not to the integrity of the backtest. On the one axis that has been measured (15m detail), the 4h backtest was the
  cautious one.
* **Grid: all four known and all ten new findings are confirmed on the unchanged simulator.** Each one reproduces in a script that runs and
  passes. Two of the audit's ratings need correcting: G-N2 (negative cash) is real but worth 0.1% of capital, not a
  critical error; G-N3 is not a separate defect once G-N1 is fixed; and half of G-N9 (double counting) could not be
  reproduced. The grid numbers in `results/research_grid.md` should be treated as unreliable in size. The verdict
  "do not deploy a grid" still holds: the fixes whose direction is certain (intrabar drawdown, recentre fees) make
  the grid look worse, and the rest need a rerun to size.
* **Protocol: the audit's criticism is fair and its policy is right.** Window A is no longer unseen. The December bar
  must stay exactly as registered.
* **December pre-registration: implementable, causal, and the acceptance criteria are untouched.** Five points are
  undefined and must be settled in writing before the first run. One of them matters: nothing says what counts as
  failing the winner stress test.
* **Two things still need the VPS:** the V4 baseline reproduction (140 trades, +79.36 USDT, PF 1.64) and the size of
  the grid errors on real candles. This sandbox has no Freqtrade, no candle data and no route to Binance.

## What was checked and how to repeat it

| Source | Version checked |
|---|---|
| `fixes/freqtrade/MemeSleeveV4.py` | blob `74f137d`, the audit's snapshot |
| `scripts/grid_backtest.py` | blob `b78026a`, the audit's snapshot, called "version 1" below |
| Freqtrade engine | tag `2026.9`, commit `1f394ea`, read from github.com/freqtrade/freqtrade |
| `docs/RESEARCH_CYCLE_2026-12.md`, `docs/RESEARCH_PROTOCOL.md`, `results/research_*.md`, `results/grid/*.json`, `results/cycle_2026-11/backtests/*.log` | commit `c34433e` |

```
git fetch origin && git checkout proposal/fable-review-2026-11-14
python3 scripts/tests/repro_grid_v1_findings.py   # all 14 findings plus one extra, on the unchanged version 1; passes while the defects exist
python3 scripts/tests/test_grid_v2.py             # 13 tests of the proposed version 2
python3 scripts/tests/test_grid.py                # the 4 original tests, still passing
```
All three use synthetic hourly candles and need no network. Data range: none (synthetic). Results on 2026-11-14:
"All version 1 findings reproduced", "All version 2 grid tests passed", "All grid tests passed".

## Scoreboard

Verdict words: **Confirmed** (reproduced or read directly in source), **Disproved**, **Needs verification** (cannot be
settled without the VPS).

| ID | Verdict | Effect on the backtest numbers | Effect on live trading | Fix |
|---|---|---|---|---|
| V4-01 | Confirmed: no lookahead | none | none | none |
| V4-02 | Confirmed: causal, and the engine enforces it | none | none | none |
| V4-03 | Confirmed: daily gate is delayed correctly | none | Needs verification on one live day change | read only check on the VPS |
| V4-04 | Confirmed as a live risk | fills are idealised: always filled, at the open, no spread | missed or worse fills | measure in the dry run; no code change |
| V4-05 | Confirmed as a live risk | 4h stop model is the cautious one for the trailing stop | market stop checked by the bot, not resting on the exchange | decide `stoploss_on_exchange` before any go live |
| V4-06 | Confirmed (figures match the reports) | 4h is likely understated, not overstated, on this axis | none | exit reason comparison, VPS |
| V4-07 | Confirmed | drawdown of 2.55% of wallet is about 34% of the 75 USDT at work | same | report both; later protocol |
| G-K1 | Confirmed, with a caveat on what the right fee is | overstates equity a little at each recentre | n/a | v2 charges it, two modes |
| G-K2 | Confirmed, and fees are doubled too | reporting columns only | n/a | v2 single ledger |
| G-K3 | Confirmed | variant 5 did not run as specified | n/a | v2 applies K3 under R2 |
| G-K4 | Confirmed | optimistic by an unknown amount | n/a | v2 runs both intrabar orders |
| G-N1 | Confirmed, critical | optimistic; up to +14.8% from one candle in a synthetic case | n/a | v2 executes at the next open |
| G-N2 | Confirmed, rating too high | cash of minus 0.1% of capital; equity unaffected | n/a | v2 budgets fees |
| G-N3 | Confirmed as coded, not a separate defect | none beyond G-N1 | n/a | solved by G-N1 |
| G-N4 | Confirmed | drawdown understated, direction certain | n/a | v2 reports both |
| G-N5 | Confirmed, narrow | a stop is skipped only on the first hour of a month | n/a | v2 fixed priority |
| G-N6 | Confirmed | reporting columns only | n/a | v2 ledger |
| G-N7 | Confirmed | fee column only (equity already pays the stop fee) | n/a | v2 ledger |
| G-N8 | Confirmed | one false recentre after each re entry | n/a | v2 sets the month key |
| G-N9 | Half confirmed: missed fills yes, double counting no | pessimistic | n/a | v2 explicit path |
| G-N10 | Confirmed: plan and code disagree | definition, not arithmetic | n/a | v2 states the definition |
| D | Agree, with additions | n/a | n/a | later protocol only |
| F | Needs verification | n/a | n/a | run on the VPS |

## A. MemeSleeveV4

**V4-01, no future data in the indicators. Confirmed.** Lines 34 to 39 use `ta.EMA`, `rolling(20).max().shift(1)` and
`rolling(20).mean()`. All look backward. There is no negative shift, no `iloc[-1]`, no whole series statistic. V4
differs from V3 only in its class name and header comment (`diff fixes/freqtrade/MemeSleeveV3.py MemeSleeveV4.py`), so
the V3 lookahead analysis in `results/research_v4_sol.md` (0 biased signals in both windows) covers V4's code.

**V4-02, signal and fill timing. Confirmed, and the audit's open question is answered.** The audit asked to verify
that orders cannot fill inside the signal candle. The engine guarantees it: `freqtrade/optimize/backtesting.py` lines
554 to 563 shift every entry and exit signal forward by one candle ("To avoid using data from future, we use
entry/exit signals shifted from the previous candle"). A signal on the candle that closes at 12:00 trades at the 12:00
open of the next candle. Live, `process_only_new_candles = True` (line 21) does the same thing.

**V4-03, the BTC daily gate. Confirmed for the backtest.** `freqtrade/strategy/strategy_helper.py` lines 34 to 46 set
the merge date of a daily candle to its date plus one day minus one base candle. The BTC candle of 5 March is attached
to the 4h candle that opens at 20:00 on 5 March and closes at 00:00 on 6 March, the same instant the daily candle
closes. Nothing is seen early. Live: Freqtrade drops the unfinished candle for Binance by default
(`ohlcv_partial_candle`, `exchange.py` line 141 and `_drop_incomplete_candle`). **Needs verification** on the VPS for
one real day change: compare the gate value the bot logs after 00:00 UTC with `scripts/v3_gate_check.py`. Read only.

**V4-04, limit orders. Confirmed as a live risk; the backtest side is now exact rather than suspected.** In backtests
a limit entry is priced at the next candle's open unless the strategy defines `custom_entry_price` (lines 1039 to
1057; V4 defines none) and it is filled if that price lies inside the candle (lines 787 to 789), which the open always
does. So every backtest entry fills, in full, at the open, with no spread. Exit signals also fill at the next open
(`docs/backtesting.md` lines 561 to 563). The baseline log shows `unfilledtimeout` of 10 minutes, so live a limit that
is not reached within 10 minutes is cancelled and the trade is missed.
* Backtest impact: optimistic on fill rate and price by an unmeasured amount. `--fee 0.002` (in the V4 study: +69.93,
  PF 1.52 on A) is a rough stand in for 0.1% of slippage per side.
* Live impact: breakout entries are the case where a passive limit is least likely to fill. The four weekly dry run
  reports are the right evidence; so far there are zero V4 trades to compare.
* Fix: no strategy change. Add to the weekly audit a count of signals, orders placed, filled and timed out. The
  `entry_pricing` and `exit_pricing` blocks of `backtest_config.json` and the live config are not in the repository
  (correctly, the live one holds secrets), so that part **needs verification** by the VPS agent, values only.

**V4-05, stop and trailing stop. Confirmed as a live risk.** Backtest rules (`docs/backtesting.md` lines 571 to 578,
code lines 597 to 642): a stop fills exactly at the stop price even if the low was lower; if the candle opens beyond
the stop it fills at the open; for the trailing stop the high is assumed to come first, the stop is raised, and then
the low is tested against the raised stop.
* Backtest impact: the plain 15% stop is slightly optimistic (no slippage through the level). The trailing stop
  assumption is the pessimistic one on wide 4h candles.
* Live impact: with `stoploss_on_exchange: False` (line 24) the stop is not an order on Binance. The bot polls the
  price and sends a market order. If the bot or the VPS is down, there is no stop. Meme coin gaps will fill below 15%.
* Fix, for the go live discussion only, not now: `stoploss_on_exchange: True` with a limit ratio. That is a live
  configuration change and needs Abdullah's written approval under CLAUDE.md. Not proposed as a patch.

**V4-06, 4h against 15m detail. Confirmed; direction clarified.** The figures match `results/research_v4_sol.md`: A
+79.36 at 4h against +117.65 with `--timeframe-detail 15m`; B +82.64 against +97.58. The audit says this "does not
itself prove optimism at 4h". Agreed, and stronger: the engine's documented trailing assumption explains why 4h is
lower, and the V4 study says the same. On this axis the published 4h figures are the conservative ones. **Needs
verification** (VPS, existing data, V4 only): the exit reason table of the two runs side by side.

**V4-07, exposure. Confirmed.** 3 slots of 25 USDT is 75 USDT. A drawdown of 2.55% of a 1,000 USDT wallet is 25.5
USDT, which is 34% of the most that can be at work. +79.36 USDT over window A is about +106% on 75 USDT and +7.9% on
the wallet over 3.2 years. Both readings are true; the reports should always print both.

**Additional V4 findings from this review**
1. **`recursive-analysis` has never been run.** The protocol (section 4) and the December file require it. No file
   under `results/` contains its output. V3's first warm up bug (120 candles) was exactly this class of error.
   **Needs verification** on the VPS for V4 with `startup_candle_count` 700.
2. **The backtest configuration changed between studies and has no checksum.** The 2 November study says
   `backtest_config.json` has `max_open_trades` 2 and passed 3 on the command line. The 14 November baseline log shows
   no `--max-open-trades` flag and "Using max_open_trades: 3" from the config. The result is identical, so no harm
   done, but it shows the config is edited between runs. The December checksum rule covers it; apply it.
3. **Dashboard caption is wrong.** `dashboard/freqtrade_panel.py` line 120 says V4 "exits on two 4h closes below
   EMA50". The code exits on one (line 56). Patch 3 below.

## B and C. Grid simulator, version 1

Every line reference in the audit matches blob `b78026a`. Evidence lines below are the output of
`scripts/tests/repro_grid_v1_findings.py`. The simulator is a backtest only tool, so "live" impact is whether a real
grid would behave as the report says.

**G-N1, fills on the candle that created the orders. Confirmed, critical.** `run()` creates the grid at the close of
candle i (lines 144, 155, 162, 173, 183) and then line 175 trades candle i's own low and high.
* `Grid(90,110,4,1000,100,0.001)`: equity 999.50, then `step(90,110)`: 1049.11. The audit's figure reproduces exactly.
* Through the full `run()` pipeline: one candle that opens and closes at 100 with a 90 to 110 swing ends at 1049.11
  on 1,000.
* On the recentre path it is worse: a flat market with one wick to 130 on the recentre candle ends at **1147.78** on
  1,000. The new grid sells its starting inventory at 120 and 130 inside the candle that defined the range.
* Historical impact: optimistic, size unknown. It happens once per restart. `results/grid/summary.json` shows 23 to
  34 restarts for the R1 variants and 297 to 580 for the R2 variants, so the R2 rows are the most exposed. My
  expectation for the chosen variant (BTC R1 N=40 K2, 23 restarts on A) is a small effect, of the order of a point of
  its +31.1% or less, because an hourly BTC candle rarely spans more than one of 40 levels. That is reasoning, not a
  measurement.

**G-N2, negative cash. Confirmed; the audit's "critical" overstates it.** Lines 64 to 69 spend `capital / n` on each
of up to n lots and then take the fee. With price at or below the lower bound: cash is minus 1.00 on 1,000 and minus
3.00 on 3,000. It is always the fee rate times capital, 0.1%. Equity is still correct because the fee is deducted; the
account simply holds 0.1% more coins than it could afford. Impact on returns: negligible. It is still wrong for an
unlevered account and version 2 removes it.

**G-N3, range uses the current candle. Confirmed as coded, but not a separate defect.** `range_for(i)` returns
(70, 130) on a wick candle against (100, 100) one bar earlier. Using candle i's data at candle i's close is legitimate.
It only becomes lookahead because of G-N1. Once orders start at the next open, `kl[:i + 1]` is causal. Version 2 keeps
the slice and fixes the timing.

**G-N4, drawdown on closes only. Confirmed; direction certain.** A wick to 60 that closes back at 100 reports a
drawdown of 0.0%. The same book marked at 60 is 812.14, minus 18.7%. Every published grid drawdown is a lower bound.
The chosen variant already fails the 25% limit at 29.6% on closes.

**G-N5, recentre before stop. Confirmed, narrow.** A close at 78 against a stop level of 81 on the first hour of
October is recentred instead of stopped (2 restarts, final 948.69). The same close one hour earlier stops (1 restart,
final 889.11). It can only happen on the first hour of a month for R1, because on every other hour the stop is tested
with no recentre in front of it. Low frequency, but it changes a risk rule, so it must be fixed.

**G-N6 and G-N7, attribution. Confirmed.** After a K2 stop the account is all cash (889.11), yet the report shows
realized 0.0 and `inventory_mtm_at_end` of minus 110.39. Fees paid were 0.50 + 0.39; reported 0.5. These are column
errors. Final equity, return and drawdown are not affected by them, with one exception already listed as G-K1.

**G-N8, month key. Confirmed.** Grids were created on 19 July, 14 August (re entry) and again on 15 August: the stale
key from July makes the first midnight after re entry look like a new month. One false recentre per re entry, with
its fees, when the range has moved more than 2% in that day.

**G-N9, `last_idx`. Half confirmed.** After a candle whose high reaches the top of the range, the next downward cross
of 100 is not bought; with a high of 109.9 it is. That is a missed fill, pessimistic. I searched for the double
counting the audit suspected and could not produce it: a level is bought only when it is not held, and sold only when
it is. **Disproved** for double counting on the cases tried; the missed fill stands.

**G-N10, K1 "pause". Confirmed as a disagreement between plan and code.** A candle that closes below the range still
fills resting orders. Real resting limit orders behave like the code, not like the plan's word "pauses". Version 2
adopts the code's behaviour and says so. `docs/RESEARCH_GRID_PLAN.md` is left as it is.

**The four known issues**
* **G-K1. Confirmed, with a caveat.** The new grid is funded with 999.50 where the cash after the sale is 999.00.
  The caveat: the plan's K3 says "sell or buy to the new grid's starting inventory", which means trading only the
  difference. On that reading version 1 undercharges the sale and overcharges the rebuy (it pays the fee on the whole
  new inventory). The honest fee is somewhere between. Version 2 offers both: `net` (fee on the difference) and
  `gross` (sell all, rebuy all).
* **G-K2. Confirmed, and wider than reported.** At a month change without a restart the report shows realized 51.32
  and fees 3.05 where the grid's own books say 25.66 and 1.53. Fees are doubled as well as realized profit.
* **G-K3. Confirmed.** Line 171. A side note for the next reader: the VPS agent found that a literal K3 under R2 goes
  to minus 100% on fees. That follows from charging a full rebuy every hour. Under `net` charging a recentre that
  changes nothing costs nothing, so the combination is no longer self destroying. Whether it is sensible is another
  matter.
* **G-K4. Confirmed.** A candle with low 94.9 and high 100.1 buys at 95 and sells at 100 in the same hour (+13.16 on
  1,000 with 4 levels) whatever the real order was.

**Additional grid findings from this review**
1. A flat lookback (high equals low) raises `ZeroDivisionError` in `Grid._idx`. Synthetic data only; real candles
   never do this over 90 days.
2. Starting inventory is one lot short of the plan. The plan gives "coins for every level above price"; line 64
   skips the top level, so there is never a sell order at the first level above price. Kept unchanged in version 2
   so that differences stay limited to defects.
3. Under R2 the grid recentres every 24 hours for as long as price stays outside the band. That is where the 297 to
   580 restarts come from. It follows the plan's wording; it is expensive and worth knowing.
4. The K2 re entry counts the close of the 00:00 candle (price at 01:00), not the daily close. Kept unchanged.

**What this means for `results/research_grid.md`.** The file stays as it is; it is the record of what version 1 said.
Its numbers are not trustworthy in size. Its verdict, do not deploy, remains the prudent one: the chosen variant
already fails on drawdown (29.6% on closes against a 25% limit) and on quarter concentration, marking the same book
inside the hour can only raise that drawdown, and charging recentre fees can only lower the return. The other fixes
change which fills happen (G-N9 adds fills, G-N1 and G-K4 remove some), so their net effect is not known. Only a
rerun with version 2 settles it, published as a new file, never as an edit.

## D. Protocol critique

**I agree with the audit's reading and its policy.** Checked against `results/research_2026-11.md`: every figure in
the audit's November table matches (140 and 170 trades; +79.36 and +104.88; PF 1.64 and 1.80; 2.55% and 2.61%;
balance drawdown 2.81% and 2.62%; +24.57 and +54.23). The 0.06 point gap is 0.60 USDT on 1,000. One trivial mismatch
inside the repository: the V4 study prints 24.56 where the November report prints 24.57 for the same run.

Additions:
1. **Part of V4c's gain may be candle size, not signal.** Unchanged V4 gains +38.29 USDT on A just from 15m detail
   (79.36 to 117.65). V4c gained +25.52 by moving to 2h. A 2h backtest sees a finer price path for the trailing stop
   than a 4h one, so some of that gain is the same effect. This also applies to DEC-01. It is a caveat to print next
   to the result, not a new gate.
2. **With 140 trades, a profit factor step of 0.10 is inside the noise.** No trade list was exported
   (`--export none`), so I cannot put an interval on it here. A later protocol should export trades and bootstrap.
3. **The protocol text is out of date in one sentence.** Section 2 still calls window A "never used for design". The
   December file discloses this correctly; the protocol should be amended for cycles after December.

The audit's list of later measurements is sound. I would rank them: fill and slippage stress first (it is the gap
between this backtest and money), then profit per deployed dollar, then a minimum trade count. None of it applies to
December.

## F. Baseline reproduction

**Needs verification. Not done, and it cannot be done here.** The figures 140 trades, +79.365 USDT, PF 1.64, 2.55%
appear consistently in `results/research_v4_sol.md`, `results/research_2026-11.md` and
`results/cycle_2026-11/backtests/A_V4_baseline.log`, and the November run reproduced the 2 November run on the same
machine. That is one pipeline agreeing with itself. An independent reproduction needs Freqtrade, the candle files and
Docker, which exist only on the VPS. The audit's command is correct and matches the logged one. It stays the first
step of December, as registered.

## December pre-registration, reviewed separately

File: `docs/RESEARCH_CYCLE_2026-12.md`. **The four acceptance criteria, the ranking rule, the windows, the candidates
and the stress list are preserved exactly. I propose no change to any of them.** No candidate file was written and
nothing was run.

**Implementable and causal: yes for all three.**

| Candidate | Check | Result |
|---|---|---|
| DEC-01 `MemeSleeveV4e` | 2h, EMA 100, 40 bar high with `.shift(1)`, 40 bar volume mean, cooldown 12, startup 1,400 | All lengths are V4's hours times two. 1,400 candles of 2h is 116.7 days, the same warm up time as V4's 700 of 4h. 2h data for all pairs was downloaded on 14 November. Causal. |
| DEC-02 `MemeSleeveV4f` | `close > hh20 + 0.25 * ATR14` | ATR on the closed signal candle is known at its close. Causal. It makes V4's `close > hh20` redundant, which is harmless. Neighbours 0.1875 and 0.3125 are exactly 25% either side. |
| DEC-03 `MemeSleeveV4g` | `ema50 > ema50.shift(8)` | Positive shift, causal. Neighbours 6 and 10 are exactly 25% either side. |

DEC-01's neighbours need no rounding: 75 and 125, 30 and 50, 30 and 50, 9 and 15.

**Five points to settle in writing before the first run.** These are undefined terms, not changes to the bar. Each
has an obvious reading; the point is to choose it before results exist.

1. **What fails the winner stress.** The file says "stress failure means no promotion" and never defines failure.
   The protocol says only "a result that needs exact settings fails". The V4 study's own summary was "all runs stay
   profitable with PF at or above 1.2 and positive without the best two months". Abdullah should write down which
   rule applies. This is the one gap that could be argued either way after the fact.
2. **Precision of the comparisons.** November compared Freqtrade's printed values: profit factor and drawdown to two
   decimals. Say so. Otherwise a candidate at 1.7449 against a line of 1.74 is a dispute.
3. **One data snapshot.** Window B ends on 1 December, so candles must be downloaded after that. A download appends
   to the same files, which changes their checksums. Either run the whole cycle (gate, A, B) after one download on or
   after 1 December, or checksum per time range. The first is simpler.
4. **No runner up.** If the A winner fails on B the cycle ends. The file implies it ("only that winner"); one
   sentence would remove doubt.
5. **Window B baseline is a new number.** The published B figures (253 trades, +82.64, PF 1.38) end on 30 October.
   The December B window ends on 1 December, so there is no reproduction gate for B and the baseline will differ a
   little. Expected, worth stating.

**Two caveats to print beside any December result (diagnostics, not gates; the file already allows diagnostics).**
* DEC-01 runs on 2h candles and the baseline on 4h. See D.1: part of any gain is backtest resolution. The registered
  15m detail stress on the winner will show how much.
* DEC-02 and DEC-03 can only remove entries from V4. With 140 baseline trades, a pass on fewer trades is weaker
  evidence, not stronger.

**Consistency with the protocol.** The December file overrides the protocol in two places, both disclosed and both
stricter: a fixed end date for B, and an explicit drawdown measure. No conflict that loosens anything.

## Proposed patches, for approval

Nothing below is merged. Branch `proposal/fable-review-2026-11-14`, one commit, `git diff main --stat`:

```
 dashboard/freqtrade_panel.py            |   2 +-
 scripts/grid_backtest_v2.py             | 330 ++++
 scripts/tests/repro_grid_v1_findings.py | 129 ++++
 scripts/tests/test_grid_v2.py           | 195 ++++
```

**Patch 1: `scripts/grid_backtest_v2.py`, a new file.** Version 1 and `results/research_grid.md` are not touched.
Priority order follows correctness first, then accounting:

| Change | Fixes |
|---|---|
| Decisions at the close of candle i, executed at the open of candle i+1; orders fill only from then on | G-N1, G-N3 |
| Per level budget `capital / (n * (1 + fee))`; cash asserted non negative after every move | G-N2 |
| Fixed priority at each close: K2 stop on the live grid, then K3, then scheduled recentre | G-N5 |
| One ledger: grid profit, liquidation profit, open profit, fees; asserted equal to equity on every candle | G-N6, G-N7, G-K2 |
| Recentre fee charged, `--recentre net` or `gross` | G-K1 |
| Explicit intrabar path, `--path OLHC` or `OHLC`; `--all` runs both | G-K4, G-N9 |
| Drawdown on closes and intrabar; equity marked to market and if liquidated | G-N4, G-N7 |
| Month key set at every creation; K3 works under R2; K1 defined as resting orders | G-N8, G-K3, G-N10 |

Kept identical to version 1 on purpose, so that any difference in results is a defect fixed and not a rule changed:
the range rules, the 2% recentre threshold, the K2 stop tested on hourly closes, the re entry count, fills at the
level price on touch, the fee. Known remaining optimism: a limit order is assumed filled when price touches it.

**Patch 2: tests.** `scripts/tests/test_grid_v2.py` (13 tests covering every finding, plus 160 random walk runs on
which the ledger must reconcile on every candle) and `scripts/tests/repro_grid_v1_findings.py` (the evidence for this
review).

**Patch 3: dashboard caption, one line.** The dashboard stays read only; `tests/test_data.py` passes (5 passed).
```diff
-...above average volume; exits on two 4h closes below EMA50, the gate shutting, a 15% stop...
+...above average volume; exits on a 4h close below EMA50, the gate shutting, a 15% stop...
```

**Patch 4, text only, not on the branch: an addendum to `docs/RESEARCH_CYCLE_2026-12.md`.** To be appended only if
Abdullah approves, before the first December run, with his answer to point 1 filled in:
```
## Addendum (clarifications before the first run; the bar is unchanged)
1. Winner stress fails if: <Abdullah's rule>.
2. All bar comparisons use Freqtrade's printed values (profit factor and drawdown to two decimals).
3. One download on or after 1 December; checksums taken once; gate, window A and window B all run on that snapshot.
4. If the window A winner fails on window B, the cycle ends. No second candidate is run on B.
5. The window B baseline is rerun on 20231030-20261201 and will differ from the 30 October figures.
```

**Patch 5, text only, for cycles after December: `docs/RESEARCH_PROTOCOL.md`.** Replace "never used for design" for
window A with the December disclosure; add trade export, `--timeframe-detail 15m` for baseline and candidates alike,
and profit per deployed dollar as reported figures. To be written and registered before any January result exists.

## If the patches are approved: commands for the VPS agent

Research only. None of these is a December candidate backtest.
```
# grid, version 2, the six registered candidates, both paths, both fee modes (Binance public klines, no keys)
python3 scripts/tests/test_grid_v2.py
python3 scripts/grid_backtest_v2.py --all --out-dir results/grid_v2
# write results/research_grid_v2.md with the command, the data range and a v1 against v2 table

# V4 only, existing data, pinned image
$FT recursive-analysis $CFG --strategy MemeSleeveV4 --timeframe 4h --timerange 20200815-20231030 --pairs DOGE/USDT SHIB/USDT SOL/USDT
```

## Limits of this review

* No real candle was touched. Every grid number here is synthetic proof of mechanism.
* The Freqtrade statements come from reading the 2026.9 source, not from running it.
* `backtest_config.json` and the live `config.json` are not in the repository and were not read.
* Version 2 was written and tested by the same reviewer. Before its numbers are relied on, the VPS agent or a second
  reviewer should read it. The random walk reconciliation test catches accounting errors, not modelling choices.

## Decisions for Abdullah

1. Approve or reject patches 1 and 2 (new simulator and tests) and, if approved, the version 2 rerun.
2. Approve or reject patch 3 (caption).
3. Give the stress failure rule for December (point 1) and approve the addendum, before 1 December.
4. Nothing else is needed. V4 keeps running unchanged; its review is still due around 1 December.
