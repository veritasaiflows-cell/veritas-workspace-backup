# OpenClaw Parallel Pilot Queue

## Purpose

Define the live operator queue for deliberate parallel execution and workflow sequencing.

This note is the compact active control surface.
Detailed historical workflow entries now live in:
- `06. Playbooks/OpenClaw Parallel Pilot Queue - History.md`

## Resource posture

### Main default
- Veritas main session is the live truth surface and final integrator
- use for orchestration, integration, final judgment, queue/registry control, QC, and quick bounded execution

### Spawned worker default
- Use the approved `openai-codex/*` model set with role-based thinking, not maximum effort by habit.
- Use for substantial workspace work expected to exceed roughly five minutes, touch multiple artifacts, require broad inspection, or need independent QA.
- Default thinking by role: low for routine research/read-only audit, medium for implementation, high for hard debugging, repeated false-green/false-red residue, or high-stakes trust adjudication.

### Lower-complexity helper posture
- Lower effort should usually mean tighter scope and lower thinking, not a lower-trust model.
- Keep helper routing inside the approved `openai-codex/*` set unless Randall intentionally changes runtime policy.

Do not use reduced-trust helper posture for:
- final trust adjudication
- canonical-state judgment
- ambiguous architecture decisions
- final portfolio or OS calls

## Pilot success standard

The queue is succeeding only if:
- completion time drops
- main-session clutter drops
- reconciliation burden stays low
- artifact ownership stays clear
- the user gets more finished passes, not more chatter

## Queue structure

Each meaningful queued item should make clear:
- lane owner
- model posture or helper posture
- deliverable
- what not to touch
- acceptance check
- category
- parallel posture
- execution mode
- QC complete

After any helper lane finishes, Veritas/main must check this queue before going idle: either spawn the next safe helper, execute the next quick bounded task directly, close/pause with proof, or ask Randall a concrete blocking question.

## Sequencing rule

- **Workflow-level order** is authoritative for which numbered workflow opens next.
- **Strict ordered execution queue** is authoritative for phase-level work inside the current day / current chain.
- If those two views appear to disagree, do not average them. Reconcile the workflow-level active / next-three truth first, then update phase-level tasks beneath it.
- Current workflow-level order: **WF40 active / scheduled-repeat pending -> WF46 targeted QC complete -> WF47 targeted QC complete -> WF44 bounded visibility slice QC complete / LMT follow-up pending -> WF45 Slice A QC complete -> WF41 artifact-derived v1 QC complete -> WF42 recommendation-object v1 QC complete -> WF43 durable path approved / proof pending -> WF48 closed -> WF49 operator-gated sidecar -> WF37 paused follow-up -> SOP / automation optimization backlog**. WF46/WF47 were moved ahead of broad WF44/WF45 work on 2026-05-09 after implementation-readiness review showed run-summary terminal semantics and authority vocabulary are upstream truth contracts. WF44 now has the safe Promotion Review + Decision Queue slice implemented without authority widening; LMT-style dual-layer owner/risk visibility remains a bounded follow-up. WF45 established shared fail-soft source classification without chain-integrating the artifact index. WF41 artifact-derived router v1 and WF42 recommendation-object v1 are closeout-ready after repeat proof. WF43 now has an approved durable path at `data/state-history/state-history-v1.jsonl`, but durable append/validate proof and lifecycle policy remain pending. Broader source-tier/external intake, sector/correlation scoring, history consumer wiring, and execution/sizing remain owner-gated or unwired. WF48 is closed as a bounded machine-companion note mutation exception; WF49 remains operator-gated because it requires credential/runtime handling.
- Rationale for 2026-05-05 insertion: folder/truth architecture research showed that finance JSON spine, chain manifest, root/tmp/script boundaries, and dashboard/document truth routing should be tightened before wider external-intelligence expansion.
- WF32/WF33 reprioritization was completed on 2026-05-06 and those hardening lanes are now closed. Their resolved discrepancy set remains part of the control-plane rationale for opening WF31 now and keeping WF26 downstream of runtime-proof closure.

## Current chain state

### Active workflow
**Workflow 40 - Cyber-Security Hardening and Bounded Daily Audit**

