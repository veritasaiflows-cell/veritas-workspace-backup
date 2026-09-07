# Script Guardrail/Evidence Inspection - 2026-05-19

Inspection-only pass for the first actionable script ownership batch. No scripts were executed; no files were moved, archived, deleted, wired into chain/cron, or finance-mutated.

## Authority

| Field | Value |
|---|---:|
| `inspection_only` | `true` |
| `scripts_executed` | `false` |
| `files_moved_deleted_archived` | `false` |
| `chain_or_cron_changed` | `false` |
| `finance_notes_or_portfolio_mutated` | `false` |
| `trade_account_or_paper_order_action` | `false` |

## Disposition table

| Script | Verdict | Active refs | CLI flags | Key contract |
|---|---|---:|---|---|
| `promotion_review_check.py` | retain_manual_guardrail; document in scripts README/manual guardrail surface; not archive; chain-tail candidate only after execution proof | 7 | `--out`, `--packet`, `--require-queue`, `--ticker`, `--write` | defs: load_json, parse_ts, age_hours, is_stale, find_record |
| `ranking_shadow_canon_check.py` | retain_manual_guardrail; document in scripts README/manual guardrail surface; not archive; chain-tail candidate only after execution proof | 3 | `--deployment-check` | defs: load_json, queue_contains, is_deployable_state, scan_deployment_check, check_packet |
| `canonical_freshness_patch.py` | retain_manual_patch_proposal_prototype; no apply authority; not chain/cron until candidate input contract is active | 9 | `--init-sample`, `--input`, `--output-dir` | defs: FreshnessClass, JudgmentImpact, ProposalStatus, EvidenceItem, PatchInput |
| `goog_official_ir_capture.py` | retain_temporarily; compare with current fundamental IR reconciliation and WF66 before deciding document-vs-archive | 4 | `--output` | defs: utc_now, rel, fetch_source, html_to_text, excerpt_around |
| `official_ir_capture_validator.py` | retain_temporarily; compare with current fundamental IR reconciliation and WF66 before deciding document-vs-archive | 4 | `--input`, `--output`, `--write` | defs: utc_now, load_json, add, validate_authority, validate_source |
| `sec_capital_freshness_review.py` | retain_manual_WF66_bridge; output/proposal authority must remain review-only; no chain/cron until validator proof | 5 | `--capital`, `--official-capture`, `--output`, `--sec`, `--ticker` | defs: utc_now, rel, load_json, latest_filing, concept_summary |
| `sec_capital_recommendation_bridge.py` | retain_manual_WF66_bridge; output/proposal authority must remain review-only; no chain/cron until validator proof | 4 | `--capital`, `--output`, `--sec` | defs: utc_now, rel, load_json, latest_filing, build_bridge |
| `sec_evidence_packet.py` | retain_manual_official_source_pair; candidate bounded smoke test; not archive; not cron yet | 4 | `--filing-limit`, `--forms`, `--markdown`, `--output`, `--tickers` | defs: utc_now, rel, sha256_file, latest_fact_unit, summarize_key_metrics |
| `sec_evidence_packet_validator.py` | retain_manual_official_source_pair; candidate bounded smoke test; not archive; not cron yet | 3 | `--input`, `--output`, `--write` | defs: load_json, walk_strings, validate_authority, validate_packet, write_json |
| `source_freshness_classifier.py` | retain_as_library_component_candidate; document importer/consumer path rather than chain step | 7 | none | defs: utc_now, parse_datetime, age_hours, worse_classification, _clean_list |

## Per-script notes

### `promotion_review_check.py`

- Verdict: retain_manual_guardrail; document in scripts README/manual guardrail surface; not archive; chain-tail candidate only after execution proof
- Writes files/static: `true`; SEC/network static: `false`
- Active non-tmp/non-backup refs: `7`
  - `06. Playbooks/Project Continuity/Workflow 38 - Sector Expansion and Promotion Review Hardening.md`
  - `06. Playbooks/Project Continuity/Workflow 51 - Daily Fresh Intelligence and Price Trend Promotion Branch.md`
  - `08. Audits/WF51 Closure Hardening Implementation Audit - 2026-05-10.md`
  - `memory/.dreams/short-term-recall.json`
  - `memory/2026-05-06.md`
  - `migration-backups/2026-05-06-wf39-posture-verification/2026-05-06.md`
  - `scripts/README.md`

### `ranking_shadow_canon_check.py`

- Verdict: retain_manual_guardrail; document in scripts README/manual guardrail surface; not archive; chain-tail candidate only after execution proof
- Writes files/static: `true`; SEC/network static: `false`
- Active non-tmp/non-backup refs: `3`
  - `06. Playbooks/Project Continuity/Workflow 38 - Sector Expansion and Promotion Review Hardening.md`
  - `06. Playbooks/WF38 Phase 0-5 Promotion Automation Foundation Proof - 2026-05-06.md`
  - `scripts/README.md`

### `canonical_freshness_patch.py`

- Verdict: retain_manual_patch_proposal_prototype; no apply authority; not chain/cron until candidate input contract is active
- Writes files/static: `true`; SEC/network static: `false`
- Active non-tmp/non-backup refs: `9`
  - `06. Playbooks/Project Continuity/Workflow 22 - Canonical Freshness Patch Pilot and Surface Sync.md`
  - `06. Playbooks/Project Continuity/Workflow 23 - Command Center Fresh Brief and Decision Surface Tightening.md`
  - `06. Playbooks/Research Automation Freshness Candidate Input Contract.md`
  - `06. Playbooks/WF22 Freshness Patch Pilot Dry Run and Manual Apply Proof - 2026-05-06.md`
  - `memory/.dreams/short-term-recall.json`
  - `memory/2026-05-03.md`
  - `memory/2026-05-06.md`
  - `migration-backups/2026-05-06-wf39-posture-verification/2026-05-06.md`
