# Full Workspace Audit Checklist

Use this as a prompt-local checklist after reading `SKILL.md`.

## Control Surfaces

- Lane register validates and active lanes are accounted for.
- PM packet validates; stale/blocked/ready counts are named.
- Cron control validates; freshness scorecard and live scheduler state are reconciled when cron matters.
- Runtime scorecard validates or blockers are named.
- Artifact index validates or stale/missing artifacts are named.
- Workflow route registry: a named-workflow query returning `routing_index_stale` is not a broken workflow — run `python scripts\workflow_routing_index.py --write --write-db --validate`, re-query, and report from the refreshed capsule's live blockers.
- Go helper route registry validates when Go route posture matters.
- DB lifecycle manifest validates or unclassified databases are listed.
- Skills check passes or skill errors are listed.
- Config validation is checked only when config trust is in scope; no config mutation during review.

## Workspace Structure

- Root files and folders match workspace policy.
- Numbered top-level domains still fit their review order.
- `tmp/` contains generated/staged proof, not durable human truth unless explicitly staged.
- Final durable audits live under `08. Audits/` with machine proof under `tmp/` when needed.
- Root exceptions are documented and still justified.
- Dirty worktree is classified by risk, not treated as a single blob.

## Authority

- Generated artifacts are proof/review surfaces only.
- No artifact implies capital deployment, paper/live execution, account action, or portfolio/canon mutation without an exact gate.
- Paper/live, customer/public, and config/auth/runtime boundaries are explicit when relevant.

## Memory And Skills

- Daily memory has no duplicate headings or repeated flush entries.
- Durable lessons are routed to `MEMORY.md`, skills, procedures, or owner notes only when they should survive many sessions.
- Repeated audit patterns are captured as skill/procedure/validator recommendations.
