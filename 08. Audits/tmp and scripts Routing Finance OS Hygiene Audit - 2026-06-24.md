# tmp and scripts Routing Finance OS Hygiene Audit - 2026-06-24

Generated: 2026-06-24 05:50 UTC  
Scope: `tmp/` and `scripts/` surfaces related to WF78 routing, WF84/WF85 finance decision-grade OS, cron/escalation, validators, full answers, cards, parity, ledgers, and SQL-canon access.  
Authority: review-only audit. No deletion, archive, move, cron mutation, finance canon/portfolio mutation, capital deployment, paper/live execution, brokerage/account action, customer output, or owner approval inference was performed or recommended as an automatic action.

## Executive Summary

The core routing/finance OS is structurally strong but operationally noisy.

- `tmp/` contains about **10,961 files / 2.0 GB**. Most space is not the active finance OS itself; the largest owners are OTEL logs (**~662 MB**), local audio tool dependencies/cache (**~469 MB**), root-level generated proof/DB files (**~525 MB**), and Go binary backups (**~267 MB combined across current/profile/backup dirs**).
- The active WF78/WF84/WF85 artifacts are fresh and their authority flags are clean. I checked representative live packets and found **0 true capital/execution/owner-approval flags** across `wf78-auto-tier-routing.json`, `wf78-intelligence-routing-v2.json`, Tier A gates, event ledger, full-answer assembler, decision cards, SQL-canon access validation, and finance-intelligence-state validation.
- The hygiene risk is not a broken safety boundary. The risk is **surface sprawl**: legacy compatibility packets, V1/V2 coexistence, stale root-level tmp artifacts, duplicated rollback/proof DBs, and producer/consumer lineage that exists in code but is hard to audit from the artifacts themselves.
- The most important live correctness gap remains the one found by the adjacent WF78 readiness audit: routing and full-answer artifacts are green, but **decision-grade / approval-ready language must remain blocked when the coverage gate says `decision_grade_allowed_count=0`**.

## Proof Gathered

- Read governing surfaces: `SOUL.md`, `USER.md`, `TOOLS.md`, Startup Truth Index, today's/yesterday's daily memory, `MEMORY.md`, and `veritas-workspace-audit-orchestrator`.
- Opened a distinct audit lane: `AUDIT::TMP-SCRIPTS-ROUTING-FINANCE-OS-HYGIENE-2026-06-24::audit`.
- Inventoried `tmp/` by file count, size, extension, top-level folder, age, and heuristic category.
- Inventoried related `scripts/*.py`; found **464 Python scripts/tests** matching routing/finance/decision/cron/validator terms out of **1,031** Python files.
- Searched representative scripts for validation paths and authority-boundary flags.
- Cross-checked selected important `tmp/` artifacts against script references to infer producer/consumer paths.

## tmp Inventory

### Counts by Category

Heuristic counts; a file can match more than one category.

| Category | Approx. count | Examples |
|---|---:|---|
| Routing / tier / candidate | 2,126 | `wf78-auto-tier-routing.json`, `wf78-repair-priority-queue.json`, `wf78-tier-routing-event-ledger.json` |
| Cards / recommendation surfaces | 2,004 | `ticker-intelligence-cards/`, `trade-grade-decision-cards.json`, deployment-card packets |
| Full-answer / answer path | 577 | `trade-grade-full-answer/`, `trade-grade-full-answer-assembler.json`, `ticker-answer-packets/` |
| SQL canon / reference levels | 525 | `canonical-finance-data-plane.sqlite`, SQL-canon validation packets |
| Freshness / readiness | 512 | `wf78-tier-weighted-freshness-resolution.json`, `cron-freshness-spine.json` |
| Parity / compatibility / legacy | 310 | `full-answer-parity/`, compatibility snapshots, legacy 42 surfaces |
| Paper / WF67 / WF86 / WF87 | 305 | `paper-autotrader/`, paper-position packets |
| Cron / escalation | 271 | `cron-control-packet.json`, `main-session-escalation-consumer.json` |
| Ledger / event / history | 132 | routing event ledger, recommendation correctness ledgers |

### Top Size Owners

