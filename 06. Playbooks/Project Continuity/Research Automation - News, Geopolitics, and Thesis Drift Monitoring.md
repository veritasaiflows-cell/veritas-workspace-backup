# Research Automation - News, Geopolitics, and Thesis Drift Monitoring

## Objective
- Build a review-first research automation lane that keeps Veritas fresh on company news, geopolitical conflict, macro/policy shocks, and management responses that could affect active theses or portfolio posture.
- Keep it evidence-first and non-canonical by default: generate review surfaces before any thesis-note mutation.
- Use parallel agents as a **contract-building and QA layer**, not as a freeform research swarm.

## Current State
- The project is activated through Workflow 16 rather than left as a vague future idea.
- The old Workflow 4B -> 4C blocker is stale; those trust-hardening prerequisites are closed.
- Workflow 17 and Workflow 18 are now closed, so the workflow-contract and spawn/closeout governance prerequisites are in place.
- Workflow 16 / 16A / 16B are now closed at the intended trust level.
- The source bundle, intake packet, routing / promotion, and canonical freshness patch contracts are approved.
- Cron already supports internal finance refresh windows, but no recurring research cron is live yet.
- The approved posture remains clear: contract-backed packet artifacts and proposal-only freshness patches are allowed; schedule expansion and canonical mutation still require a separate approval gate.

## Last Meaningful Progress
- Randall explicitly requested a dedicated research automation project on 2026-05-02.
- Workflow 16, 16A, and 16B were opened to carry the lane.
- Workflow 17 and Workflow 18 were inserted ahead of execution so the automation layer starts from a tighter protocol and skills contract.
- Randall set the new automation posture on 2026-05-03: use parallel agents to build and QA the contracts first, then run bounded research through those contracts.
- Workflow 16 family closeout on 2026-05-03 approved the contract set, wrote route / no-route / stop-line packet proof, completed the bounded freshness pilot, and kept automation-level canonical mutation fail-closed.

## Outstanding
- No recurring research cron is live.
- No gated mechanical apply helper is live.
- No autonomous canonical note mutation is approved.
- The next expansion decision is whether a scheduled packet artifact is justified after enough manual/operator use proves signal quality.

## Blockers / Trust Gaps
- Memory/index reliability is still degraded, so continuity must stay file-grounded.
- The source-quality, intake, routing, and freshness-patch contracts exist, but they are still contract surfaces rather than recurring automation.
- Canonical freshness patching remains proposal-only unless manually approved.
- This should not outrun note-owner boundaries just because the cron layer is already working.

## Next Action
- Do not reopen Workflow 16 family unless Randall intentionally asks for recurring research cron, gated mechanical helpers, or broader research automation.
- Use the approved contracts as the reference surface for any future research packet or freshness-patch proposal.
- Keep the active queue on Workflow 19 unless research automation expansion is explicitly promoted again.

## Key Files
- `06. Playbooks/Automation Orchestration Protocol.md` - queue ownership and sequential auto-start rules
- `06. Playbooks/Cron Job Protocol.md` - cron boundaries and proof requirements
- `06. Playbooks/Research Unit Concept.md` - owner/truth-layer boundaries
- `05. Intelligence/Weekly Intelligence Brief.md` - likely human-readable review surface
- `01. Dashboards/Executive Brief.md` - likely dashboard-facing summary surface
- `03. Portfolio/Deployment Trigger Sheet.md` - canonical deployment owner surface
- `06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md` - umbrella workflow contract
- `06. Playbooks/Research Automation Source Bundle Contract.md` - approved source trust boundary
- `06. Playbooks/Research Automation Intake Packet Contract.md` - approved packet schema and materiality / confidence rules
- `06. Playbooks/Research Automation Routing and Promotion Contract.md` - approved route / no-route / stop-line behavior
- `06. Playbooks/Research Automation Canonical Freshness Patch Contract.md` - approved proposal-only freshness patch boundary

## Automation / Refresh Path
- closed: source bundle contract
- closed: intake packet contract
- closed: routing / promotion contract
- closed: canonical freshness patch contract
- closed: bounded pilot
- future-only: recurring packet schedule, gated apply helper, or broader automation
- out of bounds initially: autonomous thesis rewrites, autonomous portfolio judgment, freeform multi-agent swarm debate, direct canonical-note mutation, or noisy alert spam
