# SPUS against SPY under the TrendFilter rule

Plan and bar: `docs/RESEARCH_ISLAMIC_ETF_PLAN.md`. Command: `python3 scripts/etf_compare.py --out results/research_islamic_etf.md`. Run 2026-11-17 11:46 UTC.
Data: Yahoo daily closes and adjusted closes. Window 2020-11-02 to 2026-11-16, halves split at 2023-11-09.
Rule: SMA200, band 1%, checked on the first session of each month, cash earns 0. In sample: one window, chosen by the fund's age.

## Verdict: FAIL

| Criterion | Result | Detail |
|---|---|---|
| 1. higher total return over the whole window | pass | +109.5% against +98.3% |
| 2. higher total return in each half | pass | h1: +38.7% against +37.9%; h2: +51.0% against +43.8% |
| 3. drawdown not more than 3 points worse | fail | 23.6% against 15.6% (gap +8.0) |

## Under the bot's rule

| Fund | Total | Per year | Max drawdown | First half | Second half | Switches | In market |
|---|---|---|---|---|---|---|---|
| SPUS | +109.5% | +13.0% | 23.6% | +38.7% | +51.0% | 9 | 82% |
| SPY | +98.3% | +12.0% | 15.6% | +37.9% | +43.8% | 9 | 79% |
| QQQ | +131.4% | +14.9% | 18.4% | +62.5% | +42.4% | 7 | 79% |
| HLAL | +127.8% | +14.6% | 14.9% | +49.2% | +52.7% | 5 | 83% |

## Buy and hold, same window

| Fund | Total | Per year | Max drawdown | First half | Second half |
|---|---|---|---|---|---|
| SPUS | +161.1% | +17.2% | 28.2% | +43.9% | +81.5% |
| SPY | +143.0% | +15.8% | 24.5% | +37.4% | +76.9% |
| QQQ | +153.9% | +16.7% | 35.1% | +39.6% | +81.9% |
| HLAL | +144.2% | +15.9% | 23.2% | +47.2% | +65.9% |

## Daily return correlation with SPUS

* SPY: 0.964
* QQQ: 0.969
* HLAL: 0.963

Not financial advice. One historical window; a pass is eligibility for a paper proposal, not evidence of an edge.