Status:
- opened 2026-05-07 after WF38 closed honestly from live owner-layer and proof-surface evidence
- current purpose is to harden the local OpenClaw / workspace security posture with a bounded daily read-only audit, explicit trust gates, and a non-conflicting internal-only cron run
- the v1 script now exists: `scripts/cyber_security_daily_audit.py`
- the isolated daily cron job now exists as **Security Audit - Daily Bounded Hardening** on `10 17 * * *` / `America/Phoenix`
- manual proof already exists: the script writes `tmp/cyber-security-daily-audit.json` and `.md`, security audit + deep audit both run, skills inventory is healthy, firewall/AV posture is checked, and governance truth is clean after CLI path hardening
- current live artifact truth after the post-fix refresh is warning-grade, not critical: `tmp/cyber-security-daily-audit.json` at `2026-05-10T01:47:00Z` shows `status: "warning"`, `stop_line: false`, and no critical findings
- current warning stack is real but non-critical: Telegram is enabled under a setup-pending exception but delivery is not proven, `commands.ownerAllowFrom` still cannot be read by the checker, trusted proxies remain unset for a still-loopback Gateway, `openclaw doctor` still exposes runtime/doctor debt, and workspace-boundary warnings remain cleanup/backlog items
- controlled cron proof moved past the approval gate, and the 2026-05-09 17:10 America/Phoenix scheduled run did execute from live job `d2cbac10-f1fb-4060-8445-cb13f3dfc6be`; that scheduled run failed closed, but the controlled post-fix proof at `2026-05-10T01:47:00Z` is clean enough for warning-grade posture (`proof_status: ok`, `audit_status: warning`, `audit_stop_line: false`, `errors: []`)
- WF40 still stays active because closure requires the next ordinary scheduled repeat to prove the corrected path; config/auth/channel remediation is operator-gated and was not changed here
- automatic fixes, config mutation, browser enablement, auth/network changes, destructive cleanup, and canonical note mutation remain blocked

### Next approved queue item
**WF40 blocked scheduled-proof remediation / stable cron repeat proof**

Status:
- next move is not closure: wait for the next ordinary scheduled repeat proof where `tmp/cyber-security-daily-audit-cron-proof.json` is fresh, `proof_status=ok`, `audit_stop_line=false`, and wrapper errors are empty
- operator-gated blockers remain: whether enabled Telegram/channel config is intentional versus should be disabled again after setup, whether to restore/read `commands.ownerAllowFrom`, and whether to set `gateway.trustedProxies` to explicit proxy IPs or keep Control UI local-only; do not mutate config without Randall's explicit approval
- after one clean ordinary scheduled repeat proof, WF40 can move toward closure or bounded handoff for remaining warning-grade debt
- WF37 remains paused follow-up; it is not the next queue move unless WF40 is blocked or intentionally paused

### Priority source for next workflow advancement after WF40 unblocks
`08. Audits/WFs Automation Audit 2026.05.08.md.txt` remains the priority source for Level-3 review-object automation direction once WF40 is eligible to close or hand off. The later 2026-05-09 audits still justify the prerequisite ordering now recorded here: WF44/WF45/WF46/WF47 should precede wider WF41-WF43 autonomy because decision-object visibility, stale-source fail-soft behavior, run-summary terminal semantics, and authority vocabulary need to be boring before Level-3 recommendation expansion.

### Bounded audit-response sidecar

**Daily market-intelligence review-object posture / WF41 artifact-derived v1**

Status:
- 2026-05-08 audit-response pass landed a read-only market-intelligence event/materiality router: `scripts/market_intelligence_event_router.py`
- all four finance windows now run the router immediately before `scripts/daily_review_objects.py`, so daily review packets can consume routed fresh-intelligence status while staying review-only
- 2026-05-09 WF41 hardening added per-event source trust/freshness, unresolved-truth event behavior for non-clean source states, and no-route contract coverage
- main-session QC passed py_compile, router generation, router tests, daily-review generation, daily-review tests, and direct JSON inspection; live post-close router emits 23 events, 5 escalations, and one unresolved-truth event under `review_required` source trust
- this is not a new authority lane: no broad web/news crawling, no canonical note mutation, no deployment-state mutation, no config mutation, and no trade execution
- remaining autonomy gaps stay explicit: broader WF26/WF41 source-tier/external intake policy, stable sector/correlation artifact, and append-only state-history / owner-outcome retention

### Recently completed prerequisite workflow
**Workflow 46 - Run Summary Finalization Semantics Gate**

Status:
- targeted implementation/QC completed 2026-05-09
- post-close run summary now normalizes execution state to terminal when safe and exposes ambiguity instead of allowing top-level `status=ok` with internal `chain_status=running`
- main-session QC passed py_compile, run-summary tail-order test, run-summary refresh, dashboard run-summary consumer, and direct artifact inspection
- remaining proof is repeat scheduled post-close run; no current live WF46 blocker remains

### Following approved workflow
**Workflow 47 - Post-Close Authority Vocabulary Reconciliation**

