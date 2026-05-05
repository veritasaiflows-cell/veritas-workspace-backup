# Workflow 22 - Canonical Freshness Patch Pilot and Surface Sync

## Objective
- Turn the approved canonical-freshness-patch contract into a bounded pilot that can find stale claims, draft narrow patch proposals, and surface downstream sync needs without pretending to own judgment.
- Keep freshness help narrow, reversible, and fully human-gated.
- Prove that freshness patching can support the daily and weekly operating chain without becoming an autonomous rewrite lane.

## Current State
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
- queued

### Phase 2 - Patch-candidate dry run
Purpose:
- generate narrow patch candidates and verify whether they stay mechanical/alignment-only

Required outputs:
- sample patch candidates
- verifier notes on source quality and conflicts
- affected-surface list and downstream sync notes
- rejection examples for anything that behaves like thesis rewrite

Status:
- queued

### Phase 3 - Manual apply proof
Purpose:
- prove that approved candidates can be applied reversibly without widening authority

Required outputs:
- exact old/new text capture
- rollback note
- direct inspection or validation proof
- downstream surface-sync record

Status:
- queued

### Phase 4 - Keep / widen / stop decision
Purpose:
- decide whether a later gated helper is useful enough to justify further automation

Required outputs:
- pilot verdict
- reopen triggers
- explicit no-auto-apply posture or approved narrow next step

Status:
- queued

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

## Next Action
- Select the pilot stale-claim set from the already named high-signal surfaces: NVDA timing path, JPM, ETN, GOOG / MSFT post-earnings freshness, and the oil / Hormuz sleeve.

## Key Files
- `06. Playbooks/Research Automation Canonical Freshness Patch Contract.md`
- `06. Playbooks/Research Automation Freshness Candidate Input Contract.md`
- `06. Playbooks/Research Automation Intake Packet Contract.md`
- `06. Playbooks/Research Automation Routing and Promotion Contract.md`
- `06. Playbooks/Cron Job Protocol.md`
- `scripts/canonical_freshness_patch.py`
- `06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md`
