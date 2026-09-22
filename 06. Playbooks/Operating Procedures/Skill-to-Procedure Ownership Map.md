# Skill-to-Procedure Ownership Map

## Purpose
Show where a human operator should look first when a workspace skill exists, and prevent skills from becoming detached from the operating docs they rely on.

## Map

| Skill | Primary procedure / protocol surface | Owns directly | Operator should open first when... |
|---|---|---|---|
| `cron-automation-manager` | `06. Playbooks/Cron Job Protocol.md` | scheduled workflow design and cron trust posture | the question is whether something should be scheduled or how a cron job should be shaped |
| `disciplined-implementation` | Micro/Narrow: the skill itself plus the owning file/workflow note. Major: `06. Playbooks/Major Workflow Contract Standard.md`. Helper lanes: `06. Playbooks/Spawn and Closeout Governance Matrix.md` + `06. Playbooks/Subagent Spawn Handoff Template.md` | bounded implementation size-classing, proof discipline, and reuse/flattening gate | a script, validator, manifest, or workflow implementation change is needed |
| `openclaw-operator` | `06. Playbooks/Operating Model.md` and core operator playbooks | runtime/operator maintenance work | the issue is core workspace/runtime operation |
| `openclaw-troubleshooter` | operator/runtime doctrine plus targeted troubleshooting notes; upstream handoff via `06. Playbooks/Operating Procedures/Upstream Escalation and Community Contribution Procedure.md` | diagnosis of broken runtime/config/skill behavior | something is broken or inconsistent |
| `memory-continuity-manager` | `Continuity Protocol.md` and `HEARTBEAT.md` | continuity logging and promotion routing | continuity, memory, or daily-note routing is the task |
| `project-continuity-manager` | project continuity notes under `06. Playbooks/Project Continuity/` | project handoff / resume structure | an active project needs a cleaner pickup point |
| `workspace-governor` | `06. Playbooks/Workspace Structure Protocol.md`, `06. Playbooks/Notes Layer Governance Protocol.md`, `06. Playbooks/Operating Procedures/README.md`, `Procedure Index.md`, and `Procedure Classification Rubric.md` | workspace organization, note/procedure placement, procedure classification, repository indexing, and SOP-sprawl control | the question is where something belongs, whether the workspace is drifting, or whether repeated operator work should become an operating procedure |
| `veritas-intelligence-effort-router` | `06. Playbooks/Operating Procedures/Portfolio Truth Surface Ownership Procedure.md` | alert/recommendation evidence and surface-disagreement routing; `veritas-response-contract` owns user-facing recommendation and authority wording | alert/recommendation canon, generated proof, dashboard, or continuity surface disagrees |
| `workspace-qa-pass` | owning workflow note plus relevant governance standards | bounded QA audit work | a workspace hardening pass needs independent QA |
| `ic-swarm-orchestrator` | `06. Playbooks/OpenClaw Parallel Work Plan.md` and `06. Playbooks/Spawn and Closeout Governance Matrix.md` | multi-lane orchestration posture | the task needs staged or parallel helper lanes |
| `SQLite` | `06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md` and `06. Playbooks/Project Continuity/Workflow 36 - Workspace Retrieval Index and SQLite Knowledge Layer.md` | SQLite query correctness and local DB inspection design | SQL is being used for retrieval, artifact lookup, or derived cache inspection |

## Rule
When a skill and a procedure both exist:
- the procedure explains the operator path
- the skill explains the assistant execution path
- neither should silently contradict the other

## Stop line
If a skill has no clear procedure / protocol anchor and it is not purely execution-local, tighten the map before widening the skill.
