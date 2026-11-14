# Independent code and research-method audit — 2026-11-14
**For Fable review | Evidence and remediation checklist | NO changes to live trading authorized**

Repository: [i3baid-cpu/trading-ops](https://github.com/i3baid-cpu/trading-ops).
This report preserves all findings from the ChatGPT review requested on 2026-11-14. It distinguishes **confirmed by reading the code**, **reproduced in a local synthetic model**, **plausible execution risk**, and **unverified on historical/VPS data**. Fable should independently challenge every finding, add counterexamples where appropriate, and report findings it cannot reproduce.

## TL;DR

1. **V4**: No direct lookahead/repainting bug was identified in the strategy's indicator code. The previous V3/V4 research reported clean lookahead analysis; this audit **did not re-run it**. Live-versus-backtest discrepancies remain possible because of limit fills, spread/slippage, stop/trailing execution, latency, intrabar price path, and signal/entry timing. Profitability should not be treated as independently proven.
2. **Grid**: In addition to the four known caveats in `results/research_grid.md`, further independently visible defects affect chronology, financing, risk and metric attribution. In particular, trades can be filled retroactively within a candle and initial grid inventory can create negative cash. **Do not deploy or infer corrected historical profit without a fixed, independently rerun simulator.**
3. **Protocol**: The methodology preserves a useful no-post-hoc-selection rule, but the current drawdown gate can reject an economically better strategy over a $0.60 difference on a $1,000 wallet; it does not yet require an adequate execution/friction model or returns relative to deployed exposure. More importantly, A has already been used for November selections and is **not genuinely unseen for December**.
4. **December**: Three research-only hypotheses were already pre-registered in `docs/RESEARCH_CYCLE_2026-12.md`, plus up to three reserved slots for the owner's separately registered ideas. This audit document is **not another candidate proposal**. Do not revise the December bar because of a previous near miss.
5. **V4 reproduction**: Existing VPS reports say 140 trades, +79.36 USDT, PF 1.64 on Window A; **this auditor did not independently execute the full Freqtrade baseline**. The December pre-registration makes an independent baseline match a stop/go gate.

## Exact source snapshot read

- [`fixes/freqtrade/MemeSleeveV4.py`](https://github.com/i3baid-cpu/trading-ops/blob/main/fixes/freqtrade/MemeSleeveV4.py), blob SHA `74f137dabdbee9a2307870ca24ce912fa6e6141c`
- [`scripts/grid_backtest.py`](https://github.com/i3baid-cpu/trading-ops/blob/main/scripts/grid_backtest.py), blob SHA `b78026a8ff74e2234421f720b29ba0863d4a59e7`
- [`scripts/tests/test_grid.py`](https://github.com/i3baid-cpu/trading-ops/blob/main/scripts/tests/test_grid.py)
- [`results/research_grid.md`](https://github.com/i3baid-cpu/trading-ops/blob/main/results/research_grid.md)
- [`results/research_v4_sol.md`](https://github.com/i3baid-cpu/trading-ops/blob/main/results/research_v4_sol.md)
- [`results/research_2026-11.md`](https://github.com/i3baid-cpu/trading-ops/blob/main/results/research_2026-11.md)
- [`docs/RESEARCH_PROTOCOL.md`](https://github.com/i3baid-cpu/trading-ops/blob/main/docs/RESEARCH_PROTOCOL.md)
- [`docs/RESEARCH_CYCLE_2026-12.md`](https://github.com/i3baid-cpu/trading-ops/blob/main/docs/RESEARCH_CYCLE_2026-12.md)

Line numbers below refer to those versions; re-check lines if source changes.

---

## A. MemeSleeveV4 — direct signal bias and execution realism

| ID | Priority | Finding and evidence | Status | Review / corrective test |
|---|---|---|---|---|
| V4-01 | Low | `ema50 = EMA(...,50)`, BTC 1d `EMA(...,100)` use historical rolling indicators; no negative shift, future index, or full-series future aggregate is visible ([V4 lines 33–40](https://github.com/i3baid-cpu/trading-ops/blob/main/fixes/freqtrade/MemeSleeveV4.py#L33-L40)). | **No direct lookahead found**, not a proof of absence | Repeat `lookahead-analysis` on pinned Freqtrade data/image; review any callbacks/config outside this strategy. |
| V4-02 | Low | Breakout prior high uses `high.rolling(20).max().shift(1)` ([line 35](https://github.com/i3baid-cpu/trading-ops/blob/main/fixes/freqtrade/MemeSleeveV4.py#L35)). Current bar's high is intentionally excluded; volume mean includes the completed signal candle, which is okay **only if the signal is acted on after that bar closes**. | **Code looks causally valid** | Verify signal is computed at 4h close and orders cannot fill earlier within that same signal bar. |
| V4-03 | Low | `merge_informative_pair(..., "1d", ffill=True)` merges BTC daily gate ([line 40](https://github.com/i3baid-cpu/trading-ops/blob/main/fixes/freqtrade/MemeSleeveV4.py#L40)); the Freqtrade helper is designed to delay higher-timeframe values appropriately. | **No obvious daily lookahead** | Test daily transition at UTC day boundaries, especially partial/unclosed 1d candles in live data. |
| V4-04 | High | Orders request entry/exit **limit**, stoploss **market** ([line 24](https://github.com/i3baid-cpu/trading-ops/blob/main/fixes/freqtrade/MemeSleeveV4.py#L24)). Backtests may count theoretical limit fills with no queue-position, adverse-selection, spread, latency or actual partial-fill/expiry behavior; real trades may miss or execute later. **No claim that the strategy always fills at the exact close:** inspect the installed Freqtrade engine and entry/exit price configuration before asserting that. | **Execution-model risk; not quantified** | Run conservative bid/ask/slippage and fill-delay scenarios; reconcile dry-run orders and exchanges; inspect `entry_pricing`, `exit_pricing`, timeouts, unfilled orders, and live order logs. |
| V4-05 | High | Stoploss −15%, trailing 10% activated after +20% ([lines 15–21](https://github.com/i3baid-cpu/trading-ops/blob/main/fixes/freqtrade/MemeSleeveV4.py#L15-L21)). Four-hour OHLC does not reveal path or gap through a stop, so backtest stop/trail fills can differ significantly from exchange execution. | **Execution-model risk; not quantified** | Compare 4h with 15m/5m detail on identical data; inspect trail initialization and stoploss execution at gaps and spread spikes. |
| V4-06 | Medium | Across A, November report shows **4h +79.36 USDT vs 15m detail +117.65 USDT**, demonstrating path sensitivity; this does **not** itself prove optimism at 4h. Research reports 0 biased indicators/entries/exits in V3's `lookahead-analysis`, but that only checks one category of bias. | **Documented in prior research; no independent reproduction here** | Test conservative fill assumptions and measure PF, profit, turnover, MAE/MFE, stop vs exit reason, and unmatched live signals. |
| V4-07 | Medium | Exposure is tiny: 25 USDT fixed stake × 3 concurrent slots = up to 75 USDT in a 1,000 USDT wallet. A 2.55% whole-wallet drawdown is not necessarily small relative to deployed risk. The +79.36 USDT A result was concentrated mainly in 2021. | **Documented measurement concern** | Report both whole-wallet drawdown and mark-to-market drawdown relative to allocated capital, time-in-market, and fees/turnover. Never extrapolate 75 USDT exposure returns to a 3,000 USDT grid account by simple multiplication. |

**V4 conclusion:** Neither a confirmed direct repainting mechanism nor a confirmed future-candle reference was found in this 60-line strategy. The **open risk is fill/stop realism and incomplete testing**, not a proven cheat. Review all supplied config and engine settings before claiming true live equivalence.

---

## B. Grid backtest — four *already documented* issues (do not count as new)

These are quoted/reframed from `results/research_grid.md`, not newly discovered here.

| Known ID | Prior report issue | Location |
|---|---|---|
| G-K1 | On range recenter, capital is taken from equity **before** inventory liquidation fees, so the fee for that sale can be omitted from the new grid capital. | `run()` lines 150–155, 161–162, 172–173 |
| G-K2 | During R1 month transitions with no restart, `realized_total += grid.realized` can recount profit without resetting the counter. Reported realized totals are overstated, although equity may not be. | lines 150–155 |
| G-K3 | K3 is suppressed for rule R2 (`brk == "K3" and rule != "R2"`), contrary to the literal R2+K3 specification. | lines 167–174 |
| G-K4 | Within a single hourly candle, the simulated path always runs **low before high**, creating same-hour buy-then-sell fills that may be impossible; some other fills are pessimistically omitted. | `Grid.step()` lines 80–94 |

Prior scratch test of K1–K3 was reported to change chosen grid candidate A return from +31.1% to +30.6%; **this audit did not re-run that scratch test**. Those numbers do not account for the additional issues below.

## C. Grid backtest — additional findings beyond those four

| ID | Priority | Finding | Code evidence and why it matters | Test/fix |
|---|---|---|---|---|
| G-N1 | **Critical** | **Retroactive execution in the same candle used to initialize/restart the grid.** | At `run()` lines 137–145 the algorithm computes current hour close `p=k["c"]` and creates `Grid(..., p, ...)`. It subsequently invokes `grid.step(k["l"], k["h"])` at line 175, trading that hour's high and low **before the just-used closing price**. Similar recenter paths recreate the grid and trade the same historical hour. | Choose levels and submit orders using only previously completed bars; process subsequent candles, never the current candle whose close determined those orders. Assert every fill timestamp is after order creation. |
| G-N2 | **Critical** | **Initial grid allocation can borrow fee money: negative cash on initialization.** | `Grid.__init__()` lines 63–70 allocate `capital/n` for every level at or above price, then subtract entry fees with no cash/funding constraint. When price is below the lower range bound, all `n` lots may be bought and fees drive `cash < 0`, inconsistent with an unlevered spot account. | Pre-budget fees and reserve cash; test prices below/at/above all grid bounds, minimum orders and rounding; reject any negative cash or leverage. |
| G-N3 | High | **Range signal includes the same hour's future-intrahour information.** | `range_for()` at lines 115–122 includes `kl[i]` for R1 and current close for R2; `run()` uses the resulting range in the *same hour* before processing that hour's lows/highs. Same bar range values cannot be known before those intrahour touches. | Use `kl[:i]` for order-setting decisions, or timestamp all decisions at candle close and trade next bar. |
| G-N4 | High | **Risk understates intrahour drawdowns.** | At lines 184–186 drawdown marks only `grid.equity(k["c"])` at hourly close. Deep intra-hour liquidation/unrealized-loss excursions are absent. | Add intrahour adverse-price mark under a defensible event ordering, show both close-to-close and high-frequency/intrabar DD; never label one as the other. |
| G-N5 | High | **Stop/recener interaction can change K2 behavior.** | R1 monthly and R2 recenter checks run at lines 147–163 **before** the K2 break test at 164–175. A new `lo` may reset the lower bound before `p < grid.lo*0.9` is evaluated, potentially suppressing a stop that would have fired under the old active grid. | Define explicit priority: detect stops on prior standing orders/active range first, then any recenter/re-entry; test boundary collisions. |
| G-N6 | Medium | **Stop and liquidation profit attribution is incomplete.** | `grid.realized` increments only per-level sales in `Grid.step()` (line 93). `liquidate(p)` (lines 98–105) charges fees and moves cash but does not book liquidation P&L as realized. A residual called `inventory_mtm_at_end` (line 207) therefore includes losses/profits from previously liquidated lots, not just current inventory mark-to-market. | Maintain a cost-basis ledger and separately report grid spread realized P&L, liquidation P&L, open/unrealized P&L, and fees; assert components reconcile to final equity. |
| G-N7 | Medium | **Reported fees can omit forced-liquidation fees; an executable final closeout figure is absent.** | `fees_total += grid.fees` is performed **before** `grid.liquidate(p)` on restart/stop paths (lines 150–155, 161–173). The extra sell fee is not always accumulated into reported `fees_total`. Last-candle equity is marked at mid/close without a final sell-fee assumption: defensible for a marked-to-market statistic, but **not** a cash-realizable liquidation value. | Add fees only after settlement; separately publish `equity_MTM` and `equity_if_liquidated` net of spread/slippage/fee. |
| G-N8 | Medium | **Monthly recenter state is not reset when re-entering from cash-only.** | At line 183 a new grid is created after 5 qualifying days but `month_key` is not set to the re-entry month, unlike line 145. Subsequent first-midnight monthly logic can treat an otherwise new grid as needing an extra reset. | Set the new month key at every grid creation and test stop → cash-only → re-entry across month boundaries. |
| G-N9 | Medium | **Path index bookkeeping has a questionable high/low fallback.** | `self.last_idx = self._idx(high if high < self.hi else low)` at line 94 tracks the candle *high* for most bars rather than the final close or a true chronological last-touch; when `high >= hi`, it abruptly substitutes the *low*. This changes which future downward orders can be reached and may double-count or miss crosses. | Replace with explicit ordered event simulation and inventory/order state. Test monotonic up/down, gap, high=range edge and V-shaped bars; compare against finer-granularity tick/minute replay. |
| G-N10 | Medium | **K1 outside-range pause is ambiguous relative to implementation.** | Plan says grid pauses outside range; code comment at line 174 says step still runs, and line 175 does run `grid.step()` even when the close is outside. The candle may traverse levels within the grid while ending outside; this could be valid for resting orders, but it is not a clean "pause" definition. | Clarify whether pending standing orders remain fillable outside range; align both plan and simulator and test boundary candles. |

### Synthetic reproduction of G-N1 and G-N2

An **isolated local Python reproduction of the `Grid` class logic** (same formulas, not the complete `run()` pipeline, not Binance historical data) produced:

```python
# Existing Grid semantics, zero changes to the repository:
g = Grid(lo=90, hi=110, n=4, capital=1000, price=100, fee=0.001)
# At candle close price=100, before re-trading the already-finished candle:
# g.equity(100) == 999.50
g.step(low=90, high=110)  # the same candle whose close created the grid
# g.equity(100) == 1049.107236842105
# -> retroactive +49.607236842105 USDT over already-executed init
g2 = Grid(lo=90, hi=110, n=4, capital=1000, price=80, fee=0.001)
# g2.cash == -1.0 USDT: all 4 lots consumed $1,000, fees debited afterward.
```

These are **synthetic proof-of-mechanism cases**. They do NOT quantify the impact on the previously reported A/B grid returns; only a corrected, independently rerun simulator can do that. The earlier four unit tests in `scripts/tests/test_grid.py` focus on identity/basic scenarios and do not cover event chronology, funding feasibility, fees through recenter, or order priority.

### Required grid retest suite before trusting results

1. Timestamp ordering: order must be placed before its fill; never fill on earlier portions of a candle.
2. Cash/fee invariants: available cash nonnegative, finite prices, no invisible margin, deterministic cost basis, conservation of cash plus inventory.
3. Event ordering: up→down, down→up, gap over multiple levels, high/low extremes, partial fills, resting orders, stop and recenter in same hour.
4. Settlement: separately reconcile `MTM equity`, `cash after full liquidation`, realized per-level spreads, liquidation P&L, open unrealized P&L, fee totals, and slippage.
5. R1/R2/R3 × K1/K2/K3 combinations and re-entry crossing month end; report unsupported combinations as such.
6. Hourly vs sub-hourly data replay with at least two plausible intrabar orderings where granular data is missing.
7. Re-run every original candidate, **with corrections clearly distinguished as a new simulator version**. Never overwrite original research evidence.

---

## D. Is the research protocol too strict, too loose, or targeting the wrong measure?

**Mixed: excessively brittle on an absolute drawdown comparison; insufficiently conservative on live execution and independent validation.**

### Evidence from November (already tested, not new)

| Window A metric | V4 baseline | November V4c (2h) |
|---|---:|---:|
| Trades | 140 | 170 |
| Net profit | +79.36 USDT | +104.88 USDT |
| Profit factor | 1.64 | 1.80 |
| Account-underwater max drawdown | 2.55% | 2.61% |
| Balance-based max drawdown | 2.81% | 2.62% |
| Profit without best 2 months | +24.57 | +54.23 |
| Decision under the committed November bar | Reference | FAIL |

V4c's 0.06-percentage-point larger drawdown equates to about **0.60 USDT on the $1,000 wallet**, despite +25.52 USDT greater net profit. That is a **diagnostic for future protocol design**, not permission to revise a fixed contest once results have been seen. The two reported drawdown definitions disagree on which strategy is safer.

**Too strict:** exact `DD <= baseline DD` with no scale/uncertainty tolerance can reject economically meaningful improvements for tiny currency differences. `PF +0.10` as a hard absolute requirement may also behave inconsistently across trade counts and risk profiles.

**Too loose:** no binding test for order-fill sensitivity, market impact/slippage, after-fee annualized dollars, minimum independently sampled trades, confidence/uncertainty, or risk per allocated dollar; bar can be passed with profits materially too small to cover operational cost.

**Measuring the wrong thing (in part):** whole-wallet underwater drawdown can hide concentration against only `3 × 25 = 75 USDT` maximum open stake; raw PF is not risk-adjusted expected economic utility. The “remove two best months” test helps avoid concentration but does not replace per-year/regime analysis.

**Most serious identification problem:** Window A (2020-08-15 through 2023-10-30) was expressly used to choose V4 and reject November alternatives, so it is **no longer unseen** for the December ideas. Window B was used to design/validate V3/V4 and is not an independent long-term holdout either. Be explicit about multiple research iterations; prospective new forward dry-run data is needed for true independent confirmation.

**Policy for December:** use the **unchanged, pre-committed** `docs/RESEARCH_CYCLE_2026-12.md` gate and explicit account-underwater DD metric for everybody. Log additional risk/execution metrics but **do not add retroactive pass criteria**, reclassify V4c's November outcome, or change the selected candidate after seeing B. Consider updating the general protocol **for a later cycle**, before any results under the revised rules exist.

### Proposed later-protocol measurements (NOT binding December tests)
- Profit per deployed risk dollar and whole-wallet return; time in market and fee-to-gross-profit ratio.
- Net after realistically missed-limit and delayed-stop stress; spread/slippage assumptions pinned ahead of tests.
- Peak-to-trough DD on wallet and allocated capital, recovery time, worst single trade and 90-day loss.
- Cross-regime yearly results, minimum trade count, stability/confidence intervals, and repeated-test disclosure.
- Compare against identical-exposure buy-and-hold/USDT and the true use case (dollars per year vs operational effort).
- Truly fresh prospective walk-forward records, with immutable data freeze before judgment.

---

## E. December candidate slate — already pre-registered, DO NOT test or tune here

**Source of truth:** [`docs/RESEARCH_CYCLE_2026-12.md`](https://github.com/i3baid-cpu/trading-ops/blob/main/docs/RESEARCH_CYCLE_2026-12.md). That committed document, not this audit, locks exact values, windows and comparison procedure.

| ID | Only proposed change vs V4 | Causal reason it might transfer beyond one regime | Important limitation |
|---|---|---|---|
| DEC-01 / V4e | 2h candles, EMA100, 40-bar breakout, 40-bar vol mean, 12-bar cooldown, startup 1400; keep ~same *hour* horizons as V4 | Faster trend-change detection without changing the length of each intended filter | Related 2h variant already performed well on A in November: **not a new blind discovery** |
| DEC-02 / V4f | V4 4h + require `close > previous_20bar_high + 0.25 * ATR14` | Volatility-scaled confirmation may reject minor/noisy false breaks in high-volatility markets | Could eliminate profitable early entries; no claimed validation |
| DEC-03 / V4g | V4 4h + require `EMA50 > EMA50.shift(8)` at entry | Rising intermediate trend may avoid late breakouts during flat/choppy periods | Could exclude profitable recovery trades; no claimed validation |

At most **three independently specified additional owner candidates** may be registered in the same December document **before the first test**. No hidden combinations or extra rounds. Same pinned Freqtrade image, fees, 1,000 wallet, 25 stakes, max 3 slots, A/B windows, baseline, candidate rules, and stress methodology.

If nothing qualifies on A, no B runs or winner-stress runs, and V4 remains unchanged. If a winner qualifies, verify once on B and stress per the registered protocol; an eventual forward test requires explicit owner approval.

---

## F. Baseline reproduction requirement — evidence vs what has actually run

**Original reference:** `results/research_v4_sol.md` (2026-11-02) and `results/research_2026-11.md` (2026-11-14) report V4 with `DOGE/USDT SHIB/USDT SOL/USDT` on A, **140 trades**, **+79.36 USDT** (November raw +79.365), **PF 1.64**, underwater **2.55%**.

This review **read those reports but did not execute Docker/Freqtrade or access VPS candle data**, so an *independent* pipeline reproduction remains open.

Reference-style command from the existing report (run only under the agreed read-only research procedure, with a pinned image and no live changes):

```bash
docker run --rm \
  -v /root/freqtrade/user_data:/freqtrade/user_data \
  freqtradeorg/freqtrade:stable backtesting \
  --config /freqtrade/user_data/backtest_config.json \
  --strategy MemeSleeveV4 --timeframe 4h \
  --timerange 20200815-20231030 \
  --fee 0.001 --breakdown month --enable-protections --export none \
  --max-open-trades 3 --pairs DOGE/USDT SHIB/USDT SOL/USDT
```

**Reproduction gate in December**: Freeze the image digest, market data and sanitized config checksums first; match 140 trades exactly and +79.36 USDT within 0.02, with PF 1.64 and per-year/month reconciliations. **If not, STOP before any candidates.** Capture full tool/image/data versions, candle start/end, missing pairs/warmups, fees, fills, precedence of config CLI flags, protection state, and trade reconciliation. Do not quietly “fix” the baseline by tuning settings to reproduce the desired number.

---

## G. Instructions and review checklist for Fable

**Requested work:** perform an independent adversarial review of this report, the *exact linked source files*, the pre-registration, and the cited historical results.

1. For each issue `V4-*`, `G-K*`, `G-N*`: report **confirmed / disproven / needs data** with precise file and line, a minimal reproducible test or counterexample, and whether the issue is inflated optimism, pessimism or unquantified.
2. Prioritize grid `G-N1`, `G-N2`, `G-N3`, `G-N5`, and fees reconciliation; quantify historical impact **only after an independently validated accounting/event engine** is written and results are labeled as a new version.
3. Audit actual Freqtrade fill engine, `backtest_config.json` (without exposing secrets), entry/exit pricing, stop/trail rules, data warm-up, candle timing and any fees not modeled. Avoid stating “lookahead confirmed” where no future data were demonstrated.
4. Independently reproduce V4 A baseline **before** testing any December ideas; verify differences against expected 140 / +79.36 / PF1.64 and stop on mismatch.
5. Evaluate whether proposed future protocol metrics more directly match the user's goal (reliable, small-capital, real-world net return), but **do not retroactively relax the December bar**.
6. Check that the DEC-01..03 rules are implementable, causal and identical to the pre-registration; do not tune, run, or add alternatives without an explicit later research authorization.
7. Return a review report as a **separate file** (suggested `results/fable_review_2026-11-14.md`) with a proposed patch plan and unit tests. Show diffs for approval. Preserve source evidence and do not overwrite existing historical reports.

**Safety/change boundary:** no change to live/dry-run strategy, root `config.json`, Docker containers, trading wallets, database, or deployed schedules. Creating or assessing this document is not permission to trade or run a new cycle. Research-only tests require the separate registered, fair method. No secrets in GitHub commits.

## Bottom line

- **V4:** causal signal logic looks sound on inspection, but execution realism is *not verified* by a clean lookahead test.
- **Grid:** additional chronology and accounting defects invalidate confidence in its numeric economic projections until corrected/replayed; previous no-deploy verdict remains prudent.
- **Protocol:** disciplined pre-registration is valuable; the bar must be economically relevant and honestly labeled when data are no longer unseen.
- **December:** pre-registered three hypotheses + reserved owner slots are the only allowed candidate slate, and only the stipulated reproducible baseline unlocks later testing.
