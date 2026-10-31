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
The compose file mounts /root/freqtrade/user_data and /root/lumibot/strategies as read only directories, plus
/root/lumibot/config.json. The container runs as root, so no chmod or touch is needed; a missing or empty
trend_filter_state.json shows "no paper trades yet". The exact build and start commands for this VPS are in
results/dashboard_deploy_commands.md.

The Freqtrade API reconciliation check stays "Not available" unless FT_API_URL, FT_API_USERNAME and
FT_API_PASSWORD are given to the container; credentials never go into this repository.
Open http://100.99.81.45:8501 from a Tailscale device.

## Updating
```bash
cd ~/trading-ops && git pull
docker compose -f deploy/docker-compose.dashboard.yml up -d --build
```

## Strategies and configs
Copy from fixes/ to the live folders as described in fixes/DEPLOY.md. The live secret files never come back into the repository.