| Surface | Count | Approx. size | Audit note |
|---|---:|---:|---|
| `tmp/otel-collector/` | 70 | 662 MB | Biggest file is `metrics.jsonl` at ~611 MB. Needs retention/lifecycle control, not blind deletion. |
| root `tmp/*` files | 1,939 | 525 MB | Active finance proof mixed with old proof, rollback, snapshots, and stale compatibility packets. |
| `tmp/audio-tools/` | 4,622 | 469 MB | Mostly local dependencies/cache; not finance OS, but dominates file count. |
| `tmp/go-binaries/`, `tmp/go-bin-backup-20260607/`, `tmp/go-profile-binaries/` | 36 | 267 MB | Current and backup validator binaries coexist; needs lifecycle manifest/retention decision. |
| `tmp/canonical-finance-data-plane.json` | 1 | 34.8 MB | Active large generated packet, fresh. |
| `tmp/canonical-finance-data-plane.sqlite` | 1 | 30.8 MB | Active compatibility/current-state DB, fresh. |
| `tmp/veritas-canon-cache.sqlite` | 1 | 20.7 MB | Metadata/reference cache; not recommendation/canon authority. |
| `tmp/finance-intelligence-state.sqlite` | 1 | 16.6 MB | Active review-only query cache, fresh. |

### Stale or Obsolete-Looking tmp Surfaces

`tmp/` has **6,790 files older than 14 days** by mtime, but most are under `audio-tools/node_modules` and should be treated as dependency/cache lifecycle, not finance proof residue. More relevant: **452 root-level tmp files** are older than 14 days, and **168** of those look routing/finance/decision/cron-related.

Representative stale root-level artifacts that look like cleanup candidates after owner review:

- May proof packets and proposals: `market-intelligence-events-post-earnings.json`, `portfolio-mutation-automation-audit.json`, `bounded-canon-mutation-approval-packet.json`.
- Old WF70/WF72/WF73 proof packets: many `wf70-*`, `wf72-*`, `wf73-*` files from 2026-05-21 to 2026-05-24.
- Early SQL-canon activation/rollback packets: `sql-canon-phase4a-*`, `sql-canon-low-risk-phase3-*`, `sql-current-proof-routing-archive-proposal-2026-05-29.json`.
- Legacy WF78/import artifacts: `wf78-100-ticker-import-gate.json`, `wf78-live-25-pilot-import-gate.json`, `wf78-tier-b-final-promotion-packet.production-bench.json`, `wf78-tier-b-final-promotion-packet.next-batch-2.json`.
- Old route-per-ticker packets: `wf78-route-nflx.json`, `wf78-route-vmc.json`, `wf78-route-lin.json`, and related June 7 route outputs.
- Legacy answer/card build summaries: `ticker-card-registry-build-summary-20260526.json`, `finance-intelligence-router-qa-2026-05-27-*`, `finance-intelligence-router-qa-ticker-answer-packet.json`.
- Cron live-list snapshots: multiple `cron-live-list-*` files from 2026-06-03 to 2026-06-07.

Duplicate/retention hotspots:

- `reference-levels-derived-refresh-rollback-drill-*`: **95 root-level SQLite/WAL/SHM files**. This is the clearest proof-retention sprawl cluster.
- Many active JSON+SQLite+WAL+SHM groups are legitimate current proof sets but need lifecycle labels: `canonical-finance-data-plane`, `finance-intelligence-state`, `wf78-routing-dashboard`, `wf78-sql-readiness-index`, `wf78-tier-b-evidence-repair`, `wf78-tier-capacity-policy-gate`.
- `ticker-answer-packets/` has **158 compatibility snapshots**, last touched 2026-06-20. These are known legacy compatibility artifacts, not strategic answer authority.

## scripts Inventory

### Related Script Families

| Family | Count | Important surfaces |
|---|---:|---|
| WF78 routing/evidence | 97 | `wf78_auto_tier_router.py`, `wf78_intelligence_routing_v2.py`, tier gates, evidence repair, routing dashboards, legacy 42 planners |
| WF84 data plane | 6 | `canonical_finance_data_plane.py`, contract/phase scripts, SQLite mutex |
| WF85 decision OS | 14 | `trade_grade_full_answer_assembler.py`, `trade_grade_decision_cards.py`, freshness/readiness rollups, paper digest/notifier |
| SQL canon | 29 | `finance_sql_canon_access.py`, migration/completion/front-door/readiness, reference-level helpers |
| Finance helper/state | 22 | `finance_intelligence_state.py`, `finance_decision_factory.py`, recommendation ledgers, response quality, data coverage |
| Cron/control runners | 60 | `cron_control_packet.py`, `cron_freshness_spine.py`, cron contract/reduction/escalation, market/post-close runners |
| Validators/gates | 54 | validator routers, capital/canon guards, Tier A coverage gate, Go proof wrappers |
| Tests matching scope | 117 | Good coverage density for most current WF78/WF85/cron/SQL-canon surfaces |

