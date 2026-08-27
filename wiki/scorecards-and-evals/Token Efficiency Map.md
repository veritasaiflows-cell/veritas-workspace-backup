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
- Token events observed: `907`.
- Total observed tokens: `48819242`.
- API-equivalent token benchmark (not an invoice): `13.233436` (`partial_unknown_input_semantics_or_missing_rate`; `186/907` events priced).
- Estimated ChatGPT credits (not an observed debit): `302.49816` (`partial_separate_no_public_rate_or_missing_rate`; `186/907` events priced).
- Rolling 5h / observed 7d tokens: `137375` / `1193338`; usage timestamp coverage `18.9636`%.
- Actual billed cost (owner-entered only): `None`.
- OAuth quota state / remaining / days to reset: `stale` / `58.0` / `0.0`.
- Cron token events: `721`.
- Implementation token events: `1`.
- Implementation token gaps: `597`.
- API-call reduction candidates: `6`.
- Prompt-compression candidates: `6`.
- Failure-cost candidates: `0`.
- Top token candidate: `Runtime - OS Audit Companion Packets Refresh`.

## What this proves

WF88 can now see which cron/API model calls are token-heavy, which ones are candidates for changed-only prefilters or prompt compression, where implementation lanes are missing usage attribution, and whether accepted jobs conformed to their expected route.

## Quality-weighted implementation efficiency

- Optimize uncached input tokens per Main-accepted job and gross tokens per Main-accepted job, not raw token minima.
- Track first-pass acceptance, elapsed time to accepted proof, retry tax, and escaped defects for each parent/phase/attempt route.
- Current route-conformant / mismatch rows: `16` / `1`.
- Current incidents / invalid-token-integrity rows / retry tax: `0` / `1` / `33`.
- Comparable cohorts / eligible cohorts: `6` / `0`.
- A route needs ten comparable Main-accepted jobs before it can clear the sample gate; automatic route ranking and promotion remain disabled.
- Incidents, invalid telemetry, unavailable actual-route data, and mismatches are cost or trust signals; they receive no efficiency success credit.

## Natural-language retrieval anchors

- How should a new session measure token efficiency? Use accepted-outcome metrics: uncached and gross tokens per Main-accepted job, first-pass acceptance, time to accepted proof, retry tax, and escaped defects.
- When can an implementation route be promoted? Never automatically; first collect at least ten comparable Main-accepted jobs, then require explicit Main policy review.

## What it does not prove

Token efficiency does not prove answer quality, model skill, investment performance, or execution readiness. Any API-call reduction must pass a separate regression harness before changing cron commands or model routing.

## Next safe actions

- Refresh `tmp/token-efficiency-scorecard.json` after token ledger refreshes.
- Refresh `tmp/implementation-token-attribution-bridge.json` after implementation lane closeouts.
- Use changed-input/source-hash prefilters before model calls where the scorecard identifies safe candidates.
- Use fixture-based prompt-compression checks before accepting shorter prompts.
- Run deterministic path/hash/budget preflight before independent QA, reuse the same frozen snapshot, and send only changed-file deltas on repair.
