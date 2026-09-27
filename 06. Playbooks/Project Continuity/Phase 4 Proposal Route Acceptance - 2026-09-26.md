# Phase 4 proposal-route acceptance — 2026-09-26

Owner: Main. Decision time: 22:08 America/Phoenix.

## Decision

**Accept the implemented foundation for its bounded inert scope.** The same-version lineage guard, append-only recommendation decision ledger, per-name readiness gate, and in-memory tier transaction simulator are now accepted code foundations. This is not Phase 4 activation and grants no guarded-SQL, canon, tier, scheduler, delivery, account, capital, order, brokerage, paper, live-execution, or external-product authority.

Main acceptance receipt: `tmp/phase4-proposal-route-20260926/phase4-final-acceptance-20260926.json`.

## What is accepted now

1. `scripts/recommendation_funnel.py` and its tests fail closed when SQL, reference-pin lineage, controller scope, universe/snapshot identity, or funnel inputs are not from one coherent version. The SQLite open is read-only and immutable mode is intentionally not used because the live canon may rely on committed WAL state.
2. `scripts/recommendation_decision_ledger.py` and its tests provide an inert append-only point-in-time decision ledger with immutable sequencing, duplicate/tamper checks, explicit reviewed and sent-receipted states, allowlisted provider/message-id proof shapes, confinement, torn-tail repair boundaries, and honest caller-asserted provenance limits.
3. `scripts/phase4_tier_readiness.py` provides deterministic per-name onboarding/readiness and recommendation-eligibility evaluation bound to explicit ticker, universe, snapshot, and reference-pin identity.
4. `scripts/phase4_tier_transaction.py` provides an in-memory-only promotion/demotion simulation with explicit leases, expected-prior version/generation checks, expiry, human-approval claims, rollback, chained-commit conflict handling, and journal recovery checks. It has no file, network, SQL, canon, config, or scheduler path.

## Verification and mandatory QA

Host proof: **179 tests passed** and four source files compiled to disposable `tmp` cfiles:

- `python -m pytest -q scripts/test_recommendation_funnel.py` — 39 passed.
- `python -B scripts/test_recommendation_decision_ledger.py` — 50 passed.
- `python -B scripts/test_phase4_tier_readiness.py` — 49 passed.
- `python -B scripts/test_phase4_tier_transaction.py` — 41 passed.
- `py_compile` — 4/4 source files passed; output stayed under `tmp/phase4-proposal-route-20260926/pyc`.

Mandatory independent review used exactly `ollama-cloud/glm-5.3:cloud`:

- same-version lineage — **PASS**, no blocking finding (`lineage-glm53-qa.json`);
- decision ledger initial QA — FAIL on compound forbidden-field and raw-recipient-key evasions; one bounded repair landed;
- decision ledger final QA — **PASS**, zero critical/high/medium findings (dispatch `d708e43a-dc79-4b65-bc9c-d7f93d2f5193`);
- tier prototype initial QA — PASS but Main treated its medium findings as blockers; one bounded repair landed;
- tier prototype final QA — **PASS**, zero critical/high/medium findings (dispatch `a4c700e0-a62d-42ea-97a8-36729a6038ac`).

Final host manifest: `tmp/phase4-proposal-route-20260926/host-validation-final.json`.

## Accepted residual risk

All remaining findings are low or explicitly documented trust limits:

- Lineage checks can fail closed with an exception on pathological surrogate paths or malformed unhashable lineage fields; URI helper duplication and a narrow check/read race remain maintenance hardening, not fail-open recommendation paths.
- The ledger key-name tripwire still permits some unusual separator-free secondary-token or raw-recipient compounds. This does not change its stated unauthenticated-caller limit, and every enumerated blocker was closed. Any live port should strengthen the allowlist/denylist before accepting untrusted payloads.
- The tier prototype leaves cross-script actor homoglyphs to the real Main/owner authentication gate, can over-block human names that contain machine stems, retains one unused helper, and can produce an empty live-path proposal hash only for deliberately cyclic caller-forged content; recovery rejects empty hashes. Any guarded-SQL port must reject empty hashes and use authenticated approver identity.
- Generated incremental diff text has a cosmetic fullwidth-character encoding artifact; the reviewed final source bytes and tests are correct.

## Intentionally unimplemented or deferred

- No live decision-ledger writer, historical backfill, synthetic send, delivery integration, or forward scorer.
- No guarded-SQL or finance-canon tier mutation, per-ticker production writer, whole-canon apply, effective tier movement, or rollback against live state.
- No scheduler/config/runtime/channel/credential/provider change and no external delivery in this acceptance batch.
- No authenticated approval service; prototype actor labels and digests remain claims, not proof.
- The 2026-10-15 scorer-readiness owner gate remains unchanged. Ranking weights remain uncalibrated, and this acceptance does not establish profitability.

## Lane and efficiency truth

Active Phase 4 proposal-route lanes: **0**. The two implementation lanes are terminal with `technical_acceptance_status=accepted`, `main_acceptance_status=accepted`, and `activation_status=blocked`. Their register status is `blocked`, not `complete`, because truthful isolated-session accounting recorded token/cache budget breaches and legacy v1 dispatch-binding attribution limits. That administrative/resource result does not reverse the source/test/QA acceptance. The global lane register still reports one pre-existing validation error and four warnings; it is not claimed green. Receipt: `tmp/phase4-proposal-route-20260926/lane-closeout-summary.json`.

Compact usage summary for the accepted route:

- Model mix: Muse Spark 1.3 Contributor for bounded implementation proposals; Terra for the single bounded repair batch; GLM 5.3 for mandatory independent QA; Main for integration and acceptance.
- Context: all lane starts were isolated/fresh, not transcript-forked. The tier P2 continuation reused its own isolated lane session after its first response produced no files.
- Representative proposal usage: lineage 1.830M tokens / 467s; decision-ledger P2 2.521M / 631s; tier P2 initial plus continuation 1.988M / 659s.
- Initial GLM reviews: 57.5K / 213s, 127.4K / 377s, and 109.2K / 364s. Final GLM reviews: ledger 210.1K / 333s; tier 96.4K / 116s.
- Terra repair runs: ledger 3.794M tokens, reported cost about $0.899; tier 1.920M, about $0.189. Other recorded provider costs were $0. Approximate metered total exposed by receipts: **$1.09**; subscription/opportunity cost is not represented.
- Efficiency finding: the implementation succeeded, but the ledger and tier proposal sessions materially exceeded their 600K gross / 500K cached-replay lane budgets. Future work should split large files/checklists earlier and require v2 dispatch binding before claiming usage credit.

## One next decision

When the forward-scorecard and per-name readiness prerequisites are satisfied, decide whether to authorize a **separate guarded per-name transactional writer lane**. Recommendation: choose the per-name writer rather than a whole-canon rebuild, but require a fresh explicit owner gate, authenticated approval reference, non-empty canonical hashes, crash/rollback proof, and independent QA. No decision is required now to preserve this accepted inert foundation.
