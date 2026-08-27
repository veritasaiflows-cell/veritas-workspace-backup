# Latest Agent Delta

Generated for the WF75/WF88 isolated-agent bootstrap factory lane.

## Current State

- `research-scout` and `qa-redteam` exist as persistent isolated agents.
- `finance-source-scout` and `finance-redteam` exist as persistent isolated agents for supervised finance support only.
- Active isolated agents have configured workspaces and dedicated `agentDir` paths.
- New agents should receive `BOOTSTRAP.md`, `agent.capabilities.json`, and the latest supervised template update feed when generated through `scripts\agent_bootstrap_generator.py`.
- External bindings remain disabled.
- Cross-agent messaging visibility was not enabled.
- Cron/watchdog schedules were not created.
- Telemetry capture depth was not expanded.
- Config, auth, credentials, runtime, channel, finance/account, and execution
  authority were not changed.

## Safe Next Actions

- Use `research-scout` for sourced market/service examples and vendor/tool maps.
- Use `qa-redteam` for independent critique before trusting an offer, SOP,
  demo, or claim.
- Run `scripts\agent_bootstrap_generator.py --agents all --write --validate`
  after any new isolated agent is explicitly created.
- Run `scripts\agent_bootstrap_linter.py --agents all --write --validate`
  before treating agent bootstrap packets as clean.
- For finance support agents, use the latest supervised packet template artifact:
  `tmp/agent-shadow/finance-agent-supervised-prompt-templates-20260706.json`.
- Future isolated-agent bootstraps must carry forward template lessons when the
  artifact exists: ticker echo validation, source URL/fetch-status proof,
  explicit `readiness_impact`, audit-only handling for order-style text, and
  demotion/remediation triggers for boundary violations.

## Owner-Gated Later Actions

- Cross-agent messaging visibility or agent-to-agent config.
- Telegram, Discord, email, webhook, or customer channel bindings.
- Cron/watchdog refresh schedules.
- Deeper telemetry capture or external telemetry export.
- Use of real customer data or client systems.
- Shared workspace writes beyond exact scoped file paths.

## Feed Boundary

Allowed feed inputs are metadata-only:

- OTEL status summaries and warning categories
- WF74 opportunity queues and blocker followups
- validator failure summaries
- PM job state
- lane closeout proof
- Skill Workshop proposal status

Forbidden feed inputs:

- raw prompts or responses
- hidden reasoning
- raw tool payloads
- secrets, headers, cookies, tokens, credentials
- customer/private/suitability/tax/retirement data
- brokerage/account data
- external telemetry export
