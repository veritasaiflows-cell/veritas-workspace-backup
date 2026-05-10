# Workflow Carryover Audit - 2026-05-05

## Scope
- Audit the live workflow control surfaces for workflows that are closed, closed with follow-up, deferred, active, or queued.
- Identify which carry-over items already have an owner workflow, which are intentional holds, and which still lack a dedicated owner.
- Recommend and open only the additional workflows needed to cover ownerless residue.

## Live status snapshot
- **Current active workflow:** `Workflow 21 - Recurring Source Bundle and Review Window Pilot`
- **Current queue truth source:** `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- **Current registry truth source:** `06. Playbooks/IC Project Registry.md`

## Audit findings

### 1) Control-surface truth drift is real
- The queue's top `Current chain state` block is stale: it still says **WF28 active / WF29 next** even though the same queue's detailed order and the registry both show **WF21 active**.
- The queue also mixes two different order models without making the rule explicit:
  - workflow-level compact order: `WF21 -> WF26 -> WF27 -> WF22 -> WF23`
  - immediate phase-level order: `WF21 Phase 1 -> WF26 -> WF27 -> WF21 Phase 2 -> WF22 -> WF23 gated`
- This is not catastrophic, but it is exactly the kind of orchestration drift that will rot future sequencing if left alone.

### 2) Most carry-over items are already honestly owned
These do **not** need duplicate workflows:
- **WF16 family carry-over** -> owned downstream by **WF21 / WF22 / WF26 / WF23**
- **WF25 desk handoff residue** -> owned downstream by **WF21 / WF26**
- **WF29 proof-surface downstream use** -> owned immediately by **WF21** as the next consumer lane
- **WF27 predictive layer hold** -> intentionally blocked until upstream evidence/provenance lanes are real
- **manual-only canonical mutation / presentation** -> intentional fail-closed boundary, not a missing owner
- **no admitted/promotion proofs beyond WF25's first two cases** -> intentional narrow proof set, not a closure failure

### 3) Some carry-over items are intentional holds, not defects
These should stay visible but should **not** be reopened as emergency debt:
- no dedicated WF20 review cron yet
- canonical finance-note mutation remains manual-only in v1
- presentation / packaging autonomy remains fail-closed
- broader predictive work remains blocked behind upstream evidence discipline
- sector expansion beyond the bounded healthcare pilot remains human-gated

### 4) The ownerless residue is narrower than it looked
The real missing-owner set is:
1. **workflow queue / index truth reconciliation**
   - stale active/next header in the queue
   - ambiguous next-three ordering between workflow-level and phase-level views
   - parallel / IC redundancy cleanup still named as a later bounded candidate, but not actually given a live owner
2. **runtime continuity + memory reliability residue**
   - memory indexing / embedding credential health still broken
   - upstream daily-note writer runtime debt still unpatched
   - async auth / delayed exec-event reconciliation still depends on operator vigilance
   - root worktree cleanup trust rules are better, but still not boring runtime infrastructure
3. **scheduled-proof symmetry / stronger automation proof residue**
   - WF24 left morning / Sunday sibling symmetry as named reopen-trigger material
   - 2026-05-05 fixed the morning approval prompt and added a 15:30 catch-up cron, but the wider proof-promotion question is still not owned as a discrete workflow
   - WF29 proof utilities are landed, but still bounded/manual rather than startup-enforced or elevated to a broader workflow-proof tier

## Workflow status rollup

### Completed / stable baseline
- WF1, WF2, WF3, WF3B, WF3C
- WF4, WF4B, WF4C
- WF9A, WF9B
- WF11, WF12, WF13, WF14
- WF16A, WF16B
- WF17, WF18

### Closed with follow-up or intentional residue
- trust-grade reassessment / warning-residue gate
- WF5, WF6, WF7, WF8, WF9, WF10
- WF15 (deferred backlog, not active)
- WF16, WF19, WF20, WF24, WF25, WF28, WF29
- Capital Deployment Readiness
- E17 Universe Synchronization

### Active / queued / gated
- **WF21 active**
- WF22 queued / gated behind WF21
- WF23 queued / gated behind WF22
- WF26 queued / gated behind WF21
- WF27 queued / gated behind WF26

## Carry-over owner map

| Carry-over item | Current owner | Status |
|---|---|---|
| recurring source-bundle / review-window implementation | WF21 | owned, active |
| fresh external intelligence / geopolitical verification | WF26 | owned, queued |
| predictive methodology-first layer | WF27 | owned, queued / blocked |
| canonical freshness patch pilot | WF22 | owned, queued |
| command-center tightening | WF23 | owned, queued |
| queue/index truth drift | **WF30** | newly opened |
| parallel / IC redundancy cleanup decision path | **WF30** | newly opened |
| memory indexing / embedding credential health | **WF31** | newly opened |
| upstream daily-note writer runtime debt | **WF31** | newly opened |
| async auth / delayed exec-event reconciliation hardening | **WF31** | newly opened |
| scheduled sibling proof symmetry / stronger proof-promotion decision | **WF31** | newly opened |

## New workflows opened from this audit
1. `06. Playbooks/Project Continuity/Workflow 30 - Workflow Queue Truth and Carryover Governance Reconciliation.md`
2. `06. Playbooks/Project Continuity/Workflow 31 - Runtime Continuity, Memory Indexing, and Scheduled-Proof Hardening.md`

## Recommended sequencing after this audit
1. finish **WF21** cleanly
2. open **WF30** next to reconcile the workflow control surfaces before more queue widening
3. open **WF31** after WF30 so runtime/memory/proof residue has a dedicated owner before further automation claims widen
4. continue into **WF26** only after the control-plane truth layer is honest again

## Bottom line
- The workflow system is **not broken**, but it was carrying real control-surface drift.
- Most residue already had honest downstream owners.
- The missing-owner set is now explicitly narrowed to **two** new workflows instead of a vague pile.
