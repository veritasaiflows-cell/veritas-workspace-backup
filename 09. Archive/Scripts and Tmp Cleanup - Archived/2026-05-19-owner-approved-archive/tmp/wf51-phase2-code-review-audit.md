# WF51 Phase 2 Code-Review Audit

Generated: 2026-05-09 America/Phoenix

## Review scope

Independent review of the WF51 Phase 2 read-only daily price-trend signal implementation after main-session patch.

Claimed change: add `scripts/daily_price_trend_signals.py`, `scripts/test_daily_price_trend_signals.py`, and `tmp/daily-price-trend-signals.json` as a review-only trend/readiness artifact with no canonical mutation, no execution authority, honest missing-history posture, and material shortlist visibility for PROMOTION REVIEW / ALMOST DEPLOYABLE names including GS-style candidates.

## Files inspected

- `06. Playbooks/Project Continuity/Workflow 51 - Daily Fresh Intelligence and Price Trend Promotion Branch.md`
- `tmp/wf51-phase1-synthesis.md`
- `scripts/daily_price_trend_signals.py`
- `scripts/test_daily_price_trend_signals.py`
- `tmp/daily-price-trend-signals.json`
- Representative upstream artifacts:
  - `tmp/deployment-readiness-surface.json`
  - `tmp/band-proposals.json`
  - `tmp/dashboard-validation.json` via embedded payload freshness
  - `tmp/regime-scores.json` via payload fields

## Blocking findings

### 1. Output still emits execution/sizing language through raw shortlist context

`tmp/daily-price-trend-signals.json:382` contains:

> `In band at 878.71 to 926.76, but only as a tactical add with disciplined size while JPM remains the primary bank setup`

Source is `tmp/deployment-readiness-surface.json:120`, copied by `scripts/daily_price_trend_signals.py:301-302` through `peer_or_opportunity_cost_context = record.get("trigger")`.

Why this blocks Phase 2 close:
- Phase 2 acceptance explicitly forbids promotion/sizing/execution implication.
- The audit lens requested absence of probability/execution/sizing language.
- The validator forbids only narrow phrases such as `position size` and `sizing recommendation`; it does not catch `tactical add`, `disciplined size`, or raw `trigger` execution wording.

Smallest repair:
- Sanitize or replace raw shortlist `trigger` text before writing `peer_or_opportunity_cost_context`.
- Recommended replacement style: `entry/opportunity-cost context retained from source; owner review required before any promotion decision` plus raw source reference if needed.
- Extend `FORBIDDEN_TEXT` / tests to catch at least `tactical add`, `disciplined size`, and `sizing` in the WF51 output artifact.

## Should-fix-now findings

### 1. Macro-degraded names can still be labeled `improving` / `increased`

Examples from live artifact:
- ETN: `trend_signal=improving`, `promotion_readiness_direction=increased`, blockers include `macro_gate_degraded`.
- GS: `trend_signal=improving`, `promotion_readiness_direction=increased`, blockers include `macro_gate_degraded`.
- JPM: `trend_signal=improving`, `promotion_readiness_direction=unchanged`, blockers include `macro_gate_degraded`.

Relevant code:
- `scripts/daily_price_trend_signals.py:164-165` returns `improving` for `IN_BAND` / `NEAR_BAND` / `PROMOTION REVIEW` before macro degradation is considered.
- `scripts/daily_price_trend_signals.py:182-183` returns `increased` for `PROMOTION REVIEW` / `IN_BAND` / `NEAR_BAND` before macro degradation is considered.
- `scripts/daily_price_trend_signals.py:234-235` adds `macro_gate_degraded` only as a blocker.

This is not as severe as the sizing-language blocker because authority flags remain safe and the blocker is visible. But fail-closed semantics would be stronger if macro degradation capped readiness direction to `unchanged` or added a separate `confidence_ceiling=review_required` / `macro_capped=true` field so `increased` does not read as promotion readiness under a degraded macro gate.

### 2. History status has a latent stale/available honesty gap

`history_status()` returns `available` for any parseable non-empty history file (`scripts/daily_price_trend_signals.py:81-94`) and never returns `stale`; `_latest_history` is loaded but unused (`scripts/daily_price_trend_signals.py:319`).

Current live artifact is safe because history is missing and all deltas are `unknown`. But once WF43 creates a history file, this script can report `history_status=available` while still leaving all deltas unknown and without freshness/staleness evaluation.

Smallest repair before WF43 integration:
- keep current missing-history behavior now;
- add a test fixture for stale/available history;
- either return `stale` when latest row is old/unusable or keep status `partial` until comparable prior ticker state is actually consumed.

## Acceptable residue

- Signal-level source provenance is path-only, but top-level `source_artifacts` includes existence, generated timestamps, and source freshness details. This is acceptable for Phase 2 standalone output.
- `material_shortlist` correctly preserves PROMOTION REVIEW and ALMOST DEPLOYABLE visibility, including GS, without canonical note mutation.
- BELOW_STOP / below_stop / DO NOT TOUCH repair-style names fail closed to `trend_signal=blocked` and `promotion_readiness_direction=blocked` in live output and tests.
- Missing history is handled honestly in the current run: `history_status=missing`, all deltas unknown, and `prior_state_history_unavailable` blockers are present.

## Proof assessment

Ran:

```powershell
python -m py_compile scripts\daily_price_trend_signals.py scripts\test_daily_price_trend_signals.py; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; python scripts\test_daily_price_trend_signals.py
```

Result:

```text
daily_price_trend_signals_tests_passed
```

Direct artifact inspection confirmed:
- authority flags are present and false/true as required;
- `owner_approval_granted=false`;
- no canonical/portfolio/deployment/trade authority is granted;
- GS appears in `material_shortlist`;
- source freshness/degraded macro context is carried forward;
- output contains the blocking GS sizing/execution phrase noted above.

## Phase 2 close recommendation

Phase 2 should **not close yet**. The implementation is structurally close and tests pass, but the output artifact still contains raw execution/sizing language. After sanitizing shortlist context and adding a vocabulary guard for `tactical add` / `disciplined size` / generic `sizing`, Phase 2 can likely close with the history-staleness issue recorded as WF43-linked residue or fixed immediately if the main session wants a cleaner handoff.
