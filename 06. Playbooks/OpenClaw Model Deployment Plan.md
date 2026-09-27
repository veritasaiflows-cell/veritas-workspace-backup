# OpenClaw Model Deployment Plan

## Current Status

This playbook is now a thin deployment-map pointer, not the live model-routing authority.

Live model choice is owned by `skills/veritas-model-routing-helper-lanes/SKILL.md`.
Spawn packet mechanics are owned by `06. Playbooks/Subagent Spawn Handoff Template.md`.
Verified Opus challenger lanes for serious gates remain owned by `skills/ic-swarm-orchestrator/SKILL.md`.
Cron schedule and contract design remain owned by `skills/cron-automation-manager/SKILL.md`.

## Current Baseline

- Main session: `anthropic/claude-opus-5-5` (Opus 5.5, claude-cli runtime) for truth integration, orchestration, final synthesis, high-stakes finance judgment, ambiguous cross-contract failures, and user-facing final recommendations (owner-directed 2026-09-26).
- Default serious/routine helper: `openai/gpt-5.6-terra` for file-writing implementation helpers, validator/script edits, PM implementation jobs, research, review, and tool-heavy proof work.
- Cron helper posture: keep deterministic command jobs model-free. Proven narrow `agentTurn` proof/digest/status jobs may use an approved bounded helper at low reasoning through exact patch packets and canaries. Tool-heavy, authority-sensitive, code-changing, or finance false-green-sensitive cron jobs use an approved bounded helper route; main-session judgment events remain on the live Main model.
- Fallback posture (2026-09-26): Main primary is `anthropic/claude-opus-5-5` (Opus 5.5); Main's ordered fallback chain is `ollama-cloud/glm-5.3:cloud` then `ollama-cloud/kimi-k3:cloud`. **No GPT/OpenAI model may sit in any fallback position.** Opus 5 remains Main-spawn advisory only and is not in the chain.
- Ollama Cloud: GLM-5.2, Kimi K2.7 Code, MiniMax M3, and DeepSeek V4 Pro are draft/scaffold/challenge helpers until path-specific tool-loop proof expands their role.
- Claude/Gemini: manual or special challenger lanes only unless the active routing skill and exact provider skill authorize a narrower use.

## Historical Note

Earlier May 2026 language in this file defaulted substantial spawned OpenClaw sub-sessions to a GPT-5.5-style high-thinking worker posture and kept Claude/Gemini routing in this playbook. That is superseded by the 2026-06-20 consolidation.

Reason for consolidation: model routing changed from one static "best helper" default into a resource-aware matrix across GPT-5.5, GPT-5.4, GPT-5.4-mini, Ollama Cloud draft/challenge lanes, and selective Claude/Gemini challengers. Keeping those rules in several docs created contradictory defaults.

## Durable Rule

Scale productivity by splitting lanes deliberately:

- OpenClaw main = truth surface, orchestration, QC, final integration.
- GPT-5.6 Terra helpers = default serious and routine implementation, research, review, and reliable tool/write work.
- GPT-5.6 Luna cron helpers = proven deterministic proof, digest, ledger, packet, and status `agentTurn` jobs at low reasoning; model-free command jobs stay model-free.
- Opus 5.5 = Main primary (2026-09-26); fallbacks Ollama Cloud GLM 5.3 then Ollama Cloud Kimi K3; no GPT/OpenAI model in any fallback position.
- Ollama helpers = untrusted draft, scaffold, formatting, long-context digestion, and challenge lanes until smoke proof expands trust.
- Special challenger lanes = deliberate escalation only when the work benefits from the extra cost or provider-specific judgment.

More models only help if routing discipline stays stronger than model enthusiasm.

## Boundaries

No helper model, cron model, or challenger lane may infer:

- capital deployment approval
- paper/live order approval
- account, brokerage, credential, or money-movement authority
- portfolio/canon mutation authority
- cron schedule mutation authority
- customer/public output approval
- final queue movement or final closeout authority

Generated/helper output remains evidence until Veritas main verifies it against live files, source artifacts, validators, and owner surfaces.
