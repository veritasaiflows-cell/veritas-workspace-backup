# Skill Consolidation Matrix - 2026-07-02

## Conclusion

The skill layer is not broken, but it is over-expanded. Current posture should be: keep the core operating and finance skills, merge or retire narrow bridge skills only after their behavior is absorbed by stronger owners, and do not add external skills or new local skills until overlap pressure drops.

Recommended state after the 2026-07-03 refresh, approved first five cleanup applies, and implementation-friction review: 36 keep, 3 merge candidates, 4 review, 6 deprecated.

This matrix started as a review and routing artifact. Later 2026-07-03 apply passes changed only the owner-approved Skill Workshop proposal targets listed below; the matrix itself remains non-authority for future applies, merges, external installs, finance action, or destructive cleanup.

2026-07-03 refresh note: live workspace skill count is now 49. This refresh adds `ai-drop-service-os-contract` and `veritas-isolated-agent-contract`, keeps the matrix review-only, records then-pending proposal `veritas-model-routing-helper-lanes-20260703-c4c204e344` as the narrow proof-tier blocker repair, and records then-pending proposal `ai-drop-service-os-contract-20260703-d2cc69b655` as the AI Drop-Service path-truth repair. No live skill body was changed by the refresh itself.

2026-07-03 apply note: Randall approved proceeding with the recommendations. Applied Skill Workshop proposals `veritas-model-routing-helper-lanes-20260703-c4c204e344`, `ai-drop-service-os-contract-20260703-d2cc69b655`, and `workspace-governor-20260703-f4679d312b`. Post-apply proof: `skill_core_proof_tier_audit.py --write --validate` is ok with 13 of 13 core skills Tier 2-ready and 0 blocked; `skill_workshop_body_guard.py --write --validate` is ok with 49 live skills and 0 live errors/warnings; `openclaw skills check --json` is ok with 102 total, 64 model-visible, 63 command-visible, and 0 missing requirements.

2026-07-03 first cleanup apply note: Randall approved applying the first controlled cleanup pair. Applied Skill Workshop proposals `workspace-qa-pass-20260703-8e2d8b41b2` and `code-review-auditor-20260703-d87cfb4504`. `workspace-qa-pass` now owns the code/diff review doctrine; `code-review-auditor` is a deprecated compatibility router. Counts are now 36 keep, 7 merge candidates, 4 review, and 2 deprecated.

2026-07-03 second cleanup apply note: Randall approved applying the second controlled cleanup pair. Applied Skill Workshop proposals `disciplined-implementation-20260703-46aca25874` and `safe-refactor-planner-20260703-95533d97ad`. `disciplined-implementation` now owns refactor/parity doctrine; `safe-refactor-planner` is a deprecated compatibility router. Counts are now 36 keep, 6 merge candidates, 4 review, and 3 deprecated.

2026-07-03 third cleanup apply note: Randall approved applying the third controlled cleanup pair plus trigger repair. Applied Skill Workshop proposals `disciplined-implementation-20260703-f3a8e88a3c`, `workspace-governor-20260703-fff7edafee`, and `operating-procedure-repository-manager-20260703-2167738d49`. `disciplined-implementation` regained its broad trigger description, `workspace-governor` now owns operating-procedure repository placement and SOP-sprawl doctrine, and `operating-procedure-repository-manager` is a deprecated compatibility router. Counts are now 36 keep, 5 merge candidates, 4 review, and 4 deprecated.

2026-07-03 fourth cleanup apply note: Randall approved applying the fourth controlled cleanup pair. Applied Skill Workshop proposals `veritas-intelligence-effort-router-20260703-063cb12fbd` and `opportunity-recommendation-review-router-20260703-3e3da0d597`. `veritas-intelligence-effort-router` now owns practical opportunity/recommendation next-action routing, `veritas-response-contract` remains the response-facing recommendation and authority-boundary owner, and `opportunity-recommendation-review-router` is a deprecated compatibility router. Counts are now 36 keep, 4 merge candidates, 4 review, and 5 deprecated.

