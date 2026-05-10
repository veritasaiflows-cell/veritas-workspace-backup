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
- **Model / thinking:** choose effort by role; do not default every spawned lane to high thinking.
- **Acceptance proof:** what file, command, or summary proves the lane finished?
- **Early progress checkpoint:** for implementation lanes, what harmless artifact or patch file should exist within the first 3-5 minutes?

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

Objective:
- <one sentence>

Current truth:
- <brief state>

Read first:
- <file 1>
- <file 2>
- <file 3>

Do not touch:
- <canonical notes / config / credentials / destructive surfaces>

Deliverables:
1. <required finding / patch / artifact>
2. <required risk or gap list>
3. <recommended next action>

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
- Final answer must include exact files inspected, commands run, and unresolved gaps.

Stop conditions:
- Stop and report if the scope is broader than the runtime budget.
- Stop and report if canonical ownership is ambiguous.
- Do not move queue state or claim final closeout authority.
```

## Spawn call checklist

When using `sessions_spawn`, prefer:

- `model` from the allowed `openai-codex/*` set, with `openai-codex/gpt-5.5` reserved for important or complex lanes rather than automatic use everywhere
- `thinking: "low"` for routine research, inventory, and read-only audit/alignment checks
- `thinking: "medium"` for implementation, validator/script edits, and bounded workflow artifact production
- `thinking: "high"` for hard debugging, runtime failures, high-stakes trust adjudication, repeated false-green/false-red residue, or ambiguous cross-contract failures
- `runTimeoutSeconds` set explicitly
- `timeoutSeconds` long enough for launch acknowledgement, not the work itself
- `context: "isolated"` unless current transcript context is truly required
- `lightContext: true` when the packet names the files and the child does not need the full parent transcript

## Failure handling

If a child times out:
1. inspect child history before respawning
2. classify the failure as contract, runtime budget, tool, provider, or child-execution behavior
3. preserve any partial evidence
4. narrow the next spawn or increase the explicit timeout
5. update this template or the governing protocol if the failure pattern is reusable
