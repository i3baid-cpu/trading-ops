# Research protocol: how a strategy change earns its way into the dry run

The method that produced V4 and rejected the grid, written down so every cycle runs the same way. Research never
touches the live containers; promotion is a separate, approved step.

## One cycle
1. **Pre-register.** Before any test: the question, the candidates (at most 6), the windows, the bar. Written to
   `docs/RESEARCH_CYCLE_<yyyy-mm>.md` and committed. Nothing is added to the list after seeing results; a new idea
   goes into the next cycle.
2. **Unseen first.** Every candidate runs on window A (2020-08-15 to 2023-10-30, never used for design) before
   window B (2023-10-30 to now). Choose on A only. Run the chosen one once on B. Report every candidate.
3. **Baseline beside it.** The current dry run strategy on the same windows, and holding the same coins.
4. **Stress the winner.** Fee 0.2%, `--timeframe-detail 15m`, neighbouring parameters (±25%), per year table,
   profit without the best two months, lookahead and recursive analysis. A result that needs exact settings fails.
5. **Bar.** Beats the baseline on A by at least 0.1 profit factor, positive on both windows, profit factor above
   1.2 on both, drawdown no worse than the baseline, profit without the best two months still positive.
6. **Verdict file.** `results/research_<yyyy-mm>.md` with every command, data range, tables, verdict. Pushed.
7. **Promotion** (separate step, Abdullah's written yes): a passing candidate becomes a new numbered strategy file
   and replaces the dry run strategy only when the current one has at least 4 weekly reports, or earlier if the
   current one is losing against its own study. The new one then starts its own forward test. Real money is never
   decided in a research cycle.

## Cadence
One cycle a month, started by Abdullah in Claude Code ("run the research cycle") or by the agent after the first
Sunday report of the month. Compute budget: a cycle must finish inside one session; if it cannot, cut candidates,
never windows.

## What is never allowed
Optimising a parameter on window B. Adding a candidate after a result. Reporting the winner without the losers.
Changing an existing strategy file. Touching config.json, the containers or the dry run database.
