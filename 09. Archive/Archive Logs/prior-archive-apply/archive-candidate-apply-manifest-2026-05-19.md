# Archive Candidate Apply Manifest - 2026-05-19

**Status:** read-only approval packet. No files were moved, deleted, archived, rewired, or executed.

## Authority

- `review_only`: `True`
- `apply_allowed`: `False`
- `moves_allowed`: `False`
- `deletes_allowed`: `False`
- `archive_allowed_without_owner_approval`: `False`
- `paper_readiness_touched`: `False`
- `brokerage_or_account_action_allowed`: `False`
- `trade_or_execution_authority`: `False`
- `note`: `This manifest is an approval packet only. It proposes archive targets but performs no file moves, deletes, rewires, execution, or authority widening.`

## Summary

- **families:** 43
- **candidate_files:** 156
- **candidate_bytes:** 41140115
- **active_exact_reference_found:** 47
- **active_basename_reference_found:** 3
- **active_no_static_reference_found:** 106
- **historical_or_tmp_exact_reference_found:** 154
- **current_window_overlaps:** 0

- **Proposed archive root if later approved:** `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive`

## Family summary

| Priority | Family | Matched | Retained | Candidates | Active refs | Historical/tmp refs | Reason |
|---:|---|---:|---:|---:|---|---|---|
| 1 | `__pycache__` | 1 | 0 | 1 | no_static_reference_found:1 | exact_reference_found:1 | Generated Python cache; no durable proof value. |
| 1 | `tmp_one_off_scripts` | 23 | 0 | 23 | exact_reference_found:6, no_static_reference_found:17 | exact_reference_found:21, no_static_reference_found:2 | One-off helper scripts live in tmp; durable helpers belong in scripts, stale helpers belong in archive. |
| 2 | `tmp_js_helpers` | 1 | 0 | 1 | no_static_reference_found:1 | exact_reference_found:1 | One-off JS helper/config patch residue in tmp. |
| 2 | `core-file-backups` | 0 | 0 | 0 | - | - | Backup folder; useful short-term rollback proof but should not stay active tmp forever. |
| 2 | `cron-backups` | 0 | 0 | 0 | - | - | Backup folder; useful short-term rollback proof but should not stay active tmp forever. |
| 2 | `wf59-backups` | 5 | 0 | 5 | exact_reference_found:1, no_static_reference_found:4 | exact_reference_found:5 | Backup folder; useful short-term rollback proof but should not stay active tmp forever. |
| 2 | `wf60-backups` | 8 | 0 | 8 | no_static_reference_found:8 | exact_reference_found:8 | Backup folder; useful short-term rollback proof but should not stay active tmp forever. |
| 2 | `wf61-backups` | 4 | 0 | 4 | no_static_reference_found:4 | exact_reference_found:4 | Backup folder; useful short-term rollback proof but should not stay active tmp forever. |
| 3 | `authority_window_dry_runs` | 3 | 0 | 3 | no_static_reference_found:3 | exact_reference_found:3 | Old dry-run proof family, likely superseded by current validators/artifacts. |
| 3 | `explicit_window_dry_runs` | 3 | 0 | 3 | no_static_reference_found:3 | exact_reference_found:3 | Old dry-run proof family, likely superseded by current validators/artifacts. |
| 3 | `phase3_dry_runs` | 3 | 0 | 3 | no_static_reference_found:3 | exact_reference_found:3 | Old dry-run proof family, likely superseded by current validators/artifacts. |
| 3 | `wf58_dry_runs` | 3 | 0 | 3 | no_static_reference_found:3 | exact_reference_found:3 | Old dry-run proof family, likely superseded by current validators/artifacts. |
| 3 | `wf53_dry_runs` | 3 | 0 | 3 | no_static_reference_found:3 | exact_reference_found:3 | Old dry-run proof family, likely superseded by current validators/artifacts. |
| 3 | `openclaw_schema_dumps` | 2 | 0 | 2 | no_static_reference_found:2 | exact_reference_found:2 | OpenClaw schema/config patch dumps from prior config work. |
| 3 | `config_patch_dumps` | 5 | 0 | 5 | no_static_reference_found:5 | exact_reference_found:5 | OpenClaw schema/config patch dumps from prior config work. |
| 3 | `config_patch_dumps_reset` | 1 | 0 | 1 | no_static_reference_found:1 | exact_reference_found:1 | OpenClaw schema/config patch dumps from prior config work. |
| 3 | `config_patch_dumps_codex` | 1 | 0 | 1 | no_static_reference_found:1 | exact_reference_found:1 | OpenClaw schema/config patch dumps from prior config work. |
| 4 | `wf30s_reports` | 4 | 0 | 4 | basename_reference_found:1, exact_reference_found:3 | exact_reference_found:4 | Superseded workflow proof reports should move to durable archive/evidence if no longer current. |
| 4 | `wf40s_reports` | 11 | 0 | 11 | exact_reference_found:1, no_static_reference_found:10 | exact_reference_found:11 | Superseded workflow proof reports should move to durable archive/evidence if no longer current. |
| 4 | `wf50s_reports` | 16 | 0 | 16 | exact_reference_found:10, no_static_reference_found:6 | exact_reference_found:16 | Superseded workflow proof reports should move to durable archive/evidence if no longer current. |
| 4 | `wf60s_reports` | 7 | 0 | 7 | no_static_reference_found:7 | exact_reference_found:7 | Superseded workflow proof reports should move to durable archive/evidence if no longer current. |
| 4 | `wf30s_json_reports` | 0 | 0 | 0 | - | - | Superseded workflow proof reports should move to durable archive/evidence if no longer current. |
| 4 | `wf40s_json_reports` | 3 | 0 | 3 | exact_reference_found:2, no_static_reference_found:1 | exact_reference_found:3 | Superseded workflow proof reports should move to durable archive/evidence if no longer current. |
| 4 | `wf50s_json_reports` | 4 | 0 | 4 | exact_reference_found:3, no_static_reference_found:1 | exact_reference_found:4 | Superseded workflow proof reports should move to durable archive/evidence if no longer current. |
| 4 | `wf60s_json_reports` | 0 | 0 | 0 | - | - | Superseded workflow proof reports should move to durable archive/evidence if no longer current. |
| 4 | `state_history_samples` | 2 | 0 | 2 | basename_reference_found:1, no_static_reference_found:1 | exact_reference_found:2 | Tmp state-history samples duplicate durable data/state-history. |
| 4 | `state_history_test_jsonl` | 1 | 0 | 1 | basename_reference_found:1 | exact_reference_found:1 | Tmp state-history samples duplicate durable data/state-history. |
| 4 | `tmp_state_history_jsonl` | 1 | 0 | 1 | exact_reference_found:1 | exact_reference_found:1 | Tmp state-history samples duplicate durable data/state-history. |
| 4 | `source_download_xlsx` | 2 | 0 | 2 | no_static_reference_found:2 | exact_reference_found:2 | Source downloads/extractions should either be durable evidence or archived, not loose active tmp. |
| 4 | `source_download_pdf` | 5 | 0 | 5 | no_static_reference_found:5 | exact_reference_found:5 | Source downloads/extractions should either be durable evidence or archived, not loose active tmp. |
| 4 | `source_download_csv` | 10 | 0 | 10 | exact_reference_found:9, no_static_reference_found:1 | exact_reference_found:10 | Source downloads/extractions should either be durable evidence or archived, not loose active tmp. |
| 4 | `source_download_html` | 1 | 0 | 1 | no_static_reference_found:1 | exact_reference_found:1 | Source downloads/extractions should either be durable evidence or archived, not loose active tmp. |
| 2 | `portfolio_config_backups` | 5 | 0 | 5 | no_static_reference_found:5 | exact_reference_found:5 | Rollback/config validation residue accumulates quickly. |
| 2 | `portfolio_snapshot_backups` | 2 | 0 | 2 | no_static_reference_found:2 | exact_reference_found:2 | Rollback/config validation residue accumulates quickly. |
| 2 | `investor_profile_backups` | 1 | 0 | 1 | no_static_reference_found:1 | exact_reference_found:1 | Rollback/config validation residue accumulates quickly. |
| 2 | `model_portfolio_backups` | 1 | 0 | 1 | no_static_reference_found:1 | exact_reference_found:1 | Rollback/config validation residue accumulates quickly. |
| 2 | `portfolio_config_validation_residue` | 1 | 0 | 1 | no_static_reference_found:1 | exact_reference_found:1 | Rollback/config validation residue accumulates quickly. |
| 2 | `portfolio_config_validation_residue2` | 1 | 0 | 1 | no_static_reference_found:1 | exact_reference_found:1 | Rollback/config validation residue accumulates quickly. |
| 2 | `portfolio_config_jsonlint_tmp` | 1 | 0 | 1 | no_static_reference_found:1 | exact_reference_found:1 | Rollback/config validation residue accumulates quickly. |
| 5 | `sector_dashboard_outputs` | 5 | 0 | 5 | exact_reference_found:5 | exact_reference_found:5 | Old sector/research suite outputs not indexed in current window. |
| 5 | `small_mid_cap_outputs` | 2 | 0 | 2 | exact_reference_found:2 | exact_reference_found:2 | Old sector/research suite outputs not indexed in current window. |
| 5 | `ticker_monitoring_outputs` | 2 | 0 | 2 | exact_reference_found:2 | exact_reference_found:2 | Old sector/research suite outputs not indexed in current window. |
| 5 | `research_freshness_outputs` | 2 | 0 | 2 | exact_reference_found:2 | exact_reference_found:2 | Old sector/research suite outputs not indexed in current window. |

