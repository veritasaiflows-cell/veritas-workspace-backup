# OpenClaw Doctor and Security Remediation - 2026-08-08

## Conclusion

The direct OpenClaw deep security audit improved from `0 critical / 3 warnings` to `0 critical / 2 warnings`. The removed warning was the unpinned Codex plugin specification. The two remaining direct-audit warnings are documented, condition-bound accepted risks for this one-trusted-operator, loopback-only deployment; neither should be hidden by a fictitious proxy or by breaking the approved local workspace operating model.

The former nine-row workspace warning ledger mixed duplicate basic/deep audit rows with Doctor, workspace-boundary, and database-governance decisions. Its corrected logical result is `5 total: 2 accepted risk, 3 open owner decisions`.

## Backups

- Config: `C:\Users\Veritas\.openclaw\backups\openclaw-pre-security-remediation-20260808.json`; SHA-256 matched the source at capture time.
- State database: `C:\Users\Veritas\.openclaw\backups\openclaw-state-pre-security-remediation-20260808.sqlite`; SQLite `quick_check` returned `ok`.
- No credential or secret value is recorded in this audit.

## Applied Remediation

| Area | Change | Result |
|---|---|---|
| Telegram sender gates | Populated `allowFrom` and `groupAllowFrom` from the existing paired owner record | One owner entry in each list; no channel or network exposure broadened |
| Helper model resilience | Converted six Terra helper model declarations to structured primary/fallback objects | Primary `openai/gpt-5.6-terra`; fallbacks `openai/gpt-5.5`, then `openai/gpt-5.4` |
| Bootstrap budget | Raised `agents.defaults.bootstrapTotalMaxChars` from 60,000 to 80,000 | Removed the Doctor 99%-capacity warning without removing doctrine |
| Codex plugin provenance | Reinstalled the current Codex plugin with exact version pin `@openclaw/codex@2026.7.1-1` | Unpinned-plugin security warning removed |
| TaskFlow residue | Cancelled 14 ended, blocked, zero-task historical smoke/benchmark flows through the supported TaskFlow command | `remaining blocked = 0`; no task or database deletion |
| Security warning ledger | Deduplicated equivalent basic/deep audit findings and added evidence-bound accepted-risk overlays | Five logical warnings instead of duplicated/mixed rows |
| Workspace boundary truth | Documented three governed data surfaces and taught the checker their bounded ownership | Removed false-positive warnings for `wf74-learning-loop-evals`, `workflow-checkpoints`, and `vector-memory-sources.json` |

## Direct Security Audit Decisions

1. **Reverse proxy headers are not trusted — accepted risk.** The gateway is bound to loopback and no reverse proxy is configured. Setting a fabricated trusted proxy would reduce truth and could create risk. Reopen if the gateway is exposed, proxied, tunneled, or delegated.
2. **Potential multi-user setup — accepted risk.** This remains a one-trusted-operator personal assistant. Telegram access is owner-allowlisted and mention-gated, the gateway is loopback-only, and full local tools are intentional. Reopen if another person gains access, a group becomes open, the gateway leaves loopback, or untrusted workloads share the boundary.

The machine-readable decisions are in `state/security-warning-decisions.json` and only apply while their exact evidence conditions remain true.

## Remaining Owner-Gated Decisions

### 1. Orphan transcript archive

Doctor found 21 orphan transcript files totaling 113,382 bytes. A content-free, exact-target packet is ready at `tmp/orphan-transcript-inventory-packet.json`. No file was renamed, archived, or deleted.

Exact approval phrase:

`Approve orphan transcript archive microbatch 4b08de346745553fcb45f4f50d279b4bd17b755a15ce6eb506eaf23fb316dc3d exactly as listed in tmp/orphan-transcript-inventory-packet.json.`

### 2. Workspace-boundary cleanup

The current boundary check has 16 warnings: `.pytest_cache/`, the stale root `lanes` snapshot, two root WF73 PostgreSQL pilot JSON files, the currently active `data/evals/` work surface, and 11 executable Python helpers under `tmp/`. These need reference review and an exact archive/move/delete packet; no cleanup was inferred from this review request.

### 3. Database lifecycle archive

The governance check has three archive-ready temporary SQLite candidates totaling 200,704 bytes. The DB lifecycle apply path requires a separate exact owner approval, backup/rollback, and post-apply proof. No database was archived or deleted.

## Other Doctor Findings That Need a Different Authority Path

- Anthropic OAuth was approaching expiry and Gemini CLI OAuth was expired. Refresh is interactive and must use the provider login flow.
- The authoritative secrets audit reports four plaintext secret-bearing records and three legacy OAuth records, with no unresolved references. Moving them to another file readable by the same unsandboxed agent would be security theater; meaningful remediation requires a real external secret backend or a narrower trust boundary.
- One recent session lacks a transcript, one old subagent session has stale Codex routing metadata, and Doctor sees the orphan files above. Broad `doctor --fix` was deliberately not used because it could prune or archive beyond the approved scope.
- Eleven cron model overrides are intentional migration-policy exceptions, and eleven agent-turn shell cron shapes are supported/informational rather than security failures.

## Validation

- `openclaw config validate`: passed after writes.
- `openclaw plugins doctor`: no plugin issues.
- `openclaw skills check`: 103 total, 66 eligible, 0 missing, 0 blocked.
- `openclaw security audit --deep --json`: `0 critical / 2 warnings / 1 info` after plugin pin.
- `scripts/test_security_warning_ledger.py`: passed.
- `scripts/test_workspace_boundary_check.py`: passed.
- Corrected ledger: `5 total / 3 open / 2 accepted risk`.

## Runtime Apply Note

The configuration and plugin changes require a gateway restart. Restart is deferred while another live WebChat workspace lane is running, to avoid interrupting unrelated work. The final closeout must record either clean post-restart runtime proof or this explicit pending state.
