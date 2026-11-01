# trading-ops: rules for any agent working in this repository

* Read docs/HANDOVER.md first in every session: it holds the state of the bots, the decisions taken and the open items. Update it when something material changes.

* This repository is the source of truth for strategies, configs (secrets free), the dashboard and audit results. Change files here first, then deploy to the VPS; never the other way round.
* Never commit secrets: API keys, Telegram tokens, passwords, .env files, or the live /root/freqtrade/config.json. The .gitignore blocks the common cases; check `git diff` before every commit.
* The dashboard is read only. It must never import a broker or exchange client or call an order endpoint. tests/test_data.py enforces this; keep it passing.
* Freqtrade stays in dry run and Lumibot in paper until Abdullah approves a go live in writing. Do not edit dry_run or paper flags.
* Strategy changes are new files (V4, V5...). Existing strategy files are history and stay unchanged.
* Every backtest or audit result goes under results/ as markdown with the command used and the data range.
* Commit messages state what changed and why in one line each.

## Session protocol (enforced by .claude/hooks where possible)
* Session start: the hook prints docs/HANDOVER.md and the container status. Open with three lines: what runs where, the first open item, whether anything needs root.
* Before any change to a file, show the diff and wait for Abdullah to answer "yes, apply" in his own words. Before any restart, rebuild or strategy swap, show the exact command and wait the same way. The guard hook blocks these unless the command ends with a comment quoting his approval, for example `sudo ft-swap-strategy MemeSleeveV3   # Abdullah approved: "yes swap to v3"`. Add that comment only when he said yes in the current message; never invent it. If blocked, ask, do not work around it.
* Root actions (compose up, config.json, .env, sudoers): never attempt them. Use /root to hand Abdullah one block to paste as root, then wait for "done" and verify from logs.
* Whenever a decision is taken or the state of a bot changes, run /handover: update docs/HANDOVER.md and push, so the next session and the chat assistant pick it up.
* /status answers "how are things" read only; /gate explains why V3 has or has not traded.