## Candidate details

### __pycache__

Reason: Generated Python cache; no durable proof value.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/__pycache__/update_cron_expansion_ledger.cpython-313.pyc` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/__pycache__/update_cron_expansion_ledger.cpython-313.pyc` | 7908 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### tmp_one_off_scripts

Reason: One-off helper scripts live in tmp; durable helpers belong in scripts, stale helpers belong in archive.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/add_missing_execution_board_sections_2026_05_18.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/add_missing_execution_board_sections_2026_05_18.py` | 3710 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/add_vxus_tracked_universe_2026_05_18.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/add_vxus_tracked_universe_2026_05_18.py` | 8259 | `no_static_reference_found` - | `exact_reference_found` tmp/cyber-security-daily-audit.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/apply_canon_freshness_sync_2026_05_18.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/apply_canon_freshness_sync_2026_05_18.py` | 4863 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/apply_closeout_updates.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/apply_closeout_updates.py` | 7486 | `no_static_reference_found` - | `exact_reference_found` tmp/cyber-security-daily-audit.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/build_lin_ita_ph_readiness.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/build_lin_ita_ph_readiness.py` | 13216 | `no_static_reference_found` - | `exact_reference_found` tmp/cyber-security-daily-audit.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/debug_current_dashboard.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/debug_current_dashboard.py` | 391 | `no_static_reference_found` - | `no_static_reference_found` - | `lower_static_reference_risk` |
| `tmp/debug_state_transition.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/debug_state_transition.py` | 1014 | `no_static_reference_found` - | `no_static_reference_found` - | `lower_static_reference_risk` |
| `tmp/dump_bands.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/dump_bands.py` | 230 | `exact_reference_found` 06. Playbooks/Project Continuity/Workflow 50 - Tmp Helper Archive Cleanup.md | `exact_reference_found` 08. Audits/Tmp Python Helper Promotion Review - 2026-05-09.md<br>08. Audits/WF40 Cyber-Security Scheduled Proof Report - 2026-05-09.md | `needs_manual_review` |
| `tmp/extract_relevant.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/extract_relevant.py` | 783 | `no_static_reference_found` - | `exact_reference_found` tmp/cyber-security-daily-audit.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/find_band_refs.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/find_band_refs.py` | 376 | `exact_reference_found` 06. Playbooks/Project Continuity/Workflow 50 - Tmp Helper Archive Cleanup.md | `exact_reference_found` 08. Audits/Tmp Python Helper Promotion Review - 2026-05-09.md<br>08. Audits/WF40 Cyber-Security Scheduled Proof Report - 2026-05-09.md | `needs_manual_review` |
| `tmp/find_disallowed_model_refs.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/find_disallowed_model_refs.py` | 1290 | `exact_reference_found` 06. Playbooks/Project Continuity/Workflow 50 - Tmp Helper Archive Cleanup.md | `exact_reference_found` 08. Audits/Tmp Python Helper Promotion Review - 2026-05-09.md<br>08. Audits/WF40 Cyber-Security Scheduled Proof Report - 2026-05-09.md | `needs_manual_review` |
| `tmp/find_disallowed_openclaw_refs.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/find_disallowed_openclaw_refs.py` | 1199 | `exact_reference_found` 06. Playbooks/Project Continuity/Workflow 50 - Tmp Helper Archive Cleanup.md | `exact_reference_found` 08. Audits/Tmp Python Helper Promotion Review - 2026-05-09.md<br>08. Audits/WF40 Cyber-Security Scheduled Proof Report - 2026-05-09.md | `needs_manual_review` |
| `tmp/find_model_refs.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/find_model_refs.py` | 1273 | `exact_reference_found` 06. Playbooks/Project Continuity/Workflow 50 - Tmp Helper Archive Cleanup.md | `exact_reference_found` 08. Audits/Tmp Python Helper Promotion Review - 2026-05-09.md<br>08. Audits/WF40 Cyber-Security Scheduled Proof Report - 2026-05-09.md | `needs_manual_review` |
| `tmp/fix_daily_note_entry.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/fix_daily_note_entry.py` | 1568 | `no_static_reference_found` - | `exact_reference_found` tmp/cyber-security-daily-audit.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/fix_vxus_daily_note_entry.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/fix_vxus_daily_note_entry.py` | 1115 | `no_static_reference_found` - | `exact_reference_found` tmp/cyber-security-daily-audit.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/log_ita_promotion_memory.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/log_ita_promotion_memory.py` | 1155 | `no_static_reference_found` - | `exact_reference_found` tmp/cyber-security-daily-audit.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/market_close_quick.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/market_close_quick.py` | 1805 | `exact_reference_found` 06. Playbooks/Project Continuity/Workflow 50 - Tmp Helper Archive Cleanup.md | `exact_reference_found` 08. Audits/Tmp Python Helper Promotion Review - 2026-05-09.md<br>08. Audits/WF40 Cyber-Security Scheduled Proof Report - 2026-05-09.md | `needs_manual_review` |
| `tmp/probe_ita.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/probe_ita.py` | 481 | `no_static_reference_found` - | `exact_reference_found` tmp/cyber-security-daily-audit.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/promote_ita_candidate_2026_05_18.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/promote_ita_candidate_2026_05_18.py` | 9913 | `no_static_reference_found` - | `exact_reference_found` tmp/cyber-security-daily-audit.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/update_ita_vxus_promotion.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/update_ita_vxus_promotion.py` | 1447 | `no_static_reference_found` - | `exact_reference_found` tmp/cyber-security-daily-audit.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf67_position_reconcile_once.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf67_position_reconcile_once.py` | 3551 | `no_static_reference_found` - | `exact_reference_found` tmp/cyber-security-daily-audit.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf67_submit_reconcile_once.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf67_submit_reconcile_once.py` | 3126 | `no_static_reference_found` - | `exact_reference_found` tmp/cyber-security-daily-audit-cron-proof.json<br>tmp/cyber-security-daily-audit.json | `lower_static_reference_risk` |
| `tmp/write_ita_promotion_artifact.py` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/write_ita_promotion_artifact.py` | 3917 | `no_static_reference_found` - | `exact_reference_found` tmp/cyber-security-daily-audit-cron-proof.json<br>tmp/cyber-security-daily-audit.json | `lower_static_reference_risk` |

### tmp_js_helpers

Reason: One-off JS helper/config patch residue in tmp.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/patch-session-model.js` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/patch-session-model.js` | 633 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/tmp-artifact-ownership-audit-2026-05-18.md | `lower_static_reference_risk` |

### wf59-backups

Reason: Backup folder; useful short-term rollback proof but should not stay active tmp forever.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/wf59-backups/Active Workflows.before-wf59-closeout.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf59-backups/Active Workflows.before-wf59-closeout.md` | 15281 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf59-backups/Active Workflows.before-wf59.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf59-backups/Active Workflows.before-wf59.md` | 14228 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf59-backups/AGENTS.before-wf59.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf59-backups/AGENTS.before-wf59.md` | 12199 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf59-backups/openclaw.before-disable-telegram-and-compaction.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf59-backups/openclaw.before-disable-telegram-and-compaction.json` | 4458 | `exact_reference_found` 06. Playbooks/Project Continuity/Workflow 59 - Continuity and Compaction Hardening.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `needs_manual_review` |
| `tmp/wf59-backups/TOOLS.before-telegram-disable.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf59-backups/TOOLS.before-telegram-disable.md` | 12406 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### wf60-backups

Reason: Backup folder; useful short-term rollback proof but should not stay active tmp forever.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/wf60-backups/Active Workflows.before-truth-surface.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf60-backups/Active Workflows.before-truth-surface.md` | 15332 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf60-backups/Operating Model.before-truth-surface.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf60-backups/Operating Model.before-truth-surface.md` | 11022 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf60-backups/Operating Procedures README.before-truth-surface.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf60-backups/Operating Procedures README.before-truth-surface.md` | 1820 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf60-backups/Procedure Index.before-truth-surface.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf60-backups/Procedure Index.before-truth-surface.md` | 2991 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf60-backups/research_freshness_opportunity_review.py.20260513-222414.bak` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf60-backups/research_freshness_opportunity_review.py.20260513-222414.bak` | 17181 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf60-backups/Skill-to-Procedure Ownership Map.before-truth-surface.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf60-backups/Skill-to-Procedure Ownership Map.before-truth-surface.md` | 3134 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf60-backups/Startup Truth Index.before-truth-surface.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf60-backups/Startup Truth Index.before-truth-surface.md` | 5172 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf60-backups/test_research_freshness_opportunity_review.py.20260513-222414.bak` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf60-backups/test_research_freshness_opportunity_review.py.20260513-222414.bak` | 4815 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### wf61-backups

Reason: Backup folder; useful short-term rollback proof but should not stay active tmp forever.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/wf61-backups/2026-05-12.before-research-small-mid.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf61-backups/2026-05-12.before-research-small-mid.md` | 11398 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-reference-second-pass.md | `lower_static_reference_risk` |
| `tmp/wf61-backups/Active Workflows.before-research-small-mid.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf61-backups/Active Workflows.before-research-small-mid.md` | 18107 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf61-backups/README.before-small-mid-cap-regime-feed.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf61-backups/README.before-small-mid-cap-regime-feed.md` | 76590 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-reference-second-pass.md | `lower_static_reference_risk` |
| `tmp/wf61-backups/Workflow 61.before-small-mid-cap-regime-feed.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf61-backups/Workflow 61.before-small-mid-cap-regime-feed.md` | 5790 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-reference-second-pass.md | `lower_static_reference_risk` |

### authority_window_dry_runs

Reason: Old dry-run proof family, likely superseded by current validators/artifacts.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/authority-window-morning-dry-run.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/authority-window-morning-dry-run.txt` | 8708 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-reference-second-pass.md | `lower_static_reference_risk` |
| `tmp/authority-window-post-close-dry-run.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/authority-window-post-close-dry-run.txt` | 9178 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/authority-window-sunday-dry-run.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/authority-window-sunday-dry-run.txt` | 9498 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### explicit_window_dry_runs

Reason: Old dry-run proof family, likely superseded by current validators/artifacts.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/explicit-window-morning-dry-run.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/explicit-window-morning-dry-run.txt` | 8708 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/explicit-window-post-close-dry-run.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/explicit-window-post-close-dry-run.txt` | 9178 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/explicit-window-sunday-dry-run.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/explicit-window-sunday-dry-run.txt` | 9498 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### phase3_dry_runs

