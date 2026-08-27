# Subagent Spawn Handoff Template

> **Keep execution backends distinct.** A `codex_native_subagent` is a transient bounded Codex run. A `persistent_isolated_agent` is a configured specialist with separate session provenance and requires fresh strict context-transport proof before dispatch. This template governs both handoff packets; it does not configure a new persistent agent. See `skills/veritas-isolated-agent-contract/SKILL.md`.

## Purpose
Make spawned OpenClaw helper lanes easy to launch without recreating the contract from scratch or accidentally giving the child an unbounded audit.

Use this for non-trivial `sessions_spawn` work. Keep the packet compact enough that the child can start from files, not chat reconstruction.

For long or multi-surface implementation, first use `skills/disciplined-implementation/SKILL.md` to classify the task, check cached front doors, verify authority gates, lease write surfaces, and choose the validation budget. This template starts after main has decided a helper lane is justified.

## Spawn preflight

Before spawning, answer these in the main session:

- **Mode:** `Spawn read-only` / `Spawn distinct-output` / `Blocked` / `Main-session only`
- **Route proof:** the validated `project_implementation_router.py` artifact, selected backend, expected model/thinking, and any required persistent transport proof. Missing/malformed proof blocks dispatch; it never authorizes silent Main fallback.
- **Why spawn:** what work is too broad or time-consuming for the main lane?
- **Long-work route:** which department, skill, workflow, or owner surface controls the proof?
- **Lane proof:** exact lane lease id, or explicit read-only/distinct-output no-write posture.
- **Stop line:** what must the child not do?
- **Artifact-first requirement:** where should partial/final output be written if the run may exceed 10 minutes?
- **Runtime budget:** record the budget in the packet. Use a tool timeout only where the called tool exposes one, such as cron `agentTurn.timeoutSeconds`; for `sessions_spawn`, narrow scope plus artifact-first checkpoints are the budget control.
- **Model / thinking:** consume `veritas.execution_efficiency_policy.v1`. Model-free first; explicit bounded native Terra/low or Terra/medium; persistent Terra effort by scope only after transport proof; Main/Sol explicit exceptions only. Record actual backend/model/thinking at closeout and fail closed on mismatch.
- **Acceptance proof:** what file, command, or summary proves the lane finished?
- **Validator budget:** micro / narrow / shared / major, or exact reason validation is deferred to main.
- **Early progress checkpoint:** for implementation lanes, what harmless artifact or patch file should exist within the first 3-5 minutes?
- **Context budget:** default to `lightContext: true`, an explicit workspace-relative handoff base path, and at most six named files / 120,000 bytes / 30,000 estimated tokens. Create the sorted SHA-256 manifest and frozen snapshot id before dispatch. If any limit is exceeded, split the lane; do not merely increase effort.
- **Frozen snapshot:** run `helper_lane_manifest.py` before dispatch and `swarm_completion_handshake.py` before synthesis. Missing files, path escape, hash drift, budget overflow, or failed preflight are stop lines.
- **Tool budget:** name the maximum first-pass reads/searches/commands when timeout risk is material. Prefer source-opened proof over broad repository search.
- **Windows command posture:** if the lane may run shell commands, tell it this workspace is native PowerShell/Windows: no Bash heredocs (`python - <<'PY'`), no unquoted regex pipes that PowerShell/cmd will split, and run Python scripts as `python scripts\name.py` rather than bare script names.

## Narrow-packet rule

Use narrow packets by default after the 2026-05-29 SQL scaleout timeout cluster.

Default helper lane shape:
- one objective
- one owner workflow
- one primary output artifact
- one write surface, or read-only
- three to six named files to read first
- one explicit workspace-relative base path plus a hashed frozen manifest
- one required validation command
- one early checkpoint artifact when implementation is involved

Do not spawn a broad lane that asks the child to read several workflow notes, multiple skills, several scripts, and then design/implement/document/update continuity in one pass unless the runtime budget is long and an artifact-first checkpoint is mandatory. Split that into smaller packets instead.

For validator/script work, prefer this sequence:
1. main session reads owner notes and decides the exact contract
2. helper reads the target script plus nearest validator only
3. helper writes the script/proof artifact
4. main verifies and performs continuity/control-surface updates

Use `lightContext: true` for these packets. Use `context: "fork"` only when the child needs the current transcript to answer the task; most file-grounded implementation lanes do not.

## Recommended runtime budget

Record the budget in the task packet. For cron `agentTurn` jobs, also set `timeoutSeconds`. For `sessions_spawn`, use narrow scope, checkpoint artifacts, and `sessions_yield` completion instead of polling.

| Task shape | Suggested budget | Rule |
|---|---:|---|
| quick read-only check | 900-1200 | no deep repository scan |
| bounded multi-file audit | 2400-3600 | write artifact before synthesis |
| broad inventory / architecture audit | 5400-7200 | split into phases if possible |
| implementation pass | 3600-7200 | exact files and validation required |

If the work cannot fit one of these honestly, split it before spawning.

## Copyable task packet

