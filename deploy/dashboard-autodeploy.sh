#!/usr/bin/env bash
# Pull the repository and rebuild ONLY the read-only dashboard container when main has moved.
# Never touches freqtrade or lumibot. Install once as root:
#   install -m 750 /root/trading-ops/deploy/dashboard-autodeploy.sh /usr/local/sbin/dashboard-autodeploy
#   ( crontab -l 2>/dev/null; echo "*/15 * * * * /usr/local/sbin/dashboard-autodeploy >> /var/log/dashboard-autodeploy.log 2>&1" ) | crontab -
set -euo pipefail
REPO=/root/trading-ops
cd "$REPO"
before=$(git rev-parse HEAD)
git fetch -q origin main
after=$(git rev-parse origin/main)
if [ "$before" = "$after" ]; then
  exit 0
fi
# refuse anything that is not a fast-forward of our local main (no history rewrites land here)
if ! git merge-base --is-ancestor "$before" "$after"; then
  echo "$(date -Is) refused: origin/main is not a fast-forward of $before"; exit 1
fi
git merge -q --ff-only origin/main
changed=$(git diff --name-only "$before" "$after" | grep -E '^(dashboard/|deploy/docker-compose.dashboard.yml)' || true)
if [ -z "$changed" ]; then
  echo "$(date -Is) pulled $after, no dashboard files changed"; exit 0
fi
echo "$(date -Is) dashboard changed ($before -> $after), rebuilding"
docker compose -f deploy/docker-compose.dashboard.yml up -d --build --quiet-pull 2>&1 | tail -3
sleep 20
if curl -fsS http://127.0.0.1:8501/_stcore/health >/dev/null; then
  echo "$(date -Is) dashboard healthy at $after"
else
  echo "$(date -Is) WARNING dashboard health check failed after rebuild"; docker logs --tail 20 trading-dashboard
fi
