# Cron Job Protocol

## Purpose
Keep scheduled OpenClaw jobs useful, bounded, and honest.

Pair this protocol with `06. Playbooks/Spawn and Closeout Governance Matrix.md` when a job might spawn helper lanes or produce closeout claims.
Use that file as the canonical spawn decision source rather than treating this document as an independent spawn standard.

## Job Card Format
Every cron job should define:
- **Name**
- **Schedule / time zone**
- **Owner**
- **Trigger goal**
- **Inputs read**
- **Artifacts or notes it may write**
- **Trust grade**: internal-only / review-required / automation-ready
- **Stop line**: what makes the job stop instead of pretending success
- **Escalation path**: direct finish / update notes / spawn worker / wait for human input

## Core Rules
1. **One owner per workflow window.**
   No overlapping jobs silently writing the same layer.
2. **Canonical judgment notes are out of bounds by default.**
   Cron may maintain artifacts, review surfaces, and control-plane notes unless explicit trust gates allow more.
3. **Advance only from verified state.**
   A job is not complete because a note sounds complete.
4. **Fail closed on ambiguity.**
   If trust, inputs, or completion state are unclear, stop and record the blocker.
5. **Use the smallest real action.**
   Correct the outlier, not every file.

## Effort Routing
- **Low effort** -> handle in the main cron run
- **Medium effort** -> spawn one bounded detached worker only with an approved live model and a tighter scope; do not assume a removed cheap helper model exists
- **High effort** -> require preflight review first, then spawn one bounded detached worker with `openai-codex/gpt-5.4` only if the contract is clear enough

## Secure Spawn Default
When spawn is allowed:
- `runtime="subagent"`
- `mode="run"`
- `cleanup="delete"`
- `streamTo="parent"` only when the runtime actually supports it
- one active worker at a time for that lane
- explicit bounded task contract
- file-grounded handoff packet: active workflow, current truth, blocker/trust gap, next acceptance target, exact files, and out-of-bounds surfaces
- no auth, network, destructive, or canonical-finance-note changes without approval
- if persistent thread-bound subagent sessions are unavailable in the current surface, treat the spawn as one-shot and rely on continuity notes plus resume keywords instead of pretending resumable live state exists

## Required Run Output
Each cron run should end with:
- active item
- completion decision
- current project status
- next queued item
- next action
- whether preflight was required
- whether a worker was spawned and with which model
- notes updated
- blocker, if any

## Operator surface requirement
Cron proof should be visible without reading raw chat history.

Use these surfaces together:
- `06. Playbooks/Cron Run Ledger.md`
- `06. Playbooks/Automation Run Summary Contract.md`
- cron run history

The ledger is the compact operator view.
The run-summary contract is the machine-readable per-window evidence layer.
Raw cron history is the audit trail behind them.

## Delivery posture decision (v1)
Current accepted posture for the Veritas finance/control-plane cron layer:
- internal-only / no-delivery is acceptable for now
- proof must come from cron run history plus workspace artifacts/notes
- do not pretend a routed chat delivery exists when the job has no real route

This remains acceptable only while the operator surfaces are explicit and easy to audit.

## Proof-run contract (Workflow 4B)
For each live Veritas cron job, proof is good enough only when all are true:
1. a controlled cron run exists in cron run history
2. the expected workspace artifact or note surface exists and is inspectable
3. trust-boundary fields remain explicit where relevant (`presentation_allowed`, `canonical_note_mutation_allowed`)
4. blocked/error follow-up behavior is written down
5. rerun and overlap rules are explicit

If one of those is missing, the job is not fully proved yet.

## Rerun and overlap rules
1. Do not force overlapping finance-window proof runs against the same artifact family.
2. Do not run the day-job orchestrator and continuity hygiene pass as concurrent writers on the control-plane lane.
3. Rerun a finance window when a required artifact is missing, a trust-boundary field is missing, the run is blocked/error, or a clearly recoverable source glitch justifies another pass.
4. Do not rerun only to erase honest warning-grade outputs that are still telling the truth.
5. When a run ends blocked or error, record the next-step action in the ledger or continuity note before triggering another rerun.
6. If delivery remains internal-only, absence of routed chat delivery is not itself a rerun trigger.

## Current Risks
- **Control-plane drift**: queue, registry, and continuity note can disagree.
- **False completion**: a workflow can look done before acceptance evidence exists.
- **Unsafe overlap**: multiple jobs can compete for the same outputs.
- **Runtime/session reliability debt**: Workflow 10 is still open, so control-surface state is not fully trustworthy.
- **Memory-index breakage**: continuity search is degraded, so cron must rely on file truth over assumed memory recall.
- **Automation theater**: jobs can keep moving without real readiness or clear trust boundaries.

## Actions Needed To Refine
1. **Keep validating the day-job orchestrator live** before calling Workflow 4 complete.
2. **Add a compact run-history surface** so cron results are easy to audit without reading raw chat.
3. **Add failed-run follow-up logic** for blocked or error states.
4. **Keep Workflow 10 active** until session/subagent lifecycle behavior is proven more reliable.
5. **Review overlap risk whenever a new cron is proposed** so one window still owns each output.
6. **Promote only repeated stable patterns** into stronger automation; do not widen autonomy from a single clean run.

## Default Decision
If a cron job cannot prove it is safe to continue, it should update notes and stop.
