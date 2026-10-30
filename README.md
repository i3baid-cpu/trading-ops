# trading-ops

Source of truth for Abdullah's personal algorithmic trading setup: strategies under test, secrets free
configs, the read only Trading Command Center dashboard, deployment files for the Hetzner VPS, and audit
results. Started from the Oct 30 2026 audit.

| Folder | Contents |
|---|---|
| dashboard/ | Streamlit + Plotly read only dashboard (seven screens). See dashboard/README.md |
| fixes/ | Strategy and config versions produced by the audit: MemeSleeveV2 (rejected by backtest), Alpaca TrendFilter (passed, on paper), Robinhood RULES_v2 |
| deploy/ | VPS deployment: dashboard compose file bound to localhost and the Tailscale IP, deploy instructions |
| docs/ | Specs and screenshots; LIVE_LOADER_SPEC.md is the open task for the VPS agent |
| results/ | Backtests and weekly audits, pushed from the VPS |

Status on 31 Oct 2026: Freqtrade runs MemeSleeveV3 in dry run (forward test); Lumibot runs TrendFilter on
paper with a $1,000 sleeve; Robinhood unchanged pending the ETH decision. Nothing trades real money by rule.
