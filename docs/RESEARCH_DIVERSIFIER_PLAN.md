# Research plan: a third fund for the Alpaca TrendFilter bot that does not move with SPY and QQQ

Asked for by Abdullah on 2026-11-17 ("any more stocks or indexes we should add to backtest?"; Shariah compliance is
not a requirement). Fixed before any price was downloaded or any test was run. Research only: nothing on the running
Lumibot container, its config or its paper account changes because of this file.

## Question
Does adding one more fund, as an equal third part under the bot's own rule, make the sleeve fall less than SPY and
QQQ alone, without giving up much return? The question is deliberately not "does it beat SPY": over recent years that
test mostly rewards technology heavy funds, and the sleeve already holds QQQ.

## Candidates, four, fixed here
| Fund | What it is | Listed since |
|---|---|---|
| GLD | gold | 2004 |
| EFA | developed market stocks outside the US | 2001 |
| IWM | US small companies | 2000 |
| IEF | US Treasury bonds, 7 to 10 years | 2002 |

EFA stands in for "international" instead of VXUS because VXUS only starts in 2011 and would miss 2008.
No fund is added, swapped or dropped after results are seen. SPUS is not part of this study (it failed its own bar on
17 Nov; whether it joins the paper bot is Abdullah's separate decision).

## Rule and model
* Each fund runs the bot's rule unchanged (`fixes/alpaca/strategies/trend_filter.py`, `config_v2.json`): first session
  of each month, last completed close against SMA200 with a 1% band; cash earns nothing.
* Baseline sleeve: SPY and QQQ, half each. Candidate sleeve: SPY, QQQ and the candidate, a third each.
* A sleeve is the average of its funds' rule curves, each starting with an equal share and never rebalanced. This is
  how the bot behaves (each fund's part is sized on its own); it is a model, the bot's fills will differ a little.
* Daily closes and dividend adjusted closes from Yahoo's public chart endpoint. Returns use adjusted closes.

## Window
First monthly check of 2007 to the last completed session at run time. First part 2007 to 2016, second part 2017 on:
the same split as the original TrendFilter backtest (`fixes/alpaca/backtest_v2.py`). It contains 2008, 2020 and 2022.
SPY and QQQ under this rule have been looked at before on these years; the four candidates have not.

## Bar, per candidate: all three
1. Whole window: the candidate sleeve's maximum drawdown is at least **2 percentage points lower** than the baseline's.
2. In **each** part: its maximum drawdown is not worse than the baseline's.
3. Whole window: its return per year is not more than **1.0 percentage point below** the baseline's.

If more than one passes, the one with the largest drawdown reduction is proposed; if tied to one decimal, the higher
return. At most one fund is proposed from this study.

Reported but not used to pass or fail: each fund alone under the rule and held, time in the market, daily return
correlation with SPY and QQQ, and the sleeve results per part.

## What a pass would mean
Eligibility to propose that fund for the paper bot, with Abdullah's written approval, a root config change, and the
usual checks (fractional shares on Alpaca, ledger handles the new symbol). It is a historical result on one window and
not a promise about the next ten years.

## Command and output
```
python3 scripts/tests/test_sleeve_compare.py
python3 scripts/sleeve_compare.py --out results/research_diversifier.md
```
No rerun with different funds, dates or thresholds after the result is seen.
