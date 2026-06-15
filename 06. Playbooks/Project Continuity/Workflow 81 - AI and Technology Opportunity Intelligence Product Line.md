# Workflow 81 - AI and Technology Opportunity Intelligence Product Line

## Objective
- Turn Randall's broader AI, tools, automation, and business-opportunity intelligence into a reusable product lane with sourced opportunity briefs, tool evaluations, and product candidates.

## Current State
- Activated as a P1 product-scale lane under WF80.
- Put on hold by Randall on 2026-06-06 with the rest of WF80-WF83 while near-term work focuses on efficiency/leap-forward infrastructure.
- The lane is separate from finance recommendations: it can study tools, markets, workflows, and business ideas, but it cannot imply spend, procurement, customer claims, or external launch readiness.

## Last Meaningful Progress
- Route and continuity shell created so new sessions can pick up the lane without broad search.
- Skill decision: use `veritas-response-contract`, `veritas-pm-department`, `disciplined-implementation`, `workspace-qa-pass`, and `automation-hardening-manager`; no new skill until repeated product-intelligence workflow proves a gap.

## Outstanding
- Define a source-labeled opportunity brief schema: problem, audience, current alternatives, wedge, evidence, revenue path, build cost, risk, moat, and next validation step.
- Add a small candidate queue for AI/tool/business opportunities with confidence and evidence freshness.
- Connect promising candidates to WF83 packaging/readiness instead of letting ideas remain chat-only.
- Do not start this build while the 2026-06-06 hold is active.

## Blockers / Trust Gaps
- Vendor/tool claims need current-source verification.
- Market-size, revenue, customer, legal, privacy, and security claims must be labeled as assumptions unless sourced and reviewed.

## Next Action
- Hold. Resume only if Randall explicitly restarts WF80-WF83. Direct AI/tool research can still happen when Randall asks a specific one-off question, but the product-lane build should not be advanced now.

## Key Files
- `06. Playbooks/Project Continuity/Workflow 80 - Multi-Product Scaleout Control Plane.md` - portfolio owner.
- `06. Playbooks/Project Continuity/Workflow 83 - Product Packaging and Launch Readiness Factory.md` - downstream packaging/readiness gate.
- `06. Playbooks/Skills Governance Index.md` - skill routing and no-sprawl decision.

## Automation / Refresh Path
- Current pickup: `python scripts\workflow_routing_index.py --route WF81`.
- Future proof target: opportunity-intake JSON validator under WF80/WF83.
- Stop line: no external action, spend, account creation, outreach, customer claim, compliance/security claim, or public launch without separate approval.
