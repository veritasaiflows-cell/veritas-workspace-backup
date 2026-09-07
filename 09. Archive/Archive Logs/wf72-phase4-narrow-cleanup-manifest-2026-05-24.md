# WF72 Phase 4 Narrow Cleanup Manifest - 2026-05-24

- Generated UTC: `2026-05-24T23:55:41Z`
- Status: **applied; validators complete with expected boundary warnings**
- Moves: 13 total / 6 promoted / 7 archived
- Deletes: 0

## Moves

| Source | Destination | Kind | SHA-256 preserved | JSON companions retained |
|---|---|---|---:|---|
| `tmp/clawhub-paper-trading-skill-scout-2026-05-19.md` | `06. Playbooks/Project Continuity/Workflow 67 - Paper Trading Skill Scout - 2026-05-19.md` | promotion | True | - |
| `tmp/defense-capital-base-closeout-audit-2026-05-18.md` | `08. Audits/Defense and Capital Base Closeout Audit - 2026-05-18.md` | promotion | True | - |
| `tmp/defense-capital-base-integration-summary-2026-05-18.md` | `06. Playbooks/Project Continuity/Workflow 64 - Defense and Capital Base Integration Summary - 2026-05-18.md` | promotion | True | - |
| `tmp/deployment-build-final-executive-packet-2026-05-17.md` | `03. Portfolio/Deployment Build Executive Packet - 2026-05-17.md` | promotion | True | - |
| `tmp/financial-canon-cron-authority-scan.md` | `08. Audits/Financial Canon Cron Authority Scan - 2026-05-23.md` | promotion | True | tmp/financial-canon-cron-authority-scan.json |
| `tmp/goog-ir-capture-vs-fundamental-reconciliation-2026-05-19.md` | `08. Audits/GOOG IR Capture vs Fundamental Reconciliation - 2026-05-19.md` | promotion | True | tmp/goog-ir-capture-vs-fundamental-reconciliation-2026-05-19.json |
| `tmp/active-ref-helper-disposition-2026-05-19.md` | `09. Archive/Archive Logs/wf72-prior-cleanup-proof/active-ref-helper-disposition-2026-05-19.md` | archive | True | tmp/active-ref-helper-disposition-2026-05-19.json |
| `tmp/archive-apply-manifest-latest.md` | `09. Archive/Archive Logs/prior-archive-apply/archive-apply-manifest-latest.md` | archive | True | tmp/archive-apply-manifest-latest.json |
| `tmp/archive-candidate-apply-manifest-2026-05-19.md` | `09. Archive/Archive Logs/prior-archive-apply/archive-candidate-apply-manifest-2026-05-19.md` | archive | True | tmp/archive-candidate-apply-manifest-2026-05-19.json |
| `tmp/archive-candidate-apply-result-2026-05-19.md` | `09. Archive/Archive Logs/prior-archive-apply/archive-candidate-apply-result-2026-05-19.md` | archive | True | tmp/archive-candidate-apply-result-2026-05-19.json |
| `tmp/archive-reference-second-pass.md` | `09. Archive/Archive Logs/prior-archive-reference-audits/archive-reference-second-pass.md` | archive | True | tmp/archive-reference-second-pass.json |
| `tmp/claude-weekly-macro-snapshot-contract-prompt.md` | `09. Archive/Manual IC Prompts - Archived/claude-weekly-macro-snapshot-contract-prompt.md` | archive | True | - |
| `tmp/claude-weekly-macro-w20-hard-judgment-prompt.md` | `09. Archive/Manual IC Prompts - Archived/claude-weekly-macro-w20-hard-judgment-prompt.md` | archive | True | - |

## Reference updates

- `08. Audits/Defense and Capital Base Closeout Audit - 2026-05-18.md`
- `scripts/intraday_entry_watcher.py`
- `tmp/alpaca-paper-readiness/full-portfolio-scope.wf67-100k-v1.json`
- `tmp/alpaca-paper-readiness/paper-basket-request.tranche0-dry-run.json`
- `tmp/review-packets/ita-vxus-execution-readiness-packets.json`
- `tmp/review-packets/ita-vxus-execution-readiness-packets.md`
- `tmp/review-packets/ph-lin-execution-readiness-packets.json`
- `tmp/review-packets/ph-lin-execution-readiness-packets.md`

## Rollback route

Move each destination back to its source path and verify the listed source SHA-256 in the JSON manifest. No deletes are involved.

## Posture-only boundaries

- `.claude/` not moved; document as runtime exception or handle only with explicit config/runtime cleanup approval.
- `tmp/sql-canon-cache-rollback-phase3c.py` not moved; proof-critical and referenced by artifact index tests.

## Validation

- `python scripts\workspace_boundary_check.py`: warning, 6 findings / 2 warnings / 4 info. Expected remaining warnings: `.claude/` and `tmp/sql-canon-cache-rollback-phase3c.py`.
- `python scripts\dashboard_truth_lint.py`: ok, 0 warnings / 1 info.
- `python scripts\artifact_index.py incremental`: ok, changed_or_new=0, removed=0.
- `python scripts\artifact_index.py validate`: ok, 28 checks / 0 failed / stale=0.
- Direct path verification: 13 destinations exist, 0 source Markdown residues remain in `tmp/` for this packet.
- `python -m py_compile scripts\intraday_entry_watcher.py`: ok.
