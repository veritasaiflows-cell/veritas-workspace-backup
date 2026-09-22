# PM Main Wake Deterministic Migration

## Decision

- The twice-daily continuation dispatcher is deterministic PM intake only. It must not dispatch a Main model session.
- The 30-minute priority pickup stays model-free except for one explicit Main notification when a stable signal is genuinely new or changed.
- `NEW_PRIORITY` changing to `NO_DELTA`, an unresolved accepted item, and elapsed time are not changes and must not cause another wake.
- Broken or unreadable deterministic proof remains fail-open. A failed Main dispatch remains retryable.

## PM funnel

1. Both jobs refresh `tmp/main-session-priority-handoff.json` and `tmp/main-session-action-executor.json` deterministically.
2. The continuation job writes `tmp/pm-continuation-dispatcher-predispatch.json` and its history as PM intake evidence; it has no `--dispatch-main` authority.
3. The priority pickup writes `tmp/pm-priority-pickup-predispatch-prefilter.json`; only its live contract includes `--dispatch-main`.
4. PM reads the validated handoff and predispatch history during normal control review. Main is an exception destination, not the polling engine.

## Acceptance proof

- Unit regression proves one-shot notification, receipt-transition quieting, indefinite unchanged suppression, changed-input wake, retry after failed dispatch, and fail-open invalid-proof behavior.
- Live cron contracts preserve schedules, isolated command targets, delivery `none`, timeouts, and exact output/history paths.
- A deterministic continuation canary shows `wake.dispatched=false` and `wake.routed_to_pm=true` when attention remains.

## Rollback

- Restore the two scheduler definitions from their named files under `state/cron-rollback/`.
- Revert `scripts/pm_priority_pickup_predispatch_prefilter.py` and its test together.
- Model routing rollback uses the timestamped `~/.openclaw/openclaw.json.pre-terra-default-*` copy created before the approved config change.
