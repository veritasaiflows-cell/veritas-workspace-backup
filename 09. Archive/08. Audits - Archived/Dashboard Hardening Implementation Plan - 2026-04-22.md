# Dashboard Hardening Implementation Plan

**Date:** 2026-04-22
**Purpose:** phased implementation plan for hardening the Veritas command-center dashboard before treating it as a trusted execution surface.

## Objective

The next dashboard pass should prioritize truthfulness, integrity, and drift resistance over visual polish.

The current dashboard architecture is materially improved, but it still overstates confidence in a few critical places. This plan breaks the hardening work into phases so the next implementation cycle can be executed cleanly.

---

## Phase 1, Truth and trust repair

**Goal:** stop the dashboard from overstating confidence.

### Do
- tighten `exec_freshness` logic in `scripts/generate_dashboard.py`
- degrade freshness when:
  - any critical source is `partial`
  - critical fields are null or missing
  - required sub-blocks are empty
  - market/session timing makes data operationally stale
- replace all `|| 0` style fallbacks in `scripts/dashboard-template.html`
- render missing numeric fields as `—`, `Unavailable`, or `Partial`
- add a visible trust/status panel in the dashboard showing:
  - machine-refreshed
  - manual
  - partial
  - stale
  - missing

### Success criteria
- dashboard never shows `fresh` when key macro/execution fields are partial or missing
- no missing market values render as fake numeric zeros
- user can tell in seconds what is manual versus machine-fed

---

## Phase 2, Integrity and contradiction checks

**Goal:** catch bad or conflicting data before it becomes a polished lie.

### Do
Add validation in `scripts/generate_dashboard.py` for:
- posture vs `above20/50/200`
- close vs MA levels
- `inBand` vs computed band gap
- `belowStop` vs stop distance
- action state vs blocker/stop conditions
- earnings date sanity
- portfolio concentration math sanity

Create an `integrity_warnings` or `validation` block in `tmp/dashboard-data.json`.

Surface those warnings in the dashboard UI.

### Success criteria
- contradictory records are flagged loudly
- invalid records do not silently render as if normal
- dashboard becomes self-auditing instead of just decorative

---

## Phase 3, Move logic out of the template

**Goal:** make the template mostly presentation, not hidden business logic.

### Do
Move from `scripts/dashboard-template.html` into `scripts/generate_dashboard.py`:
- compliance evaluation
- concentration checks
- trigger interpretation
- status text generation
- risk summaries
- any hardcoded ticker group logic

Pass fully prepared display objects through `dashboard-data.json`.

Keep the template responsible mainly for:
- layout
- styling
- rendering precomputed fields

### Success criteria
- little or no business logic remains in JS
- future changes happen mostly in Python/config, not in scattered template code
- template becomes thinner and easier to trust

---

## Phase 4, Remove remaining hardcoded semantics

**Goal:** make config the single source of truth.

### Do
Move any remaining hardcoded semantics into `tmp/portfolio-config.json` or another explicit config source:
- concentration ticker groups
- compliance group definitions
- risk categories
- regime labels if still duplicated
- any portfolio classification assumptions

Then make the generator consume those fields directly.

### Success criteria
- no meaningful portfolio/risk logic is hardcoded in template JS
- dashboard behavior can be changed from config without editing presentation code
- drift risk drops materially

---

## Phase 5, Improve freshness semantics for real workflow use

**Goal:** make dashboard timing match trading reality, not just file age.

### Do
Make freshness market-aware:
- distinguish same-session fresh vs prior-session stale
- distinguish overnight acceptable vs pre-open unacceptable
- apply stricter rules for execution-related widgets than slow-moving portfolio widgets

Suggested categories:
- `fresh`
- `usable_with_caution`
- `partial`
- `stale`
- `missing`

Use these categories both in payload and UI.

### Success criteria
- a 38-hour-old market snapshot does not present like same-day execution data
- portfolio config can still be valid while market context is degraded
- dashboard reflects operational reality, not just file timestamps

---

## Phase 6, Strengthen operator-facing UX

**Goal:** make uncertainty and caveats structurally visible.

### Do
Add or improve:
- trust panel
- integrity warnings panel
- manual-fields summary
- partial-data summary
- stronger header indication when execution context is degraded
- more explicit labels on:
  - manual fields
  - best-effort fields
  - partial sections

Also clean up edge cases like:
- earnings `TODAY` vs `TMRW`
- trigger labels overstating readiness
- overview cards implying confidence beyond the payload

### Success criteria
- the UI highlights uncertainty instead of hiding it in fine print
- operator can see at a glance what not to trust fully
- dashboard becomes more honest without becoming noisy

---

## Phase 7, Workflow integration and operating policy

**Goal:** fit the dashboard cleanly into the workspace and daily process.

### Do
Once hardening is done:
- update `scripts/README.md` to reflect the real architecture and trust rules
- update any dashboard usage notes in workspace files
- define how the dashboard is used relative to:
  - Weekly Positioning Review
  - Daily Execution Card
  - Event-driven updates

Recommended role:
- dashboard = fast visual operating surface
- daily card = narrative execution layer
- weekly positioning review = standing weekly logic
- event-driven notes = interpretation of major changes

### Success criteria
- dashboard has a clear role, not overlapping confusion
- workflow says when to rely on it and when to fall back to notes
- no conflicting source-of-truth problem between dashboard and vault notes

---

## Phase 8, Final acceptance pass

**Goal:** verify that the hardening actually worked.

### Do
Run a formal acceptance review:
- missing market field test
- partial macro feed test
- stale source test
- contradiction test
- earnings date change test
- blocker/stop/in-band state transition test

Then score:
- trustworthiness
- clarity
- drift resistance
- maintainability
- execution usefulness

### Success criteria
- dashboard can fail honestly
- degraded data produces degraded UI
- contradictions are surfaced, not hidden
- trust score materially improves

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

## Implementation status, 2026-04-23

- Phases 1 through 7 are now implemented in the active dashboard generator, template, validator, and supporting docs.
- The generator now emits governed trust states, contradiction warnings, manual-dependency visibility, and a dedicated validation artifact.
- Final acceptance review remains separate. Keep Phase 8 open until the formal acceptance pass is documented.

## Blunt advice

Do not start with design polish.
Do not start with new widgets.
Do not start with animation or layout tweaks.

The next version wins by being **more truthful**, not prettier.
