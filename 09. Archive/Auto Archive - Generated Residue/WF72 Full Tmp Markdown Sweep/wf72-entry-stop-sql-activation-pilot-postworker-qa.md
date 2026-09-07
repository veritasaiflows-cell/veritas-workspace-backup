# WF72 entry/stop SQL activation pilot - post-worker QA

- Generated: 2026-05-24T20:58:00Z
- Verdict: `blocked`
- Bottom line: worker output is useful shadow/preflight scaffolding, but it is **not activation-ready**.

## Findings

- Required worker artifacts exist, parse, and have real status fields.
- Entry/stop activation is still shadow/preflight only: no exact key-level approval, rollback/export, fallback equality/no-drift proof, or post-activation rollback drill exists.
- Candidate set is 42 ticker rows x 6 fields = **252 exact candidate keys**. That is too broad for first write activation; narrow to a small exact pilot slice first.
- Candidate fields are neutral enough for shadow/preflight: `reference_price_low`, `reference_price_high`, `reference_invalidation_level`, `reference_level_source_timestamp`, `reference_level_source_sha256`, `reference_level_owner_source_path`.
- `reference_invalidation_level` is acceptable as reference/display metadata if it remains gated and is not used as a stop/order/deploy/action-state field.
- Active SQL canon cache remains exactly the 13 approved metadata keys; entry/stop/reference candidate active rows = **0**.
- No SQL-canon/cache expansion beyond the 13 keys was detected.
- No portfolio Markdown/canon mutation, owner approval inference, proposal-apply readiness, dashboard action-state behavior change, trade/account/paper/live authority, money movement, credential/config mutation, or destructive action was authorized by the inspected artifacts.

## Proof commands

| Command | Result | Evidence |
|---|---:|---|
| `python scripts\\artifact_index.py validate` | FAIL | `status=blocked checks=28 failed=1`; stale `tmp/deployment-readiness-surface.json` |
| `python scripts\\sql_canon_field_family_preflight.py --write` | PASS | `status=ok`; `already_phase4a_active=13`; `entry_stop_candidate_key_count=252`; activation false |
| `python scripts\\test_artifact_index.py` | PASS | `artifact_index_tests_passed` |
| `python scripts\\test_dashboard_acceptance.py` | PASS | `29/29 passed` |

## Blocking findings

1. `artifact_index.py validate` currently fails `freshness_no_stale_content` for `tmp/deployment-readiness-surface.json`.
2. 252 exact keys is too broad for first write activation without narrowed pilot scope and exact key approval.
3. Activation-specific rollback/export, fallback equality, no-drift, consumer guard, post-activation validation, and rollback drill are not proven.

## Recommended next repair

1. Refresh/re-index `tmp/deployment-readiness-surface.json` until `artifact_index.py validate` passes with `stale_content=0`.
2. Narrow the candidate set to a small exact pilot slice and create an approval artifact naming those keys.
3. Generate activation-specific rollback/export, fallback equality/no-drift, consumer guard, post-activation validation, and rollback-drill proof before any write activation.
