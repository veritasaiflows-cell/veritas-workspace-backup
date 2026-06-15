# Workflow 82 - Learning and Teaching Product Line

## Objective
- Convert internal training, teaching, Academy assets, playbooks, and workflow explanations into reusable learning products without confusing internal training with customer-ready education.

## Current State
- Activated as a P1 product-scale lane under WF80.
- Put on hold by Randall on 2026-06-06 with the rest of WF80-WF83 while near-term work focuses on efficiency/leap-forward infrastructure.
- Existing source assets include WF75 Academy, skills, operating procedures, and workflow explanations. They are internal by default.

## Last Meaningful Progress
- Route and continuity shell created.
- Skill decision: use existing Academy/PM/continuity/response/governor skills; do not add a new education skill yet.

## Outstanding
- Inventory internal assets that can become lessons, checklists, templates, or short courses.
- Define learning-product stages: internal note, reusable lesson, guided worksheet, recorded/scripted module, customer-gated product.
- Add quality gates for clarity, accuracy, safety, and scope before any public/customer use.
- Do not start this build while the 2026-06-06 hold is active.

## Blockers / Trust Gaps
- Internal workflow assets may contain assumptions, workspace-specific paths, or finance boundaries that are not customer-safe.
- Education products need separate review for claims, audience, privacy, and support expectations.

## Next Action
- Hold. Resume only if Randall explicitly restarts WF80-WF83. Internal training assets may still support immediate workflow efficiency, but learning-product packaging should not advance now.

## Key Files
- `scripts/wf75_training_desk.py` - internal Academy route.
- `06. Playbooks/Project Continuity/Workflow 75 - AI Productivity and Business Opportunity Intelligence Expansion.md` - existing Academy/product context.
- `06. Playbooks/Project Continuity/Workflow 83 - Product Packaging and Launch Readiness Factory.md` - launch readiness owner.

## Automation / Refresh Path
- Current pickup: `python scripts\workflow_routing_index.py --route WF82`.
- Future proof target: learning-asset inventory JSON plus safety/readiness validator.
- Stop line: no customer/public training product, certification, legal/compliance claim, guaranteed outcome claim, or external publication without separate approval.