### Deprecated, Duplicate, or V1/V2 Surfaces

- **Legacy answer route:** `ticker-answer-packets/` and static ticker answer packet scripts remain as compatibility. Strategic owner is now `trade_grade_full_answer_assembler.py` and `tmp/trade-grade-full-answer/`.
- **WF78 V2 coexistence:** `wf78_intelligence_routing_v2.py` is the active layered conveyor. Older daily-core habits still surface through `trade_grade_os_freshness_cron_runner.py` and some status/action consumers. This is a naming/consumer drift risk, not an authority breach.
- **Legacy 42 surfaces:** `wf78_legacy_42_tier_state.py`, `wf78_legacy_42_tier_migration_planner.py`, and `wf78_legacy_42_archive_readiness_packet.py` remain visible. Recent memory says the legacy 42 compatibility set should not create repair noise; those scripts need clear lifecycle status in their outputs and consumer registry.
- **Apply/archive scripts:** `finance_human_notes_archive_apply.py`, `finance_sql_canon_archive_apply.py`, `sql_canon_consumer_cutover_apply.py`, `sql_field_family_canon_promotion_apply.py`, `wf78_ticker_card_field_repair_apply.py`. These are expected to be gated; they should remain excluded from routine hygiene automation.
- **Phase/prototype names:** `sql_canon_*phase*`, `wf78_sql_phase2_readiness.py`, `canonical_finance_data_plane_phase6_10.py` remain useful for migration proof but should not be treated as current-user truth without a lifecycle/owner indicator.

### Scripts with Weak or Missing Validation Path

Among related write-capable scripts, I found these with no obvious `--validate`/validation path from text inspection:

- `alpaca_read_only_connection_proof.py`
- `canonical_note_patch_proposal.py`
- `cyber_security_daily_audit_cron_runner.py`
- `earnings_date_source_confidence.py`
- `finance_discrepancy_resolver.py`
- `sec_capital_freshness_review.py`
- `wf78_legacy_42_tier_state.py`
- `wf78_pilot_provider_runtime_probe.py`
- `wf84_sqlite_mutex.py`

This does not prove they are wrong; several may be small probes. But any script that writes proof or feeds finance/current-state routing should either expose `--validate`, be wrapped by a validator, or be clearly documented as a probe with no downstream authority.

## Producer / Consumer Cross-Check