Status:
- targeted implementation/QC completed 2026-05-09 for post-close artifacts
- `postmarket-snapshot.json` and `daily-executive-brief.json` now declare generated dashboard/archive posture with canonical/presentation/portfolio/deployment/trade/owner-approval authority false
- `scripts/pipeline_state_consistency_check.py` now validates post-close authority ceilings against `tmp/run-summary-post-close.json`; `scripts/test_postclose_authority.py` covers the live contract
- main-session QC passed py_compile, authority test, pipeline consistency, market-intelligence router test, daily-review objects test, artifact-index test, and direct artifact inspection
- remaining proof is repeat scheduled post-close run; no current live post-close authority contradiction remains

### Following approved workflow
**Workflow 44 - Command Center Decision Object Visibility and Truth Alignment**

Status:
- bounded implementation/QC completed 2026-05-09 for Promotion Review rendering plus review-only Daily Intelligence / Decision Queue visibility
- Command Center payload now surfaces `deployment_summary.promotion_review`, `today_action.promotionReview`, `trigger_sheet.summary.promotion_review`, and `decision_queue` blocks from daily-review and market-intelligence artifacts
- main-session QC passed dashboard generation, validation, acceptance 18/18, truth lint, and direct payload/HTML inspection
- authority remains display/review-only: no canonical note mutation, no portfolio/deployment mutation, no trade execution, and no inferred owner approval
- remaining WF44 residue: LMT-style dual-layer owner-state / technical-risk rendering remains a follow-up, not closed

### Following approved workflow
**Workflow 45 - Shared Stale Source Fail-Soft Classifier**

Status:
- bounded Slice A implementation/QC completed 2026-05-09
- added `scripts/source_freshness_classifier.py` and tests; dashboard validation, market-intelligence packets, and daily-review packets now carry machine-readable source freshness/trust blocks
- current live state is honest: dashboard integrity is clean, but source trust is `partial / review_required`; clean validation no longer implies clean source trust
- main-session QC passed py_compile, classifier test, dashboard validation, market-intelligence router, daily-review objects, adjacent tests, artifact-index test, and direct artifact inspection
- `scripts/artifact_index.py` chain integration remains blocked until retrieval outputs visibly carry source freshness/provenance and repeat proof is clean
- authority remains read-only/degradation-only; no canonical mutation or owner approval inference

### Deferred / operator-gated sidecars
**Workflow 48 - Regime Scoring Mutation Ownership Decision**

Status:
- closed 2026-05-09 after Randall approved the controlled machine-companion note authority boundary
- `scripts/regime_scoring_refresh.py` may directly update bounded scoring/ranking/freshness blocks in `02. Markets/Regime Scoring Matrix.md`
- final action authority remains with the Deployment Trigger Sheet, Portfolio Snapshot, Risk Rules, and owner approval
- proof passed: targeted authority test, positioning ranking refresh, and full post-close finance chain

**Workflow 49 - FRED Runtime Environment Persistence**

Status:
- added 2026-05-09; blocked on credential/runtime handling after the exposed FRED key is rotated or replaced outside chat

### Previously approved workflow now behind truth-surface hardening
**Workflow 41 - Market Intelligence Event Intake and Materiality Router**

Status:
- added 2026-05-08 as the next finance-automation workflow after WF40 proof/closeout or explicit pause
- purpose is daily read-only event/materiality packet generation from approved source tiers, active/promotion-review names, macro/geopolitical sleeves, sector candidates, and earnings/calendar events
- authority is packet-only: `tmp/` or review-folder writes, no canonical mutation, no thesis/watchlist/deployment mutation, and no execution authority
- implementation must audit existing `scripts/market_intelligence_event_router.py` sidecar behavior before adding new machinery, because a bounded router is already wired ahead of daily review objects

### Following approved workflow
**Workflow 42 - Capital Deployment Recommendation Object**

Status:
- added 2026-05-08 behind WF41
- purpose is to convert research, technical, macro, risk, and fresh-intelligence evidence into a reviewable `deploy / wait / reject / review` packet
- authority is recommendation-only with explicit owner approval field; no trade execution, no account action, no automatic Portfolio Snapshot or Deployment Trigger Sheet mutation
- implementation must compare against existing daily review-object recommendation-prep output and fill only real contract/proof gaps

### Following approved workflow
**Workflow 43 - State History and Review Outcome Retention**