2026-07-03 fifth cleanup apply note: Randall approved applying the fifth controlled cleanup pair. Applied Skill Workshop proposals `project-continuity-manager-20260703-29d58ea891` and `main-session-handoff-finisher-20260703-aa7433c335`. `project-continuity-manager` now owns resumable handoff/pickup state, `cron-automation-manager` remains the cron blocker/schedule-boundary owner, `veritas-response-contract` remains the response closeout and blocker-wording owner, and `main-session-handoff-finisher` is a deprecated compatibility router. Counts are now 36 keep, 3 merge candidates, 4 review, and 6 deprecated.

2026-07-03 implementation-friction review note: reviewed `implementation-friction-closeout` -> `disciplined-implementation` and deferred consolidation. Current body-guard proof is clean, and the canonical technical guard now lives in `scripts/skill_workshop_body_guard.py`, its tests, changed-file routing, and implementation release contracts. Still, the recent June body-replacement repairs and the July Skill Workshop Windows `EPERM` retry mean the standalone human trigger remains useful. No Skill Workshop proposal was created or applied; counts remain 36 keep, 3 merge candidates, 4 review, and 6 deprecated.

## Scope

Reviewed the 49 live workspace skill bodies listed under `skills/*/SKILL.md`, the current `Skills Governance Index`, and the P0 cleanup proof from 2026-07-02.

Out of scope:

- no new skills
- no direct manual skill-body edits; skill changes are allowed only through separately approved Skill Workshop applies recorded above
- no live Skill Workshop apply/reject/quarantine actions
- no external skill installs
- no archive/delete/destructive cleanup
- no finance canon, portfolio, capital, paper/live/account, config/runtime, or external-delivery action

## Decision Labels

- `Keep`: retain as a live workspace skill.
- `Merge candidate`: keep for now, but migrate doctrine into a stronger owner after proof shows the thinner skill no longer earns its own slot.
- `Review`: keep active for now, but require usage/proof review before expansion or long-term retention.
- `Deprecated`: do not use except for the narrow fallback posture already defined.

## Consolidation Matrix

