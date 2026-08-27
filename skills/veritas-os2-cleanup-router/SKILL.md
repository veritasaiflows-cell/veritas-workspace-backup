---
name: "veritas-os2-cleanup-router"
description: "Route WF88 OS2 cleanup and retirement proof safely."
---

# Veritas OS2 Cleanup Router

Use this skill when WF88 or OS 2.0 cleanup work touches retired surfaces, route contraction, source-open residue classification, duplicate DB/script surfaces, disabled cron rows, deletion/archive readiness, wiki synthesis, or control-packet cleanup routing.

This is a cleanup and routing skill. It is not delete authority, archive authority, SQL mutation authority, cron schedule authority, paper/live execution authority, or owner approval.

## Core Doctrine

WF88 owns OS-wide cleanup, route contraction, learning/control packet synthesis, and retired-surface readiness. WF88 may classify, rank, prepare, validate, and route cleanup work. WF88 may not infer approval or perform destructive cleanup without a separate exact owner-approved apply packet.

Keep the workflow proposal-first:

- classify stale or retired surfaces
- prove active references and route ownership
- separate current truth from legacy compatibility residue
- prepare exact owner approval packets for destructive cleanup only when validators prove readiness
- preserve rollback, tombstone, and source-provenance trails
- rerun release and control closeout proof

## Required First Reads

Before material WF88 cleanup work, inspect the thin router/control surfaces first:

```powershell
python scripts\workflow_router.py WF88 --answer all --validate
python scripts\wf88_os2_control_packet.py --write --write-md --validate
python scripts\concurrent_lane_manager.py --status --write --validate
```

Then inspect only the relevant drill-in artifacts:

- `tmp\wf88-route-contraction-packet.json`
- `tmp\wf88-source-open-residue-classifier.json`
- `tmp\wf88-delete-readiness-packet.json`
- `tmp\wf88-deletion-approval-prep-packet.json`
- `tmp\wf88-cron-retired-job-inventory.json`
- `tmp\wf88-cron-disabled-job-reference-review.json`
- `tmp\wf88-script-cleanup-inventory.json`
- `tmp\wf88-typed-script-reference-graph.json`
- `tmp\db-lifecycle-manifest.json`
- `tmp\tmp-lifecycle-guard.json`
- `tmp\implementation-release-contract.json`
- `tmp\control-closeout-bundle.json`

Use exact owner artifacts before broad scans.

## Standard WF88 Cleanup Chain

Run the smallest honest subset, in dependency order.

```powershell
python scripts\db_lifecycle_manifest.py --write --validate
python scripts\wf88_script_cleanup_inventory.py --write --write-md --validate
python scripts\wf88_typed_script_reference_graph.py --write --write-md --validate
python scripts\wf88_retired_surface_cleanup_plan.py --write --write-md --validate
python scripts\wf88_route_contraction_packet.py --write --write-md --validate
python scripts\wf88_source_open_residue_classifier.py --write --write-md --validate
python scripts\wf88_cron_retired_job_inventory.py --write --write-md --validate
python scripts\wf88_cron_disabled_job_reference_review.py --write --write-md --validate
python scripts\wf88_delete_readiness_packet.py --write --write-md --validate
python scripts\wf88_deletion_approval_prep_packet.py --write --validate
python scripts\wf88_os2_control_packet.py --write --write-md --validate
```

For broad closeout, add:

```powershell
python scripts\changed_file_validator_router.py --write --validate
python scripts\validator_bundle_router.py --write --validate
python scripts\implementation_release_contract.py --phase blocking --write --validate
python scripts\control_closeout_bundle.py --validation-budget shared --write --validate
```

## Route Contraction Rules

Route contraction means narrowing consumers to current canonical route surfaces. It does not mean deleting scripts.

Allowed:

- mark old scripts as compatibility or sidecar surfaces
- update router metadata and capsules
- validate route ownership and exact reference graphs
- keep old surfaces retained when they are rollback, audit, migration, or fallback paths

Blocked without separate exact approval:

- script deletion
- archive/move/delete apply
- source-feeder retirement
- Python fallback retirement
- SQL schema mutation
- portfolio/canon note mutation
- cron schedule mutation

A route is not retired just because a newer route exists. It must have no active references, no fallback role, clean parity/repeated proof, rollback, and owner approval for archive/delete when destructive.

## Source-Open Residue Classification

Use WF88 source-open classification to keep legacy residue out of default runtime blockers.

Classification must separate:

- active SQL/JSON repair rows
- material source-open blockers
- below-stop/invalidation review-only rows
- monitor-only rows
- legacy residue rows
- unknown rows

