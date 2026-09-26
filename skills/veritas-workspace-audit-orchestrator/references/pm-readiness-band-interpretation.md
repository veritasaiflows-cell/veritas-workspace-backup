# PM Readiness Band Interpretation

Use when the request asks for the PM readiness score or band, or to "bring PM to green" or to a target number. This is a control-plane health review: read and interpret, then classify the short lanes. It grants no lane, registry, or scoring-contract change.

## Read the owner artifact

`tmp/pm-program-state.json` owns the lane set and score. `tmp/pm-control-packet.json` embeds the same summary at `sections.pm_program_state.readiness` (and as `pm_readiness` in the packet summary). Rebuild both with:

```powershell
python scripts\pm_program_state.py --write --write-db --validate
python scripts\pm_control_packet.py --write --write-db --validate
```

Never count lanes or infer the full lane set from `stale_lane_digest`. That digest skips every lane whose status is not `stale`, so it under-reports the set and its length is not the lane count.

## Arithmetic before recommendations

- `readiness.average_score` is the unweighted mean of each lane's `readiness_score`. The band is `green` at `>= 80`, `yellow` at `>= 55`, else `red`.
- Lane score by status: `complete_for_now` 95, `ready` 90, `watch`/`gated` 75, `needs_validation` 60, `stale` 45, `on_hold` 40, `blocked` 15.
- The highest reachable lane score is 95, so the mean can never reach 100. With n lanes the ceiling is `(95 + 90*(n-1))/n` — about 90.3 at n=18. When the ask is 100, say plainly that it is unreachable by repair and requires a scoring-contract decision; do not hunt for a repair that cannot exist.
- State the gap as arithmetic: `80*n - sum(lane scores)`.

## What drives each lane state

Status comes from `artifact_health`, not from effort spent:

- `blocked` 15 — a missing/unreadable required artifact, a problem `status`/`validation_status`, or an authority-boundary violation.
- `stale` 45 — a stale artifact classified `true_blocker` or `refresh_now`.
- `needs_validation` 60 — warning-grade statuses.
- `gated` 75 — a status matched by `EXPECTED_GATES`.
- `ready` 90, and the `authority` lane scores `complete_for_now` 95 when ready.
- `on_hold` 40 — an active lane override.

## Classify the short lanes before proposing work

A low score is not automatically repair work. Sort every short lane into exactly one class:

1. **real defect** — a producer that should be green and is not.
2. **deny-by-design gate** — fail-closed proof whose blocked state is correct, such as `fail_closed`, `blocked_for_sql_source_truth_promotion`, `phase2_parity_not_ready`, or a row already matched by `EXPECTED_GATES`. These cannot be "repaired" green; whether they belong in the readiness denominator is an owner/registry decision.
3. **retired or paused workflow still scoring as a live lane** — a lane on `on_hold` because the owner retired or paused the workflow. It drags the mean while needing no engineering work.
4. **unsatisfiable requirement** — a lane whose required artifact is itself forbidden by another canonical validator. Check every `missing_required` path against the alerts-OS pivot validator's retired-path registries — the `RETIRED_RUNTIME_PATHS` constant plus the runtime retirement archive manifest's source list (`scripts/alerts_os_pivot_validator.py`); a path can be retired through the manifest while absent from the constant — before planning work. Verified instance: `finance_os_data_model` and `trade_grade_decision_os` both require `tmp/canonical-finance-data-plane.json` and `.sqlite`, and both paths are on that retired list, so producing them is the violation the pivot validator reports as recreated retired state. The lane can never reach `ready`, and any repair attempt recreates retired state and cascades into other lanes.

Report the class of each short lane. Only class 1 yields a repair recommendation; classes 2, 3 and 4 need an owner decision, and no score may be moved by reclassifying them without it. For class 4 the decision is a lane-definition or registry reconciliation, never artifact production.

## Do not chase the number

Refreshing a genuinely stale producer can lower the score when the fresh proof exposes downstream staleness. Verified instance: refreshing the WF77 price bridge aged the Tier B packets, flipping `tier_promotion_review` from `stale` (45) to `blocked` (15). Report the truth movement and the blocker class; never suppress, reclassify, or defer a real failing proof to move a band.

The greenkeeper's allowlisted refresh (`main_session_greenkeeper_controller.py --refresh-frontdoors --execute-safe --append-ledger --write --validate`) runs a fixed allowlist — front-door proof refreshes plus allowlisted repair commands such as the alerts chain and pivot validator. It refreshes proof and may leave the band unchanged, so it is not a route to green; report what it actually ran and its return codes.

## Closeout

State the current average and band, the arithmetic gap to the target band, the per-lane class split, which short lanes are owner decisions rather than defects, and the ceiling under the current score map.