Reason: Old dry-run proof family, likely superseded by current validators/artifacts.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/phase3-morning-dry-run.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/phase3-morning-dry-run.txt` | 17418 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/phase3-post-close-dry-run.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/phase3-post-close-dry-run.txt` | 18358 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/phase3-sunday-dry-run.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/phase3-sunday-dry-run.txt` | 18998 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### wf58_dry_runs

Reason: Old dry-run proof family, likely superseded by current validators/artifacts.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/dry-run-morning-wf58.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/dry-run-morning-wf58.txt` | 23692 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/dry-run-post-close-wf58.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/dry-run-post-close-wf58.txt` | 27166 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/dry-run-sunday-wf58.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/dry-run-sunday-wf58.txt` | 25750 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### wf53_dry_runs

Reason: Old dry-run proof family, likely superseded by current validators/artifacts.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/wf53-morning-dryrun.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf53-morning-dryrun.txt` | 15522 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf53-postclose-dryrun.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf53-postclose-dryrun.txt` | 16416 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf53-sunday-dryrun.txt` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf53-sunday-dryrun.txt` | 16916 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### openclaw_schema_dumps

Reason: OpenClaw schema/config patch dumps from prior config work.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/openclaw-config-schema.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/openclaw-config-schema.json` | 4453366 | `no_static_reference_found` - | `exact_reference_found` tmp/cron-expansion-qa-retention-challenge.json<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/openclaw-schema.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/openclaw-schema.json` | 4739088 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/tmp-artifact-ownership-audit-2026-05-18.md | `lower_static_reference_risk` |

