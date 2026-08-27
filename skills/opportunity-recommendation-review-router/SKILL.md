---
name: "opportunity-recommendation-review-router"
description: "Deprecated router to intelligence effort and response contracts."
---

# Opportunity Recommendation Review Router

Deprecated compatibility router.

Use `veritas-intelligence-effort-router` for opportunity review, ticker recommendations, candidate ranking, deployment-readiness triage, blocker explanation, approval-card preparation routing, and whether something should move toward capital-deployment review.

Use `veritas-response-contract` for the final Randall-facing answer shape: recommendation versus approval, review-ready versus deployable, proof rollup, owner-gated action labels, approval-card wording, and plain-English blocker explanation.

This skill exists only to catch older references while they are drained. When invoked, immediately route to the two canonical owners and preserve these expectations:

- Start with SQL-canon guard/current-state routing when finance or ticker data matters.
- Use current WF78 lane-qualified truth for non-capital tier routing, promotion debt, repair state, and research-bench movement.
- Use WF84 for data-plane freshness and source-backed ticker state.
- Use WF85 for full trade-grade answer/card assembly when guard-clean.
- Use WF86/WF87 artifacts only for assisted decisions, shadow decisions, promotion outcomes, command-center state, or follow-on workflow queues.
- Open exact owner artifacts before material recommendation claims.
- Tier A gets quote/band/stop reconciliation, WF85 timing gate, source freshness/source-open checks, concentration/crowding review, and paper-card readiness only when paper preparation is in scope.
- Tier B routes to research-bench repair and must not produce deployment cards unless promoted and revalidated.
- Tier C remains thin monitor unless an attention trigger, catalyst, repair signal, or promotion candidate exists.
- Approval-card readiness still requires current market-window quote proof when relevant, current written band/stop or explicit blocker, clean WF85 timing, source freshness, portfolio-fit context, explicit authority boundary, WF67 paper guard proof when paper is involved, and exact Randall approval before any paper action.
- Historical/stale lineage surfaces, old Tier B evidence repair packets, old legacy-42 surfaces, and readiness-review labels are not current quote or tier authority.
- Conflicting current surfaces require confidence downgrade and repair routing, not forced recommendations.
- Machine blockers should be translated into human decision language before closeout.

Do not use this skill as a separate finance recommendation authority. Do not expand this skill. Do not delete or archive it until active reference scans are clean and Randall separately approves removal.

## Authority Boundary

This router does not authorize live trading, paper execution, capital deployment, brokerage/account action, cash/sizing/execution mutation, portfolio/canon mutation outside validator-backed approved gates, external/customer delivery, or owner approval inference from rankings, alerts, cards, clean validation, or paper fills.

No recommendation label creates capital deployment approval, order submit/cancel/sell authority, live endpoint authority, account action, money movement, external delivery, portfolio/canon/cash/sizing/risk mutation, or owner approval.
