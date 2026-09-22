# Finance Alert Canon Surface Ownership Procedure

Status: active replacement for the retired portfolio-truth procedure as of 2026-08-29.

## Purpose

Prevent alert, recommendation, evidence, freshness, and workflow truth from fragmenting across human canon, guarded SQL, generated proofs, dashboards, and continuity notes.

## Active ownership

| Surface | Owns |
|---|---|
| `03. Alerts and Recommendations/Investor Profile.md` | Owner objectives and alert/recommendation preferences |
| `03. Alerts and Recommendations/Alert Trigger Policy.md` | Generic signal conditions and alert-state definitions |
| `03. Alerts and Recommendations/Alert Bands and Invalidation Register.md` | Ticker-level thesis and alert interpretation only |
| `03. Alerts and Recommendations/Alert Operations Board.md` | Read-only routes, validation, and governance boundaries |
| Guarded SQL `reference_levels` | Live numeric bands, invalidation, level timestamps, and band status |
| Guarded SQL and generated proofs | Structured evidence and derivation; never approval, account, or execution authority |

## Resolution rule

1. Verify source lineage, evidence date, freshness, and exact owner.
2. Regenerate only derived proof through its governed route when stale.
3. Propose an alert-canon correction through the exact alert validation path when human canon is wrong.
4. Stop on unresolved contradictions; never infer approval or create portfolio, account, order, or execution state.

<details>
<summary>Retired portfolio-era procedure — non-operative</summary>

The preserved procedure below is historical only. Its portfolio owners, mutation gates, sizing/sleeve permissions, and apply routes were retired on 2026-08-29.

# Portfolio Truth Surface Ownership Procedure

## Purpose

Prevent portfolio and workflow truth from fragmenting across canonical notes, generated artifacts, dashboards, queues, memory, and continuity notes.

Use this procedure when a finance surface disagrees with another surface, when adding a new report/artifact, when closing a workflow that touched portfolio truth, or when recovering after compaction and deciding what to read first.

## Operating principle

Every surface gets one job. No generated surface becomes truth just because it is polished, fresh, or machine-readable.

The required spine is:

```text
script proof -> validator -> canonical owner note -> continuity checkpoint
```

## Surface ownership map

| Surface class | Owns | Examples | Does not own |
|---|---|---|---|
| Canonical portfolio notes | Portfolio truth: posture, deployability, execution discipline, watch/repair state, risk envelope | `03. Portfolio/Portfolio Snapshot.md`; `03. Portfolio/Execution Board.md`; `04. Research/Coverage and Watchlist.md`; `07. Risk/Risk Rules.md` | machine proof, run status, workflow history, inferred approval |
| Scripts / `tmp/` artifacts | Evidence, generated proof, proposals, validation payloads, review packets | `tmp/dashboard-validation.json`; `tmp/deployment-readiness-surface.json`; `tmp/full-portfolio-view.*`; `tmp/finance-discrepancy-resolver.*`; `tmp/current-window-artifacts.*` | canonical portfolio truth or owner approval |
| Validators / guardrails | Pass/fail proof, contradiction detection, authority checks | `tmp/dashboard-validation.json`; `tmp/board-canon-guardrail.*`; proposal validators | final judgment or permission to mutate portfolio state |
| `06. Playbooks/Active Workflows.md` | Live workflow state: active, paused, blocked, cron-owned, archive-ready, next action | Active workflow table; cron-owned monitors; archive queue | detailed workflow history or portfolio truth |
| One continuity note per active workflow | Workflow pickup context and phase residue | `06. Playbooks/Project Continuity/Workflow XX - ...md` | global queue truth, canonical portfolio truth, or duplicate phase logs |
| `06. Playbooks/Startup Truth Index.md` | Post-compaction/navigation map: what to read first | startup recovery order and owner-note routing | canonical truth or workflow authority |
| `memory/YYYY-MM-DD.md` | Material daily deltas only | daily facts, closure notes, approved decisions | procedure text, workflow history dump, canonical truth |
| `MEMORY.md` | Durable preferences, decisions, and lessons | durable owner decisions and operating preferences | daily detail or transient run state |
| `09. Archive/` | Retired material after owner-approved archive/move | archived continuity notes, old reports | live workflow or portfolio truth |