### config_patch_dumps

Reason: OpenClaw schema/config patch dumps from prior config work.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/set-context-391k.patch.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/set-context-391k.patch.json` | 76 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/set-gpt55-context-391k.patch.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/set-gpt55-context-391k.patch.json` | 216 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/set-model-catalog-gpt55-391k-full.patch.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/set-model-catalog-gpt55-391k-full.patch.json` | 742 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/set-model-catalog-gpt55-391k.patch.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/set-model-catalog-gpt55-391k.patch.json` | 440 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/set-model-catalog-replace-gpt55-391k.patch.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/set-model-catalog-replace-gpt55-391k.patch.json` | 765 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### config_patch_dumps_reset

Reason: OpenClaw schema/config patch dumps from prior config work.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/reset-compaction-defaults.patch.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/reset-compaction-defaults.patch.json` | 100 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/tmp-artifact-ownership-audit-2026-05-18.md | `lower_static_reference_risk` |

### config_patch_dumps_codex

Reason: OpenClaw schema/config patch dumps from prior config work.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/codex-context.patch.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/codex-context.patch.json` | 211 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/tmp-artifact-ownership-audit-2026-05-18.md | `lower_static_reference_risk` |

### wf30s_reports

Reason: Superseded workflow proof reports should move to durable archive/evidence if no longer current.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/wf37-first-postclose-brief-draft.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf37-first-postclose-brief-draft.md` | 1863 | `exact_reference_found` 06. Playbooks/WF37 Phase 4 First Writer Trial Proof - 2026-05-06.md | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-reference-second-pass.md | `needs_manual_review` |
| `tmp/wf37-first-premarket-brief-draft.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf37-first-premarket-brief-draft.md` | 1628 | `exact_reference_found` 06. Playbooks/WF37 Phase 4 First Writer Trial Proof - 2026-05-06.md | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-reference-second-pass.md | `needs_manual_review` |
| `tmp/wf37-safe-draft.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf37-safe-draft.md` | 496 | `exact_reference_found` scripts/README.md | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-reference-second-pass.md | `needs_manual_review` |
| `tmp/wf37-unsafe-draft.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf37-unsafe-draft.md` | 91 | `basename_reference_found` 06. Playbooks/WF37 Phase 3 Brief Lint and Guard Proof - 2026-05-06.md | `exact_reference_found` tmp/archive-suggestions.json<br>tmp/archive-suggestions.md | `needs_manual_review` |

### wf40s_reports

