# Deploying from this repository to the VPS

## One time: give the VPS read only access to the repository
As claude-ops on the VPS:
```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/trading-ops-deploy -C "vps-deploy"
cat ~/.ssh/trading-ops-deploy.pub
```
Add that public key in GitHub: repository trading-ops, Settings, Deploy keys, Add deploy key, read only. Then:
```bash
printf 'Host github.com\n  IdentityFile ~/.ssh/trading-ops-deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config
git clone git@github.com:i3baid-cpu/trading-ops.git ~/trading-ops
```

## Dashboard
The compose file expects the live files listed in deploy/docker-compose.dashboard.yml. Two of them are owned by root and must be readable by the container:
```bash
# as root
chmod 644 /root/lumibot/config.json
touch /root/lumibot/strategies/trend_filter_state.json
```
(The sqlite file and backtest_config.json are already readable.) Then, as root from ~claude-ops/trading-ops:
```bash
docker compose -f deploy/docker-compose.dashboard.yml up -d --build
docker logs --tail 20 trading-dashboard
```
Open http://100.99.81.45:8501 from a Tailscale device.

## Updating
```bash
cd ~/trading-ops && git pull
docker compose -f deploy/docker-compose.dashboard.yml up -d --build
```

## Strategies and configs
Copy from fixes/ to the live folders as described in fixes/DEPLOY.md. The live secret files never come back into the repository.
