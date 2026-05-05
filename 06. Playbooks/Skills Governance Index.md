# Skills Governance Index

## Purpose

Provide one operator-facing index for the active workspace skills so scope, posture, validation state, and deprecation triggers are visible without a full skill-by-skill audit.

## Governance fields
- **Owner**
- **Scope**
- **Model posture**
- **Validation tier**
- **Last tested**
- **Deprecation trigger**

Validation posture for this index on 2026-05-03:
- baseline validation method: `openclaw skills check`
- this is a governance/accounting surface, not proof that every skill just completed a live end-to-end workflow pass
- unless explicitly upgraded, the honest default validation posture for active skills is **Tier 1 structural**

## Active workspace skills (19 canonical)

| Skill | Owner | Scope | Model posture | Validation tier | Last tested | Deprecation trigger |
|---|---|---|---|---|---|---|
| automation-hardening-manager | Veritas workspace | automation architecture, trust gates, ownership boundaries | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | replace or merge if automation-governance contract moves fully into a newer canonical playbook/skill |
| cron-automation-manager | Veritas workspace | cron design, scheduling boundaries, overlap risk | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if cron layer changes enough that scheduling guidance becomes stale or duplicates another skill |
| ic-swarm-orchestrator | Veritas workspace | bounded multi-lane orchestration, challenge lanes, completion handshake | operator-maintained external-lane references; validate routing via protocol before use | Tier 2 functional local proof | 2026-05-04 | review if external lane posture or helper-lane governance drifts materially |
| memory-continuity-manager | Veritas workspace | daily/durable memory routing and dedupe posture | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if continuity system or daily-note contract changes materially |
| openclaw-operator | Veritas workspace | workspace/runtime/config/skill hygiene | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if runtime/operator procedures move into a new canonical operator layer |
| openclaw-troubleshooter | Veritas workspace | OpenClaw runtime/config troubleshooting | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if troubleshooting doctrine drifts from live runtime or docs |
| project-continuity-manager | Veritas workspace | thin project pickup points and continuity notes | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if project continuity standard is replaced by a stronger canonical workflow contract |
| veritas-fundamental-pass | Veritas workspace | Veritas equity fundamentals workflow | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if finance evidence standards or vault structure change materially |
| veritas-investment-deck | Veritas workspace | finance-first investment presentation workflow | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if deck workflow is superseded by a canonical packaging layer |
| veritas-macro-pass | Veritas workspace | macro regime and market context workflow | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if macro source/trust rules change materially |
| veritas-pdf-brief | Veritas workspace | finance-first PDF deliverable workflow | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if fixed-layout output flow changes materially |
| veritas-portfolio-update | Veritas workspace | portfolio board synchronization and trust-boundary handling | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if portfolio owner surfaces or sync contracts change materially |
| veritas-positioning-pass | Veritas workspace | portfolio-positioning decisions from macro/fundamental/technical inputs | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if positioning doctrine or risk rules change materially |
| veritas-post-earnings-sync | Veritas workspace | post-earnings closure workflow and note-layer sync | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | promote toward Tier 3 live-workflow proof as a priority core workflow |
| veritas-self-improvement | Veritas workspace | doctrine-aligned reflection and correction capture | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if self-improvement outputs begin overlapping continuity or operator layers excessively |
| veritas-technical-pass | Veritas workspace | canonical Veritas technical timing workflow | model-agnostic; OpenClaw defaults | Tier 2 functional local proof | 2026-05-04 | review if ownership drifts back toward deprecated legacy technical-state vocab or chart standards change materially |
| veritas-weekly-brief | Veritas workspace | weekly intelligence rebuild and synthesis workflow | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | promote toward Tier 3 live-workflow proof as a priority core workflow |
| workspace-governor | Veritas workspace | workspace structure, note placement, organization governance | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if workspace architecture or root-folder policy changes materially |
| workspace-qa-pass | Veritas workspace | bounded high-signal QA audits after meaningful changes | model-agnostic; OpenClaw defaults | Tier 1 structural | 2026-05-03 | review if QA standards drift from live control-plane or workflow contract standards |

## Deprecated legacy fallback

| Skill | Status | Current posture | Replacement |
|---|---|---|---|
| technical-chart-pass | Deprecated legacy fallback | Keep only as a narrow generic chart-read fallback; do not use for board sync, technical-sheet updates, or Veritas deployment-state work | `veritas-technical-pass` |

## Stale-model-reference rule

If a skill references:
- a specific OpenClaw model ID
- Gemini / Claude lane posture
- or any external routing assumption

that reference should be treated as **operator-maintained** unless it is validated live frequently.

Current skill with explicit operator-maintained external lane posture:
- `ic-swarm-orchestrator`

## Known governance follow-up

- `technical-chart-pass` overlap has now been resolved by deprecating it into a narrow legacy generic-fallback posture and routing canonical board work to `veritas-technical-pass`.
- Next governance focus should be validation-tier promotion for the core workflow skills rather than further overlap expansion.

## Planned Tier 2 pilot set

Workflow 29 should start with a narrow proof set instead of pretending the whole skill layer upgrades at once:
- `ic-swarm-orchestrator` -> completion-handshake proof **landed** via `scripts/swarm_completion_handshake.py` with local fail/pass verification on 2026-05-04
- `veritas-technical-pass` -> first sidecar validator pilot for a file-contract-heavy workflow skill **landed** via `scripts/veritas_technical_pass_validate.py` with local proof on 2026-05-04
- `automation-hardening-manager` + `cron-automation-manager` -> machine-readable trust-block producer/consumer pilot

## No-skill-sprawl rule

Current canonical active workspace skill count: **19**.
Deprecated legacy fallback count: **1** (`technical-chart-pass`).

Trigger a governance review when:
- the count exceeds 20
- a new skill overlaps an existing skill materially
- 3 or more skills cluster around one lane without a clear canonical owner
- a skill repeatedly needs operator explanation before use

When triggered:
1. update this index
2. classify affected skills as keep / merge / review / deprecate
3. avoid opening additional new skills until overlap is understood

## Related standards
- `06. Playbooks/Skill Quality Standard.md`
- `06. Playbooks/Major Workflow Contract Standard.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