Reason: Superseded workflow proof reports should move to durable archive/evidence if no longer current.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/wf40-manual-proof-report.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf40-manual-proof-report.md` | 2857 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-suggestions.json | `lower_static_reference_risk` |
| `tmp/wf40-residual-exception-note.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf40-residual-exception-note.md` | 695 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-suggestions.json<br>tmp/archive-suggestions.md | `lower_static_reference_risk` |
| `tmp/wf41-router-contract-report.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf41-router-contract-report.md` | 3365 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-suggestions.json<br>tmp/archive-suggestions.md | `lower_static_reference_risk` |
| `tmp/wf42-capital-recommendation-report.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf42-capital-recommendation-report.md` | 4034 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-suggestions.json<br>tmp/archive-suggestions.md | `lower_static_reference_risk` |
| `tmp/wf43-post-cron-validation-report.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf43-post-cron-validation-report.md` | 2726 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-suggestions.json<br>tmp/archive-suggestions.md | `lower_static_reference_risk` |
| `tmp/wf43-repeat-proof-report.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf43-repeat-proof-report.md` | 2131 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-suggestions.json<br>tmp/archive-suggestions.md | `lower_static_reference_risk` |
| `tmp/wf43-state-history-report.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf43-state-history-report.md` | 4526 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-suggestions.json<br>tmp/archive-suggestions.md | `lower_static_reference_risk` |
| `tmp/wf44-implementation-report.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf44-implementation-report.md` | 3734 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-suggestions.json<br>tmp/archive-suggestions.md | `lower_static_reference_risk` |
| `tmp/wf45-implementation-report.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf45-implementation-report.md` | 4585 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-suggestions.json<br>tmp/archive-suggestions.md | `lower_static_reference_risk` |
| `tmp/wf46-implementation-report.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf46-implementation-report.md` | 4062 | `exact_reference_found` 06. Playbooks/Project Continuity/Workflow 46 - Run Summary Finalization Semantics Gate.md | `exact_reference_found` tmp/archive-suggestions.json<br>tmp/archive-suggestions.md | `needs_manual_review` |
| `tmp/wf47-implementation-report.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf47-implementation-report.md` | 4700 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-suggestions.json<br>tmp/archive-suggestions.md | `lower_static_reference_risk` |

### wf50s_reports

Reason: Superseded workflow proof reports should move to durable archive/evidence if no longer current.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/wf51-phase1-schema-reuse-scan.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf51-phase1-schema-reuse-scan.md` | 28173 | `exact_reference_found` 06. Playbooks/OpenClaw Parallel Pilot Queue.md<br>06. Playbooks/Project Continuity/Workflow 51 - Daily Fresh Intelligence and Price Trend Promotion Branch.md | `exact_reference_found` memory/2026-05-09.md<br>memory/.dreams/short-term-recall.json | `needs_manual_review` |
| `tmp/wf51-phase1-synthesis.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf51-phase1-synthesis.md` | 2396 | `exact_reference_found` 06. Playbooks/Project Continuity/Workflow 51 - Daily Fresh Intelligence and Price Trend Promotion Branch.md | `exact_reference_found` memory/2026-05-09.md<br>memory/.dreams/short-term-recall.json | `needs_manual_review` |
| `tmp/wf51-phase1-verifier-risk-scan.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf51-phase1-verifier-risk-scan.md` | 11819 | `exact_reference_found` 06. Playbooks/OpenClaw Parallel Pilot Queue.md<br>06. Playbooks/Project Continuity/Workflow 51 - Daily Fresh Intelligence and Price Trend Promotion Branch.md | `exact_reference_found` memory/2026-05-09.md<br>memory/.dreams/short-term-recall.json | `needs_manual_review` |
| `tmp/wf51-phase2-code-review-audit.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf51-phase2-code-review-audit.md` | 6358 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-suggestions.json<br>tmp/archive-suggestions.md | `lower_static_reference_risk` |
| `tmp/wf51-phase2-final-verifier.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf51-phase2-final-verifier.md` | 1993 | `exact_reference_found` 06. Playbooks/OpenClaw Parallel Pilot Queue.md<br>06. Playbooks/Project Continuity/Workflow 51 - Daily Fresh Intelligence and Price Trend Promotion Branch.md | `exact_reference_found` memory/2026-05-09.md<br>tmp/archive-suggestions.json | `needs_manual_review` |
| `tmp/wf51-phase3-authority-risk-audit.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf51-phase3-authority-risk-audit.md` | 14063 | `exact_reference_found` 06. Playbooks/OpenClaw Parallel Pilot Queue.md<br>06. Playbooks/Project Continuity/Workflow 51 - Daily Fresh Intelligence and Price Trend Promotion Branch.md | `exact_reference_found` memory/2026-05-10-0751.md<br>memory/.dreams/short-term-recall.json | `needs_manual_review` |
| `tmp/wf51-phase3-candidate-generator-readiness.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf51-phase3-candidate-generator-readiness.md` | 19584 | `exact_reference_found` 06. Playbooks/OpenClaw Parallel Pilot Queue.md<br>06. Playbooks/Project Continuity/Workflow 51 - Daily Fresh Intelligence and Price Trend Promotion Branch.md | `exact_reference_found` memory/.dreams/short-term-recall.json<br>tmp/archive-suggestions.json | `needs_manual_review` |
| `tmp/wf51-phase3-synthesis.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf51-phase3-synthesis.md` | 3211 | `exact_reference_found` 06. Playbooks/OpenClaw Parallel Pilot Queue.md<br>06. Playbooks/Project Continuity/Workflow 51 - Daily Fresh Intelligence and Price Trend Promotion Branch.md | `exact_reference_found` memory/2026-05-10-0751.md<br>memory/.dreams/short-term-recall.json | `needs_manual_review` |
| `tmp/wf51-phase3a-root-cause-fix.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf51-phase3a-root-cause-fix.md` | 2981 | `exact_reference_found` 06. Playbooks/Project Continuity/Workflow 51 - Daily Fresh Intelligence and Price Trend Promotion Branch.md | `exact_reference_found` tmp/archive-suggestions.json<br>tmp/archive-suggestions.md | `needs_manual_review` |
| `tmp/wf52-real-chain-proof-report.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf52-real-chain-proof-report.md` | 2651 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf53-orchestration-prep.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf53-orchestration-prep.md` | 13625 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf54-implementation-report.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf54-implementation-report.md` | 2007 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-reference-second-pass.md | `lower_static_reference_risk` |
| `tmp/wf54-main-verification-report.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf54-main-verification-report.md` | 1364 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf58-paper-dashboard-truth-gap-analysis.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf58-paper-dashboard-truth-gap-analysis.md` | 13395 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf59-continuity-sprawl-audit.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf59-continuity-sprawl-audit.md` | 2692 | `exact_reference_found` 06. Playbooks/Active Workflows.md<br>06. Playbooks/Project Continuity/Workflow 59 - Continuity and Compaction Hardening.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/wf60-backups/Active Workflows.before-truth-surface.md | `needs_manual_review` |
| `tmp/wf59-runtime-config-blocker.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf59-runtime-config-blocker.md` | 1571 | `exact_reference_found` 06. Playbooks/Project Continuity/Workflow 59 - Continuity and Compaction Hardening.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `needs_manual_review` |

