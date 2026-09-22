# Cyber-Security Daily Audit

- Generated at: 2026-09-22T00:14:25Z
- Status: **WARNING**
- Stop line: **false**
- Operator action required: **true**
- Next action: Keep browser disabled and off the allowlist unless interactive automation is intentionally needed.

## Summary
- Critical findings: 0
- Warning findings: 10
- Info findings: 7

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
- **info** `config.channels` — Approved chat channel posture is active.
- **warning** `config.browser` — Browser surface is enabled or allowlisted. | Next: Keep browser disabled and off the allowlist unless interactive automation is intentionally needed.
- **info** `config.gateway` — Gateway bind remains loopback with no reverse-proxy requirement.
- **info** `exec_approvals` — Main-agent exec approvals remain narrow exact-command entries.
- **warning** `openclaw_security_audit_basic` — Command error: timeout after 60s | Next: Verify CLI/runtime health and rerun the audit.
- **warning** `openclaw_security_audit_basic` — Audit output was not usable JSON: no stdout | Next: Inspect the raw stdout/stderr and rerun the audit.
- **warning** `openclaw_security_audit_basic` — Audit timed out. | Next: Rerun the audit manually and inspect Gateway health.
- **warning** `openclaw_security_audit_deep` — Command error: timeout after 90s | Next: Verify CLI/runtime health and rerun the audit.
- **warning** `openclaw_security_audit_deep` — Audit output was not usable JSON: no stdout | Next: Inspect the raw stdout/stderr and rerun the audit.
- **warning** `openclaw_security_audit_deep` — Audit timed out. | Next: Rerun the audit manually and inspect Gateway health.
- **info** `skills_check` — Skill inventory check completed.
- **warning** `openclaw_doctor` — Doctor did not exit cleanly inside the timeout window. | Next: Treat the partial output as advisory and rerun manually if runtime health is in doubt.
- **warning** `workspace_boundary_check` — workspace_boundary_check returned warning-grade output. | Next: Review the listed findings and decide whether cleanup or documentation is needed.
- **info** `dashboard_truth_lint` — dashboard_truth_lint passed cleanly.
- **warning** `workspace_governance_truth_check` — workspace_governance_truth_check returned warning-grade output. | Next: Review the listed findings and decide whether cleanup or documentation is needed.
- **info** `windows_firewall` — All Windows Firewall profiles are enabled.
- **info** `windows_antivirus` — A third-party antivirus product is registered while Defender realtime protection is off.
