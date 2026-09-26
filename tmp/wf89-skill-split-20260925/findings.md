# WF89 skill-copy split: findings and recommendations (2026-09-25 evening)

Randall 18:12 MST: "How did the skill workshop failure happen? ... Continue to use our isolated agents to investigate, plan, and provide a summary of your findings and recommendations."

## Route (Delegation Decision reasons)

| Helper | Reason | Path | Tokens (fresh / total) | Time | Credit |
|---|---|---|---|---|---|
| research-scout | real web research (docs.openclaw.ai, GitHub) | sessions_spawn, isolated, keep | 145,367 / 1,017,047 | 60 s | CREDITABLE |
| qa-redteam #1 | independent review: 12 skill diffs | CLI + dispatch record d0adeeb5 | 52,608 / 123,840 | 61 s | CREDITABLE |
| qa-redteam #2 | independent review: 17 Workshop-only files | CLI + dispatch record 5c4909a1 | 32,468 / 86,612 | 52 s | CREDITABLE |

Inputs to qa-redteam were staged in its workspace (`workspaces/qa-redteam/inbox/skill-split-20260925/`) because both helpers are `fs.workspaceOnly`; the bundle was split in two to respect the 120 KB handoff cap. Main timeline work: Workshop applied-proposal list, collection-review history, the reviewer's `COLLECTION-REVIEW.md` log, installed docs.

## How it happened (verified)

1. **OpenClaw design, working as documented.** Workspace `skills/` is load priority 1 and the agent's Workshop directory is priority 5; the highest source wins (installed `docs/tools/skills.md`, Loading order). Skill Workshop writes only inside `agents/<id>/agent/workshop-skills` and "Skills from other sources are never changed" (`docs/tools/skill-workshop/how-it-works.md`). The weekly collection reviewer edits that directory directly when `skills.workshop.autonomous.mode` is `auto` (the default; ours is unset). The installed docs describe no shadow warning and no adopt/publish step.
2. **Two writers, no sync.** 12 skills exist in both places. Workshop-side writers: owner-approved proposal applies and the autonomous reviewer (dozens of dated deltas 09-15..09-24 in `COLLECTION-REVIEW.md`, e.g. `route-cache-reuse-review.md`, `route-change.md`, `policy-reconciliation.md` on 09-19). Workspace-side writer: Main editing the loaded copies directly under the repository-source exception (09-19, 09-22, 09-25).
3. **The warning existed but nobody saw it.** Every reviewer delta ends "live workspace skill publication remains outside this directory and requires a separate approved apply or operator edit". The 09-19 delta states that Main's direct edits made "the Workshop copies and the live copies now differ". It lives in a 455 KB file no check or alert reads.
4. **Our checks never compared the copies.** No validator or cron looked for shadowed divergence until this audit.

Correction to the premise: the Workshop copy is not uniformly the latest. It holds newer procedure for most skills, but the loaded copies hold some owner-approved content the Workshop lacks.

## What qa-redteam found, after Main verification

- Direction per skill (qa-redteam #1): WORKSHOP for 8 (agi-harness-readiness-operator, otel-operations-analyst, privacy-safe-telemetry-expansion, task-intake-contract, veritas-entry-policy-opportunity-surface, veritas-intelligence-effort-router, veritas-os2-cleanup-router, veritas-workspace-audit-orchestrator); MERGE for 3 (ai-drop-service-os-contract, veritas-isolated-agent-contract, veritas-model-routing-helper-lanes); veritas-prompt-book-operator WORKSHOP but HIGH risk (changes duplicate-proposal handling).
- Workshop-only files (qa-redteam #2): 16 ADOPT, 1 ADOPT-WITH-FIXES (split the 29.8 KB `automation-recovery-proof.md`); none weakens an approval or safety gate. Adopt the 5 routing references as a set (they link to each other).
- **Main verification:**
  - Confirmed stale in the loaded copy: the ai-drop roster lists `openai/gpt-5.6-terra` for research-scout, finance-source-scout and finance-redteam. Live primaries differ, and `agent_fleet_policy.LEGACY_DENIED_MODELS` now denies Terra.
  - Confirmed stale: "Ollama Cloud GLM 5.3 is the last-resort chain entry." Live Main fallbacks put it second of four.
  - **qa-redteam was wrong on one of its top-3 conflicts:** "Grok 4.6 remains an approved Main-selected recovery candidate" is TRUE. `SPECIALIST_RECOVERY` lists `xai/grok-4.6` for qa-redteam, finance-redteam and finance-source-scout. Main's live-facts sheet omitted the recovery lists. The Workshop copy drops this correct sentence.
  - Missed by qa-redteam: the Workshop routing copy says Codex-native is "fail-closed while OpenAI quota is exhausted" (no such outage today). The loaded copy says Codex-native uses "Terra low", and Terra is now a denied model. Both are stale.
  - Confirmed: the `SPECIALIST_PRIMARY`, `SPECIALIST_RECOVERY` and `LEGACY_DENIED_MODELS` constants the routing references rely on exist.
  - Not verified: research-scout's GitHub item numbers (PR #100310 shadow warnings, open; issue #125711 adopt/disown, open; PR #125666 merged ownership gating). Treat them as leads.

## Recommendations

1. **Merge now into the loaded (workspace) copies**, which are git-tracked and actually used. Take the Workshop version for the 8 LOW/MEDIUM skills. Main hand-merges the 4 HIGH ones, fixing stale claims on both sides against live policy. Adopt the 17 files, routing set first. Owner approval required (doctrine change). qa-redteam re-reviews the merged diff.
2. **Daily model-free shadow check** (like the grant check): list every skill whose Workshop copy differs from the loaded copy and alert only on a new divergence, so reviewer output reaches Main within a day. New cron; owner approval required.
3. **Sync the Workshop copies back** after the merge, through Skill Workshop update proposals (Randall applies), so the reviewer works from the truth instead of re-deriving from a stale base.
4. **Keep autonomous mode `auto`.** qa-redteam rated 16 of 17 unloaded procedures worth adopting. The failure was publication, not the reviewer. Revisit if the shadow check shows it creating churn.
5. **Main rule change:** after any edit to a loaded skill that also has a Workshop copy, stage the matching Workshop update the same day (memory: openclaw-skill-active-copy-check).
