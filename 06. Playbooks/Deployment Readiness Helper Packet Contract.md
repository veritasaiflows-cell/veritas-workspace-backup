# Alert Evidence Repair Packet Contract

Status: active replacement for the retired deployment-readiness contract as of 2026-08-29.

## Purpose

Define bounded, read-only packets that repair or explain missing evidence for alerts and non-executing recommendations without creating a competing truth layer.

## Packet contract

Each packet must identify:

- ticker and timeframe
- question or alert condition being evaluated
- source lineage and evidence date
- freshness and confidence
- thesis, catalyst, risk, and invalidation context
- unresolved contradictions or missing evidence
- Randall's decision point, when one exists

Packets may recommend research, source repair, freshness repair, or human review. They may not change alert canon, promote an execution state, create portfolio/account/order state, or invoke paper/live execution.

## Output

Use a clearly non-canonical proof location under `tmp/` with deterministic provenance and validation. A packet remains evidence only until Main checks it against the active owners in `03. Alerts and Recommendations/`.

<details>
<summary>Retired deployment-era contract — non-operative</summary>

The preserved contract below is historical only. Its deployment, execution-board, promotion, and action-readiness semantics were retired on 2026-08-29.

# Deployment Readiness Helper Packet Contract

## Purpose

Define the first helper packets that can support deployment readiness without creating a competing truth layer.

## Global rules

- All helper packets are read-only
- All helper packets stop at packet output
- No helper packet may:
  - move queue state
  - mutate canonical notes
  - make final portfolio conclusions
  - overrule the Execution Board
- Main-session Veritas remains the integrator and final reviewer

## Packet 1 — Admission prep

### Job
Prepare a bounded decision packet for a name that may deserve promotion into the execution board or a tighter deployment review.

### Inputs
- `04. Research/Coverage and Watchlist.md`
- `03. Portfolio/Execution Board.md`
- `tmp/trigger-sheet.json`
- `tmp/deployment-readiness-surface.json`
- current earnings / macro artifacts when relevant

### Output
A packet that states:
- ticker
- current lane / current action state
- why it is being reviewed now
- what gates already pass
- what still blocks promotion
- what evidence is still missing
- recommendation class: `ready for operator review` or `not ready for operator review`

### Stop-line rules
Stop at packet output if:
- catalyst timing is unconfirmed
- thesis language is stale or contradictory across owner surfaces
- validation or trust artifacts are degraded enough to contaminate the result

## Packet 2 — Thesis-drift / news-monitoring intake

### Job
Prepare a read-only packet showing whether recent events appear to threaten or strengthen an execution-board thesis.

### Inputs
- approved news/research bundle
- current thesis surfaces
- current deployment-readiness surface
- active event calendar / post-earnings state

### Output
A packet that states:
- affected name(s)
- event summary
- likely thesis impact: `supports`, `neutral`, `pressures`, or `contradicts`
- whether the issue is immediate deployment-relevance or only broader research relevance
- whether a human Execution Board review is warranted

### Stop-line rules
Stop at packet output if:
- source quality is weak or conflict-heavy
- the issue is clearly research-lane only, not deployment-lane relevant
- the event would require judgment-heavy thesis rewriting rather than bounded review

## Packet 3 — Contradiction / QA packet

### Job
Flag conflicts between machine surfaces and owner notes before those conflicts become false confidence.

### Inputs
- `03. Portfolio/Execution Board.md`
- `tmp/deployment-readiness-surface.json`
- `tmp/trigger-sheet.json`
- `tmp/run-summary-<window>.json`
- validation artifacts

### Output
A packet that states:
- conflicting ticker / surface
- machine claim
- owner-note claim
- probable cause class:
  - stale timing/date
  - stale note wording
  - validation / freshness issue
  - trust-gate downgrade
  - true judgment disagreement
- recommended next action:
  - note review
  - timing confirmation
  - validator rerun
  - no action / acknowledged caution

### Stop-line rules
- contradiction packets may not resolve the contradiction themselves
- they only surface the issue and route it back to operator review

## Output posture

Preferred initial output locations if these packets are later scripted:
- `tmp/deployment-admission-prep.json`
- `tmp/deployment-thesis-drift-intake.json`
- `tmp/deployment-contradiction-qa.json`

These are staging artifacts only. None are canonical notes.

</details>
