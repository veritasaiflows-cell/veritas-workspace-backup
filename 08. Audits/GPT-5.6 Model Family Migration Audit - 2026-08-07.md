# GPT-5.6 Model Family Migration Audit - 2026-08-07

## Decision

The active OpenAI routing posture is now:

- `openai/gpt-5.6-sol`: main session, orchestration, final integration, and high-stakes final judgment.
- `openai/gpt-5.6-terra`: serious and routine helper work, implementation, research, review, audit, and tool-heavy automation.
- `openai/gpt-5.6-luna`: proven deterministic cron/status/proof `agentTurn` jobs at low reasoning.
- `openai/gpt-5.5`: primary fallback.
- `openai/gpt-5.4`: explicit rollback/control route during migration validation.
- Model-free cron commands remain model-free.

No gateway restart, channel/binding change, schedule/cadence change, credential change, finance canon/portfolio mutation, or execution action was performed.

## Applied Changes

- Migrated six persistent helpers from GPT-5.4 to Terra: research-scout, qa-redteam, finance-source-scout, finance-redteam, implementation-builder, and docs-continuity-editor.
- Regenerated all six bootstrap/capability surfaces; generator validation reported `ok` and all six resolved Terra.
- Preserved the default fallback prefix exactly as Sol -> GPT-5.5 -> GPT-5.4.
- Removed the unsupported `anthropic/claude-fable-5` entry from the deep fallback chain after final route projection; the approved Sol -> GPT-5.5 -> GPT-5.4 prefix and remaining rollback/challenger routes were unchanged.
- Updated active core routing playbooks, helper-routing producers, cron policy producers, and targeted tests. Historical records were not rewritten.
- Closed the independent post-change audit's seven active-policy gaps: PM autonomy now defaults to Terra medium, cached status identifies Sol, unsupported-route guidance points to Sol/Terra, and the current agent, cron, continuity, and skill-governance playbooks reflect the new family.
- Cron inventory after migration: 50 enabled jobs = 36 model-free commands, 3 main-session system events, 8 Luna agent turns, 2 Terra agent turns, and 1 opaque internal memory turn with no explicit model override.
- Reconciled five active cron contracts to the new routes and current live payloads. Contract validation finished with drift `0`, missing `0`, and warning-only prompt-bloat residue.

## Model Proof

- Prior representative benchmark: Sol/Terra/Luna at medium and low reasoning, 6/6 strict workload passes, no fallback, about $0.31 published-rate API-equivalent cost. Proof: `tmp/gpt56-representative-benchmark-20260807.json`.
- Terra tool proof: three independent low-reasoning read-only audit lanes completed successfully using workspace tools and returned convergent findings.
- Luna scheduler canary: status-card refresh forced once on Luna low; status `ok`, exact `NO_REPLY`, no fallback, model `gpt-5.6-luna`, provider `openai`, 25.1 seconds, 417 direct input tokens, 6 output tokens, 23,719 runtime-total tokens.

## Governed Skill Proposals

Pending only; not applied without Randall's explicit approval:

- `veritas-model-routing-helper-lanes-20260808-ccb0e24e43`
- `veritas-isolated-agent-contract-20260808-c758393cab`
- `ai-drop-service-os-contract-20260808-1c5ddd5975`
- `cron-automation-manager-20260808-334c1ee3e1`

## Validation

- `openclaw config validate`: pass.
- Final redacted config projection: Sol primary, GPT-5.5 first fallback, GPT-5.4 second fallback, and no Fable fallback entry.
- `openclaw skills check`: 66 eligible/visible, 0 missing requirements.
- `cron_contract_validator.py --write --validate`: warning, drift 0, missing 0; remaining warning is prompt-bloat, not model-route drift.
- `test_long_work_packet_linter.py`: pass.
- `test_cron_cadence_reduction_plan.py`: pass.
- `test_project_implementation_router.py`: pass.
- Python compile for seven changed routing producers: pass.
- Python compile for the final PM/status/cron-policy corrections: pass.
- `test_status_card_packet.py`: pass.
- `test_cron_contract_validator.py`: pass.
- Independent read-only migration audit: required routing/config/agent/cron/contract checks passed; verdict `closed-with-follow-up` because operational and governance follow-ups below remain intentionally separate.
- Workflow router, PM control packet, and status-card generation: validation pass; current operating surfaces still contain stale/blocked domain signals.

## Honest Residue

- `test_agent_bootstrap_generator.py` still has three structural failures because implementation-builder/docs-continuity profiles and the `implementation-support` alias are absent from the generator. This predates the model migration; live regeneration itself passed and all six agents now report Terra.
- The refreshed cron control packet validates structurally but reports 22 blocked signals, 25 attention signals, 12 live last-run exceptions, and blocked OTEL health. The shared closeout bundle therefore stops at `cron_control_packet`. These are not model-install failures and were not silently converted into unrelated repair work.
- Four skill proposals remain pending, so live skill text still contains legacy routing until Randall explicitly approves application.
- The active non-skill routing surfaces identified by independent audit are now aligned. Historical governance entries remain unchanged by design.
- The current long-lived WebChat session may retain cached fallback-display state; saved config and new sessions use Sol -> GPT-5.5 -> GPT-5.4. No restart was performed.

## Next Safe Actions

1. Randall reviews and explicitly applies or rejects the four Skill Workshop proposals.
2. Observe two natural Luna runs for quiet-contract, artifact, latency, and fallback behavior before lowering more reasoning or expanding Luna scope.
3. Repair the bootstrap generator's missing implementation/docs profiles and alias as a separate bounded implementation lane.
4. Triage current cron/domain blockers from `tmp/cron-control-packet.json`; do not conflate them with model migration success.