### wf60s_reports

Reason: Superseded workflow proof reports should move to durable archive/evidence if no longer current.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/wf60-wf61-cron-payload-proposal.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf60-wf61-cron-payload-proposal.md` | 1932 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-reference-second-pass.md | `lower_static_reference_risk` |
| `tmp/wf62-cleanup-archive-plan.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf62-cleanup-archive-plan.md` | 4652 | `no_static_reference_found` - | `exact_reference_found` memory/2026-05-13.md<br>memory/.dreams/short-term-recall.json | `lower_static_reference_risk` |
| `tmp/wf65-claude-final-hardening-pass.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf65-claude-final-hardening-pass.md` | 5065 | `no_static_reference_found` - | `exact_reference_found` memory/2026-05-16-1801.md<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf67-claude-challenger-prompt.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf67-claude-challenger-prompt.md` | 5709 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf67-full-portfolio-safety-qa.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf67-full-portfolio-safety-qa.md` | 7146 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf67-full-portfolio-scope-contract-draft.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf67-full-portfolio-scope-contract-draft.md` | 10779 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/alpaca-paper-readiness/paper-basket-request.tranche0-dry-run.json | `lower_static_reference_risk` |
| `tmp/wf67-full-portfolio-validator-design.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf67-full-portfolio-validator-design.md` | 15473 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### wf40s_json_reports

Reason: Superseded workflow proof reports should move to durable archive/evidence if no longer current.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/wf40-manual-proof-report.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf40-manual-proof-report.json` | 3861 | `exact_reference_found` 06. Playbooks/IC Project Registry.md<br>06. Playbooks/Project Continuity/Workflow 40 - Cyber-Security Hardening and Bounded Daily Audit.md | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/tmp-archive-plan-2026-05-18.json | `needs_manual_review` |
| `tmp/wf43-post-cron-validation-report.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf43-post-cron-validation-report.json` | 2495 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/wf43-repeat-proof-report.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf43-repeat-proof-report.json` | 2725 | `exact_reference_found` 06. Playbooks/IC Project Registry.md<br>06. Playbooks/Project Continuity/Workflow 43 - State History and Review Outcome Retention.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `needs_manual_review` |

### wf50s_json_reports

Reason: Superseded workflow proof reports should move to durable archive/evidence if no longer current.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/wf52-real-chain-proof-report.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf52-real-chain-proof-report.json` | 2923 | `exact_reference_found` 06. Playbooks/IC Project Registry.md<br>06. Playbooks/Project Continuity/Workflow 52 - Earnings Date Source Confidence and Event Calendar Roll-Forward Automation.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `needs_manual_review` |
| `tmp/wf54-implementation-report.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf54-implementation-report.json` | 2075 | `no_static_reference_found` - | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-reference-second-pass.md | `lower_static_reference_risk` |
| `tmp/wf54-main-verification-report.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf54-main-verification-report.json` | 1472 | `exact_reference_found` 06. Playbooks/IC Project Registry.md<br>06. Playbooks/Project Continuity/Workflow 54 - Ticker Monitoring Performance Analytics v1.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `needs_manual_review` |
| `tmp/wf55-paper-outcome-ingest-proposal.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/wf55-paper-outcome-ingest-proposal.json` | 12743 | `exact_reference_found` 06. Playbooks/Project Continuity/Workflow 55 - Probability Readiness and Outcome Retention Gate.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `needs_manual_review` |

### state_history_samples

Reason: Tmp state-history samples duplicate durable data/state-history.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/state-history-v1-repeat-sample.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/state-history-v1-repeat-sample.json` | 85134 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/wf43-repeat-proof-report.json | `lower_static_reference_risk` |
| `tmp/state-history-v1-sample.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/state-history-v1-sample.json` | 85930 | `basename_reference_found` 06. Playbooks/Project Continuity/Workflow 43 - State History and Review Outcome Retention.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/wf43-state-history-report.md | `needs_manual_review` |

### state_history_test_jsonl

Reason: Tmp state-history samples duplicate durable data/state-history.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/state-history-test.jsonl` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/state-history-test.jsonl` | 85130 | `basename_reference_found` scripts/test_state_history_capture.py | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/wf43-state-history-report.md | `needs_manual_review` |

### tmp_state_history_jsonl

Reason: Tmp state-history samples duplicate durable data/state-history.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/state-history-v1.jsonl` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/state-history-v1.jsonl` | 42647 | `exact_reference_found` scripts/README.md<br>06. Playbooks/OpenClaw Parallel Pilot Queue.md<br>06. Playbooks/Project Continuity/Workflow 43 - State History and Review Outcome Retention.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/tmp-cleanup-report.json | `needs_manual_review` |

### source_download_xlsx

Reason: Source downloads/extractions should either be durable evidence or archived, not loose active tmp.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/baker-hughes-na-rig-count-2026-05-15.xlsx` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/baker-hughes-na-rig-count-2026-05-15.xlsx` | 7196675 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/ita-blackrock-data-download.xlsx` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/ita-blackrock-data-download.xlsx` | 1965369 | `no_static_reference_found` - | `exact_reference_found` tmp/build_lin_ita_ph_readiness.py<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### source_download_pdf