| Skill | Decision | Owner cluster | Reason | Next action |
|---|---|---|---|---|
| ai-drop-service-os-contract | Keep | Product/service OS | Useful AI drop-service operating contract. The 2026-07-03 path-truth repair corrected isolated-agent topology examples so they reference explicit `agents.list[].workspace` / `agentDir` configuration instead of implying fixed `~/.openclaw/workspaces/` discovery. | Keep; review after the first real AI Drop-Service isolated-agent rollout proves the operating contract earns a separate skill slot. |
| automation-hardening-manager | Keep | Automation governance | Owns autonomy levels, trust gates, OTEL/PM proof boundaries, and card-authority audits. | Promote proof tier with targeted automation-boundary checks. |
| bash-compatibility | Keep | Runtime compatibility | Useful opt-in compatibility lane for Bash/WSL/POSIX translation while PowerShell remains default. | Keep lightweight; review only if native Windows posture changes. |
| code-review-auditor | Deprecated | QA/review compatibility | First cleanup pair applied 2026-07-03. Useful code-review doctrine now lives in `workspace-qa-pass`; this skill is retained only as a compatibility router while reference residue drains. | Do not expand. Do not delete until active references are clean and Randall separately approves removal. |
| cron-automation-manager | Keep | Cron/control plane | Canonical owner for cron design, blocked signals, cadence gates, and schedule authority boundaries. | Keep; target Tier 2 proof promotion for cron safety gates. |
| disciplined-implementation | Keep | Implementation | Primary implementation contract, release-closeout owner, and refactor/parity owner after the 2026-07-03 second cleanup apply. | Keep as central owner for implementation, refactor planning, write leasing, parity proof, and release closeout. |
| ic-swarm-orchestrator | Review | Helper/challenger lanes | Still useful for verified Opus/challenger proof, but external-lane assumptions need periodic validation. | Review model-path proof and usage frequency before expanding. |
| implementation-friction-closeout | Merge candidate | Implementation cleanup | Exists because repeated Skill Workshop/body-replacement friction was real. 2026-07-03 review found the deterministic guard is now in scripts/release proof, but recent body-replacement and `EPERM` apply incidents still justify a separate human-facing hazard trigger. | Keep separate until at least two future Skill Workshop apply lanes complete with full-body prechecks, one-at-a-time apply, post-apply live readback, clean body-guard proof, and no `EPERM`, body-shrink, or manual repair incident; then merge into `disciplined-implementation`. |
| main-session-handoff-finisher | Deprecated | Handoff compatibility | Fifth cleanup pair applied 2026-07-03. Resumable handoff/pickup state now lives in `project-continuity-manager`, cron blocker/schedule boundaries remain in `cron-automation-manager`, and response closeout/blocker wording remains in `veritas-response-contract`. This skill is retained only as a compatibility router while reference residue drains. | Do not expand. Do not delete/archive until active references are clean and Randall separately approves removal. |
| memory-continuity-manager | Keep | Memory/continuity | Owns daily vs durable memory routing and compaction continuity. | Keep; add proof-tier upgrade later for duplicate-heading/durable-promotion checks. |
| obsidian | Keep | Note tooling | Narrow tool skill for Obsidian/plain-Markdown work. | Keep opt-in; do not expand into canonical finance ownership. |
| openclaw-operator | Keep | Runtime/operator | Owns shallow status, operator stop lines, and runtime hygiene. | Keep; promote proof around cached status and lane-register safety. |
| openclaw-troubleshooter | Keep | Runtime troubleshooting | Distinct runtime/config troubleshooting owner. | Keep; review if operator skill absorbs troubleshooting flows. |
| operating-procedure-repository-manager | Deprecated | Procedure governance compatibility | Third cleanup pair applied 2026-07-03. Procedure repository placement and SOP-sprawl doctrine now live in `workspace-governor`; this skill is retained only as a compatibility router while reference residue drains. | Do not expand. Do not delete/archive until active references are clean and Randall separately approves removal. |
| opportunity-recommendation-review-router | Deprecated | Finance routing compatibility | Fourth cleanup pair applied 2026-07-03. Practical opportunity/recommendation next-action routing now lives in `veritas-intelligence-effort-router`, and response-facing recommendation, blocker, approval-card, and authority-boundary doctrine remains in `veritas-response-contract`. This skill is retained only as a compatibility router while reference residue drains. | Do not expand. Do not delete/archive until active references are clean and Randall separately approves removal. |
| otel-operations-analyst | Keep | OTEL operations | New but clear owner for local OTEL status, drift, and privacy-safe ops recommendations. | Keep; upgrade after several clean OTEL digest/recommendation cycles. |
| privacy-safe-telemetry-expansion | Merge candidate | OTEL governance | Owner-gated telemetry expansion is important but could become a section inside OTEL operations once first expansion plan is settled. | Keep until metadata-depth proposal path is proven, then merge into `otel-operations-analyst` or `automation-hardening-manager`. |
| project-continuity-manager | Keep | Project continuity | Owns non-workflow project pickup state and avoids bloated PM sprawl. | Keep; pair with memory manager and handoff finisher merge plan. |
| safe-refactor-planner | Deprecated | Implementation/refactor compatibility | Second cleanup pair applied 2026-07-03. Refactor planning and parity doctrine now live in `disciplined-implementation`; this skill is retained only as a compatibility router while reference residue drains. | Do not expand. Do not delete until active references are clean and Randall separately approves removal. |
| sec | Review | External evidence | Valuable official SEC evidence skill, but local `.venv` footprint and dependency posture require separate review. | Run P2 reference-reviewed `.venv` plan; do not move/delete without approval. |
| smb-workflow-automation-operator | Keep | SMB/Product | Distinct SMB Workflow Clarity owner; keeps service/customer safety out of finance skills. | Keep while SMB lane remains active or resumable. |
| sqlite | Keep | Data/runtime | Focused SQLite correctness skill with low overlap and high utility. | Keep; consider Tier 2 proof around concurrency/pragma patterns. |
| task-intake-contract | Keep | Task intake | New compact front door for material/high-risk task framing. | Keep; review after several weeks to ensure it does not add ceremony to tiny tasks. |
| technical-chart-pass | Deprecated | Legacy technical fallback | Already deprecated; canonical technical work belongs to `veritas-technical-pass`. | Keep only as deprecated fallback; do not expand. |
| veritas-bounded-portfolio-agent | Keep | Finance/portfolio governance | Owns bounded workspace portfolio/canon proposal and approved maintenance paths without trade authority. | Keep; proof-promote because authority boundary is high consequence. |
| veritas-entry-policy-opportunity-surface | Merge candidate | Finance technical/routing | Narrow visibility router may be better as a section in technical or response doctrine. | Keep short term; merge into `veritas-technical-pass` and `veritas-response-contract` if no separate repeated friction appears. |
| veritas-financial-planning-pass | Keep | Finance planning | Distinct holistic planner/advisor synthesis owner. | Keep; do not scatter planner constraints across all finance skills. |
| veritas-fundamental-pass | Keep | Finance fundamentals | Canonical fundamentals pass; SQL-first/source-open fallback is core. | Keep; proof-promote with current evidence/source freshness checks. |
| veritas-intelligence-effort-router | Keep | Cross-skill routing | Central effort-band dispatcher across finance, PM, workflow, macro, cron, implementation, and practical opportunity/recommendation next-action routing after the fourth cleanup apply. | Keep; merge smaller routing skills into this over time. |
| veritas-investment-deck | Review | Finance packaging | Useful packaging skill, but lower-frequency than core finance passes. | Review usage frequency; merge with `veritas-pdf-brief` if deck work is mostly fixed-layout packaging. |
| veritas-isolated-agent-contract | Keep | Isolated-agent governance | Canonical owner for persistent isolated agents vs sub-agents, explicit workspace/agentDir path truth, auth/sandbox/tool boundaries, bootstrap packets, capability manifests, and no-second-authority rules. | Keep; use it as the path-truth owner when correcting AI Drop-Service OS or future multi-agent topology guidance. |
| veritas-macro-pass | Keep | Finance macro | Distinct macro regime owner. | Keep; proof-promote with macro spine freshness validation. |
| veritas-model-routing-helper-lanes | Keep | Model/helper routing | Canonical model, helper, challenger, cron, and fallback routing owner. | Keep; validate provider assumptions regularly. |
| veritas-os2-cleanup-router | Review | Cleanup/WF88 | Useful while WF88 cleanup is live, but may become temporary after cleanup posture stabilizes. | Review after WF88 route-contraction and delete-readiness work settles. |
| veritas-pdf-brief | Keep | Finance/PM packaging | Owns fixed-layout PDF/Excel/brief packaging. | Keep; possible future merge target for investment-deck packaging if overlap persists. |
| veritas-pm-department | Keep | PM/product | Owns roadmaps, readiness, and PM queue framing. | Keep; ensure it does not become a second truth source for finance state. |
| veritas-portfolio-update | Keep | Finance note sync | Owns portfolio board sync and bounded maintenance visibility. | Keep; high-authority boundary requires proof promotion. |
| veritas-positioning-pass | Keep | Finance positioning | Owns macro/fundamental/technical synthesis into owner-gated positioning. | Keep; maintain explicit recommendation vs approval boundary. |
| veritas-post-earnings-sync | Keep | Finance earnings | Distinct post-earnings workflow and note-layer sync owner. | Keep; promote to stronger proof tier. |
| veritas-response-contract | Keep | User-facing response | Core response, recommendation, proof, risk, and authority-boundary contract. | Keep; centralize user-facing closeout doctrine here. |
| veritas-self-improvement | Keep | Learning loop | Owns WF74 learning-loop routing, proposals, and response-quality repair. | Keep; avoid self-modifying authority expansion. |
| veritas-technical-pass | Keep | Finance technical | Canonical technical timing, band, stop, and SQL-first technical proof owner. | Keep; absorb entry-policy visibility if that bridge proves redundant. |
| veritas-weekly-brief | Keep | Finance weekly synthesis | Distinct weekly intelligence rebuild owner. | Keep; proof-promote with weekly freshness chain. |
| veritas-wf78-tier-promotion-spine | Keep | WF78 tier routing | Owns current tier authority and non-capital funnel-spine governance. | Keep; high-value routing owner. |
| veritas-workspace-audit-orchestrator | Keep | Audit/governance | Canonical audit and targeted finding review owner. | Keep; use for future broad workspace/skill/procedure audits. |
| wf67-paper-trading-operator | Keep | Paper-trading guardrails | High-consequence paper-only preparation and guardrail owner. | Keep; proof-promote due paper/live boundary risk. |
| windows-powershell-workspace | Keep | Runtime/PowerShell | Canonical native Windows/PowerShell execution guidance. | Keep; critical to avoiding Bash/Windows drift. |
| workspace-governor | Keep | Workspace structure | Owns placement, structural residue, tmp-vs-durable, governance stop lines, operating-procedure placement, and SOP-sprawl control. | Keep as the workspace/procedure placement owner; drain old `operating-procedure-repository-manager` references over time. |
| workspace-qa-pass | Keep | QA/reconciliation | Bounded QA owner for proof, stale artifacts, claims-vs-proof, authority checks, and code/diff review after the 2026-07-03 first cleanup apply. | Keep as the code-review owner; drain old `code-review-auditor` references over time. |

