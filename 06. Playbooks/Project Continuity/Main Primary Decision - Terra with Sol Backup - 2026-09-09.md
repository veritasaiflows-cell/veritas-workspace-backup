# Main Primary Decision — Terra with Sol Backup

## Decision (owner-gated, decided 2026-09-09 21:12 MST)
- Randall: Main primary is **Terra** (`openai/gpt-5.6-terra`); **Sol** (`openai/gpt-5.6-sol`) is first backup. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- This resolves finding 1 of the Isolated Agent Optimization and Specialization Review (policy said Astra, live config ran Sol). <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

## Current state at decision time
- `scripts/agent_fleet_policy.py`: `MAIN_PRIMARY = openai/gpt-6-astra`, `MAIN_FALLBACKS = [openai/gpt-5.6-sol]`. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Live `openclaw.json` `agents.entries.main.model`: primary `openai/gpt-5.6-sol`, fallbacks `[sol, terra, grok-4.6, glm-5.3, kimi-k3, opus-5]` (Sol duplicated as its own fallback). <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Lane collision preflight for this card + review update: `ok`, 0 collisions. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

## Applied diffs (applied 2026-09-09 evening MST on explicit Randall 'apply')
- `openclaw.json` `agents.entries.main.model`: primary `openai/gpt-5.6-sol` -> `openai/gpt-5.6-terra`; fallbacks -> `["openai/gpt-5.6-sol", "xai/grok-4.6", "ollama-cloud/glm-5.3:cloud", "ollama-cloud/kimi-k3:cloud", "anthropic/claude-opus-5"]` (Sol first, Terra removed from fallback dup). <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- `scripts/agent_fleet_policy.py`: `MAIN_PRIMARY = MAIN_MODEL` -> `MAIN_PRIMARY = TERRA_MODEL`; `MAIN_FALLBACKS = [SOL_MODEL]` unchanged (Sol already first/only). Header comment updated to match. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Rollback: re-apply the two diffs in reverse; no data migration involved. Any required gateway restart remains operator-owned. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

## Apply closeout
- Applied: both diffs above, verified by readback. Policy import: `MAIN_PRIMARY=openai/gpt-5.6-terra`, `MAIN_FALLBACKS=[sol]`, `validate_policy_maps`=ok. Config projection: primary Terra, Sol first fallback. Bootstrap generator `--agents all --validate`: exit 0. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Test note: `scripts/test_agent_fleet_policy.py` errors 9/9 on missing `errors` fixture (no conftest in repo) — identical on the unmodified HEAD version, so pre-existing and unrelated. Equivalent functional assertions (primary, fallbacks, closed recovery, no auto-fallbacks, never-authorized dispatch) all pass. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Untouched by design: `ON_DEMAND_ARCHITECTURE` Sol-architecture lane and all specialist primaries/recovery lists. Gateway restart (if needed for the new primary to take effect) remains operator-owned — verify the live Main model on the next turn. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Plan bullets above retired: all three checks executed with the results stated in this closeout.

## Follow-ons (separate explicit requests, not this lane)
- Skill wording (`veritas-model-routing-helper-lanes`, `veritas-isolated-agent-contract`, Startup Truth Index) still names Astra as Main primary: patch only through Skill Workshop with an explicit publication request. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Bootstrap profile revision + attachment re-proof on the new primary at the next real dispatch; no dedicated model-proving run. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

## Stop lines
- No capital, order, brokerage, account, or money action; no paper/live execution; no canon/portfolio mutation; no other config/auth/network/channel/runtime change beyond the two diffs above; no silent substitution anywhere else in the fleet. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