Only active SQL/JSON or material source-open repair rows should enter the main repair queue. Monitor-only, below-stop, legacy, and unknown rows must be visible but should not be promoted into deployment readiness or runtime failure without current proof.

## SQL-First Decision Pollution Guard

When WF88 cleanup intersects finance decision surfaces, verify that legacy or retired surfaces cannot outrank current SQL-first truth.

Check for these leak patterns:

- old `tmp\portfolio-config.json` bands outranking current `tmp\band-proposals.json`
- old WF78, capital-review, opportunity, chief, or morning-card bands creating current no-chase or stop blockers
- source-open residue counted as default runtime blocker after current SQL/JSON proof is clean
- generated Markdown or archived proof treated as canonical structured truth
- stale retired surfaces causing ticker readiness, approval-card, or alert-state changes

Acceptance proof should include current SQL-canon access and the relevant decision/card/timing validators, for example:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\finance_decision_sync_spine.py --write --write-md --validate
python scripts\chief_intelligence_promotion_gate.py --write --validate
python scripts\trade_grade_decision_cards.py --write --validate
python scripts\wf85_deployment_timing_gate.py --write --validate
python scripts\capital_deployment_band_integrity_validator.py --write --validate
```

Legacy context may remain as `superseded_legacy_*` audit detail. It must not be a current blocker when SQL-first current state is clean.

## Delete And Archive Readiness

WF88 may prepare deletion or archive readiness packets. It may not perform destructive apply unless Randall has approved the exact packet.

A cleanup candidate is owner-ready only when the packet proves:

- exact path or cron row identity
- source owner and route role
- no active references or exact retained-reference rationale
- hash or rollback export
- tombstone or rollback plan
- post-apply validator list
- authority boundary and stop lines

Do not batch unrelated deletion families. Separate tmp cleanup, disabled cron cleanup, DB archive, source artifact archive, and script deletion.

After approved apply, verify:

- apply report exists
- rollback/tombstone exists
- reference review still clean
- cron contract/freshness/control are clean when cron rows were involved
- implementation release contract and control closeout are clean

## Disabled Cron And Cron Retirement

Disabled cron cleanup must use proof-before-disable and rollback-export posture.

Before recommending disabled cron deletion:

```powershell
python scripts\wf88_cron_retired_job_inventory.py --write --write-md --validate
python scripts\wf88_cron_disabled_job_reference_review.py --write --write-md --validate
python scripts\cron_contract_validator.py --require-contracts --fail-on-drift --fail-on-prompt-bloat --write --validate
python scripts\cron_freshness_spine.py --write --validate
python scripts\cron_control_packet.py --write --validate
```

If any disabled row has active code/control references, keep it blocked or route reference pruning first. Do not delete scheduler rows to hide reference debt.

## Wiki And Learning Layer

WF88 wiki synthesis is a review layer. It turns OTEL, WF74, RSI, token scorecards, recommendation outcome ledgers, and cleanup packets into visible action rows.

It must not:

- claim model performance when outcome grading is immature
- capture raw prompts/tool payloads for training
- apply skill proposals
- mutate cron, config, finance canon, portfolio, paper/live execution, or customer-facing surfaces

Use:

```powershell
python scripts\wf88_wiki_synthesis_packet.py --write --write-md --write-wiki --validate
python scripts\token_efficiency_scorecard.py --write --write-md --validate
python scripts\implementation_token_attribution_bridge.py --write --write-md --validate
```

## Skill Workshop Body Guard

Do not create duplicate Skill Workshop body guards. The canonical guard is:

```powershell
python scripts\skill_workshop_body_guard.py --write --validate
python scripts\test_skill_workshop_body_guard.py
```

Use it before and after skill apply work when skill bodies or governance surfaces are changed. If the existing guard is insufficient, update that guard through the normal implementation path; do not create a parallel guard.

## Stop Lines

Stop and ask Randall for exact approval before:

- deleting, moving, or archiving files
- deleting or disabling cron rows
- applying DB archive/delete packets
- retiring source feeders or Python fallbacks
- mutating SQL schema or source artifact content
- mutating portfolio/canon/cash/sizing/risk surfaces
- changing cron schedules, runtime, auth, config, channels, services, or network exposure
- generating customer/public/external output
- paper/live/brokerage/account action
- claiming model-performance improvement from immature outcome data
- inferring owner approval

## Output Contract

For WF88 cleanup work, report:

- conclusion: refreshed, proposed, blocked, owner-ready, or applied-with-approval
- exact artifacts refreshed
- candidate counts by family
- what is current truth versus legacy retained context
- any owner-ready destructive packet and whether it is only pending approval
- validation commands and statuses
- remaining blockers and next safe action
- explicit boundary: no delete/archive/apply/execution/owner approval unless separately approved