## Merge Candidates

Do not merge these immediately. The live system has just had a Skill Workshop contamination incident, so stability matters more than aggressive slimming.

Priority merge watchlist:

Completed merge watchlist:

1. `code-review-auditor` -> `workspace-qa-pass` - applied; `code-review-auditor` is now deprecated compatibility.
2. `safe-refactor-planner` -> `disciplined-implementation` - applied; `safe-refactor-planner` is now deprecated compatibility.
3. `operating-procedure-repository-manager` -> `workspace-governor` - applied; `operating-procedure-repository-manager` is now deprecated compatibility.
4. `opportunity-recommendation-review-router` -> `veritas-intelligence-effort-router` plus `veritas-response-contract` - applied; `opportunity-recommendation-review-router` is now deprecated compatibility.
5. `main-session-handoff-finisher` -> `project-continuity-manager`, `cron-automation-manager`, and `veritas-response-contract` - applied; `main-session-handoff-finisher` is now deprecated compatibility.

Remaining priority merge watchlist:

1. `implementation-friction-closeout` -> `disciplined-implementation` only after at least two future Skill Workshop apply lanes prove clean full-body apply behavior with no body-guard, `EPERM`, body-shrink, or manual repair incident
2. `privacy-safe-telemetry-expansion` -> `otel-operations-analyst` or `automation-hardening-manager` after the first owner-gated metadata-depth proposal path is proven
3. `veritas-entry-policy-opportunity-surface` -> `veritas-technical-pass` plus `veritas-response-contract` if it remains only visibility routing