## Trigger conditions

Run this procedure when any of these happen:

1. A generated artifact disagrees with a canonical note.
2. A dashboard/brief/full-portfolio view says something different from portfolio notes.
3. A workflow creates a new report, validator, proposal object, or dashboard surface.
4. A workflow closeout tries to claim readiness from generated output alone.
5. Startup/compaction recovery would otherwise reread many files to find the current truth.
6. Archive or cleanup work finds multiple old notes describing the same state.

## Read first

1. `06. Playbooks/Startup Truth Index.md`
2. `06. Playbooks/Active Workflows.md`
3. The exact canonical owner notes involved:
   - `03. Portfolio/Portfolio Snapshot.md`
   - `03. Portfolio/Execution Board.md`
   - `04. Research/Coverage and Watchlist.md`
   - `07. Risk/Risk Rules.md`
4. The exact generated artifact or validator that triggered the discrepancy.
5. The owning workflow continuity note only if workflow state or pickup context matters.

Do not reread the full finance stack by habit.

## Procedure

### 1. Classify the claim

Ask: what is the surface trying to say?

- portfolio truth claim -> canonical note owner required
- generated evidence/proposal -> `tmp/` / script proof layer
- pass/fail or contradiction -> validator/guardrail layer
- workflow status -> `Active Workflows.md`
- resume context -> workflow continuity note
- historical material delta -> daily memory
- retired material -> archive

### 2. Identify the owner

Use the surface ownership map above. If two surfaces appear to own the same truth at the same level, assign one owner and demote the other to evidence/proposal/navigation.

### 3. Resolve conflict directionally

If a generated artifact conflicts with canonical notes:

- treat the artifact as stale or unpromoted unless validator evidence proves the canonical note is stale
- queue a bounded canonical sync review when the canonical note likely needs freshness/status update
- do not silently let the artifact overwrite canon

If canonical notes conflict with each other:

- inspect the latest validated artifacts and source evidence
- apply only allowed bounded freshness/status sync
- escalate owner-gated portfolio mutations separately

If workflow surfaces conflict:

- `Active Workflows.md` wins for live state
- reconcile detailed queue/registry/history surfaces later

### 4. Validate before claiming closure

Use the smallest relevant proof gate:

- script compile/test if code changed
- relevant validator/guardrail if artifact contracts changed
- direct `rg`/file inspection if only docs changed
- config validation only if runtime config changed

### 5. Write the durable pickup point

- active workflow state -> `Active Workflows.md`
- specific workflow resume details -> one workflow continuity note
- material daily delta -> `memory/YYYY-MM-DD.md`
- durable doctrine/preference -> `MEMORY.md`, `USER.md`, `TOOLS.md`, or a skill/procedure as appropriate

Do not create a new durable phase note when the owner surface can be updated instead.

## Stop lines

- No trade, account action, inferred owner approval, cash/risk-rule mutation, or execution entitlement. Sizing/sleeve/sector-posture/ticker-state/entry-band mutations require exact validator-backed approved gates.
- No generated artifact may silently become canonical portfolio truth.
- No clean validator result may imply owner approval.
- No dashboard, PDF, full-portfolio view, or briefing surface outranks canonical notes.
- No archive/move/delete without owner approval and reference checks.
- No broad startup reread when `Startup Truth Index.md` and `Active Workflows.md` can route the task.

## Proof of use

This procedure was promoted after repeated May 2026 failures where generated/dashboard surfaces could lag or contradict canonical notes, including MSFT/full-portfolio-view drift and stale deployment/trigger/dashboard residues. WF58/WF59 established the operating spine and the post-compaction routing model.

## Next action after this procedure

If the procedure identifies a real contradiction, either:

1. refresh/regenerate the stale artifact and validate it, or
2. prepare a bounded canonical-note sync proposal for Veritas main review, or
3. route through the exact gated apply path or ask Randall for explicit approval if the fix would change portfolio mutation, owner approval, sizing, sleeve, sector posture, cash, risk-rule, or execution entitlement.

</details>
