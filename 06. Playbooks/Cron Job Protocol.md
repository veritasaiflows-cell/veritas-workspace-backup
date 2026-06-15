# Cron Job Protocol

## Purpose
Keep scheduled OpenClaw jobs useful, bounded, honest, and symmetrical.

Pair this protocol with `06. Playbooks/Spawn and Closeout Governance Matrix.md` when a job might spawn helper lanes or produce closeout claims.
Use that file as the canonical spawn decision source rather than treating this document as an independent spawn standard.

Local OpenClaw code/docs truth that matters here:
- cron runs inside the Gateway, not inside the model
- job definitions persist separately from runtime state
- isolated jobs are usually the right default for background work; main-session jobs are mainly for reminders/system events
- live cron state wins over inherited notes if they disagree

## Symmetrical Job Card Format
Every cron job should define the same fields in the same order:
- **Name**
- **Window family**: pre-market / post-close / post-earnings / Sunday / reminder / other
- **Schedule / time zone**
- **Session target**: main / isolated / current / session:<id>
- **Owner**
- **Trigger goal**
- **Read first**
- **Execute in order**
- **Artifacts or notes to inspect after execution**
- **Response contract**
- **Spawn recommendation**
- **Inputs read**
- **Artifacts or notes it may write**
- **Delivery mode**: none / announce / webhook
- **Trust grade**: internal-only / review-required / automation-ready
- **Validation proof**: exact artifact, run-history, or note evidence required
- **Stop line**: what makes the job stop instead of pretending success
- **Escalation path**: direct finish / update notes / spawn worker / wait for human input
- **Overlap owner**: what other workflow window this job must not compete with

## Symmetry standard
Jobs that belong to the same family should be structurally parallel unless there is a documented reason not to be.

At minimum, sibling jobs should align on:
1. naming pattern
2. timezone handling
3. session-target choice
4. delivery posture
 5. read-first packet shape
 6. response contract shape
 7. artifact proof expectations
 8. rerun policy
 9. failure / skipped-run follow-up

If one sibling diverges, write the exception down instead of letting the set drift silently.

## Cron design sequence
Before adding or editing a recurring job, walk these steps in order:
1. **Classify the mechanism** - heartbeat vs cron
2. **Choose the owner window** - one writer per output family
3. **Choose the execution surface** - main reminder vs isolated worker vs current/custom session
4. **Define the smallest useful cadence** - no ornamental schedules
5. **Define proof and downgrade rules** - what proves success, what forces partial/stale/manual language
6. **Define overlap and rerun rules** - what it must not race, what justifies rerun
7. **Validate live** - list/show/run/runs plus artifact inspection

Do not skip directly from idea to scheduled job.

## Cron run packet contract
Every non-trivial cron job should carry an explicit run packet inside the job design or payload prompt.

Required packet fields:
1. **Objective** - one-sentence statement of what this run owns
2. **Read first** - exact files to inspect before acting, in priority order
3. **Execute in order** - exact scripts or commands to run, in order
4. **Inspect after execution** - exact artifacts, notes, or proofs to check before claiming completion
5. **Response contract** - exact structure the run should use when summarizing results
6. **Spawn recommendation** - whether to stay in-run, spawn one worker, or stop for operator input
7. **Out-of-bounds** - what the run must not touch or imply
8. **Stop lines** - what forces blocked/error instead of optimistic language

If a run depends on file truth, do not rely on hidden memory or vague inherited context. Name the files.

## Read-first rule
Cron prompts should not say only “use the workspace” or “check the usual files.”

They should name the exact read order for the window.

Good:
- read `06. Playbooks/Automation Orchestration Protocol.md`
- read `06. Playbooks/Cron Job Protocol.md`
- read `tmp/run-summary-morning.json`

Bad:
- read whatever seems relevant
- infer the current queue from prior chat

## Execute-in-order rule
Cron prompts should name the exact execution surface and sequence whenever the order matters.

Good:
1. run `python scripts\\run_finance_refresh_chain.py morning`
2. inspect `tmp/run-summary-morning.json`
3. inspect `tmp/dashboard-validation.json`