## Review Watchlist

- `sec`: keep active, but run the P2 `.venv` reference-reviewed cleanup plan separately before changing footprint or dependency placement.
- `ic-swarm-orchestrator`: keep only if verified challenger-lane proof remains useful and current.
- `veritas-investment-deck`: review whether it earns a separate skill or should become a packaging section under `veritas-pdf-brief`.
- `veritas-os2-cleanup-router`: review after WF88 cleanup/route-contraction stabilizes.

## Recommendations

P1A - No bulk merge apply. Keep the matrix as guidance and handle one cleanup pair at a time.

2026-07-03 P1A status: first five merge candidate lanes were applied cleanly. `code-review-auditor`, `safe-refactor-planner`, `operating-procedure-repository-manager`, `opportunity-recommendation-review-router`, and `main-session-handoff-finisher` are now deprecated compatibility routers, with owner doctrine absorbed into `workspace-qa-pass`, `disciplined-implementation`, `workspace-governor`, `veritas-intelligence-effort-router`, `project-continuity-manager`, `cron-automation-manager`, and `veritas-response-contract`. Counts are 36 keep, 3 merge candidates, 4 review, and 6 deprecated.

2026-07-03 P1A fourth cleanup update: Randall approved and applied `veritas-intelligence-effort-router-20260703-063cb12fbd` and `opportunity-recommendation-review-router-20260703-3e3da0d597`; no delete, archive, finance/canon/portfolio mutation, paper/live/account action, config/runtime/channel mutation, or external delivery was performed.

