# Macro Policy and Timing Trust Protocol

## Purpose
Separate real remaining trust limits from stale inherited caveats in the macro/policy layer.

This protocol exists so downstream notes stop repeating old warning language after the underlying trust state changes.

## Current trust split

### Intentionally retained caution
These are still real and should stay visible:
- policy expectations are a **single-step futures approximation**, not a full FedWatch tree
- true pre-market pricing is still not reliably available from the current yfinance responses
- provider-derived earnings dates may still need direct confirmation when a decision is close enough that timing changes matter
- `NVDA` remains the main live timing-confirmation residue until a cleaner primary confirmation path is available

### Repaired or retired caveats
These should **not** keep appearing as if still active:
- manual Fed target-range maintenance as the default policy posture
- broad "policy manual dependencies" wording when `tmp/policy-expectations.json` shows primary sourcing and no live manual dependencies
- broad "one or more timing-sensitive earnings dates changed" wording when the actual unresolved set has narrowed materially
- stale BRK.B pre-report timing language after the report already happened
- stale ETN Apr 30 vs May 5 mismatch framing once the earlier date passed without the event occurring

## Owner surfaces
- `tmp/policy-expectations.json` -> policy artifact truth
- `tmp/market-state.json` -> macro machine summary and source caveats
- `05. Intelligence/Event Calendar.md` -> canonical timing-risk note layer
- `02. Markets/Macro Regime Dashboard.md` -> human macro interpretation
- `03. Alerts and Recommendations/Alert Operations Board.md` -> weekly alert and recommendation implications
- `01. Dashboards/Executive Brief.md` / `01. Dashboards/Next Actions.md` -> compact downstream orientation only

## Update rules

### Policy layer
If `tmp/policy-expectations.json` shows:
- `status=ok`
- primary source mode
- no live `manual_dependencies`

then downstream notes may still say the policy layer is approximate or fail-closed, but they should **not** say it is still manually maintained by default.

### Timing layer
If timing residue narrows to one or two names, downstream notes should name those names directly.
Do not keep broad "date integrity" warnings once the unresolved set is small and specific.

### Fail-closed rule
If policy or timing confidence degrades again, re-add the specific caveat that matches reality.
Do not keep permanent caution text just because it was once true.

## Current 2026-05-03 interpretation
- policy target range is now primary-sourced and confirmed in the artifact
- policy probabilities remain usable with caution because the methodology is simplified, not because the target range is manually maintained
- broad dashboard-validation warning stacks are no longer the live reason for reduced trust on the active surfaces
- active timing residue is now narrow, led by `NVDA`; other names should be described more precisely

## Workflow 12 closure standard
Workflow 12 is honestly closed when:
- intentional caution is clearly separated from stale inherited caveats
- active downstream notes stop overstating manual-policy debt
- active downstream notes stop using broad timing-risk phrasing where a specific named residue is more truthful
- the remaining manual or approximate elements are explicitly owned instead of implied as background noise
