#!/usr/bin/env bash
# Loads the handover and a short live status into every session's context.
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
echo "=== docs/HANDOVER.md (read this first; update it and push when state changes) ==="
cat docs/HANDOVER.md 2>/dev/null || echo "HANDOVER.md missing"
echo
echo "=== live status ==="
docker ps --format '{{.Names}}: {{.Status}}' 2>/dev/null || echo "docker not reachable"
git log --oneline -3 2>/dev/null
echo "Open the session by confirming in three lines: what runs where, the first open item, and whether anything needs root."
