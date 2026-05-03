# Research Automation - News, Geopolitics, and Thesis Drift Monitoring

## Objective
- Build a review-first research automation lane that keeps Veritas fresh on company news, geopolitical conflict, macro/policy shocks, and management responses that could affect active theses or portfolio posture.
- Keep it evidence-first and non-canonical by default: generate review surfaces before any thesis-note mutation.
- Use parallel agents as a **contract-building and QA layer**, not as a freeform research swarm.

## Current State
- The project is activated through Workflow 16 rather than left as a vague future idea.
- The old Workflow 4B -> 4C blocker is stale; those trust-hardening prerequisites are closed.
- Cron already supports internal finance refresh windows, but no approved recurring research source bundle, intake packet contract, routing contract, or canonical freshness helper contract is live yet.
- The approved posture is now clear: contracts first, then bounded pilot, then only later any schedule expansion.

## Last Meaningful Progress
- Randall explicitly requested a dedicated research automation project on 2026-05-02.
- Workflow 16, 16A, and 16B were opened to carry the lane.
- Workflow 17 and Workflow 18 were inserted ahead of execution so the automation layer starts from a tighter protocol and skills contract.
- Randall set the new automation posture on 2026-05-03: use parallel agents to build and QA the contracts first, then run bounded research through those contracts.

## Outstanding
- Define the **Source Bundle Contract**.
- Define the **Intake Packet Contract**.
- Define the **Routing / Promotion Contract**.
- Define the **Canonical Freshness Patch Contract**.
- Prove the system on a bounded pilot before broader rollout.

## Blockers / Trust Gaps
- Memory/index reliability is still degraded, so continuity must stay file-grounded.
- No explicit source-quality contract exists yet for geopolitical/news monitoring.
- No approved routing / dashboard/workbook handoff contract exists yet.
- No canonical freshness classifier or apply-helper contract exists yet for daily note updates.
- This should not outrun note-owner boundaries just because the cron layer is already working.

## Next Action
- Hold execution until Workflow 17 and Workflow 18 close or are intentionally superseded.
- Then run Workflow 16A in order:
  1. Source Bundle Contract
  2. Intake Packet Contract
  3. Routing / Promotion Contract
- Then run Workflow 16B:
  4. Canonical Freshness Patch Contract
  5. bounded pilot
- Do not schedule autonomous canonical note mutation in the first pass.

## Key Files
- `06. Playbooks/Automation Orchestration Protocol.md` - queue ownership and sequential auto-start rules
- `06. Playbooks/Cron Job Protocol.md` - cron boundaries and proof requirements
- `06. Playbooks/Research Unit Concept.md` - owner/truth-layer boundaries
- `05. Intelligence/Weekly Intelligence Brief.md` - likely human-readable review surface
- `01. Dashboards/Executive Brief.md` - likely dashboard-facing summary surface
- `03. Portfolio/Deployment Trigger Sheet.md` - canonical deployment owner surface
- `06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md` - umbrella workflow contract

## Automation / Refresh Path
- phase 1: source bundle contract
- phase 2: intake packet contract
- phase 3: routing / promotion contract
- phase 4: canonical freshness patch contract
- phase 5: bounded pilot
- out of bounds initially: autonomous thesis rewrites, autonomous portfolio judgment, freeform multi-agent swarm debate, direct canonical-note mutation, or noisy alert spam