| Artifact | Current state | Primary producer | Important consumers | Finding |
|---|---|---|---|---|
| `tmp/wf78-auto-tier-routing.json` | Fresh, 0.2 MB, status ok | `wf78_auto_tier_router.py` | WF84 data plane, SQL-canon access, WF78 gates, WF85 surfaces, status/PM/cron | High fan-out. Needs explicit lineage embedded because many consumers map it differently. |
| `tmp/wf78-intelligence-routing-v2.json` | Fresh, status ok | `wf78_intelligence_routing_v2.py` via `wf_registry` path | `cron_freshness_spine.py`, `market_open_repair_cadence.py`, workflow routing | Producer is partly hidden behind registry constant; artifact should name producer command in packet. |
| `tmp/wf78-tier-weighted-freshness-resolution.json` | Fresh, 0.3 MB | `wf78_tier_weighted_freshness_resolver.py` | WF78 daily movement, canonical data plane, WF85 freshness, event ledger | Clean current lineage, high-value input. |
| `tmp/wf78-daily-movement-ledger.json` | Fresh, 0.6 MB | `wf78_daily_movement_ledger.py` | V2 routing, event ledger, opportunity refresh, workflow routing | Clean, but "ledger" is JSON snapshot; append-only history is separate. |
| `tmp/wf78-tier-routing-event-ledger.json` | Fresh, status ok | `wf78_tier_routing_event_ledger.py` | V2 routing, workflow routing | Good authority boundary; invocation-mode consistency was already flagged in WF78 audit. |
| `tmp/wf78-repair-priority-queue.json` | Fresh, small | `wf78_daily_movement_ledger.py`/WF78 repair flow | market-open cadence, opportunity refresh, V2 routing | Current count `42` can be confused with legacy 42 compatibility set; needs label hardening. |
| `tmp/tier-a-trade-grade-coverage-gate.json` | Fresh, status `coverage_floor_ok_tier_definition_mismatch` | `tier_a_trade_grade_coverage_gate.py` | SQL-canon access, event ledger, cohort reconciliation, depth/fundamental gates | Healthy fail-closed signal. Consumers must preserve `decision_grade_allowed_count=0`. |
| `tmp/wf78-tier-a-confidence-gate.json` | Fresh, status ok | `wf78_tier_a_confidence_gate.py` | auto-router, SQL-canon access, morning builder, event ledger | Clean authority; six ETF/fund style rows are forced challenged/not-applicable. |
| `tmp/canonical-finance-data-plane.json/.sqlite` | Fresh, large | `canonical_finance_data_plane.py` | finance state, WF85 decisions, coverage gate, cron/PM, workflow routing | Active and central; size is acceptable but should remain generated proof only. |
| `tmp/finance-intelligence-state.sqlite` | Fresh, 16.6 MB | `finance_intelligence_state.py` | ticker Q&A, finance stack, reference-level consumers | Compatibility/query cache only; packet correctly says it does not promote tmp DB authority. |
| `tmp/trade-grade-full-answer/` | 200 files, fresh | `trade_grade_full_answer_assembler.py` | finance intelligence state, coverage gate, WF85 rollups, artifact index | Strategic full-answer surface; no issue. |
| `tmp/trade-grade-full-answer-assembler.json` | Fresh, status ok | `trade_grade_full_answer_assembler.py` | readiness rollups, SQL migration completion, artifact index | Clean; legacy packet write not requested. |
| `tmp/ticker-answer-packets/` | 158 files, older compatibility | `trade_grade_full_answer_assembler.py --write-legacy-packets` or older packet builders | compatibility readers, retirement plan | Needs retirement/lifecycle decision; should not be strategic current-answer source. |
| `tmp/ticker-intelligence-cards/` | 200 files, fresh | `ticker_intelligence_card.py` / card refresh pipeline | data plane, full-answer assembler, finance state, coverage | Healthy current evidence cache. |
| `tmp/full-answer-parity/` | 202 files, fresh | `full_intelligence_answer_parity.py` | coverage gate, readiness rollups, SQL front door | Useful validator/parity layer; keep until legacy answer retirement clears. |
| `tmp/morning-paper-deployment-recommendation-cards.json` | Fresh-ish, warning/no candidate | `morning_paper_deployment_recommendation_builder.py` | WF85 digest, morning/midday runners, workflow routing | Must stay review-only; should not emit approval-ready language while gate count is 0. |
| `tmp/wf85-paper-deployment-notification-digest.json` | 2026-06-23 14:32 | `wf85_paper_deployment_notification_digest.py` | Telegram cron/notifier, Tier A probes | Current enough for post-close context only; should refresh before any live market claim. |
| `tmp/market-open-repair-cadence.json` | Fresh, warning | `market_open_repair_cadence.py` | currently mostly standalone | Good audit surface; consumer set is thin, so status/startup pickup should cite it only when material. |
| `tmp/cron-control-packet.json` | Fresh, status ok | `cron_control_packet.py` | status/future/startup, escalation/action executor, workflow routing | High fan-out and correct control front door. |
| `tmp/cron-freshness-spine.json` | Fresh | `cron_freshness_spine.py` | control audits, status, workflow scorecards, tmp lifecycle guard | Central consumer/proof surface; no authority issue. |
| `tmp/main-session-escalation-consumer.json` | Fresh | `main_session_escalation_consumer.py` | status/startup/action executor/PM | Correct review-only bridge; does not execute unless explicitly invoked with safe mode by main. |

Producer/consumer mismatch flags:

- `wf78-intelligence-routing-v2.json` and several registry-owned outputs are harder to trace because the artifact path is routed through `wf_registry.py`; the packet should include `producer_script`, `producer_command`, and `source_artifacts`.
- `wf78-repair-priority-queue.json` and the legacy 42 compatibility set share a confusing count (`42`) but are different populations. This is a current naming/contract drift risk.
- Some heuristic searches mark consumers as "producer/owner" because many scripts contain output constants and test fixtures. The codebase needs artifact-level lineage rather than relying on grep.
- `ticker-answer-packets/` still has consumers, but its strategic role is compatibility only. Retirement remains blocked until reader inventory and explicit owner approval clear.

## Authority-Boundary Review

Representative scripts reviewed:

- `wf78_auto_tier_router.py`: docstring says no capital deployment, no order execution, no paper/live/account action, no portfolio/cash/sizing execution authority, and no mutation of durable universe/canon/ticker cards/SQL canon/brokerage. Output validation checks all row `capital_deployment_approved` and `trade_or_execution_approved` flags are false.
- `finance_sql_canon_access.py`: read-only typed access layer; guard checks tier routing state authority columns. Output validation boundary says DB mutation false, capital/execution false, brokerage/account false, customer/external false, owner approval inferred false.
- `trade_grade_full_answer_assembler.py`: replacement for static answer packets, review-only; no canon/portfolio/cash/risk mutation, no archive/delete action, no paper/live/account action, no inferred approval. Live rollup has 549 checked authority flags and 0 true.
- `finance_intelligence_state.py`: review-only SQL query/cache surface; explicitly does not replace Markdown canon, promote tmp DBs, infer approval, or authorize paper/live execution.
- `wf78_intelligence_routing_v2.py`: layered review-only routing runner; authority boundary has capital/execution/paper-live/brokerage/owner-approval flags false and validates them.
- `tier_a_trade_grade_coverage_gate.py`: review-only, report-only, SQL read-only; capital/execution/paper-live/brokerage/customer/external/approval flags false.
- `wf78_tier_a_confidence_gate.py`: confidence-only; does not admit/promote/demote/mutate canon/approve capital/authorize paper-live-account action.
- `wf78_tier_routing_event_ledger.py`: append-only derived non-capital routing event ledger; no universe/card/SQL-canon/portfolio/broker/account/execution mutation.

Live packet confirmation:

| Packet | Flag count scanned | True capital/execution/approval flags |
|---|---:|---:|
| `wf78-auto-tier-routing.json` | 402 | 0 |
| `wf78-intelligence-routing-v2.json` | 5 | 0 |
| `tier-a-trade-grade-coverage-gate.json` | 5 | 0 |
| `wf78-tier-a-confidence-gate.json` | 53 | 0 |
| `wf78-tier-routing-event-ledger.json` | 105 | 0 |
| `trade-grade-full-answer-assembler.json` | 549 | 0 |
| `trade-grade-decision-cards.json` | 1,208 | 0 |
| `finance-sql-canon-access-validation.json` | 9 | 0 |
| `finance-intelligence-state-validation.json` | 13 | 0 |

Conclusion: the authority boundary is currently intact.

## Findings

### P1 - Decision-Grade Language Can Still Outrun the Coverage Gate

Evidence: adjacent WF78 audit found `decision_grade_allowed_count=0`, router Tier A `25`, finance Tier A `19`, and no validated A-READY production scope. Live decision cards show `approval_card_draft_count=0`, but some legacy/action surfaces still have wording such as approval-ready-if-fresh in their historical contract.

Impact: user-facing status/action queues can imply more readiness than the coverage gate allows.

Recommendation: every consumer that emits `approval_ready`, `prepare`, `deploy`, or production-answer language must join the current coverage/semantics gate and fail closed when `decision_grade_allowed_count=0`.

Acceptance proof: `finance_sql_canon_access.py --write --validate`, `finance_intelligence_state.py refresh --write --validate`, `trade_grade_decision_cards.py --write --validate`, and status/action surfaces show `validated_production_answer_count=0` and no approval-ready rows while coverage gate count is 0.

### P1 - tmp Has No Enforced Retention Boundary for Large Non-Finance Runtime Artifacts

Evidence: `tmp/otel-collector/metrics.jsonl` is ~611 MB; `audio-tools/` is ~469 MB; Go binary current/profile/backup dirs total hundreds of MB. These are not active finance decision artifacts, but they live beside the decision OS proof surface.

Impact: broad scans, backups, syncs, and audits get slower and noisier; stale runtime files can hide actual finance residue.

Recommendation: create a review-only tmp lifecycle manifest for retention classes: active finance proof, compatibility proof, rollback proof, runtime cache, dependency cache, logs, binaries, and deletion/archival candidates. Do not delete until reference review and explicit owner approval.

Acceptance proof: `db_lifecycle_manifest.py` / `tmp_lifecycle_guard.py` or equivalent reports all large tmp owners with retention class, consumer count, last producer, and proposed action.

### P2 - Legacy Compatibility Surfaces Are Still Too Easy to Mistake for Current Strategy

Evidence: `ticker-answer-packets/` has 158 compatibility snapshots; legacy 42 scripts remain in `scripts/`; many old `finance-intelligence-router-qa-*` and ticker-card summary packets remain in root `tmp/`.