Status:
- added 2026-05-08 behind WF42
- purpose is append-only point-in-time history for deployment state, band status, review outcomes, owner approvals/rejections, and realized later outcomes
- authority is historical retention only; no model-driven deployment and no rewriting prior labels with hindsight
- Randall approved `data/state-history/state-history-v1.jsonl` as the durable path on 2026-05-09; `tmp/state-history-v1.jsonl` remains proof-only residue
- next proof contract: compile/test state-history script, sample post-close row, append to durable path, validate durable JSONL, and inspect provenance/authority fields before any consumer wiring
- this is the honest prerequisite for future WF27-style predictive datasets, not a modeling or trading workflow

### Paused follow-up lane
**Workflow 37 - Daily Summary Commercial Brief Hardening**

Status:
- Phase 1 through Phase 5 are landed: packet proof, writer contract, lint proof, first writer trials, and manual-review output posture
- scheduled `morning` and `post-close` chains auto-generate review-only packet JSONs; human-readable draft generation and delivery remain manual/review-only
- remaining work is repeated clean review-only run proof plus delivery-posture decision; cron promotion stays fail-closed

### Following queue items
**SOP / automation optimization backlog**

Status:
- convert recurring operator work into stable procedures only where it reduces drift, not as a second control plane
- candidate 1: startup/session-opening SOP
- candidate 2: morning/post-close closeout SOP for daily summaries and review-only briefs
- candidate 3: incident/degraded-run response SOP for failed cron, run-summary, memory, or artifact states
- candidate 4: cron proof / promotion review SOP before scheduled review-only layers widen
- candidate 5: SOP repository maintenance procedure to prevent sprawl
- candidate 6: read-only workspace archive suggester (`scripts/archive_suggester.py`) before any auto-archive behavior; implemented v1 as suggestion/report-only (`tmp/archive-suggestions.json`, `tmp/archive-suggestions.md`) with `apply_allowed=false`, owner approval required, and no file moves
- candidate 7 / WF50: tmp helper archive cleanup after owner approval; model-routing drift check was folded into `scripts/workspace_governance_truth_check.py`, but the six `tmp/*.py` helpers still need archive-manifest cleanup before boundary warnings clear

### Recently closed truth-architecture hardening lanes

**Workflow 38 - Sector Expansion and Promotion Review Hardening**

Status:
- closed with handoff on 2026-05-07 after `06. Playbooks/WF38 Phase 4 Weekly Cadence and Coverage Closeout - 2026-05-07.md` proved the weekly sector-expansion process is now repeatable and that LLY/CAT have enough owner-layer technical coverage to stay watch-only / review-prep without remaining technically undefined
- closeout left the authority boundary intact: no direct watchlist auto-promotion, no automatic canonical owner-note mutation, and no trade execution widening
- handoff: WF40 now owns the active control-plane lane; WF37 remains paused follow-up for repeated summary-proof work

**Workflow 39 - Mission Posture and SOP Optimization Hardening**

Status:
- closed 2026-05-06 after spawned audit plus independent verification confirmed the new operating posture is reflected across core doctrine, durable memory, tool/model routing, orchestration/spawn governance, operating model, self-improvement skill, queue, registry, continuity, and daily memory
- mission baseline: Veritas main session is the live financial truth surface / final integrator; workspace files are the durable canonical financial database; substantial work defaults to `openai-codex/gpt-5.5` high-thinking helper lanes when available
- no trading, account-action, or automatic canonical finance-note mutation authority was widened

### Previously closed truth-architecture hardening lanes

**Workflow 21 - Recurring Source Bundle and Review Window Pilot**

Status:
- closed 2026-05-06 with HOLD verdict
- proved manual post-close and Sunday review packet runs plus Phase 3 cron design
- no recurring WF21 cron job was created; future activation requires a new approval/proof pass
- closeout audit: `08. Audits/WF21 Schema Island and Closeout Audit - 2026-05-06.md`

**Workflow 31 - Runtime Continuity, Memory Indexing, and Scheduled-Proof Hardening**

Status:
- closed with follow-up on 2026-05-06
- proved builtin memory recall is healthy in fail-closed lexical mode (`openclaw memory index --force` succeeded; deep status shows `provider: none`, `fts-only`, no semantic provider configured)
- daily-note writer remains contained, async auth doctrine was already landed, and morning/Sunday scheduled siblings remain intentionally non-promoted until future current-job proof exists
- closeout audit: `08. Audits/WF31 Runtime Continuity and Scheduled-Proof Closeout Audit - 2026-05-06.md`

**Workflow 26 - Fresh External Intelligence and Geopolitical Verification Pilot**

