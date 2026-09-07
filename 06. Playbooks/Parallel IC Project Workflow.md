# Parallel IC Project Workflow

## Purpose

Coordinate independent implementation and audit lanes without creating conflicting writers or duplicate control planes.

## Recommended lane split

- **Implementation lane:** one bounded code, canon, or artifact change set.
- **Evidence/QA lane:** independent inspection, adversarial tests, or source/provenance review.
- **Main:** routing, lease control, integration, acceptance, and final judgment.

Open only the lanes that are genuinely independent. Parallelism is not useful when both lanes must repeatedly touch the same files or depend on the same unresolved decision.

## Finance priorities

For finance alerts and recommendations, prioritize:

1. source truth and lineage
2. freshness and market-window context
3. thesis, catalyst, risk, band, and invalidation consistency
4. alert-state accuracy and deduplication
5. clear non-executing recommendation output
6. scheduler and end-to-end proof

Use market themes rather than system-owned finance action-state categories. No lane may maintain portfolio or simulated-account state, prepare orders, access brokerage/account routes, infer approval, or perform paper/live execution.

## Acceptance

Each lane must produce deterministic proof, state uncertainty, preserve rollback, and stop when its authority boundary is reached. Main accepts only after checking the actual diff and relevant validators.