```text
You are a bounded OpenClaw helper lane. Work from files, not hidden chat memory.

Mode: <Spawn read-only | Spawn distinct-output>
Long-work route: <department / skill / workflow owner>
Lane proof: <lease id | explicit read-only/no-write posture>
Runtime budget: <N> seconds. Prioritize artifact output before exhaustive inspection.
Context/tool budget: use light context, read only the named files first, and avoid broad scans unless the named files cannot answer the question. First-pass read budget: <3-6 files, or exact number>.
Handoff base path: <workspace-relative path; never an implicit current directory>
Frozen handoff: <manifest path, frozen snapshot id, contract hash>
Attempt: <attempt number, attempt id; on retry include prior attempt id, failure class, and retry reason>
Shell posture: native Windows PowerShell. Do not use Bash heredocs or Bash-only chaining. Run repo Python scripts through `python scripts\...`.
Validator budget: <micro | narrow | shared | major | main-owned>
Execution route: <model_free_command | codex_native_subagent | persistent_isolated_agent | main>
Expected route: backend=<...> model=<...|none> thinking=<none|low|medium|high>
Actual-route closeout requirement: backend/model/thinking plus provenance; mismatch blocks acceptance.
Persistent transport proof: <workspace-relative strict JSON proof | not_applicable>

Objective:
- <one sentence>

Current truth:
- <brief state>

Read first:
- <file 1>
- <file 2>
- <file 3>

Do not read first:
- broad workflow folders
- all skills
- full `tmp/` scans
- parent transcript/forked chat context
- unrelated continuity history

Do not touch:
- <canonical notes / config / credentials / destructive surfaces>

Deliverables:
1. <primary required patch or artifact>
2. <validation command output>
3. <one blocker/gap list, only if non-empty>

Early progress checkpoint:
- For implementation lanes, create or update the first harmless target artifact within 3-5 minutes when practical.
- If direct implementation is not safe yet, write a short checkpoint note to `<path>` explaining the blocker, inspected files, and next command.
- If the run loses context after inspection, main should preserve the partial evidence and continue or relaunch a narrower lane instead of assuming permission failure.

Detail standard:
- Be concise, but not thin.
- For each material finding, include: evidence/source file, why it matters, severity, owner or affected surface, recommended fix, and acceptance proof.
- If a finding is low-confidence or based on partial inspection, label it that way instead of omitting context.
- Do not return only a verdict unless the task explicitly asks for a smoke check.

Artifact-first rule:
- If this takes more than 10 minutes, write partial findings to `<path>` before continuing.
- If tool calls start failing because of shell/runtime mismatch, stop, record the failed command and corrected Windows-safe command, and continue only if the correction is obvious and low-risk.
- Final answer must include exact files inspected, commands run, and unresolved gaps.

Stop conditions:
- Stop and report if the scope is broader than the runtime budget.
- Stop and report if canonical ownership is ambiguous.
- Stop and report if write-capable work lacks a lane lease or explicit no-write posture.
- Do not move queue state or claim final closeout authority.
```

## Spawn call checklist

When dispatching a helper, prefer:

- validate the backend/model/thinking with `project_implementation_router.py` and record the exact route, role, trust label, and proof
- use Codex-native only for the explicit bounded eligibility contract; use a persistent specialist only with fresh transport proof; do not inherit Main/Sol into helpers
- `thinking: "xhigh"` for every Spark lane (`codex/gpt-5.3-codex-spark`) until repeated evidence proves a lower effort is equally reliable
- `thinking: "low"` for routine research, inventory, and read-only audit/alignment checks
- `thinking: "medium"` for implementation, validator/script edits, and bounded workflow artifact production
- `thinking: "high"` for serious cross-contract/multi-owner implementation, material independent QA, hard debugging, runtime failures, finance-readiness or authority semantics, high-stakes trust adjudication, repeated false-green/false-red residue, or ambiguous cross-contract failures
- runtime budget recorded in the packet; use a timeout field only when the tool exposes one
- isolated/light context unless current transcript context is strictly required
- `lightContext: true` when the packet names the files and the child does not need the full parent transcript
- a Windows-safe shell reminder in the task packet whenever `exec` may be used
- one partial-output artifact path for any lane with a timeout over 900 seconds
- `sessions_yield` after required long-running subagents are spawned; do not poll just to wait for completion

## Failure handling

If a child times out:
1. inspect child history before respawning
2. publish a provisional incident update within 90 seconds of detecting the failure
3. classify the failure as context overflow, handoff path, contract, runtime budget, tool, provider, validator, or child-execution behavior
4. preserve the attempt id, prior attempt id, frozen snapshot id, retry count, retry reason, elapsed time, and any partial evidence
5. narrow the next spawn or increase the explicit timeout; a retry gets a new attempt id and must not overwrite first-attempt evidence
6. update this template or the governing protocol if the failure pattern is reusable

Do not report retry yield as first-pass success. Fleet summaries must separately count first attempts, unusable attempts, retries, accepted retries, and unmatched session-to-parent-job attribution.

Efficiency closeout must also report uncached and gross token usage when available, elapsed time, retry tax, QA verdict, Main acceptance, and escaped defects. Incidents, invalid telemetry, unavailable actual-route evidence, and mismatches receive no success credit. Automatic route ranking/promotion remains disabled until at least ten like-for-like Main-accepted jobs exist—and remains a Main decision even after that gate.

Recent reliability lesson (2026-05-26): repeated helper failures clustered around oversized/file-broad audit packets, missing Windows shell reminders, and timeout-aborted runs that had not written a partial artifact before the provider/tool timeout. Treat those as contract failures first, not proof that the underlying task is impossible.
