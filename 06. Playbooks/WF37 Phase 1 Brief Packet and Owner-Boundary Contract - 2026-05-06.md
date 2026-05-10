# WF37 Phase 1 Brief Packet and Owner-Boundary Contract - 2026-05-06

## Purpose
Define the first safe implementation slice for commercial-grade daily briefs:
- deterministic summary artifacts remain the evidence pack
- machine packet producers prepare bounded AI input
- any future AI-written brief stays review-only and owner-subordinate until later proof widens trust

## Surfaces under this phase
- `01. Dashboards/Pre-Market Snapshot/YYYY-MM-DD.md` - deterministic morning fact pack
- `01. Dashboards/Post-Market Snapshot/YYYY-MM-DD.md` - deterministic post-close fact pack
- `01. Dashboards/Daily Executive Summary/YYYY-MM-DD.md` - current post-close machine narrative / summary surface
- `tmp/premarket-brief-input.json` - new bounded morning AI handoff packet
- `tmp/postclose-brief-input.json` - new bounded post-close AI handoff packet

## Canonical owners
- deployment state: `03. Portfolio/Portfolio Snapshot.md`
- trigger / entry logic: `03. Portfolio/Deployment Trigger Sheet.md`
- weekly operating stance: `05. Intelligence/Weekly Positioning Review.md`
- event timing / catalyst canon: `05. Intelligence/Event Calendar.md`

## Governing rule
The packets may improve commercial presentation and review speed.
They may not publish owner state on their own.

## Packet minimum fields
Each packet must include:
- `schema_version`
- `workflow`
- `generated_at_utc`
- `window`
- `review_window`
- `target_note`
- `consumer_posture`
- `canonical_mutation_allowed`
- `market_data_as_of`
- `note_date`
- `owner_layers[]`
- `source_artifacts.required`
- `source_artifacts.optional`
- `trust`
- `state_summary`
- `unresolved_truths[]`
- `focus_questions[]`
- `narrative_goal`
- `allowed_claims[]`
- `forbidden_claims[]`
- `required_citations[]`
- `delivery_readiness`

## Allowed claim shapes for future AI briefs
- bounded orientation summary
- owner-first routing
- freshness / availability signal
- unresolved-truth warning
- review sequencing

## Forbidden claim shapes
- deployable-now publication from the brief alone
- blocker clearance without owner-note confirmation
- silent conflict smoothing between owner notes
- direct portfolio-authority language
- direct trade instruction
- publishing packet-derived state as if it were canonical

## Window-specific intent
### Morning
The brief should answer:
- what actually matters before the open?
- what is actionable only in review-first / owner-first terms?
- what trust warnings or catalyst risks cap confidence this morning?

### Post-close
The brief should answer:
- what changed materially since the prior dashboard run?
- what matters for the next session?
- which names are closest to actionable without being overstated?
- what remains unresolved even after the close?

## Stop lines
Fail closed or degrade to review-only if:
- dashboard validation is critical
- packet inputs are missing or stale enough to break trust
- owner surfaces conflict and the draft tries to smooth it over
- the draft implies a state promotion not present in owner notes
- unresolved truth exists but is not surfaced explicitly

## First implementation slice
1. patch deterministic summary consumers so delta rendering is honest and window wording is accurate
2. emit `tmp/premarket-brief-input.json`
3. emit `tmp/postclose-brief-input.json`
4. inspect outputs before designing the writer contract

## Proof target for Phase 1
- `python -m py_compile` succeeds for the touched scripts
- both packet outputs are generated from live artifacts
- packet JSON clearly marks `consumer_posture: review_only`
- packet JSON clearly marks `canonical_mutation_allowed: false`
