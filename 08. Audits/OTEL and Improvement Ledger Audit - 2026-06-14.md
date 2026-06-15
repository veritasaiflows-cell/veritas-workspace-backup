# OTEL and Improvement Ledger Audit - 2026-06-14

Generated: 2026-06-14 21:28 America/Phoenix
Reference UTC: 2026-06-15 04:28 UTC

Machine packet: `tmp/otel-improvement-ledger-audit-2026-06-14.json`

## Conclusion

Rating: B+

The OTEL and improvement-learning spine is real, useful, and mostly healthy. The collector is running locally, OTEL proof packets validate, WF74 is converting telemetry and model-quality evidence into improvement opportunities, and the improvement ledger is append-only with carry-forward flags.

The gap is not collection. The gap is enforcement: every new session must reliably refresh/read `tmp/improvement-ledger-current.json` and `tmp/future-session-enhancement-packet.json` before deciding what OS/WF74 improvements to recommend or execute. Today that route exists in the Startup Truth Index, but it still depends on agent behavior and packet freshness.

Blunt operating read: this is ready for proposal-driven autonomous improvement, not unattended auto-apply.

## Scope

Rating: A

Audited:

- live local OTEL process state
- OTEL collector config and local-only boundary
- OTEL control packets and multi-window summary
- WF74 model-quality / OTEL collection runner
- model, coding, implementation, finance, and improvement ledgers
- future-session and startup packet carry-forward path
- upgrade proposals for new-session experience and autonomous improvement

Out of scope:

- collector config mutation
- runtime/auth/channel mutation
- cron mutation
- raw prompt/response/tool payload capture
- finance canon/portfolio/cash/sizing mutation
- capital approval, paper/live execution, brokerage/account action
- Skill Workshop apply/install approval

## OTEL Processes

Rating: A-

Live process inspection found one active OTEL collector:

- `otelcol.exe`
- path: `tools\otelcol\otelcol.exe`
- process id observed: `14632`
- working set: about 24 MB
- endpoint: `127.0.0.1:4318`

Related runtime processes observed:

- OpenClaw/Node runtime processes
- transient Python helper process during audit commands

Collector config:

- owner config: `tools/otelcol/openclaw-local-otel.yaml`
- receiver: OTLP HTTP on `127.0.0.1:4318`
- pipelines: traces and metrics
- exporter: debug, basic verbosity
- no logs pipeline
- no file exporter
- no external export

The current setup is intentionally local and metadata-limited. That is the right default.

## OTEL Current State

Rating: A-

Fresh proof:

- `tmp/otel-ops-control.json`: `status=ok`, validation `ok`
- `tmp/otel-ops-window-summary.json`: `status=ok`, validation `ok`
- `tmp/otel-ops.sqlite`: refreshed
- `tmp/otel/control-loop.json`: compatibility bridge refreshed

Current 24-hour OTEL packet:

- events: `1810`
- metric batches: `1434`
- trace batches: `376`
- reported data points: `251777`
- reported spans: `1426`
- daily warning/error count: `0`
- daily vs weekly event-rate ratio: `1.5784`
- drift status: `ok`

Multi-window summary exposes five windows:

- 1 hour intraday
- 6 hour intraday
- 24 hour daily control
- 7 day weekly trend
- 30 day monthly baseline

The telemetry flow is healthy enough for operations learning. It is not evidence of model quality, investment correctness, or execution readiness by itself.

## OTEL Owner Jobs

Rating: B+

Primary owner job:

- `Ops - OTEL Local Digest`
- job id: `b911d479-13aa-48fe-b662-937e08450363`
- schedule: `40 7,15,21 * * *` America/Phoenix
- model: `openai/gpt-5.4-mini`
- thinking: `medium`
- timeout: `900`
- last observed state: `ok`
- last observed duration: about `106s`
- contract: `state/cron-contracts/ops-otel-local-digest.json`

Supporting improvement radar:

- `Runtime - Weekly OS Improvement Radar Review`
- schedule: Sunday `16:30` America/Phoenix
- session target: main
- current status: idle / not yet naturally run
- purpose: turn repeated friction into practical OS-improvement candidates

The three-times-daily OTEL digest is appropriate. The weekly improvement radar is useful but should be validated after first natural run.

## Ledgers

Rating: B+

Durable/current ledgers found:

| Ledger | Surface | Current State |
|---|---|---|
| Model run ledger | `data/state-history/model-run-ledger.jsonl`, `tmp/model-run-ledger-current.json` | 106 durable rows; current packet ok |
| Model quality scorecard | `data/state-history/model-quality-scorecard.jsonl`, `tmp/model-quality-scorecard.json` | 195 durable rows; scaffold active |
| Model learning metadata | `tmp/model-learning-metadata-ledger.json` | 615 current rows; metadata-only |
| Coding outcome ledger | `data/state-history/coding-outcome-ledger.jsonl`, `tmp/coding-outcome-ledger-current.json` | 261 durable rows; current ok |
| Implementation completion ledger | `state/implementation-completion-ledger.jsonl`, `tmp/implementation-completion-ledger-current.json` | 34 durable rows; current ok |
| Finance recommendation correctness | `data/state-history/finance-recommendation-correctness-ledger.jsonl` | 102 durable rows; review-only |
| WF55 outcome ledger v2 | `data/state-history/outcome-ledger-v2.jsonl` | 15 durable rows; review-only |
| Improvement ledger | `data/state-history/improvement-ledger.jsonl`, `tmp/improvement-ledger-current.json` | 8 durable open rows; carry-forward true |
| Cron operator ledger | `tmp/cron-operator-ledger.json` | current warning class, not an OTEL blocker |
| Validator timing ledger | `tmp/validator-timing-ledger.json` | current ok |

The ledger layer is broad enough to support improvement loops. The remaining weakness is prioritization and autonomous follow-through, not missing evidence.

## Improvement Carry-Forward

Rating: B

The carry-forward path exists:

- `data/state-history/improvement-ledger.jsonl` is append-only.
- `tmp/improvement-ledger-current.json` summarizes open recommendations.
- `06. Playbooks/Startup Truth Index.md` routes new sessions to inspect the improvement ledger and current packet.
- `tmp/future-session-enhancement-packet.json` is designed to carry PM, cron, WF74, route, memory, stop-line, and improvement state.
- `tmp/startup-brief-packet.json` reads existing packets for fast startup/status.

Current improvement ledger:

- open rows: `8`
- high-priority open rows: `3`
- top item: `Repair blocked WF74 collection step`
- categories: code mutation, collector config, execution, finance mutation, skill application, OTEL learning loop

Current caveat:

An active `RUNTIME::CORE-ROUTE-HARDENING` lane is already writing `improvement_ledger.py`, `future_session_enhancement_packet.py`, `startup_brief_packet.py`, and related outputs. This audit treated those surfaces as read-only to avoid a two-writer collision.

## Autonomous Completion Path

Rating: B-

WF74 can already detect and propose improvements:

- `tmp/wf74-improvement-opportunity-queue.json`: `status=ok`, 5 opportunities
- `tmp/wf74-reflection-to-proposal-autopilot.json`: `status=ok`, 5 proposals
- `tmp/wf74-auto-patch-proposer.json`: `status=ok`, 5 plans
- patch plans: `1`
- owner-gated plans: `4`
- Skill Workshop requests: `1`
- auto-apply candidates: `0`
- auto-apply count: `0`

This is the correct posture. The system should autonomously prepare and route improvement work, but not auto-apply code, config, skill, finance, or execution changes without a separate gate.

The missing piece is a dispatcher that turns safe `patch_plan` rows into scoped leased implementation lanes automatically, while keeping `auto_apply_count=0`.

## Upgrade Proposals

Rating: A-

1. New-session improvement gate

- Route: startup/future-session packet validator
- Change: make stale or missing `tmp/improvement-ledger-current.json` visible in `startup_brief_packet.py` and `future_session_enhancement_packet.py`.
- Acceptance proof: startup/future packet includes improvement ledger summary and warns when it is stale.

2. Auto lane opener for safe patch plans

- Route: WF74 gated automation
- Change: convert `wf74-auto-patch-proposer` `patch_plan` rows into leased lanes with exact `allowed_writes`.
- Stop line: do not apply diffs automatically.
- Acceptance proof: lane created, proof commands attached, `auto_apply_count=0`.

3. Improvement SLA ladder

- Route: `improvement_ledger.py`
- Change: add age/priority fields so high-priority carry-forward rows older than N sessions surface in startup.
- Acceptance proof: `tmp/improvement-ledger-current.json` reports stale high-priority open count.

4. Owner-gated OTEL field-depth packet