2026-07-03 P1A fifth cleanup update: Randall approved and applied `project-continuity-manager-20260703-29d58ea891` and `main-session-handoff-finisher-20260703-aa7433c335`; no delete, archive, finance/canon/portfolio mutation, paper/live/account action, config/runtime/channel mutation, or external delivery was performed. Keep deprecated routers in place until residue scans are clean and delete/archive/removal is separately approved.

P1B - Add a future consolidation gate: a merge candidate can be retired only after the target owner skill explicitly contains the needed doctrine, `openclaw skills check` and body guard pass, and a wrapper-residue scan is clean.

P1C - Promote proof tiers before slimming core finance/runtime skills. Highest priority proof upgrades: `task-intake-contract`, `disciplined-implementation`, `workspace-qa-pass`, `veritas-response-contract`, `cron-automation-manager`, `openclaw-operator`, `veritas-model-routing-helper-lanes`, `veritas-intelligence-effort-router`, `wf67-paper-trading-operator`, `veritas-fundamental-pass`, `veritas-technical-pass`, `veritas-positioning-pass`, and `veritas-bounded-portfolio-agent`.

Current P1C status after the approved apply: `python scripts\skill_core_proof_tier_audit.py --write --validate` is clean. `veritas-model-routing-helper-lanes` now includes the required `NO_REPLY` and exact finance-boundary anchors.

P1D - Keep the no-skill-sprawl rule active. New local skills should require explicit governance justification and a clear owner gap that cannot be solved by tightening an existing skill.

P1E - Keep external skill installs blocked by default. External skills may be pattern sources only until security/governance review approves installation.

## Stop Lines

This matrix does not authorize:

- skill-body edits
- Skill Workshop apply/reject/quarantine actions
- external skill installation
- archive/delete/move cleanup
- `skills/sec/.venv` deletion or relocation
- finance canon, portfolio, capital, paper/live/account, brokerage, config/runtime, credential, channel, startup, service, or external-delivery mutation

## Acceptance Proof For Future Consolidation

Before any merge/deprecate action:

1. Identify exact source skill and target owner skill.
2. Verify target owner already covers required doctrine or create a Skill Workshop proposal.
3. Apply only after Randall explicitly approves the specific proposal.
4. Run `openclaw skills check --json`.
5. Run `python scripts\skill_workshop_body_guard.py --write --validate`.
6. Run an explicit wrapper-residue scan under `skills/`.
7. Compare live `skills/*` directories against this matrix and update or supersede the matrix if rows drift.
8. Update `06. Playbooks\Skills Governance Index.md` and daily memory.
