# Workflow 16 - Research Automation and Canonical Freshness Hardening

## Objective
- Build the next automation layer for Veritas without letting scheduled research or note freshness turn into uncontrolled canonical drift.
- Move from internal finance refreshes to review-first research intake, routing, freshness packets, and only later narrowly gated note-update helpers.
- Encode the approved long-run posture: parallel agents are a **contract-building and QA layer**, not a freeform research swarm.

## Current State
- Cron already handles internal finance refresh windows plus control-plane hygiene and health checks.
- The current finance cron posture is intentionally fail-closed: scheduled windows refresh machine artifacts and derived staging surfaces, but canonical notes remain protected when trust fields say internal-only.
- Workflow 17 and Workflow 18 are now closed, so the missing workflow-contract and spawn/closeout governance layer is no longer the blocker.
- Research automation remains **unstarted implementation-wise**: no recurring source bundle, intake packet contract, routing/promotion contract, or canonical freshness patch contract is approved yet.
- Capital Deployment Readiness already proved one important boundary: scheduled review surfaces can be useful daily without giving away canonical judgment ownership.
- **Current gate:** Workflow 16 is now the active readiness gate that should convert Workflow 17 / Workflow 18 outputs into the live research automation skeleton without opening research cron or note-helper execution yet.

## Why this workflow exists
- Randall wants the OS to keep research and canonical notes fresh daily.
- That is now possible in parts, but only if we separate:
  1. trusted evidence intake
  2. review-object creation
  3. routing / promotion decisions
  4. freshness patch drafting
  5. canonical note mutation
- The final step must remain gated until the earlier contracts are repeatedly proven.

## Three-contract research control plane
This workflow now treats the automation lane as a three-contract control plane:

1. **Source Bundle Contract**
   - what evidence is trusted
   - what is blocked or low-confidence
   - what belongs in cron vs manual review vs review packets only
2. **Intake Packet Contract**
   - how evidence becomes a standard review object
   - what every research packet must contain before it can route anywhere
3. **Canonical Freshness Patch Contract**
   - when evidence can propose a change to the truth layer
   - what remains freshness hygiene versus thesis rewrite

A separate **Routing / Promotion Contract** sits between #2 and #3 so the system knows when a packet goes to:
- archive / weekly digest
- dashboard watch item
- weekly intelligence
- thesis-review queue
- canonical freshness patch candidate

## Target posture after successful hardening
```text
Main / Orchestrator
 ├── Contract-building lanes (source bundle / intake schema / routing / patch QA)
 ├── Review lanes (event detection / thesis drift / contradiction / surface impact)
 └── Final Veritas synthesis and approval
 ↓
Approved dashboard/workbook/weekly-brief routing
 ↓
Optional gated canonical freshness patch review
 ↓
Approved canonical note update / queue movement / portfolio judgment
```

## Operating sequence
1. **Source bundle contract**
   - define approved evidence before cron ever runs it
2. **Intake packet contract**
   - define the standard review object for all research lanes
3. **Routing / promotion contract**
   - define weekly brief / dashboard / workbook / thesis-review / patch-candidate routing
4. **Canonical freshness patch contract**
   - define the narrow conditions for touching canonical notes
5. **Bounded pilot**
   - prove the system on a small live set before scale

## Safe automation boundary
- Safe now:
  - scheduled evidence collection
  - scheduled internal finance refreshes
  - scheduled research intake packets
  - scheduled freshness checks and stale-surface detectors
  - contradiction memos and QA packets
  - exact patch/checklist proposals for canonical notes
- Still human-gated:
  - canonical thesis rewrites
  - final portfolio posture changes
  - final macro judgment wording
  - queue movement and workflow advancement
  - any direct note mutation that changes investment judgment rather than freshness hygiene

## Sub-workflows
- `Workflow 16A - Research Intake Desk and Parallel Review Packets`
  - owns Source Bundle Contract
  - owns Intake Packet Contract
  - owns Routing / Promotion Contract
- `Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers`
  - owns Canonical Freshness Patch Contract
  - owns freshness/owner-surface guardrails
  - owns the first bounded pilot after 16A contract completion

## Initial schedule recommendation
- No new research cron should go live before the source bundle, intake packet, and routing contracts are approved.
- Intended windows after approval:
  - weekday premarket research intake packet after morning finance refresh
  - weekday post-close research intake packet after post-close finance refresh
  - Sunday weekly research synthesis packet after Sunday rebuild
  - freshness packet after the relevant refresh window, still patch/checklist only until 16B trust gates are proven

## Trust gates still missing
- approved source bundle by category and tier
- explicit ownership boundary for dashboard, workbook, weekly brief, thesis-review queue, and canonical notes
- approved review windows by source type and event class
- dashboard/workbook handoff contract
- bounded stop lines for rumor-heavy, duplicate, low-confidence, or unsourced events
- canonical-note drift protection and freshness/rewrites separation
- run-history proof that scheduled research packets improve freshness without flooding the note layer
- protocol hardening from Workflow 17 and Workflow 18 so this lane starts from an explicit entry / spawn / closeout / checkpoint contract rather than distributed assumptions

## First bounded pilot target
Do not test broadly first.
Use:
- `NVDA`
- `JPM`
- `ETN`
- `GOOG` / `MSFT` post-earnings revalidation
- Oil / Hormuz / Middle East production-risk sleeve

## Next Action
- Run the Workflow 16 readiness gate now that Workflow 17 and Workflow 18 are closed.
- Confirm that the three-contract research control plane inherits the new workflow/governance standards cleanly.
- Then execute Workflow 16A in order:
  1. Source Bundle Contract
  2. Intake Packet Contract
  3. Routing / Promotion Contract
- Then execute Workflow 16B:
  4. Canonical Freshness Patch Contract
  5. bounded pilot
- Do not schedule autonomous canonical note mutation in v1.

## Key Files
- `06. Playbooks/Major Workflow Contract Standard.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
- `06. Playbooks/Project Continuity/Research Automation - News, Geopolitics, and Thesis Drift Monitoring.md`
- `06. Playbooks/Research Unit Concept.md`
- `06. Playbooks/Project Continuity/Capital Deployment Readiness.md`
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- `05. Intelligence/Weekly Intelligence Brief.md`
- `01. Dashboards/Executive Brief.md`
- `03. Portfolio/Deployment Trigger Sheet.md`
- `05. Intelligence/Event Calendar.md`

## Automation / Refresh Path
- Phase 0: readiness gate using Workflow 17 / Workflow 18 outputs
- Phase 1: source bundle contract
- Phase 2: intake packet contract
- Phase 3: routing / promotion contract
- Phase 4: canonical freshness patch contract
- Phase 5: bounded pilot
- Out of bounds until proven: silent thesis rewrites, autonomous portfolio conclusions, freeform multi-agent debate without orchestrator control, or noisy alert spam
