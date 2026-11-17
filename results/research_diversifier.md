# A third fund for the TrendFilter sleeve: does it fall less?

Plan and bar: `docs/RESEARCH_DIVERSIFIER_PLAN.md`. Command: `python3 scripts/sleeve_compare.py --out results/research_diversifier.md`. Run 2026-11-17 12:00 UTC.
Data: Yahoo daily closes and adjusted closes, sessions common to all funds. Window 2007-01-03 to 2026-11-16; parts split at 2017-01-01.
Rule: SMA200, band 1%, first session of each month, cash earns 0. Sleeves are equal starting shares, not rebalanced. In sample: one window.

## Verdict: no candidate passes

Passed: none.

## Sleeves under the rule

| Sleeve | Per year | Total | Max drawdown | Drawdown 2007 to 2016 | Drawdown 2017 on | Result |
|---|---|---|---|---|---|---|
| SPY + QQQ (baseline) | +11.41% | +755% | 20.6% | 20.6% | 19.8% | |
| SPY + QQQ + GLD | +10.21% | +590% | 17.3% | 13.5% | 17.3% | FAIL |
| SPY + QQQ + EFA | +9.78% | +538% | 18.8% | 18.8% | 18.3% | FAIL |
| SPY + QQQ + IWM | +9.88% | +550% | 19.5% | 19.5% | 18.2% | FAIL |
| SPY + QQQ + IEF | +9.55% | +512% | 16.3% | 15.7% | 16.3% | FAIL |

### GLD

| Criterion | Result | Detail |
|---|---|---|
| 1. drawdown at least 2 points lower over the whole window | pass | 17.3% against 20.6% (+3.3) |
| 2. drawdown not worse in each part | pass | p1: 13.5% against 20.6%; p2: 17.3% against 19.8% |
| 3. return per year not more than 1.0 point below | fail | +10.21% against +11.41% (gives up +1.20) |

### EFA

| Criterion | Result | Detail |
|---|---|---|
| 1. drawdown at least 2 points lower over the whole window | fail | 18.8% against 20.6% (+1.8) |
| 2. drawdown not worse in each part | pass | p1: 18.8% against 20.6%; p2: 18.3% against 19.8% |
| 3. return per year not more than 1.0 point below | fail | +9.78% against +11.41% (gives up +1.63) |

### IWM

| Criterion | Result | Detail |
|---|---|---|
| 1. drawdown at least 2 points lower over the whole window | fail | 19.5% against 20.6% (+1.0) |
| 2. drawdown not worse in each part | pass | p1: 19.5% against 20.6%; p2: 18.2% against 19.8% |
| 3. return per year not more than 1.0 point below | fail | +9.88% against +11.41% (gives up +1.53) |

### IEF

| Criterion | Result | Detail |
|---|---|---|
| 1. drawdown at least 2 points lower over the whole window | pass | 16.3% against 20.6% (+4.2) |
| 2. drawdown not worse in each part | pass | p1: 15.7% against 20.6%; p2: 16.3% against 19.8% |
| 3. return per year not more than 1.0 point below | fail | +9.55% against +11.41% (gives up +1.86) |

## Each fund alone (context, not part of the bar)

| Fund | Rule: per year | Rule: max drawdown | Held: per year | Held: max drawdown | In market | Correlation with SPY, QQQ |
|---|---|---|---|---|---|---|
| SPY | +10.21% | 17.3% | +10.68% | 55.2% | 77% | QQQ 0.92 |
| QQQ | +12.40% | 28.6% | +15.62% | 53.4% | 81% | SPY 0.92 |
| GLD | +6.65% | 44.3% | +9.12% | 45.6% | 69% | SPY 0.07, QQQ 0.06 |
| EFA | +3.64% | 27.4% | +4.72% | 61.0% | 64% | SPY 0.88, QQQ 0.78 |
| IWM | +4.47% | 33.2% | +7.91% | 58.6% | 68% | SPY 0.89, QQQ 0.82 |
| IEF | +1.14% | 12.5% | +3.06% | 23.9% | 53% | SPY -0.28, QQQ -0.23 |

Not financial advice. One historical window; a pass is eligibility for a paper proposal, not a promise about the future.