Status:
- closed with follow-up on 2026-05-06
- Phase 1 source/sleeve map, bounded manual verification-object proof, recurring-review design, and usefulness verdict are complete
- no standalone WF26 cron was authorized; future use stays downstream of existing packet/review windows
- closeout audit: `08. Audits/WF26 External Intelligence Pilot Closeout Audit - 2026-05-06.md`

**Workflow 22 - Canonical Freshness Patch Pilot and Surface Sync**

Status:
- closed with follow-up on 2026-05-06
- Phase 1 inventory narrowed the pilot honestly; Phase 2 dry run forced ETN into higher review; Phase 3 manual apply proof cleaned stale ETN pre-print wording from `Executive Brief`, `This Week`, and `Next Actions`
- no auto-apply, no portfolio/manual-truth mutation, and no thesis/posture widening occurred
- closeout proof: `06. Playbooks/WF22 Freshness Patch Pilot Dry Run and Manual Apply Proof - 2026-05-06.md`

**Workflow 36 follow-up - bounded SQL readiness hardening**

Status:
- closed with follow-up on 2026-05-06
- Slice A added discovery-only `artifact_metadata` summaries for bounded finance artifacts and passed independent audit without canon-shadowing, queue authority, or cron widening
- 2026-05-09 follow-up Slice B added a derived artifact-output SQLite index: `scripts/artifact_index.py` rebuilds `tmp/veritas-artifact-index.sqlite` from current market-intelligence and daily-review JSON outputs; independent QA returned closed-with-follow-up and main-session micro-fixes closed ignore, item-level trust-test, and provenance-display gaps
- Slice B is safe manual-only retrieval support, but not approved for chain integration until stale-source fail-soft behavior is designed and proven
- retrieval hit -> open source files/artifacts before judgment remains explicit
- closeout audit: `08. Audits/WF36 Slice A Retrieval Metadata Follow-up Audit - 2026-05-06.md`
- Slice B audit: `08. Audits/WF36 Slice B Artifact Output SQLite Retrieval QA - 2026-05-09.md`

**Workflow 27 - Predictive Analytics and Forecasting Readiness**

Status:
- closed with follow-up on 2026-05-06
- Phase 1 forecast-question framing, Phase 2 provenance audit, and a bounded Phases 3-4 baseline-method / decision-boundary contract all landed honestly
- predictive work remains blocked on frozen state-history, event-history, and review-outcome retention rather than fake-clean model enthusiasm
- closeout audit: `08. Audits/WF27 Predictive Readiness Methodology Audit - 2026-05-06.md`

**Workflow 23 - Command Center fresh brief and decision surface tightening**

Status:
- closed with follow-up on 2026-05-06
- Phase 1 surface map, Phase 2 sentence-shape / authority contract, and the bounded live overlap edit pass all landed honestly
- the three dashboard surfaces now route back to owner notes instead of acting like a second live-state board
- closeout audit: `08. Audits/WF23 Dashboard Overlap Resolution Audit - 2026-05-06.md`

**Workflow 32 - Finance Surface Contract and JSON Spine Normalization**

Status:
- closed 2026-05-05
- resolved shared finance surface vocabulary, canonical state normalization, trust-gate parity, deployment-check enrichment, and cross-surface contradiction validation

**Workflow 33 - Declarative Finance Chain and Dependency Map Hardening**

Status:
- closed 2026-05-06
- resolved weekly chain ordering, validation freshness visibility, canonical helper adoption in consistency checks, and manifest-backed chain definitions for the finance refresh chain

**Workflow 34 - Workspace Folder Governance and Root Drift Integration**

Status:
- closed with follow-up on 2026-05-05 after Randall explicitly prioritized truth architecture / automation hardening
- archived executable helpers out of `tmp`, moved script backups out of active `scripts`, removed empty `state`, retained Obsidian-owned `attachments`, retained `migration-review.md` as documented review exception, and created `scripts/workspace_boundary_check.py`
- completion audit: `08. Audits/WF34 Folder Boundary Audit and Completion - 2026-05-05.md`

**Workflow 35 - Dashboard and Document Truth-Surface Integration**

Status:
- closed with follow-up on 2026-05-05 after Randall explicitly prioritized truth architecture / automation hardening
- documented dashboard/canonical owner map, machine-companion subordinate policy, and created `scripts/dashboard_truth_lint.py`
- completion audit: `08. Audits/WF35 Dashboard Truth-Surface Audit and Completion - 2026-05-05.md`

**Workflow 36 - Workspace Retrieval Index and SQLite Knowledge Layer**

Status:
- closed with follow-up on 2026-05-05 as a v1 SQL-backed retrieval layer
- SQLite schema now includes documents, headings, links, aliases, owners, artifacts, freshness, runs, and FTS search; SQL is retrieval/cache only, not canon
- completion audit: `08. Audits/WF36 SQLite Retrieval Knowledge Layer Audit and Completion - 2026-05-05.md`

