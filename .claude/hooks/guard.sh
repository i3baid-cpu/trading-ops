#!/usr/bin/env bash
# PreToolUse guard for Bash. Blocks actions that change a running bot or move secrets unless the operator
# has explicitly approved in the current conversation. Exit 2 = block (stderr goes back to the model).
input=$(cat)
cmd=$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null)
block() { echo "BLOCKED by .claude/hooks/guard.sh: $1. Show Abdullah the exact command and the diff, and run it only after he answers 'yes, apply' in his own words; if it needs root, give him the block to paste as root and wait for 'done'." >&2; exit 2; }
# 1. things that change a running system
# Allowed only when the command carries the operator's approval verbatim, e.g.
#   sudo ft-swap-strategy MemeSleeveV3   # Abdullah approved: "yes swap to v3"
# The agent may add that comment only when Abdullah said yes in the current message.
if echo "$cmd" | grep -Eq 'docker[[:space:]]+(restart|stop|rm|kill)|docker[[:space:]]+compose.*(up|down|restart)|ft-swap-strategy'; then
  echo "$cmd" | grep -Eq '# Abdullah approved: ".+"' || block "restart / rebuild / strategy swap without a quoted approval comment"
fi
# 2. secrets and live configs
echo "$cmd" | grep -Eq '(^|[[:space:]/])\.env([[:space:]]|$)|/root/freqtrade/config\.json|TELEGRAM_TOKEN|ALPACA_API|jwt_secret' && \
  block "touches a secrets file or a live config"
# 3. live trading flags and order endpoints
echo "$cmd" | grep -Eiq 'dry_run["'"'"']?[[:space:]]*:[[:space:]]*false|"paper"[[:space:]]*:[[:space:]]*false|forceenter|forceexit|forcebuy|forcesell' && \
  block "would enable live trading or place an order"
# 4. force pushes and history rewrites
echo "$cmd" | grep -Eq 'git[[:space:]]+push.*(--force|-f[[:space:]])|git[[:space:]]+reset[[:space:]]+--hard|git[[:space:]]+rebase' && \
  block "rewrites git history"
exit 0
