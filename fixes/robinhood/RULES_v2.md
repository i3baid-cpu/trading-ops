# Robinhood ••8275: proposed rule set v2 (replaces the contradictory v1 rules)

Nothing here can be automated; Robinhood has no bot API. These are the rules the agent and you follow by hand.

## 1. Who decides
* The agent proposes, you approve. Every order needs your explicit "yes" in the same thread. Remove the words "AI managed" from all briefs; the account is "AI assisted, human approved".
* Any order placed without approval is reported the same day and reversed if still open.

## 2. Two books, measured separately
* **Core book**: ETH, BTC, NVDA, QQQ, AMD. Long term holdings. Not traded by rules. Reported with cost basis where known and "Not available" where not.
* **Sleeve book**: everything bought after Oct 30 2026 under rule 4. Starting capital for the sleeve is whatever cash you assign to it (today that is about $7, which means the sleeve is effectively closed until you fund it or sell something).
* Performance "since Grok took charge" is reported for the sleeve only. Mixing in ETH's price moves tells you nothing about the agent's skill.

## 3. Concentration
* ETH is 66% of the account. Decide one of two things, in writing, this week:
  a) ETH is a deliberate long term holding exempt from the 20% rule and sits in the core book, or
  b) ETH is to be brought to 20% or below by selling in steps (for example 15% of the position per month) with an order each time that you approve.
* Until that decision is written down, no new buys of any kind in the account.

## 4. Sleeve trading rules (if you keep the sleeve on Robinhood at all)
* Minimum ticket $100. A $22 ticket loses more to Robinhood's crypto spread than it can reasonably earn; the five $22 trades so far returned −$5.11 before spread.
* Every buy has a GTC stop placed in the same minute, and a written target. No stop, no trade. The Oct 30 FLOKI position currently breaks this: place its stop at −10% from $0.00002343 (about $0.0000211) or close it.
* Maximum 2 sleeve positions, maximum 10% of account each.
* No meme coins on Robinhood. The meme experiment lives in Freqtrade dry run, where fees are 0.1% a side and results are measurable. Shift the crypto allocation to Binance only when MemeSleeveV2 passes its gate.

## 5. Daily and monthly limits (apply to the sleeve)
* Daily loss limit: 3% of sleeve capital. Hit it, no more orders that day.
* Monthly loss limit: 8% of sleeve capital. Hit it, sleeve closed for the rest of the month and rules reviewed.

## 6. Alerts (the routine that was offered on Oct 28 and never confirmed)
* One message per fill: account, side, ticker, qty, price, total, reason, stop level, and sleeve P&L month to date.
* One message per day at 09:00 Kuwait: equity, sleeve P&L, open stops, any rule breach.

## 7. Migration to Alpaca
* The stock side moves to Alpaca only after the TrendFilter strategy passes its paper gate (DEPLOY.md). Until then the stock positions in Robinhood are core book and untouched.
* "5% better than the S&P 500" is not a rule a bot can be given; it is an outcome. The rule you can enforce is: paper strategy must track SPY within 3 points of CAGR with a smaller drawdown for 3 months before any live dollar moves.
