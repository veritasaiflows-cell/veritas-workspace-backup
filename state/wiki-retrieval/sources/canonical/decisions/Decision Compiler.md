<!-- openclaw:wiki:raw-source -->
# Decision Compiler

Canonical page: `wiki/decisions/Decision Compiler.md`
Canonical rendered SHA-256: `46efd6b0119535c5f1061cc3aa9ed2624fcae00918cb6ba6f1ba6b4b9413b186`.
Source snapshot SHA-256: `6d670804398925df4f3bc27dab7cc30bbe29f708f93a6ae28f56af63a0467218`.
Authority: review-only retrieval mirror; canonical wiki and named owner artifacts remain authoritative.

## Query aliases

- decision object compiler
- evidence to decision
- review only decision route

## Canonical content

# Decision Compiler

Status: synthesis only
Owner workflow: WF88
Generated page type: decision_map
Authority boundary: review-only map; no canon, approval, execution, cron mutation, portfolio mutation, model training, or owner approval inference.
Promotion path: wiki insight -> WF88 recommendation -> WF74/PM/Skill Workshop/validator route -> proof -> explicit approval or validated implementation where allowed.

## Source artifacts

- `tmp/wf88-decision-compiler.json`
- `tmp/retrieval-quality-scorecard.json`
- `tmp/actionable-improvement-queue.json`
- `tmp/wf74-decision-docket.json`
- `tmp/wf74-autonomy-work-router.json`
- `tmp/wf74-wf88-loop-trace.json`
- `tmp/improvement-ledger-current.json`
- `tmp/recommendation-outcome-ledger-current.json`
## Current compiler state

- Status / validation: `decision_objects_warning_review_only` / `warning`.
- Decision objects: `5`; states: `{'monitor_only': 3, 'repair_ready_review_only': 1, 'review_ready': 1}`.
- Conflicts / uncertainties: `1` / `5`.
- Owner review required / blocked: `0` / `0`.
- Leak guard: `True`; wiki/OS2 runtime inputs forbidden: `['tmp/wf88-os2-control-packet.json', 'tmp/wf88-wiki-synthesis-packet.json']`.

## Retrieval contract

- Retrieval fixtures: `42/42` passed across `10` classes.
- Conflict fixtures: `13`; average score: `1.0`.
- Freshness modes: `{'fixture_timestamp_age': 9, 'source_timestamp_age': 1, 'synthetic_ordering_semantics': 24}`; live source timestamp-age assessments: `1`; live states: `{'fresh': 1}`.
- Declared labels authoritative: `False`; label-only cases count as live-source proof: `False`.

The compiler selects deterministic upstream evidence first, records source precedence/freshness/conflict/authority/expiry/later-outcome fields, and emits review-only decision objects. Runtime direction is upstream artifacts -> compiler -> wiki. The compiler must never read wiki or OS2 as decision inputs.