- Route: owner config decision
- Change: prepare a proposed local-only config diff for richer token/cost/latency metadata, with privacy scan and rollback.
- Stop line: no collector config mutation without explicit approval.
- Acceptance proof: privacy scan ok, rollback documented, config mutation flag remains false until approved.

5. Weekly improvement radar first-run validation

- Route: cron contract validation
- Change: after the first Sunday run, verify `Runtime - Weekly OS Improvement Radar Review` wakes main only when material improvement candidates exist.
- Acceptance proof: cron control ok, no noisy wake, improvement candidate summary correct.

## Findings

Rating: B+

### P1 - Carry-Forward Needs Enforcement

Rating: B

Evidence:

- `tmp/improvement-ledger-current.json` exists and is current.
- `Startup Truth Index.md` names improvement ledger routes.
- Startup/future packets exist, but startup packet currently reports `stale_input_warning`.

Impact:

New sessions can miss improvement priorities if they rely on chat history or stale startup packets.

Recommendation:

After the active hardening lane closes, validate that future-session and startup packets refresh/read improvement ledger state before OS/WF74 recommendations.

Acceptance proof:

- `tmp/future-session-enhancement-packet.json` validation ok
- `tmp/startup-brief-packet.json` not stale for improvement inputs
- improvement ledger summary appears in startup route

### P1 - Autonomous Improvement Must Stay Proposal-First

Rating: B+

Evidence:

- `tmp/wf74-auto-patch-proposer.json` has `auto_apply_count=0`.
- `skills/veritas-self-improvement/SKILL.md` blocks auto-apply for code, skills, collector config, finance, execution, and runtime changes.

Impact:

This prevents self-improvement from becoming unsafe self-mutation.

Recommendation:

Autonomously open scoped lanes for safe patch plans, but require separate approval/gates for actual apply when risk crosses code/config/skill/finance/execution boundaries.

Acceptance proof:

- leased lane with exact writes
- validation commands listed
- no diff applied from WF74 artifact alone
- `auto_apply_count=0`

### P2 - OTEL Field Depth Is Useful But Owner-Gated

Rating: A-

Evidence:

- `tmp/otel-field-depth-limited-owner-packet.json` status is `owner_decision_required`.
- `tmp/otel-learning-loop.json` recommends token/cost metadata depth.

Impact:

Better token/cost/latency metadata would improve model-routing economics and efficiency learning. But it touches collector/runtime capture depth, so it cannot be silently enabled.

Recommendation:

Prepare a config-diff packet only if Randall wants richer local metadata. Do not capture raw prompts, responses, tool payloads, headers, secrets, or system prompts.

Acceptance proof:

- owner-approved diff
- rollback path
- privacy scan ok
- collector still loopback/local-only

### P2 - Active Lane Collision Limits Immediate Action

Rating: B

Evidence:

- Active `RUNTIME::CORE-ROUTE-HARDENING` lane owns improvement-ledger and startup packet scripts/artifacts.
- Active WF75 lane owns today’s memory.

Impact:

This audit should not patch those files during the active lanes.

Recommendation:

Feed this audit into the active lane or revisit after it closes.

Acceptance proof:

- active lanes closed
- no overlapping writes
- future-session/startup packet validation clean

## Next Concrete Action

Rating: A

After `RUNTIME::CORE-ROUTE-HARDENING` closes, run this sequence:

```powershell
python scripts\improvement_ledger.py --write --write-md --validate
python scripts\future_session_enhancement_packet.py --write --write-md --validate
python scripts\startup_brief_packet.py --write --validate
python scripts\wf74_auto_patch_proposer.py --write --write-md --validate
```

Then inspect:

- improvement ledger open/high-priority counts
- startup packet stale-input status
- future-session packet WF74/improvement section
- auto-patch `patch_plan_count`, `owner_gated_plan_count`, `skill_workshop_request_count`, `auto_apply_count`

Clean target:

- `auto_apply_count=0`
- startup/future packets validation ok
- high-priority improvement items visible in new-session handoff
- no config/runtime/canon/portfolio/execution authority widened

## Authority Boundary

Rating: A

This audit was review-only. It refreshed OTEL proof packets and wrote this audit plus its machine packet. It did not mutate collector config, runtime config, cron jobs, startup files, improvement-ledger scripts, skills, finance canon/portfolio/cash/sizing, paper/live/account surfaces, external delivery, or owner approval state.

Raw prompt/response/tool payload capture remains blocked. Secret/header/system-prompt capture remains blocked. OTEL remains local-only.
