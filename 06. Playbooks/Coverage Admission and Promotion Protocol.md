# Coverage Admission and Promotion Protocol

## Purpose
Define how a ticker enters, advances within, or leaves the Veritas tracked universe without reopening Workflow 6's settled lane framework.

This protocol governs procedure, not thesis quality by vibes.

## Inherited lane framework
Use the existing machine lanes only:
- `execution`
- `watch`
- `macro`
- `speculative`

Do not relitigate lane definitions here.

## Core rule
A name may be machine-tracked before it is execution-ready, but it may not be treated as honestly covered unless the required thesis and owner-note obligations are met for its lane.

## Minimum admission gates

### A. Machine-tracked universe admission
Required before adding a name to `tmp/portfolio-config.json` / tracked-universe surfaces:
- ticker, sector, lane, and portfolio-role choice are explicit
- reason for inclusion is explicit in one sentence
- thesis status is not blank
- macro fit is not blank
- trigger condition is not blank
- owner note destination is named up front
- next review condition is explicit (earnings, valuation reset, technical base, macro catalyst, etc.)

### B. Honest written-coverage admission
Required before a name is treated as thesis-covered in `04. Research/Coverage Universe.md`:
- full thesis block exists
- key risk is explicit
- act-when condition is explicit
- status language does not overstate deployment readiness

### C. Execution-lane promotion
Required before promotion into the execution lane:
- thesis block exists in `04. Research/Coverage Universe.md`
- live deployment state is defined in `03. Portfolio/Deployment Trigger Sheet.md`
- explicit entry band and stop exist in `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- earnings/timing blocker posture is explicit
- portfolio competition is real (the name is being compared against other capital uses, not just admired)

## Owner-boundary map
- `tmp/portfolio-config.json` -> machine-tracked universe, lane, workflow state
- `02. Markets/Watchlist.md` -> high-level mirror of the machine-tracked universe
- `04. Research/Coverage Universe.md` -> thesis coverage and promotion logic
- `03. Portfolio/Deployment Trigger Sheet.md` -> deployment entitlement and action state
- `03. Portfolio/Technical Entry and Invalidation Sheet.md` -> entry bands, stops, and invalidation logic
- `03. Portfolio/Portfolio Snapshot.md` -> actual position/posture once capital is competing or allocated

Do not let a mirror note invent a greener state than the owner note.

## Admission checklist
1. Decide lane (`execution`, `watch`, `macro`, `speculative`)
2. Record machine fields in `tmp/portfolio-config.json`
3. Update `02. Markets/Watchlist.md` if the name is in the tracked universe
4. Add or update the thesis block in `04. Research/Coverage Universe.md`
5. If execution-lane eligible, update Trigger Sheet and Technical Entry sheet in the same pass
6. If capital competition changes, update Portfolio Snapshot
7. Re-run validators / affected downstream checks

## Promotion / demotion rules

### Promote to execution
Only when:
- thesis exists
- levels exist
- timing blockers are honest
- the name deserves real capital competition now

### Demote from execution to watch
When any of these become true:
- levels are missing or stale
- repair mode begins
- earnings/timing block turns the setup non-actionable
- a stronger name displaces it and the weaker one becomes secondary research only

### Remove from tracked universe
When any of these become true:
- no durable reason remains to monitor it
- note maintenance cost exceeds expected decision value
- the thesis no longer fits the portfolio framework
- a cleaner sector proxy fully replaces it

Removal requires updating both machine and note mirrors in the same pass.

## LLY pilot result
`LLY` is the first bounded live intake pilot under Workflow 11.

Pilot outcome:
- remain in the `watch` lane
- keep `portfolio_role=watch_only`
- thesis block now exists in `04. Research/Coverage Universe.md`
- no execution-lane promotion because valuation/setup and explicit levels are still undefined

This is the model for future watch-lane admissions:
- thesis-covered
- machine-tracked
- not falsely deployable

## No-go assumptions
- do not add a tracked name just because it is interesting
- do not promote to execution without levels and timing posture
- do not let `Watchlist.md` or quick-reference wording imply a greener state than Trigger Sheet / Technical Entry
- do not leave machine-tracked names without thesis coverage indefinitely

## Workflow 11 closure standard
Workflow 11 is honestly closed when:
- the procedure is explicit
- the live pilot (`LLY`) is complete
- existing thesis-coverage residue names are resolved or intentionally removed
- owner-boundary mutations are clear enough that the next ticker can be admitted without reconstructing chat history
