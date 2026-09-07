# Cyber-Security Daily Audit

- Generated at: 2026-09-07T00:12:03Z
- Status: **CRITICAL**
- Stop line: **true**
- Operator action required: **true**
- Next action: Inspect the attached findings before trusting the workspace posture.

## Summary
- Critical findings: 1
- Warning findings: 13
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
- **workspace_governance_truth_check** — critical
- **windows_firewall** — info
- **windows_antivirus** — info

## Findings
- **info** `config.channels` — Approved chat channel posture is active.
- **warning** `config.browser` — Browser surface is enabled or allowlisted. | Next: Keep browser disabled and off the allowlist unless interactive automation is intentionally needed.
- **info** `config.gateway` — Gateway bind remains loopback with no reverse-proxy requirement.
- **info** `exec_approvals` — Main-agent exec approvals remain narrow exact-command entries.
- **info** `openclaw_security_audit_basic` — Attack surface summary
- **warning** `openclaw_security_audit_basic` — Reverse proxy headers are not trusted | Next: Set gateway.trustedProxies to your proxy IPs or keep the Control UI local-only.
- **warning** `openclaw_security_audit_basic` — Exec security=full is configured | Next: Prefer tools.exec.mode="ask" or "allowlist", and reserve "full" for tightly scoped break-glass agents only.
- **warning** `openclaw_security_audit_basic` — Some configured models are below recommended tiers | Next: Use the latest, top-tier model for any bot with tools or untrusted inboxes. Avoid Haiku tiers; prefer GPT-5+ and Claude 4.5+.
- **warning** `openclaw_security_audit_basic` — Potential multi-user setup detected (personal-assistant model warning) | Next: If users may be mutually untrusted, split trust boundaries (separate gateways + credentials, ideally separate OS users/hosts). If you intentionally run shared-user access, set agents.defaults.sandbox.mode="all", keep tools.fs.workspaceOnly=true, deny runtime/fs/web tools unless required, and keep personal/private identities + credentials off that runtime.
- **warning** `openclaw_security_audit_basic` — Plugin index includes unpinned npm specs | Next: Pin install specs to exact versions (for example, `@scope/pkg@1.2.3`) for higher supply-chain stability.
- **info** `openclaw_security_audit_deep` — Attack surface summary
- **warning** `openclaw_security_audit_deep` — Reverse proxy headers are not trusted | Next: Set gateway.trustedProxies to your proxy IPs or keep the Control UI local-only.
- **warning** `openclaw_security_audit_deep` — Exec security=full is configured | Next: Prefer tools.exec.mode="ask" or "allowlist", and reserve "full" for tightly scoped break-glass agents only.
- **warning** `openclaw_security_audit_deep` — Some configured models are below recommended tiers | Next: Use the latest, top-tier model for any bot with tools or untrusted inboxes. Avoid Haiku tiers; prefer GPT-5+ and Claude 4.5+.
- **warning** `openclaw_security_audit_deep` — Potential multi-user setup detected (personal-assistant model warning) | Next: If users may be mutually untrusted, split trust boundaries (separate gateways + credentials, ideally separate OS users/hosts). If you intentionally run shared-user access, set agents.defaults.sandbox.mode="all", keep tools.fs.workspaceOnly=true, deny runtime/fs/web tools unless required, and keep personal/private identities + credentials off that runtime.
- **warning** `openclaw_security_audit_deep` — Plugin index includes unpinned npm specs | Next: Pin install specs to exact versions (for example, `@scope/pkg@1.2.3`) for higher supply-chain stability.
- **info** `skills_check` — Skill inventory check completed.
- **warning** `openclaw_doctor` — Doctor did not exit cleanly inside the timeout window. | Next: Treat the partial output as advisory and rerun manually if runtime health is in doubt.
- **warning** `workspace_boundary_check` — workspace_boundary_check returned warning-grade output. | Next: Review the listed findings and decide whether cleanup or documentation is needed.
- **info** `dashboard_truth_lint` — dashboard_truth_lint passed cleanly.
- **critical** `workspace_governance_truth_check` — workspace_governance_truth_check returned critical. | Next: Inspect the attached findings before trusting the workspace posture.
- **info** `windows_firewall` — All Windows Firewall profiles are enabled.
- **info** `windows_antivirus` — A third-party antivirus product is registered while Defender realtime protection is off.
