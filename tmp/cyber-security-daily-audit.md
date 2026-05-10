# Cyber-Security Daily Audit

- Generated at: 2026-05-10T01:47:00Z
- Status: **WARNING**
- Stop line: **false**
- Operator action required: **true**
- Next action: Keep `channels` empty unless channel expansion is intentional.

## Summary
- Critical findings: 0
- Warning findings: 10
- Info findings: 9

## Checks
- **config_posture** — warning
- **exec_approvals_posture** — info
- **openclaw_security_audit_basic** — warning
- **openclaw_security_audit_deep** — warning
- **skills_inventory** — info
- **doctor_posture** — warning
- **workspace_boundary_check** — warning
- **dashboard_truth_lint** — info
- **workspace_governance_truth_check** — warning
- **windows_firewall** — info
- **windows_antivirus** — info

## Findings
- **warning** `config.channels` — Chat channels are enabled; intended posture is local Control UI only. | Next: Keep `channels` empty unless channel expansion is intentional.
- **warning** `config.commands.ownerAllowFrom` — Local Control UI sender allowlist is incomplete. | Next: Restore the expected local sender identifiers.
- **info** `config.browser` — Browser plugin is disabled and excluded from the allowlist.
- **warning** `config.model_runtime` — Default OpenAI model still routes through PI instead of the native Codex runtime. | Next: If native Codex execution is intended, use `openai/<model>` plus `agents.defaults.agentRuntime.id = "codex"`.
- **info** `config.gateway` — Gateway bind remains loopback with no reverse-proxy requirement.
- **info** `exec_approvals` — Main-agent exec approvals remain narrow exact-command entries.
- **info** `openclaw_security_audit_basic` — Attack surface summary
- **warning** `openclaw_security_audit_basic` — Reverse proxy headers are not trusted | Next: Set gateway.trustedProxies to your proxy IPs or keep the Control UI local-only.
- **warning** `openclaw_security_audit_basic` — Potential multi-user setup detected (personal-assistant model warning) | Next: If users may be mutually untrusted, split trust boundaries (separate gateways + credentials, ideally separate OS users/hosts). If you intentionally run shared-user access, set agents.defaults.sandbox.mode="all", keep tools.fs.workspaceOnly=true, deny runtime/fs/web tools unless required, and keep personal/private identities + credentials off that runtime.
- **info** `openclaw_security_audit_deep` — Attack surface summary
- **warning** `openclaw_security_audit_deep` — Reverse proxy headers are not trusted | Next: Set gateway.trustedProxies to your proxy IPs or keep the Control UI local-only.
- **warning** `openclaw_security_audit_deep` — Potential multi-user setup detected (personal-assistant model warning) | Next: If users may be mutually untrusted, split trust boundaries (separate gateways + credentials, ideally separate OS users/hosts). If you intentionally run shared-user access, set agents.defaults.sandbox.mode="all", keep tools.fs.workspaceOnly=true, deny runtime/fs/web tools unless required, and keep personal/private identities + credentials off that runtime.
- **info** `skills_check` — Skill inventory check completed.
- **warning** `openclaw_doctor` — Doctor did not exit cleanly inside the timeout window. | Next: Treat the partial output as advisory and rerun manually if runtime health is in doubt.
- **warning** `workspace_boundary_check` — workspace_boundary_check returned warning-grade output. | Next: Review the listed findings and decide whether cleanup or documentation is needed.
- **info** `dashboard_truth_lint` — dashboard_truth_lint passed cleanly.
- **warning** `workspace_governance_truth_check` — workspace_governance_truth_check returned warning-grade output. | Next: Review the listed findings and decide whether cleanup or documentation is needed.
- **info** `windows_firewall` — All Windows Firewall profiles are enabled.
- **info** `windows_antivirus` — A third-party antivirus product is registered while Defender realtime protection is off.
