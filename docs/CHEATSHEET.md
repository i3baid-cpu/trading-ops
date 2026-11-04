# Cheat sheet: operating the trading VPS

Two users. root = configs, secrets, compose, cron. claude-ops = Claude Code and git. `su - claude-ops` alone on a line; `exit` to go back.

## As root (aliases from /root/.bash_aliases)
| Type | Does |
|---|---|
| `cc` | open Claude Code as claude-ops in ~/trading-ops (prints handover + status on start) |
| `bots` | are freqtrade, lumibot, trading-dashboard up |
| `ftlogs` / `allogs` / `dashlogs` | last log lines of each container |
| `dashdeploy` | pull the repo and rebuild the dashboard now (cron also does this every 15 min) |
| `audit` | run the Sunday audit now (report to Telegram) |
| `ftswap MemeSleeveV3` | swap the Freqtrade dry run strategy and restart (dry run only) |
| `help-trading` | print this file |
| `cd /root/lumibot && docker compose up -d --build` | rebuild the Alpaca bot after a strategy change |

## Inside Claude Code (as claude-ops)
| Type | Does |
|---|---|
| `/status` | read only state of everything, open items |
| `/gate` | why V3 has or has not traded (BTC gate + pair conditions) |
| `/root` | get one block to paste as root for a change it cannot make |
| `/handover` | update docs/HANDOVER.md and push |
| `/exit` | leave Claude Code |
| plain words | "what did Alpaca do on Monday", "show me the diff before applying" |

## Telegram (phone)
Freqtrade bot: `/status`, `/profit`, `/daily`, `/stopentry` (no new entries, keep managing open ones), `/reload_config`.
Alpaca messages arrive on their own: "[Alpaca paper] ..." for starts, fills, rejections and the daily summary.
"[Weekly audit] ..." every Sunday about 09:18 Kuwait.

## Dashboard
http://100.99.81.45:8501 over Tailscale (iPhone, iPad, laptop). Tabs: Freqtrade, Alpaca, Stock Check, Robinhood, then Risk, Performance, Strategies, Trades, Health, Signals. Sidebar (top left arrows on phone) for time zone, systems, date range.

## Rules that never change
Dry run and paper until a written go live. Nothing automated on Robinhood. New strategies are new files. Secrets stay on the server. The agent shows a diff and waits for "yes, apply"; root commands come from you.
