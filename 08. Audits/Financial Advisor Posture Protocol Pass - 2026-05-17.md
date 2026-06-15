# Financial Advisor Posture Protocol Pass - 2026-05-17

## Goal

Align Veritas runtime notes, protocols, and skills around a bounded financial-advisor posture: high-quality recommendation synthesis is allowed, and main-session Veritas may apply exact standing-approved workspace portfolio/canon maintenance when WF64/WF56 gates pass; external execution, account control, owner-approval inference for trades/accounts, tax/legal/professional advice, and ungated portfolio/canon mutation remain blocked.

## Surfaces updated

| Surface | Update |
|---|---|
| `TOOLS.md` | Added `sec` as inspected official-source evidence tooling; added `veritas-financial-planning-pass` to the finance spine; codified financial-advisor posture and boundaries. |
| `06. Playbooks/Startup Truth Index.md` | Added active advisor posture pickup language and `tmp/sec-skill-smoke-test-report.json` proof pointer. |
| `06. Playbooks/Skills Governance Index.md` | Updated live workspace skill count to 30 and added `sec` with Tier 2 bounded smoke proof. |
| `skills/veritas-financial-planning-pass/SKILL.md` | Tightened planner/advisor posture: not licensed adviser/broker/custodian/accountant/attorney; added tax/legal/retirement/insurance/debt/outside-asset constraints and one-missing-decision rule. |
| `skills/veritas-response-contract/SKILL.md` | Added planner/advisor response routing and tax/legal/outside-account constraint boundary. |
| `skills/veritas-portfolio-update/SKILL.md` | Separated board sync from holistic planning and blocked advisor-laundering through board state. |
| `skills/veritas-weekly-brief/SKILL.md` | Added planner handoff and weekly advisor boundary. |
| `skills/veritas-investment-deck/SKILL.md` | Added presentation/advisor authority boundary and WF55/review-only disclosure rule. |
| `skills/veritas-post-earnings-sync/SKILL.md` | Added planner handoff and post-earnings advisor boundary. |
| `skills/veritas-macro-pass/SKILL.md` | Added macro-to-planning handoff and authority boundary. |
| `skills/veritas-technical-pass/SKILL.md` | Added technical readiness is not advice/execution authority boundary. |
| `skills/veritas-fundamental-pass/SKILL.md` | Added planner handoff for holistic allocation advice and broader-constraint fit. |

## Current posture after pass

Allowed:
- synthesize goals, constraints, risk, liquidity, concentration, macro, fundamentals, technicals, and official-source evidence
- act as Randall's bounded financial advisor inside the workspace
- prepare owner-gated recommendations and portfolio-adjustment proposals
- apply exact standing-approved workspace portfolio/canon maintenance as main-session Veritas only through WF64-style gated validators
- use SEC/EDGAR evidence as review input under WF65/WF66

Blocked:
- trade/account/brokerage/money movement
- owner-approval inference
- execution entitlement
- tax/legal/insurance/estate/accounting professional advice
- probability, win-rate, expected-return, percent-likelihood, calibrated-score, or model-ranked deployment language without WF55 retained-outcome validation
- direct canon/portfolio mutation from `sec`, dashboard packets, weekly briefs, decks, technical passes, macro passes, post-earnings scorecards, or planner prose without the separate WF64/WF56 gated apply path

## Validation required

- `openclaw skills check`
- targeted grep scan for advisor/probability/execution boundary terms after patching

## Remaining limits

This pass hardens procedural posture; it does not make Veritas a licensed financial adviser or authorize external action. The next useful build step is a small SEC evidence wrapper that writes review-only WF65/WF66 packets with provenance and hard-false authority fields.
