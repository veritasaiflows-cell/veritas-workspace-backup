# Workflow 22 - Canonical Freshness Patch Pilot and Surface Sync

## Objective
- Turn the approved canonical-freshness-patch contract into a bounded pilot that can find stale claims, draft narrow patch proposals, and surface downstream sync needs without pretending to own judgment.
- Keep freshness help narrow, reversible, and fully human-gated.
- Prove that freshness patching can support the daily and weekly operating chain without becoming an autonomous rewrite lane.

## Current State
- closed with follow-up on 2026-05-06 after a bounded dry run and manual apply proof
- WF26 handed forward a bounded input posture only: mechanical/alignment freshness candidates emerging from the WF21/WF26 intake path, plus explicit owner-surface mapping
- early QA challenge found one real scope bug before Phase 2: **ETN is not a safe normal patch candidate yet** because primary-source capture stayed incomplete and the packet itself flagged thesis-drift risk
- ETN may still be used in Phase 2 only as a **higher-review contradiction/alignment dry run** against stale pre-print wording on approved owner surfaces; it is not a normal safe candidate
- NVDA timing and oil / Hormuz remain valid only as fail-closed rejection examples, not normal patch candidates
- JPM may be used only on approved owner surfaces like brief/dashboard notes named in the contract, not portfolio/manual-truth surfaces
- Phase 1 inventory is now captured in `06. Playbooks/WF22 Phase 1 Pilot Stale-Claim Inventory and Owner-Surface Map - 2026-05-06.md`
- Phase 2 dry run and Phase 3 manual apply proof are now captured in `06. Playbooks/WF22 Freshness Patch Pilot Dry Run and Manual Apply Proof - 2026-05-06.md`
- The canonical patch contract already exists: `06. Playbooks/Research Automation Canonical Freshness Patch Contract.md`.
- The exact v1 patch-proposal input shape now exists: `06. Playbooks/Research Automation Freshness Candidate Input Contract.md`.
- `scripts/canonical_freshness_patch.py` now exists as a review-only prototype for freshness candidate preparation.
- Workflow 16B already proved manual-only low-risk mirror-surface freshness fixes.
- The intake-packet and routing contracts now explicitly allow `canonical_freshness_patch_candidate` as a review-only route.
- No recurring patch cron or auto-apply helper is live.

## Scope
- choose a bounded pilot target set
- define how stale claims are found and verified
- define the patch-candidate packet shape and downstream sync checklist
- prove narrow manual-review patch handling on a small set of surfaces
- decide whether a later gated helper is justified

## Out of Scope
- autonomous patch apply
- thesis rewrite disguised as freshness
- deployment-state change
- target-weight or posture change
- broad note reconciliation across the whole vault

## Sequential phase approach

### Phase 1 - Pilot target and stale-claim inventory
Purpose:
- choose the limited note set and stale-claim classes worth testing

Required outputs:
- pilot note list
- stale-claim inventory
- freshness classes per target
- owner-surface map for each candidate

Status:
- completed

### Phase 2 - Patch-candidate dry run
Purpose:
- generate narrow patch candidates and verify whether they stay mechanical/alignment-only

Required outputs:
- sample patch candidates
- verifier notes on source quality and conflicts
- affected-surface list and downstream sync notes
- rejection examples for anything that behaves like thesis rewrite

Status:
- completed

### Phase 3 - Manual apply proof
Purpose:
- prove that approved candidates can be applied reversibly without widening authority

Required outputs:
- exact old/new text capture
- rollback note
- direct inspection or validation proof
- downstream surface-sync record

Status:
- completed

### Phase 4 - Keep / widen / stop decision
Purpose:
- decide whether a later gated helper is useful enough to justify further automation

Required outputs:
- pilot verdict
- reopen triggers
- explicit no-auto-apply posture or approved narrow next step

Status:
- completed

## Daily / Weekly chain insertion
- **Post-close / post-earnings**: patch candidates may be prepared only after refresh artifacts and packet review exist.
- **Sunday weekly chain**: allowed as a review pass for stale weekly surfaces and alignment checks.
- **Pre-market**: no freshness patch lane in v1.
- **Event-driven**: manual only unless a named pilot target is already approved.

## Operating chain
1. receive a high-confidence narrow freshness issue from WF21 packet review or direct operator review
2. write it into `Research Automation Freshness Candidate Input Contract.md` shape
3. run `python scripts\canonical_freshness_patch.py --input <file>`
4. inspect proposal status, rejection reasons, and downstream sync list
5. approve or reject in the main session
6. if approved later, apply manually and record rollback + validation proof

## Immediate-use posture
Use it now as a manual review-only lane:
1. identify a stale claim on a pilot surface
2. write the candidate in the exact shape required by `06. Playbooks/Research Automation Freshness Candidate Input Contract.md`
3. run `python scripts\canonical_freshness_patch.py --input <file>`
4. inspect proposal status, rejection reasons, and downstream sync needs
5. require main-session approval before any apply

## Acceptance Gates
Workflow 22 should not close unless all are true:
1. the pilot target list is explicit and narrow
2. patch candidates stay mechanical/alignment-only unless explicitly rejected
3. every approved apply remains reversible with exact old/new text capture
4. downstream surface-sync requirements are visible
5. no autonomous canonical mutation or hidden judgment drift occurs
6. the pilot produces a clear keep / widen / stop decision

## Phase 2 admission rule
- Only candidates that are still clearly mechanical/alignment-only may enter the dry run as normal proposals.
- Demote to rejection-only or stop-line examples when primary capture is incomplete, source quality is unresolved, or the packet itself flags thesis drift.
- Current bounded posture:
  - keep `GOOG / MSFT` post-earnings wording cleanup as likely normal candidates if the patch stays entry-neutral
  - keep `NVDA timing path` as rejection-only / stop-line proof unless primary confirmation becomes clean
  - keep `oil / Hormuz sleeve` as verification-only rejection proof
  - keep `JPM` only on approved owner surfaces, never portfolio/manual-truth surfaces
  - remove `ETN` from the normal Phase 2 target set; allow it only as a higher-review contradiction/alignment dry run if the stale sentence is exact and the replacement text stays limited to reported/interpreted status plus explicit primary-capture incompleteness

## Next Action
- Hand the queue to the bounded WF36 follow-up. Keep SQL/retrieval work subordinate to source files and artifacts, and do not let the retrieval layer become a second judgment or queue-advancement surface.

## Key Files
- `06. Playbooks/Research Automation Canonical Freshness Patch Contract.md`
- `06. Playbooks/Research Automation Freshness Candidate Input Contract.md`
- `06. Playbooks/Research Automation Intake Packet Contract.md`
- `06. Playbooks/Research Automation Routing and Promotion Contract.md`
- `06. Playbooks/Cron Job Protocol.md`
- `scripts/canonical_freshness_patch.py`
- `06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md`
- `06. Playbooks/WF22 Phase 1 Pilot Stale-Claim Inventory and Owner-Surface Map - 2026-05-06.md`
- `06. Playbooks/WF22 Freshness Patch Pilot Dry Run and Manual Apply Proof - 2026-05-06.md`
