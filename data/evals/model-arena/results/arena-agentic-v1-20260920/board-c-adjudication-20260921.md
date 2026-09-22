# Board C - adjudication canon (2026-09-21)

- Envelope: `arena-agentic-v1-20260920` (+ `arena-six-20260919` token-budget-r1 where noted)
- **Supersedes the eligibility canon** in `arena-agentic-v1-20260920/board.md`
  ("a trajectory is eligible iff its response is non-empty"), which is sealed and
  hash-pinned in `evidence-manifest.json` and was therefore left byte-identical
  rather than edited. Follows the precedent at `board-b-superseding-20260921.md`.
- Code of record: `scripts/arena_unified_intake.py`
  (precedence `TRANSPORT_TAINT > CONTAMINATED > TIMEOUT_EMPTY > INVENTED > ANSWERED_FAIL`;
  `summarize_surface` emits `eligible_rule: "operational_excluded"`).
- No budget numbers change: 64,000 output-token cap, 600s backstop, 0 retries,
  T4 6-read fixture budget all unchanged. No contract budget site touched.

## 1. Denominator rule (Gap 3)

**Operational outcomes are EXCLUDED from `eligible`.**
`eligible = total - operational_count`, where operational means
`adjudicate() == TIMEOUT_EMPTY` (explicit operational `stop_reason`,
`truncated` flag, or empty response text). `strict / eligible` therefore measures
capability conditional on answered turns.

Why: preserving partial response text made truncated turns satisfy both halves of
the old canon at once (non-empty text AND operational outcome), while
`summarize_surface` counted them in the denominator even though they can never be
strict. The token cap then systematically depressed scores as truncation grew more
reachable. The canon's second clause ("parse_error json_empty denotes the
operational timeout and is excluded from factual denominators") already required
exclusion; this artifact resolves the contradiction in favour of that clause and
extends it to all operational outcomes, truncated or empty.

Agreement: `arena-six-20260919/overlay/token-budget-r1.json` already says
`timeout_classification: "operational_not_capability"` ("never scored as a factual
failure") and `stop_reasons.rule: "Any stop_reason but complete is an operational
outcome, reported separately, never scored as a factual failure."` Exclusion from
the factual denominator is exactly that rule implemented. The overlay was left
untouched (no number or wording change); this board and the code agree with it as
written.

## 2. Integrity precedence (Gap 1)

Precedence settled: **TRANSPORT_TAINT > CONTAMINATED > TIMEOUT_EMPTY > INVENTED >
ANSWERED_FAIL**. Contamination is an integrity signal and must not be maskable by
an operational one: a response that leaks hidden-bank content and then hits the
token cap adjudicates CONTAMINATED and quarantines the take
(`take_voided: True`), never TIMEOUT_EMPTY. TRANSPORT_TAINT remains highest (it
invalidates everything downstream).

Wiring (verified, not assumed): `arena_hidden_bank_runner.grade_text` /
`detect_contamination` already runs on any non-empty response text at grading time,
so the detection exists. The defect was that the adjudication/quarantine layer never
saw the flag for truncated records: `make_truncated_turn_evidence` built the flag
as absent/False and `adjudicate()` returned before reading it. Fixed by (a) moving
the contamination check above the operational check and (b) requiring the truncated
path to carry the grading-layer verdict on the preserved `partial_response_text`
(`make_truncated_turn_evidence(..., contaminated, strict_pass, invented)` and
`attach_truncation_grading(record, grade_text(partial_text))`). Precedence alone
without the flag would be useless; both halves are now in place.

## 3. Truncated correct answer (Gap 2) - decision (b)

**Chosen: (b) keep it operational, count it separately.** A truncated turn whose
preserved partial text strictly passes still adjudicates TIMEOUT_EMPTY, stays
excluded from `eligible`, and is additionally counted in
`summarize_surface.truncated_with_pass` (with `truncated_count` and
`operational_count` alongside). A correct-but-non-terminating run is therefore
visibly distinct from an empty response and can never be silently absorbed into
the timeout bucket.

Rationale: (a) would convert an operational outcome into a capability pass,
violating the overlay's `operational_not_capability` classification and the frozen
grader's strict semantics (complete response + `strict_equal`), and would erase the
termination failure that `build_contract()` scores as the `verification_termination`
dimension ("knows when to stop"). It would also need a new extraction rule
(first-JSON-object parsing of 64k runaway tails), i.e. a grading-primitive change
with false-pass risk. (b) preserves both signals with no grading change: capability
(answer preserved) in the counter, termination failure in the operational bucket.

## 4. What was NOT verified without dispatch

- No live runs were dispatched (gate stays `dispatch_ready: false`;
  `refuse_live_dispatch()` still raises). All truncation/contamination cases above
  are synthetic records through the adjudication layer, not model output.
- Whether any real archived run would have finished under a larger budget
  ("still generating" vs "looping") remains unproven; the token-budget overlay's
  known-open-question stands.
- No re-grading of archived `graded-results.json` / `responses.json` was performed
  or needed; they are untouched.

No routing, configuration, role, capital, or execution authority follows from this board.