- Literal paths detected:
  - `03. Portfolio/Portfolio Snapshot.md`
  - `tmp/research-automation`
  - `tmp/research-automation/raw-freshness-candidates.json`

### `goog_official_ir_capture.py`

- Verdict: retain_temporarily; compare with current fundamental IR reconciliation and WF66 before deciding document-vs-archive
- Writes files/static: `true`; SEC/network static: `true`
- Active non-tmp/non-backup refs: `4`
  - `06. Playbooks/Active Workflows.md`
  - `06. Playbooks/Project Continuity/Workflow 66 - Why-Aware Recommendation Packet Evidence Bridge.md`
  - `memory/2026-05-17.md`
  - `scripts/README.md`
- Literal paths detected:
  - `https://www.sec.gov/Archives/edgar/data/1652044/000165204426000043/goog-20260429.htm`
  - `https://www.sec.gov/Archives/edgar/data/1652044/000165204426000043/googexhibit991q12026.htm`

### `official_ir_capture_validator.py`

- Verdict: retain_temporarily; compare with current fundamental IR reconciliation and WF66 before deciding document-vs-archive
- Writes files/static: `true`; SEC/network static: `false`
- Active non-tmp/non-backup refs: `4`
  - `06. Playbooks/Active Workflows.md`
  - `06. Playbooks/Project Continuity/Workflow 66 - Why-Aware Recommendation Packet Evidence Bridge.md`
  - `memory/2026-05-17.md`
  - `scripts/README.md`

### `sec_capital_freshness_review.py`

- Verdict: retain_manual_WF66_bridge; output/proposal authority must remain review-only; no chain/cron until validator proof
- Writes files/static: `true`; SEC/network static: `false`
- Active non-tmp/non-backup refs: `5`
  - `06. Playbooks/Active Workflows.md`
  - `06. Playbooks/Project Continuity/Workflow 66 - Why-Aware Recommendation Packet Evidence Bridge.md`
  - `memory/.dreams/short-term-recall.json`
  - `memory/2026-05-17.md`
  - `scripts/README.md`
- Literal paths detected:
  - `tmp/official-ir-captures/goog-q1-2026.json`

### `sec_capital_recommendation_bridge.py`

- Verdict: retain_manual_WF66_bridge; output/proposal authority must remain review-only; no chain/cron until validator proof
- Writes files/static: `true`; SEC/network static: `false`
- Active non-tmp/non-backup refs: `4`
  - `06. Playbooks/Active Workflows.md`
  - `06. Playbooks/Project Continuity/Workflow 66 - Why-Aware Recommendation Packet Evidence Bridge.md`
  - `memory/2026-05-17.md`
  - `scripts/README.md`

### `sec_evidence_packet.py`

- Verdict: retain_manual_official_source_pair; candidate bounded smoke test; not archive; not cron yet
- Writes files/static: `true`; SEC/network static: `false`
- Active non-tmp/non-backup refs: `4`
  - `06. Playbooks/Active Workflows.md`
  - `06. Playbooks/Project Continuity/Workflow 66 - Why-Aware Recommendation Packet Evidence Bridge.md`
  - `memory/2026-05-17.md`
  - `scripts/README.md`
- Literal paths detected:
  - `scripts/sec_evidence_packet.py`

### `sec_evidence_packet_validator.py`

- Verdict: retain_manual_official_source_pair; candidate bounded smoke test; not archive; not cron yet
- Writes files/static: `true`; SEC/network static: `false`
- Active non-tmp/non-backup refs: `3`
  - `06. Playbooks/Project Continuity/Workflow 66 - Why-Aware Recommendation Packet Evidence Bridge.md`
  - `memory/2026-05-17.md`
  - `scripts/README.md`

### `source_freshness_classifier.py`

- Verdict: retain_as_library_component_candidate; document importer/consumer path rather than chain step
- Writes files/static: `false`; SEC/network static: `false`
- Active non-tmp/non-backup refs: `7`
  - `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
  - `06. Playbooks/Project Continuity/Workflow 45 - Shared Stale Source Fail-Soft Classifier.md`
  - `06. Playbooks/Project Continuity/Workflow 58 - Dashboard Freshness Entry Bands Capital Recommendations and Discrepancy Automation.md`
  - `06. Playbooks/WF High-Grade Recommendations Program Plan - 2026-05-09.md`
  - `08. Audits/Stale Source Fail-Soft Hardening Plan - 2026-05-09.md`
  - `memory/.dreams/short-term-recall.json`
  - `migration-backups/2026-05-10-skill-hardening-20260510-211649/06. Playbooks/OpenClaw Parallel Pilot Queue.md`

## Decisions / next actions

1. Document the two manual guardrails before considering chain-tail wiring: `promotion_review_check.py`, `ranking_shadow_canon_check.py`.
2. Bounded smoke-test the SEC evidence packet/validator pair manually before WF65/WF66 wiring.
3. Compare GOOG official IR capture tools against current fundamental IR reconciliation; retain until supersession is proven.
4. Keep recommendation/patch bridge scripts manual/review-only. They touch proposal/canon-adjacent surfaces and must not gain cron authority by accident.
5. Treat `source_freshness_classifier.py` as a library/helper candidate, not a standalone cron step.

Machine-readable detail: `tmp/script-guardrail-evidence-inspection-2026-05-19.json`.
