# Research Automation - News, Geopolitics, and Thesis Drift Monitoring

## Objective
- Build a review-first research automation lane that keeps Veritas fresh on company news, geopolitical conflict, macro/policy shocks, and management responses that could affect active theses or portfolio posture.
- Keep it evidence-first and non-canonical by default: generate review surfaces before any thesis-note mutation.

## Current State
- The project is defined but not active yet.
- The current higher-priority chain is still Workflow 4B -> Workflow 4C because the control plane and finance note layer need honest synchronization first.
- No trusted recurring source bundle, review window, or dashboard/workbook handoff contract is pinned down yet.

## Last Meaningful Progress
- Randall explicitly requested a dedicated research automation project on 2026-05-02.
- The intended scope is clear: news freshness, geopolitical conflict monitoring, company-response tracking, and event detection that matters to existing theses or posture.

## Outstanding
- Define the first approved source bundle and ownership boundary.
- Decide what belongs in cron, what remains a review surface, and what stays manual.
- Define how findings should surface into dashboards, workbooks, weekly intelligence, and thesis-review queues without creating canonical-note drift.
- Define stop lines for rumor-heavy, low-confidence, or duplicate event noise.

## Blockers / Trust Gaps
- The finance note layer is not fully truth-synced yet.
- Memory/index reliability is still degraded, so continuity must stay file-grounded.
- No explicit source-quality contract exists yet for geopolitical/news monitoring.
- This should not outrun the current trust-hardening and note-sync queue.

## Next Action
- After Workflow 4C stabilizes the top finance notes, open a bounded design pass for source bundle, review windows, stop lines, and dashboard/workbook handoff.

## Key Files
- `06. Playbooks/Automation Orchestration Protocol.md` - queue ownership and sequential auto-start rules
- `06. Playbooks/Cron Job Protocol.md` - cron boundaries and proof requirements
- `05. Intelligence/Weekly Intelligence Brief.md` - likely human-readable review surface
- `01. Dashboards/Executive Brief.md` - likely dashboard-facing summary surface
- `06. Playbooks/Project Continuity/Workflow 4C - Finance Chain Truth Sync Hardening.md` - current prerequisite chain

## Automation / Refresh Path
- likely phase 1: scheduled evidence collection or intake packets only
- likely phase 2: scheduled review surfaces for thesis drift / geopolitical risk / company response
- out of bounds initially: autonomous thesis rewrites, autonomous portfolio judgment, or noisy alert spam
