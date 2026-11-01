# trading-ops: rules for any agent working in this repository

* Read docs/HANDOVER.md first in every session: it holds the state of the bots, the decisions taken and the open items. Update it when something material changes.

* This repository is the source of truth for strategies, configs (secrets free), the dashboard and audit results. Change files here first, then deploy to the VPS; never the other way round.
* Never commit secrets: API keys, Telegram tokens, passwords, .env files, or the live /root/freqtrade/config.json. The .gitignore blocks the common cases; check `git diff` before every commit.
* The dashboard is read only. It must never import a broker or exchange client or call an order endpoint. tests/test_data.py enforces this; keep it passing.
* Freqtrade stays in dry run and Lumibot in paper until Abdullah approves a go live in writing. Do not edit dry_run or paper flags.
* Strategy changes are new files (V4, V5...). Existing strategy files are history and stay unchanged.
* Every backtest or audit result goes under results/ as markdown with the command used and the data range.
* Commit messages state what changed and why in one line each.