Recent control-plane truth:
- the 2026-05-05 audit confirmed most carry-over items already have downstream owners
- the missing-owner set was narrowed to queue/index truth drift plus runtime/proof residue
- new owner workflows were opened instead of leaving those items as vague follow-up

## Strict ordered execution queue for today (2026-05-05)

1. **WF20 Phase 2A - cron-builder packet standard**
   - status: completed
   - owner: Veritas main lane
   - category: control plane / automation
   - posture: serial
   - deliverable: hardened `06. Playbooks/Cron Job Protocol.md` so every new cron job must specify read-first files, execution order, response contract, stop lines, and spawn recommendation
   - acceptance check: met

2. **WF20 Phase 2B - review cadence and owner map**
   - status: completed
   - owner: Veritas main lane
   - category: control plane / automation
   - posture: serial
   - deliverable: one smallest honest review cadence with overlap-owner and downgrade rules
   - acceptance check: met via `06. Playbooks/Parallel Review Cadence and Owner Map.md`

3. **WF24 Phase 1 - cron build contract and retrofit checklist**
   - status: completed
   - owner: Veritas main lane
   - category: control plane / automation
   - posture: serial
   - deliverable: reusable cron-build contract plus retrofit checklist for live sibling finance jobs
   - acceptance check: met; the contract and checklist now exist and the sibling prompts were retrofitted to match

4. **WF24 Phase 2 through Phase 4 - proof, audit, and closeout**
   - status: completed (closed with follow-up)
   - owner: Veritas main lane
   - category: control plane / automation
   - posture: serial
   - deliverable: controlled proof, independent audit, closeout artifacts, and downstream promotion for the retrofitted cron family
   - acceptance check: met for closure at intended scope; post-close proof is history-visible, while morning/Sunday symmetry remains named residue and reopen-trigger material

5. **WF25 Phase 1 through Phase 4 - desk operating proof and handoff contract**
   - status: completed (closed with follow-up)
   - owner: Veritas main lane
   - category: research / governance
   - posture: serial
   - deliverable: real operating queue, decision objects, first live pilot proofs, downstream handoff contract, and closeout-layer artifacts
   - acceptance check: met for closure at intended scope; the desk can now produce honest admit/defer/hold outcomes without reconstructing chat history
   - closeout rule: satisfied; WF25 now has chain-log, executive-summary, checkpoint, and audit surfaces in progress for final verification

6. **WF28 Phase 1 through Phase 4 - skill coherence hardening and closeout**
   - status: completed (closed with follow-up)
   - owner: Veritas main lane
   - category: skills / governance
   - posture: serial
   - deliverable: land the audit's critical live-skill fixes, resolve the technical-analysis overlap, remove routing-drift assumptions, harden governance hooks, and close with audit-backed honesty
   - acceptance check: met for closure at intended scope; the skill layer now fails closed more cleanly and the governance index is honest about validation posture
   - closeout rule: satisfied; WF28 now has chain-log, executive-summary, checkpoint, and independent-audit artifacts

7. **WF29 Phase 1 - validation tier truth and machine-proof utility design**
   - status: completed (closed with follow-up)
   - owner: Veritas main lane
   - category: skills / validation
   - posture: serial
   - deliverable: honest validation-tier labeling plus bounded machine-proof utility design for swarm handshake / sidecar validators / automation trust block
   - acceptance check: validation tiers and the first executable-proof pilot set are explicit instead of implied
   - current progress: validation-tier posture is explicit, all three bounded proof families landed with local proof, runtime/bootstrap limits are explicit, and independent audit says the workflow is closeout-ready at intended scope
   - closeout rule: satisfied; WF29 now has chain-log, checkpoint, executive-summary, and independent-audit closure artifacts

8. **WF32 - finance pipeline discrepancy resolution (all phases)**
   - status: completed
   - owner: Veritas main lane
   - category: finance surface / JSON contract
   - posture: serial
   - deliverable: (A) BENCH as first-class canonical state; (B) unified state normalizer across deployment_check, board_state_contract, dashboard_payload; (C) trust-gate parity for premarket_snapshot.py; (D) deployment-check enrichment wired into daily_executive_brief.py sections 5-6; (E) pipeline contradiction validator
   - acceptance check: same name cannot silently land in contradictory state buckets across trigger sheet, deployment check, and daily brief surfaces

