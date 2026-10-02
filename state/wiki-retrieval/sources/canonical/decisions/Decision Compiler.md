<!-- openclaw:wiki:raw-source -->
# Decision Compiler

Canonical page: `wiki/decisions/Decision Compiler.md`
Canonical rendered SHA-256: `53a719f8ec91a7330233b25660f4c2cf1498f978098e816529166d7f0382a099`.
Source snapshot SHA-256: `c2f5083a99c97499f05ef2f7632fd70bbbf0cff8eb6b53a2b2392add476f2a38`.
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
- Decision objects: `5`; states: `{'monitor_only': 2, 'repair_ready_review_only': 2, 'review_ready': 1}`.
- Conflicts / uncertainties: `1` / `5`.
- Owner review required / blocked: `0` / `0`.
- Leak guard: `True`; wiki/OS2 runtime inputs forbidden: `['tmp/wf88-os2-control-packet.json', 'tmp/wf88-wiki-synthesis-packet.json']`.

## Retrieval contract

- Retrieval fixtures: `42/42` passed across `10` classes.
- Conflict fixtures: `13`; average score: `1.0`.
- Freshness modes: `{'fixture_timestamp_age': 9, 'source_timestamp_age': 1, 'synthetic_ordering_semantics': 24}`; live source timestamp-age assessments: `1`; live states: `{'fresh': 1}`.
- Declared labels authoritative: `False`; label-only cases count as live-source proof: `False`.

The compiler selects deterministic upstream evidence first, records source precedence/freshness/conflict/authority/expiry/later-outcome fields, and emits review-only decision objects. Runtime direction is upstream artifacts -> compiler -> wiki. The compiler must never read wiki or OS2 as decision inputs.
