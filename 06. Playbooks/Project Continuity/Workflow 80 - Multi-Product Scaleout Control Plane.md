# Workflow 80 - Multi-Product Scaleout Control Plane

## Objective
- Build a product-portfolio operating layer so Veritas can scale from finance-first workflows into multiple product lines without fragmenting truth, authority, or resource focus.

## Current State
- Activated on 2026-06-05 after Randall asked whether adding resources could scale the workspace toward a Microsoft-style multi-product posture.
- Put on hold by Randall on 2026-06-06 as an ultimate goal while near-term work focuses on efficiency/leap-forward infrastructure.
- Existing product lanes: Retail Investor Finance Intelligence SaaS remains P0; SMB Workflow Clarity / Lead Rescue remains P1.
- New scaleout lanes: WF81 AI/technology opportunity intelligence, WF82 learning/teaching product line, and WF83 product packaging / launch-readiness factory.

## Last Meaningful Progress
- Product scaleout was routed into Active Workflows, Startup Truth Index, TOOLS, Skills Governance Index, and the workflow routing index.
- Decision: do not add a new skill yet. Use existing PM, SMB, response-contract, implementation, QA, and continuity skills until repeated product-scale friction proves a new skill is justified.

## Outstanding
- Build a JSON-first product registry and validator with product IDs, stage, owner workflow, proof route, target user, current artifact, blocker, next action, and stop lines.
- Add a product-stage vocabulary: idea, research, prototype, internal-pilot, service-ready, packaged, customer-gated, blocked.
- Add a resource-allocation scorecard across product lanes so more resources improve throughput instead of multiplying unfinished work.
- Do not start this build while the 2026-06-06 hold is active.

## Blockers / Trust Gaps
- Customer/public delivery remains blocked until privacy, source licensing, compliance, support, and output-safety gates exist.
- Additional resources only scale the system if product lanes have owners, validators, artifacts, stop lines, and a queue discipline.

## Next Action
- Hold. Resume only if Randall explicitly restarts WF80-WF83 after the near-term efficiency/leap-forward lanes are stronger. Current priority should route through WF78 evidence quality, WF73/WF72 control-plane efficiency, WF79 command visibility, and P0 retail truth routing.

## Key Files
- `06. Playbooks/Active Workflows.md` - live queue truth.
- `scripts/workflow_routing_index.py` - derived route map for WF80-WF83 pickup.
- `06. Playbooks/Skills Governance Index.md` - skill ownership and no-skill-sprawl boundary.
- `06. Playbooks/Project Continuity/Workflow 81 - AI and Technology Opportunity Intelligence Product Line.md` - AI/opportunity vertical.
- `06. Playbooks/Project Continuity/Workflow 82 - Learning and Teaching Product Line.md` - education/content vertical.
- `06. Playbooks/Project Continuity/Workflow 83 - Product Packaging and Launch Readiness Factory.md` - shared packaging gate.

## Automation / Refresh Path
- Current pickup: `python scripts\workflow_routing_index.py --route WF80`.
- Future proof target: `python scripts\product_scaleout_registry.py --write --validate`.
- Stop line: report-only until separately approved; no customer/public output, spend, external action, account/customer data import, legal/compliance claim, or finance execution authority.