9. **WF33 - Sunday chain order fix and manifest hardening**
   - status: completed
   - owner: Veritas main lane
   - category: finance chain / automation architecture
   - posture: serial
   - deliverable: weekly_review_skeleton.py moved after fresh band/trigger rebuild in Sunday chain; validation freshness surfaced and stale-aware; manifest-backed chain definitions with step dependencies, expected artifacts, and recovery posture
   - acceptance check: met - synthetic weekly proof, stale-validation degradation proof, 17/17 acceptance pass, and successful manifest-backed post-close run

10. **WF21 Phase 4 - usefulness verdict and closeout recommendation**
    - status: completed
    - owner: Veritas main lane
    - category: research / automation
    - posture: serial
    - deliverable: compare the two real packet runs, document noise / miss analysis, and make an honest widen / hold / stop recommendation
    - acceptance check: met - HOLD verdict is grounded in `tmp/research-automation/intake-packets-20260506-021940.json`, `tmp/research-automation/intake-packets-20260506-152048.json`, and the Phase 3 design artifact without implying live cron proof

11. **WF31 Phase 1 - runtime continuity and scheduled-proof hardening**
    - status: active
    - owner: Veritas main lane
    - category: runtime / infrastructure
    - posture: serial; defer unless live runtime breaks earlier
    - deliverable: bounded owner pass for memory indexing, daily-note writer runtime debt, async exec/auth reconciliation, and scheduled-proof symmetry
    - acceptance check: runtime residue is either fixed or explicitly isolated with honest proof posture
    - opening note: DB-readiness follow-ups from the WF21 audit remain explicit deferred work; do not smuggle them into WF31 unless they directly intersect runtime retrieval/index health.

14. **WF34 Phase 1 - root and boundary inventory**
   - owner: Veritas main lane
   - category: workspace governance / automation truth
   - posture: serial
   - deliverable: classify root drift, executable files in `tmp`, `scripts` debris, and stale generated artifacts
   - acceptance check: every candidate move/archive has an owner decision and reference-check requirement

15. **WF35 Phase 1 - dashboard/document truth-owner map**
   - owner: Veritas main lane
   - category: dashboard / document truth integration
   - posture: serial
   - deliverable: map each dashboard/read-stack surface to its canonical owner, generated inputs, and allowed claims
   - acceptance check: dashboards and machine companions cannot present as canonical portfolio truth

16. **WF36 Phase 1 - local SQLite retrieval index hardening**
   - owner: Veritas main lane
   - category: retrieval / workspace indexing
   - posture: serial
   - deliverable: generated SQLite index, report, query recipes, and non-canonical retrieval rules
   - acceptance check: index build/search are proved and source Markdown remains authoritative

17. **WF26 Phase 1 - fresh external intelligence and geopolitical verification map**
   - owner: Veritas main lane
   - category: research / external intelligence
   - posture: serial
   - deliverable: approved fresh-news / geopolitical source map, pilot sleeves, and unresolved-truth handling rules
   - acceptance check: the lane can keep fast-moving developments visible without rumor-driven false certainty

18. **WF27 Phase 1 - predictive analytics and forecasting readiness**
   - owner: Veritas main lane
   - category: research / quantitative methods
   - posture: blocked until upstream evidence and provenance layers are real
   - deliverable: bounded forecast-question set, target definitions, and data-readiness audit
   - acceptance check: predictive work stays methodology-first rather than model theater

19. **WF22 Phase 1 - stale-claim pilot inventory**
   - owner: Veritas main lane
   - category: note-sync / reconciliation
   - posture: blocked until WF21 yields honest candidates and the queue/runtime cleanup passes stop confusing downstream order truth
   - deliverable: pilot stale-claim list and owner-surface map
   - acceptance check: candidates stay freshness/mechanical, not thesis rewrite

20. **WF23 stays gated**
   - do not open until WF21 and WF22 both become materially real

### Recent completed item
**Workflow 29 - Skill Validation and Machine-Proof Utilities**
- closed with follow-up
- bounded proof utilities are real and locally proved
- WF21 is now the live downstream consumer, while stronger proof-promotion residue is handed to WF31 instead of being implied solved

## Compact execution order

