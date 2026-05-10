# WF22 Freshness Patch Pilot Dry Run and Manual Apply Proof - 2026-05-06

## Purpose
Capture the bounded WF22 Phase 2 dry run, Phase 3 manual apply proof, and the usefulness verdict for the first canonical-freshness patch pilot.

## Phase 1 gate used
- `06. Playbooks/WF22 Phase 1 Pilot Stale-Claim Inventory and Owner-Surface Map - 2026-05-06.md`

Phase 1 narrowed the pilot honestly:
- ETN allowed only as a **higher-review contradiction/alignment** case against stale pre-print wording
- GOOG / MSFT kept conditional on exact stale owner-surface wording
- NVDA timing, JPM, and oil / Hormuz remained rejection-only / out of bounds

## Phase 2 dry run
### Input
- `tmp/research-automation/wf22-phase2-etn-dry-run-input-20260506.json`

### Command
- `python scripts\canonical_freshness_patch.py --input tmp\research-automation\wf22-phase2-etn-dry-run-input-20260506.json`

### Output
- `tmp/research-automation/freshness-patch-candidates-20260506-204259.json`

### Dry-run result
- candidate count: `1`
- status mix: `0 proposed`, `1 needs_review`, `0 rejected`
- `apply_allowed: false`

### What the dry run proved
- the helper path did **not** auto-approve ETN
- classing ETN as `cross_surface_contradiction` correctly forced higher review
- the candidate stayed bounded to orientation-surface wording cleanup
- downstream sync stayed visible (`Executive Brief`, `This Week`, `Next Actions`)

## Phase 3 manual apply proof

### Manual approval basis
Approved manually only because the target text was stale **pre-print wording** on orientation surfaces and the replacement stayed narrow:
- no thesis rewrite
- no deployability promotion
- no portfolio/manual-truth mutation
- explicit carry-forward of incomplete primary-source capture

### Exact old/new text capture

#### 1) `01. Dashboards/Executive Brief.md`
**Old**
- `1. **The live action list is narrow.** **JPM**, **NVDA**, and **GS** are the names currently in band. GS is now a confirmed tactical secondary to JPM at Tier 2 sizing. **ETN** remains an event-risk decision into May 5 earnings.`

**New**
- `1. **The live action list is narrow.** **JPM**, **NVDA**, and **GS** are the names currently in band. GS is now a confirmed tactical secondary to JPM at Tier 2 sizing. **ETN** is no longer a pre-print decision; it has already reported and remains a post-earnings review item with incomplete primary-source capture.`

#### 2) `01. Dashboards/This Week.md`
**Old**
- `- **ETN** kept conditional only`
- `- **ETN** remains conditional into the May 5 print.`

**New**
- `- **ETN** moved out of pre-print status and into post-earnings review only`
- `- **ETN** is no longer a pre-print item; it has already reported and remains under post-earnings review pending primary-source follow-up.`

#### 3) `01. Dashboards/Next Actions.md`
**Old**
- `2. **Make the ETN pre-print decision explicit before May 5**`
- `- **ETN** at 425.55 vs. band 395.59–420.31 is only ~1.2% above the band ceiling, but the real issue now is earnings-event risk, not minor entry-distance math.`
- `- Default posture should be stand aside into the print unless an explicit event-risk exception is chosen.`

**New**
- `2. **Keep ETN in post-print review mode**`
- `- **ETN** is no longer a pre-print decision. The live issue is post-earnings interpretation quality because direct primary capture did not land cleanly.`
- `- Default posture should stay review-only until primary-source capture and next-session confirmation remove the remaining ambiguity.`

### Downstream sync record
- `Executive Brief` patched as the primary orientation surface
- `This Week` patched to remove stale pre-print ETN wording
- `Next Actions` patched to remove stale pre-print ETN task language
- no changes made to:
  - `03. Portfolio/Deployment Trigger Sheet.md`
  - `03. Portfolio/Portfolio Snapshot.md`
  - `03. Portfolio/Technical Entry and Invalidation Sheet.md`
  - `02. Markets/Macro Regime Dashboard.md`

### Validation
- direct post-edit inspection confirmed the stale ETN pre-print wording is no longer present in the three patched owner surfaces
- dry-run artifact remained `needs_review`, proving the helper path stayed subordinate and manual-gated

## Phase 4 verdict
- **Close WF22 with follow-up.**
- The pilot proved narrow freshness help is useful for stale orientation-surface cleanup.
- Keep it bounded:
  - manual-review only
  - exact old/new capture required
  - cross-surface contradiction cases stay higher review
  - rumor/geopolitical and thesis/posture cases stay out of bounds

## Reopen triggers
- a future candidate drifts into thesis or posture rewrite
- owner authority becomes ambiguous
- helper output starts acting like a second truth layer
- a later pass tries to patch manual-truth portfolio or macro surfaces automatically

## Next queue handoff
- Move to WF36 follow-up only after control surfaces are updated to show WF22 closed and the SQL/retrieval pass remains retrieval/cache-only.