Bad:
- refresh the morning chain and then look around

## Response contract rule
Each scheduled run should be told exactly how to respond.

Minimum response fields for non-trivial jobs:
- active item
- completion decision
- trust state
- fresh outputs checked
- next queued item
- next concrete action
- blocker or warning, if any
- whether a worker was spawned

If the job is review-only, it must say what operator action is still required instead of implying completion from artifacts alone.

## Spawn recommendation rule
Each cron design should say which of these is expected:
- **stay in-run** -> low-effort work, no separate worker
- **spawn one bounded worker** -> medium-effort detached pass with explicit files and acceptance target
- **stop for operator input** -> trust, auth, destructive, or ambiguous judgment boundary

If spawning is allowed, the packet should also specify:
- recommended model posture
- required thinking posture; Spark (`codex/gpt-5.3-codex-spark`) cron/helper lanes must use `xhigh` thinking until repeated proof says otherwise
- exact files to read first
- exact acceptance target
- out-of-bounds surfaces
- whether the child is read-only, distinct-output, or patch-prep only

Do not let cron invent a spawn contract at runtime.

## Efficiency fields
To keep runs smaller, faster, and more coherent, prefer adding these fields when the job is more than trivial:
- **Time budget** - expected max run length before the run should downgrade or stop
- **Retry budget** - whether retry is allowed and for which failure class
- **Allowed tools/surfaces** - the smallest required tool set
- **Decision owner** - who owns the final judgment if the run ends in warning or review-required state
- **Resume anchor** - continuity note or file path a later worker should use if the run must be resumed

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


## Cron Automation Authority Tiers

Randall approved broader cron automation authority on 2026-05-23. Use these tiers for every recurring job and handoff. The machine-readable contract is `tmp/cron-automation-authority-contract.json`; validate it with `python scripts\cron_authority_matrix_validator.py --write`.

| Tier | Name | Cron can do | Cron cannot do |
|---|---|---|---|
| T0 | Observe/report | status, warnings, run summaries, ledger rows | mutate notes/canon/archive |
| T1 | Review-only artifact/dashboard refresh | write `tmp/` packets, dashboards, reports, SQL proof/index/staging | canonical/portfolio mutation or approval language |
| T2 | Patch proposal / semantic preview | generate canonical-note patch proposals, portfolio proposals, exact previews, verifier reports | apply patches or imply eligibility |
| T3 | Main-session bounded freshness/status sync | wake/handoff main session to inspect artifacts and apply bounded freshness/status sync | unattended direct cron note write |
| T4 | Exact gated workspace portfolio/canon maintenance | generate proposal/verifier; use existing narrow applies only where already approved | broaden direct apply; trade/account/cash/risk/execution changes |
| T4A | Future narrow cron-direct maintenance candidate | inactive placeholder only | any current direct apply |
| T5 | Bounded auto-archive movement | archive-only moves under the approved policy | deletes or moving protected/canonical/current-window/script/skill/config files |
| TX | Blocked | nothing | live/paper-outside-WF67, credentials, config/service, deletes, approval inference |

Financial notes/canon default to T1/T2 proposal, preview, verifier, and reporting. Main-session Veritas owns T3 bounded freshness/status sync after artifact inspection. Existing narrow T4 helper applies (`event_calendar_apply.py --apply`, `auto_apply_entry_band_maintenance.py --apply`, and `canon_volatile_execution_board_sync.py --apply --strict-exit`) are category-specific and do not authorize broader cron-direct canon apply. T4A remains inactive until a future exact category is separately promoted with repeated proof, lock, rollback, audit, and independent QA.

## Session-target rule
- **main** -> reminders and system events only
- **isolated** -> default for background reports, review windows, and bounded artifact work
- **current** -> only when the job truly depends on the current bound session context
- **session:<id>** -> only when deliberate persistent history is part of the workflow contract

If a recurring job does not need chat-history continuity, do not give it one.

