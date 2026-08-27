# Scripts

Durable repeatable helpers for the finance operating system.

## Rules

- Keep `scripts/` for supported tooling only.
- Keep `tmp/` for generated artifacts and staged render outputs only.
- Default to read-only behavior unless a script intentionally updates vault files.
- Prefer explicit inputs, explicit outputs, and visible freshness or warning states.
- Treat autonomous generation as proposal/review/report production by default: generated artifacts may rank, route, summarize, warn, and stage review objects, but they do not authorize portfolio mutation, owner approval, sizing, execution, trades, destructive cleanup, or broader canonical-note mutation.
- Archive one-off diagnostics, scratch helpers, and superseded planning notes instead of leaving them in the active operator surface.

## Requirements

```bash
pip install yfinance tzdata
```

Those are the minimum required Python dependencies for the current supported script surface.
On this Windows / Python 3.14 runtime, `tzdata` is required so `zoneinfo` can resolve market time zones reliably.

Optional dependencies for richer report generation:
```bash
pip install python-docx pillow python-pptx
```

## PM control cockpit

The local TypeScript/Node PM cockpit lives at `apps/pm-control-cockpit/` and reads the thin source registry at `state/pm-cockpit-source-registry.json`.

Run:
```bash
cd apps\pm-control-cockpit
npm run validate
npm run start
```

Default URL:
```text
http://127.0.0.1:8765
```

Purpose:
- render PM readiness, lane status, blockers, ranked next actions, main-session handoff, WF75 closeout proof, source freshness, cron/autonomy status, and authority flags from current JSON contracts
- keep source paths in the registry so future `/state` or `/data` promotion does not require UI rewrites

Boundary:
- internal control only; no public launch, real customer data, external delivery, SQL import, canon/portfolio mutation, cleanup move/delete/archive, paper/live/account action, config/auth/runtime mutation, or owner approval inference

## Local audio transcription

`local_audio_transcriber.py` is the repeatable local route for Telegram/OpenClaw voice notes. It resolves either an explicit path, `media://inbound/<file>`, or the newest file under `~\.openclaw\media\inbound`, then uses the local Node/Whisper helper to write one transcript JSON.

Run:
```powershell
python scripts\local_audio_transcriber.py --write --pretty --validate
python scripts\local_audio_transcriber.py media://inbound/<file>.ogg --write --pretty --validate
python scripts\test_local_audio_transcriber.py
```

Current proof:
- `tmp/audio-transcripts/latest-audio-transcript.json`

Purpose:
- avoid broad filesystem searches for voice-note media
- avoid manually choosing ffmpeg/Whisper commands each time
- keep audio transcription local by default
- cache Node dependencies and model files under `tmp\audio-tools` so repeat runs are faster

Boundary:
- local transcription only; no external transcription upload, Telegram send, config/auth/runtime mutation, canon/portfolio mutation, paper/live/account action, or owner approval inference

## Truth-surface inventory and fast-path QA

`wf73_control_plane_audit.py`, `truth_surface_inventory.py`, and `fast_path_qa.py` are WF73/WF72 report-only efficiency controls.

Run:
```powershell
python scripts\wf73_control_plane_audit.py --write --validate
python scripts\truth_surface_inventory.py --write --validate
python scripts\startup_brief_packet.py --write --validate
python scripts\dream_review_packet.py --write --validate --include-rem-harness
python scripts\future_session_enhancement_packet.py --write --write-md --validate
python scripts\main_session_escalation_consumer.py --context main_session --refresh-frontdoors --execute-safe --write --validate --append-ledger
python scripts\fast_path_qa.py --write --validate
python scripts\changed_file_validator_router.py --write --validate
python scripts\validator_timing_ledger.py --profile normal --write --validate
python scripts\otel_ops_control.py --write --write-db --validate
```

Current proof:
- `tmp/wf73-control-plane-audit.json`
- `tmp/truth-surface-inventory.json`
- `tmp/startup-brief-packet.json`
- `tmp/dream-review-packet.json`
- `tmp/future-session-enhancement-packet.json`
- `tmp/main-session-escalation-consumer.json`
- `tmp/route-efficiency-scorecard.json`
- `tmp/fast-path-qa.json`
- `tmp/changed-file-validator-router.json`
- `tmp/validator-timing-ledger.json`
- `tmp/otel-ops-control.json`
- `tmp/otel-ops.sqlite`

Purpose:
- run the full WF73 control-plane audit in producer-before-consumer order
- classify major surfaces as authority, router, proof, dashboard, legacy, or archive-candidate
- build a fast direct-session startup/status packet from existing PM/cron/future-session packets without regenerating them
- build a review-only Dreaming readiness and learning-signal packet without mutating memory
- build a thin future-session startup packet for PM, cron, WF74, workflow, memory, and stop-line routing
- consume cron escalation residue through allowlisted safe actions before raw blocker handoff reaches Randall
- define the compact "open first" route before broad scans
- measure route SQL and PM cockpit latency
- validate route/PM/artifact/cron fast-path health and closeout ordering discipline
- map changed files to the smallest honest validator budget
- record elapsed validator timing by normal/shared/major profile
- turn local OTEL collector summaries into queryable operational evidence and action candidates
- prevent false WF73 blockers caused by running route-index writers and fast-path/artifact-index consumers in parallel

Boundary:
- classification and QA only; no move/delete/archive, SQL-canon promotion, canon/portfolio mutation, customer/public output, config/runtime mutation, paper/live/account action, or owner approval inference. `dream_review_packet.py` may read OpenClaw Dreaming status and the read-only REM harness, but it writes only `tmp/dream-review-packet.json` and does not promote memories.

## Future session enhancement packet

`startup_brief_packet.py` builds the fastest read-only direct-session greeting/status packet from existing route packets. Use it when a simple hello or shallow status check does not require full PM/cron/future-session regeneration.

Run:
```powershell
python scripts\startup_brief_packet.py --write --validate
```

Current proof:
- `tmp/startup-brief-packet.json`

Boundary:
- routing/proof only; reads existing generated packets and does not refresh control packets, mutate canon/portfolio, approve capital, execute paper/live actions, change config/runtime, deliver externally, or infer owner approval.

`future_session_enhancement_packet.py` builds the compact open-first packet for future Veritas sessions and post-compaction recovery.

Run:
```powershell
python scripts\future_session_enhancement_packet.py --write --write-md --validate
```

Current proof:
- `tmp/future-session-enhancement-packet.json`
- `tmp/future-session-enhancement-packet.md`

Purpose:
- summarize core boot surfaces, today's/yesterday's memory files, PM state, cron state, WF74 model-quality collection state, selected workflow capsules, and route commands
- make new sessions faster and less dependent on broad scans or chat reconstruction
- keep model-quality and finance-correctness claims bounded to review-only evidence
- carry the verified serious-work challenger model policy: WF84/WF85-class gates should use `claude-cli/claude-opus-4-8` as the Opus challenger and verify the actual spawned model path before counting Opus proof

Boundary:
- routing/proof only; no canon/portfolio mutation, capital deployment, paper/live/account action, config/auth/runtime mutation, customer/external delivery, owner approval inference, model ranking, or WF55 outcome grading.

## Main-session escalation consumer and action executor

`handoff_first_proof_gate.py` is the dashboard/main-session handoff proof classifier. It reads the morning, post-close, Sunday weekly, Sunday research, and weekday research handoff artifacts, writes `tmp/main-session-handoff-first-proof.json`, and emits a repair packet when a lane is blocked, missing, stale, or still pending first proof. It does not run finance producers or mutate cron schedules.

`main_session_escalation_consumer.py` is the cron escalation pickup layer. It reads `tmp/cron-control-packet.json`, classifies embedded escalation signals, runs only allowlisted safe refresh/repair commands outside heartbeat, refreshes cron front doors including the handoff first-proof gate, and records unresolved owner/manual/helper residue in `state/main-session-escalation-action-ledger.jsonl`.

Run:
```powershell
python scripts\handoff_first_proof_gate.py --write --validate
python scripts\main_session_escalation_consumer.py --context main_session --refresh-frontdoors --execute-safe --write --validate --append-ledger
python scripts\heartbeat_priority_handoff.py --write --validate
python scripts\test_main_session_escalation_consumer.py
```

Current proof:
- `tmp/main-session-handoff-first-proof.json`
- `tmp/main-session-escalation-consumer.json`
- `state/main-session-escalation-action-ledger.jsonl`

`main_session_action_executor.py` first refreshes the handoff first-proof gate and calls the escalation consumer when `--refresh-frontdoors` is set, then picks one PM-safe proof job or prepares a helper-lane handoff. If the handoff gate still reports target lanes, the executor surfaces the repair packet as the next safe action instead of leaving the dashboard pills as passive queue residue.

Run:
```powershell
python scripts\main_session_action_executor.py --context main_session --refresh-frontdoors --execute-safe --write --validate --append-ledger
python scripts\test_main_session_action_executor.py
```

Boundary:
- review/control proof only; no broad canon/portfolio/cash/sizing/risk mutation authority, no capital deployment, no paper/live/brokerage/account action, no money movement, no cron schedule/config/auth/runtime mutation, no external/customer delivery, and no owner approval inference. Existing exact gated workspace-maintenance rails remain owned by their own validators and runners.

## Training dataset candidate builder

`training_dataset_candidate_builder.py` builds a local review-only candidate index for future eval/fine-tune dataset design. It scans WF74/RSI observations, model-run metadata, finance-correctness rows, harness checks, validator/closeout packets, and daily-memory surfaces, then writes metadata-only rows with eligibility, redaction status, recommended use, proof paths, and stop lines.

Run:
```powershell
python scripts\training_dataset_candidate_builder.py --write --write-md --validate
```

Current proof:
- `tmp/training-dataset-candidates.json`
- `tmp/training-dataset-candidates.md`

Purpose:
- identify usable eval/routing/future fine-tune candidates without exporting raw content
- separate eligible metadata rows from finance holdout/eval-only rows and daily-memory redaction-review rows
- prevent unsafe training data from stale chat, unredacted memory, finance execution context, duplicate cron artifacts, unverified helper output, or authority-drifting examples

Boundary:
- local metadata/proof only; no raw prompt/chat capture, no secret capture, no external upload, no OpenAI training/fine-tuning call, no model-weight mutation, no model ranking claim, no WF55 outcome grading, no canon/portfolio mutation, no capital deployment, no paper/live/account action, and no owner approval inference.

## Skill git checkpoint

`skill_git_checkpoint.py` validates or creates a targeted local git checkpoint for the workspace skill layer. Report mode checks that every live `skills\*\` directory is tracked and writes checkpoint status; commit mode stages only `skills\`, `06. Playbooks\Skills Governance Index.md`, and today's `memory\YYYY-MM-DD.md`.

Run:
```powershell
python scripts\skill_git_checkpoint.py --write --validate
python scripts\skill_git_checkpoint.py --write --validate --commit --message "Checkpoint workspace skills" --tag-name skills-checkpoint-YYYYMMDD-HHMM
```

Current proof:
- `tmp/skill-git-checkpoint.json`

Purpose:
- make pre/post Skill Workshop apply checkpoints repeatable
- prevent restored skill state from living only in the working tree
- prove all live skill directories are tracked before relying on git recovery

Boundary:
- local git only; no external push, no whole-workspace staging, no live skill-content mutation, no portfolio/canon mutation, no paper/live/account action, and no owner approval inference.

## Skill Workshop body guard

`skill_workshop_body_guard.py` is the repeatable review-only gate for Skill Workshop apply safety. It scans live workspace skills for body-replacement residue and can compare a proposed update body against the current live `SKILL.md` before apply.

WF88 treats this as the canonical Skill Workshop body-replacement guard. Do not create a parallel guard for the same failure mode; route improvements through this script, its tests, changed-file validation, and the implementation release contract.

Run:
```powershell
python scripts\skill_workshop_body_guard.py --write --validate
python scripts\skill_workshop_body_guard.py --live-skill skills\workspace-qa-pass\SKILL.md --proposal-file tmp\proposal.md --validate
python scripts\test_skill_workshop_body_guard.py
```

Current proof:
- `tmp/skill-workshop-body-guard.json`

Purpose:
- block live `# Proposed Update` wrappers and thin addendum residue
- flag existing-skill update proposals that are materially shorter than the live body
- flag preserve/retain claims that omit current live headings
- make post-apply readback deterministic before batch skill updates continue
- force skill-surface closeout through the existing body guard instead of relying on memory or duplicate procedures

Boundary:
- review-only; no Skill Workshop proposal creation/application, no skill mutation, no config/auth/runtime/cron mutation, no finance canon/portfolio/cash/sizing/risk mutation, no paper/live/account action, and no owner approval inference.

## Core skill proof-tier audit

`skill_core_proof_tier_audit.py` is the P3 governance validator for promoting selected core operating and finance skills to Tier 2 functional local proof. It reads the live skill bodies, checks frontmatter/H1/body hygiene, verifies per-skill contract anchors and authority stop-line groups, and writes `tmp/skill-core-proof-tier-audit.json`.

Commands:

```powershell
python scripts\skill_core_proof_tier_audit.py --write --validate
python scripts\test_skill_core_proof_tier_audit.py
```

Authority boundary:
- review-only; no Skill Workshop proposal creation/application, no skill mutation, no config/auth/runtime/cron mutation, no finance canon/portfolio/cash/sizing/risk mutation, no paper/live/account action, no external delivery, and no owner approval inference.

## Implementation completion ledger

`implementation_completion_ledger.py` records completed implementation/PM proof jobs into a local hash-chained JSONL ledger. Each row stores the previous row hash, the row hash, source proof artifact hashes, command-result digests, git HEAD/dirty metadata, changed-file-router snapshot, and explicit no-authority flags.

Run:
```powershell
python scripts\implementation_completion_ledger.py --source tmp\pm-execution-loop.json --record --write --validate
python scripts\implementation_completion_ledger.py --write --validate
python scripts\test_implementation_completion_ledger.py
```

Manual/backfill source artifacts may provide `completed_jobs[]` rows with job id,
title, summary, completed timestamp, owner surface, implementation class, and
target files. Successful PM execution-loop runs append automatically unless
`--skip-completion-ledger` is set. Successful non-PM closeout bundles can append
with:
```powershell
python scripts\control_closeout_bundle.py --write --validate --record-completion --completion-job-id <job_id> --completion-title "<title>" --completion-summary "<summary>"
```

Current proof:
- `state/implementation-completion-ledger.jsonl`
- `tmp/implementation-completion-ledger-current.json`

Purpose:
- make completed implementation jobs reconstructable from a durable tamper-evident ledger instead of chat or daily-memory reconstruction alone
- tie each completed job to source proof hashes, validation state, changed-file routing, and git dirty-state metadata
- give PM closeout a future audit spine without turning generated artifacts into approval or canon

Boundary:
- local proof metadata only; no external notarization, canon/portfolio mutation, SQL import/promotion, archive/delete/apply, config/auth/runtime mutation, customer output, capital approval, paper/live/account action, or owner approval inference

## OTEL operations control

`otel_ops_control.py` is the local-only OTEL digest path. It reads the official collector debug log and legacy receipt ledger when present, then writes a compact JSON packet, JSONL event stream, and SQLite database.

Run:
```powershell
python scripts\otel_ops_control.py --write --write-db --validate
```

Current proof:
- `tmp/otel-ops-control.json`
- `tmp/otel-ops-events.jsonl`
- `tmp/otel-ops.sqlite`

Purpose:
- prove collector health and loopback binding
- count metric batches, trace batches, spans, datapoints, and warning/error lines
- expose local query tables for recent OTEL events and action candidates
- feed `cron_control_packet.py`, `fast_path_qa.py`, `model_quality_scorecard.py`, and validator timing profiles

Boundary:
- local operational evidence only; no external export, runtime/config mutation, content capture expansion, prompt/tool/system-content logging, finance correctness scoring, portfolio/canon mutation, customer output, paper/live/account action, or owner approval inference

## Model learning capture approval packet

`model_learning_capture_approval_packet.py` builds the approval-ready packet for the next WF74 learning layer: metadata-only capture/scoring for model runs, tool use, failures, and coding outcomes. After Randall's approval, `model_learning_metadata_ledger.py` is the bounded implementation layer: it derives model/tool/failure/coding metadata rows from existing local proof artifacts and feeds `model_quality_scorecard.py`.

`otel_runtime_metadata_probe.py` is the Phase 2 local runtime proof gate. It parses the local collector debug log for approved OpenClaw runtime metadata field names and blocks the pilot if raw prompt/response/tool payload/system-prompt, secret, credential, or header markers appear. It is paired with `tools\otelcol\openclaw-local-otel-runtime-metadata.yaml`, which keeps OTLP metrics/traces local on `127.0.0.1:4318`, uses the debug exporter for detailed local inspection, and does not enable logs or content capture.

`coding_runtime_kpi_probe.py` is the metadata-only coding-runtime KPI layer. It consumes changed-file routing, validator timing, closeout, WF74, and learning-ledger artifacts to report diff/path counts, validator budget, elapsed validator time, first-pass clean state, rework state, failure buckets, and learning-row coverage. It never captures raw diffs or file contents.

Run:
```powershell
python scripts\model_learning_capture_approval_packet.py --write --write-md --validate
python scripts\test_model_learning_capture_approval_packet.py
python scripts\otel_runtime_metadata_probe.py --write --write-md --validate
python scripts\test_otel_runtime_metadata_probe.py
python scripts\coding_runtime_kpi_probe.py --write --write-md --validate
python scripts\test_coding_runtime_kpi_probe.py
python scripts\model_learning_metadata_ledger.py --write --write-md --validate
python scripts\test_model_learning_metadata_ledger.py
```

Current proof:
- `tmp/model-learning-capture-approval-packet.json`
- `tmp/model-learning-capture-approval-packet.md`
- `tmp/otel-runtime-metadata-probe.json`
- `tmp/otel-runtime-metadata-probe.md`
- `tmp/coding-runtime-kpi-probe.json`
- `tmp/coding-runtime-kpi-probe.md`
- `tmp/model-learning-metadata-ledger.json`
- `tmp/model-learning-metadata-ledger.md`

Purpose:
- define approved-after-owner-approval metadata fields for model, tool, failure, and coding capture
- prove direct local runtime OTEL metadata is privacy-clean before using it for learning/scoring
- implement the approved metadata-only ledger with local artifact-derived rows, runtime OTEL metadata rows, and coding-runtime KPI rows when the probes are clean
- expose PM-visible KPIs for first-pass clean state, rework, failure buckets, validator elapsed time, and learning-row coverage
- preserve raw prompt/response/tool payload/system prompt/secrets/content capture blocks
- preserve raw diff/file-content capture blocks
- route scoring into WF74 model-quality surfaces without implying model ranking, investment correctness, base-model self-modification, or finance/execution authority

Boundary:
- approval packet plus local metadata ledger and local runtime metadata probe only; no external export, no raw content capture, no finance/canon/portfolio mutation, no paper/live/account action, and no owner approval inference. Collector start/stop or config/runtime mutation remains explicit-owner-approved runtime work.

## Spark cron canary monitor

`cron_spark_canary_monitor.py` monitors the bounded Spark model canary registry. As of 2026-06-20 there are no active live Spark cron canaries; the monitor records an intentionally empty active set and keeps retired or migrated canaries visible for audit history.

Run:
```powershell
python scripts\cron_spark_canary_monitor.py --write --validate
```

Current proof:
- `tmp/cron-spark-canary-monitor.json`

Purpose:
- verify active canary jobs, when present, are configured with `codex/gpt-5.3-codex-spark`
- verify active Spark canary jobs use `xhigh` thinking
- compare post-canary run status and duration against the last successful `openai/gpt-5.5` baselines
- warn while the first natural canary run is still pending
- block if an active canary job is missing, configured to the wrong model/thinking posture, or reports a non-ok run after the canary window

Boundary:
- monitor/proof only; no cron mutation, config/auth/runtime mutation, canon/portfolio mutation, paper/live/account action, or owner approval inference

## WF78 evidence drag reduction

`wf78_evidence_drag_reducer.py` ranks WF78 event-rerouting, stale-card, and capital-review evidence debt into a smaller repair/card-prep queue.

Run:
```powershell
python scripts\wf78_evidence_drag_reducer.py --write --validate
```

Current proof:
- `tmp/wf78-evidence-drag-reduction.json`

Purpose:
- rank evidence repair by decision impact
- keep non-executing owner-card prep for capital-review candidates separate from execution approval
- expose the largest stale evidence families before broad card repair

Boundary:
- ranking/proof only; no ticker-card mutation, canon/portfolio mutation, capital deployment, trade execution, paper/live/account action, customer output, or owner approval inference

## Finance ticker card refresh gate

`finance_ticker_card_refresh_gate.py` is the repeatable review-only gate for refreshing finance evidence, rebuilding the active ticker-card set, validating finance state, and turning remaining stale evidence into a repair queue.

Run:
```powershell
python scripts\finance_ticker_card_refresh_gate.py --write --validate
python scripts\finance_ticker_card_refresh_gate.py --write --validate --skip-provider-refresh --full-answer-mode never
```

Current proof:
- `tmp/finance-ticker-card-refresh-gate.json`
- `tmp/ticker-card-refresh-gate-card-build-summary.json`
- `tmp/finance-intelligence-state-stale-tickers.json`

Purpose:
- refresh technical, price-freshness, fundamental, analyst, and coverage proof before card rebuilds
- rebuild review-only ticker-card artifacts from coverage
- validate the finance intelligence state after rebuild
- classify stale card families so PM can create repair jobs before Tier B/Tier A promotion
- keep normal ticker-card proof fast by rebuilding WF85 full answers only when `--full-answer-mode changed` detects a semantic source change; use `always` for full WF84/WF85 closeout and `never` for card-only proof
- provide a repeatable prerequisite before WF78 500-ticker scaleout moves beyond review-monitor posture

Boundary:
- review/report only; no ticker import/apply, production promotion, SQL-first answer route, canon/portfolio mutation, customer/external output, paper/live/account action, or owner approval inference

## WF78 small/mid-cap scaleout candidate pass

`wf78_small_mid_cap_scaleout_candidate_pass.py` is the review-only pass for a rate-stabilization small/mid-cap next-batch theme. It scores liquid operating-company candidates outside the active finance universe and emits migration-ready thin-monitor stubs for a future owner-gated WF78 import path. It also embeds the current-regime analog scenario panel as thesis context only; the analog panel cannot promote, rank for deployment, size, approve, import, or execute.

Run:
```powershell
python scripts\wf78_small_mid_cap_scaleout_candidate_pass.py --write --validate
```

Current proof:
- `tmp/wf78-small-mid-cap-scaleout-candidate-pass.json`
- `tmp/wf78-small-mid-cap-scaleout-candidate-pass.md`

Boundary:
- candidate packet only; no ticker import/apply, no Tier B/A promotion, no production answer-path change, no SQL/canon expansion, no portfolio mutation, no capital approval, no paper/live/account action, and no owner approval inference.

## WF78 tier promotion review gate

`wf78_tier_promotion_review_gate.py` is the review-only separator between broad Tier C/D discovery and Tier B/A research or deployment readiness. It prepares the exact 101-200 Tier C owner-decision packet and creates evidence-repair jobs before any promotion-quality finance use.

Run:
```powershell
python scripts\wf78_tier_promotion_review_gate.py --write --write-db --validate
```

Current proof:
- `tmp/wf78-tier-promotion-review-gate.json`
- `tmp/wf78-tier-promotion-review-gate.sqlite`
- `tmp/wf78-101-200-tier-c-owner-decision-packet.json`

Purpose:
- preserve 101-200 as an owner-gated Tier C review-monitor decision, not a bulk import
- keep Tier C/D breadth separate from Tier B/A research and capital-deployment decisions
- expose Tier C -> Tier B research leads while marking the full missing evidence stack
- turn stale current-card evidence into repair jobs before any Tier B/Tier A promotion packet

Boundary:
- review/report only; no import/apply until exact owner approval, no Tier B/A promotion from Tier C existence, no capital deployment, no SQL-first route, no canon/portfolio mutation, no customer/external output, no paper/live/account action, and no owner approval inference

## WF78 101-200 Tier C import gate

`wf78_101_200_tier_c_import_gate.py` is the exact approved import path for the 101-200 batch as Tier C review-monitor rows only. It backs up `data/finance/universe-v1.json`, applies the owner-approved rows, preserves the 42-name production answer path, and leaves Tier B/A promotion and capital deployment blocked.

Run only with an exact owner approval reference:
```powershell
python scripts\wf78_101_200_tier_c_import_gate.py --write --apply --owner-approval-reference "<exact owner approval reference>" --validate
```

Current proof:
- `tmp/wf78-101-200-tier-c-import-gate.json`

Boundary:
- bounded Tier C metadata import only; no production answer-path expansion, no Tier B/A promotion, no recommendation, no sizing, no SQL-first route, no canon/portfolio mutation, no customer/external output, no paper/live/account action, and no inferred approval.

## WF78 macro thesis overlay gate

`wf78_macro_thesis_overlay_gate.py` is the repeatable review-only macro/theme triage layer for imported Tier C breadth. It turns 100 Tier C review-monitor names into a small Tier B research shortlist while explicitly marking that full macro work, fundamentals, valuation, technicals, source-open evidence, and owner approval are still missing.

Run:
```powershell
python scripts\wf78_macro_thesis_overlay_gate.py --write --write-db --validate
```

Current proof:
- `tmp/wf78-macro-thesis-overlay-gate.json`
- `tmp/wf78-macro-thesis-overlay-gate.sqlite`

Boundary:
- triage/ranking only; no full macro-vetting claim, no full fundamentals claim, no Tier B/A promotion, no capital deployment, no production answer-path change, no canon/portfolio mutation, no customer/external output, no paper/live/account action, and no owner approval inference.

## WF78 tier capacity policy gate

`wf78_tier_capacity_policy_gate.py` is the repeatable review-only capacity policy for Randall's lighter scaleout model: Tier A max 25, Tier B max 50, and Tier A+B combined max 75. It separates legacy universe tier metadata from actual Tier A/B admission so old labels cannot become false deployment or research readiness.

Run:
```powershell
python scripts\wf78_tier_capacity_policy_gate.py --write --write-db --validate
```

Current proof:
- `tmp/wf78-tier-capacity-policy-gate.json`
- `tmp/wf78-tier-capacity-policy-gate.sqlite`

Boundary:
- capacity policy/proof only; no import/apply, no Tier B/A promotion, no capital deployment, no production answer-path change, no canon/portfolio mutation, no customer/external output, no paper/live/account action, and no owner approval inference.

## WF78 legacy 42 tier migration planner

`wf78_legacy_42_tier_migration_planner.py` is the shadow migration and dependency gate for folding the legacy `production_current_42` ticker set into Randall's 25 Tier A / 50 Tier B operating model. It writes a derived shadow Tier A/B database, identifies current auto-router alignment gaps, and classifies legacy references as active migration blockers, compatibility exceptions, or nonblocking governance/history. It blocks legacy 42-row database retirement until active consumers are clean and a separate explicit archive/delete approval exists.

Run:
```powershell
python scripts\wf78_legacy_42_tier_migration_planner.py --write --write-db --validate
```

Current proof:
- `tmp/wf78-legacy-42-tier-migration-planner.json`
- `tmp/wf78-legacy-42-tier-state-shadow.sqlite`

Consumer migration helper:
- `wf78_legacy_42_tier_state.py` is the shared read-only reader for migrated legacy-42 Tier A/B state. It prefers `tmp/wf78-legacy-42-tier-state-shadow.sqlite` and falls back to `data/finance/universe-v1.json`.
- Use it in active consumers that need the effective production/tier set instead of re-reading `production_current_42` directly.
- It grants no router mutation, universe/canon/portfolio mutation, SQL-canon promotion, archive/delete, capital, paper/live, account, customer/public, or owner-approval authority.

Deprecation classification:
- Do not delete every `production_current_42`, `42 production`, `252`, or `265` reference just to clear the scan.
- Active readers should migrate to `wf78_legacy_42_tier_state.py` or the WF78 auto-router.
- WF72 252/265 row-count checks are compatibility guardrails unless their approved SQL/cache contract changes.
- Archive/delete/lifecycle references are governance history until a separate exact retirement approval exists.

Archive-readiness preview:
- `wf78_legacy_42_archive_readiness_packet.py` writes `tmp/wf78-legacy-42-archive-readiness-packet.json`.
- It is preview-only: no archive, move, delete, checkpoint, vacuum, rewrite, SQL promotion, or authority expansion.
- Current expected policy: `tmp/wf78-production-tier-adjudication.json` and `.sqlite` are archive candidates only after exact approval; `tmp/go-sql-consumer-authority-guard.json` and `tmp/veritas-canon-cache.sqlite` are retained as WF72/shared SQL guardrails.
- Run after planner and DB lifecycle validation:

```powershell
python scripts\wf78_legacy_42_archive_readiness_packet.py --write --validate
```

Boundary:
- shadow migration/dependency proof only; no live router mutation, no universe/canon/portfolio mutation, no SQL-canon promotion, no legacy database archive/delete, no capital deployment, no customer/external output, no paper/live/account action, and no owner approval inference.

## Finance production-grade policy gate

`finance_production_grade_policy_gate.py` is the forward production answer-boundary proof. It defines production-grade review eligibility as SQL Tier A/A-READY joined to current router, coverage, confidence, and authority proof, and reports both the legacy `production_current_42` answer path and label-only Tier A/A-READY rows as compatibility-only. This is the preferred target for future consumers that need the strategic production-grade set instead of the old hardcoded 42.

Run:
```powershell
python scripts\finance_production_grade_policy_gate.py --write --validate
python scripts\test_finance_production_grade_policy_gate.py
```

Current proof:
- `tmp/finance-production-grade-policy-gate.json`

Purpose:
- make proof-joined validated eligibility the clean production-grade review boundary
- keep the old 42 visible only as a compatibility surface until consumer cutover is explicitly approved
- make `finance_sql_canon_access.production_answer_tickers()` return the proof-joined validated set, with `legacy_production_answer_tickers()` and `legacy_tier_a_ready_compatibility_tickers()` retained for explicit compatibility checks
- expose Tier A rows that are not A-READY as repair/watch/challenged rows, not production-grade
- preserve the execution boundary: validated production-grade means review/card eligibility only, not buy/sell/sizing/order authority

Boundary:
- policy/proof only; no SQL data/schema mutation, no universe/canon/portfolio mutation, no answer-consumer cutover, no production-card mutation, no customer/external output, no capital deployment, no paper/live/account action, and no owner approval inference.

## WF84 canonical finance data-plane

`finance_sql_canon_access.py` is the guarded internal SQL-canon access proof for `state\finance\finance-canon.sqlite`. New finance sessions should validate this first. The durable SQL-canon is the internal SQL-primary current-state layer for answer-path scope, evidence freshness, reference levels, source lineage, tier routing, and universe membership. It remains review/current-state routing only: no owner approval, retail/customer activation, archive/delete, portfolio/canon-note mutation, capital deployment, paper/live execution, account action, or money movement.
`canonical_finance_data_plane_contract.py` is the Phase 0 contract for the internal trade-grade personal finance OS data model. `canonical_finance_data_plane.py` is the Phase 1/2 writer: it builds the validated read-only JSON packet and then loads the derived SQLite lookup companion from that packet only. `canonical_finance_data_plane_phase6_10.py` proves the read-only consumer expansion, parity, source drillback, priority queue, and retirement-gate posture after the packet is refreshed.
`trade_grade_full_answer_assembler.py` builds the WF85 full-answer route from WF84/WF85 state and ticker evidence. Its `catalyst_news_macro` and `risk_invalidation` sections consume the review-only macro metrics/judgment artifacts, including CPI release decomposition for energy/gasoline/shelter/rent/OER context, as evidence-burden and no-chase/rate-sensitivity context only. It does not approve capital, sizing, paper/live execution, account action, portfolio/canon mutation, or owner approval.
`route_readiness.py` is the shared review-only classifier for routing tier/state, timing, decision state, trade readiness, and authority. Finance renderers and ticker packets should import this helper instead of recreating local label logic. It grants no capital, trade, paper/live, brokerage/account, owner-approval, or portfolio/canon mutation authority.
`finance_cache_frontdoor.py` is the lightweight SQL/WF85 chat-consumption surface. It emits `route_readiness` for every ticker with separate `routing_tier`, `routing_state`, `decision_state`, `timing_state`, `trade_readiness_state`, and `authority_state`. Use those fields for quick routing/status answers; do not compress them back into one label or treat `IN_BAND`, `Tier A`, or `A-WATCH` as approval-card, paper, live, or capital readiness. When WF84 lacks a required band on Tier C monitor rows, the frontdoor may use `tmp\tier-c-band-status.json` as monitor-grade timing context only; those overlays must remain `not_trade_ready_monitor_grade` and review-only.
`wf78_route_readiness_p3_market_ranking.py` is the review-only P3 queue compiler above the frontdoor. It ranks current route-readiness rows into market-aware categories such as owner-gated approval-card candidates, in-band review monitors, reclaim watch, no-chase, monitor-grade triage, and avoid-until-reclaim. It uses the existing market-session policy to mark names that need a market-window refresh, but it does not refresh market data, create cards, approve capital, prepare orders, mutate canon/portfolio state, or infer owner approval.
`full_intelligence_answer_parity.py` is the WF84/WF85 full-answer value-parity harness. It compares the old rich answer packet/card stack against the WF84/WF85 assembled route and writes section-level proof for duplicate-surface retirement planning. Pilot mode is for quick diagnosis; duplicate-surface retirement planning requires `--all` coverage across the full WF84 ticker population. It is report-only and fail-closed: archive/delete/apply remain false when parity is blocked.
`finance_response_quality_slice.py` is the internal answer-quality service slice for finance Q&A. It reuses the WF75 service-slice pattern only as an internal rubric, scores whether WF84/WF85 answers carry freshness/band/stop, macro, 5DMA/20DMA, and authority-boundary warnings, confirms WF72 remains support-only, and owns remediation tracks for visible coverage/freshness gaps.

Run:
```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\canonical_finance_data_plane_contract.py --write --validate
python scripts\canonical_finance_data_plane.py --write --write-db --validate
python scripts\tier_c_band_status_refresh.py --no-skip-provider-refresh --write --validate
python scripts\wf78_missing_band_context_repair.py --write --validate
python scripts\finance_cache_frontdoor.py --write --validate
python scripts\wf78_route_readiness_p3_market_ranking.py --write --validate
python scripts\trade_grade_full_answer_assembler.py --all-wf84 --write --validate
python scripts\full_intelligence_answer_parity.py --all --write --pretty
python scripts\finance_response_quality_slice.py --write --write-md --validate
python scripts\canonical_finance_data_plane_phase6_10.py --write --validate
python scripts\canonical_finance_data_plane_retirement_readiness.py --write --validate
python scripts\db_lifecycle_manifest.py --write --validate
python scripts\test_route_readiness.py
```

Current proof:
- `tmp/finance-sql-canon-access-validation.json`
- `tmp/canonical-finance-data-plane-contract.json`
- `tmp/canonical-finance-data-plane.json`
- `tmp/canonical-finance-data-plane-validation.json`
- `tmp/canonical-finance-data-plane.sqlite`
- `tmp/tier-c-band-status.json`
- `tmp/wf78-missing-band-context-repair.json`
- `tmp/finance-cache-frontdoor.json`
- `tmp/wf78-route-readiness-p3-market-ranking.json`
- `tmp/trade-grade-full-answer-assembler.json`
- `tmp/canonical-finance-data-plane-phase6-10.json`
- `tmp/canonical-finance-data-plane-retirement-readiness.json`
- `tmp/full-answer-parity/full-answer-parity-rollup.json`
- `tmp/finance-response-quality-slice.json`

SQLite posture:
- `state\finance\finance-canon.sqlite` is the guarded internal SQL-primary current-state layer for answer-path scope, evidence freshness, reference levels, source lineage, tier routing, and universe membership
- WF84's `tmp/canonical-finance-data-plane.sqlite` remains a rebuildable derived lookup above that guarded current-state layer
- loaded from the validated JSON packet, not ad hoc source reads
- lifecycle-classified by `db_lifecycle_manifest.py`
- decision views include `v_current_decision_overview`, `v_owner_action_queue`, `v_decision_grade_os_layer`, and `v_source_lineage_drillback`
- `finance_intelligence_state.py ticker <TICKER>` starts from guarded SQL-canon current-state and prefers WF85/WF84 only when the read-only consumer switch is clean and freshness/source guards are clean; stale, blocked, or material state falls back to source-open required instead of silently serving generated answers.
- `finance_intelligence_state.py` carries an explicit WF72 support-only guard; `test_finance_intelligence_state_wf72_guard.py` proves WF72 cannot be promoted into finance answer ownership by future route drift.
- PM cockpit reads allowlisted WF84 views for local read-only Finance OS visibility
- WF85 decision cards and morning paper recommendation cards consume WF84 behind parity/switch gates; generated cards still do not approve execution
- full ticker-intelligence answers must consult `tmp/full-answer-parity/<TICKER>.json`; if parity is blocked, the front door reports section status/fallback instead of treating duplicate surfaces as retirement-ready
- finance response quality is measured by `tmp/finance-response-quality-slice.json` and then surfaced through WF74/PM; it does not create customer/public SaaS output or approval authority
- the weekday `wf78_daily_freshness_loop.py` refreshes the WF84 packet, SQLite companion, phase 6-10 proof, and retirement-readiness proof after the WF78 feeder chain
- retirement readiness includes an owner-approval archive plan, but archive/delete/apply remain false until a separate lifecycle packet and exact owner approval

Boundary:
- internal/personal finance infrastructure only; no retail/customer launch, no customer/account/PII/suitability/brokerage schema, no canon/portfolio/cash/risk-rule mutation, no capital deployment, no paper/live/account action, no SQL/capsule/dashboard row as approval, and no owner approval inference.

## WF85 trade-grade decision OS

`trade_grade_decision_os_contract.py` is the Phase 0 contract for the decision and approval-card layer above WF84. It defines the review-only card fields, decision-state vocabulary, implementation lanes, source/freshness gates, risk/sizing overlay posture, and hard false authority flags. `trade_grade_decision_cards.py` is the Phase 1 builder/gate runner. It consumes WF84's validated JSON/SQLite plane and writes fail-closed decision cards, source/freshness gate proof, generated-card authority/vocabulary validation, approval-card draft eligibility, recommendation-only risk/sizing overlay, and compact current-regime analog scenario context. The scenario context is displayed on cards only as review context; it is not a probability, score, deployment rank, sizing recommendation, approval, or execution signal. `trade_grade_repair_conveyor.py` routes fail-closed cards back to WF78/WF84 source, freshness, and band/stop repair lanes and identifies the tiny review-ready pilot queue. Its normal repair rows are finance-domain debt only; monitor-only, below-stop/invalidation, and band/stop context rows must not become PM implementation blockers unless the conveyor itself fails validation. Tier A/B rows require daily decision-grade entry-band/stop coverage for finance review; missing coverage is finance-domain repair debt, and canon/note apply remains limited to the approved `entry_band` maintenance gate. `tier_ab_band_freshness_cron_guard.py` is the cron hardening guard for that policy: it proves complete Tier A/B band rows have current market-date band context, verifies missing-band repair coverage for any still-missing rows, and verifies cron freshness contracts carry the guard artifacts. Phase 1 is explicitly fail-closed: WF84 SQLite/JSON parity, source/freshness, state-precedence, generated-card authority/vocabulary, Tier A/B band freshness, and repair-conveyor gates must run before approval-card drafts.

`wf85_decision_os_review_packet.py` is the compact review-only operating surface above the existing WF85 proof stack. It reads decision cards, source/freshness, authority validation, approval gate, risk overlay, repair conveyor, readiness/freshness rollups, deployment timing, full-answer assembler, and capital-review queue artifacts, then writes `tmp/wf85-decision-os-review-packet.json` plus optional Markdown. Use it to rank the Tier A/B repair/review surface and choose the next finance-domain repair lane without generating approval-card drafts or implying capital/execution authority.

Run:
```powershell
python scripts\trade_grade_decision_os_contract.py --write --validate
python scripts\trade_grade_decision_cards.py --write --validate
python scripts\trade_grade_repair_conveyor.py --write --validate
python scripts\tier_ab_band_freshness_cron_guard.py --write --validate
python scripts\trade_grade_os_freshness_cron_runner.py --component all --full-answer-mode changed --write --write-md --validate
python scripts\trade_grade_os_freshness_cron_runner.py --component cards --write --validate
python scripts\trade_grade_os_freshness_cron_runner.py --component answers --full-answer-mode always --write --validate
python scripts\wf85_deployment_timing_gate.py --write --validate
python scripts\trade_grade_full_answer_assembler.py --all-wf84 --write --validate
python scripts\wf85_decision_os_review_packet.py --write --write-md --validate
python scripts\test_wf85_decision_os_review_packet.py
python scripts\workflow_router.py WF85 --answer all --write-capsules --validate
```

Current proof:
- `tmp/trade-grade-decision-os-contract.json`
- `tmp/trade-grade-source-freshness-gate.json`
- `tmp/trade-grade-decision-cards.json`
- `tmp/trade-grade-decision-card-authority-validation.json`
- `tmp/trade-grade-approval-card-gate.json`
- `tmp/trade-grade-risk-sizing-overlay.json`
- `tmp/trade-grade-repair-conveyor.json`
- `tmp/wf85-decision-os-review-packet.json`
- `tmp/wf85-decision-os-review-packet.md`
- `tmp/tier-ab-band-freshness-cron-guard.json`
- `tmp/trade-grade-os-freshness-cron-runner.json`
- `tmp/wf78-missing-band-context-repair.json`

Planned WF85 artifact:
- `tmp/trade-grade-decision-os-challenger-review.json`

Boundary:
- internal/personal decision support only; no customer/account/PII/suitability schema, no external delivery, no canon/portfolio/cash/sizing/risk-rule mutation, no capital deployment approval, no paper/live/account action, no money movement, and no generated card, score, SQL row, or approval-card draft becomes Randall approval.

Cron posture:
- `trade_grade_os_freshness_cron_runner.py` is the deterministic WF84/WF85 freshness owner command for scheduled proof. It supports targeted `--component` modes (`foundation`, `wf78`, `wf84`, `cards`, `answers`, `parity`, `repair`, `all`) and `--full-answer-mode changed|always|never`. The scheduled/default optimized posture is `--component all --full-answer-mode changed`: it refreshes the broad chain but skips the expensive WF85 full-answer assembler, post-answer WF84 rebuild, and parity proof when the semantic source digest is unchanged. Use `always` for a forced full-answer closeout and narrower `--component` modes for targeted maintenance.
- `operator_action=NO_REPLY` is normal while `review_ready_count=0` and `approval_card_draft_count=0`, even when the Tier A/B band guard has warning-class finance-domain debt. `MAIN_HANDOFF_REQUIRED` is expected when review-ready cards appear; any review-ready/draft candidates route to main-session review only, and no execution or approval authority is inferred.
- `wf85_paper_deployment_notification_digest.py`, `wf85_paper_deployment_telegram_notifier.py`, and `wf85_paper_deployment_telegram_cron_runner.py` provide the review-only paper-deployment radar above WF85/WF67. The digest classifies deployment-ready-for-review, near-deployment, watch, and blocked/repair rows; the notifier can deliver that digest to Randall on Telegram; the cron runner executes the manager -> digest -> notifier -> cron-control sequence serially. A deployment-ready row means review/preparation only. Execution-ready stays zero until exact Randall order approval, fresh WF67 guard, fresh short-lived kill switch, paper endpoint/wrapper, redacted audit, and reconciliation proof exist. Telegram supports REVIEW/PREPARE only; APPROVE is not active.

## WF78 tier funnel contract (Phase 1)

`wf78_tier_funnel_contract.py` is the single machine-readable source for the WF78 D/C/B/A funnel. It encodes the tiers, each transition's gate question and required evidence, the competition rules (C->B 15-per-100-batch nomination + 50 Tier B cap; B->A 25 Tier A cap + +5 challenger margin + owner approval), the state vocabularies, the decay/demotion triggers, the caps, and the authority boundary as data. `06. Playbooks/Coverage Admission and Promotion Protocol.md` is its prose mirror. The future promotion gates import its constants instead of re-deriving the rules, and it cross-checks its caps against `wf78_tier_capacity_policy_gate.py` so the two cannot silently diverge.

Run:
```powershell
python scripts\wf78_tier_funnel_contract.py --write --validate
```

Current proof:
- `tmp/wf78-tier-funnel-contract.json` (schema `veritas.wf78_tier_funnel_contract.v1`; 56 checks green, caps cross-checked)

Boundary:
- contract/proof only; it moves no ticker, imports/applies nothing, and grants no promotion, capital-deployment, production answer-path, canon/portfolio, customer/external, paper/live/account, or owner-approval-inference authority.

## WF78 tier funnel promotion gate (Phase 2)

`wf78_tier_funnel_promotion_gate.py` is the report-only deterministic evaluator for Tier D -> C (monitorability) and Tier C -> B (research-worthiness). It imports the Phase 1 contract constants (`TRANSITIONS`, `STATE_VOCABULARY`, `TIER_B_CAP`, `TIER_B_BATCH_NOMINATION_LIMIT`) and, per candidate transition, enforces required-evidence completeness, decay/reject from-states, the 15-per-batch C->B nomination limit, and live Tier B cap pressure (read from `wf78_tier_capacity_policy_gate.py`). Each candidate gets one verdict: `eligible_for_admission`, `blocked_missing_evidence`, `blocked_decay_state`, `blocked_invalid_state`, `blocked_batch_nomination_limit`, `blocked_tier_b_cap`, `blocked_unknown_transition`, or `routed_to_other_gate` (Tier B->A goes to Phase 3). The live default population is the tier-promotion review gate's Tier C->B research queue; `--requests <json>` feeds ad-hoc transitions instead. 11 embedded self-tests exercise every verdict branch as runtime proof.

An `eligible_for_admission` verdict means the evidence/competition gate would pass; it is not an admission and not owner approval. The gate admits/promotes nothing.

Run:
```powershell
python scripts\wf78_tier_funnel_promotion_gate.py --write --validate
```

Current proof:
- default `tmp/wf78-tier-funnel-promotion-gate.json` remains the broad repair-queue proof.
- request-fed `tmp/wf78-tier-b-research-packet-phase2-eval.json` has 15 C->B candidates and 15 `eligible_for_admission` verdicts from `tmp/wf78-tier-b-research-packet-requests.json`.

Boundary:
- evaluation/proof only; no admission, promotion, import/apply, production answer-path, canon/portfolio, customer/external, paper/live/account, or owner-approval-inference authority.

## WF78 tier A competitive promotion gate (Phase 3)

`wf78_tier_a_competitive_promotion_gate.py` is the report-only deterministic evaluator for the scarce Tier B -> A 25-seat deployment-review roster. It imports the Phase 1 contract constants (`TIER_A_CAP`, `TIER_A_CHALLENGER_MARGIN_POINTS`, the b_to_a `TRANSITIONS` ladder/required evidence, `STATE_VOCABULARY`) and enforces the competitive ladder. Its output feeds automated non-capital routing; it does not ask Randall for ordinary Tier A/B routing approval.

The gate can identify a candidate that is eligible for non-capital routing competition. Capital deployment and trade/order execution remain separate owner approval gates. A score creates eligibility for competition; it never authorizes capital deployment or execution.

Run:
```powershell
python scripts\wf78_tier_a_competitive_promotion_gate.py --write --validate
```

Current proof:
- `tmp/wf78-tier-a-competitive-promotion-gate.json` (schema `veritas.wf78_tier_a_competitive_promotion_gate.v1`; 49 checks + 11 self-tests green; live proof has 34 candidates, 2 `eligible_for_auto_tier_a_routing`, 29 `blocked_not_validated`, and 3 `blocked_decay_state`)

Boundary:
- evaluation/proof only; no import/apply, production answer-path, canon/portfolio, customer/external, paper/live/account, or capital/execution approval authority. `A-DEPLOY` still requires a separate exact order approval before any paper/live action.

## WF78 funnel routing packet (Phase 4 legacy)

`wf78_funnel_owner_decision_packet.py` is a legacy report-only output layer that turns the Phase 2 and Phase 3 gate verdicts into candidate routing packets. The current operating route is `wf78_auto_tier_router.py` -> `tmp/wf78-auto-tier-routing.json`; do not use the legacy packet layer to ask Randall for ordinary tier-routing approvals.

Trust rule: a source gate is trusted only if it is present, its schema matches, its `status` is `ok`, and its `validation.status` is `ok`. If a gate is untrusted, any packet that would be actionable is downgraded so a stale gate can never present a stale "ready" routing state. Any capital deployment or paper/live action still requires separate exact approval.

Run:
```powershell
python scripts\wf78_funnel_owner_decision_packet.py --write --validate
```
`--phase2 <path>` and `--phase3 <path>` override the source gate paths (used for fixture proof without clobbering the live artifacts).

Current proof:
- `tmp/wf78-funnel-owner-decision-packet.json` is legacy proof; prefer `tmp/wf78-auto-tier-routing.json` for current non-capital routing state.

Boundary:
- routing-packet/proof only; reads existing gate artifacts; no import/apply, production answer-path, canon/portfolio, customer/external, paper/live/account, money-movement, or capital/execution approval authority.

## WF78 routing dashboard

`wf78_routing_dashboard.py` is the secondary route-first control-plane layer over WF78 funnel JSON proof. It now requires `tmp/wf78-auto-tier-routing.json` as the primary non-capital routing source and keeps the Phase 2/3/4 funnel rows as legacy evidence/repair context. Use the auto-router for current Tier A/B/C state; use this dashboard when the question is "which legacy evidence lane owns this blocker?"

Run:
```powershell
python scripts\wf78_routing_dashboard.py --write --write-db --validate
```

Current proof:
- `tmp/wf78-routing-dashboard.json`
- `tmp/wf78-routing-dashboard.sqlite`
- live output is secondary legacy route proof; `summary.primary_routing_source` must be `tmp/wf78-auto-tier-routing.json`
- PM program state, PM implementation queue, and PM cockpit source registry expose `wf78_auto_tier_router` as the primary derived non-capital routing state

Boundary:
- derived routing/index only; JSON gate artifacts remain source proof. No canon, import, promotion, approval, production answer-path, portfolio, customer, paper/live/account, or execution authority.

## WF78 lower-tier funnel promotion doctrine

Status: Phase 1 funnel contract built (`wf78_tier_funnel_contract.py`), Phase 2 report-only `tier_funnel_promotion_gate` built (`wf78_tier_funnel_promotion_gate.py`, Tier D->C / Tier C->B), Phase 3 report-only `tier_a_competitive_promotion_gate` built (`wf78_tier_a_competitive_promotion_gate.py`, Tier B->A), legacy Phase 4 routing packet layer built (`wf78_funnel_owner_decision_packet.py`), current automated non-capital router built (`wf78_auto_tier_router.py`), model-safe clean tier roster built (`wf78_clean_tier_roster.py`), tier semantics guard built (`wf78_tier_semantics_guard.py`), Tier C attention trigger built (`wf78_tier_c_attention_trigger.py`), Tier C hold quote/card recheck built (`wf78_tier_c_hold_recheck.py`), daily routing delta built (`wf78_routing_delta.py`), `route TICKER` quick packet built (`wf78_route_ticker.py`), owner-gated `A-DEPLOY-CANDIDATE` capital-review queue built (`wf78_capital_review_queue.py`), AI event-triggered rerouting built (`wf78_event_triggered_rerouting.py`), and market execution-readiness cron hardening built (`market_execution_readiness_cron_hardening.py`). Downstream PM/routing-map/cockpit consumer sync is complete for `pm_program_state.py`, `pm_implementation_job_queue.py`, `state/pm-cockpit-source-registry.json`, and `wf78_routing_dashboard.py`; the current operating target is using event rerouting plus daily Tier 1 quote proof to drive targeted evidence repair and non-executing owner-card preparation.

`wf78_clean_tier_roster.py` is the model-safe current roster surface for Tier A/B/C questions. It reads `tmp/wf78-auto-tier-routing.json` as the only current tier authority, reads `tmp/wf78-tier-label-sync-preview.json` only as audit/formal-label context, and writes `tmp/wf78-clean-tier-roster.json` with exclusive `true_tier_a`, `true_tier_b`, and `true_tier_c` arrays plus overlap explanation arrays. Use this artifact, or the auto-router directly, when answering "who is Tier A/B/C?" Do not answer current tier membership from the legacy label sync preview.

`wf78_truth_layer_map.py` is the model-safe truth-layer contract for WF78 tier interpretation. It writes `tmp/wf78-truth-layer-map.json` and classifies current authority, repair/readiness, audit-only label sync, retired Legacy 42 archive proof, and paper-readiness guardrail layers. Current tier membership may be answered only from `tmp/wf78-clean-tier-roster.json` or `tmp/wf78-auto-tier-routing.json`. `tmp/wf78-tier-promotion-review-gate.json` is a repair/review queue, `tmp/deployment-readiness-surface.json` is actionability/freshness context, `tmp/wf78-tier-label-sync-preview.json` is audit-only, `tmp/legacy-42-full-archive-packet.json` plus `tmp/legacy-42-no-runtime-imports-guard.json` are retirement proof only, and `tmp/alpaca-paper-readiness/*` is execution guardrail context. None of those non-authority layers may decide current Tier A/B/C membership.

`wf78_route_ticker.py --ticker <TICKER> --write --validate` writes a single-ticker packet such as `tmp/wf78-route-anet.json`. Its `route_readiness` object is the quick human/status contract: show `routing_tier`, `routing_state`, `timing_state`, `decision_state`, `trade_readiness_state`, and `authority_state` as separate fields. An in-band `timing_state` is price/timing context only; it never means decision-ready, approval-ready, paper-ready, live-ready, or owner-approved without the separate trade-readiness and authority gates.

`tier_c_band_status_refresh.py` writes `tmp\tier-c-band-status.json` as a monitor-grade reference-band context surface for Tier C rows. `wf78_missing_band_context_repair.py` writes `tmp\wf78-missing-band-context-repair.json` to prove whether any missing-band rows are actually ready for decision-grade band repair. These artifacts may help classify monitor/watch timing states, but they do not create decision-grade entry bands, Tier B/A promotion, approval-card readiness, paper readiness, live readiness, or capital/execution authority.

`wf78_tier_semantics_guard.py` validates that the clean roster and label preview preserve the semantics boundary: auto-router wins, label preview is audit-only, exclusive lists match router rows, and capital/trade flags remain false. It writes `tmp/wf78-tier-semantics-guard.json`; current proof has zero tier mismatches and explicit wording guards for promotion-overlap names that must not be called current Tier B.

`wf78_tier_semantics_guard.py` also requires `tmp/wf78-truth-layer-map.json` to stay clean. It fails if any non-authority layer can decide current membership, if paper-readiness guardrails are treated as tier truth, or if tier states such as `A-READY`, `A-CHALLENGED`, `A-REPAIR`, `B-CANDIDATE`, `B-VALIDATED`, or `B-STALE` are confused with tier membership. Treat these as substates inside Tier A or Tier B, never as separate tiers.

`wf78_tier_label_sync_preview.py` is audit/apply-preview only. Its artifact now carries `semantic_contract.not_current_tier_authority=true` and `semantic_contract.current_tier_authority=tmp/wf78-auto-tier-routing.json`. It may show formal/legacy Tier B label context for names currently routed Tier A; those rows are overlap explanation, not current Tier B membership.

`wf78_tier_c_attention_trigger.py` scans active Tier C names for fresh price momentum, initial fundamental strength, valuation/quality warnings, and repair burden. It writes `tmp/wf78-tier-c-attention-trigger.json` / `.sqlite` and marks triggered rows as `C-CANDIDATE`, `C-CANDIDATE-REPAIR`, or `C-THEME-WATCH` for auto-router consumption. This is attention routing only: it does not admit Tier B/A, write universe/canon/portfolio state, approve capital deployment, or authorize paper/live execution.

`wf78_tier_c_hold_recheck.py` refreshes review-only post-close quote overlays and ticker cards for Tier C held/repair candidates, then reruns the Tier C attention trigger and auto-router. It writes `tmp/wf78-tier-c-hold-recheck.json` plus `tmp/wf78-tier-c-hold-recheck-card-summary.json` and is included in the daily `tier_routing` phase before the C-to-B pipeline. It may move names into the attention candidate set, but it does not approve Tier B, capital deployment, or execution.

The lower tiers use the same discipline as Tier A, but with lighter standards and lower authority. Tier D -> C is monitorability admission. Tier C -> B is research-worthiness admission. Neither route creates investability, deployment, production answer-path, portfolio, paper, live, customer, or owner-approval authority.

Tier D posture:
- raw intake
- weak or unresolved source proof
- unclear identity
- sector/theme mapping repair
- ticker-card/provider gaps
- duplicate/overlap review
- low-confidence business model
- stale or broken evidence

Tier D states:
- `D-RAW`
- `D-IDENTITY-REPAIR`
- `D-SOURCE-REPAIR`
- `D-DUPLICATE-REVIEW`
- `D-REJECT`

Tier D -> Tier C requires:
- clean ticker/company identity
- sector and industry classification
- basic business model description
- source-open identity proof
- provider/runtime proof
- basic liquidity sanity check
- duplicate/conflict check against current universe
- explicit reason to monitor

Tier C posture:
- broad radar
- cheap monitoring
- macro/theme watch
- valuation-reset watch
- earnings/revision inflection watch
- technical-improvement watch
- source/evidence repair queue
- bounded Tier B candidate nomination pool

Tier C states:
- `C-MONITOR`
- `C-REPAIR`
- `C-THEME-WATCH`
- `C-CANDIDATE`
- `C-DECAY`

Tier C -> Tier B candidate status requires:
- macro/theme fit
- business quality reason
- initial fundamentals snapshot available
- valuation context available
- analyst/revision layer available or explicitly not applicable
- initial technical/price-band context
- risk reason understood
- portfolio role identified
- source-open proof usable
- evidence repair burden acceptable

Competitive rules:
- each 100-name batch may nominate no more than 15 Tier B candidates
- only top-ranked Tier C names enter the Tier B research queue
- if Tier B is full at 50, a new candidate must beat the weakest Tier B candidate or remain Tier C
- a score can nominate research work; it cannot auto-promote a ticker

Tier B states:
- `B-CANDIDATE`
- `B-VALIDATED`
- `B-STALE`
- `B-CHALLENGED`
- `B-REJECT-TO-C`

Implemented:
- `tier_funnel_promotion_gate` is built as `wf78_tier_funnel_promotion_gate.py` (see the "WF78 tier funnel promotion gate (Phase 2)" section above): deterministic, report-only gate for Tier D -> C and Tier C -> B that validates monitorability, research-worthiness, batch limits, Tier B cap pressure, evidence gaps, and decay states before any admitted tier change.

Implemented (Phase 3):
- `tier_a_competitive_promotion_gate` is built as `wf78_tier_a_competitive_promotion_gate.py` (see the "WF78 tier A competitive promotion gate (Phase 3)" section above): deterministic, report-only Tier B -> A competitive deployment-roster gate over the same contract. The full promotion machinery now exists for all three transitions; the next WF78 target shifts from machinery to per-lead Tier B research/evidence depth.

Boundary:
- doctrine and validator targets only; no import/apply, no D/C/B/A promotion by score alone, no capital deployment, no production answer-path change, no canon/portfolio mutation, no customer/external output, no paper/live/account action, and no owner approval inference.

## WF78 competitive Tier A promotion doctrine

Status: continuity adopted; report-only validator target built as `wf78_tier_a_competitive_promotion_gate.py` (Phase 3 above).

Tier B -> Tier A promotion is competitive, not checklist-based. A Tier B ticker can become Tier A only when it has complete current evidence, fits the portfolio, has an actionable readiness state, and either fills an open Tier A seat or defeats the weakest relevant Tier A incumbent by at least 5 points. A score creates eligibility for competition; it never auto-promotes a ticker.

Operating ladder:
- `Tier B Candidate`: research-candidate from Tier C/D monitoring or macro overlay; no portfolio action.
- `Tier B Validated`: full research packet exists; serious-monitor quality, not deployment quality.
- `Tier A Nominee`: validated name has a live reason to compete for a Tier A seat.
- `Tier A Approved`: evidence completeness, relative superiority, portfolio-fit/capacity, and owner approval all pass.

Tier A states:
- `A-NOMINEE`
- `A-WATCH`
- `A-READY`
- `A-DEPLOY`
- `A-HOLD`
- `A-CHALLENGED`
- `A-DEMOTE`

Hard gates:
- source-open proof
- current ticker card
- current price, entry band, and stop/invalidation
- thesis and counter-thesis
- risk register and invalidation event
- current fundamentals/earnings context
- valuation context
- analyst/revision layer
- portfolio-fit and concentration check
- deployment/readiness state
- Tier A capacity check
- owner approval

Implemented (Phase 3):
- `tier_a_competitive_promotion_gate` is built as `wf78_tier_a_competitive_promotion_gate.py`: deterministic, review-only gate that validates the 10 hard evidence families, `B-VALIDATED` state, open-seat admission vs. challenger/incumbent comparison, decay/invalid states, and the 25-name Tier A cap. The deepest reachable verdict is `eligible_for_auto_tier_a_routing`, which feeds the auto-router as non-capital routing state only; capital deployment and execution remain separate exact owner gates.

Boundary:
- report-only validator; no Tier A roster change, no checklist/score auto-promotion, no capital deployment, no production answer-path change, no canon/portfolio mutation, no customer/external output, no paper/live/account action, and no owner approval inference. `A-DEPLOY` means approval-ready packet only; execution still requires separate exact order approval.

## Go validator layer

The bounded Go validator layer lives under `scripts/go/`. It is for fast, strict, read-only lint checks over generated JSON/Markdown proof artifacts.

Freshness: compiled binaries in `scripts/go/bin/` can fall behind their source — a fixed `.go` that is never rebuilt keeps emitting the old (wrong) result. `python scripts/go_binary_freshness_guard.py --write --validate` flags any `bin/*.exe` older than its `cmd/<name>` or shared `internal/` source; it is review-only (it does not build) and runs inside the SQL Coverage guard. After editing any `.go`, rebuild with the build loop below before trusting binary output.

Run:
```powershell
cd scripts\go
go test .\...
cd ..\..
New-Item -ItemType Directory -Force -Path scripts\go\bin | Out-Null
cd scripts\go
foreach ($cmd in Get-ChildItem -Path cmd -Directory | Sort-Object Name) { go build -o (Join-Path "bin" ($cmd.Name + ".exe")) (".\cmd\" + $cmd.Name); if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
go run .\cmd\wf75-smb-boundary-lint --root ..\.. --out ..\..\tmp\wf75-smb-boundary-lint.json
go run .\cmd\finance-sql-boundary-lint --root ..\.. --out ..\..\tmp\finance-sql-boundary-lint.json
go run .\cmd\python-sql-contract-lint --root ..\.. --out ..\..\tmp\python-sql-contract-lint.json
go run .\cmd\sql-schema-drift-lint --root ..\.. --out ..\..\tmp\sql-schema-drift-lint.json
go run .\cmd\sql-proof-probe --root ..\.. --out ..\..\tmp\sql-proof-probe.json
go run .\cmd\go-json-proof-contract-lint --root ..\.. --out ..\..\tmp\go-json-proof-contract-lint.json
go run .\cmd\go-sql-canon-proof-bundle-lint --root ..\.. --driver inprocess --out ..\..\tmp\go-sql-canon-proof-bundle-lint.json
go run .\cmd\go-json-proof-warning-residue-lint --root ..\.. --out ..\..\tmp\go-json-proof-warning-residue-lint.json
go run .\cmd\go-sql-source-artifact-freshness-lint --root ..\.. --driver inprocess --out ..\..\tmp\go-sql-source-artifact-freshness-lint.json
go run .\cmd\go-sql-source-lineage-producer-contract-lint --root ..\.. --freshness-report ..\..\tmp\go-sql-source-artifact-freshness-lint.json --out ..\..\tmp\go-sql-source-lineage-producer-contract-lint.json
go run .\cmd\go-implementation-closeout-ledger-lint --root ..\.. --out ..\..\tmp\go-implementation-closeout-ledger-lint.json
go run .\cmd\go-json-proof-structural-validator --root ..\.. --driver inprocess --out ..\..\tmp\go-json-proof-structural-validator.json
go run .\cmd\go-entry-stop-band-freshness-validator --root ..\.. --driver inprocess --out ..\..\tmp\go-entry-stop-band-freshness-validator.json
go run .\cmd\go-pm-queue-authority-lint --root ..\.. --out ..\..\tmp\go-pm-queue-authority-lint.json
go run .\cmd\go-finance-answer-completeness-validator --root ..\.. --out ..\..\tmp\go-finance-answer-completeness-validator.json
go run .\cmd\go-cross-db-referential-integrity-probe --root ..\.. --driver inprocess --out ..\..\tmp\go-cross-db-referential-integrity-probe.json
go run .\cmd\go-workflow-artifact-freshness-gate --root ..\.. --driver inprocess --out ..\..\tmp\go-workflow-artifact-freshness-gate.json
go run .\cmd\go-validator-timing-benchmark --root ..\.. --out ..\..\tmp\go-validator-timing-benchmark.json
go run .\cmd\go-execution-board-structural-lint --root ..\.. --out ..\..\tmp\go-execution-board-structural-lint.json
go run .\cmd\go-paper-trading-guard-preflight --root ..\.. --out ..\..\tmp\go-paper-trading-guard-preflight.json
go build -o ..\..\tmp\go-binaries\go-sql-latency-probe.exe .\cmd\go-sql-latency-probe
go build -o ..\..\tmp\go-binaries\go-sql-inventory-helper.exe .\cmd\go-sql-inventory-helper
go build -o ..\..\tmp\go-binaries\go-finance-human-notes-sql-check.exe .\cmd\go-finance-human-notes-sql-check
..\..\tmp\go-binaries\go-sql-latency-probe.exe --root ..\.. --iterations 5 --driver inprocess --out ..\..\tmp\go-sql-latency-probe.json
..\..\tmp\go-binaries\go-sql-inventory-helper.exe --root ..\.. --driver inprocess --out ..\..\tmp\go-sql-inventory-helper.json
go run .\cmd\go-sql-source-truth-manifest --root ..\.. --out ..\..\tmp\go-sql-source-truth-authority-manifest.json
go run .\cmd\go-finance-data-coverage-probe --root ..\.. --out ..\..\tmp\go-finance-data-coverage-probe.json
..\..\tmp\go-binaries\go-finance-human-notes-sql-check.exe --root ..\.. --driver inprocess --out ..\..\tmp\go-finance-human-notes-sql-check.json
go run .\cmd\go-finance-universe-validation-probe --root ..\.. --out ..\..\tmp\go-finance-universe-validation-probe.json
go run .\cmd\go-wf78-sql-phase2-readiness-probe --root ..\.. --out ..\..\tmp\go-wf78-sql-phase2-readiness-probe.json
go run .\cmd\go-sql-consumer-authority-guard --root ..\.. --out ..\..\tmp\go-sql-consumer-authority-guard.json
cd ..\..
python scripts\python_go_sql_parity_check.py --write --validate
python scripts\python_go_sql_migration_candidates.py --write --validate
python scripts\python_go_source_truth_manifest_parity.py --write --validate
python scripts\python_go_source_truth_parity_validator_parity.py --write --validate
python scripts\python_go_sql_500_expansion_gate_parity.py --write --validate
python scripts\python_go_finance_data_coverage_probe_parity.py --write --validate
python scripts\python_go_finance_human_notes_sql_check_parity.py --write --validate
python scripts\python_go_finance_universe_validation_parity.py --write --validate
python scripts\python_go_wf78_sql_phase2_readiness_parity.py --write --validate
python scripts\python_go_durable_output_parity_repeated_gate.py --write --validate --cycles 3
python scripts\python_go_sql_consumer_authority_guard_parity.py --write --validate
python scripts\python_go_sql_consumer_authority_guard_fixture_parity.py --write --validate
python scripts\python_go_sql_consumer_authority_dashboard_ab.py --write --validate --cycles 3
python scripts\python_go_sql_consumer_authority_demotion_dry_run.py --write --validate
python scripts\python_go_sql_consumer_authority_controlled_router.py --write --validate
python scripts\python_go_sql_helper_demotion_readiness_gate.py --write --validate
python scripts\python_go_sql_helper_demotion_queue.py --write --validate
python scripts\python_go_sql_helper_contract_gate.py --write --validate
python scripts\python_go_sql_helper_controlled_router_batch.py --write --validate
python scripts\python_go_sql_helper_go_primary_history_gate.py --write --validate --cycles 3
python scripts\python_go_sql_helper_default_route_promotion.py --write --validate
python scripts\python_go_sql_helper_default_route_history_gate.py --write --write-history --validate --cycles 5
python scripts\python_go_sql_helper_fallback_removal_readiness_gate.py --write --validate
python scripts\python_go_sql_helper_retirement_gate.py --write --validate
python scripts\go_sql_inprocess_driver_pilot_gate.py --write --write-md --validate --run-probes --build-binaries --binary-route-active
python scripts\go_fast_proof_validators.py --write --validate
python scripts\wf72_a2_fallback_fixture_prep.py --write --validate
python scripts\automation_stack_hardening_pass.py --write --validate
```

Current proof:
- `tmp/wf75-smb-boundary-lint.json`
- `tmp/finance-sql-boundary-lint.json`
- `tmp/python-sql-contract-lint.json`
- `tmp/sql-schema-drift-lint.json`
- `tmp/sql-proof-probe.json`
- `tmp/go-json-proof-contract-lint.json`
- `tmp/go-sql-canon-proof-bundle-lint.json`
- `tmp/go-json-proof-warning-residue-lint.json`
- `tmp/go-sql-source-artifact-freshness-lint.json`
- `tmp/go-sql-source-lineage-producer-contract-lint.json`
- `tmp/go-implementation-closeout-ledger-lint.json`
- `tmp/go-json-proof-structural-validator.json`
- `tmp/go-entry-stop-band-freshness-validator.json`
- `tmp/go-pm-queue-authority-lint.json`
- `tmp/go-finance-answer-completeness-validator.json`
- `tmp/go-cross-db-referential-integrity-probe.json`
- `tmp/go-workflow-artifact-freshness-gate.json`
- `tmp/go-validator-timing-benchmark.json`
- `tmp/go-execution-board-structural-lint.json`
- `tmp/go-paper-trading-guard-preflight.json`
- `tmp/go-sql-latency-probe.json`
- `tmp/go-sql-inventory-helper.json`
- `tmp/go-binaries/go-sql-latency-probe.exe`
- `tmp/go-binaries/go-sql-inventory-helper.exe`
- `tmp/go-binaries/go-finance-human-notes-sql-check.exe`
- `tmp/python-go-sql-parity-check.json`
- `tmp/python-go-sql-migration-candidates.json`
- `tmp/go-sql-source-truth-authority-manifest.json`
- `tmp/python-go-source-truth-manifest-parity.json`
- `tmp/go-source-truth-parity-validation.json`
- `tmp/python-go-source-truth-parity-validator-parity.json`
- `tmp/go-sql-500-ticker-expansion-design-gate.json`
- `scripts/go/bin/go-sql-500-expansion-design-gate.exe`
- `tmp/python-go-sql-500-expansion-gate-parity.json`
- `tmp/go-finance-data-coverage-probe.json`
- `tmp/python-go-finance-data-coverage-probe-parity.json`
- `tmp/go-finance-human-notes-sql-check.json`
- `tmp/python-go-finance-human-notes-sql-check-parity.json`
- `tmp/go-finance-universe-validation-probe.json`
- `tmp/python-go-finance-universe-validation-parity.json`
- `tmp/go-wf78-sql-phase2-readiness-probe.json`
- `tmp/python-go-wf78-sql-phase2-readiness-parity.json`
- `tmp/python-go-durable-output-parity-repeated-gate.json`
- `tmp/go-sql-consumer-authority-guard.json`
- `tmp/python-go-sql-consumer-authority-guard-parity.json`
- `tmp/python-go-sql-consumer-authority-guard-fixture-parity.json`
- `tmp/python-go-sql-consumer-authority-dashboard-ab.json`
- `tmp/python-go-sql-consumer-authority-demotion-dry-run.json`
- `tmp/python-go-sql-consumer-authority-controlled-router.json`
- `tmp/python-go-sql-helper-demotion-readiness-gate.json`
- `tmp/python-go-sql-helper-demotion-queue.json`
- `tmp/python-go-sql-helper-contract-gate.json`
- `tmp/python-go-sql-helper-controlled-router-batch.json`
- `tmp/python-go-sql-helper-go-primary-history-gate.json`
- `tmp/python-go-sql-helper-default-route-promotion.json`
- `tmp/python-go-sql-helper-default-route-history-gate.json`
- `tmp/python-go-sql-helper-fallback-removal-readiness-gate.json`
- `tmp/python-go-sql-helper-retirement-gate.json`
- `tmp/go-sql-inprocess-driver-pilot-gate.json`
- `tmp/wf72-a2-fallback-fixture-parity-prep.json`
- `tmp/wf72-a2-consumer-authority-fallback-manifest.json`
- `tmp/wf72-a2-consumer-authority-fallback-values.json`
- `tmp/automation-stack-hardening-pass.json`

Purpose:
- independently challenge SMB/WF75 artifacts for customer-data, credential, outbound-message, customer-system writeback, public-launch, ROI/revenue, legal/compliance/security readiness, and owner-approval drift
- independently challenge finance/SQL proof for SQL-as-canon drift, proposal-apply authority, owner-approval inference, customer/external output authority, paper/live/account authority, SQLite integrity, and finance SQL row-count regressions
- independently audit Python SQL scripts for migration readiness, validation/boundary presence, durable finance approval/backup markers, and unsafe runtime authority language
- independently check core SQLite schemas for table/view, integrity, row-count, and forbidden-authority drift
- independently aggregate core SQLite proof into a Go-owned read-only SQL proof surface for Python-to-Go migration readiness
- independently lint SQL/canon JSON proof packet contracts for status, timestamp, validation-envelope, warning visibility, and forbidden-authority drift
- independently lint the SQL canon plus JSON proof bundle as one read-only advisory validator before any stronger cron or implementation-job integration
- independently bulk-validate indexed JSON proof artifacts for structure, freshness, hash continuity, blocked status residue, and forbidden authority flags
- independently check entry/stop band source lineage, hashes, generated timestamps, SQL reference rows, and mirror continuity without applying band maintenance
- independently lint PM control packets for stale lanes, blocked/needs-validation lanes, unsafe auto-execution posture, owner-gated work, and authority-language drift
- independently check finance answer packets for required sections, rollup continuity, stale packet residue, and forbidden authority flags
- independently probe cross-DB integrity and required/optional ticker-set referential drift across finance canon, finance state, WF84, and canon-cache SQLite surfaces
- independently gate workflow artifact/source freshness from artifact-index and source-freshness rows, preserving critical stale/manual dependency residue
- independently collect timing evidence for a fixed allowlist of compiled Go validators without allowing arbitrary shell or workflow execution
- independently lint the Execution Board structure while preserving Markdown/canon as owner-owned surfaces
- independently preflight paper-trading guard artifacts and kill-switch freshness without submitting, cancelling, replacing, or approving paper/live orders
- independently run fixed read-only SQL latency/probe queries beside the Python benchmark so selected SQL helpers can be ported with parity evidence
- independently inventory core SQLite tables, views, row counts, and expected-table presence as the first reusable Go SQL helper migration target
- independently compare Python and Go SQL helper proof artifacts before retiring or demoting selected Python SQL helper surfaces
- independently rank read-only Python SQL helpers for selective Go migration while preserving Python governance over canon/portfolio/apply/approval/orchestration/paper surfaces
- independently mirror and compare the SQL source-truth authority manifest as the first Batch 2 report-generator parity target
- independently mirror and compare the SQL source-truth parity validator as the first actual Markdown-to-SQL parity validator port
- independently mirror and compare the SQL 500-ticker expansion design gate as a compact report-generator parity target
- independently probe durable-output semantics for the finance universe validator and WF78 SQL Phase 2 readiness before any Python demotion
- independently compare top-level keys, status vocabulary, summary/validation fields, authority boundary fields, and row-count/readiness/universe-state semantics for durable-output helpers
- repeatedly run durable-output parity gates so the demotion queue depends on stable fingerprints, not one clean run
- independently mirror and compare the SQL consumer authority guard's fail-closed no-fallback surface before any Python demotion
- independently prove SQL consumer authority guard fallback-present clean-fixture parity as the first demotion-readiness gate
- independently compare the dashboard SQL consumer hook against Go across repeated live fail-closed, clean-fixture allow, missing fallback, and stale/unsafe source cycles before any controlled Python demotion
- independently dry-run Go-first/Python-fallback routing for `sql_consumer_authority_guard.py`, proving Go is selected only for the clean allow case while Python fallback remains blocked for unsafe cases
- independently prove the explicit controlled-router contract: default remains Python-owned, Go-first mode is available only as a controlled proof path, and Python fallback remains retained
- independently gate Python helper demotion readiness so durable-output helpers require semantic/shape parity and contract-first candidates have fixture contracts before replacement
- independently record the first controlled demotion and prepare the remaining demotion queue without retiring Python
- independently capture fixture contracts, expected output shapes, semantic/shape parity state, and downstream consumer stability for the remaining 11 demotion candidates
- independently record controlled Go-first/Python-fallback demotion for parity-green eligible helpers while keeping default routing unchanged and Python fallback retained
- independently prove repeated controlled Go-primary history stays stable across clean cycles before any default routing change
- independently record Randall-approved rollback from default Go-primary to Python owner/default after benchmark proof showed no material Go speed advantage for this path; Go remains validator-only
- independently collect repeated Python-owner/default route history with stable fingerprints, Go validator-only posture, fallback retained, and Python deletion denied
- keep fallback-removal readiness not applicable while Python is owner/default, with Python fallback active and separate exact approval required before any future removal attempt
- independently gate full Python helper retirement, requiring explicit future retirement approval/default-route migration/longer live history and denying Python deletion while fallback is retained
- independently compare CLI-backed Go SQL helpers against opt-in in-process SQLite driver runs for selected low-risk helpers, including JSON shape, status vocabulary, row counts, authority boundaries, error behavior, read-only enforcement, runtime/harness/PM stability, and compiled-binary readiness
- independently prove the live WF72 A2 fallback-backed read guard from current live/fixture/router proof so stale prep metadata does not misstate the approved 265-key boundary
- independently prove retail-grade answer routing Phases 1-4: route contract, source-open SQL gate, fallback-decay gate, and adversarial answer harness, all report-only and wired into the harness scorecard
- independently harden the automation stack after cron load reductions, skill-routing changes, and WF72 A2 proof changes by checking the JSON cron ledger, key skill ownership surfaces, and SQL consumer-authority readiness in one report-only gate
- support quick routing by validating existing proof routes first; routing wrappers may call these artifacts but must not create SQL-first, canon, customer, paper/live/account, or approval authority
- route only approved Go validator/proof helpers through compiled binaries under `tmp/go-binaries/` with `--driver inprocess`; Python remains the owner/default for workflow generators and SQL/cache helper ownership unless separately approved
- reuse shared Go toolkit packages for report/status writing and read-only SQLite access instead of adding one-off wrappers per validator
- provide a hard validator edge separate from the Python generators and TypeScript/Node cockpit

Boundary:
- read-only validation only; no artifact generation beyond the report, no SQL/canon/customer/portfolio mutation, no cron/runtime mutation, no external delivery, no paper/live/account action, and no owner approval inference

## Runtime performance scorecard

`runtime_performance_scorecard.py` is the unified local scorecard for SQL, Go, Python, and TypeScript/Node validation performance.

Full timed run:
```bash
python scripts/runtime_performance_scorecard.py --write --write-md --validate
```

Fast live smoke run:
```bash
python scripts/runtime_performance_scorecard.py --smoke --write --write-md --validate
```

Artifact-only refresh:
```bash
python scripts/runtime_performance_scorecard.py --artifact-only --write --validate
```

Current proof:
- `tmp/runtime-performance-scorecard.json`
- `tmp/runtime-performance-scorecard.md`
- `tmp/runtime-performance-scorecard-smoke.json`
- `tmp/runtime-performance-scorecard-smoke.md`
- `data/state-history/runtime-performance-scorecard.jsonl`

Purpose:
- run and time representative SQL latency, Go validator, Python control-plane, and Node cockpit validation checks
- provide a separate `smoke_live` path for frequent cheap runtime trust checks without overwriting the broad PM/cockpit scorecard artifact
- refresh the finance SQL Go lint and SQL latency proof as part of one scorecard pass
- keep append-only runtime history so future regressions can be detected instead of guessed

Boundary:
- report-only local proof; no finance canon/portfolio mutation, no customer/external delivery, no paper/live/account action, no config/auth/runtime mutation, and no owner approval inference

## WF74 model/run and finance correctness ledgers

Use these before refreshing `model_quality_scorecard.py` when measuring model performance, model-quality readiness, finance recommendation correctness, or finance response-quality warning coverage.

Run:
```bash
python scripts/wf74_model_quality_collection_cron_runner.py --write --write-md --validate --include-harness
python scripts/improvement_ledger.py --write --write-md --validate
python scripts/token_usage_ledger.py --write --write-md --validate
python scripts/wf74_cron_duplication_audit.py --write --validate
python scripts/otel_ops_control.py --write --write-db --multi-window --validate
python scripts/model_run_ledger.py --write --write-md --validate
python scripts/finance_recommendation_correctness_ledger.py --write --write-md --validate
python scripts/finance_response_quality_slice.py --write --write-md --validate
python scripts/model_quality_scorecard.py --write --write-md --validate
```

OAuth/ChatGPT subscription monitoring uses the same ledger chain and does not need an API key. Record only a sanitized capacity observation from a trusted usage/status surface, replacing the example numbers with the current remaining percentage and reset hours:

```powershell
python scripts\token_usage_ledger.py --write --write-md --validate --record-remaining-percent 58 --record-reset-hours 149 --record-source-label openclaw_session_status --record-window-label weekly
python scripts\token_budget_status.py --write --validate
python scripts\token_efficiency_scorecard.py --write --write-md --validate
```

The snapshot stores no account identity or raw status text. `state/openai-oauth-budget-policy.json` owns the advisory thresholds and optional owner-entered actual-bill field. Any non-null actual bill must be entered there with explicit owner provenance, a period label, and a UTC timestamp; it is never inferred from tokens or credits.

Capacity cadence is event-gated to avoid per-job churn:

- Record a sanitized observation after a verified weekly-window reset, or when an authoritative status surface supplies a materially changed value.
- The daily efficiency cron consumes the existing snapshot only; it never fabricates a capacity refresh from its own runtime.
- A candidate already classified as `repeated_high_burn_job` receives a six-hour advisory preflight. A stale or unavailable snapshot requests refresh, but cannot auto-skip work, throttle usage, change a cron/model route, or imply approval.
- A same-value authoritative recheck updates `checked_at_utc` without creating a second history row. A changed value creates one new auditable observation.
- Parent/child implementation closeout and token attribution never record or refresh OAuth capacity. They remain separate control paths.

There is intentionally no automated quota scraper. If a trusted structured status field is not available, leave capacity unknown/stale rather than parse UI text or store account details.

Pricing coverage is intentionally conservative. Historical total-only rows and rows with ambiguous or inconsistent input/cache/output counters remain visible for token totals but receive null API-equivalent and ChatGPT-credit estimates. Packet-level OAuth may be used to estimate credits only when the policy explicitly declares OAuth; an event's access mode remains `unknown` unless sanitized producer metadata proves `chatgpt` or `apikey`. Unknown speed is labeled as a standard-speed assumption, while explicit fast mode remains unpriced when no public rate exists. Rolling 5-hour and observed 7-day pace windows use only provider timestamps or explicit lane-completion approximations—never ledger ingestion time. Consequently, partial dollar or credit totals cover priced rows only and must not be extrapolated into an invoice or observed debit.

Current proof:
- `tmp/wf74-model-quality-collection-cron-runner.json`
- `tmp/wf74-cron-duplication-audit.json`
- `tmp/otel-ops-control.json`
- `tmp/otel-ops-window-summary.json`
- `tmp/otel/control-loop.json` (legacy audit bridge; canonical owner remains `tmp/otel-ops-control.json`)
- `tmp/model-run-ledger-current.json`
- `tmp/finance-recommendation-correctness-ledger-current.json`
- `tmp/finance-response-quality-slice.json`
- `tmp/model-quality-scorecard.json`
- `data/state-history/model-run-ledger.jsonl`
- `data/state-history/finance-recommendation-correctness-ledger.jsonl`
- `data/state-history/model-quality-scorecard.jsonl`
- `state/openai-oauth-budget-policy.json`
- `state/openai-oauth-capacity-current.json`
- `data/state-history/openai-oauth-capacity.jsonl`

Purpose:
- keep cron collection behind one stable runner instead of long inline prompt command chains
- audit that component collectors are not scheduled as duplicate cron jobs outside `Ops - OTEL Local Digest`
- keep `tmp/otel-ops-control.json` as the default 24h daily health packet while `tmp/otel-ops-window-summary.json` carries 1h, 6h, 24h, 7d, and 30d operational windows for follow-up review
- keep `tmp/otel/control-loop.json` as a compatibility bridge for older audit language that expected a main OTEL control-loop path; do not treat it as a second owner
- normalize runtime, OTEL, and Spark canary evidence into one model/run ledger with explicit model/session attribution coverage
- score current finance recommendation packets against observable ex-ante rule discipline: owner decision required, no approval inferred, no apply/execution authority, band context present, risk/concentration/catalyst gates present, and freshness blockers preserved
- score finance answer archetypes for WF84/WF85 routing, band/stop/freshness visibility, thin macro and 5DMA/20DMA warnings, and WF72 support-only boundaries
- let WF74 join performance, model attribution, ex-ante finance correctness, and WF55 later-outcome readiness without claiming model ranking from thin samples
- expose the current efficiency-loop state for coding validation, model quality, implementation queue, routing, and cron/OTEL operations through `model_quality_scorecard.py` instead of adding a separate peer control packet
- preserve standing interpretation rules: input drift is not automatically broken work, producers must refresh before consumers, OTEL is operational telemetry rather than coding-skill proof, freshness windows must be named before warning/blocker promotion, and stale source data should be labeled instead of hidden
- keep multi-window OTEL operational only: intraday is manual/post-change, 24h remains cron/PM control, 7d is trend review, and 30d is baseline review; none of those windows authorizes model ranking, coding-skill inference, finance correctness, capture-depth expansion, or config/runtime mutation
- carry open improvement recommendations across sessions through `data/state-history/improvement-ledger.jsonl` and the current packet `tmp/improvement-ledger-current.json`; use it before recommending OS/WF74 improvements and do not treat it as auto-apply authority
- rank token-heavy cron runs and implementation attribution gaps through `data/state-history/token-usage-ledger.jsonl` and `tmp/token-usage-ledger-current.json`; token counts are factual metadata, partial pricing totals cover priced rows only, `api_equivalent_cost_usd` is a comparison benchmark rather than an invoice, ChatGPT credits are estimated rather than observed debits, and `actual_billed_cost_usd` remains null unless the owner records it
- treat OAuth capacity thresholds as advisory only: missing/stale snapshots warn, fresh snapshots classify `normal`, `reduce_routine`, `pause_noncritical`, or `urgent_only`, and no packet may automatically alter schedules, model routes, runtime config, or credit purchases

Regression:
```bash
python scripts/test_otel_ops_control.py
python scripts/otel_ops_control.py --write --write-db --multi-window --validate
python scripts/test_full_intelligence_answer_parity.py
python scripts/test_finance_response_quality_slice.py
python scripts/test_model_quality_scorecard.py
```

Cron owner:
- `Ops - OTEL Local Digest`
- schedule: `40 7,15,21 * * *` America/Phoenix
- expected artifacts are registered in `cron_freshness_spine.py`

Boundary:
- review-only measurement; no model-ranking claim, no investment-correctness claim from telemetry, no WF55 later-outcome grade assignment, no canon/portfolio mutation, no capital deployment approval, no paper/live/account action, no runtime/config mutation, and no owner approval inference

## Generic Intelligence SaaS pivot

### `generic_intelligence_saas_pivot.py`

Status: WF75 generic service-run and SMB Workflow Clarity / Marketing Ops Automation control packet. SMB was resumed by Randall on 2026-06-13 as a P1 monetization lane; verify current status with `python scripts\workflow_router.py WF79-SMB --answer all` before advancing it.

Run:
```bash
python scripts/generic_intelligence_saas_pivot.py --write --write-db --validate
```

Writes:
- `tmp/generic-service-run-contract.json`
- `tmp/wf75-smb-workflow-scenario-library.json`
- `tmp/wf75-smb-pivot-pm-decision-packet.json`
- `tmp/wf75-smb-customer-preview.json/.md`
- `tmp/wf75-smb-customer-preview-validation.json`
- `tmp/wf75-smb-pilot-decision-packet.json`
- `tmp/wf75-smb-automation-blueprints.json`
- `tmp/wf75-smb-automation-blueprints-validation.json`
- `tmp/wf75-smb-service-state-current.json`
- `tmp/wf75-smb-service-state-validation.json`
- `tmp/wf75-smb-boundary-lint.json` after running the Go boundary validator
- `tmp/generic-service-state.sqlite`

Purpose:
- lock the Veritas Intelligence Operations Engine posture
- keep Retail Finance as P0 continuity while preserving SMB Workflow Clarity / Lead Rescue artifacts for explicit owner resume
- define the generic service-run contract, first SMB scenario library, dry-run automation blueprints, Lead Rescue service-state slice, SQL-control-plane scaffold, TypeScript/Node cockpit direction, and PM automation path
- embed useful ClawHub `queue` / `agent-task-queue`, product-manager, agent/skill-evaluation, and workflow-automation patterns into Veritas-owned review-only artifacts without installing generic skills

Boundary:
- derived SQL/control-plane proof only; JSON remains source proof
- no real customer identity/data, customer-data retention, CRM/phone/ad/email/payment/POS/payroll/automation-platform credentials, outbound messaging/automation, customer-system implementation/writeback, external delivery, public launch, guaranteed ROI/revenue claim, legal/compliance/security readiness claim, finance-canon mutation, paper/live/account action, or owner approval inference

## WF75 Academy / Training Desk

### `wf75_training_desk.py`

Status: live Randall training and fake-scenario practice surface for SMB Workflow Clarity.

Run:
```bash
python scripts/wf75_training_desk.py --write --write-md --write-training-assets --validate
```

Writes:
- `tmp/wf75-training-desk-current.json/.md`
- `training/wf75-academy/wf75-academy-current.json/.md`
- `training/wf75-academy/wf75-academy-handout.html`
- `training/wf75-academy/wf75-academy-handout.pdf`
- `training/wf75-academy/wf75-academy-activity-deck.pptx`
- `training/wf75-academy/wf75-academy-simulation-deck.html`
- `training/wf75-academy/wf75-academy-manifest.json`

Purpose:
- keep Academy material in a durable `training/` review folder instead of only `tmp/`
- generate a PDF handout, PowerPoint activity deck, and browser-based simulation deck from the same source packet
- support adult-learning sessions with explain-back prompts, fake-scenario practice, activities, and QA stop-line review
- provide a future app substrate through the HTML simulation deck and current JSON contract

Boundary:
- internal readiness and training only
- no real customer data, customer outreach, external delivery, credential access, customer-system implementation, public launch, spending/subscriptions, guaranteed ROI/revenue claim, legal/compliance/security readiness claim, or certification claim

### `interactive_training_builder.py`

Status: reusable local-first builder for HTML interactive training modules.

Run:
```bash
python scripts/interactive_training_builder.py --write --validate
python scripts/test_interactive_training_builder.py
python scripts/interactive_training_qa_validator.py --write --validate
python scripts/interactive_training_scorm_smoke_validator.py --write --validate
python scripts/interactive_training_xapi_ledger.py --write --validate
python scripts/interactive_training_catalog_builder.py --write --validate
```

Writes:
- `schemas/interactive_training_module.schema.json`
- `training/interactive-training-builder/sample-wf75-boundary-module.json`
- `training/interactive-training-builder/sample-wf75-boundary-module.html`
- `training/interactive-training-builder/sample-wf75-boundary-module.xapi.json`
- `training/interactive-training-builder/sample-wf75-boundary-module-scorm.zip`
- `training/interactive-training-builder/wf75-hvac-outreach-module.json`
- `training/interactive-training-builder/wf75-hvac-outreach-module.html`
- `training/interactive-training-builder/wf75-hvac-outreach-module.xapi.json`
- `training/interactive-training-builder/wf75-hvac-outreach-module-scorm.zip`
- `training/interactive-training-builder/sec-evidence-review-module.json`
- `training/interactive-training-builder/sec-evidence-review-module.html`
- `training/interactive-training-builder/sec-evidence-review-module.xapi.json`
- `training/interactive-training-builder/sec-evidence-review-module-scorm.zip`
- `training/interactive-training-builder/otel-proof-validator-module.json`
- `training/interactive-training-builder/otel-proof-validator-module.html`
- `training/interactive-training-builder/otel-proof-validator-module.xapi.json`
- `training/interactive-training-builder/otel-proof-validator-module-scorm.zip`
- `training/interactive-training-builder/authoring-checklist.md`
- `training/interactive-training-builder/component-library.json/.md`
- `training/interactive-training-builder/qa-screenshots/*.png`
- `training/interactive-training-builder/scorm-smoke-screenshots/*.png`
- `training/interactive-training-builder/standards-upgrade-evaluation.json/.md`
- `training/interactive-training-builder/*-manifest.json`
- `training/interactive-training-builder/catalog.json`
- `training/index.html`
- `tmp/interactive-training-builder-proof.json`
- `tmp/interactive-training-qa-validation.json`
- `tmp/interactive-training-scorm-smoke-validation.json`
- `tmp/interactive-training-xapi-ledger-proof.json`
- `tmp/interactive-training-catalog-proof.json`

Purpose:
- standardize interactive training modules with a schema-backed source contract
- generate a static HTML runtime with local scoring, progress, keyboard navigation, aria-live updates, and xAPI-style event export
- create SCORM 1.2 packages with LMS API bridge calls while preserving local-browser fallback
- smoke-test SCORM zips and packaged runtimes locally with a mock LMS API before any external LMS import is considered
- convert existing WF75 HVAC outreach simulations into the reusable module/runtime shape
- convert SEC evidence review into the same reusable module/runtime shape
- convert OTEL proof/validator review into the same reusable module/runtime shape
- run local Playwright + axe browser QA through installed Edge with desktop/mobile screenshots
- provide a local catalog/launcher front door for modules, SCORM zips, manifests, screenshots, local progress, and proof links
- provide generated authoring checklist and component-library files for repeatable module creation
- optionally capture xAPI-style events through a loopback-only collector when explicitly started
- preserve a standards evaluation path for H5P, Adapt, xAPI, SCORM, and cmi5 without configuring external services

Boundary:
- local internal training only
- no external LMS/LRS setup, hosting, account mutation, learner-data transport, customer data, outreach, credentials, production access, public delivery, paid tooling, or owner approval inference

Optional local xAPI ledger:
```powershell
python scripts\interactive_training_xapi_ledger.py --serve
```

Open `training\index.html`, enable ledger capture, then launch a module. The collector binds to loopback only and writes local JSONL events; if it is not running, modules still use browser localStorage and downloadable event export.

## Boundary note

- `scripts/` root remains the stable CLI surface documented across the workspace.
- Selected operator-only implementations now live under `scripts/operators/`.
- Root entrypoints such as `python scripts/apply_band_update.py` are intentionally preserved as thin compatibility wrappers so existing docs and operator habits do not break.
- Do not assume everything in `scripts/` root is chain-active; use `run_finance_refresh_chain.py` as the authoritative chain map.

## Artifact taxonomy

Use this taxonomy when deciding whether a generated file should stay active, become a report input, move to durable notes, or be archived.

| Class | Purpose | Examples | Authority |
|---|---|---|---|
| Canonical machine input | Current script-readable evidence used by downstream reports | `tmp/portfolio-config.json`, `tmp/technical-refresh.json`, `tmp/deployment-check.json`, `tmp/trigger-sheet.json`, `tmp/regime-scores.json`, `tmp/market-state.json` | Evidence input only; does not outrank canonical notes |
| Operator portfolio view | Clean human/machine communication layer for portfolio status | `tmp/full-portfolio-view.json`, `.md`, `.html`, `tmp/full-portfolio-view-validation.json` | Review-only report; no canon, portfolio, approval, execution, or trade authority |
| Decision/report surface | Ranked review objects, summaries, and guardrails for Veritas/Randall review | `tmp/daily-executive-brief.json`, `tmp/deployment-readiness-surface.json`, `tmp/daily-review-objects-*.json`, `tmp/market-intelligence-events-*.json`, guardrail reports | Review/proposal only unless a specific bounded note-sync path is approved |
| UI payload | Dashboard/web rendering support | `tmp/dashboard-data.json`, `tmp/dashboard-last.json`, `tmp/veritas-command-center.html` | Presentation only; not portfolio truth |
| Run/proof artifact | Chain evidence, validation, dry-runs, workflow proof, and current-window indexes | `tmp/run-chain-*.json`, `tmp/run-summary-*.json`, `tmp/current-window-artifacts.json`, `optional Markdown digest beside `tmp/current-window-artifacts.json``, `tmp/wf*.json`, `tmp/wf*.md` | Audit/navigation evidence; archive by retention/reference policy |
| Scratch/research sidecar | One-off research, candidate packets, manual probes, temporary helpers | `tmp/materials-*`, `tmp/bkng-*`, `tmp/promotion-candidate-*`, `tmp/*.py` probes | Promote to `04. Research/` or `08. Audits/` only when accepted as durable; otherwise archive/expire after review |

## Deployment-state contract

`board_state_contract.py` owns shared deployment-state normalization. Use `deployment_contract(record)` for canonical status (`deployment_status`, `status_reason`, `display_label`, `raw_context`, `authority`). Use `legacy_state(record, field)` only when a reader still needs legacy vocabulary for scoring, history, or compatibility output; it reads `deployment_contract.raw_context` before falling back to removed top-level aliases.

`deployment_contract_legacy_read_audit.py` is the Slice 5/6 guard for direct legacy state reads. Run:

```powershell
python scripts\deployment_contract_legacy_read_audit.py --write --fail-on-unclassified
```

For finish/commit prep, run the repeatable migration proof bundle:

```powershell
python scripts\deployment_contract_migration_validation_bundle.py --write --full
```

Current contract: generated `tmp/deployment-readiness-surface.json` records no longer emit duplicate top-level `surface_state`, `base_surface_state`, `workflow_state`, `machine_state`, or `action_state`; those values remain preserved under each record's `deployment_contract.raw_context`. The audit must stay at 0 warning hits before extending this removal pattern to other generated artifacts. This contract is review-only and grants no canon/portfolio/SQL-canon, capital deployment, paper/live/account, or owner-approval authority.

## Presentation artifact flattening

Presentation/retrieval flattening is owned by `06. Playbooks/Project Continuity/Presentation Artifact Flattening and Retrieval Routing.md`. Current additive helpers:

```powershell
python scripts\presentation_artifact_inventory.py --write
python scripts\dashboard_presentation_dto_design.py --write
python scripts\dashboard_presentation_dto.py --write --validate
python scripts\dashboard_presentation_compatibility_proof.py --write --validate
python scripts\dashboard_presentation_adapter.py --write --validate
python scripts\dashboard_presentation_view_model.py --write --validate
python scripts\dashboard_presentation_renderer.py --write --validate
python scripts\dashboard_presentation_acceptance.py --write --validate
python scripts\dashboard_thin_payload_preview.py --write --validate
python scripts\dashboard_v2_reader_migration.py --write --validate
python scripts\dashboard_compact_shell.py --write --validate
python scripts\dashboard_compact_shell_acceptance.py --write --validate
python scripts\dashboard_compatibility_payload.py --write --validate
python scripts\dashboard_shrink_readiness_score.py --write --validate
python scripts\presentation_render_default_compatibility.py --write --validate
python scripts\wf78_packet_summary_consolidation.py --write --validate
python scripts\presentation_retrieval_route_map.py --write --validate
python scripts\presentation_retrieval_enforcement.py --write --validate
```

These write review-only artifacts under `tmp/` and do not replace `tmp/dashboard-data.json`. The compatibility proof currently allows `tmp/dashboard-presentation-dto.json` as a compact retrieval/presentation route, but not as a drop-in replacement for the standalone Command Center HTML because the current `scripts/dashboard-js/*.js` modules read the full `DATA` object directly. The adapter artifact promotes compact DTO retrieval while keeping legacy `DATA` passthrough for current UI compatibility. The view-model/renderer/acceptance trio is the compact parallel UI proof path; `generate_dashboard.py` refreshes these compact artifacts alongside the stable legacy Command Center. `dashboard_thin_payload_preview.py` writes a thin future payload preview that references, but does not embed or replace, the legacy dashboard payload. `dashboard_v2_reader_migration.py` now proves all 8 compact panels are migrated to the compact reader contract. `dashboard_compact_shell.py` renders the usable compact shell at `tmp/veritas-command-center-compact.html`, and `dashboard_compact_shell_acceptance.py` validates it. `dashboard_compatibility_payload.py` proves route coverage for all current `DATA` sections while still blocking drop-in replacement. `dashboard_shrink_readiness_score.py` makes that replacement blocker explicit and measurable. `presentation_render_default_compatibility.py` now proves full-portfolio/WF75 Markdown and HTML sidecars are safe as explicit-only renders: 4 safe default-disable paths, 0 unsafe/unproven paths. `wf78_packet_summary_consolidation.py` previews shared WF78 packet summary/header consolidation and writes `tmp/wf78-packet-shared-header.json`; the Tier B final-promotion packet family now carries an additive `shared_header_ref` while preserving embedded fields and routing behavior. `presentation_retrieval_route_map.py` records compact/JSON-first retrieval routes with proof refs behind them, and `presentation_retrieval_enforcement.py` validates that route map. `full_portfolio_view.py` and `wf75_operator_console.py` are JSON-first by default; use `--write-html` and `--write-md` only for explicit optional sidecar renders. Do not delete proof, archive sidecars, remove source fields, or replace existing presentation payloads without consumer-by-consumer compatibility proof and a separate go.

Durable derived registries live under `data/` only when they are reusable inputs rather than generated proof. `data/finance/` is the current finance registry surface for WF77/WF78 universe metadata and must keep its own README authority boundary.

### `concurrent_lane_manager.py`

Status: MVP helper-lane lease and anti-collision register.

Builds and validates `tmp/concurrent-lane-register.json`, a JSON lease register for concurrent workflow/helper lanes. It derives read-first and acceptance defaults from `tmp/workflow-routing-index.json`, records planned/leased/running/complete lanes, tags running lanes with `started_at_utc`, tags terminal lanes with `ended_at_utc` / `completed_at_utc`, and can attach OpenClaw `session_key`, `session_id`, `session_label`, and `task_name` metadata after a helper is spawned. It fails closed if active lanes collide on write surfaces, write forbidden paths, have stale leases, or complete without proof. It does not spawn helpers, schedule work, or grant authority.

Active-lane admission is separate from the full historical-ledger audit. Any `--write` action that creates or reactivates an active lane is checked in memory under a short exclusive admission lock before its register row or imported usage receipt can be written. `leased` and `running` transitions receive a fresh lease expiry and admission rejects missing or expired lease expiry; `planned` remains lease-free. An unsafe candidate returns a critical `lease_admission` result and leaves the register unchanged. Use `--active-lease-safety` to emit/exit on that current active-lane gate explicitly. `--validate` remains the full ledger audit: it intentionally stays nonzero for terminal route/proof debt, which must remain visible and must not be mistaken for a current collision or a cleared ledger.

Run:
```bash
python scripts/concurrent_lane_manager.py --status --write --validate
python scripts/concurrent_lane_manager.py --plan WF78 --workstream event-rerouting --owner main --write --active-lease-safety
python scripts/concurrent_lane_manager.py --lease WF78 --workstream event-rerouting --owner helper-wf78-a --allowed-write scripts\wf78_event_triggered_rerouting.py --allowed-write tmp\wf78-event-triggered-rerouting.json --write --active-lease-safety
python scripts/concurrent_lane_manager.py --set-status WF78 --workstream event-rerouting --status-value running --session-key agent:main:example --session-id <session-id> --session-label helper-wf78-a --task-name wf78_event_rerouting --write --active-lease-safety
python scripts/concurrent_lane_manager.py --complete WF78 --workstream event-rerouting --proof tmp\wf78-event-triggered-rerouting.json --write --validate
```

Writes:
- `tmp/concurrent-lane-register.json`

Boundary:
- coordination/lease register only
- no autonomous spawning, scheduler, canon/portfolio/ticker-card/SQL-canon mutation, config/auth/runtime mutation, destructive cleanup, capital deployment, trade execution, paper/live/brokerage/account action, money movement, customer/public output, or owner approval inference.

### `parallel_lane_recommender.py`

Builds `tmp/parallel-lane-recommendation.json`, a fast recommendation packet for the next safe isolated helper lane. It reads the workflow routing index, concurrent lane register, PM implementation queue, WF78 event-rerouting queue, and automation hardening proof. It ranks narrow one-output lanes, rejects write collisions/forbidden writes, and emits:

- `lease_command` for `concurrent_lane_manager.py`
- `spawn_args` for the OpenClaw `sessions_spawn` tool
- a complete command template for the proof artifact
- ranked candidate context

Run:
```powershell
python scripts\parallel_lane_recommender.py --write --validate
python scripts\parallel_lane_recommender.py --workflow WF78 --out tmp\parallel-lane-recommendation-wf78.json --write --validate
python scripts\parallel_lane_recommender.py --workflow WF72 --out tmp\parallel-lane-recommendation-wf72.json --write --validate
```

Current default behavior:
- recommends the lowest-collision eligible lane first, including PM-derived implementation slices when the PM job capability flags allow helper-lane work
- prefers one distinct output under `tmp/parallel-lanes/`; PM-derived candidates may include explicit target files from the PM job contract plus a dedicated proof artifact under `tmp/parallel-lanes/`
- does not call `sessions_spawn` itself
- requires main session to lease, spawn, verify the proof artifact, and complete the lease

Boundary:
- recommendation/coordination only
- no autonomous spawning, cron mutation, canon/portfolio/ticker-card/SQL-canon mutation, config/auth/runtime mutation, destructive cleanup, capital deployment, trade execution, paper/live/brokerage/account action, customer/public output, money movement, or owner approval inference

### `main_session_action_executor.py`

Status: active main-session PM/cron pickup layer

Runs the thin automatic pickup step above cron control, greenkeeper, PM control, PM implementation queue, and the parallel lane recommender.

```bash
python scripts/main_session_action_executor.py --context main_session --write --validate
python scripts/main_session_action_executor.py --context main_session --refresh-frontdoors --execute-safe --write --validate --append-ledger
```

It can refresh front-door control packets, select one PM job whose `automation_capabilities` allow the current context, and either run a guarded review-only PM proof through `pm_execution_loop.py --execute --job <job_id> --write --validate` or prepare a PM-derived helper-lane recommendation. Heartbeat must not invoke this executor directly; use only `heartbeat_priority_handoff.py`, whose isolated receipt route is no-execute and no-spawn. The executor appends `state/main-session-action-executor-ledger.jsonl` when `--append-ledger` is set.

Current proof:
- `tmp/main-session-action-executor.json`
- `state/main-session-action-executor-ledger.jsonl`

Boundary:
- review-only PM proof execution and helper-lane preparation only
- no code patches, helper spawning, cron/config/auth/runtime mutation, canon/portfolio/ticker-card/SQL-canon mutation, capital deployment, trade execution, paper/live/brokerage/account action, customer/public output, money movement, or owner approval inference

### `workflow_routing_index.py`

Status: WF73 derived workflow route map and SQL route-control lookup.

Builds `tmp/workflow-routing-index.json`, validates it, optionally rebuilds `tmp/workflow-routing-index.sqlite`, and exposes canned route-control queries. PM cockpit consumes the SQL route views through `/api/workflows/routes` and the Workflows tab; `sql_coverage_guard.py` refreshes the route JSON/validation/SQLite artifacts through the existing review-only cron chain. Active Workflows and exact continuity notes remain authority; JSON is proof, SQLite is a derived/rebuildable lookup layer.

Run:
```bash
python scripts/workflow_routing_index.py --write --write-db --validate
python scripts/workflow_routing_index.py --sql-route WF78
python scripts/workflow_routing_index.py --sql-freshness
python scripts/workflow_routing_index.py --sql-next-actions
python scripts/workflow_routing_index.py --sql-helper-safe
python scripts/workflow_routing_index.py --sql-owner-gated
```

Writes:
- `tmp/workflow-routing-index.json`
- `tmp/workflow-routing-index-validation.json`
- `tmp/workflow-routing-index.sqlite`

Boundary:
- derived/rebuildable route-control lookup only
- no workflow authority over Active Workflows or continuity notes
- no canon/portfolio/ticker-card/SQL-canon mutation, customer/public output, cron/config/runtime mutation, paper/live/brokerage/account action, capital deployment, trade execution, money movement, or owner approval inference

Default portfolio communication source:
- use `tmp/full-portfolio-view.json/.md/.html` for “show me the portfolio,” “what matters today,” and portfolio-status summaries.
- treat `tmp/dashboard-data.json` as UI backend only.
- cron may generate reports, guardrails, proposals, archive suggestions, scoped eligible entry-band maintenance through `auto_apply_entry_band_maintenance.py --apply`, and the Sunday weekly minimum reference-band note refresh through `reference_band_note_sync.py --apply`; cron must not apply canonical portfolio/intelligence edits outside those approved band-maintenance/reference-visibility paths or perform cleanup moves.
- `auto_apply_entry_band_maintenance.py --dry-run` preflights the same current Execution Board table/parser-section update path as `--apply`; blocked status means the board cannot be patched safely.
- `auto_apply_entry_band_maintenance.py --apply` is limited to `canonical_apply_eligible=true` routine `entry_band` proposals, updates `tmp/portfolio-config.json` plus `03. Portfolio/Execution Board.md`, writes `tmp/auto-band-apply.json`, then serially refreshes the WF72 entry/stop SQL reference cache, `finance-intelligence-state.sqlite`, WF84, WF85 decision cards, changed-ticker WF85 full answers/parity, and `tmp/cache-dependency-manifest.json`; if the post-apply cache/proof refresh fails, the run exits `blocked_needs_sql_reference_refresh`. It grants no capital, sizing, sleeve, cash, risk-rule, paper/live order, brokerage/account, or owner-approval authority.

## Retail investor SaaS fixture and validator

### `retail_saas_fixture_demo.py`, `retail_saas_customer_output_validator.py`, and `retail_saas_html_report.py`

Status: WF75 Retail Investor Finance Intelligence SaaS anonymous-scenario demo/export and customer-output safety validator.

Run:
```bash
python scripts/retail_saas_fixture_demo.py --write-seeded-bad
python scripts/retail_saas_customer_output_validator.py tmp\retail-saas-fixture-demo.json --rendered-text tmp\retail-saas-fixture-demo.md --out tmp\retail-saas-fixture-demo-validation.rerun.json
python scripts/retail_saas_customer_output_validator.py tmp\retail-saas-fixture-demo.customer-export.json --out tmp\retail-saas-fixture-demo.customer-export-validation.json
python scripts/retail_saas_html_report.py
```

Writes:
- `tmp/retail-saas-fixture-demo.json` internal fixture/proof wrapper
- `tmp/retail-saas-fixture-demo.customer-export.json` customer-only JSON export
- `tmp/retail-saas-fixture-demo.md` rendered customer brief
- `tmp/retail-saas-fixture-demo.html` local fixture-only HTML report prototype
- `tmp/retail-saas-fixture-demo.html-validation.json`
- `tmp/retail-saas-fixture-demo-validation*.json`
- seeded-bad JSON/Markdown validation artifacts under `tmp/retail-saas-fixture-demo.seeded-bad*`

Purpose:
- prove an anonymous watchlist/ticker service request can be generated from existing finance-engine cards and real public evidence where available without exposing internal machinery
- enforce no internal path/workflow/SQL/proof leaks, no credential-shaped text, no advice/execution/performance overreach, visible stale/missing evidence, customer-safe source categories, and rendered Markdown checks
- keep the export anonymous-scenario/internal-only while the active WF75 route builds infrastructure first: service-state storage, SQLite WAL control plane, operator queue/status, renderer/export pipeline, QA regression, macro-event calendar proof, scenario-template library, and artifact-only PM handoff. Fake-person customer personas are deprecated. Privacy/licensing/counsel decision-packet work is not the current sprint route.

Boundary:
- no public/customer launch, real customer/prospect data, external delivery, brokerage/account connection, order controls, paper/live execution, personalized regulated advice, guaranteed-return/win-rate/probability/expected-return claims, legal/compliance-readiness claims, canon/portfolio mutation, owner approval, or trading authority
- no customer identity, customer portfolio, suitability/risk-profile, income/net-worth, tax/retirement, brokerage, account, or credential data
- validator success means only the fixture/export passed local safety checks; it does not grant launch, advice, customer-data, external-delivery, brokerage, execution, or compliance authority

## Governance validators

### `boot_surface_size_guard.py`, `workflow_hygiene_check.py`, `tool_bloat_reduction_guard.py`, `automation_health_dashboard.py`, `major_closeout_delta.py`, `workflow_automation_autonomy_review.py`, `operator_packet.py`, `heartbeat_continuation_candidates.py`, `pm_program_state.py`, `pm_main_session_handoff.py`, `wf75_closeout_refresh.py`, `wf75_service_led_saas_readiness_plan.py`, `wf75_service_state.py`, `wf75_service_state_sqlite.py`, `wf75_operator_console.py`, `wf75_deliverable_packager.py`, `veritas_harness_scorecard.py`, `veritas_harness_failure_classifier.py`, `veritas_pm_department_validate.py`, `wf75_pm_weekly_update.py`, `wf75_cron_automation_authority_plan.py`, `cron_operator_ledger.py`, `morning_control_digest.py`, `post_close_control_digest.py`, `cron_notes_flattening_plan.py`, `cron_execution_posture_patch.py`, `cron_patch_manager.py`, `cron_contract_validator.py`, `worktree_checkpoint_planner.py`, `validator_bundle_router.py`, `artifact_staleness_explainer.py`, `lane_collision_preflight.py`, `authority_matrix.py`, `sql_staging_import_gate.py`, `bounded_canon_mutation_approval_packet.py`, `audit_event_table_design.py`, `sql_retail_grade_validation_bundle.py`, `sql_retail_expansion_phase_gate.py`, `sql_500_ticker_expansion_design_gate.py`, `wf78_100_ticker_candidate_scope_packet.py`, `wf78_100_ticker_import_gate.py`, `sql_pre_phase5_hardening_gate.py`, `sql_hardening_flattening_plan.py`, `sql_source_truth_authority_manifest.py`, `sql_source_truth_parity_validator.py`, `sql_source_truth_drift_validator.py`, `sql_source_truth_ab_consumer_probe.py`, `sql_source_truth_promotion_readiness_gate.py`, `sql_source_truth_field_family_decision_packet.py`, `sql_source_truth_apply_scaffold.py`, `sql_source_truth_exact_apply_packet.py`, `sql_first_consumer_wiring_preflight.py`, and `tmp_helper_residue_cleanup.py`

Status: WF72 report-only runtime-efficiency, telemetry, and closeout-delta helpers.

Run:
```bash
python scripts/boot_surface_size_guard.py --write --validate
python scripts/workflow_hygiene_check.py --write --validate
python scripts/tool_bloat_reduction_guard.py --write --validate
python scripts/tool_bloat_reduction_guard.py --write --validate --baseline tmp\tool-bloat-reduction-baseline-prepass-2026-05-25.json --target-reduction-pct 25
python scripts/automation_health_dashboard.py --write --validate
python scripts/major_closeout_delta.py --write --validate
python scripts/workflow_automation_autonomy_review.py --write --validate
python scripts/operator_packet.py --workflow all --write --validate
python scripts/pm_control_packet.py --write --write-db --validate
python scripts/wf75_closeout_refresh.py --write --validate
python scripts/wf75_service_led_saas_readiness_plan.py --write --validate
python scripts/wf75_service_state.py --scenario-id anon-risk-freshness-edge-cases-v1 --write --validate
python scripts/wf75_service_state_sqlite.py --write --validate
python scripts/wf75_operator_console.py --write --validate
python scripts/veritas_harness_scorecard.py --fast --write --validate
python scripts/veritas_harness_scorecard.py --go --write --validate
python scripts/veritas_harness_scorecard.py --full --write --validate
python scripts/veritas_harness_failure_classifier.py --text "rg wildcard failed with Windows path syntax" --write
python scripts/veritas_pm_department_validate.py --write
python scripts/wf75_pm_weekly_update.py --write --validate
python scripts/wf75_cron_automation_authority_plan.py --write --validate
python scripts/cron_operator_ledger.py --write --write-md --validate
python scripts/cron_freshness_spine.py --write --validate
python scripts/morning_control_digest.py --write --write-md --validate
python scripts/post_close_control_digest.py --write --write-md --validate
python scripts/cron_notes_flattening_plan.py --write --write-md --validate
python scripts/cron_execution_posture_patch.py --validate
python scripts/cron_patch_manager.py --name "Ops - OTEL Local Digest" --timeout-seconds 901 --write --validate
python scripts/cron_contract_validator.py --write --validate
python scripts/worktree_checkpoint_planner.py --write --validate
python scripts/validator_bundle_router.py --write --validate
python scripts/artifact_staleness_explainer.py --write --validate
python scripts/lane_collision_preflight.py --write-path scripts\example.py --write --validate
python scripts/authority_matrix.py --write --validate
python scripts/sql_staging_import_gate.py --write --validate
python scripts/bounded_canon_mutation_approval_packet.py --write --validate
python scripts/audit_event_table_design.py --write --validate
```

SQL retail-grade, SQL source-of-truth, and WF78 expansion commands below are on-demand/change-triggered only. Do not place them in routine morning, post-close, post-earnings, or Sunday finance windows just to re-prove the known `retail SQL-first blocked / 0 effective rows` state.

```bash
python scripts/retail_truth_routing_contract.py --write --validate
python scripts/retail_answer_harness.py --write --validate
python scripts/retail_automation_control_plane.py --write --validate
python scripts/sql_retail_grade_validation_bundle.py --write --validate
python scripts/sql_retail_expansion_phase_gate.py --write --validate
python scripts/sql_500_ticker_expansion_design_gate.py --write --validate
python scripts/wf78_enrichment_orchestrator.py --batch pilot-10 --write --validate
python scripts/sql_pre_phase5_hardening_gate.py --write --validate --run-gates
python scripts/sql_hardening_flattening_plan.py --write --validate
python scripts/sql_source_truth_authority_manifest.py --write --validate
python scripts/sql_source_truth_parity_validator.py --write --validate
python scripts/sql_source_truth_drift_validator.py --write --validate
python scripts/sql_source_truth_ab_consumer_probe.py --write --validate
python scripts/sql_source_truth_promotion_readiness_gate.py --write --validate --run-gates
python scripts/sql_source_truth_field_family_decision_packet.py --write --validate
python scripts/sql_source_truth_apply_scaffold.py --write --validate --run-gates
python scripts/sql_source_truth_exact_apply_packet.py --write --validate
python scripts/sql_first_consumer_wiring_preflight.py --write --validate
python scripts/wf78_100_ticker_candidate_scope_packet.py --write --validate
python scripts/tmp_helper_residue_cleanup.py --write --validate
```

For noisy local commands, route full stdout/stderr to artifacts and print only compact status/count/path:
```bash
python scripts/compact_exec.py --label scorecard-latest-main -- python scripts\openclaw_cache_efficiency_scorecard.py --write --write-redacted-tool-telemetry --latest-main-session
python scripts/test_compact_exec.py
```

Writes:
- `tmp/boot-surface-size-guard.json`
- `tmp/workflow-hygiene-check.json`
- `tmp/tool-bloat-reduction-guard.json/.md`
- optional comparison baseline such as `tmp/tool-bloat-reduction-baseline-prepass-2026-05-25.json`
- compact command logs under `tmp/compact-exec-logs/*.json`, `*.stdout.txt`, and `*.stderr.txt`
- `tmp/automation-health-dashboard.json/.md`
- `tmp/automation-health-dashboard-trends.json/.md`
- `data/state-history/automation-health-dashboard-history.jsonl`
- `tmp/major-closeout-telemetry-delta.json/.md`
- `tmp/workflow-automation-autonomy-review.json`
- `tmp/operator-packets/*.json`
- `tmp/pm-control-packet.json`
- `tmp/pm-control-packet.sqlite`
- `tmp/pm-sidecar-retirement-guard.json`
- `tmp/wf75-closeout-refresh.json`
- `tmp/wf75-service-led-saas-readiness-plan.json`
- `tmp/wf75-service-state-current.json`
- `tmp/wf75-service-runs/wf75-anon-watchlist-ai-infrastructure-v1.json`
- `tmp/wf75-operator-queue.json`
- `tmp/wf75-automation-movement.json`
- `tmp/veritas-harness-scorecard.json/.md`
- `tmp/veritas-harness-failure-classification.json`
- `tmp/veritas-pm-department-validation.json`
- `tmp/wf75-pm-weekly-update.json/.md`
- `tmp/wf75-cron-automation-authority-plan.json`
- optional Markdown digest when `--write-md` is supplied
- `tmp/cron-operator-ledger.json/.md`
- `tmp/cron-notes-flattening-plan.json/.md`
- `tmp/cron-execution-posture-patch.json`
- `tmp/authority-matrix.json`
- `tmp/authority-matrix-validation.json`
- `tmp/sql-staging-import-gate.json`
- `tmp/sql-staging-import-gate-validation.json`
- `tmp/bounded-canon-mutation-approval-packet.json`
- `tmp/bounded-canon-mutation-approval-packet-validation.json`
- `tmp/audit-event-table-design.json`
- `tmp/audit-event-table-design-validation.json`
- `tmp/sql-retail-grade-validation-bundle.json`
- `tmp/sql-retail-expansion-phases-1-4-gate.json`
- `tmp/wf72-entry-stop-helper-42-no-drift-review.json`
- `tmp/sql-retail-blocker-classification.json`
- `tmp/sql-500-ticker-expansion-design-gate.json`
- `tmp/sql-pre-phase5-hardening-gate.json`
- `tmp/sql-hardening-flattening-phased-plan-2026-05-29.json`
- `tmp/sql-source-truth-exact-apply-packet.json`
- `tmp/sql-first-consumer-wiring-preflight.json`
- `tmp/wf78-100-ticker-candidate-scope-packet.json`
- pre-SQL audit artifacts such as `tmp/scripts-hardening-audit-pre-sql-2026-05-29.json`, `tmp/tmp-hardening-audit-pre-sql-2026-05-29.json`, and `tmp/sql-pre-phase5-hardening-audit-2026-05-29.json`

Purpose:
- use `boot_surface_size_guard.py` after boot/control-surface edits to catch core Markdown files before they approach bootstrap truncation again
- use `workflow_hygiene_check.py` after queue/control-surface edits to verify required P0/P1 lanes, WF68 advisor-validation visibility, WF72/WF73 next-action hygiene, stop-line terms, WF50 non-active status, and boot-guard hard-failure proof
- use `tool_bloat_reduction_guard.py` after long runs to identify medium/high/truncated tool-output pressure without exporting raw tool bodies, and compare against a frozen baseline when measuring a reduction target
- use `compact_exec.py` for commands likely to emit large logs; full output stays in tmp artifacts while the terminal/tool result stays compact
- use `automation_health_dashboard.py` for compact local automation readiness and trend history
- use `major_closeout_delta.py` to paste compact trend/tool-bloat/OTEL fields into major workflow closeouts without rereading large artifacts
- use `workflow_automation_autonomy_review.py` to classify P0/P1/P2/P3/P4 workflows by safe heartbeat, cron, helper-lane, and main-session posture
- use `operator_packet.py` to refresh standardized recovery packets for the high-risk long-work lanes: SQL/WF78, Retail SaaS/WF75, WF68 alerts, WF67 paper, and bounded portfolio/canon maintenance
- use `pm_control_packet.py` as the primary PM fast path. `python scripts\pm_control_packet.py --write --write-db --validate` writes `tmp/pm-control-packet.json` and `.sqlite`; `summary.stale_lane_digest` is the compact PM-yellow drilldown. Legacy PM sidecars are opt-in only with `--write-compat`. Coordination only: no launch, customer data, external delivery, SQL import, archive/delete, canon/portfolio mutation, paper/live/account action, helper spawn, heartbeat execution, or owner approval inference.
- use `pm_sidecar_retirement_guard.py --write --validate` after PM/cockpit/routing edits to ensure active consumers read `tmp/pm-control-packet.json` instead of legacy PM state, queue, heartbeat, or handoff sidecars.
- use `cron_control_packet.py --write --validate` as the primary cron fast path. It composes cron freshness, handoff first-proof, signal scorecard, and escalation state into `tmp/cron-control-packet.json`; drill into `handoff_first_proof_gate.py`, `cron_freshness_spine.py`, `cron_signal_scorecard.py`, or `escalation_trigger.py` only when the packet reports handoff repair need, attention, blockage, stale/noisy signals, or route-specific detail.
- use `otel_ops_control.py --write --write-db --validate` as the local OTEL fast path. It turns official collector debug summaries and legacy receipt rows into `tmp/otel-ops-control.json`, `tmp/otel-ops-events.jsonl`, and `tmp/otel-ops.sqlite`; cron control, fast QA, model-quality scorecard, and validator timing consume this packet instead of parsing collector logs independently.
- use `changed_file_validator_router.py --write --validate` before manual validation planning. It maps the current diff to the smallest honest validator budget and keeps DB lifecycle plus WF75 major closeout reserved for exact shared/major routes. It recommends only; it does not execute validators.
- use `validator_timing_ledger.py --profile normal --write --validate` when measuring validation efficiency. `normal` is the routine control-plane timing route; `shared` and `major` are explicit opt-ins for broader proof.
- use `long_work_packet_linter.py` for long-work plan/lease preflight and `long_work_job_status_packet.py --write --write-md --validate` for actual runtime/checkpoint status. Provider-backed or full-source jobs should publish resumable status and run in bounded `--max-seconds` slices instead of one foreground tool call.
- use `workflow_router.py WF## --answer summary|next|blockers|helper|all` as the low-overhead workflow lookup before broad scans. `workflow_router.py --all --write-capsules --validate` writes compact route capsules to `state/workflows/*.json`. Use `workflow_control_override.py hold|resume ... --validate` for workflow pause/resume state; PM, heartbeat, and route index consume `state/workflow-control-overrides.json`.
- use `retail_truth_routing_contract.py` as the retail-grade answer routing contract. Phase 1 names the current owner artifacts, source-open requirements, bounded SQL read/proof role, PM coordination role, next phases, and stop lines for ticker, portfolio, entry/stop, freshness, capital-deployment, paper-card, SQL-scaleout, and customer-safe blocked routes. Phase 2 adds an enforced per-route `source_open_gate` (emits source-open proof + an ordered fallback condition; `sql_first_answer_allowed=False`) validated for every ready route. It writes `tmp/retail-truth-routing-contract.json` (with `implemented_phases`, `source_open_gate_enforced=true`) and is report-only: no SQL writes/imports, SQL-first promotion, customer/external output, canon/portfolio mutation, paper/live/account action, Python fallback retirement, or owner approval inference.
- use `retail_answer_harness.py` as the Phase 4 adversarial regression layer over `veritas_question_router.build_route`. It runs clean cases (must classify correctly and emit a source-open contract) plus seeded-bad cases (unknown ticker, authority/execution question, customer advice, guaranteed returns, stale-source claim, allocation demand, and brokerage/action request) that MUST block the final answer (`answer_contract_v2 ... final_answer_allowed=False`), surface missing/residue, and keep every authority flag review-only. It writes `tmp/retail-answer-harness.json` (`veritas.retail_answer_harness.v1`) and is wired into `veritas_harness_scorecard.py` (`retail_answer_harness` check on `validation.status`). Report-only; it complements `finance_intelligence_router_qa.py` rather than duplicating clean-classification tests.
- use `retail_automation_control_plane.py` as the Phase 4.5-7 automation-first control packet. It reads the retail truth routing contract, answer harness, clean/seeded-bad retail SaaS validator artifacts, WF72 A2 guard, WF78 all-safe packet, and harness scorecard, then writes `tmp/retail-automation-control-plane.json` with route gates, SQL support health, customer-safety gate state, seeded-bad coverage, freshness prompts, internal demo cards, and quiet summary. It is surfaced in the PM cockpit Retail tab and wired into `veritas_harness_scorecard.py`. The enabled review-only cron `P0 Retail Automation Control Plane Guard` runs weekdays at 06:45 and 14:45 America/Phoenix in an isolated/no-delivery session; it refreshes the retail contract, answer harness, retail fixture proof, WF78 all-safe proof, WF78 AI event rerouting, hardening pass, automation control plane, PM state, and cockpit validation. It must not run `cron_operator_ledger.py`; cron inventory/freshness belongs to the dedicated freshness spine, scorecard, and escalation lane. Report-only: no customer/external output, SQL writes/imports, SQL-first promotion, canon/portfolio mutation, paper/live/account action, Python fallback retirement, or owner approval inference.
- use `wf75_closeout_refresh.py --validation-budget shared` after significant WF75 implementation work to refresh generic SMB pivot artifacts, WF75 service state, SQLite control-plane proof, operator console, PM update, artifact-only handoff, PM readiness brief, operator packet, the consolidated PM control packet, workspace boundary, and artifact index. Reserve `--validation-budget major` for DB lifecycle proof.
- use `wf75_service_led_saas_readiness_plan.py` to refresh the 6-10 week, 55-65% internal/service-led WF75 infrastructure plan; current work is anonymous-scenario service-state storage, SQLite WAL control plane, operator queue/status, operator console/control cockpit, renderer/export pipeline, QA regression, scenario-template library, artifact-only PM handoff, and weekly PM readiness PDF. It can use real public ticker/company/market evidence when source-labeled and validator-gated, but it cannot grant public launch, real customer data, external delivery, legal/compliance, source-licensing, trading/account, paper execution, or portfolio/canon authority
- use `wf75_deliverable_packager.py` to keep the WF75 polished-deliverables spine current. It reads WF75 service-state, operator console, scenario library, renderer regression, PM readiness PDF manifest, artifact-only handoff, and WF75 capsule, then writes `tmp/wf75-deliverable-packaging-plan.json/.md`, `tmp/wf75-deliverable-packager.json`, and the internal operator workbook `tmp/wf75-deliverables-workbook.xlsx`. It treats the internal PM PDF and operator Excel as live internal review deliverables while keeping customer-safe PDF/Excel exports planned and gated behind no-leak/no-claim, source/freshness, policy, operator-review, source-licensing, and compliance gates. It is not external delivery, public launch, customer-data authority, legal/compliance readiness, source-licensing clearance, finance canon/portfolio mutation, paper/live/account action, or approval authority.
- use `finance_delivery_series_orchestrator.py` to keep Randall's recurring finance intelligence delivery series fresh. It reads macro, WF84/WF85, trade-grade, performance, WF87 paper-pilot, PM, cron, and WF75/SaaS artifacts, then writes `tmp/finance-delivery-series.json`, `tmp/finance-delivery-series.xlsx`, and HTML/PDF outputs under `tmp/finance-delivery-series/` for daily market read, weekly market read, weekly investments and performance, monthly investment direction, and monthly market deep dive. Daily/weekly outputs are concise; monthly outputs are deeper and include fundamentals, business outlook, YoY finance, charts, scenario outlook, SaaS/SMB interconnect, KPIs, and improvement signals. It is internal review only: no customer/public delivery, legal/compliance/source-licensing claim, capital deployment, portfolio/canon mutation, paper/live/account action, forecast certainty, or owner approval inference.
- use `wf77_supplemental_price_evidence.py` before `wf77_price_freshness_bridge.py` when production WF77 coverage needs review-only public price rows for tickers outside `technical_refresh` entitlement; this supplements freshness proof without widening portfolio/deployment scope
- use `wf75_scenario_template_library.py` and `wf75_renderer_export_regression.py` to refresh the anonymous scenario library and reusable renderer/export regression proof; clean scenarios must pass and seeded-bad cases must fail before PM handoff claims
- use `wf75_service_state.py` to refresh the Phase C/D JSON service-state, service-run, operator-queue, and movement proof. The current recommended slice is `--scenario-id anon-risk-freshness-edge-cases-v1` for supplemental price, macro/speculative, and below-stop/repair wording coverage. It records anonymous request state, validator state, WF77 freshness blockers, next operator action, and heartbeat pickup. It is JSON v0 only, not a customer DB, customer intake authority, external delivery path, canon/portfolio mutation, SQL import, paper/live/account action, or approval surface.
- use `wf75_service_state_sqlite.py` to refresh the WF75 SQLite WAL control-plane proof at `tmp/wf75-service-state.sqlite` and `tmp/wf75-service-state-sqlite.json`. It indexes anonymous service request state, artifact refs, queue rows, events, and one-worker claim proof with WAL, `busy_timeout`, and foreign-key validation. It is local control-plane infrastructure only, not finance canon, not a customer DB, not SQL/ticker import, not approval, and not execution/account authority.
- use `macro_event_calendar.py` to refresh the review-only high-impact macro calendar at `tmp/macro-event-calendar.json/.md`. It tracks CPI, PPI, labor, FOMC, and PCE release timing plus follow-up expectations; it is source-labeled schedule proof, not a forecast/probability surface, portfolio/canon mutation path, or paper/live execution authority.
- use `artifact_intelligence_action_scorer.py` to refresh the review-only cross-artifact materiality/action queue at `tmp/artifact-intelligence-action-scorer.json`. It reads macro calendar/metrics/judgment, WF78 routing/confidence/event-rerouting, and workflow routing proof to classify changes into safe actions such as refresh artifact, repair evidence, rerun validator, reroute candidate, block readiness, prepare review packet, escalate, or notify-if-material. It writes only its own queue and grants no workflow mutation, canon/portfolio mutation, ticker-card mutation, SQL-canon mutation, customer/external delivery, capital deployment, paper/live execution, brokerage/account action, money movement, or owner approval inference.
- use `macro_metrics_ingest.py` to refresh the review-only current macro metrics surface at `tmp/macro-metrics-current.json/.md` plus derived SQLite companion `tmp/macro-metrics-current.sqlite`. It ingests public FRED CSV rows for CPI, PPI, PCE, unemployment, payrolls, claims, and GDP; parses the official BLS CPI news release into `cpi_release_detail` and `cpi_release_components` DB rows for all-items/core/food/energy/gasoline/shelter/rent/OER decomposition; uses the official ISM manufacturing report/PDF for PMI; and can fall back to `tmp/market-state.json` proxies for Treasury 2Y, Treasury 10Y, and DXY when FRED paths are unavailable. Fetches run in bounded parallel batches (`--max-workers`, default 6) with per-series timeout (`--timeout`, default 6 seconds). If a live fetch fails, a recent previous `ok` metric or CPI release detail may be reused as `source_mode=cached_fallback` within `--cache-max-age-hours` while the artifact remains warning-classified. It is metrics proof only, not a forecast/probability surface, portfolio/canon mutation path, or paper/live execution authority.
- use `macro_signal_spine.py` to refresh the review-only strategic macro signal spine at `tmp/macro-signal-spine.json`. It adds Sahm Rule plus UNRATE fallback, claims trend, Yale/Shiller CAPE, a clearly labeled FRED/Fed Z.1 Buffett-indicator proxy, NFCI/ANFCI, HY/IG OAS, rates/volatility context, and expanded index/breadth confirmation (SPY, QQQ, IWM, MDY/IJH, RSP, VTV/VUG, VXUS, EFA/EEM, VIX, MOVE). Cadence: daily market-day run for source freshness, with monthly/quarterly/weekly interpretation windows by source. It is evidence/routing support only, not a timing model, forecast/probability surface, portfolio/canon mutation path, capital action, or paper/live execution authority.
- use `macro_energy_supply_ingest.py` to refresh the review-only official energy-supply artifact at `tmp/macro-energy-supply.json/.md`. It parses the EIA Weekly Petroleum Status Report table 1 CSV for crude, gasoline, distillate, propane/propylene, and total-stock context, then attempts Baker Hughes official rig-count pages with short fail-soft timeouts and cached fallback when available. It is energy-supply evidence only, not a forecast, commodity recommendation, portfolio/canon mutation path, or paper/live execution authority.
- use `macro_geopolitical_sweep.py` to refresh the review-only official-source geopolitical sweep at `tmp/macro-geopolitical-sweep.json/.md`. It scans configured official RSS/Atom feeds by title/link keyword buckets for energy supply, trade/tariff, defense/conflict, and financial-sanctions review cues. It is routing evidence only, not a news-completeness claim, geopolitical conclusion, portfolio/canon mutation path, or paper/live execution authority.
- use `macro_judgment_draft.py` to refresh the repeatable review-only macro interpretation layer at `tmp/macro-judgment-draft.json/.md`. It fills weekly macro judgment fields from macro metrics, the macro signal spine, macro calendar, market state, macro regime, regime scores, deployment posture, EIA/Baker energy supply, geopolitical sweep artifacts, and the current-regime analog scenario panel while preserving manual-dependency warnings for unavailable inputs. It is first-draft interpretation only, not final macro doctrine, forecast/probability authority, portfolio/canon mutation, capital action, or paper/live execution authority.
- use `json_sql_promotion_index.py` to refresh the JSON-to-SQL promotion registry and derived SQLite index at `tmp/json-sql-promotion-registry.json/.md`, `tmp/json-sql-promotion-index.json/.md`, and `tmp/json-sql-promotion-index.sqlite`. JSON remains proof/source/rebuildable evidence; SQLite is only a fast derived lookup/control plane over stable macro, WF75, research, and decision-packet JSON contracts. It is not canon, approval, portfolio authority, capital action, customer authority, SQL import authority, or paper/live/account authority.
- use `wf75_operator_console.py` to refresh the local static WF75 operator console/control cockpit at `tmp/wf75-operator-console.json`; HTML/Markdown sidecars are explicit optional renders. It reads the SQLite WAL DB, service state, queue, renderer/scenario proof, macro-event calendar, WF77 bridge, PM handoff/update/PDF, and cron plan to show artifact health, lifecycle state, next operator action, and blocked authority flags. It is local internal control only, not a public UI, customer portal, approval surface, SQL import, or execution/account authority.
- use `veritas_harness_scorecard.py` as the unified active-workflow harness gate. It inspects WF75/WF55/WF77 proof artifacts plus the SMB Workflow Clarity contract/scenario/preview/pilot/automation-blueprint artifacts and `tmp/wf75-smb-boundary-lint.json`. Use `--fast` for chat-safe routine command checks (Python compile, artifact-index validation, Node syntax), `--go` for Go/build/SQL-helper checks, and `--full` for all command lanes including OpenClaw skills and slow/product regression. `warning` means review-only readiness debt; hard failures block readiness claims.
- use `veritas_harness_failure_classifier.py` to classify reported OpenClaw/tool errors before deciding whether they are harmless Windows shell/path issues, warning-only validator debt, real breakage, stale evidence/readiness gaps, or authority regressions.
- use `wf75_artifact_only_pm_handoff.py` to refresh `tmp/wf75-artifact-only-pm-handoff.json/.md` from the WF77 bridge, renderer regression, scenario library, service state, operator queue, PM weekly update, operator console, and SQLite WAL control-plane proof. It is internal artifact-only PM/operator handoff, not external delivery or customer/public readiness.
- use `veritas_pm_department_validate.py` to prove the PM/PDF skill contract still points at live WF75 sources and preserves blocked launch/customer/source/legal/execution authority
- use `wf75_pm_weekly_update.py` to generate the current WF75 weekly PM update and presentation handoff from live readiness/operator artifacts
- use `wf75_cron_automation_authority_plan.py` to prove the paired WF75 weekly automation model: isolated cron builds bounded PM artifacts, main-session Veritas reads them and reports intelligence to Randall only when material, stale, blocked, or decision-needed. `--write` is JSON-first; use `--write-md` only for an explicit human rendering.
- use `cron_operator_ledger.py` as the JSON-first current cron operator inventory route. It reads the live cron store plus run summaries/current-window artifacts and writes `tmp/cron-operator-ledger.json`; the optional Markdown digest is generated from JSON and should stay compact.
- use `cron_freshness_spine.py --write --validate` as the cron freshness component behind `cron_control_packet.py`. It writes per-job state plus attention buckets: urgent blocked/owner-decision, main review queue, monitor-only/stale, and quiet success. Review-only; no cron schedule/config/runtime, SQL, canon/portfolio, customer, paper/live/account, or approval authority.
- use `morning_control_digest.py` as the weekday morning proof gate. It reads morning, sector, current-window, WF68, SQL coverage, cron ledger, PM, and service-state SQL surfaces into `tmp/morning-control-digest.json`; after clean `NO_REPLY` proof, the separate weekday morning main-session handoff is disabled and awareness routes through the digest, cron freshness spine, scorecard, and escalation trigger.
- use `cron_notes_flattening_plan.py` as the full migration plan from heavy mixed cron Markdown to thin human Markdown plus structured JSON truth. It is plan/proof only and cannot mutate cron schedules, archive/delete files, mutate canon/portfolio state, deliver externally, or authorize paper/live/account action.
- use `cron_execution_posture_patch.py` to audit or apply the payload-only JSON-first cron posture patch: remove restrictive Python execution settings from enabled producer jobs, replace routine `current-window-artifacts.md` references with JSON, add cron-operator-ledger refreshes to producers, and wire main-session handoffs/watchdogs to read the ledger. It writes a timestamped cron-store backup before applying and does not add/delete jobs or change schedules.
- use `cron_patch_manager.py` as the Gateway cron patch route before manual live cron edits. Default mode is plan-only: it resolves one job by exact name or id, shows the requested diff, classifies authority impact, and writes `tmp/cron-patch-manager.json`. With explicit `--apply`, it writes a backup under `tmp/cron-patch-manager-backups/`, applies only supported fields (`description`, agent message/model/thinking/timeout/light-context, and failure alert), and can run ordered verification. With `--rollback <backup.json>`, it restores those supported fields from backup. It refuses schedule, delivery, lifecycle, config/runtime, and authority-widening patches by default.
- use `cron_contract_validator.py` to compare live Gateway cron jobs against local intended-contract JSON under `state\cron-contracts\`. It writes `tmp/cron-contract-validator.json`, reports drift/missing jobs, and performs no live cron mutation. Current priority contracts cover Memory Dreaming Promotion, WF78 Daily Freshness, Weekday Morning Review, Weekday Post-Close Review, WF78 Open-Ready Owner Review, Tier A Intraday/Confirmation/Late-Session probes, morning/midday paper deployment recommendation cards, WF85 Paper Deployment Telegram Radar, WF85 Post-Refresh Paper Deployment Telegram Radar, WF87 Market-Hours Fresh Gate Probe, and the weekly OS-improvement radar reminder.
- use `worktree_checkpoint_planner.py` before local checkpoint/commit work. It groups dirty paths into coherent staging batches, flags sensitive/generated surfaces, and routes the matching validator set without staging, committing, reverting, deleting, or pushing.
- use `validator_bundle_router.py` as the active wrapper around `changed_file_validator_router.py`. Default mode plans the smallest honest validator bundle; `--execute` runs only guarded `python`/`openclaw` commands without shell metacharacters or apply/submit/promote/import tokens.
- use `artifact_staleness_explainer.py` when a control surface is stale, missing, or confusing. It maps the artifact to its likely owner, source refs, age, reason, and refresh command without refreshing or mutating anything.
- use `lane_collision_preflight.py` before starting multi-surface implementation or helper work. It checks intended write paths against active lane leases, forbidden-write policy, and dirty worktree overlap; it does not lease or write the lane register.
- use `authority_matrix.py` as the general approval-lane spine for SQL/ticker import, SQL reads/writes, bounded canon/portfolio mutation, customer/suitability/account data, credential reference/secret handling, and external delivery. It defines gates only; it does not grant SQL import, canon/portfolio apply, customer data, credential storage, external delivery, account action, or execution authority.
- use `sql_staging_import_gate.py` after the authority matrix to prepare a fail-closed staging-import review surface. It consumes provider/schema/no-regression/rollback proof and stays blocked until an exact import scope, table list, hashes, post-import validators, and scoped approval artifact exist. It performs no import or SQL write.
- use `bounded_canon_mutation_approval_packet.py` as the proposal-only approval packet for bounded workspace canon/portfolio categories. It can prepare review, diff, validator, rollback, and audit-event requirements, but it cannot apply changes, infer owner approval, change cash/risk rules/execution entitlement, or touch account/paper/live systems.
- use `audit_event_table_design.py` for the future service-state audit-event table design. It is schema design only and creates no DB; customer data, credential secrets, external delivery, and account/execution events remain future-gated.
- use `sql_retail_grade_validation_bundle.py` for the on-demand/change-triggered WF72/WF78 SQL retail-grade validation lane; it keeps SQL-first retail use explicitly `blocked_expected`, forbids production answer-path writes, runs the ticker-card pilot in `--validate-only` mode, and proves helper, no-drift, WF78, index, dashboard, and boundary checks
- use `sql_retail_expansion_phase_gate.py` after the bundle to prove Phases 1-4: baseline freeze, 42-card additive-overlay no-drift, semantic retail blocker classification, and existing 25-name pilot hardening; non-`--write` mode must not delete existing proof artifacts, and the gate prepares Phase 5 design without importing tickers
- use `sql_500_ticker_expansion_design_gate.py` for the 100-row WF78 baseline plus 500-ticker shard/readiness gate. It proves 42 production cards stay locked, 58 review-monitor rows remain thin until enriched, the 25-name pilot stays isolated, provider/coverage proof is present, tier targets sum to 500, and the first 10-name enrichment pilot is bounded. It does not import broad names, change cron schedules, expand SQL canon, or change production cards.
- use `wf78_500_ticker_reputation_gate.py --write --write-db --validate` as the repeatable 100->500 reputation gate. It outputs `tmp/wf78-500-ticker-reputation-gate.json/.sqlite` with 500 candidate rows, five 100-name batch lanes, reputation scores, source-open/provider/freshness posture, repair queues, promotion eligibility, next actions, and closed authority flags. It is review-only and performs no import/apply/promotion.
- use compiled `scripts/go/bin/go-sql-500-expansion-design-gate.exe` for the Go companion WF78 500-gate path in harness/runtime scorecards; the current accepted gate status is `ready_for_source_open_cleanup`.
- use `wf78_enrichment_orchestrator.py` for bounded review-monitor enrichment batches. `--batch pilot-10` refreshes fundamentals and analyst consensus for `AAPL`, `AVGO`, `ASML`, `COST`, `CRM`, `PANW`, `TSM`, `V`, `UNH`, and `WMT`, builds the selected ticker cards, refreshes all-100 SQL current state, and reruns the WF78/SQL gates. It merges selected rows into current artifacts instead of replacing the universe. Default retry mode does not append duplicate fundamentals JSONL history; pass `--append-history` only when intentionally creating a durable history row. It is review-only and grants no production-card promotion, customer output, canon/portfolio mutation, owner approval, or paper/live/account authority.
- use `sql_pre_phase5_hardening_gate.py` before any Phase 5 design packet; it records the current-proof/tmp routing manifest and exclude rules, checks fresh WF78 provider/runtime proof, runs A/B production-42 card hash no-regression when `--run-gates` is supplied, records retail fixture renderer/export validation, and verifies the legacy mutating `artifact_index.py phase4a-activate` path is guarded
- use `sql_hardening_flattening_plan.py` as the flattened operator packet for SQL hardening phases, command-surface flattening, tmp routing, provider/runtime proof, renderer validation, and Phase 5 no-import readiness
- keep the `sql_source_truth_*` gate sequence for historical promotion/retirement/external-activation decisions; internal SQL-canon current-state migration is complete for answer-path scope, evidence freshness, reference levels, source lineage, tier routing, and universe membership, while retail/customer SQL-first remains blocked behind separate readiness gates
- use `sql_source_truth_field_family_decision_packet.py` as the human decision surface before any separate apply packet; it requests approval to prepare the apply packet only and cannot apply/promote by itself
- use `sql_source_truth_apply_scaffold.py` after the decision packet to generate the separate no-apply scaffold: preapply backups, rollback simulation, SQL-first consumer diff, archive readiness, and post-apply validator proof. It cannot promote SQL, write SQL, migrate consumers, mutate Markdown/canon/portfolio state, archive/move/delete files, allow customer output, or grant paper/live/account authority.
- use `sql_source_truth_exact_apply_packet.py` for the exact owner-facing apply packet after the scaffold; current safe scope is only the 42-ticker entry/stop reference metadata read path, with backup, rollback trigger, SQL-first consumer diff, and post-apply validators. It does not import tickers or authorize action/recommendation/customer/execution fields.
- use `sql_first_consumer_wiring_preflight.py` only as an on-demand preflight after scoped SQL/helper/router changes or before owner-reviewed SQL packets; it proves the bounded finance-state/router command path is present, authority flags remain false, source-open fallback remains required, and recurring chain churn is absent.
- use `wf78_100_ticker_candidate_scope_packet.py` to prepare the review-only 100-ticker candidate-scope packet; it proposes Tier C thin monitor candidates and required research/proof before any import, but performs no SQL writes, universe writes, production answer-path change, customer output, or execution action.
- use `wf78_100_ticker_import_gate.py` only after explicit owner approval for a review-only monitor import. It creates backups, probes the exact 58-name review set, converts prior pilot fixtures into `review_100_monitor` rows instead of duplicating them, preserves the 42 production answer path, and emits import/provider proof. It does not create production cards, expand SQL canon/cache, authorize customer output, or authorize capital/trade action.
- use `finance_sql_canon.py` only in an approved SQL-canon maintenance lane to rebuild/validate the durable finance SQL canon at `state/finance/finance-canon.sqlite`, sync the universe JSON summary, and create backup/rollback proof. It does not archive candidates by itself and grants no portfolio/canon-note mutation, customer delivery, sizing/cash/risk-rule authority, paper/live execution, brokerage/account action, or money movement.
- use `finance_sql_canon_archive_apply.py` only after explicit owner archive approval to apply the WF78 legacy-42 proof archive microbatch. It reference-scans archive-plan candidates, moves only files with no live script/control-surface dependency into `09. Archive/WF78 Finance SQL Canon Legacy 42 Proof/2026-05-30/`, writes `tmp/finance-sql-canon-legacy-42-archive-apply-report.json`, and leaves dependency-blocked proof files in place. It never deletes files and grants no portfolio/canon-note mutation, customer delivery, sizing/cash/risk-rule authority, paper/live execution, brokerage/account action, or money movement.
- `sql_source_truth_promotion_readiness_gate.py` cannot promote SQL, migrate consumers, import tickers, mutate Markdown/canon/portfolio state, authorize customer output, or grant paper/live/account authority
- use `tmp_helper_residue_cleanup.py` only for exact tmp Python helper cleanup with manifest, hashes, archive target, and rollback-by-move-back; it never deletes files

Boundary:
- report-only local operator evidence
- no config/auth/runtime/network/cron/canon/portfolio mutation
- no raw prompt/tool/system/content export
- no finance/trading/account/paper/live authority
- heartbeat continuation candidates may queue or wake bounded main-session review only; they do not grant phase execution, helper swarms, SQL import, customer launch, external delivery, cleanup, canon/portfolio apply, paper/live/account action, or owner approval
- dashboard/trend health must not be treated as owner approval, capital-action permission, or Gateway/native-runtime migration approval

### `openai_provider_compat_matrix.py`

Status: bounded report-only OpenAI/OpenClaw SDK/provider compatibility matrix.

Summarizes the installed OpenClaw package version, bundled SDK/library state, OpenAI Responses/Completions/Codex routing considerations, native Codex runtime vs `openai-codex/*` PI behavior, prompt-cache knobs/accounting, Gateway-compatible endpoint posture, telemetry availability, exact config-change packet requirements, security stop lines, a non-mutating local validator checklist, and safe enhancement recommendations.

Run:
```bash
python scripts/openai_provider_compat_matrix.py --write
python scripts/openai_provider_compat_matrix.py --validate-only
```

Writes:
- `tmp/openai-provider-compat-matrix.json`
- `tmp/openai-provider-compat-matrix.md`

Boundary:
- report-only local inspection
- no config/auth/runtime/package/plugin mutation
- no secret collection, package installs, Gateway endpoint enablement, external API calls, or finance/trading authority
- evidence comes from the installed local OpenClaw package/docs/dist files
- any future direct OpenAI, native Codex runtime, or Gateway `/v1` endpoint migration must be a separate approved config/security packet with schema lookup, backup, redacted diff, rollback, and post-change proof

### `openclaw_otel_privacy_packet.py`

Status: privacy-reviewed diagnostics-otel approval packet and validator/prototype.

Builds a local-only telemetry proposal for request correlation, latency, cache/token usage, and bounded rate-limit/error visibility with content capture off. It also discloses the current gap that exact `x-ratelimit-*` header metrics are not confirmed as out-of-the-box diagnostics-otel exports.

Run:
```bash
python scripts/openclaw_otel_privacy_packet.py --write --validate
```

Writes:
- `tmp/openclaw-otel-privacy-packet.json`
- `tmp/openclaw-otel-privacy-packet.md`

Boundary:
- packet/validator only; no config edit, plugin install/enable, service start, Gateway restart, collector start, or external API call
- no prompt/response/tool/system-prompt capture, raw request-id export, secret/header collection, package upgrades, or finance/trading/account authority
- phase-1 proposal is loopback-only, metrics/traces only, OTLP logs off, and `diagnostics.otel.captureContent.*` all false

### `wf74_learning_loop_eval_harness.py`

Status: primary WF74 learning-loop routing and dispatch regression harness.

Run:
```bash
python scripts/wf74_learning_loop_eval_harness.py --write --validate
python scripts/test_wf74_learning_loop_eval_harness.py
```

Writes:
- `tmp/wf74-learning-loop-eval-harness.json`

WF74 eval-surface ownership:
- primary: `tmp/wf74-learning-loop-eval-harness.json`, produced by this script
- secondary: `tmp/wf74-outcome-eval-suite-v2.json`, produced by `python scripts/wf74_rsi.py --outcome-eval-v2`
- deprecated compatibility/drill-in only: `tmp/wf74-rsi-evaluation-harness.json`, produced by `python scripts/wf74_rsi.py`
- RSI maturity/rubric state is folded into this primary harness under `rsi_maturity`; WF88 must read RSI status from this primary artifact, not from the deprecated compatibility artifact

Boundary:
- review-only eval contract; no auto-apply, code mutation, skill application, cron schedule mutation, finance canon/portfolio mutation, paper/live execution, owner approval inference, or base-model self-modification
- the legacy RSI harness remains available for one transition cycle but is not first-hop WF74 eval truth; archive/delete requires clean references and explicit cleanup authority
- regression guard: `test_wf88_wiki_synthesis_packet.py` must block if `tmp/wf74-rsi-evaluation-harness.json` is restored as a required WF88 source

### `wf74_rsi.py`

Status: WF74 bounded recursive-self-improvement validator, secondary outcome fixture generator, and deprecated compatibility RSI scaffold.

Run:
```bash
python scripts/wf74_rsi.py --validate-only
python scripts/wf74_rsi.py --outcome-eval-v2
python scripts/test_wf74_rsi_outcome_eval_v2.py
```

Writes:
- normal generation writes the WF74 review artifacts under `tmp/wf74-rsi-*`, `tmp/wf74-clawhub-*`, `tmp/wf74-reflection-*`, and `tmp/wf74-outcome-eval-suite-v2.*`
- `--outcome-eval-v2` writes only `tmp/wf74-outcome-eval-suite-v2.json/.md`
- `--validate-only` writes nothing and validates existing artifacts plus in-memory outcome-eval fixtures
- `tmp/wf74-rsi-evaluation-harness.json` is compatibility/drill-in only, not first-hop WF74 eval truth

Boundary:
- validate-only / report-only RSI support
- no canon/portfolio mutation, owner approval, finance authority expansion, config/auth/channel/service/runtime mutation, destructive cleanup, external action, or trade/account/paper/live authority
- fixture success is proof of classifier coverage only, not a claim that Veritas behavior is globally solved
- current evaluator coverage includes shell/tooling mismatch, taxonomy alias gaps, post-compaction recovery, and skill-sprawl governance gates in addition to stale-state, approval, helper, patch, archive, retrieval, SQL, context-size, cache, and finance-boundary fixtures

### `workspace_governance_truth_check.py`

Status: read-only validator

Checks boot-file approval boundaries, active workflow alignment across the Active Workflows surface, parallel queue, and IC registry, workspace-structure ownership text, DB lifecycle route/manifest health, active-control-surface model-routing policy drift, and safe channel/plugin config snippets when the OpenClaw CLI exposes them. It includes the operator-approved exception that WF40 may remain residual scheduled-proof watch without reclaiming the active workflow slot.

Run:
```bash
python scripts/workspace_governance_truth_check.py
python scripts/workspace_governance_truth_check.py --write
```

Writes with `--write` only:
- `tmp/workspace-governance-truth-check.json`

Notes:
- warnings are explicit but do not fail the run
- critical cross-surface contradictions exit nonzero
- config snippets are summarized only; the validator does not print owner IDs or raw config
- model-routing checks scan active control surfaces only and report bounded file/line/snippet evidence for stale disallowed provider/runtime wording
- DB lifecycle checks require `tmp/db-lifecycle-manifest.json` to remain classified, integrity-clean, delete-ready-free, and discoverable through `TOOLS.md`; current scan scope includes `tmp/**/*.sqlite`, `state/**/*.sqlite`, and archived DB lifecycle files

### `sector_allocation_decision_matrix.py`

Status: generalized report-only sector/sleeve allocation decision matrix.

Builds `tmp/sector-allocation-decision-matrix.json/.md` from the existing sector-expansion board, deployment/trigger/technical artifacts, fundamentals, capital packets, probability readiness, and advisor trust gate. It compares all active sectors/sleeves, ranks candidates, labels growth/value posture, and preserves explicit no-authority flags.

Run:
```bash
python scripts/sector_allocation_decision_matrix.py --write
python scripts/test_sector_allocation_decision_matrix.py
```

Boundary:
- report-only / review-only sector allocation support
- no canon/portfolio mutation, owner approval, sizing/cash/risk-rule change, paper/live order, brokerage/account action, or trade authority
- scores are heuristic routing aids only while WF55 probability readiness remains `NOT_READY`

### `analyst_consensus_refresh.py`

Status: WF77 review-only analyst consensus/rating/price-target refresh.

Uses yfinance as the default breadth source for Yahoo-derived analyst recommendation counts and price targets, writes `tmp/analyst-consensus-current.json`, and marks unavailable values as null/stale rather than fabricating them. Tier A/B names are automatically placed on the weekly manual/source-open review queue before high-consequence recommendation, portfolio-change, or paper-order-card use.

Run:
```bash
python scripts/analyst_consensus_refresh.py --write --validate
python scripts/finance_data_coverage.py --validate --write-contract
python scripts/finance_intelligence_router_qa.py
```

Automation:
- cron job `95da55c1-5288-4aab-972e-b730ad140c55` runs Mondays at 15:30 America/Phoenix to refresh yfinance analyst data, rebuild WF77 coverage/card surfaces, validate router/index state, and announce the Tier A/B manual-review queue or blockers.

Boundary:
- yfinance/Yahoo-derived data is unofficial routing/review evidence, not institutional-grade authority
- source-open remains required before final finance claims
- no canon/portfolio mutation, owner approval inference, sizing/cash/risk-rule change, paper/live order, brokerage/account action, or money movement

### `finance_stack_snapshot.py`

Status: reusable full-stack finance intelligence snapshot and SQL query layer.

Builds `tmp/finance-stack-snapshot.json/.md` and `tmp/finance-stack-snapshot.sqlite` from the existing market-state, deployment-readiness, capital recommendation, sector allocation, Tuesday watchlist/sizing, probability-readiness, intraday-handoff, paper-readiness, and optional structured web/AI evidence seed artifacts. The SQLite export provides `latest_snapshot`, `latest_ticker_rows`, and web-evidence tables for fast querying.

Run:
```bash
python scripts/finance_stack_snapshot.py --write --validate
python scripts/test_finance_stack_snapshot.py
```

Boundary:
- report/query/review-only synthesis surface
- `tmp` SQL remains derived retrieval/staging only; `state/finance/finance-canon.sqlite` is the approved durable machine-canon candidate for universe/answer-path scope only
- no canon/portfolio mutation, owner approval, sizing/cash/risk-rule apply, paper/live order, brokerage/account action, or money movement
- web evidence and AI flags are cited advisory interpretation fields only; WF55 probability/win-rate language remains blocked while readiness is `NOT_READY`

### `chief_intelligence_promotion_gate.py`

Status: review-only Chief Intelligence promotion gate for capital-deployment and paper-card readiness.

Builds `tmp/chief-intelligence-promotion-gate.json` and `tmp/chief-intelligence-promotion-gate-validation.json` from technical refresh, deployment readiness, sector expansion, opportunity/freshness review, ticker monitoring performance, WF55 probability readiness, paper-position SQLite, and `tmp/portfolio-config.json` entry bands. The gate ranks candidates relative to alternatives, blocks out-of-band/below-stop/watch-only monitor drift, carries paper-position context, and labels WF55 probability as not ready when applicable. It is the required local proof surface before treating a buy candidate as paper-card ready.

Run:
```bash
python scripts/chief_intelligence_promotion_gate.py --write --validate
python scripts/test_chief_intelligence_promotion_gate.py
```

WF67 gated request generation:
```bash
python scripts/wf67_order_card_request_generator.py --card tmp\alpaca-paper-readiness\order-card.xlb-monday-band-gated-2026-06-01.json --require-promotion-gate
python scripts/test_wf67_order_card_request_generator.py
```

Boundary:
- review/routing/proof only
- no canonical note/model mutation, watchlist promotion apply, portfolio/cash/risk-rule mutation, paper order execution, live/account action, owner approval inference, probability/model authority, or money movement
- `--require-promotion-gate` only validates that a buy card is `promote_for_owner_review`, `IN_BAND`, and veto-free; it does not create a kill switch or submit an order

### `wf67_autonomous_paper_manager.py`

Status: review-only WF67 paper manager approval packet.

Builds `tmp/alpaca-paper-readiness/wf67-autonomous-paper-manager-current.json` and validation sidecar from the paper-position packet, Chief Intelligence gate, Monday order-card packet index, existing order cards, and WF67 request artifacts. With `--refresh-requests`, it regenerates eligible pending request artifacts through `wf67_order_card_request_generator.py --require-promotion-gate` semantics so each eligible request carries Chief Intelligence proof. It remains an approval/readiness surface only.

Run:
```bash
python scripts/wf67_autonomous_paper_manager.py --write --validate --refresh-requests
```

Writes:
- `tmp/alpaca-paper-readiness/wf67-autonomous-paper-manager-current.json`
- `tmp/alpaca-paper-readiness/wf67-autonomous-paper-manager-validation.json`
- refreshed pending `tmp/alpaca-paper-readiness/paper-trade-request.*monday-band-gated-2026-06-01.json` when `--refresh-requests` is used

Boundary:
- packet/request generation only; no Alpaca API call, no kill switch, no submit/cancel/sell
- no live endpoint/credentials, money movement, account mutation, portfolio/canon/cash/risk-rule mutation, owner approval inference, or probability/model authority
- ready names remain conditional on fresh market-session quotes, exact Randall approval, fresh WF67 guard validation, and a fresh short-lived kill switch

### `finance_universe_validator.py`

Status: WF78 durable universe registry builder/validator with production-vs-review-monitor scope separation.

Builds and validates `data/finance/universe-v1.json`. The file is now the rebuild/audit mirror for the SQL canon candidate. The legacy production answer path remains locked to the current 42 active WF77/WF72 tickers. WF78 review-monitor rows use `universe_scope: review_100_monitor` as Tier C, non-decision-grade, source-open-required thin metadata for breadth/routing only.

Run:
```bash
python scripts/finance_universe_validator.py --write-from-coverage --validate
python scripts/finance_universe_validator.py --add-pilot-fixtures --validate
python scripts/finance_universe_validator.py --validate
```

Writes:
- `data/finance/universe-v1.json`
- `tmp/wf78-finance-universe-validation.json`

Boundary:
- review/routing metadata only
- production rows use `universe_scope: production_current_42`; review-monitor rows use `universe_scope: review_100_monitor`; legacy fixture rows may be absent after conversion
- review-monitor rows do not enter production ticker cards, current 42 answer paths, approval queues, canon, sizing, cash/risk-rule, or execution authority
- no broad ticker import, no production overwrite, no owner approval inference, and no paper/live/brokerage/account action

### `wf78_tier_b_research_packet.py`

Status: WF78 report-only Tier B research/evidence packet route.

Builds the first evidence-depth packet layer between the macro/thesis overlay and the Phase 2 C->B promotion gate. It reads the macro shortlist, ticker-card refresh gate, current coverage artifact, promotion-review gate, available ticker cards, and evidence-repair proof, then writes concrete C->B research packets plus a Phase 2 request file. Current request-fed proof: 15 packets, 15 Phase 2 eligible for non-capital C->B routing.

Run:
```bash
python scripts/wf78_tier_b_research_packet.py --write --write-db --validate
python scripts/wf78_tier_funnel_promotion_gate.py --requests tmp/wf78-tier-b-research-packet-requests.json --out tmp/wf78-tier-b-research-packet-phase2-eval.json --write --validate
```

Writes:
- `tmp/wf78-tier-b-research-packets.json`
- `tmp/wf78-tier-b-research-packet-requests.json`
- `tmp/wf78-tier-b-research-packets.sqlite`
- downstream eval: `tmp/wf78-tier-b-research-packet-phase2-eval.json`

Boundary:
- packet/request/evidence-repair routing only
- an eligible Phase 2 verdict would still be eligibility only, not owner approval or Tier B admission
- no import, apply, promotion/admission, production answer-path expansion, SQL-first/canon/portfolio/customer output, paper/live/account action, or owner approval inference

### `wf78_tier_label_sync_preview.py`

Status: WF78 preview-only label-sync proof for approved Tier B research-bench labels.

Reads the record-only Tier label decision register and the durable universe registry, then previews how approved Tier B research-bench labels would map to a formal roster surface. It distinguishes names already carrying legacy universe `tier: B` metadata from names still legacy-C that would need a separate, owner-gated roster sync. It does not apply labels.

Run:
```bash
python scripts/wf78_tier_label_sync_preview.py --write --validate
```

Writes:
- `tmp/wf78-tier-label-sync-preview.json`

Boundary:
- preview/proof only
- no Tier A/B label apply, universe mutation, portfolio/canon mutation, ticker-card mutation, SQL mutation, production answer-path change, capital deployment, customer output, paper/live/account action, or owner approval inference

### `wf78_tier_a_confidence_gate.py`

Status: WF78 deterministic Tier A confidence/conflict gate.

Builds a repeatable confidence artifact for current Tier A names from the auto-router, fundamentals, IR reconciliation, and SEC reconciliation artifacts. It records data confidence, fundamentals confidence, critical conflicts, warnings, manual-review requirements, confidence reasons, and downstream `promotion_effect`. Critical operating-company SEC/data conflicts and ETF/proxy no-look-through cases force `A-CHALLENGED`; they cannot be `A-READY`.

Run:
```bash
python scripts/wf78_tier_a_confidence_gate.py --write --validate
```

Writes:
- `tmp/wf78-tier-a-confidence-gate.json`

Boundary:
- derived confidence/routing input only
- no Tier A admission, no promotion by confidence score, no universe/canon/portfolio/ticker-card/SQL-canon mutation
- no capital deployment, order execution, paper/live/brokerage/account action, money movement, customer/public output, or owner approval inference

### `wf78_auto_tier_router.py`

Status: WF78 automated non-capital tier/routing state generator.

Builds the live derived routing artifact for all active WF78 tickers under Randall's 2026-06-05 posture: Veritas may automate ticker tier/routing states; Randall approval is reserved for capital deployment, trade execution, paper/live/account action, and other explicitly gated mutations. The router consumes the universe registry, Tier A packet, Tier B label-sync preview, request-fed Phase 2 C->B gate output, the Phase 3 B->A competitive gate, production adjudication, and the Tier A confidence gate. It emits current automated `auto_tier` / `auto_state` rows while keeping execution and deployment approvals false.

Run:
```bash
python scripts/wf78_tier_a_confidence_gate.py --write --validate
python scripts/wf78_auto_tier_router.py --write --validate
python scripts/wf78_phase_runner.py --phase all-safe --write --validate
```

Writes:
- `tmp/wf78-auto-tier-routing.json`

Boundary:
- derived non-capital routing state only
- no universe/canon/portfolio/ticker-card/SQL-canon mutation
- no production answer-path change
- no capital deployment, order execution, paper/live/brokerage/account action, money movement, customer/public output, or owner approval inference

Next phased build:
1. downstream consumer sync to `tmp/wf78-auto-tier-routing.json` is complete for PM/routing-map surfaces: `pm_program_state.py`, `pm_implementation_job_queue.py`, `state/pm-cockpit-source-registry.json`, and `wf78_routing_dashboard.py`
2. daily routing delta packet is complete: `python scripts/wf78_routing_delta.py --write --validate` writes `tmp/wf78-routing-delta.json`
3. `route TICKER` quick packet is complete: `python scripts/wf78_route_ticker.py --ticker NVDA --write --validate` writes ticker-specific route packets such as `tmp/wf78-route-nvda.json`; current packets include `route_readiness` fields for routing tier/state, timing, decision, trade readiness, and authority so in-band names cannot be mistaken for approval-ready names.
4. `A-DEPLOY-CANDIDATE` capital-review queue is complete: `python scripts/wf78_capital_review_queue.py --write --write-db --validate` writes `tmp/wf78-capital-review-queue.json` and `tmp/wf78-capital-review-queue.sqlite`
5. Tier A confidence gate is complete: `python scripts/wf78_tier_a_confidence_gate.py --write --validate` writes `tmp/wf78-tier-a-confidence-gate.json`, and the auto-router consumes it so critical data conflicts cannot be `A-READY`
6. event-triggered rerouting is complete: `python scripts/wf78_event_triggered_rerouting.py --write --write-db --validate` writes `tmp/wf78-event-triggered-rerouting.json` and `tmp/wf78-event-triggered-rerouting.sqlite`
7. market execution-readiness cron hardening is complete: `python scripts/market_execution_readiness_cron_hardening.py --write --validate` writes `tmp/market-execution-readiness-cron-hardening.json`
8. weekday WF78 cron now runs request-fed Phase 2 C->B evaluation, Phase 3 B->A competitive evaluation, the post-gate auto-router, and `wf78_routing_delta.py`; `cron_freshness_spine.py` requires those artifacts.

`wf78_capital_review_queue.py` ranks current `A-READY` names for non-executing owner capital-review card preparation. It must keep every row owner-gated with `capital_deployment_approved=false`, `trade_or_execution_approved=false`, and `owner_action_required=true`. A queue row never grants capital deployment, order execution, paper/live action, brokerage/account action, or portfolio/canon mutation authority.

`market_execution_readiness_cron_hardening.py` checks the daily quote-readiness contract around WF68 and P0 cron windows. It requires the WF68 quote snapshot to cover the current WF78 Tier A/capital-review symbol set, confirms the quote artifact is current for the latest completed market date, separates calendar-aware closed-market quote status from unexpected provider staleness, and proves no execution/capital authority is granted. During regular market hours it requires intraday-fresh quotes; after close, weekends, and holidays it accepts latest-completed-session quotes only as review proof, not execution freshness.

`wf78_event_triggered_rerouting.py` is the AI work-selection layer. It reads the auto-router, routing delta, capital-review queue, and stale-ticker queue, then emits review-only actions for evidence repair, route review, and owner-card preparation. Every action must keep `apply_allowed=false`, `capital_deployment_approved=false`, `trade_or_execution_approved=false`, and `paper_or_live_execution_allowed=false`.

Acceptance target:
- every consumer uses the router output as derived non-capital state only
- no `A-READY` row has a critical data conflict
- capital-review packets remain separate and owner-gated
- all changed routes preserve hard-false execution, brokerage/account, money-movement, customer/public, and canon/portfolio authority

### `finance_sql_canon.py`

Status: WF78 first-pass durable SQL canon candidate for finance universe and answer-path scope.

Builds `state/finance/finance-canon.sqlite` from `data/finance/universe-v1.json`, validator artifacts, coverage proof, and provider proof. It records current active universe state, answer-path scope, evidence status, validator statuses, source artifacts, archive candidates, and audit events. It also writes the legacy-42 archive plan used by the guarded archive helper.

Run:
```bash
python scripts/finance_sql_canon.py --write --validate --approval-reference "<owner approval reference>"
```

Writes:
- `state/finance/finance-canon.sqlite`
- `tmp/finance-sql-canon-promotion.json`
- `tmp/finance-sql-canon-legacy-42-archive-plan.json`
- `backups/finance-sql-canon-promotion/<run_id>/manifest.json`

Boundary:
- approved SQL machine-canon candidate only for universe/answer-path scope
- JSON remains rebuild/audit proof; Markdown remains human judgment
- no portfolio/canon-note mutation, customer/external delivery, sizing/cash/risk-rule authority, paper/live execution, brokerage/account action, or money movement

### `finance_sql_canon_archive_apply.py`

Status: approved WF78 legacy-42 proof archive microbatch with reference-scan guard.

Reads `tmp/finance-sql-canon-legacy-42-archive-plan.json`, scans candidate references, and moves only eligible historical proof files into `09. Archive/WF78 Finance SQL Canon Legacy 42 Proof/2026-05-30/`. Files with live script dependencies stay in `tmp/` and are reported as blocked.

Run:
```bash
python scripts/finance_sql_canon_archive_apply.py --write --validate
python scripts/finance_sql_canon_archive_apply.py --apply --write --validate
```

Writes:
- `tmp/finance-sql-canon-legacy-42-archive-apply-report.json`
- archived proof files under `09. Archive/WF78 Finance SQL Canon Legacy 42 Proof/2026-05-30/`

Boundary:
- move-only archive microbatch
- no delete, no active script dependency archive, no config/auth/channel/runtime mutation, no portfolio/canon-note mutation, no customer/external delivery, no paper/live execution, no brokerage/account action, and no money movement

### `finance_human_notes_thinning_candidates.py`

Status: review-only finance human-note thinning candidate packet.

Builds `tmp/finance-human-notes-thinning-candidates.json` from Markdown notes. The first pass is intentionally conservative: it treats generated `tmp/*.md` sidecars with same-name JSON proof as candidates, scans script/control-surface references, proves the finance SQL-canon candidate is healthy, and marks only reference-clean rows as future move-only archive candidates. It does not move, delete, or mutate any note.

Run:
```bash
python scripts/finance_human_notes_thinning_candidates.py --write --validate
```

Writes:
- `tmp/finance-human-notes-thinning-candidates.json`

Boundary:
- plan/candidate packet only
- no archive move, no delete, no canonical-note mutation, no portfolio mutation, no customer/external delivery, no paper/live execution, no brokerage/account action, and no money movement

### `finance_human_notes_archive_apply.py`

Status: guarded move-only human-note thinning archive helper.

Reads `tmp/finance-human-notes-thinning-candidates.json` and selects eligible generated Markdown sidecars with JSON replacement proof. The default microbatch is 50 rows. Dry-run writes readiness proof only; actual moves require `--apply` plus an exact `--approval-reference`.

Run:
```bash
python scripts/finance_human_notes_archive_apply.py --write --validate --limit 50
python scripts/finance_human_notes_archive_apply.py --apply --write --validate --limit 50 --approval-reference "<exact owner approval>"
```

Writes:
- `tmp/finance-human-notes-archive-apply-report.json`
- archived generated Markdown sidecars under `09. Archive/Finance Human Notes Thinning/2026-05-30/` only when `--apply` is supplied

Boundary:
- move-only generated Markdown sidecar archive
- no delete, no owner-truth note archive, no active script/control-surface dependency archive, no canonical-note mutation, no portfolio mutation, no customer/external delivery, no paper/live execution, no brokerage/account action, and no money movement

### `core_folders_flattening_watchdog.py`

Status: core finance human-folder flattening watchdog for `01. Dashboards` through `05. Intelligence`.

Classifies every file in folders `01`-`05` as live, compression target, archive candidate, or blocked. It keeps owner-truth/current surfaces live, treats dated dashboard/macro/research snapshots as archive candidates, and writes the phased flattening/delete-readiness posture.

Run:
```bash
python scripts/core_folders_flattening_watchdog.py --write
```

Writes:
- `tmp/core-folders-flattening-watchdog.json`

Boundary:
- watchdog/candidate packet only
- no archive move, no delete, no owner-truth mutation, no portfolio mutation, no customer/external delivery, no paper/live execution, no brokerage/account action, and no money movement

### `human_facing_truth_surface.py`

Status: active human-facing routing surface generator.

Regenerates the compact review-only `01. Dashboards/Executive Brief.md` from current proof artifacts so Randall and Veritas have one first-read surface instead of scattered dashboard pickup notes.

Run:
```bash
python scripts/human_facing_truth_surface.py --write --validate
```

Outputs:
- `tmp/human-facing-truth-surface.json`
- `01. Dashboards/Executive Brief.md`

Boundary:
- orientation surface only
- no canon, owner approval, archive/delete apply authority, portfolio mutation, customer/external delivery, paper/live execution, brokerage/account action, or money movement

### `core_live_surface_migration.py`

Status: approved replacement-proof migration helper for the remaining live human finance surfaces.

Archives full source-open originals, writes structured replacement proof under `state/finance/`, and rewrites dependency-heavy live paths as compact parser-compatible stubs. Current covered surfaces are the post-earnings scorecards, `03. Portfolio/Rebalance Log.md`, `03. Portfolio/Execution Board.md`, and adjacent `04. Research/Coverage and Watchlist.md`.

Run:
```bash
python scripts/core_live_surface_migration.py --write --validate --scope report-only
python scripts/core_live_surface_migration.py --apply --validate --scope earnings-rebalance --approval-reference "<exact owner approval>"
python scripts/core_live_surface_migration.py --apply --validate --scope parser-surfaces --approval-reference "<exact owner approval>"
python scripts/core_live_surface_migration.py --scope rerender-stubs --validate
```

Writes:
- `tmp/core-live-surface-migration.json`
- `state/finance/earnings-scorecard-index.json`
- `state/finance/rebalance-log.json`
- `state/finance/execution-board-replacement.json`
- `state/finance/coverage-watchlist-replacement.json`
- compact live stubs at the original parser paths

Boundary:
- archive/compression only after exact owner approval
- no delete, no SQL-canon authority expansion, no owner approval inference, no portfolio/cash/risk-rule mutation, no customer/external delivery, no paper/live execution, no brokerage/account action, and no money movement

### `core_folders_archive_apply.py`

Status: approved move-only archive helper for watchdog-eligible `01`-`05` files.

Reads `tmp/core-folders-flattening-watchdog.json` and moves only rows marked `eligible_for_move_only_archive=true`.

Run:
```bash
python scripts/core_folders_archive_apply.py --apply --write --validate --approval-reference "<exact owner approval>"
```

Writes:
- `tmp/core-folders-archive-apply-report.json`
- archived files under `09. Archive/Core Finance Human Surfaces/2026-05-30/`

Boundary:
- move-only archive
- no delete, no owner-truth note archive, no active dependency archive, no canonical-note mutation, no portfolio mutation, no customer/external delivery, no paper/live execution, no brokerage/account action, and no money movement

### `archive_delete_readiness_plan.py`

Status: plan-only archived-file delete readiness packet.

Scans `09. Archive/` and classifies possible future delete candidates. It does not delete files and does not create delete authority.

Run:
```bash
python scripts/archive_delete_readiness_plan.py --write --validate
```

Writes:
- `tmp/archive-delete-readiness-plan.json`

Boundary:
- delete planning only
- deletion remains blocked until retention window, restore drill, replacement proof, post-archive validators, and a separate exact owner delete approval

### `full_workspace_delete_readiness.py`

Status: report-only full-workspace delete-readiness packet.

Scans the workspace and classifies deletion candidates into exact-approval-only generated residue, future archived-file deletion candidates, protected live surfaces, and manual-review blockers. It does not delete files and does not create delete authority.

Run:
```bash
python scripts/full_workspace_delete_readiness.py --write --validate
```

Writes:
- `tmp/full-workspace-delete-readiness.json`

Boundary:
- generated cache/log/temp candidates still require exact owner approval before deletion
- archived files require retention and restore proof before any future delete apply
- active numbered folders, `data/`, `state/`, `memory/`, `scripts/`, skills, and root doctrine/control files are protected

### `full_workspace_generated_residue_delete_apply.py`

Status: exact-approval-only generated-residue delete helper.

Consumes `tmp/full-workspace-delete-readiness.json` and deletes only rows already classified as `delete_ready_after_exact_approval` with an allowed generated-residue class. It verifies workspace path containment and current SHA-256 before file deletion, removes empty generated/cache directories, and writes a proof report.

Run dry-run:
```bash
python scripts/full_workspace_generated_residue_delete_apply.py --write --validate
```

Run apply only after exact owner approval:
```bash
python scripts/full_workspace_generated_residue_delete_apply.py --apply --write --validate --approval-reference "<exact owner approval>"
```

Writes:
- `tmp/full-workspace-generated-residue-delete-apply-report.json`

Boundary:
- deletes only approved generated residue from the readiness manifest: Python bytecode cache, OS metadata cache, temporary files, tmp logs, and empty generated/archive dirs
- no active live files, `tmp` machine proof/state, Markdown sidecars, presentation artifacts, archive files, config/auth/runtime files, canonical notes, portfolio/canon mutation, customer/external delivery, paper/live/account action, or owner approval inference

### `tmp_lifecycle_delete_proposal.py`

Status: proposal-only lifecycle delete plan for remaining `tmp` residue.

Reads `tmp/full-workspace-delete-readiness.json` and classifies only `tmp/` blocked/review rows into phased deletion, retention, or retarget/adjudication lanes. Non-`tmp` readiness rows are out of scope for this proposal. It applies the WF75 PM presentation-control migration posture from `08. Audits/Python SQLite TypeScript Node Presentation Control Layer Migration Audit - 2026-05-30.md`: PM/control JSON, SQLite, operator console HTML/PDF, and active dashboard render assets are retained unless replacement proof exists.

Run:
```bash
python scripts/tmp_lifecycle_delete_proposal.py --write --validate
```

Writes:
- `tmp/tmp-lifecycle-delete-proposal.json`

Boundary:
- proposal only
- no delete, archive move, canonical-note mutation, portfolio/canon mutation, customer/external delivery, config/auth/runtime change, paper/live/account action, or owner approval inference
- future delete phases still require exact owner approval and, where needed, restore/tombstone proof, consumer retarget proof, PM replacement proof, or workflow-owner retention policy

### `tmp_lifecycle_phase1_delete_apply.py`

Status: exact-approval-only phase-one tmp lifecycle delete helper.

Consumes `tmp/tmp-lifecycle-delete-proposal.json` and deletes only `tmp/` rows classified as `phase_1_delete_candidate_after_exact_approval` with one of three allowed classes: raw OTEL protobuf payloads, compact-exec command logs, or empty manual-review directories. It verifies workspace path containment and current SHA-256 before file deletion; filesystem-denied directories are reported as blockers rather than crashing.

Run dry-run:
```bash
python scripts/tmp_lifecycle_phase1_delete_apply.py --write --validate
```

Run apply only after exact owner approval:
```bash
python scripts/tmp_lifecycle_phase1_delete_apply.py --apply --write --validate --approval-reference "<exact owner approval>"
```

Writes:
- `tmp/tmp-lifecycle-phase1-delete-apply-report.json`

Boundary:
- deletes only phase-one generated/log/empty-dir residue from the lifecycle proposal
- no PM/control-layer artifacts, current finance/source proof, paper-readiness audit state, active presentation/dashboard render assets, workflow proof packets, backups, Markdown retarget candidates, canonical notes, portfolio/canon mutation, customer/external delivery, config/auth/runtime change, paper/live/account action, or owner approval inference

### `tmp_lifecycle_phase2_6_delete_apply.py`

Status: exact-approval-only tmp lifecycle delete helper for phases 2 through 6.

Consumes `tmp/tmp-lifecycle-delete-proposal.json` and applies only bounded `tmp/` cleanup rows. It deletes phase 2 backup/restore copies with SHA-256 tombstone proof, phase 3 Markdown rows only when current reference count is zero, phase 4 presentation rows only when current reference count is zero and the path is not an active presentation surface, phase 5 workflow proof packets only when current reference count is zero, and phase 6 unreferenced machine artifacts. Referenced Markdown/proof rows and active presentation surfaces are blockers for a producer/reference retarget pass.

Run dry-run:
```bash
python scripts/tmp_lifecycle_phase2_6_delete_apply.py --write
```

Run apply only after exact owner approval:
```bash
python scripts/tmp_lifecycle_phase2_6_delete_apply.py --apply --write --approval-reference "<exact owner approval>"
```

Writes:
- `tmp/tmp-lifecycle-phase2-6-delete-apply-report.json`
- `state/tmp-lifecycle-deletion-tombstone.json` when `--apply` is used

Boundary:
- delete scope is limited to `tmp/`
- referenced Markdown, active HTML/fallback render surfaces, and referenced workflow proof packets remain blocked until retarget/replacement/retention proof exists
- no PM/control-layer artifact delete, current finance/source proof delete, paper-readiness audit delete, canonical-note/portfolio mutation, config/auth/runtime change, customer/external delivery, paper/live/account action, or owner approval inference

### `archive_delete_apply.py`

Status: exact-approval-only archive delete apply helper.

Deletes only readiness-plan rows classified as approved move-only archive outputs after path containment, SHA-256, original-path derivation, and restore-drill hash checks pass. It is scoped to `core_folder_flattening_archive` and `tmp_markdown_sidecar_archive` rows from `tmp/archive-delete-readiness-plan.json`.

Run dry-run:
```bash
python scripts/archive_delete_apply.py --write --validate
```

Run apply only after exact owner approval:
```bash
python scripts/archive_delete_apply.py --apply --write --validate --approval-reference "<exact owner approval>"
```

Writes:
- `tmp/archive-delete-apply-report.json`

Boundary:
- deletes approved archived copies only
- no active live files, manual-review archive files, retained proof archives, config/auth/runtime files, canonical notes, portfolio/canon mutation, customer/external delivery, paper/live/account action, or owner approval inference

### `archive_manual_delete_review.py`

Status: report-only manual archive deletion decision packet.

Classifies remaining archived files after the restore-proof archive-delete pass into generated-residue delete candidates, historical business/archive decision candidates, binary research deliverables, continuity/memory reconciliation candidates, retained finance/SQL proof, and live-referenced blockers.

Run:
```bash
python scripts/archive_manual_delete_review.py
```

Writes:
- `tmp/archive-manual-delete-review.json`

Boundary:
- no delete authority
- live references must be retargeted or explicitly accepted before deletion
- historical/business, binary deliverable, and continuity archive deletion require human decision, not just technical cleanup

### `full_archive_delete_apply.py`

Status: exact-approval-only full archive delete helper.

Deletes every file under `09. Archive/` after a restore-drill hash check, then writes `state/archive-deletion-tombstone.json` so deleted archive provenance remains queryable without retaining the archived copies.

Run dry-run:
```bash
python scripts/full_archive_delete_apply.py --write --validate
```

Run apply only after exact owner approval:
```bash
python scripts/full_archive_delete_apply.py --apply --write --validate --approval-reference "<exact owner approval>"
```

Writes:
- `tmp/full-archive-delete-apply-report.json`
- `state/archive-deletion-tombstone.json` on apply

Boundary:
- only files inside `09. Archive/`
- no active live-file delete, canonical-note/portfolio mutation, config/auth/runtime change, customer/external delivery, paper/live/account action, or owner approval inference

### `finance_intelligence_state.py`

Status: unified review-only ticker front door for the SQL-canon guard/current-state -> finance_intelligence_state -> WF84 data plane -> WF85 full-answer/card route, with source-open fallback when guard or freshness proof is stale.

Builds `tmp/finance-intelligence-state.sqlite` from guarded SQL-canon current-state, the durable universe registry, WF77 coverage registry, ticker cards, bounded WF72 support/cache entry-stop references, WF84 data-plane proof, WF85 full-answer/card proof, and router QA proof. It emits compact JSON packets for routine routing/status/proof questions so main-session answers start with one envelope: validate SQL-canon first, use WF85 full-answer/card when WF84/WF85 and freshness/source guards are clean, use WF84 for normalized read-only decision joins, and source-open exact owner notes/artifacts before material claims when stale or blocked. WF77/WF78 are feeders and repair lanes; WF72 is support/index/cache infrastructure, not the finance-answer front door.

Run:
```bash
python scripts/finance_intelligence_state.py build --pretty
python scripts/finance_intelligence_state.py validate --pretty
python scripts/finance_intelligence_state.py ticker ETN --pretty
python scripts/finance_intelligence_state.py preopen --limit 10 --pretty
python scripts/finance_intelligence_state.py stale-tickers --limit 10 --pretty
python scripts/finance_intelligence_state.py pending-approvals --pretty
python scripts/finance_intelligence_state.py validator-status --pretty
python scripts/finance_intelligence_state.py source-proof VRT --pretty
python scripts/finance_intelligence_state.py entry-stop-refs --limit 42 --pretty
python scripts/finance_intelligence_state.py action-queue --limit 10 --pretty
python scripts/finance_intelligence_state.py phase3-qc --pretty
python scripts/finance_intelligence_state.py pilot-fixtures --pretty
python scripts/finance_intelligence_state.py live-pilot --pretty
python scripts/finance_intelligence_state.py paper-positions --pretty
```

Writes:
- `tmp/finance-intelligence-state.sqlite`
- `tmp/finance-intelligence-state-validation.json`
- `tmp/finance-intelligence-state-ticker-packet.json`
- `tmp/finance-intelligence-state-preopen-packet.json`
- `tmp/finance-intelligence-state-stale-tickers.json`
- `tmp/finance-intelligence-state-pending-approvals.json`
- `tmp/finance-intelligence-state-validator-status.json`
- `tmp/finance-intelligence-state-source-proof.json`
- `tmp/finance-intelligence-state-entry-stop-refs.json`
- `tmp/finance-intelligence-state-action-queue.json`
- `tmp/finance-intelligence-state-phase3-qc.json`
- `tmp/finance-intelligence-state-pilot-fixtures.json`
- `tmp/finance-intelligence-state-live-pilot.json`
- `tmp/finance-intelligence-state-paper-positions.json`

Boundary:
- read-only routing/current-state/query support
- review-monitor rows are thin/on-demand scaleout proof rows only and remain below the WF84/WF85 decision/full-answer route
- live pilot rows, when present, are isolated SQL/query rows only and remain excluded from production ticker cards/current 42 answers
- SQL and JSON packets are not canon, approval, apply authority, sizing/cash/risk-rule authority, or paper/live execution authority
- material finance, readiness, recommendation, or authority claims still require opening the listed exact source artifacts or canonical owner notes
- no retail/customer SQL-first activation, destructive archive/delete, `tmp` promotion, canon/portfolio mutation, owner approval inference, brokerage/account action, paper/live order, or money movement

### `cache_dependency_manifest.py`

Status: review-only dependency guard for the owner-truth plus WF72 support/cache -> finance-state -> WF84 -> WF85 cache chain.

Builds `tmp/cache-dependency-manifest.json` with source hashes, cache paths, affected tickers, and stale-read policy. Use it after entry-band/cache/front-door changes and after bounded band applies. If it reports `stale`, generated WF85 answers must not be treated as current for affected tickers; use source-open fallback and refresh the cache chain.

Run:
```bash
python scripts/cache_dependency_manifest.py --write --validate
python scripts/cache_dependency_manifest.py --tickers ETN,VRT,GS --write --validate --pretty
```

Boundary:
- proof/guard surface only
- no canon/portfolio mutation, owner approval inference, paper/live order, brokerage/account action, cash/sizing/risk-rule change, or money movement

### `wf78_pilot_contract_gate.py`

Status: WF78 Phase 0/1 review-only baseline-freeze and pilot-contract gate.

Freezes the current 42-ticker production baseline and emits/validates the pilot contract before any broader 100-name or scaleout rows are added. It reuses the existing WF78 validators and fails closed if production 42 quality, source-open boundaries, authority flags, fixture limits, or pilot/production separation are not clean.

Run:
```bash
python scripts/wf78_pilot_contract_gate.py --write --pretty
```

Writes:
- `tmp/wf78-phase0-baseline-freeze.json`
- `tmp/wf78-phase1-pilot-contract.json`
- `tmp/wf78-phase1-pilot-contract-validation.json`

Boundary:
- review/proof gate only
- no broad ticker import, no production answer-path overwrite, no database path migration, no `tmp` promotion, no full SQL-canon migration, no canon/portfolio/sizing/cash/risk-rule mutation, no owner approval inference, no paper submit/cancel/sell, no live brokerage/account action, and no money movement
- next allowed step after green validation is provider telemetry/runtime budget proof over fixture rows before any live 25/100+ ticker pilot expansion

### `wf78_pilot_provider_runtime_probe.py`

Status: WF78 Phase 4 Part 1 review-only provider/runtime and on-demand fixture-card proof gate.

Probes the 11 lower-tier pilot fixture rows through a narrow Yahoo chart endpoint with retry/backoff/circuit-breaker telemetry, then builds formal on-demand fixture cards for a small sample in an isolated pilot output directory. This proves provider runtime behavior and lower-tier card generation without importing pilot rows into the current 42-ticker production answer path.

Run:
```bash
python scripts/wf78_pilot_provider_runtime_probe.py --pretty
```

Writes:
- `tmp/wf78-pilot-provider-runtime-proof.json`
- `tmp/wf78-pilot-on-demand-card-proof.json`
- `tmp/wf78-pilot-on-demand-card-build-summary.json`
- `tmp/wf78-pilot-on-demand-cards/*.current.json`

Boundary:
- review/proof gate only
- fixture-only provider telemetry; material finance claims still require source-open proof
- on-demand cards are lower-tier review artifacts and stale/missing evidence blocks actionability
- no broad ticker import, no production answer-path overwrite, no SQL-canon expansion, no database path migration, no `tmp` promotion, no canon/portfolio/sizing/cash/risk-rule mutation, no approval inference, no paper/live/brokerage/account action, and no money movement

### `wf78_live_pilot_preflight.py`

Status: WF78 live 25-name pilot proposal/preflight packet.

Builds a review-only preflight packet for the next possible WF78 live pilot. It proposes 25 candidate symbols, runtime/provider limits, SQL row/card behavior, A/B regression gates, rollback/no-overwrite requirements, and stop lines. It does not import those rows into the universe registry or production answer path.

Run:
```bash
python scripts/wf78_live_pilot_preflight.py --pretty
```

Writes:
- `tmp/wf78-live-25-pilot-preflight.json`
- `tmp/wf78-live-25-pilot-preflight.md`

Boundary:
- proposal/preflight only
- no live pilot import from this packet alone
- no broad ticker import, no production answer-path overwrite, no SQL-canon expansion, no database path migration, no `tmp` promotion, no canon/portfolio/sizing/cash/risk-rule mutation, no approval inference, no paper/live/brokerage/account action, and no money movement

### `wf78_live_pilot_import_gate.py`

Status: WF78 isolated 25-name live-pilot import gate.

Creates timestamped backups, probes all 25 approved live-pilot candidates, writes isolated `live_pilot_*` SQL tables/views inside `tmp/finance-intelligence-state.sqlite`, and emits a compact live-pilot packet. It preserves the production 42 answer path and requires full regression after the isolated pilot import. Mutation requires explicit `--apply`; running without it exits blocked.

Run:
```bash
python scripts/wf78_live_pilot_import_gate.py --apply --pretty
python scripts/finance_intelligence_state.py live-pilot --pretty
```

Writes:
- `tmp/wf78-live-25-pilot-import-gate.json`
- `tmp/wf78-live-25-pilot-import-gate.md`
- `tmp/finance-intelligence-state-live-pilot.json`
- backup manifest under `backups/wf78-live-pilot-import/<run-id>/manifest.json`

Boundary:
- isolated pilot SQL import only
- no production answer-path overwrite, no production ticker-card registry write, no SQL-canon/canon-cache write, no DB path migration, no `tmp` promotion, no canon/portfolio/sizing/cash/risk-rule mutation, no owner approval inference, no paper/live/brokerage/account action, and no money movement

### `wf78_100_ticker_import_gate.py`

Status: WF78 guarded review-only 100-ticker monitor import gate.

Creates timestamped backups, probes the exact 58-name review-monitor set, converts any existing pilot fixture rows into `review_100_monitor` rows instead of duplicating them, writes the durable universe registry to exactly 100 active rows, and runs post-import validators. Production answer-path rows remain 42 and review-monitor rows remain Tier C, non-decision-grade, source-open-required, thin metadata only.

Run:
```bash
python scripts/wf78_100_ticker_import_gate.py --apply --owner-approval-reference "<exact owner approval text>" --pretty
```

Writes:
- `data/finance/universe-v1.json`
- `tmp/wf78-100-ticker-import-gate.json`
- `tmp/wf78-100-ticker-import-gate.md`
- `tmp/wf78-100-ticker-provider-runtime-proof.json`
- backup manifest under `backups/wf78-100-review-monitor-import/<run-id>/manifest.json`

Boundary:
- review-monitor universe metadata import only
- no production answer-path overwrite, no production ticker-card registry write, no SQL-canon/canon-cache expansion, no customer/retail output, no canon/portfolio/sizing/cash/risk-rule mutation, no owner approval inference for capital action, no paper/live/brokerage/account action, and no money movement

### `alpaca_paper_position_sql_refresh.py`

Status: WF63/WF67 GET-only paper-position SQL current-state refresh.

Reads Alpaca paper account, positions, and recent orders using GET only, writes the sibling review-only DB `tmp/wf67-paper-position-state.sqlite`, emits the compact paper-position query packet, and refreshes legacy compatibility exports. This is the WF78 Phase 4 Part 1 stale paper-position repair path.

Blocked refresh behavior:
- blocked runs append a blocked freshness/run row instead of deleting the last successful snapshot
- `current_paper_positions` resolves to the latest successful `status='ok'` snapshot
- packets expose `latest_refresh`, `latest_successful_snapshot_at_utc`, and `last_known_positions_status` so stale-but-known positions are explicit

Run:
```bash
python scripts/alpaca_paper_position_sql_refresh.py refresh --create-kill-switch --expires-minutes 90 --pretty
python scripts/alpaca_paper_position_sql_refresh.py validate --pretty
python scripts/finance_intelligence_state.py paper-positions --pretty
```

Writes:
- `tmp/wf67-paper-position-state.sqlite`
- `tmp/finance-intelligence-state-paper-positions.json`
- `tmp/alpaca-paper-readiness/current-paper-holdings-readonly.json`
- `tmp/alpaca-paper-readiness/current-paper-holdings-readonly.md`

SQL surface:
- `paper_account_snapshot`
- `paper_position_snapshot`
- `paper_position_freshness`
- `current_paper_positions`

Automation:
- cron job `5e33df77-ebc5-4b09-84a6-feaa5832142c`, `Finance - WF63/WF67 Paper Position Read-Only Refresh`, runs weekdays at 13:50 America/Phoenix.

Boundary:
- GET-only paper endpoint refresh; no paper submit/cancel/sell, no live endpoint or live credentials, no brokerage/account mutation, no money movement, no owner approval inference, no canon/portfolio/sizing/cash/risk-rule mutation
- `tmp/wf67-paper-position-state.sqlite` is review/current-state only; JSON/Markdown holdings files are exports, not truth owners
- `tmp/veritas-canon-cache.sqlite` is not used for paper positions, and `tmp/veritas-artifact-index.sqlite` indexes proof only rather than owning state

### `runtime_expansion_pilot.py`

Status: approved local-only WF68/WF72 report-only runtime expansion pilot runner.

Runs the finance-stack snapshot refresh, checks WF68 runtime/advisor validation artifacts, compares a compact state against the prior run, and writes `tmp/runtime-expansion-pilot-status.json/.md` plus compact state history under `data/state-history/`. The paired cron job is main-session only and reports only material changes or validation blockers.

Run:
```bash
python scripts/runtime_expansion_pilot.py --write --validate
```

Boundary:
- local-only report/runtime handoff support
- no external channels, config/auth/network exposure, canon/portfolio/sizing/cash/risk-rule mutation, live trading/account/money movement, paper execution, owner-approval inference, probability/win-rate claims, Gateway `/v1`, or native Codex migration
- material-change handoff is review-only; any paper order still requires exact WF67 approval path

### `wf67_order_card_request_generator.py`

Status: main-session approval-ready order-card to WF67 request generator.

Converts a `main_session_wf67_order_decision_card` artifact into a WF67 paper-trade request artifact. This is the direct main-session path for turning a fresh capital/advisor alert into exact proposed order terms for Randall approval.

Run:
```bash
python scripts/wf67_order_card_request_generator.py --card tmp/alpaca-paper-readiness/order-card.<id>.json
python scripts/test_wf67_order_card_request_generator.py
python scripts/test_alpaca_paper_trade_executor.py
```

Boundary:
- generator only; no Alpaca call, no kill switch, no submit/cancel/sell
- pending approval request artifacts are valid for review/proof but are blocked from `--execute` by `alpaca_paper_trade_executor.py`
- execution requires exact Randall approval metadata, a fresh short-lived kill switch, rerun guard validation, and WF67 wrapper execution; live trading remains blocked


### Runtime/report Markdown policy

Routine runtime and cleanup producers are JSON-first. Use `--write-md` only when a legacy human-readable sidecar is explicitly needed for audit, durable closeout, or compatibility. Randall-facing summaries should be delivered in webchat; `tmp/*.md` is not a normal user-facing surface.

Current JSON-first/Markdown-opt-in producers include:
- `archive_suggester.py --write-md`
- `automation_health_dashboard.py --write-md`
- `db_lifecycle_manifest.py --write-md`
- `major_closeout_delta.py --write-md`
- `tool_bloat_reduction_guard.py --write-md`
- `openclaw_cache_efficiency_scorecard.py --write-md`

### `db_lifecycle_manifest.py`

Status: read-only SQLite lifecycle and archive-decision manifest

Classifies active `tmp/**/*.sqlite`, `state/**/*.sqlite`, and previously archived DB lifecycle files as `live`, `derived`, `snapshot`, `rollback`, `drill`, `test`, or `archived`. It hashes each database, opens SQLite read-only for integrity/schema/row-count metadata, checks sidecars, separates operational references from proof/audit/history references, and prepares an owner-decision list.

Run:
```bash
python scripts/db_lifecycle_manifest.py --write --write-md --validate
python scripts/db_lifecycle_archive_apply.py --dry-run --write --validate
python scripts/db_lifecycle_archive_apply.py --write --validate
```

Writes:
- `tmp/db-lifecycle-manifest.json`
- `tmp/db-lifecycle-manifest.md` when `--write-md` is supplied
- `tmp/db-lifecycle-archive-apply-report.json` from the apply helper

Notes:
- read-only only; it never moves, deletes, rewrites, checkpoints, vacuums, or mutates SQL
- `apply_allowed=false`, `archive_apply_allowed=false`, and `delete_apply_allowed=false` are hard boundaries
- live/derived databases are protected; archive-ready candidates still require explicit owner approval before any move
- `finance-stack-snapshot.sqlite` is a labeled `snapshot` / `conditional_keep` surface with a regenerate-on-demand command, not a live authority database
- `db_lifecycle_archive_apply.py` is the bounded owner-approved apply helper for the manifest's `archive_ready` DBs and their WAL/SHM sidecars only; it verifies hashes after move and writes a closeout report
- deletion is not a v1 action; archive first with hashes/manifests, then consider deletion only after a later retention proof

### `sql_latency_benchmark.py`

Status: manual read-only SQLite latency benchmark

Runs representative read-only SQL queries against the current workspace SQLite engines and writes a repeatable benchmark report. This promotes the earlier tmp-only latency proof into an official manual diagnostic. It is for evidence and regression checks only, not tuning by default.

Run:
```bash
python scripts/sql_latency_benchmark.py
python scripts/sql_latency_benchmark.py --json --validate
```

Writes:
- `tmp/sql-latency-benchmark-current.json`

Notes:
- opens databases read-only with `mode=ro`
- no DB mutation, canon/portfolio mutation, paper/live/account action, or authority expansion
- if latency ever becomes a real problem, the likely fix is batching/persistent process orchestration, not SQL/index tuning

### `archive_suggester.py`

Status: read-only archive/cleanup suggestion report

Scans for conservative cleanup candidates without moving, deleting, or rewriting anything. It is a pre-automation guardrail: suggestions require owner approval and are not an apply plan.

Run:
```bash
python scripts/archive_suggester.py
python scripts/archive_suggester.py --include-tmp-md
```

Writes:
- `tmp/archive-suggestions.json`

Notes:
- `apply_allowed=false` and `moves_performed=false` are hard boundaries
- Routine tmp Markdown sidecars are not user-facing; prefer JSON proof plus webchat summaries unless a durable/audit/decision surface requires Markdown
- protected surfaces include canonical finance notes, active workflow surfaces, `data/`, memory, scripts, and skills
- current v1 focuses on executable helpers in `tmp/`, runtime cache candidates, and undocumented `backups/` only when the approved rollback/provenance README contract is missing
- with `--include-tmp-md`, the tmp Markdown scan is no longer capped at the first 50 files; reviewed hash-matched sidecars from `tmp/wf72-active-tmp-md-cleanup-2026-05-25.json` are suppressed, and changed/new reports surface again
- use the report to decide what to promote/archive manually; do not treat it as auto-archive authority

### `cyber_security_daily_audit.py`

Status: bounded read-only security audit

Runs the current daily cyber-security / workspace-hardening audit for the local OpenClaw host. It combines `openclaw security audit --json`, a bounded `openclaw doctor` pass, skills inventory, workspace boundary/governance validators, and Windows firewall/antivirus checks. It writes report artifacts only under `tmp/`; it does not mutate config, notes, auth, or packages.

Run:
```bash
python scripts/cyber_security_daily_audit.py
```

Writes:
- `tmp/cyber-security-daily-audit.json`
- `tmp/cyber-security-daily-audit.md`

Notes:
- default posture is read-only / review-only
- `status=warning` is expected whenever real drift exists; do not rerun just to hide warning-grade truth
- `stop_line=true` is reserved for critical conditions where the audit should force human review
- `openclaw doctor` is treated as advisory because the current install can emit useful warnings and still hang or error during reinstall/runtime drift

### `openclaw_cache_efficiency_scorecard.py`

Status: bounded report-only OpenClaw cache/prompt efficiency scorecard.

Inspects workspace-owned bootstrap/prompt surfaces, workspace skill metadata volume, large `tmp/` artifacts, and optional transcript/session exports for oversized old tool results. It accepts OpenClaw/provider-style JSON exports or text logs with tool-result markers, then flags oversized tool outputs, repeated large file reads, and cache-friendly follow-up behavior. It is meant to diagnose prompt-prefix stability, bootstrap cap pressure, and tool-result bloat without touching config, auth, runtime, transcripts, or canonical notes.

Run:
```bash
python scripts/openclaw_cache_efficiency_scorecard.py --write
python scripts/openclaw_cache_efficiency_scorecard.py --write --transcript path\to\session.json
python scripts/openclaw_cache_efficiency_scorecard.py --write --transcript path\to\session-1.json --transcript path\to\session-2.json
python scripts/openclaw_cache_efficiency_scorecard.py --write --write-redacted-tool-telemetry --latest-main-session
python scripts/test_openclaw_cache_efficiency_scorecard.py
```

If no transcript export is available, use the test command as the synthetic fixture smoke path; it exercises an OpenClaw-shaped repeated-read transcript without requiring real session files. `--latest-main-session` performs read-only discovery of the newest local main-session JSONL transcript and should be used only for local diagnostics where transcript access is appropriate.

Writes with `--write` only:
- `tmp/openclaw-cache-efficiency-scorecard.json`
- with `--write-redacted-tool-telemetry`: `tmp/redacted-tool-result-telemetry.json`

Boundary:
- report-only / review-only cache and prompt efficiency support
- no OpenClaw config/auth/channel/service/runtime mutation
- no transcript rewrite, no canon mutation, no approval inference, no finance/paper/live execution authority


### `cron_authority_matrix_validator.py` and `bounded_auto_archive.py`

Status: WF76 cron-governance support tools.

`cron_authority_matrix_validator.py` validates `tmp/cron-automation-authority-contract.json` and fails closed if global hard boundaries or T0-T5/TX tier definitions drift. `bounded_auto_archive.py` is a policy-compliant archive-only helper; it moves nothing unless an upstream suggestion is explicitly apply-eligible, owner approval is no longer required, references are zero, destination is inside the approved archive roots, and kind is allowlisted.

Run:
```bash
python scripts/cron_authority_matrix_validator.py --write
python scripts/bounded_auto_archive.py
python scripts/bounded_auto_archive.py --validate-last-report
```

Boundary:
- no deletes
- no config/auth/channel/service/runtime mutation
- no portfolio/canon/trade/account/paper/live authority
- archive apply requires the bounded auto-archive policy and main-session reporting

## Supported active tooling

### `intraday_alert_packet_validator.py`

Status: WF68 Phase 0 alert-packet contract validator; review-only and no-authority

Validates intraday alert packet artifacts before any scheduler, delivery, broker, or channel path is allowed to depend on them. It rejects missing source timestamp/freshness, stale/ambiguous represented data, missing owner-surface references, missing authority blocks, and any true trade/account/paper/canonical/portfolio/owner-approval/sizing/sleeve/cash/risk-rule authority flag.

Run:
```bash
python scripts/intraday_alert_packet_validator.py --write
python scripts/intraday_alert_packet_validator.py tmp/intraday-alerts/invalid-authority-fixture.sample.json
python scripts/test_intraday_alert_packet_validator.py
```

Writes:
- `tmp/intraday-alerts/alert-packet-validation.json`
- optional caller-selected validation report path

Fixture/schema:
- `tmp/intraday-alerts/alert-packet.schema.json`
- `tmp/intraday-alerts/forced-alert-fixture.etn.json`
- `tmp/intraday-alerts/invalid-authority-fixture.sample.json` intentionally fails validation and exists only as a regression/proof fixture.

Boundary:
- alert packets are review-only decision-support objects
- no live/paper order, broker/account mutation, cron/channel/config change, canonical note mutation, portfolio mutation, owner-approval inference, sizing/sleeve/cash/risk-rule change, or execution entitlement is authorized by packet creation or validator success

### `intraday_quote_snapshot_proof.py`

Status: WF68 Phase 1 read-only market-data proof; review-only and no-authority

Proves or fails closed on a sanitized Alpaca market-data quote/snapshot path using paper-named credentials and GET-only requests. It writes only provider, endpoint classification, symbol, source timestamp, received timestamp, legacy freshness status, calendar-aware freshness status, price/bid/ask, redaction flags, and hard-false authority flags. `market_calendar_freshness.py` classifies quotes as `fresh_intraday`, `current_last_completed_session`, `market_closed_expected_stale`, `stale_unexpected`, or `provider_missing`, so weekends/holidays/closed-market windows do not create false provider-stale signals. It does not persist secrets, raw headers, raw response bodies, or brokerage/account data. Default symbols are now the first 10 tracked universe symbols plus ETN plus the current WF78 Tier A/capital-review tickers, so VRT/GOOG/NVDA-style capital-review candidates cannot silently fall out of quote proof.

Run:
```bash
python scripts/intraday_quote_snapshot_proof.py
python scripts/intraday_quote_snapshot_proof.py --symbols ETN JPM GOOG MSFT LMT BRK.B XOM NVDA AMZN BKNG
```

Writes:
- `tmp/intraday-alerts/quote-snapshot-proof.json`
- `tmp/intraday-alerts/quote-snapshot-proof.md`
- `tmp/intraday-alerts/quote-snapshot-proof-validation.json`

Boundary:
- quote snapshots are alert-input proof only
- stale or missing quote/source-timestamp states must degrade trigger behavior instead of firing false-green alerts
- no live/paper order, broker/account mutation, cron/channel/config change, canonical note mutation, portfolio mutation, owner-approval inference, sizing/sleeve/cash/risk-rule change, or execution entitlement is authorized by this proof

### `intraday_alert_trigger_engine.py`

Status: WF68 Phase 2 thin trigger engine; review-only and no-authority

Consumes the Phase 1 sanitized quote snapshot proof, `tmp/portfolio-config.json` bands/stops, and sanitized WF67 paper-result state. It tracks Core 10 plus active paper-position symbols, emits alert packets only for fresh/current quote evidence with age <= 1800 seconds, and degrades `current_but_not_intraday_fresh`, stale, missing, partial, or ambiguous quote evidence to no-fire/monitor-only rows.

Run:
```bash
python scripts/intraday_alert_trigger_engine.py
python scripts/test_intraday_alert_trigger_engine.py
```

Writes:
- `tmp/intraday-alerts/current-alerts.json`
- `tmp/intraday-alerts/current-alerts.md`
- `tmp/intraday-alerts/trigger-engine-validation.json`

Boundary:
- output is alert packets and no-fire summaries only
- no live/paper order, broker/account mutation, cron/channel/config change, canonical note mutation, portfolio mutation, owner-approval inference, sizing/sleeve/cash/risk-rule change, or execution entitlement is authorized by trigger generation or validation success


### `intraday_alert_main_handoff.py`, `intraday_alert_advisor_enricher.py`, and `intraday_alert_outcome_link.py`

Status: WF68 Phases 3-5 artifact-proof advisor handoff; review-only and no-authority

These scripts convert validated intraday alert packets into the attended OpenClaw/main-session artifact surface, enrich actionable alerts with WF58 recommendation context and WF66 official-source/why-stack context, then create a proposal-only WF55/Call Log outcome-link artifact. They do not inject actual runtime events, configure cron/channels, mutate Call Log/state history/canonical notes/portfolio state, or perform paper/live order/account actions.

Run:
```bash
python scripts/intraday_alert_main_handoff.py --input tmp\intraday-alerts\current-alerts.json
python scripts/intraday_alert_main_handoff.py --input tmp\intraday-alerts\forced-alert-fixture.etn.json --output-json tmp\intraday-alerts\forced-main-session-handoff.json --output-md tmp\intraday-alerts\forced-main-session-handoff.md --validation-output tmp\intraday-alerts\forced-main-session-handoff-validation.json
python scripts/intraday_alert_advisor_enricher.py --handoff tmp\intraday-alerts\forced-main-session-handoff.json
python scripts/intraday_alert_outcome_link.py --write
python scripts/test_intraday_alert_main_handoff.py
python scripts/test_intraday_alert_advisor_enricher.py
python scripts/test_intraday_alert_outcome_link.py
```

Writes:
- `tmp/intraday-alerts/main-session-handoff.json/.md`
- `tmp/intraday-alerts/forced-main-session-handoff.json/.md`
- `tmp/intraday-alerts/advisor-alert-packet.json/.md`
- `tmp/intraday-alerts/advisor-alert-outcome-link.json/.md`
- associated `*-validation.json` proof artifacts

Boundary:
- artifact-proof only until explicit owner approval for bounded runtime/systemEvent wiring
- outcome-link output is proposal-only; it does not append `data/state-history/outcome-updates-v1.jsonl` or edit `04. Research/Call Log.md`
- no live/paper order, broker/account mutation, cron/channel/config change, canonical note mutation, portfolio mutation, owner-approval inference, sizing/sleeve/cash/risk-rule change, execution entitlement, or probability/modeling claim is authorized

### `intraday_alert_runtime_handoff_validator.py` and `wf68_runtime_wiring_plan_validator.py`

Status: WF68 Phase 7 runtime handoff/wiring design validators; proposal-only and no-authority

`intraday_alert_runtime_handoff_validator.py` validates the high-level two-job handoff design. `wf68_runtime_wiring_plan_validator.py` validates the phased runtime wiring preview, including exact in-place cron update previews for the existing intraday watcher pair, rollback/disable requirements, pre-enable proof gates, `NO_REPLY` / `ALERT_READY` behavior, stale/current-but-not-intraday-fresh no-fire downgrade, and hard-false authority.

Run:
```bash
python scripts/intraday_alert_runtime_handoff_validator.py --write
python scripts/wf68_runtime_wiring_plan_validator.py --write
```

Writes:
- `tmp/intraday-alerts/runtime-handoff-design-validation.json`
- `tmp/intraday-alerts/runtime-wiring-phase-plan-validation.json`

Boundary:
- these validators and design artifacts do not create, edit, enable, disable, or delete cron jobs
- runtime wiring remains blocked until explicit owner approval of the exact update patches
- no live/paper order, broker/account mutation, channel/config/auth/runtime change, canonical/portfolio/Call Log mutation, state-history append, owner-approval inference, or probability/modeling claim is authorized

### `wf68_intraday_alert_producer.py`

Status: WF68 enabled runtime producer wrapper; review-only and no-authority

Runs the approved WF68 producer chain deterministically for the enabled intraday cron job. It refreshes the sanitized quote proof, trigger engine output, main-session handoff artifact, and runtime handoff status; it runs advisor/outcome-link steps only when an actionable handoff exists. It writes proof only and does not message Randall directly.

Run:
```bash
python scripts/wf68_intraday_alert_producer.py
```

Writes:
- `tmp/intraday-alerts/runtime-handoff-status.json`
- `tmp/intraday-alerts/runtime-handoff-status.md`
- refreshed WF68 input/output artifacts under `tmp/intraday-alerts/`

Enabled cron pair:
- Producer: `a9f14c77-9223-4760-9e8e-e83417708b38`, `Finance - WF68 Intraday Alert Producer`, isolated, `5,35 6-12 * * 1-5` America/Phoenix, delivery none.
- Main-session handoff: `a6b30d94-629f-44f6-b9c7-e3bd16f25a44`, `Finance - Main Session WF68 Intraday Alert Handoff`, main `systemEvent`, `8,38 6-12 * * 1-5` America/Phoenix.

Post-enable proof:
- `tmp/intraday-alerts/runtime-post-enable-validation.json`
- `tmp/intraday-alerts/runtime-post-enable-validation.md`

Boundary:
- no direct user/channel delivery from the isolated producer
- no live/paper order, broker/account mutation, money movement, live endpoint/credential use, cron/channel/config/auth mutation, canonical/portfolio/Call Log/state-history mutation, owner-approval inference, or probability/modeling claim
- stale, missing, ambiguous, or `current_but_not_intraday_fresh` quote evidence must downgrade to no-fire/monitor-only rather than triggering actionable alerts

### `wf68_telegram_notifier.py`

Status: WF68 Telegram shadow notifier; delivery-only and no execution authority

Reads the WF68 runtime handoff and delivery-router proof, sends Telegram only for fresh `EXECUTION_PACKET_READY` packets or blocker visibility, and writes notifier proof. It blocks stale packets by default and dedupes daily ticker sets. Replies are operating cues only: `REVIEW` means inspect the packet, and `PREPARE` means prepare a WF67 paper request artifact. `APPROVE` is not active in shadow mode.

Run:
```bash
python scripts/wf68_telegram_notifier.py
python scripts/wf68_telegram_notifier.py --send --target 8650152206 --max-age-minutes 45
python scripts/wf68_telegram_notifier.py --delivery-test --send --target 8650152206
python scripts/test_wf68_telegram_notifier.py
```

Writes:
- `tmp/intraday-alerts/telegram-notifier-status.json`
- `tmp/intraday-alerts/telegram-notifier-status.md`
- `tmp/intraday-alerts/telegram-notifier-state.json`

Enabled cron:
- Telegram shadow notifier: `67c3eeaf-4040-4be4-a2b3-7a6dd3280baf`, `Finance - WF68 Telegram Shadow Alert Notifier`, isolated, `10,40 6-12 * * 1-5` America/Phoenix, delivery none. Payload runs `python scripts\wf68_telegram_notifier.py --send --target 8650152206 --max-age-minutes 45` and then refreshes the cron operator ledger.

Proof:
- Targeted tests pass with fresh dry-run, stale-block, and `NO_REPLY` cases.
- Manual cron run `manual:67c3eeaf-4040-4be4-a2b3-7a6dd3280baf:1780375166598:1` completed ok with notifier status `BLOCKED`, `sent_count=0`, and blocker `artifact_stale:545.2min_gt_45min`, proving stale June 1 trade-ready packets were not sent.
- On 2026-06-01 at 22:16 America/Phoenix, delivery-test mode sent one clearly labeled Telegram transport test to `8650152206`; proof: `tmp/intraday-alerts/telegram-notifier-delivery-test-status.json`, status `SENT`, `sent_count=1`, OpenClaw message ID `97`. A normal market-alert send immediately afterward still blocked the stale packet with `sent_count=0`.

Boundary:
- Telegram delivery to Randall only
- no live/paper order submission or cancellation, broker/account mutation, money movement, live endpoint/credential use, canonical/portfolio/sizing/sleeve/cash/risk-rule mutation, owner approval inference, Discord/Signal/email expansion, or paper execution from Telegram
- paper execution remains WF67-only after exact request artifact, fresh kill switch, guard validation, paper wrapper, redacted audit, and Randall exact approval

### `wf68_telegram_reply_bridge.py`

Status: WF68 Telegram shadow reply parser and main-session handoff proof; no execution authority

Reads Randall's Telegram direct-session transcript, recognizes only `ACK`, `REVIEW`, `PREPARE`, and blocked `APPROVE`, writes a reply bridge status artifact, and supports dedupe state after an authorized main-session wake succeeds.

Run:
```bash
python scripts/wf68_telegram_reply_bridge.py
python scripts/wf68_telegram_reply_bridge.py --force
python scripts/wf68_telegram_reply_bridge.py --force --mark-processed
python scripts/test_wf68_telegram_reply_bridge.py
```

Writes:
- `tmp/intraday-alerts/telegram-reply-bridge-status.json`
- `tmp/intraday-alerts/telegram-reply-bridge-status.md`
- `tmp/intraday-alerts/telegram-reply-bridge-state.json`

Proof:
- On 2026-06-01 at 22:19 America/Phoenix, Telegram inbound reply `Ack wf68 delivery test 97` arrived in session `agent:main:telegram:direct:8650152206`.
- The bridge parsed it as `ACK`, workflow `WF68`, message ref `97`, not a ticker/action command.
- Main-session wake via the authorized OpenClaw cron tool returned `ok=true`; CLI cron-add from Python remains blocked by Gateway scope upgrade pending approval, so unattended CLI wake is not the active route.
- Processed-state proof shows row `a54804dc-e7d2-4d11-85fb-a30a4b2627fc` marked after external authorized wake; a later normal bridge run returned `NO_REPLY`, proving dedupe.

Boundary:
- reply bridge only
- `ACK` confirms delivery; `REVIEW` asks main session to inspect; `PREPARE` asks main session to consider WF67 request-artifact preparation after fresh proof
- `APPROVE` is blocked in Telegram shadow mode
- no WF67 request generation by this script, no paper/live order submission or cancellation, no broker/account mutation, no money movement, no canonical/portfolio/sizing/sleeve/cash/risk-rule mutation, and no owner approval inference

### `alpaca_paper_trade_executor.py` and `alpaca_paper_execution_guard_validator.py`

Status: WF67 paper-only wrapper + validator; scoped paper pilots active, not autonomous trading

`alpaca_paper_trade_executor.py` validates scoped paper submit/cancel request artifacts and defaults to dry-run. Actual paper submit/cancel requires `--execute`, an unexpired WF67 kill switch, exact paper endpoint, paper-specific credentials, a non-sample scoped request artifact, and a redacted audit event. It must not use live endpoints, live credentials, money movement, account settings, replace/close/liquidation paths, or inferred approval.

`alpaca_paper_execution_guard_validator.py` validates the paper-only submit/cancel authority artifact, request-contract scaffolds, wrapper presence/static gates, kill switch, WF63 read-only proof, audit log, dry-run result, and guard report. It performs no Alpaca API calls and does not submit, cancel, replace, close, liquidate, transfer, or mutate account state.

`alpaca_reviewed_packet_pilot_request.py` creates a WF67 paper-trade request artifact from the current reviewed capital-deployment recommendation packet. It is paper-only artifact preparation: no Alpaca API call, no owner approval inference, no trade/account authority, and no live execution. It requires the recommendation bundle and validator to be clean review-only surfaces, then creates a 1-share passive limit/day paper pilot request under the `$500` cap.

`alpaca_paper_pilot_reconciliation.py` is the post-pilot read-only reconciliation/report step. It fetches only the named paper order from the scoped cancel artifact, persists only redacted lifecycle fields, and verifies accepted/submitted/canceled/fill-zero/validator-clean proof.

`paper_pilot_status_surface.py` aggregates redacted WF67 reconciliation artifacts into `tmp/alpaca-paper-readiness/paper-pilot-status-surface.json` for dashboard/Command Center truth. It is read-only telemetry: paper simulation only, no live trading, no account action, no inferred owner approval, and no paper-to-live promotion.

`wf67_full_portfolio_scope_validator.py` validates the review-ready `$100k` full-portfolio/basket paper-scope scaffolding and tranche-0 dry-run basket request. It performs no Alpaca API calls and does not submit/cancel/replace/close/liquidate/transfer/mutate anything. It preserves the existing `$500 / 1-share` single-order pilot caps as the default path unless an explicit full-scope artifact is passed and validates cleanly; even then, current artifacts keep `ready_for_paper_execution=false` and require owner approval, fresh kill switch, and exact tranche/basket order terms.

WF78 Phase 4 Part 1 stale-state repair is implemented through `alpaca_paper_position_sql_refresh.py` and sibling review-only DB `tmp/wf67-paper-position-state.sqlite`. The SQL-first flow is: Alpaca GET-only paper account/positions/orders refresh -> `paper_account_snapshot`, `paper_position_snapshot`, and `paper_position_freshness` tables -> `current_paper_positions` view from latest successful snapshot -> compatibility `current-paper-holdings-readonly.json/.md` exports -> artifact-index incremental. The refresh must not submit/cancel/sell, use live endpoints/credentials, mutate account settings, infer owner approval, or promote paper state to live authority.

Run:
```bash
python scripts/alpaca_reviewed_packet_pilot_request.py
python scripts/alpaca_paper_trade_executor.py --trade-request tmp\alpaca-paper-readiness\paper-trade-request.wf67-reviewed-packet-001.json
python scripts/alpaca_paper_execution_guard_validator.py --write --trade-request tmp\alpaca-paper-readiness\paper-trade-request.wf67-reviewed-packet-001.json

python scripts/alpaca_paper_trade_executor.py --init-samples
python scripts/alpaca_paper_trade_executor.py --trade-request tmp\alpaca-paper-readiness\paper-trade-request.sample.json
python scripts/alpaca_paper_trade_executor.py --cancel-request tmp\alpaca-paper-readiness\paper-cancel-request.sample.json
python scripts/alpaca_paper_execution_guard_validator.py --write
python scripts/alpaca_paper_pilot_reconciliation.py
python scripts/paper_pilot_status_surface.py --write
python scripts/wf67_full_portfolio_scope_validator.py --write
```

Writes:
- `tmp/alpaca-paper-readiness/paper-execution-guard-validation.json`
- `tmp/alpaca-paper-readiness/paper-pilot-reconciliation.wf67-pilot-001.json`
- `tmp/alpaca-paper-readiness/paper-pilot-reconciliation.wf67-pilot-001.md`
- `tmp/alpaca-paper-readiness/paper-pilot-status-surface.json`
- `tmp/alpaca-paper-readiness/full-portfolio-scope-validation.json`
- `tmp/alpaca-paper-readiness/full-portfolio-scope-validation.md`

Notes:
- current WF67 validator/status-surface posture is `ok` only for exact scoped paper-pilot operation and monitoring; it is not autonomous trading approval
- non-executable sample artifacts are blocked from `--execute` by `sample_request_cannot_execute`
- required paper endpoint remains `https://paper-api.alpaca.markets`
- required credential names remain `ALPACA_PAPER_API_KEY_ID` and `ALPACA_PAPER_API_SECRET_KEY`
- live endpoint, live credentials, money movement, account mutation, replace/close/liquidation paths, and inferred approval remain blocked

### `research_intake_packet.py`

Status: bounded review-only prototype

Builds fail-closed intake packets from raw research-event input for the approved research-automation contract. The script is a packet-prep surface only: it may recommend routing, but it never authorizes canonical mutation.

Run:
```bash
python scripts/research_intake_packet.py --init-sample
python scripts/research_intake_packet.py --input tmp/research-automation/raw-events.json
```

Writes:
- `tmp/research-automation/raw-events.json` (sample input when `--init-sample` is used)
- `tmp/research-automation/intake-packets-<timestamp>.json`

Notes:
- the exact pre-packet input shape is documented in `06. Playbooks/Research Automation Raw Event Input Contract.md`
- parallel role lanes are deterministic contract lanes in this first version (`event_detector`, `materiality_scorer`, `thesis_drift_agent`, `evidence_qa_agent`, `routing_agent`)
- unresolved truths and fast-moving geopolitical items can stay open as verification objects instead of being forced into fake certainty
- `canonical_mutation_allowed` stays `false`
- validation failures force `stop_line_no_promotion`
- this is an intake/review object, not a verdict or auto-apply surface

### `canonical_freshness_patch.py`

Status: bounded review-only prototype

Builds narrow canonical freshness patch proposals from explicit candidate input. It does not apply patches. It exists to prepare human-review packets for mechanical/alignment freshness work only.

Run:
```bash
python scripts/canonical_freshness_patch.py --init-sample
python scripts/canonical_freshness_patch.py --input tmp/research-automation/raw-freshness-candidates.json
```

Writes:
- `tmp/research-automation/raw-freshness-candidates.json` (sample input when `--init-sample` is used)
- `tmp/research-automation/freshness-patch-candidates-<timestamp>.json`

Notes:
- `apply_allowed` stays `false`
- mechanical date / elapsed-event and post-catalyst status are the normal safe v1 classes
- cross-surface contradiction and thesis/posture change candidates are review-escalation or rejection cases, not auto-help surfaces
- this is a patch-proposal surface, not an apply surface

### `technical_refresh.py`

Status: live

Fetches closing prices and 20/50/200-day moving averages for tracked names, classifies posture, checks entry-band and stop status, and flags near-term earnings-blocked names.

Run:
```bash
python scripts/technical_refresh.py
```

Writes:
- `tmp/technical-refresh.json`

### `market_state_refresh.py`

Status: live

Fetches the core macro and market snapshot used by the operating stack, including SPX, VIX, Treasury context, DXY, energy, futures, sector snapshots, and actionable-name context. Supports partial-success reporting and freshness warnings.

Run:
```bash
python scripts/market_state_refresh.py
```

Writes:
- `tmp/market-state.json`

### `small_mid_cap_regime_feed.py`

Status: WF61 review-only v1

Builds the small/mid-cap, diversified fund, and commodity-probe regime feed. It compares IWM/SCHA/IJR/VB/AVUV/VBR/IJS, IJH/MDY/VO, SLV/GLD, PDBC/DBC, and USO/CPER/DBA/URA/COPX against SPY and QQQ with trailing relative strength, 20/50/200DMA posture, 52-week drawdown, liquidity warnings, ATR/volatility proxies, owner-gated next-review language, and the current-regime analog scenario panel when available.

Run:
```bash
python scripts/small_mid_cap_regime_feed.py
```

Writes:
- `tmp/small-mid-cap-regime-feed.json`

Notes:
- review-only evidence surface; all authority flags remain false
- scenario context is historical analog discipline only; it is not probability, score, ranking, sizing, approval, or execution authority

### `research_freshness_opportunity_review.py`

Status: WF60 review-only v1

Composes existing sector-expansion and ticker-monitoring outputs into one research freshness / opportunity review packet. It is a coordinator surface only: it does not refresh upstream data by itself unless the calling cron/run packet executes the upstream scripts first.

Run:
```bash
python scripts/research_freshness_opportunity_review.py --window post-close
```

Writes:
- `tmp/research-freshness-opportunity-review.json`

Notes:
- review-only evidence surface; all authority flags remain false
- degrades when upstream sector/ticker artifacts are stale, missing, or already degraded
- candidate queues are packet requests for Veritas/Randall review, not watchlist promotion or portfolio authority
- research cron should refresh and inspect `macro_judgment_draft.py --write --validate` before this packet so opportunity cues carry the same review-only macro posture used by the finance stack
- no canonical mutation, portfolio addition, sleeve creation, sizing/allocation recommendation, watchlist promotion, owner approval inference, trade execution, or account action
- tactical commodity probes require explicit liquidity, volatility, macro, correlation, and risk-budget review before any owner-gated proposal

### `policy_expectations_refresh.py`

Status: live first-version policy layer

Builds the dedicated policy-expectations artifact used to separate Fed-path evidence from general macro narrative. The first version still carries explicit manual dependencies for the current target range and next FOMC date, but it fetches live FedWatch-style futures expectations when available and writes honest warning states when it cannot.

Run:
```bash
python scripts/policy_expectations_refresh.py
```

Writes:
- `tmp/policy-expectations.json`

Notes:
- this is the first dedicated policy layer, not the finished automation state
- the current target range and next FOMC meeting date are still manually maintained in the script until the broader policy workflow is wired
- the meeting distribution is a single-step 25bp approximation from one 30-day Fed Funds futures contract, not a full multi-outcome FedWatch tree

### `credit_spread_refresh.py`

Status: live first-version credit layer

Builds the dedicated credit-spread artifact used to add credit-stress context to regime and deployment work. Primary sourcing uses FRED / ICE BofA OAS series for investment-grade and high-yield spreads. When direct coverage is incomplete, the script degrades honestly into partial status and uses HYG/JNK/LQD proxy behavior to preserve directional context.

Run:
```bash
python scripts/credit_spread_refresh.py
```

Writes:
- `tmp/credit-spreads.json`

Notes:
- direct ICE BofA OAS series can lag by a trading day in FRED
- first version uses heuristic stress-regime thresholds and proxy degradation logic rather than a full credit model
- downstream consumers should treat non-`ok` output as lower-confidence credit state

### `full_portfolio_view.py`

Status: live review-only machine report

Builds a reusable full-portfolio view from the machine layer: portfolio config, technical refresh, deployment check, trigger sheet, regime scores, board/canon guardrail, daily executive brief, and market state. `--write` writes JSON by default; use `--write-md` and `--write-html` for explicit optional renders with graphics/tables. It is a report layer, not canon.

Run:
```bash
python scripts/full_portfolio_view.py --window post-close --write
python scripts/full_portfolio_view_validate.py --window post-close --write
```

Writes:
- `tmp/full-portfolio-view.json`
- optional `tmp/full-portfolio-view.md` with `--write-md`
- optional `tmp/full-portfolio-view.html` with `--write-html`
- `tmp/full-portfolio-view-validation.json`

Boundary:
- review-only; no canonical mutation, portfolio mutation, owner approval, sizing, execution entitlement, or trade authority
- market/theme views must use fresh workspace artifacts or fresh external/primary-source checks when decision-critical

### `portfolio_snapshot_patch_proposal.py`

Status: live review-only proposal generator

Reads `tmp/full-portfolio-view.json` and `03. Portfolio/Portfolio Snapshot.md`, then stages exact-text patch proposals when Snapshot freshness/header state lags the machine layer. It never applies edits.

Run:
```bash
python scripts/portfolio_snapshot_patch_proposal.py --write
```

Writes:
- `tmp/portfolio-snapshot-patch-proposal.json`
- `tmp/portfolio-snapshot-patch-proposal.md`

Boundary:
- cron may generate proposals only
- main session may apply bounded freshness/status sync after review
- no weight, cash, sleeve, sizing, owner-approval, execution-entitlement, promotion/demotion, or trade/action changes

### `current_window_artifact_index.py`

Status: live review-only chain index

Writes a stable current-window artifact map so operator prompts and downstream review can find the right run summary, review objects, report surfaces, guardrails, patch proposals, archive suggestions, and portfolio view without guessing which window just ran. It creates aliases by role only; it does not copy artifacts or promote generated reports into canon.

Run:
```bash
python scripts/current_window_artifact_index.py --window post-close --write
```

Writes:
- `tmp/current-window-artifacts.json`
- `optional Markdown digest beside `tmp/current-window-artifacts.json``

Boundary:
- review-only index/navigation artifact
- no canonical mutation, portfolio mutation, deployment-state mutation, owner approval, execution entitlement, or trade authority
- optional artifacts may be missing when a window does not produce that role or when an advisory report has not been run

### WF56 portfolio proposal validators

Status: live review-only validator spine

These validators make portfolio-mutation proposal generation fail closed before any future patch/apply helper exists. They accept a proposal file, a directory of proposal JSON files, or a wrapper object with `proposals: [...]`. The default input is `tmp/portfolio-mutation-proposals/`.

Run:
```bash
python scripts/proposal_patch_scope_validator.py --write
python scripts/canonical_status_invariant_validator.py --write
python scripts/portfolio_pro_forma_risk_validator.py --write
python scripts/authority_vocabulary_consistency_check.py --write
python scripts/post_apply_validation_chain.py --write
```

Writes:
- `tmp/proposal-patch-scope-validation.json`
- `tmp/canonical-status-invariant-validation.json`
- `tmp/portfolio-pro-forma-risk-validation.json`
- `tmp/authority-vocabulary-consistency.json`
- `tmp/post-apply-validation-chain.json`

Contracts:
- `proposal_patch_scope_validator.py` allows only approved WF56 proposal surfaces: Watchlist, Execution Board, Execution Board, Portfolio Snapshot, Coverage and Watchlist, Risk Rules, `tmp/portfolio-config.json`, and `tmp/portfolio-mutation-proposals/`. It blocks absolute paths, `..` traversal, account/brokerage/secret surfaces, true authority flags, and apply-capable packets.
- `canonical_status_invariant_validator.py` requires complete current/proposed status tuples across Coverage and Watchlist, Execution Board, Portfolio Snapshot, and portfolio config; it requires owner-surface and field-delta metadata; it blocks jumps from do-not-touch/repair/below-stop/blocked/post-earnings review states to deployable-now without preserving review-only owner-decision gating.
- `portfolio_pro_forma_risk_validator.py` requires risk-rule, concentration, sector, correlated-sleeve, sleeve-delta, and cash-target blocks; it enforces the 25% sector cap, 15% normal single-name ceiling, declared sleeve/correlation caps, speculative-sleeve exception language, and configured cash floor when present.
- `authority_vocabulary_consistency_check.py` scans proposal/report artifacts for forbidden approval, execution, deployment-probability, win-probability, and guaranteed-return language while preserving safe review-only/no-authority phrasing.
- `post_apply_validation_chain.py` is dry-run/planned by default. `--execute` runs only after scoped owner approval and includes canonical ownership, portfolio config, dashboard/state, pipeline consistency, full portfolio view regeneration/validation, board/stale guardrails, and proposal-specific validators.

Boundary:
- clean validation is not approval
- cron may generate proposal objects and validator reports only
- no ungated portfolio mutation, owner approval, cash/risk-rule change, execution entitlement, trade/account action, or destructive cleanup is authorized by these scripts; sizing/sleeve/sector-posture writes require exact approved gated apply artifacts

### `canonical_note_patch_proposal.py`

Status: live review-only proposal generator

Builds canonical-note patch proposals from board/canon and stale-intelligence guardrail findings. Cron may run it to stage `tmp/canonical-note-patch-proposal.json` and `.md`, but it never applies edits. Main-session review is required before bounded freshness/status sync is applied to canonical notes.

Run:
```bash
python scripts/canonical_note_patch_proposal.py --write
```

Writes:
- `tmp/canonical-note-patch-proposal.json`
- `tmp/canonical-note-patch-proposal.md`

Notes:
- `cron_apply_allowed=false` is a hard boundary
- main-session apply is limited to review-only freshness/source-confidence/catalyst-state/technical-state/watch-repair-deployment-state sync
- portfolio mutation, owner approval, sizing, sleeve, sector-posture, execution-entitlement, and trade/action changes remain out of bounds for this review-only generator; use the WF56 exact gated apply path for approved portfolio note/model writes

### `stale_intelligence_guardrail.py`

Status: live read-only guardrail

Checks high-risk stale intelligence patterns in canonical finance notes: JPM appearing in deployable-now language after a stop breach, unquarantined Weekly Intelligence Brief placeholders/skeleton sections, stale Regime Matrix refresh-deadline text, and ETN deployable-note close/no-chase drift versus current artifacts.

Run:
```bash
python scripts/stale_intelligence_guardrail.py --write
```

Writes:
- `tmp/stale-intelligence-guardrail.json`

Notes:
- exits nonzero on critical stale-intelligence findings
- writes reports only; canonical note edits remain main-session gated

### `board_canon_guardrail.py`

Status: live read-only guardrail

Checks below-stop and near-stop artifact states against the canonical board notes so stale softer labels like “almost deployable” or “active watch” cannot quietly survive after a stop breach. It writes proof artifacts only and does not mutate portfolio notes, deployment states, owner approval, or trade/account surfaces.

Run:
```bash
python scripts/board_canon_guardrail.py --write
```

Writes:
- `tmp/board-canon-guardrail.json`
- `tmp/board-canon-guardrail.md`

Notes:
- exits nonzero on critical stop/canon contradictions
- runs in the morning, post-close, and Sunday finance chains after fresh deployment/trigger/regime artifacts are built
- below-stop and near-stop states must outrank softer watch, almost-deployable, or owner-approved-history language

### `deployment_check.py`

Status: live

Reads cached technical and market-state outputs and produces a ranked deployment-readiness summary with freshness checks.

Run:
```bash
python scripts/deployment_check.py
```

Writes:
- `tmp/deployment-check.json`

### `market_intelligence_event_router.py`

Status: live review-only event/materiality router

Builds the bounded WF41-style v1 event packet from approved workspace artifacts. This is not broad news crawling. It routes existing dashboard trust warnings, macro warnings, promotion-review / near-deployable names, band-review debt, provider-calendar catalyst windows, and post-earnings prep packets into ranked owner-review events.

Run:
```bash
python scripts/market_intelligence_event_router.py --window morning
python scripts/market_intelligence_event_router.py --window post-close
```

Writes:
- `tmp/market-intelligence-events-morning.json`
- `tmp/market-intelligence-events-post-close.json`
- `tmp/market-intelligence-events-post-earnings.json`
- `tmp/market-intelligence-events-sunday.json`

Notes:
- remains strictly `review_only`
- every event keeps `owner_review_required=true`
- may rank and route events, but may not mutate thesis, portfolio state, canonical notes, config, or trades
- source quality is workspace-artifact based in v1; wider external-source automation still needs a separate approval/proof pass

Regression guard:
```bash
python scripts/test_market_intelligence_event_router.py
```

### `sector_correlation_check.py`

Status: live review-only WF53 concentration/correlation proof artifact

Builds `tmp/sector-correlation-check.json` from portfolio config, Risk Rules, portfolio notes, and generated finance artifacts. It computes sector exposure versus the 25% cap, highlights correlated-sleeve warnings such as Tech + AI-power, and keeps promotion-impact checks owner-gated. In the finance chain it runs before the sector expansion board and before daily review objects for morning, post-close, and Sunday windows.

Run:
```bash
python scripts/sector_correlation_check.py --window post-close --output tmp/sector-correlation-check.json
```

### `sector_expansion_board.py`

Status: live review-only WF53 daily sector expansion board

Builds `tmp/sector-expansion-board.json` and answers: “Where is sector leadership improving, where are we underexposed, and which names deserve promotion review?” It reviews all 11 SPDR sectors against SPY using 1d/5d/20d relative strength, 50DMA participation, portfolio exposure, tracked-universe candidates, promotion-review queue status, and concentration warnings. It is wired after `sector_correlation_check.py` and before `daily_review_objects.py` for morning, post-close, and Sunday chains.

Run:
```bash
python scripts/sector_expansion_board.py --window post-close --output tmp/sector-expansion-board.json
```

Notes:
- remains strictly `review_only`
- emits `short_term_moving_averages` for each sector ETF (`sma_5`, `sma_20`, price-vs-5DMA, price-vs-20DMA, 5DMA-vs-20DMA, and a thin signal warning) so capital recommendations can include timing cautions without implying approval
- all authority flags stay false; no canonical mutation, watchlist promotion, sizing/allocation recommendation, trade execution, owner approval inference, or probability/modeling authority
- no SPY or no sector price history blocks; partial sector/provider data degrades rather than faking clean status

### `sector_dashboard_suite.py`

Status: live review-only WF53 HTML/CSV dashboard renderer

Builds a local presentation suite from `tmp/sector-expansion-board.json` using pandas. It writes an HTML dashboard plus CSV pivot surfaces for the sector table, leadership/underexposure pivot, exposure pivot, and promotion-review queue context. This is a presentation layer only; it does not mutate canonical notes, portfolio/deployment state, watchlist state, sizing, trade, approval, or probability authority.

Run:
```bash
python scripts/sector_dashboard_suite.py --input tmp/sector-expansion-board.json --output tmp/sector-dashboard-suite.html --csv-dir tmp
```

Writes:
- `tmp/sector-dashboard-suite.html`
- `tmp/sector-dashboard-sector-table.csv`
- `tmp/sector-dashboard-leadership-pivot.csv`
- `tmp/sector-dashboard-exposure-pivot.csv`
- `tmp/sector-dashboard-promotion-queue.csv`

Regression guard:
```bash
python scripts/test_sector_correlation_check.py
python scripts/test_sector_expansion_board.py
python scripts/test_sector_dashboard_suite.py
```

### `daily_review_objects.py`

Status: live review-only decision-prep layer

Builds the bounded daily review-object packet that ranks what matters, escalates only the highest-signal items, and prepares owner-gated capital-deployment recommendation objects from the native finance artifact stack. It consumes the read-only market-intelligence event router and fresh WF53 sector/correlation artifacts when present. Freshness gating is per artifact: stale sector board fields are not mixed into fresh correlation context, and stale correlation fields are not mixed into fresh sector-board context.

Run:
```bash
python scripts/daily_review_objects.py --window morning
python scripts/daily_review_objects.py --window post-close
```

Writes:
- `tmp/daily-review-objects-morning.json`
- `tmp/daily-review-objects-post-close.json`
- `tmp/daily-review-objects-post-earnings.json`
- `tmp/daily-review-objects-sunday.json`

Notes:
- remains strictly `review_only`
- every capital recommendation keeps `owner_approval_required=true`
- capital recommendations include deterministic final-advice fields (`thesis`, `setup_summary`, `catalyst_risk`, `sizing_risk_envelope`, `base_case`, `bull_case`, `bear_case`) sourced from existing artifacts/config without probability, expected-return, model-ranked claims, or per-name numeric sizing ranges/maxes
- may rank and recommend, but may not mutate canonical notes, change deployment state, or execute
- current known gaps stay explicit: wider external-source automation and state-history retention are not wired yet; sector/correlation context is consumed only when fresh enough and remains a manual fallback when absent, stale, or blocked

Regression guard:
```bash
python scripts/test_daily_review_objects.py
```

### `portfolio_mutation_proposal_generator.py`

Status: gated capital-deployment proposal packet generator

Converts `daily_review_objects.py` capital-deployment recommendation objects into validator-readable proposal packets under `tmp/portfolio-mutation-proposals/`. The bundle now records Randall's approved posture for **portfolio note/model mutation under WF58/WF56 guardrails**, while each generated packet still proposes no direct state change and remains non-self-applying. Trade/account actions, brokerage orders, money movement, unscoped execution entitlement, per-packet owner-approval inference, sizing, sleeve, cash, and risk-rule changes remain blocked unless a separate exact apply artifact and validator chain explicitly support them.

Run:
```bash
python scripts/portfolio_mutation_proposal_generator.py --window post-close --write
```

Writes:
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`

Companion renderer/validator:
```bash
python scripts/capital_deployment_recommendation_report.py --write
python scripts/capital_deployment_recommendation_validator.py --write
```

Companion outputs:
- `optional Markdown digest beside `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json``
- `tmp/capital-deployment-recommendation-validation.json`

Chain placement:
- morning, post-close, and Sunday finance-chain tails
- runs after `daily_review_objects.py` and before downstream guardrails/discrepancy/index surfaces
- the Markdown renderer and bundle validator run immediately after the generator in those tails
- post-close also runs before `proposal_patch_scope_validator.py`, `canonical_status_invariant_validator.py`, `portfolio_pro_forma_risk_validator.py`, `authority_vocabulary_consistency_check.py`, and `post_apply_validation_chain.py`

Stop lines:
- generated packets are proposal/review artifacts and do not apply changes by themselves
- portfolio note/model mutation is approved only inside the WF58/WF56 guarded workflow; exact packet/diff/apply proof is still required before writes
- trade/account actions, brokerage orders, money movement, and unscoped execution entitlement remain blocked
- validator success is not per-packet approval and is not execution entitlement

Regression guard:
```bash
python scripts/test_portfolio_mutation_proposal_generator.py
python scripts/test_capital_deployment_recommendation_validator.py
python scripts/portfolio_mutation_proposal_schema_validator.py tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json
python scripts/capital_deployment_recommendation_validator.py tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json
python scripts/proposal_patch_scope_validator.py tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json
python scripts/portfolio_pro_forma_risk_validator.py tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json
```

### `finance_discrepancy_resolver.py`

Status: review-only discrepancy queue generator

Aggregates discrepancy and guardrail findings from earnings-date source confidence, Event Calendar rollforward/apply, board/canon guardrails, stale-intelligence guardrails, canonical note patch proposals, and portfolio snapshot patch proposals. It writes an operator queue only; every candidate is `cron_apply_allowed=false` and `main_session_review_required=true`.

Run:
```bash
python scripts/finance_discrepancy_resolver.py --write
```

Writes:
- `tmp/finance-discrepancy-resolver.json`
- `tmp/finance-discrepancy-resolver.md`

Chain placement:
- morning, post-close, and Sunday finance-chain tails
- runs after canonical/portfolio patch proposals and before current-window artifact indexing
- does not run an apply path; it only queues review work

Regression guard:
```bash
python scripts/test_finance_discrepancy_resolver.py
```

### `ticker_monitoring_performance.py`

Status: live review-only WF54 current-state monitoring analytics

Builds `tmp/ticker-monitoring-performance.json` from deployment checks, price-trend signals, WF53 sector context, and WF43 state-history row counts. It measures monitoring state only: band/stop posture, repair/fail-closed names, catalyst flags, review debt, WF53 context, and whether history is present but still insufficient for outcome analytics.

Run:
```bash
python scripts/ticker_monitoring_performance.py --window post-close --output tmp/ticker-monitoring-performance.json
```

Notes:
- remains strictly `review_only`
- `fail_closed_tickers` means below-stop / repair fail-closed names only
- `blocked_or_review_required_tickers` carries broader band-review/catalyst/review debt
- outcome analytics stay disabled until realized-outcome retention exists and the probability-readiness gate passes
- no probability, expected-return, model-ranked deployment, watchlist promotion, sizing/allocation, trade execution, canonical mutation, or owner approval inference

Regression guard:
```bash
python scripts/test_ticker_monitoring_performance.py
```

### `state_history_capture.py`

Status: live append-only historical review writer; durable path approved, consumer wiring pending

Captures point-in-time post-close review state into JSONL history without mutating canonical notes, portfolio state, deployment state, owner approval, or trade execution surfaces.

Default durable output:
- `data/state-history/state-history-v1.jsonl`

Legacy proof artifact:
- `tmp/state-history-v1.jsonl` remains proof-only residue, not durable truth.

Run:
```bash
python scripts/state_history_capture.py sample --window post-close
python scripts/state_history_capture.py append --window post-close
python scripts/state_history_capture.py validate
```

Proof contract:
```bash
python -m py_compile scripts\state_history_capture.py scripts\test_state_history_capture.py
python scripts\test_state_history_capture.py
python scripts\state_history_capture.py sample --window post-close
python scripts\state_history_capture.py append --window post-close
python scripts\state_history_capture.py validate
```

Authority:
- historical review and provenance only
- no model training by default
- no model-driven deployment
- no canonical note mutation
- no portfolio/deployment mutation
- no trade execution
- no owner-approval inference

Stop lines:
- validation fails
- source provenance or hashes are missing
- known-at-time fields are mixed with realized future outcomes
- any authority flag widens beyond historical review

### `state_history_outcome_update.py` / `state_history_outcome_update_validator.py`

Status: live append-only WF55 outcome sidecar; review-only and non-modeling

Writes/validates retained realized-outcome updates without rewriting `data/state-history/state-history-v1.jsonl`. Outcome rows link back to a prior `capture_run_id`, must have later observed/recorded timestamps, allowed outcome labels, source provenance + hash, and hard-false authority flags. Allowed labels include thesis/band/stop/promotion/owner-decision outcomes plus explicit WF67 paper lifecycle labels (`paper_order_*`, `paper_position_*`) for validated paper-only evidence; labels do not create trading, account, portfolio, or model authority.

Default durable output:
- `data/state-history/outcome-updates-v1.jsonl`

Validation report:
- `tmp/state-history-outcome-update-validation.json`

Run:
```bash
python scripts/state_history_outcome_update.py sample --linked-capture-run-id <id> --ticker GOOG --question-id band_reclaim_retention --outcome-label band_reclaim_held --observed-at-utc 2026-05-20T20:00:00Z --provenance-path tmp/probability-readiness-report.json
python scripts/state_history_outcome_update.py validate
python scripts/state_history_outcome_update_validator.py --write
```

Proof contract:
```bash
python -m py_compile scripts\state_history_outcome_update.py scripts\state_history_outcome_update_validator.py scripts\test_state_history_outcome_update.py
python scripts\test_state_history_outcome_update.py
python scripts\state_history_outcome_update_validator.py --write
python scripts\probability_readiness_report.py --write
python scripts\probability_readiness_validator.py --write
```

Authority:
- retained outcome evidence only
- no probability/win-rate/expected-return/model-ranked language
- no model training by default
- no portfolio/deployment/canonical mutation
- no trade/account action
- no owner-approval inference

### `historical_regime_event_library.py`

Status: live review-only WF55/WF69 historical analog/base-rate scaffold

Builds `tmp/historical-regime-event-library.json/.md` from a curated event list and public historical daily market data. It includes 1970s/1980s/1990s/2000s+ war, crash, inflation, rate-shock, credit-stress, and bull-market/broadening analogs. The output is for stress context and base-rate review only; older periods degrade honestly when small-cap comparison data is unavailable.

Default outputs:
- `tmp/historical-regime-event-library.json`
- `tmp/historical-regime-event-library.md`

Run:
```bash
python scripts\historical_regime_event_library.py --write --validate
python scripts\probability_readiness_report.py --write
python scripts\probability_readiness_validator.py --write
```

Proof contract:
```bash
python -m py_compile scripts\historical_regime_event_library.py scripts\test_historical_regime_event_library.py
python scripts\test_historical_regime_event_library.py
python scripts\historical_regime_event_library.py --write --validate
python scripts\probability_readiness_report.py --write
python scripts\probability_readiness_validator.py --write
```

Authority:
- analog/base-rate context only
- no calibrated probability
- no deployment ranking
- no return projection claim
- no capital deployment, portfolio/canon mutation, paper/live/account action, money movement, or owner-approval inference

### `current_regime_analog_matcher.py`

Status: live review-only WF55/WF61/WF78/WF85 scenario-context panel

Builds `tmp/current-regime-analog-match.json/.md` from `tmp/historical-regime-event-library.json` plus the current `tmp/small-mid-cap-regime-feed.json` context. It classifies historical analog rows into primary rate-stabilization/breadth-repair context and stress/caution context for downstream packets. Consumers include macro judgment, WF61 small/mid-cap regime feed, WF78 small/mid-cap candidate review, the finance market deployment loop, and future WF85 decision cards as `scenario_context`, not score.

Run:
```bash
python scripts\current_regime_analog_matcher.py --write --validate
```

Proof contract:
```bash
python -m py_compile scripts\current_regime_analog_matcher.py scripts\test_current_regime_analog_matcher.py
python scripts\test_current_regime_analog_matcher.py
python scripts\current_regime_analog_matcher.py --write --validate
```

Authority:
- scenario/base-rate context only
- no calibrated probability, predictive score, deployment ranking, sizing/allocation recommendation, capital action, paper/live execution, account action, money movement, or owner-approval inference

### `wf55_outcome_ledger_v2.py`

Status: preview-only WF55 v2 outcome/recommendation ledger

Builds and validates the current review-only recommendation/outcome loop. It converts retained v1 outcome rows, then adds non-durable tracking rows for open capital-deployment recommendations and Monday WF67 paper-card follow-up. The current artifact is consumed by the WF75 operator console so recommendations and prepared paper cards do not disappear between sessions.

Default outputs:
- `tmp/wf55-outcome-ledger-v2-migration-preview.json`
- `tmp/wf55-outcome-ledger-v2-validation.json`
- `tmp/recommendation-outcome-ledger-current.json`
- `tmp/wf55-outcome-ledger-v2-migration-preview.md`

Run:
```bash
python scripts\wf55_outcome_ledger_v2.py preview
python scripts\probability_readiness_report.py --write
python scripts\wf75_operator_console.py --write --validate
```

Proof contract:
```bash
python -m py_compile scripts\wf55_outcome_ledger_v2.py scripts\test_wf55_outcome_ledger_v2.py
python scripts\test_wf55_outcome_ledger_v2.py
python scripts\wf55_outcome_ledger_v2.py preview
```

Authority:
- preview/current ledger only; no durable `data/state-history/outcome-ledger-v2.jsonl` write
- no probability, win-rate, expected-return, model-ranked, or model-readiness claim
- no portfolio/canon mutation, SQL/ticker import, customer output, owner-approval inference, paper/live execution, or account action
- Monday paper-card rows remain pending until fresh quote, fresh WF67 guard, fresh short-lived kill switch, and exact Randall order approval

### `sec_evidence_packet.py` / `sec_evidence_packet_validator.py` / `goog_official_ir_capture.py`

Status: live WF65/WF66 official-source evidence sidecar plus GOOG official IR capture; review-only Option A/D foundation

Builds review-only SEC/EDGAR evidence packets through the inspected local `skills/sec` skill. The packet captures CIK, company name, latest 10-K/10-Q/8-K filing dates and links, selected SEC company facts/concepts, source provenance, SEC User-Agent, producer script/hash, and hard-false authority fields. `goog_official_ir_capture.py` captures GOOG Q1 2026 official earnings fields from SEC 8-K Exhibit 99.1 into a validated review-only artifact. This preserves the path to Option D: validated SEC evidence and official IR capture can later feed WF65/WF66 and capital-recommendation freshness gates, while any actual main-session workspace portfolio/canon maintenance still requires separate WF64/WF56 exact gated apply artifacts and post-apply proof.

Default outputs:
- `tmp/sec-env-audit-validator.json`
- `tmp/sec-evidence-packets/current-sec-evidence.json`
- `tmp/sec-evidence-packets/current-sec-evidence.md`
- `tmp/sec-evidence-packets/current-sec-evidence-validation.json`
- `tmp/sec-evidence-packets/capital-recommendation-sec-bridge.json`
- `tmp/sec-evidence-packets/capital-recommendation-sec-bridge.md`
- `tmp/sec-evidence-packets/goog-sec-freshness-review.json`
- `tmp/sec-evidence-packets/goog-sec-freshness-review.md`
- `tmp/official-ir-captures/goog-q1-2026.json`
- `tmp/official-ir-captures/goog-q1-2026.md`
- `tmp/official-ir-captures/goog-q1-2026-validation.json`

Run with the SEC skill venv:
```powershell
python scripts\sec_env_audit_validator.py --write --validate
skills\sec\.venv\Scripts\python.exe scripts\sec_evidence_packet.py --tickers GOOG GS MSFT ETN --output tmp\sec-evidence-packets\current-sec-evidence.json --markdown tmp\sec-evidence-packets\current-sec-evidence.md
python scripts\sec_evidence_packet_validator.py --input tmp\sec-evidence-packets\current-sec-evidence.json --output tmp\sec-evidence-packets\current-sec-evidence-validation.json --write
python scripts\sec_capital_recommendation_bridge.py --output tmp\sec-evidence-packets\capital-recommendation-sec-bridge.json
python scripts\goog_official_ir_capture.py --output tmp\official-ir-captures\goog-q1-2026.json --write-md
python scripts\official_ir_capture_validator.py --input tmp\official-ir-captures\goog-q1-2026.json --output tmp\official-ir-captures\goog-q1-2026-validation.json --write
python scripts\sec_capital_freshness_review.py --ticker GOOG --output tmp\sec-evidence-packets\goog-sec-freshness-review.json
```

Proof contract:
```powershell
python -m py_compile scripts\sec_env_audit_validator.py scripts\test_sec_env_audit_validator.py scripts\sec_evidence_packet.py scripts\sec_evidence_packet_validator.py scripts\test_sec_evidence_packet_validator.py scripts\sec_capital_recommendation_bridge.py scripts\sec_capital_freshness_review.py scripts\goog_official_ir_capture.py scripts\official_ir_capture_validator.py
python scripts\sec_env_audit_validator.py --write --validate
python scripts\test_sec_env_audit_validator.py
python scripts\test_sec_evidence_packet_validator.py
skills\sec\.venv\Scripts\python.exe scripts\sec_evidence_packet.py --tickers GOOG GS MSFT ETN --output tmp\sec-evidence-packets\current-sec-evidence.json --markdown tmp\sec-evidence-packets\current-sec-evidence.md
python scripts\sec_evidence_packet_validator.py --input tmp\sec-evidence-packets\current-sec-evidence.json --output tmp\sec-evidence-packets\current-sec-evidence-validation.json --write
python scripts\sec_capital_recommendation_bridge.py --output tmp\sec-evidence-packets\capital-recommendation-sec-bridge.json
python scripts\goog_official_ir_capture.py --output tmp\official-ir-captures\goog-q1-2026.json --write-md
python scripts\official_ir_capture_validator.py --input tmp\official-ir-captures\goog-q1-2026.json --output tmp\official-ir-captures\goog-q1-2026-validation.json --write
python scripts\sec_capital_freshness_review.py --ticker GOOG --output tmp\sec-evidence-packets\goog-sec-freshness-review.json
```

Bounded smoke-test contract:
```powershell
skills\sec\.venv\Scripts\python.exe scripts\sec_evidence_packet.py --tickers MSFT --forms 10-K 10-Q 8-K --filing-limit 1 --output tmp\sec-evidence-packets\smoke-sec-evidence-YYYY-MM-DD.json --markdown tmp\sec-evidence-packets\smoke-sec-evidence-YYYY-MM-DD.md
python scripts\sec_evidence_packet_validator.py --input tmp\sec-evidence-packets\smoke-sec-evidence-YYYY-MM-DD.json --output tmp\sec-evidence-packets\smoke-sec-evidence-validation-YYYY-MM-DD.json --write
```

Latest bounded smoke proof:
- 2026-05-19: MSFT single-ticker SEC packet generated with `status=ok`, 0 critical / 0 warning, latest 10-K `2025-07-30`, latest 10-Q `2026-04-29`, latest 8-K `2026-05-14`.
- Validator proof: `tmp/sec-evidence-packets/smoke-sec-evidence-validation-2026-05-19.json` returned `status=ok`, 0 critical / 0 warning.
- Smoke artifacts are review-only proof, not chain/cron ownership and not portfolio/canon/trade/account authority.

Authority:
- official-source evidence only
- SEC packet alone does not apply canonical/portfolio mutation, owner approval, sizing/allocation, account action, money movement, or trades
- main-session Veritas may use validated SEC evidence as support for later WF64/WF56 standing-approved workspace maintenance only through the separate gated apply path
- no probability/win-rate/expected-return/model-ranked deployment language

Stop lines:
- invalid/placeholder SEC User-Agent
- missing CIK/provenance/hash
- widened authority fields
- SEC retrieval failure for a required evidence target
- stale/manual/contradictory evidence when a downstream mutation would depend on it

### `workspace_index.py`

Status: live derived workspace retrieval/cache index

Builds `tmp/workspace-index.sqlite` from Markdown notes plus a bounded generated-artifact manifest. It is a retrieval/cache layer only: source Markdown notes and source JSON artifacts remain authoritative.

Run:
```powershell
python scripts\workspace_index.py
python scripts\workspace_index.py --search "WF72" --limit 10
python scripts\workspace_index.py --search "note-drift" --limit 10
python scripts\workspace_index.py --search "Phase 4A SQL canon" --limit 10
```

Writes:
- `tmp/workspace-index.sqlite`
- `tmp/workspace-index-report.json`
- SQLite sidecars may also appear under `tmp/` when WAL mode is active: `tmp/workspace-index.sqlite-wal` and `tmp/workspace-index.sqlite-shm`

Query behavior:
- exact alias matches, such as `WF72` / `Workflow 72`, are returned as retrieval hints before body-search hits
- FTS5 raw query behavior is preserved first for normal/advanced queries
- if FTS5 rejects punctuation or returns no useful parse for human text, the search falls back to parser-safe quoted phrase and token-AND variants; hyphenated terms such as `note-drift` normalize to `note drift` instead of failing on the hyphen
- all FTS fallback expressions are built from extracted word tokens and passed as SQLite parameters; this is retrieval hardening, not a new authority surface
- retrieval hit -> open the source file before judgment, queue movement, or mutation

Boundary:
- workspace index is retrieval/cache only
- no canon/apply/portfolio/trade/account/paper/approval authority
- do not use SQL rows as a substitute for reading the source Markdown note or generated artifact

### `artifact_index.py`

Status: live derived SQL cockpit / retrieval index

Builds a read-only SQLite index from current generated finance artifacts, including market-intelligence packets, daily review objects, capital recommendation surfaces, current-window artifacts, Today-card proof, official IR capture fields/lineage, validator runs, authority flags, and canon-staging proposal rows. This is the primary fast route for generated-artifact/proof/provenance/staging lookup, but it remains derived index/staging only: the JSON artifacts and note layer remain the operating truth, and the SQLite DB must not be treated as canonical portfolio state, owner approval, an apply engine, or trade/account/paper authority.

Run:
```bash
python scripts/artifact_index.py rebuild
python scripts/artifact_index.py incremental
python scripts/artifact_index.py validate
python scripts/artifact_index.py cockpit --limit 20
python scripts/artifact_index.py ticker-cockpit ETN --limit 30
python scripts/artifact_index.py trust-cockpit --limit 50
python scripts/artifact_index.py proof-field AMD adjusted_eps
python scripts/artifact_index.py stoplines --limit 50
python scripts/artifact_index.py handoff --workflow WF72 --limit 20
python scripts/artifact_index.py note-drift --limit 100 --output tmp/wf72-sql-to-note-drift-report.json
python scripts/artifact_index.py fingerprints --json
```

Writes:
- `tmp/veritas-artifact-index.sqlite`
- SQLite sidecars may also appear under `tmp/` when WAL mode is active: `tmp/veritas-artifact-index.sqlite-wal` and `tmp/veritas-artifact-index.sqlite-shm`

Notes:
- derived index/staging only; rebuild or incrementally refresh from source artifacts when in doubt
- enables fast lookup by ticker/sleeve, workflow queue, helper handoff locator packets, official-source fields, canon proposal stop lines, escalations, capital recommendations, and trust/freshness boundaries
- cockpit outputs include source files/provenance so operators can inspect the target artifact before finance/readiness claims
- `handoff --workflow <WFxx>` emits a derived helper locator packet plus validation/stopline context; canonical next-step ownership remains `06. Playbooks/Active Workflows.md`
- `note-drift` emits SQL-routed canon/note drift candidates only; it compares staged proposal text/hashes to current Markdown notes and does not apply changes
- `validate` checks integrity/FK/view availability, authority stop lines, official IR lineage, query-plan health, and drift fingerprint row-count coverage
- `fingerprints --json` emits stable semantic row hashes for full-vs-incremental drift proof
- uses WAL, `busy_timeout`, explicit indexes, strict tables, `BEGIN IMMEDIATE` incremental rebuilds, and `artifact_file_state` stale-source cleanup
- wired into scheduled finance tails after `current_window_artifact_index.py` as a derived refresh only; it does not apply canon, mutate portfolio state, infer approval, or authorize execution

### `sql_canon_metadata_resolver.py`

Status: WF72 SQL-canon V2 typed metadata resolver / read-only fallback-first scaffold

Resolves approved SQL-canon/cache metadata through the fail-closed authority guard while preserving fallback-first behavior. It is the first V2 consumption scaffold: values become SQL-effective only when the global guard is clean, the key is active-approved, fallback exists, SQL equals fallback, and the row is not stale/unsafe. With current Phase 3F stale blockers, it deliberately resolves affected keys to fallback/degraded rather than SQL-first.

Run:
```bash
python scripts/sql_canon_metadata_resolver.py --key NVDA:earnings_lifecycle_status --fallback NVDA:earnings_lifecycle_status=watchlist_already_closed --write --validate
python scripts/test_sql_canon_metadata_resolver.py
```

Writes:
- `tmp/sql-canon-metadata-resolution.json`

Boundary:
- read-only resolver scaffold only
- no DB writes/schema changes/cache activation
- no consumer behavior change or dashboard/action-state mutation
- no Markdown/canon/portfolio mutation
- no owner approval, trade/account/paper/live, money movement, config/auth/channel/service/runtime authority

### `sql_canon_retail_grade_readiness.py`

Status: WF72 SQL-canon retail-grade readiness map / JSON-only report surface

Builds a row-level readiness report for the active 265-row SQL-canon/cache boundary. It classifies each approved row as SQL-effective, fallback-required, stale/unsafe, missing-fallback, display-only reference metadata, or blocked higher-risk metadata. This is the retail-grade gate before any SQL-first consumer or customer-safe renderer binding. It is deliberately JSON-first and does not create a routine Markdown sidecar.

Run:
```bash
python scripts/sql_canon_retail_grade_readiness.py --write --validate
python scripts/test_sql_canon_retail_grade_readiness.py
```

Writes:
- `tmp/sql-canon-retail-grade-readiness.json`

Boundary:
- report-only readiness map
- no DB writes/schema changes/cache activation
- no SQL-first consumer migration or dashboard/action-state behavior change
- no Markdown/canon/portfolio mutation
- no owner approval, trade/account/paper/live, money movement, real customer data, external delivery, or config/auth/channel/service/runtime authority
- ticker and leadership research is artifact-only until current source-open/freshness/licensing/compliance gates are satisfied

### `sql_canon_v2_planner.py`

Status: WF72 SQL-canon V2 state-contract planner / report-only control surface

Builds the V2 planning artifact for advancing `tmp/veritas-canon-cache.sqlite` from bounded cache/routing toward governed SQL-first metadata consumption. It reads live SQL surfaces, validates the current 265-row boundary, exposes Phase 3F stale blockers, lists V2 phases and candidate families, and preserves fail-closed authority boundaries. It does not write cache rows, mutate consumers, mutate Markdown/canon/portfolio notes, infer approval, or authorize execution.

Run:
```bash
python scripts/sql_canon_v2_planner.py --write --validate
python scripts/test_sql_canon_v2_planner.py
```

Writes:
- `tmp/sql-canon-v2-prototype-plan.json`
- `tmp/sql-canon-v2-prototype-plan.md`

Boundary:
- planning/report-only V2 state contract
- no SQL-canon row activation or field-family expansion
- no consumer behavior change
- no Markdown/canon/portfolio mutation
- no owner approval, trade/account/paper/live, money movement, config/auth/channel/service/runtime authority

### `sql_canon_field_family_preflight.py`

Status: WF72 SQL-canon field-family migration protocol / review-only shadow preflight

Builds the reusable protocol and candidate preflight for controlled SQL-canon field-family expansion after Phase 4A. The first approved follow-on activation is complete through `sql_canon_low_risk_phase3_activate.py`, and the current live canon-cache boundary is exactly 265 metadata rows: 13 proof/freshness/lifecycle rows plus 252 WF72 entry/stop reference-metadata rows. This preflight script remains review/shadow proof and does not itself activate new keys, write SQL canon/cache rows, mutate Markdown/canonical notes, mutate portfolio state, infer approval, authorize cron direct apply, or touch trade/account/paper/live/money surfaces.

Run:
```bash
python scripts/sql_canon_field_family_preflight.py --write
```

Writes:
- `tmp/sql-canon-field-family-migration-protocol.json`
- `tmp/sql-canon-low-risk-field-family-preflight.json`

Notes:
- opens the artifact index read-only and treats all outputs as review/shadow proof
- current active low-risk metadata set is 13 exact keys under `phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority`
- current active entry/stop reference set is 252 exact metadata rows under `wf72_entry_stop_reference_metadata_exact_key_gated_no_execution_authority`
- deployment/status wording such as `deployment_proof_status` is deliberately held for a separate gate because it can imply action
- any actual SQL-canon expansion still requires a separate exact activation artifact, no-drift consumer proof, rollback/export proof, and approval gate

### `sql_canon_low_risk_phase3_activate.py`

Status: WF72 bounded activation entrypoint / exact approved low-risk metadata only

Activates the Randall-approved low-risk SQL-canon metadata set after the shadow plan, consumer no-drift proof, rollback/export, and stale-artifact-index blockers are clean. Despite the legacy filename, the current active low-risk SQL-canon/cache set is exactly 13 proof/freshness/lifecycle metadata keys under `phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority`. Combined with the separately gated WF72 entry/stop reference metadata activation, the live `tmp/veritas-canon-cache.sqlite` boundary is exactly 265 metadata rows.

Run:
```bash
python scripts/sql_canon_low_risk_phase3_activate.py --write
```

Writes:
- `tmp/sql-canon-low-risk-phase3-approval-context.json`
- `tmp/sql-canon-low-risk-phase3-activation.json`
- `tmp/sql-canon-low-risk-phase3-validation.json`
- `tmp/sql-canon-low-risk-phase3-post-activation-no-drift.json`
- `tmp/sql-canon-low-risk-phase3-preactivation-export.json`
- `tmp/sql-canon-low-risk-phase3-rollback.sql`

Boundary:
- SQL-canon/cache activation only for the exact approved metadata set
- fallback remains required before consumer SQL reads
- no Markdown/canon/portfolio mutation
- no owner-approval inference
- no cron-direct apply
- no entry band, technical state, sector, sleeve, sizing, cash, risk-rule, recommendation/deployment/action-state behavior, trade/account/paper/live, credential, or money-movement authority

### `wf72_entry_stop_reference_helper.py`

Status: WF72 typed read-only entry/stop reference metadata helper

Reads only the exact 252 active WF72 entry/stop reference metadata rows from `tmp/veritas-canon-cache.sqlite` using SQLite URI `mode=ro`. The helper returns typed display/reference metadata for the six approved fields and supports the ETN/VRT/NVDA ticker-card no-drift pilot. Ticker cards may add this metadata beside existing fallback values, but the helper must not replace card price/band/stop fields or recommendation posture.

Run:
```bash
python scripts/wf72_entry_stop_reference_helper.py --ticker ETN --ticker VRT --ticker NVDA
python scripts/ticker_intelligence_card.py --ticker ETN --ticker VRT --ticker NVDA --summary-output tmp/wf72-entry-stop-helper-card-build-summary.json
```

Writes through the ticker-card pilot only:
- `tmp/wf72-entry-stop-helper-no-drift-pilot.json`
- `tmp/wf72-entry-stop-helper-card-build-summary.json`

Boundary:
- read-only SQL cache access only
- display/reference/fallback-required metadata only
- no SQL writes/schema changes/cache activation
- no SQL-first consumer migration
- no price/band/stop fallback replacement
- no recommendation, deployment/action-state behavior change, Markdown/canon/portfolio mutation, owner approval, trade/account/paper/live, money movement, or config/auth/channel/service/runtime authority

### `earnings_calendar_enrichment.py`

Status: live

Refreshes next confirmed earnings dates for the coverage universe and flags date changes only for operator-selected timing-sensitive baselines configured in `tmp/portfolio-config.json` under `earnings_date_watchlist`. Do not hardcode already-reported dates or broad quarter-ahead estimates in the script; use the Event Calendar and post-earnings workflow to roll the note layer forward.

Run:
```bash
python scripts/earnings_calendar_enrichment.py
```

Writes:
- `tmp/earnings-calendar.json` with provider dates plus explicit `date_source_class` and `primary_confirmed` fields. Provider/yfinance dates are `provider_estimate` / `primary_confirmed=false` unless a separate primary-source confidence pass supplies real official evidence.

### `earnings_date_source_confidence.py`

Status: live review-only

Builds a source-confidence packet for timing-sensitive earnings-date baselines configured in `tmp/portfolio-config.json -> earnings_date_watchlist`. It keeps provider dates visible while separating `provider_estimate_unconfirmed` from primary company/IR confirmation. A bare `primary_confirmed: true` config flag is not enough to upgrade confidence; it must include matching `primary_evidence` metadata with date, source/source_type, URL, and matched text. If the optional browser sidecar `tmp/earnings-date-browser-confirmation.json` exists, official-source browser evidence may primary-confirm a date; blocked or inconclusive primary-source fetches, including NVIDIA IR 403 behavior, remain visible trust limits rather than silently promoted.

Run:
```bash
python scripts/earnings_date_source_confidence.py
```

Writes:
- `tmp/earnings-date-source-confidence.json`
- `optional Markdown digest beside `tmp/earnings-date-source-confidence.json``

Optional browser sidecar input:
- `tmp/earnings-date-browser-confirmation.json`
- accepted records must include official `source_type` (`company_ir`, `company_newsroom`, `company_release`, `sec_filing`, or `sec`), `confirmation_status=primary_confirmed`, a matching `evidence_date`, `url`, and visible `matched_text`
- browser evidence is review-only and does not authorize Event Calendar mutation by itself

Discrepancy response rule:
- when yfinance/provider dates are missing, contradictory, or not primary-confirmed, include official verification sites in the response/review packet
- for NVDA, include NVIDIA Investor Relations Events & Presentations, NVIDIA Newsroom, and SEC EDGAR

### `event_calendar_rollforward.py`

Status: live

Builds a read-only roll-forward review packet for `05. Intelligence/Event Calendar.md` by comparing dated ticker rows in the note against `tmp/earnings-calendar.json` provider dates, `tmp/earnings-date-source-confidence.json` confidence evidence, and tracked-universe policy in `tmp/portfolio-config.json`. It does **not** edit the vault note; it stages review-only proposals so provider-estimated next-quarter dates can be accepted, caveated, or rejected without silent canonical mutation.

Run:
```bash
python scripts/event_calendar_rollforward.py
```

Writes:
- `tmp/event-calendar-rollforward.json`
- `optional Markdown digest beside `tmp/event-calendar-rollforward.json``

### `event_calendar_apply.py`

Status: live bounded apply helper

Applies Randall-approved daily-chain Event Calendar maintenance. It consumes `tmp/event-calendar-rollforward.json` and `tmp/earnings-date-source-confidence.json`, then updates only the auto-managed provider-estimated earnings roll-forward block plus narrow timing-source wording for already-dated timing-sensitive events such as NVDA. Provider-estimated rows remain explicitly non-primary-confirmed unless primary evidence is attached. This helper does not authorize portfolio mutation, deployment mutation, watchlist promotion, sizing, trade execution, or owner-approval inference.

Run:
```bash
python scripts/event_calendar_apply.py --dry-run
python scripts/event_calendar_apply.py --apply
```

Writes:
- `tmp/event-calendar-apply.json`
- `optional Markdown digest beside `tmp/event-calendar-apply.json``
- `05. Intelligence/Event Calendar.md` only in `--apply` mode

### `trigger_sheet_refresh.py`

Status: live

Builds the machine-readable trigger layer from cached technical, deployment, macro, and earnings artifacts.

Run:
```bash
python scripts/trigger_sheet_refresh.py
```

Writes:
- `tmp/trigger-sheet.json`

### `post_earnings_prep.py`

Status: live

Builds a structured post-earnings interpretation packet from cached trigger, deployment, technical, earnings, and macro artifacts.

Run:
```bash
python scripts/post_earnings_prep.py
```

Writes:
- `tmp/post-earnings-prep.json`

### `post_earnings_note_targets.py`

Status: live

Translates post-earnings packets into selective candidate note updates and update intents.

Run:
```bash
python scripts/post_earnings_note_targets.py
```

Writes:
- `tmp/post-earnings-note-targets.json`

### `band_refresh.py`

Status: live

Reads `tmp/technical-refresh.json`, `tmp/portfolio-config.json`, and `tmp/earnings-calendar.json` to detect stale or miscalibrated entry bands. The proposal engine is now **Keltner-first, Dual-MA-gated, and SMA-envelope-audited**: it calculates EMA20/EMA50/SMA200, ATR20/ATRP20, trend-stack, method label, band type, band status, confidence, SMA-envelope audit levels, and earnings-state handling.

Read-only. Does not modify `portfolio-config.json` or the note layer. Routine eligible band maintenance is now handled by `auto_apply_entry_band_maintenance.py --apply`; proposals are `canonical_apply_eligible=true` only when they are execution-lane, band-defined, decision-grade workflow states with clear earnings state and approved band status (`IN_BAND` / `NEAR_BAND`). Earnings-imminent, earnings-timing-window, above-band-wait, below-stop/reclaim, watch-lane, underdefined, and non-execution proposals remain review-only / non-applyable.

Run:
```bash
python scripts/band_refresh.py
```

Writes:
- `tmp/band-proposals.json`

Depends on:
- `tmp/technical-refresh.json` (must be fresh)
- `tmp/portfolio-config.json` (must contain `band_last_set` in each entry_bands entry)

Band proposal maintenance workflow:
1. Run `band_refresh.py` - review `tmp/band-proposals.json` for any `needs_review=true` entries and their `entry_band_method`, `band_status`, `trend_stack`, `earnings_state`, and `canonical_apply_eligible` values.
2. Daily finance chains now run `auto_apply_entry_band_maintenance.py --apply` immediately after `band_refresh.py`. This applies only machine-eligible `canonical_apply_eligible=true` maintenance proposals to `tmp/portfolio-config.json` and `03. Portfolio/Execution Board.md`, with an audit at `tmp/auto-band-apply.json/.md`. The updater supports the current table-format Execution Board and the parser-compatible ticker sections; it updates band/stop/freshness text only and preserves lane/action-state/authority posture. After any real apply it must refresh WF72 entry/stop SQL reference metadata, rebuild the derived finance state, and rebuild WF84/WF85 before returning `ok`.
3. The Sunday finance chain runs `reference_band_note_sync.py --apply` after eligible auto-apply and before entry-band/status consumers. This writes fresh calculated reference bands for all complete tracked proposals into the Execution Board with restrictive authority labels and audit proof at `tmp/reference-band-note-sync.json/.md`.
4. Non-applyable proposals remain review-only/monitor-only. Automatic band maintenance and reference-band refreshes do not create trade, sizing, sleeve, cash, risk-rule, owner-approval, or execution authority.
5. Use `apply_band_update.py` only for explicit operator/manual override flows.

Regression guards:
```bash
python scripts/test_entry_band_automation.py
python scripts/test_auto_apply_entry_band_maintenance.py
python scripts/test_reference_band_note_sync.py
```
Checks same-day band-age honesty, workflow badge color rendering, earnings-imminent non-applyability, live protection for unsafe watch-lane / underdefined / timing-window / above-band-wait / below-stop proposals, and the scoped automatic apply/note-sync contract.

### `reference_band_note_sync.py`

Status: live weekly minimum reference-band note sync

Synchronizes fresh calculated reference bands from `tmp/band-proposals.json` into `03. Portfolio/Execution Board.md` without touching execution bands in `tmp/portfolio-config.json`. It is intended to keep the note layer from going stale while preserving the distinction between chart-context reference levels and gated execution bands.

Run:
```bash
python scripts/reference_band_note_sync.py --dry-run
python scripts/reference_band_note_sync.py --apply
```

Writes:
- `03. Portfolio/Execution Board.md` (`--apply` only)
- `tmp/reference-band-note-sync.json`

Chain placement:
- Sunday finance chain only, after `auto_apply_entry_band_maintenance.py --apply` and before `entry_band_fetch.py`
- provides the weekly minimum note-layer reference-band refresh; Command Center daily reference-band display is generated from `tmp/band-proposals.json` in `dashboard_payload.py`

Authority boundary:
- reference-band visibility only
- no execution-band mutation, no owner approval inference, no cash/risk-rule authority, no trade/account action; sizing/sleeve authority requires a separate exact gated apply artifact
- non-eligible names must carry restrictive labels such as reference-only, no execution entitlement, repair, below-stop, timing-window, above-band-wait, or watch/reference lane

### `apply_band_update.py`

Status: live

Implementation location:
- CLI entrypoint preserved at `scripts/apply_band_update.py`
- underlying implementation now lives at `scripts/operators/apply_band_update.py`

Manual override applier for band proposals generated by `band_refresh.py`. Reads `tmp/band-proposals.json`, presents each `needs_review=true` / `canonical_apply_eligible=true` proposal for confirmation (or accepts all eligible proposals with `--all`), writes approved changes back to `tmp/portfolio-config.json`, and writes a formatted summary to `tmp/band-update-log.txt` for pasting into the Execution Board. Routine eligible daily maintenance is now handled by `auto_apply_entry_band_maintenance.py --apply` inside the finance chains.

Approved updates now stamp `band_last_set` from the proposal/trading data date when available, instead of the current UTC wall-clock date, so Arizona-session note sync does not drift a day ahead.

Never auto-commits without human review unless `--all` is explicitly passed. For scheduled daily maintenance, prefer `auto_apply_entry_band_maintenance.py --apply`, which has narrower eligibility gates and writes an explicit audit artifact.

Run:
```bash
# Review and confirm each proposal interactively
python scripts/apply_band_update.py

# Apply only specific tickers
python scripts/apply_band_update.py --tickers ETN NVDA

# Preview without writing
python scripts/apply_band_update.py --dry-run

# Accept all needs_review proposals non-interactively
# Only canonical_apply_eligible=true proposals are included; unsafe/review-only proposals are skipped.
python scripts/apply_band_update.py --all
```

Writes:
- `tmp/portfolio-config.json` (updated entry bands and band_last_set dates)
- `tmp/band-update-log.txt` (formatted note-layer update summary)

After running: use `python scripts/band_note_sync.py` to generate an exact note-sync report, then update `03. Portfolio/Execution Board.md` from the helper output and `tmp/band-update-log.txt` if owner-note mutation is approved.

### `band_note_sync.py`

Status: live

Implementation location:
- CLI entrypoint preserved at `scripts/band_note_sync.py`
- underlying implementation now lives at `scripts/operators/band_note_sync.py`

Thin note-sync helper for entry-band upkeep. Compares `tmp/portfolio-config.json` against the canonical `03. Portfolio/Execution Board.md` and emits a review report showing exact band/stop lines that need syncing. It does not rewrite the note layer.

Run:
```bash
python scripts/band_note_sync.py
```

Writes:
- ``tmp/band-note-sync.json``
- `tmp/band-note-sync.json`

Use this after manual `apply_band_update.py` overrides or any direct band/config edit when you want a precise note-sync checklist. Routine eligible daily maintenance should use `auto_apply_entry_band_maintenance.py --apply`, which writes both the bounded note sync and `tmp/auto-band-apply.json/.md` audit proof.

### `validate_canonical_ownership.py`

Validates the note-layer ownership contract across `Coverage and Watchlist.md`, `Execution Board.md`, and `Portfolio Snapshot.md`. It checks that Coverage and Watchlist remains the consolidated universe/thesis surface, Execution Board owns execution/watch technical sections and compressed action-state rows, Snapshot no longer carries legacy thesis/entry/stop tables, archived pre-consolidation originals are preserved, and retired Watchlist / Technical / Trigger / Coverage Universe redirect stubs no longer live in active canon folders.

```powershell
python scripts/validate_canonical_ownership.py
python scripts/test_canonical_ownership.py
```

Outputs:

- `tmp/canonical-ownership-validation.json`

This is a canon-hygiene validator only. A clean result does not authorize portfolio mutation, deployment-state mutation, trading, or owner-approval inference.

### `generate_dashboard.py`

Status: live

Builds the normalized dashboard payload, computes the delta vs the prior run, runs trust and contradiction checks, and renders the staged dashboard surface from the static template.

Trust rules now enforced in the generator:
- degraded, partial, stale, missing, manual, and unconfirmed inputs must stay visible in payload and UI
- integrity warnings are emitted instead of being silently smoothed away
- business logic for trust, contradictions, compliance checks, and operator warnings lives in Python rather than the template where practical
- payload now carries both gated `executionBand` fields from `tmp/portfolio-config.json` and fresh `referenceBand` / `reference_bands.by_ticker` fields from `tmp/band-proposals.json`; reference bands are visibility-only and carry explicit no-approval/no-trade/no-sizing authority flags

Run:
```bash
python scripts/generate_dashboard.py
```

Writes:
- `tmp/dashboard-data.json`
- `tmp/dashboard-delta.json`
- `tmp/dashboard-last.json`
- `tmp/dashboard-validation.json`
- `tmp/veritas-command-center.html`

Depends on:
- `scripts/dashboard-template.html`
- upstream JSON artifacts in `tmp/`
- `tmp/portfolio-config.json`

### `validate_dashboard_state.py`

Status: live

Runs the dashboard trust and integrity validator without rendering HTML. Use this as the lightweight closure check before trusting the derived dashboard after note, config, or script changes.

Run:
```bash
python scripts/validate_dashboard_state.py --write
```

Optional strict mode:
```bash
python scripts/validate_dashboard_state.py --strict
```

Writes when `--write` is used:
- `tmp/dashboard-validation.json`

Exit codes:
- `0` = no critical issues
- `1` = warnings present in `--strict` mode
- `2` = critical contradictions detected

### `test_dashboard_acceptance.py`

Status: live

Runs the formal dashboard acceptance harness against controlled temporary mutations of the current `tmp/` artifacts, then restores the originals.

Covers:
- missing market field
- partial macro feed
- stale source
- contradiction surfacing
- earnings-date change visibility
- coherent blocker or stop or in-band state transition behavior

Run:
```bash
python scripts/test_dashboard_acceptance.py
```

Writes:
- `tmp/dashboard-acceptance-report.json`

Use this before declaring future dashboard hardening work accepted.

### `equity_visual_report.py`

Status: live reusable report generator

Builds a reusable visual Word report core for a public equity using live market data, analyst context, valuation metrics, real ticker-level annual history when available from yfinance, and auto-generated PNG panels staged in `tmp/`.

Run:
```bash
python scripts/equity_visual_report.py RTX
python scripts/equity_visual_report.py MSFT --out "06. Playbooks\\MSFT Visual Report.docx"
```

Writes:
- `tmp/<ticker>-price-panel.png`
- `tmp/<ticker>-history-panel.png`
- `tmp/<ticker>-visual-report-data.json`
- Word report output path, defaulting to `06. Playbooks/<TICKER> Visual Report - <date>.docx`

Notes:
- this is the reusable report core, not the full company-specific earnings or segment overlay system
- ticker-specific earnings, guidance, and segment panels can be layered on top when curated quarter data exists
- use this when you want a decision-grade visual report shell without rebuilding layout logic each time

### `equity_ppt_report.py`

Status: live generic first-version PowerPoint generator

Builds a PowerPoint deck from the generated visual-report assets and staged JSON payloads.

Run:
```bash
python scripts/equity_ppt_report.py RTX
```

Writes:
- `06. Playbooks/<TICKER> Deck - <date>.pptx`

Notes:
- current version now supports a generic deck path for any ticker with generated visual-report assets
- optional ticker-specific overlays such as earnings and segment panels are included automatically when matching PNG assets exist in `tmp/`
- use this when the user wants a presentation rather than a memo or Word report

### `premarket_snapshot.py`

Status: live intelligence-layer writer

Reads the cached morning-chain artifacts and produces the daily Pre-Market Snapshot deliverable. Quantitative sections auto-populate; no judgment slots are emitted at this stage - the daily executive brief is the place for narrative.

Run:
```bash
python scripts/premarket_snapshot.py
```

Reads:
- `tmp/market-state.json`
- `tmp/trigger-sheet.json`
- `tmp/dashboard-validation.json`
- `tmp/earnings-calendar.json`
- `tmp/dashboard-delta.json`

Writes:
- `01. Dashboards/Pre-Market Snapshot/YYYY-MM-DD.md`
- `tmp/premarket-snapshot.json`

Idempotency:
- If a session-written file already exists at the canonical path, the script writes to `YYYY-MM-DD-machine.md` so the human/agent version takes precedence.
- Re-runs over a machine-owned file overwrite in place.

### `postmarket_snapshot.py`

Status: live intelligence-layer writer

Reads the cached post-close artifacts and produces the daily Post-Market Snapshot - day summary, tracked-name day results, what changed since the prior dashboard run, open triggers for tomorrow, and tomorrow's catalysts.

Run:
```bash
python scripts/postmarket_snapshot.py
```

Reads:
- `tmp/market-state.json`
- `tmp/trigger-sheet.json`
- `tmp/dashboard-delta.json`
- `tmp/post-earnings-prep.json`
- `tmp/earnings-calendar.json`
- `tmp/dashboard-validation.json`

Writes:
- `01. Dashboards/Post-Market Snapshot/YYYY-MM-DD.md`
- `tmp/postmarket-snapshot.json`

Idempotency: same session-precedence rule as `premarket_snapshot.py`.

### `market_today_answer_packet.py`

Status: live local-only market-answer packet

Assembles the workspace's answer surface for "how did the market do today?" without fetching the web. It reads the post-close market/macro/postmarket artifacts, consumes the broad-index close/change table and same-day 2Y Treasury value from `market-state.json`, and includes a source-labeled driver digest that separates observed tape from supported macro/rates context instead of inventing single-cause narratives.

Run:
```bash
python scripts/market_today_answer_packet.py --write --validate
```

Reads:
- `tmp/market-state.json`
- `tmp/postmarket-snapshot.json`
- `tmp/macro-metrics-current.json`
- `tmp/macro-signal-spine.json`
- `data/market/price-snapshots/wf77-price-state-current.json`

Writes:
- `tmp/market-today-answer-packet.json`
- optional `tmp/market-today-answer-packet.md` with `--write-md`

Contract:
- `answer_readiness.can_answer_basic_market_day_without_web=true` means the workspace has enough local evidence for a basic post-close read.
- `answer_readiness.can_answer_full_market_close_recap_without_web=true` requires SPX/Dow/Nasdaq Composite/Russell same-day close/change rows, a normalized broad-index table, same-day 2Y Treasury value, and at least one source-backed market-driver digest row.
- `normalized_broad_index_daily_change_table` carries SPX, Dow, Nasdaq Composite, Nasdaq 100, Russell 2000, and ETF proxies with close, point change, percent change, source, and as-of date.
- `source_backed_market_driver_news_digest` is a review aid: each row must include `source_refs` and a `claim_boundary`; it may not convert tape correlation into unsupported causality.
- Review-only/local-only: no external fetch, news completeness claim, portfolio/canon mutation, ticker-card mutation, capital approval, paper/live/account action, external delivery, or owner approval inference.

### `daily_executive_brief.py`

Status: live intelligence-layer writer

Generates the autonomous Daily Executive Summary in the established 7-section template. Quantitative sections auto-populate (executive bottom line, execution context, what changed since the prior dashboard run, today's catalysts, closest actionable names with dollar/percent gap to band, trigger conditions, recommended actions). Confidence grade is derived from the dashboard validation summary.

Run:
```bash
python scripts/daily_executive_brief.py
```

Reads:
- `tmp/market-state.json`
- `tmp/trigger-sheet.json`
- `tmp/technical-refresh.json`
- `tmp/post-earnings-prep.json`
- `tmp/dashboard-validation.json`
- `tmp/deployment-check.json`
- `tmp/earnings-calendar.json`
- `tmp/dashboard-delta.json`

Writes:
- `01. Dashboards/Daily Executive Summary/YYYY-MM-DD.md`
- `tmp/daily-executive-brief.json`

Critical rule: never overwrite a session-written brief. If the canonical file exists and was NOT auto-generated by this script, the script writes to `YYYY-MM-DD-machine.md` so the agent version takes precedence.

### `summary_brief_packet.py`

Status: bounded review-only packet producer for AI-authored commercial briefs

Builds the machine-side handoff packet for a future bounded agent writer. This script does **not** write canonical notes or publish a brief by itself. It packages owner layers, trust posture, source artifact status, state summary, unresolved-truth constraints, and allowed / forbidden claim shapes for either the morning or post-close window.

Current live posture:
- the scheduled `morning` and `post-close` chains now run this packet producer automatically
- packets are generated under `tmp/` as review-only handoff objects
- any human-readable draft should live under `01. Dashboards/Review-Only Briefs/`
- no review brief is auto-delivered or auto-written to a canonical note yet

Run:
```bash
python scripts/summary_brief_packet.py --window morning
python scripts/summary_brief_packet.py --window post-close
```

Writes:
- `tmp/premarket-brief-input.json`
- `tmp/postclose-brief-input.json`

Key rule: output is `review_only` and `canonical_mutation_allowed: false`. The packet is a bounded writer input, not a second truth surface or an authorization surface.

### `summary_brief_lint.py`

Status: bounded validator for future AI-authored commercial briefs

Checks a draft brief against its packet contract. Current v1 coverage is intentionally simple and fail-closed: review-only posture, owner citation presence, unresolved-truth visibility, and forbidden authority / trade language.

Run:
```bash
python scripts/summary_brief_lint.py --packet tmp/premarket-brief-input.json --draft <draft-path>
```

Typical use:
- run after a bounded agent writer produces a draft
- block promotion if the draft bypasses owner notes or publishes state it does not own

### `weekly_macro_snapshot.py`

Status: live intelligence-layer writer

Generates the Weekly Macro Snapshot with 8 sections - regime assessment, Fed and rates, inflation/growth pulse, energy and commodities, FX, geopolitical flags, key events next week, regime posture and portfolio implication. Sections requiring qualitative narrative (inflation/growth detail, geopolitical flags, posture call) are emitted with explicit `_[judgment]_` placeholders. The script writes a machine sidecar until the macro-specific completion validator sees zero placeholders, a review-only authority statement, required DXY and high-yield credit-spread inputs, no source stop-line, no dashboard criticals, presentation-ready source freshness, and `capital_action_allowed=false`; dashboard warnings alone do not block a completed macro note. Oil lines include source timestamps/freshness caveats, key events include official FiscalData Treasury auction rows when available, and tariff/trade risk stays an explicit manual-review flag. A deployment-readiness surface with `presentation_allowed=false` but `stop_line=false` is treated as degraded/review-only deployment posture, not as a macro-note blocker.

Run:
```bash
python scripts/weekly_macro_snapshot.py
python scripts/weekly_macro_snapshot.py --validate "02. Markets/Weekly Macro Snapshot/YYYY-Www-machine.md"
```

Reads:
- `tmp/market-state.json`
- `tmp/macro-regime.json`
- `tmp/regime-scores.json`
- `tmp/deployment-readiness-surface.json`
- `tmp/earnings-calendar.json`

Writes:
- `02. Markets/Weekly Macro Snapshot/YYYY-Www.md` or `YYYY-Www-machine.md` (ISO week label; machine sidecar when completion gates block canonical write)
- `tmp/weekly-macro-snapshot.json` including placeholder/completion/gate metadata; broader portfolio/trade/account authority fields remain false even when `generated_macro_note_write_allowed=true`
- `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (weekly-macro-snapshot-judgment-fill.md)` with the bounded fill contract for the judgment layer

Idempotency: session-precedence rule plus machine-sidecar protection. Re-runs can overwrite an auto-generated incomplete machine sidecar, but if the machine sidecar appears human-owned or completed, the script preserves it and writes `YYYY-Www-machine-refresh.md` instead. `--validate` never regenerates or overwrites the markdown; it only updates `tmp/weekly-macro-snapshot.json` with validation status.

### `weekly_intelligence_brief.py`

Status: live intelligence-layer writer

Appends a structured, machine-populated section to `05. Intelligence/Weekly Intelligence Brief.md`. Mirrors the SOUL-defined weekly intelligence routine: macro pulse, energy sweep, geopolitical scan, earnings radar, analyst/institutional flow, technical check, sentiment gauge, recommended actions, and a review-only fundamental quality tracker. Sections requiring qualitative interpretation are emitted with `_[judgment]_` placeholders. Macro pulse now carries DXY plus credit spreads, energy carries oil timestamp/stale caveats, earnings radar adds official FiscalData Treasury auctions and a best-effort NVDA options/implied-move read, and geopolitical scan includes an explicit tariff/trade-risk manual-review flag.

Run:
```bash
python scripts/weekly_intelligence_brief.py
```

Reads:
- `tmp/market-state.json`
- `tmp/trigger-sheet.json`
- `tmp/deployment-check.json`
- `tmp/earnings-calendar.json`
- `tmp/post-earnings-prep.json`
- `tmp/technical-refresh.json`
- `tmp/portfolio-config.json`
- `tmp/regime-scores.json`
- `tmp/fundamental-metrics-current.json`
- `tmp/fundamental-metrics-validation.json`
- `05. Intelligence/Weekly Intelligence Brief.md` (read for idempotency)

Writes:
- `05. Intelligence/Weekly Intelligence Brief.md` (new section appended)
- `tmp/weekly-intelligence-brief.json`

Idempotency: if the current week's heading is already present in the WIB, the script prints a delta report and does NOT overwrite or duplicate the section. Same pattern as `weekly_review_skeleton.py`.

### `equity_pdf_report.py`

Status: live first-version PDF brief generator

Builds a fixed-layout PDF brief from the generated visual-report JSON and PNG assets.

Run:
```bash
python scripts/equity_pdf_report.py RTX
```

Writes:
- `06. Playbooks/<TICKER> PDF Brief - <date>.pdf`

Notes:
- this is the first PDF path for printable/shareable finance briefs
- it reuses the report JSON and generated PNG panels rather than duplicating the full research workflow
- use this when the user wants a clean PDF deliverable instead of Word or PowerPoint

### `regime_scoring_refresh.py`

Status: live controlled machine-companion ranking writer

Scores every tracked name against the current macro regime and writes the derived score artifact. It is also approved to update bounded scoring/ranking/freshness blocks in `02. Markets/Regime Scoring Matrix.md`.

Run:
```bash
python scripts/regime_scoring_refresh.py
```

Reads:
- `tmp/portfolio-config.json`
- `tmp/trigger-sheet.json`
- `tmp/technical-refresh.json`
- `tmp/earnings-calendar.json`
- `tmp/macro-regime.json`

Writes:
- `tmp/regime-scores.json`
- bounded sections of `02. Markets/Regime Scoring Matrix.md`

Authority:
- `Regime Scoring Matrix.md` is a controlled machine-companion ranking note, not final canonical deployment truth
- final action authority remains with `03. Portfolio/Execution Board.md`, `03. Portfolio/Portfolio Snapshot.md`, `07. Risk/Risk Rules.md`, and explicit owner approval
- no portfolio mutation, deployment-state mutation, trade execution, or owner-approval inference is allowed

Proof:
```bash
python scripts/test_regime_scoring_authority.py
```

### `positioning_ranking_refresh.py`

Status: live structured ranking artifact builder

Builds `tmp/positioning-ranking.json` as the structured capital-priority source for workbook exports and future positioning surfaces.

Run:
```bash
python scripts/positioning_ranking_refresh.py
```

Reads:
- `tmp/trigger-sheet.json`
- `tmp/deployment-check.json`
- `tmp/regime-scores.json`

Writes:
- `tmp/positioning-ranking.json`

Notes:
- merges regime score totals with deployability context and event risk into one ranking artifact
- intended to replace markdown parsing as the priority-rank source
- now wired into the refresh chains after `trigger_sheet_refresh.py`

### `workbook_export.py`

Status: live workbook export normalizer

Builds workbook-ready CSV exports from the current `tmp/` artifact stack for the minimum-viable Veritas operating workbook.

Run:
```bash
python scripts/workbook_export.py
```

Writes:
- `tmp/workbook-control-panel.csv`
- `tmp/workbook-watchlist-board.csv`
- `tmp/workbook-deployment-ranking.csv`
- `tmp/workbook-earnings-tracker.csv`
- `tmp/workbook-technical-drift.csv`
- `tmp/workbook-export-manifest.json`

Notes:
- normalizes raw machine labels into workbook vocabularies instead of exposing raw JSON states directly
- leaves unavailable fields blank rather than inventing fake precision
- intended to run after validation, not during half-built chains
- consumes `tmp/band-note-sync.json` when present so workbook surfaces can show note-parity gaps like missing technical-note sections without mutating the canonical note
- export manifest now carries per-export checksum, row-count, file-size, and source-freshness metadata so later workbook packaging can detect stray CSV edits instead of trusting `tmp/` blindly
- now wired into the `morning`, `post-close`, `post-earnings`, and `sunday` refresh chains immediately after `validate_dashboard_state.py --write`

### `workbook_template.py`

Status: live first-version workbook generator

Boundary note:
- stays in `scripts/` root because `python scripts/run_finance_refresh_chain.py <window> --build-workbook` can call it as a manual packaging tail

Builds the first `.xlsx` workbook template from the current workbook CSV exports.

Run:
```bash
python scripts/workbook_template.py
```

Manual chain-tail parity path:
```bash
python scripts/run_finance_refresh_chain.py morning --build-workbook
```

Reads:
- `tmp/workbook-control-panel.csv`
- `tmp/workbook-watchlist-board.csv`
- `tmp/workbook-deployment-ranking.csv`
- `tmp/workbook-earnings-tracker.csv`
- `tmp/workbook-technical-drift.csv`
- `tmp/workbook-export-manifest.json`

Writes:
- `06. Playbooks/Workbooks/Veritas Operating Workbook.xlsx`
- `tmp/workbook-build-validation.json`

Notes:
- uses a control-panel sheet plus four filtered operating-table sheets
- includes first-pass conditional formatting for deployable / blocked / stale / priority states
- includes a control-panel legend plus basic date/number formatting for cleaner scanning
- designed as the first workbook template, not a final styled reporting product
- consumes the live export layer rather than parsing raw JSON directly
- validates manifest row counts and SHA-256 checksums before packaging; missing or mismatched export inputs abort the build instead of silently packaging stray CSV state
- surfaces package age and upstream warning-grade status inside the workbook control panel so stale/manual packaging remains visible
- remains an operator-invoked staging package by default; scheduled workbook packaging stays fail-closed until the Workflow 5 trust contract is upgraded explicitly

### `veritas_technical_pass_validate.py`

Status: Workflow 29 pilot validator

Bounded sidecar validator for the `veritas-technical-pass` skill. Proves the skill's local file contract still exists and that the skill still names the canonical four-state model plus minimum technical-output requirements.

Run:
```bash
python scripts/veritas_technical_pass_validate.py --write
```

Writes when `--write` is used:
- `tmp/veritas-technical-pass-validation.json`

Exit codes:
- `0` = file contract and required skill clauses present
- `2` = missing referenced files or missing required contract clauses

Notes:
- this is a Tier 2 local-proof pilot, not a live chart or workflow-quality validator
- keeps scope intentionally narrow to the file-contract-heavy `veritas-technical-pass` skill

### `veritas_pm_department_validate.py`

Status: WF75 PM/PDF skill contract validator

Validates that `veritas-pm-department` and `veritas-pdf-brief` still preserve the PM weekly update, WF75 readiness timeline, enhancement roadmap, and PDF/presentation handoff contract. It also checks required WF75 source artifacts and verifies the WF75 readiness plan still keeps launch/customer/external/legal/source/trading authority false.

Run:
```bash
python scripts/veritas_pm_department_validate.py --write
```

Writes when `--write` is used:
- `tmp/veritas-pm-department-validation.json`

Exit codes:
- `0` = PM/PDF skill contract and WF75 source posture are intact
- `2` = required source, required phrase, or authority boundary is missing

### `wf75_pm_weekly_update.py`

Status: WF75 PM department weekly update generator

Builds the current internal WF75 PM weekly update from the service-led readiness plan, Retail SaaS operator packet, macro-event calendar, and PM skill validation. It writes a JSON proof surface; the Markdown review packet is optional when `--write-md` is explicitly supplied.

Run:
```bash
python scripts/wf75_pm_weekly_update.py --write --validate
```

Writes when `--write` is used:
- `tmp/wf75-pm-weekly-update.json`

Writes only when `--write-md` is also supplied:
- optional Markdown digest

Boundary:
- internal review/proof only
- no public launch, real customer data, external delivery, source-licensing claim, legal/compliance claim, portfolio/canon mutation, paper/live/account action, or owner approval inference

### `wf75_pm_readiness_pdf.py`

Status: WF75 PM readiness HTML/PDF renderer

Renders the current artifact-only WF75 PM readiness brief from the weekly update, artifact-only PM handoff, SQLite WAL control-plane manifest, operator console/control cockpit, and Retail SaaS operator packet. It writes an internal review PDF plus a machine-readable manifest; it is a PM/status surface, not a launch or customer-facing deliverable.

Run:
```bash
python scripts/wf75_pm_readiness_pdf.py --write --validate
python scripts/wf75_deliverable_packager.py --write --validate
```

Writes when `--write` is used:
- `tmp/wf75-pm-readiness-brief.json`
- `tmp/wf75-pm-readiness-brief.html`
- `tmp/wf75-pm-readiness-brief.pdf`

Boundary:
- internal artifact-only PM review
- no public launch, real customer data, external delivery, source-licensing claim, legal/compliance claim, portfolio/canon mutation, paper/live/account action, or owner approval inference

### `wf75_cron_automation_authority_plan.py`

Status: WF75 PM cron automation authority plan

Builds the durable plan for the paired WF75 weekly automation jobs. The isolated builder refreshes PM/readiness/operator proof artifacts. The main-session handoff inspects those artifacts and gives Randall a concise intelligence update only when something is material, stale, blocked, regressed, or decision-needed.

Run:
```bash
python scripts/wf75_cron_automation_authority_plan.py --write --validate
python scripts/wf75_cron_automation_authority_plan.py --write --write-md --validate
```

Writes when `--write` is used:
- `tmp/wf75-cron-automation-authority-plan.json`

Writes only when `--write-md` is also supplied:
- optional Markdown digest

Current cron pair:
- `WF75 PM Weekly Artifact Builder`: isolated, Friday 16:30 America/Phoenix, refreshes WF77 supplemental price evidence, bridge freshness, macro-event calendar, macro metrics, macro judgment draft, JSON-to-SQL promotion index, scenario library, renderer regression, service-state JSON, SQLite WAL control plane, operator console/control cockpit, PM validation, operator packet, weekly update, artifact-only handoff, PDF brief, and heartbeat pickup
- `WF75 PM Weekly Main Intelligence Handoff`: main session, Friday 16:40 America/Phoenix, reads the weekly update, macro-event calendar, macro metrics, macro judgment draft, JSON-to-SQL promotion index, operator console/control cockpit, PDF manifest/PDF, artifact-only handoff, PM validation, operator packet, and heartbeat pickup; Randall-facing intelligence only when material
- `Finance - Research Freshness and Opportunity Review`: isolated, weekdays 14:05 America/Phoenix, refreshes macro judgment draft and JSON-to-SQL promotion index before/after WF60/WF61 sector, ticker, research freshness, and small/mid-cap feeds so research opportunity cues inherit current macro posture and get fast derived lookup without gaining portfolio/capital/trade/customer/SQL-import authority
- `Finance - Sunday Research Opportunity Reset`: isolated, Sunday 09:35 America/Phoenix, runs `python scripts\sunday_research_opportunity_reset_cron_runner.py --write --validate` after the Sunday weekly refresh. The runner executes the macro-judgment-first WF60/WF61 reset sequence, writes `tmp/sunday-research-opportunity-reset-cron-runner.json`, and preserves review-only/no-authority boundaries.

Boundary:
- cron may produce proof, PM weekly updates, operator packets, and heartbeat handoff candidates
- main-session Veritas remains the intelligence integrator and escalation owner
- no public launch, real customer data, external delivery, source/legal/compliance readiness claim, SQL import, canon/portfolio mutation, paper/live/account action, config/auth/runtime mutation, or owner approval inference

### `cron_operator_ledger.py`, `cron_freshness_spine.py`, `cron_retire_merge_candidates.py`, `morning_control_digest.py`, `post_close_control_digest.py`, and `cron_notes_flattening_plan.py`

Status: JSON-first cron operator ledger, cron freshness spine, retire/merge candidate report, morning/post-close consolidation proof gates, and full cron-note flattening plan.

`cron_operator_ledger.py` reads the live cron store, run summaries, run-chain pointers, and current-window artifact index. It writes the current machine-readable cron operator status and an optional compact human digest.

`cron_freshness_spine.py` reads `tmp/cron-operator-ledger.json` and `tmp/operating-leverage-spine.json`, maps every enabled cron job to expected proof artifacts and freshness windows, and writes `tmp/cron-freshness-spine.json`. Main-session Veritas should inspect this first for cron freshness. The scorecard consumes it; the hardening pass fails if enabled jobs are unregistered or lack expected-artifact contracts.

`cron_retire_merge_candidates.py` reads the live cron store and produces `tmp/cron-retire-merge-candidates.json/.md`, a review-only candidate list for repairs, merges, scope reductions, and prompt simplification before adding more enabled jobs.

`morning_control_digest.py` reads the morning run summary, sector allocation matrix, current-window index, WF68 runtime/handoff proof, SQL coverage, cron ledger, PM state, and service-state SQLite caches into one proof packet. Use it as the proof gate before disabling the separate weekday morning handoff cron. It can report `NO_REPLY`, `MAIN_HANDOFF_REQUIRED`, or `BLOCKED`; it does not mutate cron state or apply any finance/customer action.

`post_close_control_digest.py` reads the post-close run summary, research freshness, paper-position SQLite, SQL coverage, canon-drift gate, cron ledger, PM state, and WF75 service-state surfaces into one escalation packet. Use it as the proof gate before disabling any additional post-close handoff cron. It can report `NO_REPLY`, `MAIN_HANDOFF_REQUIRED`, or `BLOCKED`; it does not mutate cron state or apply any finance/customer action.

`cron_notes_flattening_plan.py` reads the latest audit in `08. Audits/` and produces the full migration plan from heavy mixed cron Markdown to thin human Markdown plus structured JSON truth.

`weekday_morning_review_cron_runner.py`, `post_close_review_cron_runner.py`, `retail_automation_control_plane_cron_runner.py`, `wf78_daily_freshness_cron_runner.py`, `tier_a_late_session_opportunity_cron_runner.py`, and `sunday_research_opportunity_reset_cron_runner.py` are stable wrapper commands for formerly noisy isolated cron jobs. The morning and post-close runners execute the existing approved finance chains and classify proof without ad hoc final inspection; the morning runner also has a `--launch-background` mode. The retail runner refreshes dynamic quote proof before market-readiness validation, then classifies the P0 retail control-plane proof. The WF78 runner executes the daily freshness loop, market-readiness proof, decision factory, trade-grade OS runner, and cron-control refresh as one compact proof path. The Tier A late-session runner preserves the existing review/prep notification path while separating notification from execution authority. The Sunday research runner executes the WF60/WF61 opportunity reset and emits one contract artifact with step-level return codes. `handoff_first_proof_gate.py` classifies the scheduled handoff artifacts into proved/blocked/missing/stale/pending states and emits a repair packet for main-session/cron pickup. These wrappers are review-only except for already-approved scoped note-maintenance rails in the finance chains; they do not widen finance, customer, paper/live, account, cron, or runtime authority.

Cron model posture after the 2026-06-14 cron audit: heavy long-chain finance runners should use at least `openai/gpt-5.4` with explicit `thinking=high` and enough timeout headroom. Use `openai/gpt-5.4-mini` for short, deterministic, single-artifact proof jobs; use Mini `high` only when a wrapper still crosses a review/notification boundary. Spark remains bounded canary/proof only with `xhigh`.

Run:
```bash
python scripts/cron_operator_ledger.py --write --write-md --validate
python scripts/cron_freshness_spine.py --write --validate
python scripts/cron_retire_merge_candidates.py --write --write-md --validate
python scripts/morning_control_digest.py --write --write-md --validate
python scripts/post_close_control_digest.py --write --write-md --validate
python scripts/cron_notes_flattening_plan.py --write --write-md --validate
python scripts/weekday_morning_review_cron_runner.py --write --validate
python scripts/weekday_morning_review_cron_runner.py --launch-background --write --validate
python scripts/post_close_review_cron_runner.py --write --validate
python scripts/retail_automation_control_plane_cron_runner.py --write --validate
python scripts/wf78_daily_freshness_cron_runner.py --write --validate
python scripts/tier_a_late_session_opportunity_cron_runner.py --send --write --validate
```

Writes:
- `tmp/cron-operator-ledger.json`
- optional compact digest `optional Markdown digest beside `tmp/cron-operator-ledger.json``
- `tmp/cron-retire-merge-candidates.json`
- optional compact digest `tmp/cron-retire-merge-candidates.md`
- `tmp/post-close-control-digest.json`
- optional compact digest `tmp/post-close-control-digest.md`
- `tmp/cron-notes-flattening-plan.json`
- optional plan rendering `tmp/cron-notes-flattening-plan.md`
- `tmp/weekday-morning-review-cron-runner.json`
- `tmp/weekday-morning-review-cron-launcher.json`
- `tmp/post-close-review-cron-runner.json`
- `tmp/retail-automation-control-plane-cron-runner.json`
- `tmp/wf78-daily-freshness-cron-runner.json`
- `tmp/tier-a-late-session-opportunity-cron-runner.json`

Boundary:
- read-only planning/status proof
- no cron schedule/job mutation, archive move/delete, canon/portfolio mutation, customer/external delivery, paper/live/account action, or owner approval inference

### `wf77_weekly_analyst_refresh_cron_runner.py`

Status: WF77 stable weekly analyst-consensus cron runner.

Runs the weekly WF77 analyst consensus, ticker-card, finance coverage, router QA, artifact-index, and cron-ledger proof chain as one stable command so the scheduled job does not depend on a brittle long inline shell sequence.

Run:
```bash
python scripts/wf77_weekly_analyst_refresh_cron_runner.py --write --validate
```

Writes:
- `tmp/wf77-weekly-analyst-refresh-cron-runner.json`

Boundary:
- review-only analyst/coverage/router proof
- no canon/portfolio mutation, owner approval inference, sizing/sleeve/cash/risk-rule change, paper/live order, brokerage/account action, credential use, money movement, or config/auth/channel/service/runtime mutation

### `automation_trust_block.py`

Status: Workflow 29 pilot validator/normalizer

Builds and validates the first machine-readable automation trust block for the bounded `automation-hardening-manager` -> `cron-automation-manager` producer/consumer path.

Run:
```bash
python scripts/automation_trust_block.py --input scripts/testdata/automation-trust-block-approved.json --write
```

Writes when `--write` is used:
- `tmp/automation-trust-block.json`

Exit codes:
- `0` = trust block is valid and approved for the pilot's read-only consumer posture
- `2` = trust block is missing required fields or fails the pilot approval rules

Notes:
- `approve` is only valid when `trust_level=automation_ready`, `trust_gates_missing=[]`, and consumer posture is `read_only`
- this artifact is a bounded cron-facing trust gate, not a scheduler-expansion or note-mutation permission slip

### `cron_trust_block_consumer.py`

Status: Workflow 29 pilot fail-closed consumer

Reads the normalized automation trust block and exits non-zero unless cron may safely continue in the already-approved read-only posture.

Run:
```bash
python scripts/cron_trust_block_consumer.py --trust-block tmp/automation-trust-block.json --require-workflow "finance scheduled artifact generation pilot"
```

Exit codes:
- `0` = trust block explicitly allows the bounded read-only consumer posture
- `2` = missing/blocked/mismatched/unsafe trust state

Notes:
- intentionally narrow consumer: requires `status=ok`, `cron_read_allowed=true`, and `allowed_posture=read_only`
- fail closed when the trust block is absent, invalid, blocked, or workflow-mismatched

### WF38 promotion-review automation checks

Status: live bounded foundation, manual guardrail surface; review-verdict automation only

These scripts support the sector-expansion / promotion-review gate chain. Candidate packets remain review-only and do not authorize ticker promotion or canonical note mutation. `promotion_review_check.py` may now auto-approve the workspace review verdict only when the exact bounded gate pattern passes; it still does not authorize trade execution or automatic canonical note mutation.

Ownership / wiring posture:
- `promotion_review_check.py` and `ranking_shadow_canon_check.py` are retained as manual guardrails, not archive candidates.
- They are not chain/cron-owned by default; consider chain-tail wiring only after stable output contracts, clean execution proof, and no false stop-line behavior are proven.
- Manual runs may write review/guardrail artifacts under `tmp/`; those artifacts are review-only and do not grant deployment, canonical mutation, owner approval, or trade/account authority.

Run:
```bash
python scripts/candidate_packet_validator.py tmp/wf38-fixtures/passing_packet.json
python scripts/portfolio_integrity_check.py tmp/wf38-fixtures/passing_packet.json
python scripts/catalyst_window_check.py tmp/wf38-fixtures/passing_packet.json
python scripts/ranking_shadow_canon_check.py
python scripts/promotion_review_check.py --ticker JPM --write
python scripts/promotion_review_check.py --ticker NVDA --write
python scripts/test_wf38_authority.py
```

Files:
- `scripts/schemas/candidate_packet_schema.json`
- `scripts/candidate_packet_validator.py`
- `scripts/portfolio_integrity_check.py`
- `scripts/catalyst_window_check.py`
- `scripts/ranking_shadow_canon_check.py`
- `scripts/promotion_review_check.py`

Notes:
- `ALMOST DEPLOYABLE` does not require a Promotion Review Queue row by default.
- `DEPLOYABLE` / `DEPLOYABLE NOW` requires a queue row unless an explicit written threshold override exists.
- Catalyst status vocabulary is `clear`, `warning`, `blocked`, or `unknown`.
- Coverage and Watchlist is thesis/research context only; it is not the candidate-packet authority gate, deployment owner, universe-membership owner, or dashboard consistency surface.
- The candidate-packet thesis field is `thesis_evidence_source`; do not reintroduce canonical-thesis wording for research context.
- `promotion_review_check.py` auto-approves only the workspace review verdict when all of these are true: thesis `pass`, macro/regime `pass`, technical `pass`, catalyst `clear`, risk/sizing `warning`, action state `PROMOTION REVIEW`, execution lane, ALMOST/PROMOTION REVIEW workflow state, queue row present, all owner surfaces present, and no readiness blockers.
- Auto-approval leaves `canonical_mutation_allowed=false` and `trade_execution_authorized=false`; owner-note updates remain separate and explicit.
- Correlated-sleeve taxonomy is currently local to `portfolio_integrity_check.py` and should be centralized later if this chain widens.

### `run_finance_refresh_chain.py`

Status: live operating-window runner

Runs explicit refresh chains by operating window instead of treating the whole workflow as one generic pass.

Supported windows:

1. `morning`
   - data spine: `earnings_calendar_enrichment.py`, `earnings_date_source_confidence.py`, `event_calendar_rollforward.py`, `market_state_refresh.py`, `technical_refresh.py`, `regime_scoring_refresh.py`, `band_refresh.py`, `entry_band_fetch.py --all-tracked --html`, `generate_entry_band_status.py`, `deployment_check.py`, `trigger_sheet_refresh.py`
   - dashboard surface: `test_dashboard_acceptance.py`, `generate_dashboard.py`, `validate_dashboard_state.py --write`
   - intelligence layer: `premarket_snapshot.py` - writes `01. Dashboards/Pre-Market Snapshot/YYYY-MM-DD.md`
   - review-only brief packet: `summary_brief_packet.py --window morning` - writes `tmp/premarket-brief-input.json`
2. `post-close` (default)
   - data spine: `earnings_calendar_enrichment.py`, `earnings_date_source_confidence.py`, `event_calendar_rollforward.py`, `market_state_refresh.py`, `technical_refresh.py`, `regime_scoring_refresh.py`, `band_refresh.py`, `entry_band_fetch.py --all-tracked --html`, `generate_entry_band_status.py`, `deployment_check.py`, `trigger_sheet_refresh.py`, `post_earnings_prep.py`, `post_earnings_note_targets.py`
   - dashboard surface: `test_dashboard_acceptance.py`, `generate_dashboard.py`, `validate_dashboard_state.py --write`
   - intelligence layer: `postmarket_snapshot.py` - writes `01. Dashboards/Post-Market Snapshot/YYYY-MM-DD.md`; `market_today_answer_packet.py --write --validate` - writes `tmp/market-today-answer-packet.json` for local-only market-day Q&A readiness; `daily_executive_brief.py` - writes `01. Dashboards/Daily Executive Summary/YYYY-MM-DD.md` (machine-sidecar pattern preserves any session-written brief)
   - review-only brief packet: `summary_brief_packet.py --window post-close` - writes `tmp/postclose-brief-input.json`
3. `post-earnings`
   - `earnings_calendar_enrichment.py`
   - `earnings_date_source_confidence.py`
   - `event_calendar_rollforward.py`
   - `post_earnings_prep.py`
   - `post_earnings_note_targets.py`
   - `generate_dashboard.py`
   - `validate_dashboard_state.py --write`
4. `sunday`
   - data spine: full earnings + source-confidence + Event Calendar roll-forward + market + technical + regime score rebuild, plus `weekly_review_skeleton.py`, band, entry-band, deployment, trigger, post-earnings, `call_log_sync.py`
   - dashboard surface: `test_dashboard_acceptance.py`, `generate_dashboard.py`, `validate_dashboard_state.py --write`
   - intelligence layer: `weekly_macro_snapshot.py` - writes `02. Markets/Weekly Macro Snapshot/YYYY-Www.md`; `weekly_intelligence_brief.py` - appends a new section to `05. Intelligence/Weekly Intelligence Brief.md` (idempotent on week-heading); plus `postmarket_snapshot.py` and `daily_executive_brief.py` so the Sunday session opens with a primed daily brief as well
5. `full`
   - alias for `post-close` to preserve compatibility with the older one-shot command

Run:
```bash
python scripts/run_finance_refresh_chain.py
python scripts/run_finance_refresh_chain.py morning
python scripts/run_finance_refresh_chain.py post-earnings
python scripts/run_finance_refresh_chain.py --list
python scripts/run_finance_refresh_chain.py morning --dry-run
python scripts/run_finance_refresh_chain.py morning --build-workbook
python scripts/run_finance_refresh_chain.py post-earnings --dry-run --analyze --list-stages
python scripts/run_finance_refresh_chain.py post-earnings --dry-run --incremental --force --analyze
python scripts/run_finance_refresh_chain.py post-earnings --dry-run --parallel 2 --analyze
python scripts/chain_validator.py post-earnings --analyze --validate
```

Refresh-chain implementation modules:

- `chain_manifest.py` owns the operating-window manifests, expected outputs, stages, and dependency graph.
- `chain_validator.py` owns manifest summaries, stage listing, graph analysis, and the standalone validation CLI.
- `chain_state.py` owns run-state/log paths, atomic state writes, prior-state reads, and chain/step record construction.
- `chain_executor.py` owns command planning, incremental freshness checks, bounded parallel execution, subprocess handling, and failure recovery hooks.
- `run_finance_refresh_chain.py` stays the stable operator entrypoint and orchestration wrapper.

`--parallel` remains opt-in. Steps with `--apply`, cleanup/portfolio categories, recovery finalizers, or `parallel_safe=false` stay serial even when a larger worker count is requested. `--force` bypasses incremental freshness skips for the selected scope without changing authority boundaries.

### `dashboard-template.html`

Status: live support file

Static presentation shell consumed by `generate_dashboard.py`. Presentation belongs here, not business logic.

### `prompts/post_earnings_vault_update_v1.md`

Status: live support file

Reusable prompt artifact for the agent-driven post-earnings vault update pass.

## Generated artifact contract

`tmp/` is the machine-artifact surface. Active expected outputs currently include:
- `tmp/technical-refresh.json`
- `tmp/market-state.json`
- `tmp/band-proposals.json` - band staleness proposals from `band_refresh.py`
- `tmp/band-update-log.txt` - formatted note-layer summary from `apply_band_update.py`
- `tmp/deployment-check.json`
- `tmp/earnings-calendar.json`
- `tmp/trigger-sheet.json`
- `tmp/post-earnings-prep.json`
- `tmp/post-earnings-note-targets.json`
- `tmp/portfolio-config.json`
- `tmp/dashboard-data.json`
- `tmp/dashboard-delta.json`
- `tmp/dashboard-last.json`
- `tmp/dashboard-validation.json`
- `tmp/dashboard-acceptance-report.json`
- `tmp/veritas-command-center.html`
- `tmp/premarket-snapshot.json` - structured summary from `premarket_snapshot.py`
- `tmp/postmarket-snapshot.json` - structured summary from `postmarket_snapshot.py`
- `tmp/daily-executive-brief.json` - structured summary from `daily_executive_brief.py`
- `tmp/weekly-macro-snapshot.json` - structured summary from `weekly_macro_snapshot.py`
- `tmp/weekly-intelligence-brief.json` - structured summary from `weekly_intelligence_brief.py`
- `tmp/run-summary-morning.json` - workflow-level closure summary for the morning window
- `tmp/run-summary-post-close.json` - workflow-level closure summary for the post-close window
- `tmp/run-summary-post-earnings.json` - workflow-level closure summary for the post-earnings window
- `tmp/run-summary-sunday.json` - workflow-level closure summary for the sunday window
- `tmp/current-window-artifacts.json` - review-only current-window artifact index and role-alias map; `.md` is optional/on-demand with `--write-md`
- `tmp/cron-operator-ledger.json` - JSON-first current cron operator status; `.md` is the compact generated digest
- `tmp/cron-notes-flattening-plan.json` - full migration plan for thinning cron Markdown into JSON-first truth plus human digests
- `tmp/workbook-build-validation.json` - manifest/checksum validation result for workbook packaging

Generated artifacts are evidence and staging surfaces. They do not outrank the canonical note layer.
Report visuals generated into `tmp/` are presentation assets, not canonical research truth by themselves.

### `operator_packet.py`

Status: active governance/orchestration validator

Builds standardized recovery/operator packets for the five high-risk long-work lanes:
SQL/WF78, Retail SaaS/WF75, WF68 alerts, WF67 paper, and bounded portfolio/canon maintenance.

```bash
python scripts/operator_packet.py --workflow all --write --validate
```

### `long_work_packet_linter.py`

Status: active long-work plan and lane-contract validator

Use this before spawning or opening long work that needs helper routing, model routing, write leases, multi-surface implementation, or closeout proof. It validates the plan/lease/closeout shape; it does not track runtime progress.

```bash
python scripts/long_work_packet_linter.py --packet tmp/packet.json --stage preflight --validate
python scripts/long_work_packet_linter.py --packet tmp/packet.json --stage spawn --validate
python scripts/long_work_packet_linter.py --packet tmp/packet.json --stage closeout --validate
```

Boundary: review/proof only. It does not grant cron schedule mutation, runtime/config mutation, finance/canon/portfolio mutation, paper/live execution, external delivery, delete/archive, or owner approval.

### `long_work_job_runtime.py` and `long_work_job_status_packet.py`

Status: active generic checkpoint/status contract for long local jobs

Use these for provider-backed, full-source, or long-running local scripts that may exceed a single OpenClaw/Codex foreground tool call. The runtime stores per-job status under `state/long-work-jobs/<job-id>/status.json`; the packet writes `tmp/long-work-job-status-packet.json` and `.md` for WF88, future sessions, and main-session resume decisions.

```bash
python scripts/long_work_job_runtime.py validate --write --pretty
python scripts/long_work_job_status_packet.py --write --write-md --validate
```

Job contract requirements:
- publish `job_id`, `owner_workflow`, `job_type`, `profile`, progress counts, validation state, and `next_resume_command`
- use bounded resume commands for work that can exceed tool/session timeouts
- classify `complete`, `warning`, `blocked`, `cancelled`, `created`, `running`, `paused`, or `resumable`
- keep authority flags false for cron schedule mutation, runtime/config mutation, SQL/source mutation, finance/canon/portfolio/cash/sizing/risk mutation, paper/live/brokerage/account action, external delivery, delete/archive/move, raw prompt/tool capture, model-training claims, and owner approval inference

WF88 consumption:
- `wf88_os2_control_packet.py` consumes `tmp/long-work-job-status-packet.json`
- `wf88_wiki_synthesis_packet.py` includes long-work status in the durable route map
- blocked long-work jobs block WF88 validation; resumable/stale active jobs remain warning-visible with next safe action

### `vector_memory_ollama_job_runner.py`

Status: active resumable vector-memory indexing runner

Use this instead of a single foreground `vector_memory_index.py --embedding-provider ollama` run when indexing medium/full sources through Ollama embeddings. It snapshots sources/chunks, checkpoints progress, reuses unchanged chunks, and resumes in bounded slices.

```bash
python scripts/vector_memory_ollama_job_runner.py start --profile medium --embedding-provider ollama --embedding-model nomic-embed-text:latest --max-seconds 240 --batch-size 8 --write --validate
python scripts/vector_memory_ollama_job_runner.py resume --profile medium --embedding-provider ollama --embedding-model nomic-embed-text:latest --max-seconds 240 --batch-size 8 --write --validate
python scripts/vector_memory_ollama_job_runner.py validate --profile medium --write --validate
python scripts/vector_memory_ollama_job_runner.py query --profile medium --query "recursive self improvement approval gate" --limit 5 --write --validate
python scripts/vector_memory_ollama_job_runner.py start --profile full --embedding-provider ollama --embedding-model nomic-embed-text:latest --max-seconds 240 --batch-size 8 --write --validate
python scripts/vector_memory_ollama_job_runner.py resume --profile full --embedding-provider ollama --embedding-model nomic-embed-text:latest --max-seconds 240 --batch-size 8 --write --validate
python scripts/vector_memory_ollama_job_runner.py promote --profile full --write --validate
```

Profiles:
- `medium`: targeted WF74/WF88/token/PM/memory sources
- `full`: full default vector-memory source set
- `test`: local test profile; use `--embedding-provider hash` for deterministic tests

Promotion rule: medium Ollama can be clean production-search evidence when validation is ok. Full-source Ollama can become the default local derived memory index only when validation is ok, stale source hashes are zero, semantic query smoke passes, and the hash/FTS default is preserved first as `tmp/vector-memory-hash-fallback.sqlite`. If volatile generated packets create `stale_source_hashes`, rerun after producer quiescence; do not suppress the stale-source guard.

Boundary: derived local search index only. No canon, portfolio, finance execution, cron schedule, runtime/config, external delivery, model-training, raw prompt/tool capture, delete/archive, or owner-approval authority.

### `retrieval_quality_scorecard.py` and `retrieval_live_eval.py`

Status: separate compatibility-contract and live-discrimination evaluation routes

`retrieval_quality_scorecard.py` validates authority, freshness, precedence, parseability, and source-selection behavior over fixture-supplied candidate sets. Its 42-case result is useful contract-regression proof, but it does not query `vector-memory.sqlite`, measure recall/MRR, test paraphrase retrieval, calibrate abstention, or rank embedding providers.

`retrieval_live_eval.py` is the isolated live pilot. It verifies a frozen 10-source manifest, builds distinct hash+FTS and Ollama semantic+FTS SQLite indexes from identical chunks, runs an FTS-only ablation, scores 19 draft fixtures with recall@1/3/5, MRR, and named-distractor error rate, rejects provider fallback/stale/mismatched indexes, runs three mutation sensitivity checks, and appends compatible-run metrics to `data/state-history/retrieval-live-eval.jsonl`.

```powershell
python scripts\retrieval_quality_scorecard.py --write --write-md --validate
python scripts\test_retrieval_quality_scorecard.py
python scripts\retrieval_live_eval.py --write --write-md --validate
python scripts\test_retrieval_live_eval.py
```

Live-eval outputs:

- `tmp/retrieval-live-eval.json` and `.md`
- `tmp/retrieval-live-eval-hash.sqlite`
- `tmp/retrieval-live-eval-semantic.sqlite`
- `tmp/retrieval-live-eval-mutation.sqlite` (deliberately corrupted proof residue; never use for retrieval)
- `data/state-history/retrieval-live-eval.jsonl`

Trust rule: the pilot remains `draft_review_required` even when validation is clean. Absent-answer rows are `abstention_uncalibrated`, the gold labels still require source-open human review, and no provider-promotion threshold exists. The harness never writes the protected default vector index and creates no finance, canon, portfolio, capital, paper/live, config/runtime, external-delivery, or approval authority.

Outputs:
- `tmp/operator-packets/operator-packet-index.json`
- `tmp/operator-packets/sql-wf78.json`
- `tmp/operator-packets/retail-saas-wf75.json`
- `tmp/operator-packets/wf68-alerts.json`
- `tmp/operator-packets/wf67-paper.json`
- `tmp/operator-packets/wf64-wf56-bounded-portfolio-canon.json`

These packets standardize owner surface, current phase, next safe action, proof artifacts, read-only checks, proof-refresh validators, stop lines, missing trust gates, and helper-lane contracts. They are recovery/proof surfaces only. They do not grant import, launch, external delivery, paper/live execution, canon/portfolio mutation, account action, owner approval, or cleanup authority.

### `parallel_repeatable_work_orchestrator.py`

Status: active review-only orchestration wrapper

Runs the repeatable WF78/WF67/macro work bundle:

```bash
python scripts/parallel_repeatable_work_orchestrator.py --write --validate
```

Outputs:
- `tmp/parallel-repeatable-work-orchestration.json`
- `tmp/macro-event-guard-loop.json`
- `tmp/wf78-owner-card-prep-loop.json`
- `tmp/wf78-tier-a-evidence-repair-batch.json`
- `tmp/alpaca-paper-readiness/main-session-cards/*.owner-card.json`

It reuses existing macro, ticker-card refresh, WF78 rerouting/reducer, and WF67 request-generator scripts. It is non-executing and review-only: no capital deployment, paper/live order execution, brokerage/account action, money movement, canon/portfolio mutation, SQL-canon mutation, customer output, or owner approval inference.

### `band_hygiene_freshness_controller.py`

Status: finance band hygiene and quote-freshness controller.

Refreshes quote proof, market execution-readiness hardening, technicals, and `band_refresh.py`, then runs the existing `auto_apply_entry_band_maintenance.py` gate in dry-run mode or bounded apply mode. Apply mode is limited to proposals already marked `canonical_apply_eligible=true`; it reruns `band_refresh.py` after apply so downstream cards and the sync spine do not read stale pre-apply band debt.

```bash
python scripts/band_hygiene_freshness_controller.py --write --write-md --validate
python scripts/band_hygiene_freshness_controller.py --apply-eligible --write --write-md --validate
```

Outputs:
- `tmp/band-hygiene-freshness-controller.json`
- `tmp/band-hygiene-freshness-controller.md`
- refreshed `tmp/intraday-alerts/quote-snapshot-proof.json`
- refreshed `tmp/market-execution-readiness-cron-hardening.json`
- refreshed `tmp/technical-refresh.json`
- refreshed `tmp/band-proposals.json`
- refreshed `tmp/auto-band-apply.json`

The morning paper recommendation cron consumes this controller before building cards. It is band/quote hygiene only: no capital approval, no paper/live order action, no brokerage/account action, no money movement, no cash/sizing/sleeve/risk-rule mutation, and no owner approval inference.

### `capital_deployment_band_integrity_validator.py`

Status: report-only capital-review band drift validator.

Compares entry bands and stops across the WF78 capital-review queue, finance decision factory, current capital-deployment recommendation proposals, and WF67 owner cards:

```bash
python scripts/capital_deployment_band_integrity_validator.py --write --write-md --validate
```

Outputs:
- `tmp/capital-deployment-band-integrity-validator.json`
- `tmp/capital-deployment-band-integrity-validator.md`

The validator can report `status=blocked` while `validation.status=ok`; that means the script ran correctly and found domain drift that must be fixed by the owning generator/source before approval-card use. It is review-only: no source-card mutation, WF67 request mutation, canon/portfolio mutation, capital approval, paper/live action, brokerage/account action, cash/sizing mutation, or owner approval inference.

Permanent prevention rule: any workflow that sends or stages approval-card/radar output must rebuild or verify this validator after regenerating WF78 capital-review queue, capital recommendation proposals, owner cards, WF67 request artifacts, and the finance decision factory. A one-off ticker card refresh is not sufficient.

### `morning_paper_deployment_recommendation_builder.py`

Status: weekday morning review-only WF78/WF67 approval-card builder.

Runs the morning paper deployment recommendation path after quote freshness is available. It refreshes or consumes WF68 quote proof, market execution-readiness hardening, the band hygiene/freshness controller, the WF78 capital-review queue, owner-card preparation, WF67 request artifacts, and the decision factory, then writes a single approval-card summary:

```bash
python scripts/morning_paper_deployment_recommendation_builder.py --write --write-md --validate
```

Scheduled cron must run the full pre-open builder before the 06:42 MST radar, with a second full refresh around midday after WF87 command-center proof:

```bash
python scripts/morning_paper_deployment_recommendation_builder.py --write --write-md --validate
```

The WF85 paper-deployment Telegram radar is consolidated to 06:42 MST and 11:30 MST. Before each digest/send, `wf85_paper_deployment_telegram_cron_runner.py` rebuilds `morning-paper-deployment-recommendation-cards` and `capital-deployment-band-integrity-validator`, then surfaces any domain blocker instead of sending stale "near deployment" language.

The radar runner uses the fast ledger-only builder verification by default:

```bash
python scripts/wf85_paper_deployment_telegram_cron_runner.py --write --validate
```

Use `--full-builder-refresh` only for manual deep proof. Cron should not run the full provider/card-refresh chain inline with Telegram delivery because that can create silent long turns; the standalone builder owns that work.

Outputs:
- `tmp/morning-paper-deployment-recommendation-cards.json`
- `tmp/morning-paper-deployment-recommendation-cards.md`
- `tmp/band-hygiene-freshness-controller.json`
- `tmp/band-hygiene-freshness-controller.md`
- `tmp/finance-decision-sync-spine.json`
- `tmp/finance-decision-sync-spine.md`
- `tmp/capital-deployment-band-integrity-validator.json`
- `tmp/capital-deployment-band-integrity-validator.md`
- refreshed `tmp/wf78-capital-review-queue.json`
- refreshed `tmp/wf78-owner-card-prep-loop.json`
- refreshed eligible `tmp/alpaca-paper-readiness/main-session-cards/*.owner-card.json`
- refreshed eligible `tmp/alpaca-paper-readiness/paper-trade-request.wf78-owner-card-prep-*.json`

The runner requires fresh quote snapshots for clean approval cards and blocks candidates with repair posture, band-review-required posture, confidence-gate issues, promotion vetoes, non-IN_BAND prices, missing WF67 request artifacts, or non-false authority flags. It then writes `finance_decision_sync_spine.py` so WF78 routing, WF68 alerts, WF67 requests, band/repair posture, paper positions, and morning cards converge into one derived decision-state surface. It is approval-card preparation only: no paper/live submit, cancel, sell, modify, approval, brokerage/account action, money movement, portfolio/canon mutation, or owner approval inference.

### `finance_decision_sync_spine.py`

Status: finance OS decision-state synchronization spine.

Builds one derived ticker state ledger from morning paper cards, WF78 capital-review queue, WF68 alerts, WF67 request artifacts, promotion/confidence gates, band/repair proposals, paper positions, and the finance decision factory:

```bash
python scripts/finance_decision_sync_spine.py --write --write-md --validate
```

Outputs:
- `tmp/finance-decision-sync-spine.json`
- `tmp/finance-decision-sync-spine.md`

Primary state labels include `approval_card_clean`, `paper_request_ready_pending_exact_approval`, `in_band_not_clean`, `repair_mode`, `promotion_vetoed`, `below_stop_or_invalidation`, `no_chase`, `wf67_request_blocked`, `blocked_missing_freshness`, `alert_only`, `paper_position_monitor`, and `evidence_repair`. The spine is derived review-only state; it cannot generate orders, mutate WF67 requests, approve capital, mutate portfolio/canon state, touch accounts, or infer owner approval.

### `repeatable_work_closeout.py`

Status: active closeout wrapper

Runs the standard closeout chain after repeatable workflow work:

```bash
python scripts/repeatable_work_closeout.py --write --validate
```

The chain refreshes workflow routing, artifact scoring, WF78 event rerouting, truth-surface inventory, PM sidecar retirement proof, cron control, OTEL ops, fast-path QA, artifact index, and PM control state in the validated order. `--validation-budget micro|narrow` keeps the normal path compact; DB lifecycle and WF75 major closeout stay reserved for shared/major routes. It is validation/proof only and performs no archive/delete, config/auth/runtime mutation, capital/execution action, or approval inference.

### `finance_decision_factory.py`

Status: active review-only candidate-to-card spine (Finance Decision Factory)

Standardizes the candidate-to-card loop into one repeatable runner:

```bash
python scripts/finance_decision_factory.py --write --validate
python scripts/finance_decision_factory.py --ledger-only --write --validate
python scripts/finance_decision_factory.py --closeout --recommend-qa-lane --write --validate
```

It chains existing scripts as a thin spine — `parallel_repeatable_work_orchestrator.py` (candidate prep), `wf78_evidence_repair_batch_runner.py` (evidence repair), and optionally `control_closeout_bundle.py` (`--closeout`) — then builds a normalized decision ledger (`tmp/finance-decision-factory.json`) joining the capital-review queue, owner-card-prep loop, and Chief Intelligence promotion gate per candidate. Each candidate is assigned a disposition: `owner_card_and_wf67_request_ready`, `gate_deferred`, `owner_card_ready_wf67_blocked`, `not_card_preparable`, or `pending`, with an explicit `blocked_reason` when deferred.

For closed-market/weekend recommendation work, refresh the final quote overlay first:

```powershell
python scripts/post_close_final_quote_ledger.py --write --validate
python scripts/ticker_card_freshness_owner_runner.py --skip-provider-refresh --full-answer-mode changed --write --validate
python scripts/wf78_capital_review_queue.py --write --write-db --validate
python scripts/finance_decision_factory.py --ledger-only --write --validate
```

The post-close finance chain runs this sequence automatically. `tmp/post-close-final-quote-ledger.json` is review-only quote evidence; after it is written, the chain rebuilds ticker cards through `ticker_card_freshness_owner_runner.py --skip-provider-refresh --full-answer-mode changed` so card prices consume the same closed-market price overlay before downstream recommendation surfaces run. The changed-mode digest runs the slower WF85 full-answer rebuild only when card/source semantics changed. This does not mutate canon, portfolio notes, SQL canon, or execution authority.

Flags: `--ledger-only` (skip the chain, rebuild ledger from current artifacts), `--repair-tier {A,B,C,all}` (default A), `--repair-limit` (default 10; must be greater than 0), `--repair-cursor` (default 0; must be 0 or greater), `--skip-provider-refresh`, `--closeout`, `--recommend-qa-lane` (when explicitly requested, refreshes and surfaces — never spawns — a parallel WF72 A2 read-only QA lease/spawn via `parallel_lane_recommender.py`), `--out`.

It does not build card content itself (the orchestrator owns that); it is a spine + normalized ledger. Review-only: `capital_deployment_approved`, `trade_or_execution_approved`, `paper_or_live_execution_allowed`, and `owner_approval_inferred` all stay false. No capital deployment, order execution, brokerage/account action, money movement, canon/portfolio mutation, or owner approval inference.

### `wf78_evidence_repair_batch_runner.py`

Status: active review-only evidence-repair burn-down

Turns the ~199-card stale evidence debt into a controlled, resumable queue:

```bash
python scripts/wf78_evidence_repair_batch_runner.py --tier A --limit 10 --write --validate
python scripts/wf78_evidence_repair_batch_runner.py --tier A --cursor 10 --refresh --write --validate
```

It reads the repair queue from `tmp/wf78-evidence-drag-reduction.json`, selects a tier-ordered batch (Tier A challenged-first, then Tier B, Tier C), measures global stale debt before and after, and emits a resumable cursor (`next_cursor`, `remaining`). With `--refresh` it reruns the refresh chain (`finance_ticker_card_refresh_gate.py` + `wf78_auto_tier_router.py` + `wf78_event_triggered_rerouting.py` + `wf78_evidence_drag_reducer.py`) so WF78 routing reflects each repaired batch; `--skip-provider-refresh` keeps it offline. Output: `tmp/wf78-evidence-repair-batch.json`.

Review-only: no card mutation, capital deployment, execution, account action, or approval inference.

### `wf78_evidence_family_repair_runner.py`

Status: active review-only family-first evidence repair router

Targets repeated stale-evidence families across the WF78 queue so broad debt, especially `price_band_stop`, is handled as a reusable lane instead of one ticker at a time:

```bash
python scripts/wf78_evidence_family_repair_runner.py --family price_band_stop --write --validate
python scripts/wf78_evidence_family_repair_runner.py --family price_band_stop --tier A --cursor 0 --limit 25 --write --validate
```

It consumes `tmp/wf78-evidence-drag-reduction.json`, selects a resumable family batch, classifies each row by repair mode (`refresh_remeasure_quote`, `source_open_entry_stop_required`, `thin_monitor_source_open_entry_stop_required`, `position_sizing_readiness_surface_required`, or `deployment_readiness_surface_required`), and writes `tmp/wf78-evidence-family-repair.json`. `--refresh` runs only the existing review-only refresh/remeasure chain. The runner makes structural gaps explicit: thin-monitor `price_band_stop` rows need source-open entry/stop evidence or promotion before material claims; they are not fixed by fabricating bands.

Review-only: no ticker-card mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_source_open_repair_executor.py`

Status: active review-only source-open repair execution proof

Turns WF78 family-repair classification into concrete repair dispositions for material Tier A/B rows:

```bash
python scripts/wf78_source_open_repair_executor.py --tier all --write --validate
python scripts/wf78_source_open_repair_executor.py --tier A --write --validate
python scripts/wf78_source_open_repair_executor.py --tier all --include-tier-c --write --validate
```

It reads `tmp/wf78-evidence-drag-reduction.json`, `data/finance/wf78-source-open-official-registry.json`, and current ticker cards. Output: `tmp/wf78-source-open-repair-execution.json`. It separates `needs_position_sizing_surface`, `needs_owner_entry_stop_source`, `needs_source_artifact`, `thin_monitor_hold`, and `repaired_from_owner_source` so source-open debt is not confused with quote refresh or fabricated band/stop values.

Review-only: no ticker-card mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_source_open_work_packet.py`

Status: active review-only source-open repair work-packet generator

Turns source-open repair dispositions into parallel-safe repair packets:

```bash
python scripts/wf78_source_open_work_packet.py --write --validate
python scripts/wf78_source_open_work_packet.py --batch-size 8 --write --validate
```

It reads `tmp/wf78-source-open-repair-execution.json`, `tmp/wf78-ticker-freshness-ledger.json`, `tmp/finance-decision-factory.json`, `tmp/deployment-readiness-surface.json`, and current ticker cards. Output: `tmp/wf78-source-open-work-packets.json`. Packets group rows such as `position_sizing_surface-01`, `source_artifact_capture-01`, and `deployment_readiness_surface-01` with collision groups, parallel-safety flags, source lineage, current band context, and acceptance criteria.

Review-only: no ticker-card mutation, deployment-surface mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_position_sizing_surface_review.py`

Status: active review-only position-sizing/deployment-readiness packaging

Builds concrete review rows from the `position_sizing_surface` packets:

```bash
python scripts/wf78_position_sizing_surface_review.py --write --validate
```

It reads `tmp/wf78-source-open-work-packets.json`, `tmp/deployment-readiness-surface.json`, `tmp/finance-decision-factory.json`, and current ticker cards. Output: `tmp/wf78-position-sizing-surface-review.json`. The artifact packages source-backed entry/stop lineage, current band context, deployment-surface context, readiness impact, residual blockers, and non-executing review actions for the 25 sizing/deployment rows.

Review-only: no ticker-card mutation, deployment-surface mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_deployment_readiness_review.py`

Status: active review-only deployment-readiness singleton packaging

Builds deployment-readiness review rows from source-open work packets:

```bash
python scripts/wf78_deployment_readiness_review.py --write --validate
```

It reads `tmp/wf78-source-open-work-packets.json`, `tmp/deployment-readiness-surface.json`, and current ticker cards. Output: `tmp/wf78-deployment-readiness-review.json`. It currently packages the LIN singleton and either marks it ready for non-executing deployment-readiness review or preserves the blocker.

Review-only: no deployment-surface mutation, ticker-card mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_position_sizing_integration_proposal.py`

Status: active review-only position-sizing integration proposal packet

Builds not-applied integration proposals from source-backed sizing/deployment rows:

```bash
python scripts/wf78_position_sizing_integration_proposal.py --write --validate
```

It reads `tmp/wf78-position-sizing-surface-review.json` and `tmp/wf78-deployment-readiness-review.json`. Output: `tmp/wf78-position-sizing-integration-proposal.json`. Rows are split into `tier_a_ready`, `tier_b_ready`, and `blocked`; every row stays `not_applied_review_only`.

Review-only: no ticker-card mutation, deployment-surface mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_tier_a_owner_readiness_proposal.py`

Status: active non-executing Tier A owner-readiness proposal packet

Builds owner-review framing for Tier A rows:

```bash
python scripts/wf78_tier_a_owner_readiness_proposal.py --write --validate
```

It reads `tmp/wf78-position-sizing-integration-proposal.json` and writes `tmp/wf78-tier-a-owner-readiness-proposals.json`. It separates in-band review candidates from no-chase, wait/reclaim, and invalidation review rows so readiness language does not overstate deployability.

Review-only: no ticker-card mutation, deployment-surface mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_source_artifact_capture_review.py`

Status: active review-only source-artifact capture blocker queue

Builds capture-review rows from the source artifact packet:

```bash
python scripts/wf78_source_artifact_capture_review.py --write --validate
```

It reads `tmp/wf78-source-open-work-packets.json`, current ticker cards, and `data/finance/wf78-source-open-official-registry.json`. Output: `tmp/wf78-source-artifact-capture-review.json`. Current proof shows 10 Tier B rows are real blockers: no source lineage and no official registry entry are available, so they require manual/source-open capture rather than fabricated values.

Review-only: no source values copied into cards, no ticker-card mutation, deployment-surface mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_source_capture_requirements_queue.py`

Status: active review-only source-capture requirements queue

Builds exact requirements for blocked source-capture names:

```bash
python scripts/wf78_source_capture_requirements_queue.py --write --validate
```

It reads `tmp/wf78-source-artifact-capture-review.json`, current ticker cards, and `data/finance/wf78-source-open-official-registry.json`. Output: `tmp/wf78-source-capture-requirements-queue.json`. It lists required company IR URL, latest earnings source, owner entry/stop source, and registry-entry needs for each blocked ticker.

Review-only: no source values copied into cards, no ticker-card mutation, registry mutation, deployment-surface mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_official_source_discovery_runner.py`

Status: active review-only official-source discovery runner

Builds reusable discovery candidates for source-capture blockers:

```bash
python scripts/wf78_official_source_discovery_runner.py --write --validate
```

It reads `tmp/wf78-source-capture-requirements-queue.json`, current ticker cards, and `data/finance/wf78-source-open-official-registry.json`, then writes `tmp/wf78-official-source-discovery.json`. Rows are classified as `official_registry_existing`, `official_exact`, `official_index_page`, or `not_found`.

Review-only: no registry mutation, no source values copied into cards, no ticker-card mutation, no deployment-surface mutation, no canon/portfolio mutation, no SQL-canon mutation, no capital deployment, no order execution, no account action, no money movement, no customer output, and no approval inference.

### `wf78_official_registry_proposal.py`

Status: active not-applied official registry proposal

Turns discovery rows into conflict-aware registry proposals:

```bash
python scripts/wf78_official_registry_proposal.py --write --validate
```

It reads `tmp/wf78-official-source-discovery.json` and the current official registry, then writes `tmp/wf78-official-registry-proposal.json`. The output proposes rows only; it does not apply them to the registry.

Review-only: no registry mutation, no ticker-card mutation, no deployment-surface mutation, no canon/portfolio mutation, no SQL-canon mutation, no capital deployment, no order execution, no account action, no money movement, no customer output, and no approval inference.

### `wf78_official_registry_apply_preview.py`

Status: active review-only official registry apply preview

Builds diff/hash/proposed-registry proof from not-applied proposal rows:

```bash
python scripts/wf78_official_registry_apply_preview.py --write --write-proposed --validate
```

It reads `tmp/wf78-official-registry-proposal.json` and `data/finance/wf78-source-open-official-registry.json`, then writes `tmp/wf78-official-registry-apply-preview.json` plus `tmp/wf78-official-registry-proposed.preview.json`. The current preview shows 10 conflict-free `would_add_registry_row` rows, current registry count 15, proposed registry count 25, and `registry_apply_executed=false`.

Review-only: no registry mutation, no ticker-card mutation, no deployment-surface mutation, no canon/portfolio mutation, no SQL-canon mutation, no capital deployment, no order execution, no account action, no money movement, no customer output, and no approval inference.

### `wf78_promotion_owner_lineage_queue.py`

Status: active promotion-only owner-lineage queue

Routes owner entry/stop lineage work only for promotion-scope rows:

```bash
python scripts/wf78_promotion_owner_lineage_queue.py --write --validate
```

It reads auto routing, production adjudication, source-capture requirements, sizing integration proposals, and owner-readiness proposals, then writes `tmp/wf78-promotion-owner-lineage-queue.json`. Ordinary Tier C monitor rows are explicitly excluded from lineage creation.

Review-only: no owner-note mutation, no ticker-card mutation, no deployment-surface mutation, no canon/portfolio mutation, no SQL-canon mutation, no capital deployment, no order execution, no account action, no money movement, no customer output, and no approval inference.

### `wf78_contract_state_guard.py`

Status: active review-only WF78 repair-contract guard

Validates the reusable repair artifact contracts:

```bash
python scripts/wf78_contract_state_guard.py --write --validate
```

It reads official-source discovery, registry proposal, promotion owner-lineage queue, position-sizing integration proposal, and deployment-readiness review outputs, then writes `tmp/wf78-contract-state-guard.json`. Latest proof: 112 checks, status `ok`.

Review-only: no registry/card/deployment/canon/portfolio/SQL-canon mutation, no capital deployment, no execution/account action, no money movement, no customer output, and no approval inference.

### `wf78_owner_lineage_discovery.py`

Status: active review-only owner entry/stop lineage discovery

Classifies promotion-scope owner-lineage residue:

```bash
python scripts/wf78_owner_lineage_discovery.py --write --validate
```

It reads the promotion owner-lineage queue plus cards and repair proposal artifacts, then writes `tmp/wf78-owner-lineage-discovery.json`. Latest proof: 10 target rows, all `needs_owner_decision`; `lineage_found_count=0`.

Review-only: no owner-note mutation, no ticker-card mutation, no deployment-surface mutation, no canon/portfolio mutation, no SQL-canon mutation, no fabricated bands/stops, no capital deployment, no execution/account action, no money movement, no customer output, and no approval inference.

### `wf78_owner_lineage_proposal.py`

Status: active review-only proposed owner entry/stop lineage packet

Generates not-applied proposed entry/stop lineage for Tier B owner-lineage blockers:

```bash
python scripts/wf78_owner_lineage_proposal.py --write --validate
```

It reads owner-lineage discovery, official source-capture packet, registry apply preview, and yfinance one-year close history, then writes `tmp/wf78-owner-lineage-proposal.json`. Latest proof: 10 rows, all `ready_for_owner_review`, with proposed entry bands/stops marked as generated review-only proposals, not owner-approved lineage.

Review-only: no ticker-card mutation, registry mutation, owner-note mutation, deployment-surface mutation, canon/portfolio mutation, SQL-canon mutation, ticker import, promotion, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_missing_band_context_repair.py`

Status: active review-only missing band-context repair packet

Repairs current price / band-status context for rows that already have owner band/stop lineage:

```bash
python scripts/wf78_missing_band_context_repair.py --write --validate
```

It reads current WF85 decision cards, derives Tier A/B rows that are missing decision-grade entry-band/stop coverage or already depend on this repair source, and writes `tmp/wf78-missing-band-context-repair.json`. The active repair rows can persist after the actual missing count reaches zero so WF84/WF85 rebuilds keep review-only technical band/stop context for the same routed Tier B names. Latest proof: actual missing decision-grade band/stop count is 0; 15 active repair-backed context rows remain for `ACN`, `ADI`, `ADP`, `ADSK`, `AKAM`, `ALB`, `ALLE`, `AMAT`, `AMCR`, `AME`, `ANET`, `AOS`, `APH`, `APP`, and `CDNS`. These rows are review-only technical context, not implementation blockers, approval drafts, card/canon mutations, or execution authority.

Review-only: no ticker-card mutation, owner-note mutation, deployment-surface mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_tier_c_to_b_auto_promotion_pipeline.py`

Status: active bounded Tier C attention -> Tier B research-bench pipeline

Evaluates explicit Tier C attention candidates through source-open, fundamentals, valuation, analyst/revision, technical band, and red-flag gates, then optionally records only passing rows as owner-approved derived Tier B research-bench labels:

```bash
python scripts/wf78_tier_c_to_b_auto_promotion_pipeline.py --candidate SCCO --candidate CASY --candidate TXN --candidate ASML --candidate ARES --approve-passing --write --validate
python scripts/wf78_tier_c_to_b_auto_promotion_pipeline.py --from-attention --max-candidates 25 --approve-passing --write --validate
```

It writes `tmp/wf78-tier-c-to-b-auto-promotion-pipeline.json` and closeout `tmp/wf78-tier-c-to-b-auto-promotion-pipeline.closeout.json`. The daily WF78 cron loop runs the dynamic `--from-attention` form with `--approve-passing` under Randall's 2026-07-05 standing label-only policy. Passing rows are appended to `tmp/wf78-tier-label-decision-register.json`, `tmp/wf78-tier-label-sync-preview.json` is refreshed, and `tmp/wf78-auto-tier-routing.json` is refreshed so passing candidates route as derived Tier B research-bench names.

Review-only/non-capital: no universe/canon/portfolio/ticker-card/SQL-canon mutation, no production answer-path change, no capital deployment, no order execution, no account action, no money movement, no customer output, and no approval inference. Passing rows are Tier B research bench only.

### `tier_ab_band_freshness_cron_guard.py`

Status: active cron hardening guard for Tier A/B band freshness

Checks the scheduled WF84/WF85 finance chain:

```bash
python scripts/tier_ab_band_freshness_cron_guard.py --write --validate
```

It reads WF85 decision cards, the dynamic missing-band repair packet, the WF85 repair conveyor, and `cron_freshness_spine.py` contracts. It fails on stale complete Tier A/B band context, uncovered missing decision-grade band/stop rows, or missing cron expected-artifact contracts. Active repair-backed context rows are allowed when the actual missing count is zero and complete/current Tier A/B coverage is proven.

Review-only: no ticker-card mutation, owner-note mutation, cron schedule mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_repair_debt_scoreboard.py`

Status: active review-only WF78 repair debt scoreboard

Builds the next-wave repair scoreboard:

```bash
python scripts/wf78_repair_debt_scoreboard.py --write --validate
```

It reads freshness, source-open repair, work packets, integration proposal, deployment review, registry apply preview, lineage discovery, and contract guard artifacts, then writes `tmp/wf78-repair-debt-scoreboard.json`. Latest proof: `stale_refreshable=166`, `stale_source_open=25`, `blocked_structural=9`; explicit repair dispositions are `needs_position_sizing_surface=25`, `needs_source_artifact=10`, `needs_deployment_readiness_surface=1`. Next wave: 23 sizing rows ready, 2 sizing rows blocked, 1 deployment singleton ready, 10 registry preview rows ready, and 10 owner-lineage rows blocked for owner/source decision.

Review-only: scoreboard only; no registry/card/deployment/canon/portfolio/SQL-canon mutation, no capital deployment, no execution/account action, no money movement, no customer output, and no approval inference.

### `wf78_scaleout_policy_dry_run.py`

Status: active review-only WF78 500-scale policy dry run

Proves that scaleout stays tier-gated instead of making all 500 names decision-grade:

```bash
python scripts/wf78_scaleout_policy_dry_run.py --write --validate
```

It reads auto routing, promotion owner-lineage queue, the 500-ticker reputation gate when present, and the repair scoreboard, then writes `tmp/wf78-scaleout-policy-dry-run.json`. Latest proof: 200 active rows, 152 ordinary Tier C monitor exclusions, next batch label 201-300 with 100 Tier C eligible rows in the reputation gate, and `decision_grade_for_all_500=false`.

Review-only: no ticker import/apply/promotion, no production answer-path change, no registry/card/canon/portfolio/SQL-canon mutation, no capital deployment, no execution/account action, no money movement, no customer output, and no approval inference.

### `wf78_ph_owner_review_candidate_packet.py`

Status: active review-only PH owner-review candidate packet

Packages PH as the first Tier A owner-review candidate from the current owner-readiness surface:

```bash
python scripts/wf78_ph_owner_review_candidate_packet.py --write --validate
```

It reads `tmp/wf78-tier-a-owner-readiness-proposals.json` and writes `tmp/wf78-ph-owner-review-candidate-packet.json`. It validates that PH is currently the in-band Tier A candidate and preserves all capital/execution flags as false.

Review-only: no order card, ticker-card mutation, deployment-surface mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_tier_a_invalidation_review_queue.py`

Status: active review-only Tier A invalidation queue

Separates CME, LMT, and META from the buy-candidate lane:

```bash
python scripts/wf78_tier_a_invalidation_review_queue.py --write --validate
```

It reads `tmp/wf78-tier-a-owner-readiness-proposals.json` and writes `tmp/wf78-tier-a-invalidation-review-queue.json`. It requires all three rows to be tagged below-stop/invalidation review and marks them `invalidation_review_not_buy_candidate`.

Review-only: no buy-candidate treatment, order card, ticker-card mutation, deployment-surface mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_official_source_capture_packet.py`

Status: active review-only official source pointer packet

Captures official IR/latest earnings pointers for blocked Tier B names:

```bash
python scripts/wf78_official_source_capture_packet.py --write --validate
```

It reads `tmp/wf78-source-capture-requirements-queue.json` and writes `tmp/wf78-official-source-capture-packet.json` for ACN, ADI, ADP, ADSK, AKAM, AMAT, ANET, APH, APP, and CDNS. It records official source pointers only; owner entry/stop lineage remains required before repair integration.

Review-only: no source values copied into cards, no registry mutation, no ticker-card mutation, no deployment-surface mutation, no canon/portfolio mutation, no SQL-canon mutation, no capital deployment, no order execution, no account action, no money movement, no customer output, and no approval inference.

### `wf78_next_owner_review_and_source_capture_integration.py`

Status: active review-only next-push integration summary

Combines PH owner-review, Tier A invalidation, and Tier B official source capture:

```bash
python scripts/wf78_next_owner_review_and_source_capture_integration.py --write --validate
```

It reads the three packet artifacts above and writes `tmp/wf78-next-owner-review-and-source-capture-integration.json`, preserving the next safe action: review PH first, keep CME/LMT/META in invalidation review, and use official source pointers while owner entry/stop lineage remains blocked.

Review-only: no apply, registry update, card update, deployment-surface update, canon/portfolio mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_ticker_freshness_ledger.py`

Status: active review-only WF78 freshness ledger

Builds the recurring per-ticker freshness state that prevents another broad stale-card cleanup wave:

```bash
python scripts/wf78_ticker_freshness_ledger.py --write --validate
```

It reads `tmp/finance-intelligence-state-stale-tickers.json`, `tmp/wf78-auto-tier-routing.json`, and `tmp/wf78-source-open-repair-execution.json`, then writes `tmp/wf78-ticker-freshness-ledger.json`. Rows classify each ticker as `fresh`, `stale_refreshable`, `source_open_repaired_rerun_needed`, `stale_source_open`, `blocked_structural`, or `stale_review_required`, with Tier A/B/C freshness SLAs and next actions.

Review-only: no ticker-card mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, order execution, account action, money movement, customer output, or approval inference.

### `wf78_tier_weighted_freshness_resolver.py`

Status: active review-only tier-weighted freshness resolver

Separates raw stale-card warnings from tier-appropriate WF78 debt resolution:

```bash
python scripts/wf78_tier_weighted_freshness_resolver.py --write --validate
```

It reads the freshness ledger, auto routing, repair execution, sizing/deployment proposals, owner-lineage discovery/proposal, missing-band repair, registry preview, and ticker-card refresh proof, then writes `tmp/wf78-tier-weighted-freshness-resolution.json`. Tier A/B rows stay strict for decision or promotion repair; ordinary Tier C `C-MONITOR` rows resolve as thin-monitor current with decision-grade families deferred until promotion. It keeps quote-window gates visible while allowing review-only owner-lineage proposals and band-context repair packets to clear their respective blockers into review states.

Review-only: no ticker-card mutation, registry mutation, owner-note mutation, deployment-surface mutation, canon/portfolio mutation, SQL-canon mutation, ticker import, promotion, capital deployment, order execution, account action, money movement, customer output, config/auth/runtime mutation, or approval inference.

### `wf78_daily_freshness_loop.py`

Status: active review-only daily freshness orchestration wrapper

Runs the daily WF78 freshness spine in the validated order:

```bash
python scripts/wf78_daily_freshness_loop.py --skip-provider-refresh --write --validate
python scripts/wf78_daily_freshness_loop.py --no-skip-provider-refresh --write --validate
python scripts/wf78_daily_freshness_loop.py --skip-provider-refresh --full-answer-mode never --write --validate
python scripts/wf78_daily_freshness_loop.py --phase daily_core --skip-provider-refresh --write --validate
python scripts/wf78_daily_freshness_loop.py --phase source_capture --write --validate
```

Scheduler posture: enabled cron `Finance - WF78 Daily Freshness and Promotion Proof` now targets `wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded --write --validate`. That keeps the daily scheduled proof on the time-boxed routing/freshness/repair/ledger path and makes runtime-budget drift fail validation instead of becoming accepted warning noise. Source-capture, owner-review expansion, card materialization, and provider-refresh paths remain on-demand targeted runs.

The loop now supports `--phase all|daily_core|card_refresh|tier_routing|evidence_repair|source_capture|owner_review|wf84_sync`. `daily_core` runs ticker-card refresh, routing, Tier C hold quote/card recheck, evidence repair, Tier C/band/freshness resolution, Finance Decision Factory ledger-only proof, and WF84 sync. Source-capture/registry/owner-review expansion remains available by exact phase instead of being paid for on every scheduled run. Output: `tmp/wf78-daily-freshness-loop.json`. Default `--skip-provider-refresh` keeps manual proof offline/local unless a provider refresh is explicitly requested. `--full-answer-mode changed` is the default optimization: the first card gate rebuilds WF85 full answers only on semantic card/source changes, while the post-freshness card recheck uses `never` to avoid duplicate full-answer rebuilds in the same loop.

Review-only: no ticker-card/canon/portfolio/SQL-canon mutation beyond existing proof rebuilds, no capital deployment, order execution, account action, money movement, customer output, config/auth/runtime change, or approval inference.

### `wf78_daily_movement_ledger.py`

Status: active review-only Intelligence Routing V2 ledger

Builds the daily operator surface that was missing from the scattered WF78/WF84/WF85 proof chain:

```bash
python scripts/wf78_daily_movement_ledger.py --write --write-md --validate
```

It reads the auto-router, routing delta, tier-weighted freshness resolver, Tier C attention trigger, Tier C-to-B promotion gate, autonomous deployment cards, WF85 decision cards, and WF84 data plane. Outputs:
- `tmp/wf78-daily-movement-ledger.json`
- `tmp/wf78-daily-movement-ledger.md`
- `tmp/wf78-repair-priority-queue.json`

The ledger groups the day into moved, blocked, newly hot, stale-but-important, owner-review, no-chase, and invalidation buckets. The repair queue ranks blocked rows by Tier A decision repair first, Tier B promotion repair second, and Tier C thin-monitor repair last.

Review-only: no universe mutation, ticker-card mutation, canon/portfolio mutation, SQL-canon mutation, capital deployment, paper/live execution, brokerage/account action, money movement, customer/external output, or approval inference.

### `wf78_intelligence_routing_v2.py`

Status: active layered daily routing wrapper

Splits the prior daily-core habit into checkpointed layers:

```bash
python scripts/wf78_intelligence_routing_v2.py --layer daily_core_v2 --write --validate
python scripts/wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded --write --validate
python scripts/wf78_intelligence_routing_v2.py --layer market_probe --write --validate
python scripts/wf78_intelligence_routing_v2.py --layer evening_ledger --write --validate
python scripts/wf78_intelligence_routing_v2.py --layer ledger_publish --write --validate
```

Layer aliases:
- `daily_core_v2`: preflight, tier routing, freshness, repair scan, ledger publish, postflight artifact-index refresh/validation
- `market_probe`: tier routing, freshness, ledger publish, postflight artifact-index refresh/validation
- `evening_ledger`: repair scan, card materialization, ledger publish, postflight artifact-index refresh/validation
- `all`: every V2 layer

Use `--fail-on-budget-exceeded` for scheduled or promotion proof windows. The old monolithic `daily_core` path and `wf78_daily_freshness_cron_runner.py` remain compatibility surfaces, not the preferred daily review cadence.

Review-only: no cron schedule mutation by itself, no universe mutation, no canon/portfolio mutation, no capital deployment, no paper/live execution, no brokerage/account action, no money movement, and no owner approval inference.

### `wf78_daily_freshness_cron_runner.py`

Status: stable WF78/WF84/WF85 cron-facing wrapper

Runs the daily WF78 loop plus market-readiness, decision-factory, trade-grade OS, workflow index, cron ledger, freshness spine, scorecard, escalation, and control-packet refresh as one compact command:

```bash
python scripts/wf78_daily_freshness_cron_runner.py --write --validate
python scripts/wf78_daily_freshness_cron_runner.py --provider-refresh --write --validate
python scripts/wf78_daily_freshness_cron_runner.py --launch-background --write --validate
```

Default mode uses the local/offline WF78 daily-core loop (`--phase daily_core --skip-provider-refresh`) and relies on the separate quote snapshot plus market-readiness proof for current market-window execution-readiness checks. Use `--provider-refresh` only when the longer provider-refresh loop is explicitly needed and the caller can tolerate a longer local run. Scheduled cron uses `--launch-background` so the isolated cron agent owns only a short launcher command while the child process writes the full proof artifact.

Writes:
- `tmp/wf78-daily-freshness-cron-runner.json`
- `tmp/wf78-daily-freshness-cron-launcher.json` when launched in background mode

Boundary:
- review-only WF78/WF84/WF85 proof and routing
- no registry apply, canon/portfolio mutation, capital approval, paper/live execution, brokerage/account action, money movement, customer/external output, cron schedule mutation, runtime config mutation, or owner approval inference

### `pm_execution_loop.py`

Status: active review-only PM execution loop

Uses the PM implementation job queue as the operating system:

```bash
python scripts/pm_execution_loop.py --write --validate          # dry-run (default)
python scripts/pm_execution_loop.py --execute --write --validate # run guarded proof + closeout
```

It reads `tmp/pm-control-packet.json`, ranks jobs, and picks the top safe job enforcing one writer per collision group (skipping jobs whose collision group is leased/running in `tmp/concurrent-lane-register.json`). A `FORBIDDEN_TOKENS` guard marks any job whose proof commands contain mutation/execution/import/config tokens (`--execute`, `--apply`, `--promote`, `--import`, `--submit`, shell metacharacters, `paper`, `alpaca`, `gateway`, etc.) as `needs_main_review` so it is never auto-run. Dry-run is the default; `--execute` runs only review-only proof commands then the job's budgeted closeout, now routed through `pm_control_packet.py`. Identical successful proof commands are reused within one execution batch and proof-level PM packet refreshes are moved to closeout when another proof command exists. The PM queue consumes `state/implementation-completion-ledger.jsonl`, so completed PM jobs are not reselected as automatic proof work. Flags: `--limit` (default 1), `--job <job_id>`, `--reuse-proof-cache` / `--no-reuse-proof-cache`, `--out`.

It never patches implementation files, spawns helpers, mutates canon/portfolio/SQL, or infers owner approval. Broad or patch-bearing PM jobs are surfaced to the main session as helper-lane candidates instead of being executed inline.

### `control_closeout_bundle.py`

Status: active review-only control bundle

One command for the end-of-session cockpit/control refresh:

```bash
python scripts/control_closeout_bundle.py --write --validate
python scripts/control_closeout_bundle.py --cockpit-validate --write --validate
python scripts/control_closeout_bundle.py --write --validate --record-completion --completion-job-id <job_id>
```

It runs `repeatable_work_closeout.py --write --validate` (900s budget), `pm_control_packet.py --write --write-db --validate`, `main_session_escalation_consumer.py --context closeout --refresh-frontdoors --execute-safe --write --validate --append-ledger`, `main_session_action_executor.py --context closeout --execute-safe --write --validate --append-ledger`, a final PM packet refresh, and `concurrent_lane_manager.py --status --validate` (lane-register health), plus optional cockpit validation. If cockpit validation is requested but `npm` or the cockpit directory is unavailable, the bundle fails closed. `--continue-on-failure` runs all steps regardless of intermediate failures. Output: `tmp/control-closeout-bundle.json`. Review-only proof plus allowlisted cron escalation and PM proof pickup; no mutation, patch execution, helper spawning, or approval authority.

### `wf73_control_plane_audit.py`

Status: active ordered WF73 audit runner

```bash
python scripts/wf73_control_plane_audit.py --write --validate
python scripts/wf73_control_plane_audit.py --write --validate --skip-memory-status
```

It serially refreshes the WF73 producer/consumer chain: WF73 route summary, workflow routing JSON/SQLite, lane register, truth-surface inventory, cron freshness, PM control packet, boot-size guard, workflow hygiene, fast-path QA, timing ledger, control closeout, artifact-index incremental refresh, artifact-index validation, and memory-index status. Memory-index provider failure is warning-class unless a critical control-plane validator fails.

Use this for WF73 audits instead of parallel producer/consumer validation batches. It exists to prevent false blockers where a writer is rebuilding `tmp/workflow-routing-index.sqlite` while a consumer reads it.

Review-only: no helper spawn, workflow execution, archive/delete, config/auth/runtime mutation, canon/portfolio mutation, external delivery, paper/live/account action, capital action, or approval inference.

### `helper_lane_manifest.py`

Status: active frozen-handoff and helper-lane proof adapter

Builds `tmp/helper-lane-active-manifest.json` with a workspace-relative base path, a sorted SHA-256 file inventory, a frozen snapshot id, and deterministic file/byte/token budgets. The hard ceilings are six files, 120,000 bytes, and 30,000 estimated context tokens; CLI values may narrow but cannot widen them. The estimator is versioned (`utf8_bytes_div4_ceiling_v1`); files and bytes remain the authoritative limits.

Each run records a derived attempt id and retry count. Attempt 2+ requires the prior attempt id, failure class, retry reason, incident trigger, and provisional incident update. The update SLA is exactly 90 seconds. Failed/timed-out attempts and retries fail validation if incident proof is missing or breached. `swarm_completion_handshake.py` re-hashes every context file and the immutable contract before synthesis, so a changed or missing snapshot blocks closeout.

```powershell
python scripts\helper_lane_manifest.py --lane-id op-lev-phase-ac-qa --status running --base-path handoff\op-lev-phase-ac-qa --context-file target.py --context-file test_target.py --write --validate
python scripts\swarm_completion_handshake.py --manifest tmp\helper-lane-active-manifest.json --write
```

Required artifacts in a v2 manifest are also relative to `--base-path`. Run the manifest command before dispatch, keep the exact snapshot frozen during review, and run the swarm handshake again immediately before Main accepts or synthesizes the result. Version-1 manifests remain readable but emit a legacy warning and do not claim frozen-handoff proof.

This is proof routing only. It does not spawn helpers, merge results, move queue state, mutate cron/config/runtime/canon/portfolio surfaces, perform paper/live/account actions, or infer owner approval.

`tmp/portfolio-config.json` is the machine-readable portfolio and execution config spine. It now carries tracked-universe policy, yfinance symbol mapping, coverage tiers, workflow semantics, and entry-band metadata. Scripts should read tracked names and execution semantics from this file instead of hardcoding local universe lists or band maps.

## Operating-window sequence

Use the chain that matches the real decision window.

The refresh runner is now the default orchestration entrypoint. Prefer it over manually calling long script sequences in cron prompts or ad hoc operator instructions.

Workbook packaging rule:
- default chain runs stop at `workbook_export.py`
- add `--build-workbook` only when you intentionally want a manual staging workbook package after the export layer is fresh
- leaving the flag off preserves the current fail-closed posture for scheduled workbook packaging

### Morning readiness

Use before the session or pre-open when the goal is to read the current board, not rebuild every catalyst workflow.

```bash
python scripts/run_finance_refresh_chain.py morning
```

### Post-close refresh

Use after the close as the default full rebuild for the next session. This is the main convenience path.

```bash
python scripts/run_finance_refresh_chain.py post-close
```

This refreshes the earnings-date layer before trigger generation, then stages post-earnings prep and note-target artifacts so they are not left to memory.

### Post-earnings refresh

Use after a material company report lands when the close-level artifacts already exist and the main need is closure-state follow-up.

```bash
python scripts/run_finance_refresh_chain.py post-earnings
```

### Sunday weekly rebuild

Use once on Sunday to fully prime the next week - full earnings + market + technical + regime score rebuild, weekly positioning review scaffold, weekly macro snapshot, weekly intelligence brief append, and a primed daily executive brief. Designed so the Sunday weekly review session opens against a complete artifact set.

```bash
python scripts/run_finance_refresh_chain.py sunday
```

### Missed-earnings roll-forward guard

Every finance refresh window should run the review-only guard before official
capture and card rebuild:

```bash
python scripts/earnings_rollforward_guard.py --priority-only --auto-capture --write --validate
```

For a named ticker, use `--ticker ETN` (repeat the option for a shard). The
guard compares the latest validated capture period with SEC filing metadata,
creates an idempotent catch-up result, and auto-captures only a ticker/parser
pair that has an independently verified official-source parser. Unsupported or
ambiguous releases remain explicit `manual_required`/`catch_up_required`
findings; they are never silently presented as current.

The guard is inserted before official capture in the morning, post-close,
post-earnings, Sunday, and full refresh manifests. It is also the first step of
the ticker-card refresh gate. `tmp/earnings-rollforward-guard.json` is included
in cron freshness/control inputs. Historical capture files are additive and
never overwritten by a newer quarter.

When an official release advances before normalized 10-Q metrics do, the card
period-aligns to the official release, shows only explicitly captured current
values, withholds older period-sensitive fields such as ROIC, debt, and derived
valuation, and retains the prior normalized row as prior context. This prevents
hybrid-period research from looking current.

### Validation placement

`generate_dashboard.py` still emits the inline validation payload used by the dashboard, but the independent closure check now belongs at the end of each operating-window chain:

```bash
python scripts/validate_dashboard_state.py --write
```

That final validator run is the last trust gate before the derived dashboard is treated as decision support.

Scheduled-window closure now has one more layer after validation:
- `run_summary_refresh.py --window <window>` writes the machine-readable workflow summary
- `dashboard_run_summary_consumer.py --window <window>` propagates that trust state into the command center payload and rendered HTML
- `current_window_artifact_index.py --window <window> --write` writes a stable review-only map of the current run's reports, guardrails, proposals, and proof artifacts

This keeps stop lines, missing required outputs, fallback/manual dependencies, and current artifact locations visible instead of letting a rendered dashboard fake success.

### Operator rule

If a workflow needs more than one artifact-refresh script in sequence, default to `run_finance_refresh_chain.py` unless there is a concrete reason to run a narrower step directly.

## Governance note

The active operator surface above is intentionally narrow. Temporary diagnostics, scratch helpers, historical raw dumps, and superseded implementation plans belong in archive if they still matter, not in `scripts/` or `tmp/`.

## SQL-primary finance migration efficiency

Use these review-only packets when evaluating the human-canon, SQL-routing, and JSON-proof restructuring work:

```bash
python scripts\finance_sql_primary_migration_plan.py --write --write-md --validate
python scripts\finance_sql_markdown_field_ownership.py --write --validate
python scripts\execution_board_canon_anchor_pilot.py --write --write-md --validate
python scripts\execution_board_canon_anchor_drift_validator.py --write --validate
python scripts\reference_levels_production_grade_refresh_dry_run.py --write --write-md --validate
python scripts\reference_levels_expected_parity_validator.py --anchors tmp/reference-levels-production-grade-anchor-pilot.json --dry-run tmp/reference-levels-production-grade-refresh-dry-run.json --output tmp/reference-levels-production-grade-expected-parity-validator.json --md-output tmp/reference-levels-production-grade-expected-parity-validator.md --write --write-md --validate
python scripts\artifact_index.py incremental
python scripts\artifact_index.py validate
```

What they do:
- `finance_sql_primary_migration_plan.py` records the current decision to finish SQL-primary migration with explicit schedule and parity gates.
- `finance_sql_markdown_field_ownership.py` classifies SQL/Markdown reconciliation fields as `canon_anchor_required`, `sql_proof_only`, or `human_judgment_only` so cross-class mismatches do not become fake blockers.
- `execution_board_canon_anchor_pilot.py` generates a 42-ticker anchor preview from the Execution Board table without editing the note.
- `execution_board_canon_anchor_drift_validator.py` compares the anchor preview against SQL `reference_levels`; domain drift reports `status=blocked` while script validation can still be `ok`.
- `reference_levels_production_grade_refresh_dry_run.py` filters that anchor preview to the current proof-joined production-grade answer set from `finance_sql_canon_access.production_answer_tickers()`, then builds the review-only `reference_levels` SQL metadata dry-run and apply packet for that strategic scope. The legacy 42-row dry-run remains compatibility repair evidence, not the forward production boundary.
- `reference_levels_expected_parity_validator.py` can validate the production-grade filtered packet with the `--anchors`, `--dry-run`, `--output`, and `--md-output` arguments shown above; the target count follows the validated proof-joined production-grade set and may be 0 when stale router/coverage gates fail closed.
- `artifact_index.py` owns both the raw `v_cockpit_action_queue` and the de-duped `v_cockpit_action_queue_deduped` view.

Boundary:
- review/proof/routing only
- no SQL data/schema mutation
- no human canon or portfolio mutation
- no cron schedule mutation
- no archive/delete/apply action
- no capital deployment, paper/live execution, brokerage/account action, or owner approval inference