Reason: Source downloads/extractions should either be durable evidence or archived, not loose active tmp.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/dol-w20-source.pdf` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/dol-w20-source.pdf` | 451982 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/eia-w20-source.pdf` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/eia-w20-source.pdf` | 71754 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/ita-ishares-fact-sheet.pdf` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/ita-ishares-fact-sheet.pdf` | 193853 | `no_static_reference_found` - | `exact_reference_found` tmp/build_lin_ita_ph_readiness.py<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/linde-1q26-earnings-release-tables.pdf` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/linde-1q26-earnings-release-tables.pdf` | 368945 | `no_static_reference_found` - | `exact_reference_found` tmp/build_lin_ita_ph_readiness.py<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/vxus-vanguard-factsheet-F3369.pdf` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/vxus-vanguard-factsheet-F3369.pdf` | 453242 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/review-packets/vxus-entry-band-official-proof-2026-05-18.json | `lower_static_reference_risk` |

### source_download_csv

Reason: Source downloads/extractions should either be durable evidence or archived, not loose active tmp.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/ita-ishares-holdings.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/ita-ishares-holdings.csv` | 9913502 | `no_static_reference_found` - | `exact_reference_found` tmp/probe_ita.py<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/sector-dashboard-exposure-pivot.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/sector-dashboard-exposure-pivot.csv` | 812 | `exact_reference_found` scripts/README.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/wf61-backups/README.before-small-mid-cap-regime-feed.md | `needs_manual_review` |
| `tmp/sector-dashboard-leadership-pivot.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/sector-dashboard-leadership-pivot.csv` | 109 | `exact_reference_found` scripts/README.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/wf61-backups/README.before-small-mid-cap-regime-feed.md | `needs_manual_review` |
| `tmp/sector-dashboard-promotion-queue.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/sector-dashboard-promotion-queue.csv` | 1628 | `exact_reference_found` scripts/README.md | `exact_reference_found` tmp/research-freshness-opportunity-review.json<br>tmp/tmp-archive-plan-2026-05-18.json | `needs_manual_review` |
| `tmp/sector-dashboard-sector-table.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/sector-dashboard-sector-table.csv` | 2722 | `exact_reference_found` scripts/README.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/wf61-backups/README.before-small-mid-cap-regime-feed.md | `needs_manual_review` |
| `tmp/workbook-control-panel.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/workbook-control-panel.csv` | 4261 | `exact_reference_found` scripts/README.md<br>06. Playbooks/Minimum-Viable Workbook Schema.md<br>06. Playbooks/Workbook Export Contracts.md | `exact_reference_found` 08. Audits/WF38 Mission Control Follow-up Recommendation - 2026-05-06.md<br>memory/2026-04-29.md | `needs_manual_review` |
| `tmp/workbook-deployment-ranking.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/workbook-deployment-ranking.csv` | 4651 | `exact_reference_found` scripts/README.md<br>06. Playbooks/Minimum-Viable Workbook Schema.md<br>06. Playbooks/Workbook Export Contracts.md | `exact_reference_found` memory/2026-04-29.md<br>memory/.dreams/short-term-recall.json | `needs_manual_review` |
| `tmp/workbook-earnings-tracker.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/workbook-earnings-tracker.csv` | 230 | `exact_reference_found` scripts/README.md<br>06. Playbooks/Minimum-Viable Workbook Schema.md<br>06. Playbooks/Workbook Export Contracts.md | `exact_reference_found` memory/2026-04-29.md<br>memory/.dreams/short-term-recall.json | `needs_manual_review` |
| `tmp/workbook-technical-drift.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/workbook-technical-drift.csv` | 9536 | `exact_reference_found` scripts/README.md<br>06. Playbooks/Minimum-Viable Workbook Schema.md<br>06. Playbooks/Workbook Export Contracts.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/workbook-build-validation.json | `needs_manual_review` |
| `tmp/workbook-watchlist-board.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/workbook-watchlist-board.csv` | 20773 | `exact_reference_found` scripts/README.md<br>06. Playbooks/Minimum-Viable Workbook Schema.md<br>06. Playbooks/Workbook Export Contracts.md | `exact_reference_found` memory/2026-04-29.md<br>memory/.dreams/short-term-recall.json | `needs_manual_review` |

### source_download_html

Reason: Source downloads/extractions should either be durable evidence or archived, not loose active tmp.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/jpm-20260331-official.html` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/jpm-20260331-official.html` | 9164618 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### portfolio_config_backups

Reason: Rollback/config validation residue accumulates quickly.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/portfolio-config.before-10k-universe-20260518T191332Z.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/portfolio-config.before-10k-universe-20260518T191332Z.json` | 76557 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/portfolio-config.before-defense-sizing-20260518T184323Z.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/portfolio-config.before-defense-sizing-20260518T184323Z.json` | 73886 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/portfolio-config.before-ita-candidate-promotion-2026-05-18.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/portfolio-config.before-ita-candidate-promotion-2026-05-18.json` | 70530 | `no_static_reference_found` - | `exact_reference_found` tmp/promote_ita_candidate_2026_05_18.py<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/portfolio-config.before-vxus-entry-band-2026-05-18.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/portfolio-config.before-vxus-entry-band-2026-05-18.json` | 69870 | `no_static_reference_found` - | `exact_reference_found` memory/2026-05-18.md<br>memory/.dreams/short-term-recall.json | `lower_static_reference_risk` |
| `tmp/portfolio-config.before-vxus-tracked-universe-2026-05-18.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/portfolio-config.before-vxus-tracked-universe-2026-05-18.json` | 71424 | `no_static_reference_found` - | `exact_reference_found` tmp/add_vxus_tracked_universe_2026_05_18.py<br>tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### portfolio_snapshot_backups

Reason: Rollback/config validation residue accumulates quickly.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/Portfolio Snapshot.before-10k-universe-20260518T191332Z.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/Portfolio Snapshot.before-10k-universe-20260518T191332Z.md` | 13789 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |
| `tmp/Portfolio Snapshot.before-defense-sizing-20260518T184323Z.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/Portfolio Snapshot.before-defense-sizing-20260518T184323Z.md` | 11884 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### investor_profile_backups

Reason: Rollback/config validation residue accumulates quickly.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/Investor Profile.before-10k-universe-20260518T191332Z.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/Investor Profile.before-10k-universe-20260518T191332Z.md` | 3968 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### model_portfolio_backups

