# WF38 LLY / CAT Owner-Layer Band Review Prep - 2026-05-06

## Purpose
Turn the approved LLY/CAT band-review work into an owner-layer prep artifact without promoting either name.

This is review-only. It does not authorize canonical band application, execution-lane promotion, Trigger Sheet mutation, Portfolio Snapshot mutation, or capital deployment.

## Inputs checked
- `tmp/technical-refresh.json`
- `tmp/band-proposals.json`
- `tmp/promotion-candidate-packet-LLY.json`
- `tmp/promotion-candidate-packet-CAT.json`
- `tmp/earnings-calendar.json`
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- `03. Portfolio/Deployment Trigger Sheet.md`
- `04. Research/Coverage Universe.md`
- `06. Playbooks/Promotion Review Queue.md`

## LLY - Eli Lilly

### Current evidence
- Close: **987.05**
- MA20 / MA50 / MA200: **923.20 / 944.33 / 912.90**
- MA posture: above all MAs, but not a clean bullish 20 > 50 > 200 stack because MA50 is above MA20
- Current canonical band: **none**
- Review-only proposed band from `band_refresh.py`: **907.64-969.88**
- Review-only proposed stop: **876.52**
- Candidate packet state: `promotion_candidate=false`
- Catalyst posture: **unknown** because LLY is missing from `tmp/earnings-calendar.json`

### Owner-layer judgment
- Operational state: **Watch-only**
- Band decision: **hold as review-only; do not apply canonically yet**
- Promotion posture: **not promotion-review eligible yet**

### Blocking gates
1. No canonical entry band / stop currently exists.
2. Earnings/catalyst coverage is unknown because LLY is absent from `tmp/earnings-calendar.json`.
3. Owner-layer sizing and promotion judgment is still required.
4. Healthcare sleeve expansion case is directionally useful, but still needs a decision-grade setup.

### Next cleanup
1. Add/fix LLY earnings-calendar coverage in the machine evidence layer.
2. Re-run `catalyst_window_check.py` on the LLY packet.
3. If catalyst coverage clears, decide whether to apply the proposed band or set a more conservative owner-reviewed band.
4. Keep LLY watch-only until technical + catalyst + sizing gates clear.

## CAT - Caterpillar

### Current evidence
- Close: **926.64**
- MA20 / MA50 / MA200: **825.35 / 757.75 / 596.17**
- MA posture: above all MAs with bullish 20 > 50 > 200 stack
- Current canonical band: **787.41-840.59**
- Current canonical stop: **760.82**
- Review-only proposed band from `band_refresh.py`: **811.64-866.47**
- Review-only proposed stop: **784.24**
- Price drift: **13.8% above current band midpoint**
- Candidate packet state: `promotion_candidate=false`
- Catalyst posture: clear; next earnings shown in current artifacts as roughly 90 days out

### Owner-layer judgment
- Operational state: **Watch-only**
- Band decision: **hold as review-only; do not apply canonically yet**
- Promotion posture: **not promotion-review eligible yet**

### Blocking gates
1. CAT remains outside execution-board scope.
2. Price is extended above both the current canonical band and the suggested refreshed band.
3. Technical setup is constructive but not disciplined for new capital here.
4. Owner-layer thesis/sizing judgment still required versus ETN and stronger current setups.

### Next cleanup
1. Reconcile stale note wording that says CAT needs explicit entry/stop with the machine fact that a band/stop exists.
2. Keep the refreshed band proposal review-only until price/structure makes it useful.
3. Compare CAT against ETN and other industrial / capex candidates before any execution-lane promotion.
4. Keep CAT watch-only unless a pullback or fresh base makes the band actionable.

## Decision summary
- **LLY:** better sector-diversification candidate, but structurally underdefined and catalyst-unknown.
- **CAT:** cleaner technical coverage, but extended and still watch-lane.
- **Neither is deployable.**
- **Neither should be promoted now.**

## Recommended next action
1. Fix LLY earnings-calendar coverage.
2. Re-run the LLY validator chain.
3. Reconcile CAT note-layer band wording.
4. Revisit both in the first weekly sector-expansion review.
