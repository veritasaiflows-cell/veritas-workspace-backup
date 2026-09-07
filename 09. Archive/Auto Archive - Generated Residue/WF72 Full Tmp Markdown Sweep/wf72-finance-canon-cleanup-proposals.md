# WF72 Phase 2 Finance Canon Cleanup Proposals

Status: **review-only patch proposal packet**. No canonical notes were edited. This artifact does **not** authorize portfolio mutation, sizing, sleeve/cash/risk-rule changes, trade/account action, paper/live orders, file moves/deletes/archive, or owner-approval inference.

Generated: 2026-05-22T06:37:00Z

## Evidence basis

- `tmp/current-window-artifacts.json` — generated 2026-05-22T05:13:12Z; status `ok`; 104/104 artifacts present; warning roles include `board_canon_guardrail` and `finance_discrepancy_resolver`.
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json` — generated 2026-05-22T04:56:17Z; 7 review-only packets; `apply_allowed=false`; `trade_or_account_action_allowed=false`.
- `tmp/capital-deployment-recommendation-validation.json` — generated 2026-05-22T05:48:05Z; 7 packets checked; 0 critical / 0 warning.
- `tmp/portfolio-snapshot-patch-proposal.json` — generated 2026-05-22T04:17:43Z; Snapshot freshness mismatch candidate exists.
- `tmp/board-canon-guardrail.json` — warning; 11 risk alerts; critical 0; below-stop / near-stop states must not be softened.
- `tmp/dashboard-validation.json` — warning; `canonical_sync_review_ready=true`, `capital_action_allowed=false`.
- `tmp/research-freshness-opportunity-review.json` — degraded / review-only; no portfolio/watchlist/sizing/deployment/trade authority.
- `tmp/wf72-financial-truth-map.md` and `tmp/wf72-financial-canon-os-synthesis.md` — identified the same drift themes.

## Proposal summary

| ID | Target | Drift | Authority classification |
|---|---|---|---|
| wf72_p2_001 | `03. Portfolio/Portfolio Snapshot.md` | top freshness mismatch | Eligible for bounded freshness/status sync |
| wf72_p2_002 | `03. Portfolio/Portfolio Snapshot.md` | freshness policy block still 2026-05-19 | Eligible for bounded freshness/status sync |
| wf72_p2_003 | `05. Intelligence/Weekly Intelligence Brief.md` | stale weekly scaffold / duplicated radar | Requires owner/main-session product decision |
| wf72_p2_004 | `05. Intelligence/Weekly Positioning Review.md` | weekly product owner marker | Requires owner/main-session product decision |
| wf72_p2_005 | `02. Markets/Macro Regime Dashboard.md` | duplicated opportunity radar | Eligible for bounded freshness/status sync |
| wf72_p2_006 | `04. Research/Coverage and Watchlist.md` | stale sector queue header | Eligible for bounded freshness/status sync |
| wf72_p2_007 | `04. Research/Coverage and Watchlist.md` | portfolio-review queue stale LIN status | Eligible for bounded freshness/status sync |
| wf72_p2_008 | `04. Research/Coverage and Watchlist.md` | quick-reference status mismatch | Eligible for bounded freshness/status sync |
| wf72_p2_009 | `02. Markets/Macro Regime Dashboard.md` | NVDA future-tense event row | Eligible for bounded freshness/status sync |
| wf72_p2_010 | `02. Markets/Macro Regime Dashboard.md` | NVDA future-tense open question | Eligible for bounded freshness/status sync |

## Exact proposals

### wf72_p2_001 — Snapshot top freshness block

**Target:** `03. Portfolio/Portfolio Snapshot.md`  
**Authority:** eligible for bounded freshness/status sync after main-session review.

Old:
```md
- **Date:** 2026-05-21
- **Data as of:** 2026-05-21 technical refresh
```

New:
```md
- **Date:** 2026-05-21
- **Data as of:** 2026-05-21 close / 2026-05-22 current-window artifact review
```

Rationale: current-window and Snapshot patch artifacts prove current 2026-05-21 close context. No weight/cash/sleeve/risk/execution mutation.

### wf72_p2_002 — Snapshot freshness policy block

**Target:** `03. Portfolio/Portfolio Snapshot.md`  
**Authority:** eligible for bounded freshness/status sync after main-session review.

Old:
```md
- **Last updated:** 2026-05-19 - Randall promoted LIN into a formal Materials sleeve / starter-sizing planning lane at 0% active / 3% conditional planning weight / $200-$350 starter context. This is workspace model/sleeve planning only: no live trade, paper order, brokerage/account action, money movement, owner-approval inference, or external execution entitlement.
- **Data as of:** 2026-05-19 technical refresh for current Execution Board/deployment surfaces; other technical rows remain governed by the Execution Board freshness fields
```

New:
```md
- **Last updated:** 2026-05-21 / reviewed 2026-05-22 - bounded freshness/status sync candidate after current-window artifact review. Prior LIN formal Materials sleeve / starter-sizing planning context remains unchanged: 0% active / 3% conditional planning weight / $200-$350 starter context; no live trade, paper order, brokerage/account action, money movement, owner-approval inference, or external execution entitlement.
- **Data as of:** 2026-05-21 close for current Execution Board/deployment surfaces; other technical rows remain governed by the Execution Board freshness fields
```

### wf72_p2_003 / 004 — Weekly surface consolidation

**Targets:**
- `05. Intelligence/Weekly Intelligence Brief.md`
- `05. Intelligence/Weekly Positioning Review.md`

**Authority:** requires owner/main-session product decision before apply. This is a canonical product-role choice, not a mechanical freshness sync.

Recommendation:
- Demote `Weekly Intelligence Brief.md` to a stale archive/scaffold pointer unless deliberately rebuilt.
- Mark `Weekly Positioning Review.md` as the proposed single current weekly strategy/intelligence product.
- Stop duplicating full opportunity radar inside the stale weekly scaffold.

Proof: WF72 truth map says Weekly Intelligence Brief is stale/scaffolded and Weekly Positioning Review is the best current weekly strategy candidate.

### wf72_p2_005 — Macro duplicate opportunity radar pointer

**Target:** `02. Markets/Macro Regime Dashboard.md`  
**Authority:** eligible for bounded freshness/status sync after main-session review.

Replace the full duplicated `Research and sector opportunity cue — 2026-05-21 post-close` block with a pointer that says generated opportunity-radar detail belongs in weekly/Today support and `tmp/research-freshness-opportunity-review.json`; Macro should own regime implications only.

### wf72_p2_006 / 007 / 008 — Coverage queue stale residue

**Target:** `04. Research/Coverage and Watchlist.md`  
**Authority:** eligible for bounded freshness/status sync after main-session review.

Proposed cleanup:
1. Reframe `Sector expansion research queue - 2026-05-15` as historical lineage, not current active-universe truth.
2. Update portfolio-review pass wording so LIN is no longer presented as still only in the old zero-weight queue; LIN is now formal Materials starter-sizing planning, still non-deployed/non-executable.
3. Align quick-reference statuses for LIN, META, PH, CME with the active universe / Snapshot / Execution Board.

### wf72_p2_009 / 010 — Macro stale NVDA event language

**Target:** `02. Markets/Macro Regime Dashboard.md`  
**Authority:** eligible for bounded freshness/status sync after main-session review.

Proposed cleanup:
- Change NVDA May 20 from future-tense event risk to reported/interpreted status.
- Keep no-chase discipline because Execution Board still has NVDA almost deployable / above-band no-chase.

## Stop lines preserved

- No canonical edits applied.
- No portfolio weights, cash, sleeves, sizing, risk rules, deployment entitlement, or execution authority changed.
- No trade/account action or paper/live order authority inferred.
- Weekly product consolidation is not applied here; it remains a main-session/owner product decision.
