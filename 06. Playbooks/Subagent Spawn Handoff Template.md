# Subagent Spawn Handoff Template

## Purpose
Make spawned OpenClaw helper lanes easy to launch without recreating the contract from scratch or accidentally giving the child an unbounded audit.

Use this for non-trivial `sessions_spawn` work. Keep the packet compact enough that the child can start from files, not chat reconstruction.

## Spawn preflight

Before spawning, answer these in the main session:

- **Mode:** `Spawn read-only` / `Spawn distinct-output` / `Blocked` / `Main-session only`
- **Why spawn:** what work is too broad or time-consuming for the main lane?
- **Stop line:** what must the child not do?
- **Artifact-first requirement:** where should partial/final output be written if the run may exceed 10 minutes?
- **Runtime budget:** set `runTimeoutSeconds` explicitly; do not rely on the implicit default for broad work.
- **Model / thinking:** default bounded helpers to `openai/gpt-5.4`; choose thinking effort by role; do not default every spawned lane to high thinking or GPT-5.5. Exception: any lane using `codex/gpt-5.3-codex-spark` must use `xhigh` thinking until repeated proof says otherwise.
- **Acceptance proof:** what file, command, or summary proves the lane finished?
- **Early progress checkpoint:** for implementation lanes, what harmless artifact or patch file should exist within the first 3-5 minutes?
- **Context budget:** default to `lightContext: true` and a short file list. Do not spawn broad helper lanes with the full parent transcript unless the child genuinely needs that transcript.
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
- one required validation command
- one early checkpoint artifact when implementation is involved

Do not spawn a broad lane that asks the child to read several workflow notes, multiple skills, several scripts, and then design/implement/document/update continuity in one pass unless the runtime budget is long and an artifact-first checkpoint is mandatory. Split that into smaller packets instead.

For validator/script work, prefer this sequence:
1. main session reads owner notes and decides the exact contract
2. helper reads the target script plus nearest validator only
3. helper writes the script/proof artifact
4. main verifies and performs continuity/control-surface updates

Use `lightContext: true` for these packets. Use `context: "fork"` only when the child needs the current transcript to answer the task; most file-grounded implementation lanes do not.

## Recommended timeout budget

| Task shape | Suggested `runTimeoutSeconds` | Rule |
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
Runtime budget: <N> seconds. Prioritize artifact output before exhaustive inspection.
Context/tool budget: use light context, read only the named files first, and avoid broad scans unless the named files cannot answer the question. First-pass read budget: <3-6 files, or exact number>.
Shell posture: native Windows PowerShell. Do not use Bash heredocs or Bash-only chaining. Run repo Python scripts through `python scripts\...`.

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
- Do not move queue state or claim final closeout authority.
```

## Spawn call checklist

When using `sessions_spawn`, prefer:

- `model: "openai/gpt-5.4"` for normal bounded helper lanes; use `openai/gpt-5.5` only for deliberate high-stakes exceptions and `codex/gpt-5.3-codex-spark` only for narrow proof/canary/QA/pre-work lanes after proof is clean
- `thinking: "xhigh"` for every Spark lane (`codex/gpt-5.3-codex-spark`) until repeated evidence proves a lower effort is equally reliable
- `thinking: "low"` for routine research, inventory, and read-only audit/alignment checks
- `thinking: "medium"` for implementation, validator/script edits, and bounded workflow artifact production
- `thinking: "high"` for hard debugging, runtime failures, high-stakes trust adjudication, repeated false-green/false-red residue, or ambiguous cross-contract failures
- `runTimeoutSeconds` set explicitly
- `timeoutSeconds` long enough for launch acknowledgement, not the work itself
- `context: "isolated"` unless current transcript context is truly required
- `lightContext: true` when the packet names the files and the child does not need the full parent transcript
- a Windows-safe shell reminder in the task packet whenever `exec` may be used
- one partial-output artifact path for any lane with a timeout over 900 seconds

## Failure handling

If a child times out:
1. inspect child history before respawning
2. classify the failure as contract, runtime budget, tool, provider, or child-execution behavior
3. preserve any partial evidence
4. narrow the next spawn or increase the explicit timeout
5. update this template or the governing protocol if the failure pattern is reusable

Recent reliability lesson (2026-05-26): repeated helper failures clustered around oversized/file-broad audit packets, missing Windows shell reminders, and timeout-aborted runs that had not written a partial artifact before the provider/tool timeout. Treat those as contract failures first, not proof that the underlying task is impossible.
