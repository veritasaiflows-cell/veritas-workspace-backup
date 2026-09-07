# WF40 Manual Proof Report

- Generated at UTC: 2026-05-10T23:17:56Z
- Status: manual_proof_complete
- Proof status: ok
- Audit status: warning
- Audit stop line: false
- Manual proof, not ordinary cron: true
- Closure recommended: false
- Scheduled proof residue remains: true

## Verdict
Wrapper path manually proves clean execution: `proof_status=ok`, `artifact_fresh_for_runner=true`, `audit_exit_code=0`, `audit_status=warning`, `audit_stop_line=false`, and wrapper `errors=[]`.

Do **not** close WF40 solely from this manual run. The manual proof is healthy, but the ordinary scheduled repeat proof remains required.

## Command run
- `python scripts\cyber_security_daily_audit_cron_runner.py`

## Artifacts inspected
- `tmp\cyber-security-daily-audit-cron-proof.json`
- `tmp\cyber-security-daily-audit.json`
- `tmp\cyber-security-daily-audit.md`

## Artifacts written
- `tmp\wf40-manual-proof-report.md`
- `tmp\wf40-manual-proof-report.json`

## Errors
- None

## Critical findings
- None

## Warning findings (10)
- `config.channels` — Chat channels are enabled; intended posture is local Control UI only. | Next: Keep `channels` empty unless channel expansion is intentional.
- `config.commands.ownerAllowFrom` — Local Control UI sender allowlist is incomplete. | Next: Restore the expected local sender identifiers.
- `config.model_runtime` — Default OpenAI model still routes through PI instead of the native Codex runtime. | Next: If native Codex execution is intended, use `openai/<model>` plus `agents.defaults.agentRuntime.id = "codex"`.
- `openclaw_security_audit_basic` — Reverse proxy headers are not trusted. | Next: Set gateway.trustedProxies to your proxy IPs or keep the Control UI local-only.
- `openclaw_security_audit_basic` — Potential multi-user setup detected (personal-assistant model warning). | Next: Keep trust boundaries explicit; split gateways/credentials if users may be mutually untrusted.
- `openclaw_security_audit_deep` — Reverse proxy headers are not trusted. | Next: Set gateway.trustedProxies to your proxy IPs or keep the Control UI local-only.
- `openclaw_security_audit_deep` — Potential multi-user setup detected (personal-assistant model warning). | Next: Keep trust boundaries explicit; split gateways/credentials if users may be mutually untrusted.
- `openclaw_doctor` — Doctor did not exit cleanly inside the timeout window. | Next: Treat partial output as advisory and rerun manually if runtime health is in doubt.
- `workspace_boundary_check` — workspace_boundary_check returned warning-grade output. | Next: Review the listed findings and decide whether cleanup or documentation is needed.
- `workspace_governance_truth_check` — workspace_governance_truth_check returned warning-grade output. | Next: Review the listed findings and decide whether cleanup or documentation is needed.
