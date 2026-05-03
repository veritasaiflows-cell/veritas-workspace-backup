# Workspace Tightening Plan

**Date:** 2026-04-22
**Purpose:** phased cleanup and hardening plan to reduce workspace drift, tighten source-of-truth discipline, and improve structural clarity.

## Objective

The workspace is operational and increasingly capable, but it is now complex enough to generate polished contradictions if doctrine, config, structure, and source-of-truth hierarchy are not tightened.

This plan focuses on reducing drift, cleaning the root, clarifying doctrine, and making the operating model easier to trust.

---

## Phase 1, Resolve doctrine and identity conflicts

**Goal:** eliminate conflicting operating doctrine.

### Do
- review `SOUL.md` and `FINANCE_SOUL.MD` side by side
- decide which file is canonical for identity and operating doctrine
- keep one clear governing identity
- if `FINANCE_SOUL.MD` contains useful finance-specific standards, either:
  - convert it into a subordinate finance doctrine note with explicit scope, or
  - archive it if it conflicts too much
- add one explicit note in the surviving doctrine files about hierarchy so future edits cannot recreate ambiguity

### Success criteria
- there is no ambiguity about active identity
- there is no conflicting doctrine between core soul/mission files
- future sessions cannot read two equally authoritative but different personas

---

## Phase 2, realign config truth with live note truth

**Goal:** stop structured config from drifting behind the actual operating notes.

### Do
- review `tmp/portfolio-config.json` against:
  - `03. Portfolio/Portfolio Snapshot.md`
  - `07. Risk/Risk Rules.md`
  - `03. Portfolio/Deployment Trigger Sheet.md`
  - any current dashboard risk assumptions
- update weights, cash, risk thresholds, concentration assumptions, posture labels, and entry-band-related semantics so they match the live operating posture
- explicitly note which fields are allowed to be manual and how often they must be reviewed
- if needed, add a short header comment or adjacent documentation note defining this file’s role as dashboard/config truth rather than freeform scratch config

### Success criteria
- `tmp/portfolio-config.json` matches live portfolio and risk posture
- dashboard/config layer no longer disagrees with note layer on obvious points
- config drift risk is materially reduced

---

## Phase 3, define source-of-truth precedence

**Goal:** make it explicit which layer wins when files disagree.

### Do
- create a short written source-of-truth hierarchy for:
  - portfolio posture
  - risk posture
  - macro readiness
  - dashboard rendering
  - event dates
- recommended pattern:
  - interpreted portfolio posture lives in notes
  - structured dashboard/config semantics live in `tmp/portfolio-config.json`
  - macro readiness lives in `tmp/market-state.json`
  - dashboard is a derived surface, not an independent truth source
  - timing-critical earnings dates require verified cross-checking when unresolved
- add this hierarchy to the most appropriate operating file or playbook

### Success criteria
- conflicting files can be reconciled quickly
- future maintenance has a clear decision rule
- dashboard and notes stop competing silently as equal truth sources

---

## Phase 4, update workspace standards and governance docs

**Goal:** make written policy match the actual finance-first workspace.

### Do
- review and update any stale workspace-governor standards or reference docs so they reflect:
  - current root structure
  - finance-first folder policy
  - archive policy
  - root-folder discipline
- make sure any standards doc no longer describes the prior consulting/content structure
- check whether related playbooks or helper docs also need alignment

### Success criteria
- written workspace standards match the live vault structure
- skills and governance references stop teaching obsolete structure
- workspace maintenance guidance becomes credible again

---

## Phase 5, clean the root and tighten folder hygiene

**Goal:** make the root folder strict, intentional, and easier to trust.

### Do
- inspect top-level folders and classify each as:
  - canonical active
  - archival
  - generated
  - stray
- remove or relocate empty dead-weight folders such as `state/` if still unused
- decide whether `Evening Review/` is:
  - a real permanent operating folder, or
  - something that should move into a numbered structure or archive
- decide whether `veritas-command-center.html` belongs permanently at root or should be treated as a staged/generated artifact with documented rationale
- tighten root policy so future folders do not accumulate casually

### Success criteria
- every top-level folder has a clear reason to exist
- root becomes visually cleaner and semantically stricter
- review order is not diluted by stray folders

---

## Phase 6, clean scripts and tmp surfaces

**Goal:** reduce clutter in active machine and tooling layers.

### Do
- review `scripts/` for obsolete diagnostics, planning files, or one-off helpers
- archive or remove files that no longer belong in the active operator surface
- review `tmp/` and ensure it is used for generated artifacts, not long-lived helper scripts or scratch work
- relocate scratch utilities to a more appropriate place if they still matter
- keep `scripts/README.md` aligned with the actually supported script surface

### Success criteria
- `scripts/` contains current, intentional tools
- `tmp/` is mostly or entirely machine-artifact territory
- operator judgment is not slowed by old helper clutter

---

## Phase 7, reduce redundancy drift across operating layers

**Goal:** keep the reporting and navigation stack layered, but not duplicative.

### Do
- review the role of:
  - `Executive Brief`
  - `This Week`
  - `Next Actions`
  - `Weekly Positioning Review`
  - `Daily Executive Summary`
  - dashboard
  - trigger sheet
- write or tighten one-line role definitions for each layer
- remove repeated content where a layer is clearly restating another layer without adding value
- preserve layering, but sharpen scope boundaries

### Success criteria
- each operating layer answers a distinct question
- repetition is reduced without collapsing useful structure
- maintenance burden falls and contradiction risk drops

---

## Phase 8, add validation and closure discipline

**Goal:** stop known issues from lingering half-fixed.

### Do
- review prior audits and identify findings that were marked but not actually closed
- create a lightweight closure habit:
  - resolved
  - intentionally deferred
  - still open
- where useful, add simple validation checks for known drift points between notes, config, and generated artifacts
- avoid “noted but never closed” accumulation

### Success criteria
- audit findings close cleanly instead of lingering as ambient debt
- repeated issues become less common
- the workspace gets tighter over time instead of just more documented

---

## Recommended execution order

1. **Phase 1**
2. **Phase 2**
3. **Phase 3**
4. **Phase 4**
5. **Phase 5**
6. **Phase 6**
7. **Phase 7**
8. **Phase 8**

## Blunt advice

Do not solve this by writing more overlapping notes.
Do not let the dashboard, config layer, and note layer all become independent truth systems.
Do not leave doctrine ambiguity alive just because it is tolerable in the moment.

The workspace is already good enough to work.
The next jump comes from making it harder for the system to lie by accident.
