# Research Automation Canonical Freshness Patch Contract

## Purpose
Define the only kind of canonical-note help allowed in v1: narrow freshness patch proposals that keep notes aligned without pretending to own judgment.

## Core rule
Freshness patch != thesis rewrite.

## Freshness classes
1. **Mechanical date / elapsed-event wording**
2. **Post-catalyst or post-earnings status wording**
3. **Cross-surface contradiction against an already-approved owner surface**
4. **Real thesis / posture change**

Only classes 1 and 2 are normal v1 patch candidates.
Class 3 requires extra review.
Class 4 is fully human-gated.

## Required patch packet fields
Every patch candidate must include:
- `candidate_id`
- `target_note`
- `stale_claim`
- `why_stale`
- `new_evidence`
- `source_quality`
- `freshness_class`
- `patch_scope`
- `proposed_replacement`
- `judgment_impact` (`none`, `possible`, `material`)
- `affected_surfaces`
- `required_downstream_sync`
- `rollback_note`
- `verifier_signoff`
- `main_approval_required` (`true`)

## Owner-surface map
### Candidate owner surfaces for v1 patch proposals
- `01. Dashboards/Executive Brief.md`
- `01. Dashboards/Next Actions.md`
- `01. Dashboards/This Week.md`
- `05. Intelligence/Event Calendar.md`
- `05. Intelligence/Weekly Intelligence Brief.md`

### Manual-only / caution surfaces in v1
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- `02. Markets/Macro Regime Dashboard.md`

A candidate patch may reference manual-only surfaces as evidence.
It may not auto-mutate them.

## Safe automation boundary
Allowed in v1:
- stale-claim detection
- exact patch proposal drafting
- owner-surface classification
- surface-impact audit
- patch packet generation

Not allowed in v1:
- auto-apply
- silent note mutation
- thesis rewrite
- deployment-state change
- target-weight or posture change
- cross-surface truth arbitration by helpers

## Approval and rollback rule
- all patch packets require Veritas/main approval before apply
- applied patches must be reversible via exact old/new text capture
- validation or direct inspection must run after any approved apply

## Pilot rule
The bounded pilot may use the named high-signal set only:
- NVDA timing path
- JPM
- ETN
- GOOG / MSFT post-earnings freshness
- oil / Hormuz sleeve

The pilot must stop immediately if:
- a candidate behaves like a new thesis decision
- helper output starts acting like a second truth layer
- the owner boundary is ambiguous
- source quality is too weak for the proposed patch

## Acceptance use
This contract is approved for Workflow 16B when:
- freshness classes are explicit
- owner surfaces are explicit
- exact patch fields exist
- approval and rollback rules are explicit
- no-auto-apply remains explicit
- bounded pilot evidence exists
