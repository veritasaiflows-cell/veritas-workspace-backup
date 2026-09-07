<!-- openclaw:wiki:raw-source -->
# Frontier Capability Eval

Canonical page: `wiki/scorecards-and-evals/Frontier Capability Eval.md`
Canonical rendered SHA-256: `a698fed4f9476d44807e9db22f58f138074da7f7dc92847c3e9da9a9ba1458df`.
Source snapshot SHA-256: `f6ee80a8d183635520f429f34c7ca23360ebdb6d238c1622f6dffae691bee7f1`.
Authority: review-only retrieval mirror; canonical wiki and named owner artifacts remain authoritative.

## Query aliases

- frontier capability evaluation
- matched model eval
- blind scorer contract

## Canonical content

# Frontier Capability Eval

Status: synthesis only
Owner workflow: WF88
Generated page type: evaluation_contract
Authority boundary: review-only map; no canon, approval, execution, cron mutation, portfolio mutation, model training, or owner approval inference.
Promotion path: wiki insight -> WF88 recommendation -> WF74/PM/Skill Workshop/validator route -> proof -> explicit approval or validated implementation where allowed.

## Source artifacts

- `tmp/frontier-capability-eval-spine.json`
- `data/evals/frontier-capability-eval-fixtures.json`
- `tmp/model-quality-scorecard.json`
- `tmp/implementation-token-attribution-bridge.json`
## Current contract

- Status: `ready_to_collect`; validation: `ok`.
- Frozen cases / assignments: `100` / `300`.
- Collected result rows: `0`.
- Fully trusted result rows: `0`; execution state: `verifier_ready_no_result_claims`.
- Trusted execution/output/grader attestations: `False` / `False` / `False`.
- Cross-model ranking allowed: `False`.
- Promotion action allowed: `False`.
- Recent attribution coverage: `0.8557`; provider-run join ready: `False`.

## Interpretation

The frozen 100-case design is ready to collect blinded, source-identical metadata results. Zero collected rows means there is no frontier ranking or promotion evidence yet. Local producer labels and unkeyed hashes establish consistency only; they cannot prove execution, output existence, or independent grading. The grader must receive only the scorer surface, never the coordinator route-to-alias map.