Reason: Rollback/config validation residue accumulates quickly.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/Model Portfolio.before-10k-universe-20260518T191332Z.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/Model Portfolio.before-10k-universe-20260518T191332Z.md` | 1650 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### portfolio_config_validation_residue

Reason: Rollback/config validation residue accumulates quickly.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/portfolio-config.validated.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/portfolio-config.validated.json` | 163004 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### portfolio_config_validation_residue2

Reason: Rollback/config validation residue accumulates quickly.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/portfolio-config.validation.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/portfolio-config.validation.json` | 157778 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### portfolio_config_jsonlint_tmp

Reason: Rollback/config validation residue accumulates quickly.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/portfolio-config.jsonlint.tmp` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/portfolio-config.jsonlint.tmp` | 164462 | `no_static_reference_found` - | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json | `lower_static_reference_risk` |

### sector_dashboard_outputs

Reason: Old sector/research suite outputs not indexed in current window.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/sector-dashboard-exposure-pivot.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/sector-dashboard-exposure-pivot.csv` | 812 | `exact_reference_found` scripts/README.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/wf61-backups/README.before-small-mid-cap-regime-feed.md | `needs_manual_review` |
| `tmp/sector-dashboard-leadership-pivot.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/sector-dashboard-leadership-pivot.csv` | 109 | `exact_reference_found` scripts/README.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/wf61-backups/README.before-small-mid-cap-regime-feed.md | `needs_manual_review` |
| `tmp/sector-dashboard-promotion-queue.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/sector-dashboard-promotion-queue.csv` | 1628 | `exact_reference_found` scripts/README.md | `exact_reference_found` tmp/research-freshness-opportunity-review.json<br>tmp/tmp-archive-plan-2026-05-18.json | `needs_manual_review` |
| `tmp/sector-dashboard-sector-table.csv` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/sector-dashboard-sector-table.csv` | 2722 | `exact_reference_found` scripts/README.md | `exact_reference_found` tmp/tmp-archive-plan-2026-05-18.json<br>tmp/wf61-backups/README.before-small-mid-cap-regime-feed.md | `needs_manual_review` |
| `tmp/sector-dashboard-suite.html` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/sector-dashboard-suite.html` | 16559 | `exact_reference_found` scripts/README.md<br>06. Playbooks/Active Workflows.md<br>06. Playbooks/Cron Run Ledger.md | `exact_reference_found` memory/.dreams/short-term-recall.json<br>tmp/research-freshness-opportunity-review.json | `needs_manual_review` |

### small_mid_cap_outputs

Reason: Old sector/research suite outputs not indexed in current window.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/small-mid-cap-regime-feed.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/small-mid-cap-regime-feed.json` | 27613 | `exact_reference_found` scripts/README.md<br>06. Playbooks/Cron Run Ledger.md<br>06. Playbooks/Project Continuity/Workflow 60 - Research Freshness and Opportunity Cron Automation.md | `exact_reference_found` tmp/probability-readiness-report.json<br>tmp/probability-readiness-validation.json | `needs_manual_review` |
| `tmp/small-mid-cap-regime-feed.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/small-mid-cap-regime-feed.md` | 6359 | `exact_reference_found` scripts/README.md<br>06. Playbooks/Project Continuity/Workflow 61 - Small Mid Cap Regime Feed and Candidate Sleeve.md<br>06. Playbooks/Research Department Reviews/Sector Diversification Review Packet - 2026-05-14.md | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-reference-second-pass.md | `needs_manual_review` |

### ticker_monitoring_outputs

Reason: Old sector/research suite outputs not indexed in current window.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/ticker-monitoring-performance.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/ticker-monitoring-performance.json` | 56119 | `exact_reference_found` scripts/README.md<br>06. Playbooks/Cron Run Ledger.md<br>06. Playbooks/IC Project Registry.md | `exact_reference_found` tmp/research-freshness-opportunity-review.json<br>tmp/tmp-archive-plan-2026-05-18.json | `needs_manual_review` |
| `tmp/ticker-monitoring-performance.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/ticker-monitoring-performance.md` | 461 | `exact_reference_found` scripts/README.md<br>06. Playbooks/Cron Run Ledger.md<br>06. Playbooks/Project Continuity/Workflow 54 - Ticker Monitoring Performance Analytics v1.md | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-reference-second-pass.md | `needs_manual_review` |

### research_freshness_outputs

Reason: Old sector/research suite outputs not indexed in current window.

| Path | Proposed archive path | Size | Active refs | Historical/tmp refs | Risk |
|---|---|---:|---|---|---|
| `tmp/research-freshness-opportunity-review.json` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/research-freshness-opportunity-review.json` | 33092 | `exact_reference_found` scripts/dashboard_payload.py<br>scripts/README.md<br>06. Playbooks/Active Workflows.md | `exact_reference_found` tmp/dashboard-data.json<br>tmp/dashboard-last.json | `needs_manual_review` |
| `tmp/research-freshness-opportunity-review.md` | `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-19-owner-approved-archive/tmp/research-freshness-opportunity-review.md` | 1269 | `exact_reference_found` scripts/README.md<br>06. Playbooks/Project Continuity/Workflow 60 - Research Freshness and Opportunity Cron Automation.md | `exact_reference_found` tmp/archive-reference-second-pass.json<br>tmp/archive-reference-second-pass.md | `needs_manual_review` |

## Stop lines

- Do not apply from this manifest without explicit owner approval.
- Do not delete first; archive first only after approval.
- Do not touch tmp/alpaca-paper-readiness/ or tmp/review-packets/ from this broad pass.
- Do not archive current-window indexed artifacts.
- Static orphan/manual status does not prove obsolescence.

## Validation plan if later approved

- `python scripts\current_window_artifact_index.py --window post-close --write`
- `python scripts\dashboard_run_summary_consumer.py --window post-close`
- `python scripts\validate_portfolio_config.py --strict`
- `python scripts\canon_drift_freshness_gate.py --write --strict-exit`
- `python scripts\workspace_boundary_check.py`
- `WF63/WF67 validators only if a later narrower approved pass touches Alpaca paper-readiness proof surfaces; this manifest intentionally excludes that family.`