1. Workflow 1 - policy target-range fail-closed hardening [completed]
2. Workflow 2 - residual atomic-write migration [completed]
3. Workflow 3 - external payload schema guards [completed]
4. Workflow 3B - independent workspace QA audit and QA-pass skill creation [completed]
5. Workflow 3C - canonical-note trust gate enforcement [completed]
6. Workflow 4 - sequential chain protocol [completed]
7. Workflow 4B - live cron shakedown + run ledger hardening [completed]
8. Workflow 4C - finance chain truth-sync hardening [completed]
9. Trust-grade reassessment / warning-residue gate [completed - closed with follow-up]
10. Workflow 5 - PDF/Excel workflow-fit pass [completed - closed with follow-up]
11. Workflow 6 - coverage tier framework [completed - closed with follow-up]
12. Workflow 7 - sector coverage expansion plan [completed - closed with follow-up]
13. Workflow 8 - command center chain readiness review [completed - historical no-go preserved; bounded reopen closed]
14. Workflow 9 - research department operating model [completed - closed with follow-up]
15. Workflow 9A - workspace structure and drift cleanup [completed]
16. Workflow 9B - surface alignment and drift-guard hardening [completed]
17. Workflow 10 - subagent/session lifecycle reliability review [completed]
18. Workflow 11 - coverage admission model [completed]
19. Workflow 12 - macro / policy trust repair [completed]
20. Workflow 13 - script and tmp hygiene hardening [completed]
21. Workflow 14 - operator script boundary and lifecycle cleanup [completed]
22. Workflow 15 - script performance and payload modularity backlog [deferred]
23. Workflow 17 - sequential workflow contract and skills hardening [completed]
24. Workflow 18 - spawn, closeout, and skills governance hardening [completed]
25. Workflow 16 - research automation and canonical freshness hardening [closed with follow-up]
26. Workflow 16A - research intake desk and parallel review packets [completed]
27. Workflow 16B - canonical freshness sync and gated note update helpers [completed]
28. Workflow 19 - playbooks retrieval and governance cleanup [closed with follow-up]
29. Workflow 20 - parallel agents automation and human-gated review workflow [closed with follow-up]
30. Workflow 24 - cron job build contract and session handoff hardening [closed with follow-up]
31. Workflow 25 - research department completion and coverage admission operations [closed with follow-up]
32. Workflow 28 - skills critical corrections and coherence hardening [closed with follow-up]
33. Workflow 29 - skill validation and machine-proof utilities [closed with follow-up]
34. Workflow 30 - workflow queue truth and carryover governance reconciliation [closed: control-surface reprioritization complete 2026-05-06]
35. Workflow 32 - finance surface contract and JSON spine normalization [closed - 2026-05-05]
36. Workflow 33 - declarative finance chain and dependency map hardening [closed - 2026-05-06]
37. Workflow 21 - recurring source bundle and review window pilot [closed with follow-up - HOLD verdict 2026-05-06]
38. Workflow 31 - runtime continuity, memory indexing, and scheduled-proof hardening [closed with follow-up - 2026-05-06]
39. Workflow 34 - workspace folder governance and root drift integration [closed with follow-up]
40. Workflow 35 - dashboard and document truth-surface integration [closed with follow-up]
41. Workflow 36 - workspace retrieval index and SQLite knowledge layer [closed with follow-up; SQL/SQLite v1 landed]
42. Workflow 26 - fresh external intelligence and geopolitical verification pilot [closed with follow-up - bounded review-first external-intelligence layer proved 2026-05-06]
43. Workflow 27 - predictive analytics and forecasting readiness [closed with follow-up - methodology spine landed 2026-05-06]
44. Workflow 22 - canonical freshness patch pilot and surface sync [closed with follow-up - narrow ETN stale-wording pilot proved 2026-05-06]
45. Workflow 23 - Command Center fresh brief and decision surface tightening [active after Workflow 27 closeout]

## Capacity rule for this queue

At one time:
- 1 active OpenClaw subagent implementation lane
- 1 active Claude review lane
- 0 or 1 cheap helper lane

Do not open multiple cleanup or governance implementation lanes at once unless the merge cost is clearly lower than the speed gain.

## Queue hardening rule

- keep execution order explicit
- update this queue before opening a new major lane when real blockers or prerequisites change
- prefer a named workflow over chat-only residue
- do not widen scope mid-chain without updating the queue entry
- do not mark a workflow advanced unless execution mode and QC posture are visible here or in the registry
- sequential advancement is contract-gated: the queue may move from one workflow to the next only when the active workflow's continuity note, acceptance gates, and required artifacts prove completion or a bounded handoff
- cron may run a workflow-advancement preflight / control-plane update pass, but it must fail closed if gates are ambiguous; heartbeat must not advance the queue and may only flag drift or missing continuity
- workflow lookup must resolve the exact live continuity filename before any status or advancement claim

## History rule

Use `06. Playbooks/OpenClaw Parallel Pilot Queue - History.md` for:
- detailed completed-workflow history
- long-form rationale from older completed items
- preserved historical proof context that no longer belongs in the active operator surface
