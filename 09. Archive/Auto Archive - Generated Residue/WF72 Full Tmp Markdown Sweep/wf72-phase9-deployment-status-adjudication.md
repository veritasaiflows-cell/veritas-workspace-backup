# WF72 Phase 9 - Deployment/status adjudication

Generated: `2026-05-24T18:36:09Z`

## Decision

Permanent hold is best for `deployment_proof_status` under SQL-canon. No neutral non-action SQL-canon metadata contract is feasible for the current field name and values without changing deployment/action-state semantics.

No SQL activation, cache write, Markdown/canon/portfolio mutation, owner-approval inference, or dashboard recommendation/deployment/action-state behavior change was performed.

## Inventory - 10 held rows

| Key | Exact value | Workflow | Machine state | Band position | Source |
|---|---:|---|---|---|---|
| `BRK.B:deployment_proof_status` | `DO NOT TOUCH` | `REPAIR` | `BENCH` | 0.7% below band low | `tmp/deployment-readiness-surface.json` |
| `ETN:deployment_proof_status` | `DEPLOYABLE NOW` | `DEPLOYED` | `DEPLOYABLE NOW` | IN BAND | `tmp/deployment-readiness-surface.json` |
| `GOOG:deployment_proof_status` | `ALMOST DEPLOYABLE` | `ALMOST` | `ALMOST DEPLOYABLE` | 0.1% above band top | `tmp/deployment-readiness-surface.json` |
| `GS:deployment_proof_status` | `ALMOST DEPLOYABLE` | `ALMOST` | `ALMOST DEPLOYABLE` | 6.5% above band top | `tmp/deployment-readiness-surface.json` |
| `JPM:deployment_proof_status` | `ALMOST DEPLOYABLE` | `ALMOST` | `ALMOST DEPLOYABLE` | 0.4% above band top | `tmp/deployment-readiness-surface.json` |
| `LMT:deployment_proof_status` | `DO NOT TOUCH` | `REPAIR` | `BENCH` | 2.8% below band low | `tmp/deployment-readiness-surface.json` |
| `MSFT:deployment_proof_status` | `ALMOST DEPLOYABLE` | `ALMOST` | `ALMOST DEPLOYABLE` | 1.5% above band top | `tmp/deployment-readiness-surface.json` |
| `NVDA:deployment_proof_status` | `PROMOTION REVIEW` | `ALMOST` | `PROMOTION REVIEW` | IN BAND | `tmp/deployment-readiness-surface.json` |
| `VRT:deployment_proof_status` | `PROMOTION REVIEW` | `PROMOTION REVIEW` | `PROMOTION REVIEW` | IN BAND | `tmp/deployment-readiness-surface.json` |
| `XOM:deployment_proof_status` | `DO NOT TOUCH` | `REPAIR` | `BENCH` | IN BAND | `tmp/deployment-readiness-surface.json` |

Value counts: `ALMOST DEPLOYABLE`=4, `DEPLOYABLE NOW`=1, `DO NOT TOUCH`=3, `PROMOTION REVIEW`=2

## Rationale

- The field name deployment_proof_status itself carries deployment/action semantics; moving it into SQL-canon would make SQL look like a durable deployment-status owner.
- The exact values are action/readiness words: DEPLOYABLE NOW, ALMOST DEPLOYABLE, PROMOTION REVIEW, and DO NOT TOUCH.
- dashboard_payload.py maps the same vocabulary into deployable/promotion_review/almost/bench buckets and Today action-card states; SQL-canon migration would be difficult to prove metadata-only without changing or duplicating action-state behavior.
- deployment_readiness_surface.py intentionally owns these states as a bounded review surface generated from trigger/technical/earnings/risk logic, not as canon/cache metadata.
- A neutral contract would need a renamed field and disconnected vocabulary; that is a producer/consumer wording redesign, not a safe activation of deployment_proof_status.
- BRK.B and LMT retain extra review_needed_or_sql_newer/prework blockers from Phase 6 history.

## Cache/read proof

- Active cache key count: `13`
- `deployment_proof_status` keys in cache: `[]`
- Source hash: `c7b1f3e29208bdf94afe46af237afeb8a8da21057d79f8c35b776e01cfa9548d`

## Future route

If reconsidered, redesign as a separately named non-action display label and prove no dashboard/Today/run-summary behavior drift. Do not activate `deployment_proof_status` itself.
