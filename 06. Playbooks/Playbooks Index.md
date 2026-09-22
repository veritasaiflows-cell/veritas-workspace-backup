# Playbooks Index

## Purpose

Use this note as the fast retrieval map for `06. Playbooks/`.

This is the operator index.
It exists so the right control surface can be found without scanning the whole playbooks root.

## Fast path by job

| If you need to... | Open this first | Then check |
|---|---|---|
| run or close a major workflow | `06. Playbooks/Major Workflow Contract Standard.md` | `06. Playbooks/Spawn and Closeout Governance Matrix.md`, `06. Playbooks/Workflow Closeout Artifact Standard.md` |
| see the live workflow queue | `06. Playbooks/OpenClaw Parallel Pilot Queue.md` | `06. Playbooks/IC Project Registry.md`, `06. Playbooks/OpenClaw Parallel Pilot Queue - History.md` |
| decide whether work should stay manual, use cron, or use helper lanes | `06. Playbooks/Automation Orchestration Protocol.md` | `06. Playbooks/Cron Job Protocol.md`, `06. Playbooks/OpenClaw Parallel Work Plan.md` |
| review scheduled automation proof | `06. Playbooks/Cron Run Ledger.md` | `06. Playbooks/Automation Run Summary Contract.md` |
| inspect research-automation boundaries | `06. Playbooks/Research Automation Intake Packet Contract.md` | the other `Research Automation *.md` contract notes |
| use SQL/SQLite retrieval without canon-shadowing | `06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md` | `06. Playbooks/Project Continuity/Workflow 36 - Workspace Retrieval Index and SQLite Knowledge Layer.md`, `scripts/README.md` |
| add retrieval/status/archive metadata to major notes | `06. Playbooks/Operating Procedures/Retrieval Metadata and Notes Field Standard.md` | `06. Playbooks/Workspace Structure Protocol.md`, `skills/workspace-governor/references/workspace-standards.md` |
| recover after OpenClaw reinstall/update/restart | `06. Playbooks/Operating Procedures/OpenClaw Reinstall Recovery Checklist.md` | `skills/openclaw-troubleshooter/SKILL.md`, `TOOLS.md` |
| escalate a verified local OpenClaw finding upstream | `06. Playbooks/Operating Procedures/Upstream Escalation and Community Contribution Procedure.md` | `06. Playbooks/Project Continuity/Upstream Escalation Register.md`, `skills/openclaw-troubleshooter/SKILL.md` |
| inspect finance alert evidence, freshness, and recommendation review posture | `03. Alerts and Recommendations/Alert Operations Board.md` | `03. Alerts and Recommendations/Alert Trigger Policy.md`, `06. Playbooks/Deployment Readiness Helper Packet Contract.md` (retitled alert-evidence replacement) |
| understand parallel-lane / IC posture | `06. Playbooks/Independent Contractor Workflow.md` | `06. Playbooks/OpenClaw Parallel Work Plan.md`, `06. Playbooks/OpenClaw Model Deployment Plan.md`, `06. Playbooks/IC Model Routing Policy.md` |
| govern reusable prompts and internal challenge-solving loops | `06. Playbooks/Veritas Prompt Book.md` | `06. Playbooks/Model Prompt Operations.md`, `tmp/prompt-book-registry.json`, `tmp/prompt-book-eval-gap-packet.json` |
| launch a bounded OpenClaw subagent | `06. Playbooks/Subagent Spawn Handoff Template.md` | `06. Playbooks/Spawn and Closeout Governance Matrix.md`, `06. Playbooks/OpenClaw Parallel Work Plan.md` |
| inspect workbook / PDF packaging rules | `06. Playbooks/Workbook Export Contracts.md` | `06. Playbooks/Excel Operating Workbook Structure.md`, `06. Playbooks/PDF Brief Standards.md`, `06. Playbooks/Minimum-Viable Workbook Schema.md` |
| audit skills / workflow-driving standards | `06. Playbooks/Skills Governance Index.md` | `06. Playbooks/Skill Quality Standard.md` |

