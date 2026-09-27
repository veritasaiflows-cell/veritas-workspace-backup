# Current Scorecards And Evals

Status: synthesis only
Owner workflow: WF88
Generated page type: scorecard_map
Authority boundary: review-only map; no canon, approval, execution, cron mutation, portfolio mutation, model training, or owner approval inference.
Promotion path: wiki insight -> WF88 recommendation -> WF74/PM/Skill Workshop/validator route -> proof -> explicit approval or validated implementation where allowed.

## Source artifacts

- `tmp/wf74-learning-loop-eval-harness.json`
- `tmp/wf74-outcome-eval-suite-v2.json`
- `tmp/model-quality-scorecard.json`
- `tmp/wf87-shadow-outcome-scorecard.json`
- `tmp/retrieval-quality-scorecard.json`
- `tmp/frontier-capability-eval-spine.json`
- `tmp/wf88-decision-compiler.json`
- `tmp/rsi-outcome-scorecard.json`
- `tmp/advanced-capability-pilot-packet.json`
- `tmp/route-efficiency-scorecard.json`
- `tmp/token-efficiency-scorecard.json`
## Current eval state

- WF74 learning eval: `18/18` passed; failed `0`.
- WF74 outcome eval suite: categories `17`, fixtures `34`, failed classifications `0`.
- Model quality scorecard status: `scaffold_active`.
- Retrieval regression corpus: `42/42` passed across `10` classes; average `1.0`; live timestamp-age proofs `1`.
- Frontier eval: `ready_to_collect` with `100` frozen cases, `0` results, `0` fully proof-verified, execution `verifier_ready_no_result_claims`, ranking `False`.
- Decision compiler: `5` objects; conflicts `1`; leak guard `True`.
- RSI later-outcome maturity: `warning_insufficient_real_outcome_evidence`; stable closures `0`; linkage debt `22`.
- Advanced capability pilots: `6` fixture-ready, `0` executed, `0` promotion-ready.
- Recommendation later-outcome rows (current preview / durable / grade history): `0` / `316` / `316`. The aggregate `316` uses scope `durable_recommendation_outcome_ledger_max_of_preview_durable_and_grade_history`; model-performance claim allowed now: `False`.
- RSI maturity status from primary WF74 eval: `proof_worker_ready`.
- WF74 eval primary first-hop surface: `tmp/wf74-learning-loop-eval-harness.json`.

## Token efficiency state

- Token usage ledger status: `warning`.
- Token efficiency scorecard status: `warning`.
- Token events observed: `1255`.
- Total observed tokens: `87458558`.
- API-equivalent token benchmark (not an invoice): `14.925727` (`partial_unknown_input_semantics_or_missing_rate`; `200/1255` events priced).
- Estimated ChatGPT credits (not an observed debit): `338.593006` (`partial_separate_no_public_rate_or_missing_rate`; `200/1255` events priced).
- Rolling 5h / observed 7d tokens: `0` / `46176`; usage timestamp coverage `14.9004`%.
- Actual billed cost (owner-entered only): `None`.
- OAuth quota state / remaining / days to reset: `stale` / `58.0` / `0.0`.
- Cron token events: `736`.
- Implementation token events: `5`.
- Implementation token gaps: `597`.
- API-call reduction candidates: `0`.
- Prompt-compression candidates: `0`.
- Failure-cost candidates: `0`.
- Top token candidate: `None`.

## Interpretation

These scorecards prove routing, regression behavior, and cost-attribution targets, not investment skill, model performance, or execution readiness.

## Claim evidence

- `recommendation-outcome-closure`: `{"current_preview_later_outcome_graded_rows":0,"durable_later_outcome_graded_rows":316,"grade_history_graded_ledger_event_count":316,"later_outcome_graded_rows":316}`; authority `review_only`; source refs `wf88_os2_control#/summary/recommendation_later_outcome_graded_rows`, `wf88_os2_control#/summary/recommendation_current_preview_later_outcome_graded_rows`, `wf88_os2_control#/summary/recommendation_durable_later_outcome_graded_rows`, `wf88_os2_control#/summary/recommendation_grade_history_graded_ledger_event_count`.
