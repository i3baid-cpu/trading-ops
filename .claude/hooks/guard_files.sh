#!/usr/bin/env bash
# PreToolUse guard for Edit/Write: existing strategy files are history; live configs and secrets are off limits.
input=$(cat)
path=$(printf '%s' "$input" | python3 -c 'import json,sys; d=json.load(sys.stdin).get("tool_input",{}); print(d.get("file_path") or d.get("path") or "")' 2>/dev/null)
case "$path" in
  */MemeSleeveV1.py|*/MemeSleeveV2.py|*/MemeSleeveV3.py|*/sma_cross.py)
    echo "BLOCKED: $path is an existing strategy file and stays unchanged; create a new versioned file instead (CLAUDE.md)." >&2; exit 2;;
  */.env|/root/freqtrade/config.json|/root/lumibot/config.json)
    echo "BLOCKED: $path is a live config or secrets file. Propose the change as a diff for Abdullah to apply as root." >&2; exit 2;;
esac
exit 0