## Scheduling rule
- always write cron expressions in the intended local wall-clock timezone
- always declare the timezone when the wall-clock matters
- prefer one smallest useful review window over many overlapping nudges
- stagger top-of-hour recurring windows when exact timing is not required
- treat current live cron state as authoritative over stale notes or memory

## Validation sequence after create/edit
After adding or editing a job, verify in this order:
1. `cron list` - job exists and schedule looks right
2. delivery preview / job detail - route resolves the way you expect
3. one controlled manual run when safe
4. run history - outcome matches the intended contract
5. artifact proof - expected file/note/output actually exists
6. overlap check - no sibling window is competing for the same writer layer

A job is not real because it was created. It is real after proof.

## Failure and skipped-run rule
- treat `skipped` as meaningful state, not fake success
- if local providers, upstream inputs, or manual dependencies are unavailable, downgrade honestly instead of forcing green output
- define whether skipped runs should alert, and where
- do not rerun merely to hide truthful warning-grade output

## Git / audit posture
- if cron definitions are tracked, definitions belong in the durable layer and runtime state does not
- prefer one compact operator-readable source of truth for active job design
- keep audit proof in cron run history plus workspace artifacts, not only chat memory

## Effort Routing
- **Low effort** -> handle in the main cron run
- **Medium effort** -> spawn one bounded detached worker with `openai/gpt-5.4` and a tighter scope; do not assume an unpinned/default helper model
- **High effort** -> require preflight review first, then spawn one bounded detached worker with `openai/gpt-5.4` and high-thinking posture when the contract is clear enough; use `openai/gpt-5.5` only as a deliberate high-stakes exception
- **Spark effort rule** -> if a cron job or spawned cron helper uses `codex/gpt-5.3-codex-spark`, set `--thinking xhigh` / payload thinking `xhigh`; Spark is cheap enough that lower effort is not the default until proof says otherwise
- **Fallback rule** -> if the chosen model is unavailable, keep the same bounded contract and record the fallback rather than silently using a weaker lane

## Secure Spawn Default
When spawn is allowed:
- `runtime="subagent"`
- `mode="run"`
- `cleanup="delete"`
- `streamTo="parent"` only when the runtime actually supports it
- one active worker at a time for that lane
- explicit bounded task contract
- file-grounded handoff packet: active workflow, current truth, blocker/trust gap, next acceptance target, exact files, exact response contract, and out-of-bounds surfaces
- no auth, network, destructive, or canonical-finance-note changes without approval
- if persistent thread-bound subagent sessions are unavailable in the current surface, treat the spawn as one-shot and rely on continuity notes plus resume keywords instead of pretending resumable live state exists

## Required Run Output
Each cron run should end with:
- active item
- completion decision
- trust state
- fresh outputs checked
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
- `tmp/cron-operator-ledger.json` for current machine-readable cron operator status
- `optional Markdown digest beside `tmp/cron-operator-ledger.json`` for the compact human digest generated from that JSON
- `06. Playbooks/Cron Run Ledger.md` for legacy historical proof until migration is complete
- `06. Playbooks/Automation Run Summary Contract.md`
- cron run history

The JSON ledger is the current operator truth route.
The Markdown digest is the compact operator view.
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
- **Runtime/session reliability debt**: Workflow 10 is closed, but runtime/session state is still advisory beneath artifact-level proof, especially when memory index health remains degraded.
- **Memory-index breakage**: continuity search is degraded, so cron must rely on file truth over assumed memory recall.
- **Automation theater**: jobs can keep moving without real readiness or clear trust boundaries.

## Actions Needed To Refine
1. **Keep validating the day-job orchestrator live** before calling Workflow 4 complete.
2. **Add a compact run-history surface** so cron results are easy to audit without reading raw chat.
3. **Add failed-run follow-up logic** for blocked or error states.
4. **Keep runtime/session state subordinate to artifact-level proof** until lifecycle behavior remains boringly consistent over time.
5. **Review overlap risk whenever a new cron is proposed** so one window still owns each output.
6. **Promote only repeated stable patterns** into stronger automation; do not widen autonomy from a single clean run.

## Default Decision
If a cron job cannot prove it is safe to continue, it should update notes and stop.