Impact: future agents may pick old compatibility snapshots over the SQL-first WF84/WF85 route, especially during ticker review or status synthesis.

Recommendation: add visible `compatibility_only=true`, `strategic_answer_authority=false`, `retirement_blocked_until_reader_inventory=true` to legacy answer/42 packets and route status surfaces away from them.

Acceptance proof: artifact index and ticker-answer lookup prefer `trade-grade-full-answer/` and disclose legacy snapshots only as compatibility.

### P2 - Producer/Consumer Lineage Is Mostly Recoverable from Code, Not Artifacts

Evidence: high-fan-out artifacts such as `wf78-auto-tier-routing.json`, `canonical-finance-data-plane.sqlite`, and `trade-grade-decision-cards.json` have dozens of consumers. Some registry-backed outputs do not self-name producer command/source artifacts clearly enough.

Impact: audits rely on grep and heuristics; stale files and renamed scripts are harder to classify safely.

Recommendation: standardize a small lineage block in generated finance/routing packets: `producer_script`, `producer_command`, `source_artifacts`, `consumer_registry_hint`, `authority_boundary`, `retention_class`.

Acceptance proof: Go JSON proof contract or Python validator checks the lineage block on the top 20 routing/finance artifacts.

### P2 - Some Related Write-Capable Scripts Lack Obvious Validation Paths

Evidence: text inspection flagged nine related scripts with writes/probe outputs and no obvious `--validate`/validation path, including `wf78_legacy_42_tier_state.py`, `wf78_pilot_provider_runtime_probe.py`, `finance_discrepancy_resolver.py`, and `earnings_date_source_confidence.py`.

Impact: isolated probes can become unvalidated dependencies if later consumed by cron/status/finance surfaces.

Recommendation: either add `--validate` or mark each as `probe_only_no_downstream_authority` and ensure any consumer validates before trusting output.

Acceptance proof: `changed_file_validator_router.py --write --validate` can route each important writer to a test/validator or documented no-downstream probe classification.

### P3 - Root tmp Contains Many Old Audit/Proof Snapshots That Need Owner-Routed Cleanup Review

Evidence: 452 root-level tmp files are older than 14 days; 168 look finance/routing/cron-related. Clear clusters include old WF70/WF72/WF73 proof, SQL-canon activation/rollback files, route-per-ticker WF78 packets, and old cron live-list snapshots.

Impact: scan noise and accidental stale-source selection.

Recommendation: generate an archive/delete proposal only after reference review. Keep destructive cleanup owner-gated.

Acceptance proof: a tmp lifecycle proposal lists candidate path, age, size, consumers, replacement current artifact, backup/rollback route, and explicit stop line.

## Prioritized Recommendations

1. **P1: Fail closed on decision-grade language.** Route all approval-ready/production-answer wording through current coverage/semantics gates; keep capital/execution flags false.
2. **P1: Build tmp lifecycle manifest, no deletion.** Classify large tmp owners and stale root artifacts into retention classes with consumer counts.
3. **P2: Add lineage blocks to top finance/routing artifacts.** Start with `wf78-auto-tier-routing`, `wf78-intelligence-routing-v2`, `canonical-finance-data-plane`, `finance-intelligence-state`, `trade-grade-full-answer-assembler`, and decision cards.
4. **P2: Quarantine compatibility semantics in-place.** Mark `ticker-answer-packets` and legacy 42 outputs as compatibility-only in their packets/index, not by moving/deleting them.
5. **P2: Add validation or probe-only classification for the nine weak-validation scripts.**
6. **P3: Owner-routed stale tmp cleanup proposal.** Only after lineage/reference review and explicit approval.

## Stop Lines

Do not automatically delete, move, archive, compact, or rewrite tmp artifacts. Do not mutate `state/finance`, portfolio/canon notes, cash/sizing/risk, cron schedules, runtime config, credentials, channels, paper/live/brokerage/account state, or external/customer delivery surfaces from this audit. Generated routing/card/full-answer artifacts remain review/proof surfaces, not approval or execution authority.

## Bottom Line

The routing/finance/decision OS safety boundary is intact. The hygiene problem is lifecycle and lineage: too many old compatibility/proof/runtime artifacts live beside current decision OS surfaces, and too many important consumers rely on naming convention or code-level knowledge instead of artifact-level lineage. Fix the wording gate first, then add retention and lineage controls before any cleanup.