## Current operator control surfaces

- `06. Playbooks/OpenClaw Parallel Pilot Queue.md` - live active queue and next approved work
- `06. Playbooks/OpenClaw Parallel Pilot Queue - History.md` - detailed historical workflow ledger preserved after queue compaction
- `06. Playbooks/IC Project Registry.md` - active/recent project control board
- `06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md` - operator procedure for SQL retrieval use, proof, and stop lines
- `06. Playbooks/Operating Procedures/Retrieval Metadata and Notes Field Standard.md` - lightweight metadata block for audits, workflows, research notes, and archive posture
- `06. Playbooks/Operating Procedures/OpenClaw Reinstall Recovery Checklist.md` - return-to-service checklist after reinstall/update/restart
- `06. Playbooks/Operating Procedures/Upstream Escalation and Community Contribution Procedure.md` - turn a verified local finding into an upstream issue; duplicate-check, severity frame, stop lines
- `06. Playbooks/Project Continuity/Upstream Escalation Register.md` - tracking surface for filed upstream issues and closed-by-upstream predecessor work
- `06. Playbooks/Automation Orchestration Protocol.md` - orchestration, categorization, status, and queue-movement rules
- `06. Playbooks/Cron Run Ledger.md` - proof surface for live scheduled windows
- `06. Playbooks/Workspace Structure Protocol.md` - root structure and folder-boundary rules

## Workflow / governance standards

- `06. Playbooks/Major Workflow Contract Standard.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
- `06. Playbooks/Workflow Closeout Artifact Standard.md`
- `06. Playbooks/Skill Quality Standard.md`
- `06. Playbooks/Skills Governance Index.md`

## Automation / cadence

- `06. Playbooks/Automation Architecture Spec.md`
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Continuity Stewardship Protocol.md`
- `06. Playbooks/Automation Run Summary Contract.md`
- `06. Playbooks/Cron Run Ledger.md`

## Research automation and human-gated review contracts

- `06. Playbooks/Research Automation Source Bundle Contract.md`
- `06. Playbooks/Research Automation Intake Packet Contract.md`
- `06. Playbooks/Research Automation Routing and Promotion Contract.md`
- `06. Playbooks/Research Automation Canonical Freshness Patch Contract.md`
- `06. Playbooks/External Research Intake Workflow.md`
- `06. Playbooks/Research Unit Concept.md`

## Parallel lanes / model routing / IC operations

- `06. Playbooks/Independent Contractor Workflow.md`
- `06. Playbooks/OpenClaw Parallel Work Plan.md`
- `06. Playbooks/OpenClaw Model Deployment Plan.md`
- `06. Playbooks/IC Model Routing Policy.md`
- `06. Playbooks/Subagent Spawn Handoff Template.md`
- `06. Playbooks/Claude CLI Guardrails.md`
- `06. Playbooks/Gemini CLI Guardrails.md`
- `06. Playbooks/Veritas Prompt Book.md`
- `06. Playbooks/Model Prompt Operations.md`

## Workbook / packaging / deliverables

- `06. Playbooks/Workbook Export Contracts.md`
- `06. Playbooks/Excel Operating Workbook Structure.md`
- `06. Playbooks/Minimum-Viable Workbook Schema.md`
- `06. Playbooks/PDF Brief Standards.md`
- `06. Playbooks/Weekly Intelligence PDF Product Spec.md`
- `06. Playbooks/External Model Report Template.md`

## Historical and review-heavy support notes

- `06. Playbooks/Playbooks Redundancy Cleanup Plan.md`
- `06. Playbooks/OpenClaw Parallel Pilot Queue - History.md`
- `08. Audits/Playbooks Folder Review and Optimization Audit - 2026-05-03.md`
- `06. Playbooks/Project Continuity/` for workflow-specific continuity truth
- `09. Archive/Project Continuity/` for archived continuity notes

## Retrieval rule

When a playbook feels hard to find, update this index before creating another overlapping root note.
