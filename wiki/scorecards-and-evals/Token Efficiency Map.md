# Token Efficiency Map

Status: synthesis only
Owner workflow: WF88
Generated page type: scorecard_map
Authority boundary: review-only map; no canon, approval, execution, cron mutation, portfolio mutation, model training, or owner approval inference.
Promotion path: wiki insight -> WF88 recommendation -> WF74/PM/Skill Workshop/validator route -> proof -> explicit approval or validated implementation where allowed.

## Source artifacts

- `tmp/token-usage-ledger-current.json`
- `tmp/token-budget-status.json`
- `tmp/token-efficiency-scorecard.json`
- `tmp/implementation-token-attribution-bridge.json`
- `tmp/model-run-ledger-current.json`
- `tmp/concurrent-lane-register.json`
- `tmp/coding-outcome-ledger-current.json`
## Current token posture

- Token usage ledger status: `warning`.
- Token efficiency scorecard status: `warning`.
- Token events observed: `1166`.
- Total observed tokens: `68413287`.
- API-equivalent token benchmark (not an invoice): `14.925727` (`partial_unknown_input_semantics_or_missing_rate`; `200/1166` events priced).
- Estimated ChatGPT credits (not an observed debit): `338.593006` (`partial_separate_no_public_rate_or_missing_rate`; `200/1166` events priced).
- Rolling 5h / observed 7d tokens: `0` / `46176`; usage timestamp coverage `16.0377`%.
- Actual billed cost (owner-entered only): `None`.
- OAuth quota state / remaining / days to reset: `stale` / `58.0` / `0.0`.
- Cron token events: `736`.
- Implementation token events: `4`.
- Implementation token gaps: `597`.
- API-call reduction candidates: `0`.
- Prompt-compression candidates: `0`.
- Failure-cost candidates: `0`.
- Top token candidate: `None`.

## What this proves

WF88 can now see which cron/API model calls are token-heavy, which ones are candidates for changed-only prefilters or prompt compression, where implementation lanes are missing usage attribution, and whether accepted jobs conformed to their expected route.

## Quality-weighted implementation efficiency

- Optimize uncached input tokens per Main-accepted job and gross tokens per Main-accepted job, not raw token minima.
- Track first-pass acceptance, elapsed time to accepted proof, retry tax, and escaped defects for each parent/phase/attempt route.
- Current route-conformant / mismatch rows: `16` / `1`.
- Current incidents / invalid-token-integrity rows / retry tax: `0` / `1` / `37`.
- Comparable cohorts / eligible cohorts: `6` / `0`.
- Evaluation mode: owner-directed on-demand evidence review.
- Use available token attribution, elapsed-time, retry, first-pass/Main-acceptance, and escaped-defect evidence; prefer like-for-like comparisons when available; no fixed cohort pilot is required.
- Keep normal routing light. Load these ledgers only for an explicit review with `python scripts\project_implementation_router.py --example --include-efficiency-observation --validate`.
- automatic route ranking and promotion remain disabled; a route-policy change requires explicit Main/owner review.
- Incidents, invalid telemetry, unavailable actual-route data, and mismatches are cost or trust signals; they receive no efficiency success credit.

## Natural-language retrieval anchors

- How should a new session measure token efficiency? Use accepted-outcome metrics: uncached and gross tokens per Main-accepted job, first-pass acceptance, time to accepted proof, retry tax, and escaped defects.
- When can an implementation route be promoted? Never automatically; review available evidence on demand, then require an explicit Main/owner policy change.

## What it does not prove

Token efficiency does not prove answer quality, model skill, investment performance, or execution readiness. Any API-call reduction must pass a separate regression harness before changing cron commands or model routing.

## Next safe actions

- Refresh `tmp/token-efficiency-scorecard.json` after token ledger refreshes.
- Refresh `tmp/implementation-token-attribution-bridge.json` after implementation lane closeouts.
- Use changed-input/source-hash prefilters before model calls where the scorecard identifies safe candidates.
- Use fixture-based prompt-compression checks before accepting shorter prompts.
- Run deterministic path/hash/budget preflight before independent QA, reuse the same frozen snapshot, and send only changed-file deltas on repair.
