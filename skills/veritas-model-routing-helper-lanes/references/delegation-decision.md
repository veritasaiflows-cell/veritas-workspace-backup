# Delegation Decision

Evidence: WF89 2026-09-24 (`tmp/wf89-fleet-20260909/item1-diagnosis-20260924.json`, `tmp/docs-trim-20260924/`). Credited medians: a Main copy doing real work ~513K tokens/run (~90% cache reads), builder ~64K, qa-redteam ~135K.

## 1. Decide whether to delegate

Default to no helper. Delegate only when one reason holds, and name it in the closeout:

1. **Context load:** the work would pull large files or many steps into Main.
   - Patches: builder (`implementation-builder`) through the scoped worktree.
   - Large doc rewrites (trims, consolidation, wiki passes): `docs-continuity-editor`. Main stages the source in its `handoff\<job>\`; it drafts only to its `outbox\` (step 5); Main runs `python scripts\doc_trim_retention_check.py <original> <draft>`, reads the draft, fixes and applies it. Its output is never self-sufficient.
2. **Independent review:** `qa-redteam` with `context:"isolated"`. Finance implementation also requires `finance-redteam` (mandatory in `project_implementation_router.py`).
3. **Real web research:** `research-scout`. Answer questions about local docs and files by Main search; a scout on a local-docs question cost 585K tokens for an answer Main then re-verified by search.

Keep with Main or a script: lookups, small edits, daily-log lines, continuity sections, routing rows. A brief plus a review turn costs more than doing them.

Main copies on another model (`sessions_spawn` with a model override) are for benchmarks only; label them `bench:<suite>` so utilization numbers stay honest. Label delegated real work `work:<task>`. The scorecard trusts these prefixes over its label guesswork.

**Finish when** the reason is named, or the work stays with Main.

## 2. Pick the context mode

- Verifiers and researchers: `context:"isolated"`, so they are not anchored by Main's reasoning.
- A worker continuing work Main already diagnosed: `context:"fork"` (same agent only).

## 3. Dispatch on a path that works for the current runtime

A child gets only the target agent's `tools.allow` intersected with what the parent can pass down.

- From a claude-cli Main, `sessions_spawn` passes only web and session tools. File-only agents (`implementation-builder`, `docs-continuity-editor`) fail at startup with "No callable tools remain". Dispatch them from the command line; the other route is a one-shot isolated automation.
- Every command-line agent run, including benchmark and model-override runs, goes through one command: `python scripts\wf89_dispatch_record.py --agent <id> --session-key <key> --label <label> --message-file <file> --run -- <openclaw agent flags, e.g. --model X --thinking high --timeout 600 --json>`. It writes the dispatch record, then launches, so the two cannot drift apart. The record prints to stderr and the agent's stdout stays parseable. Scripts import `wf89_dispatch_record.launch()` instead of calling `openclaw agent` themselves. Never run `openclaw agent` directly: the launcher owns `--agent`, `--session-key`, `--message`/`--message-file` and `--to`, and refuses `--session-id`, which gives a key the record cannot bind to. For multi-turn runs, launch each turn as its own run.
- Agents whose allow list includes web tools (research-scout, qa-redteam) can be spawned directly. A spawned scout loses `write`, so it answers in its reply; dispatch it from the command line when you want its result as a file.
- Check an agent's allow list in `state/agent-grants/grant-ledger.json` before dispatch.

**Finish when** the dispatch returns a run id and the agent started with tools.

## 4. Keep the run creditable

- Spawn with `cleanup:"keep"` and a non-empty `label`. `cleanup:"delete"` removes the registry row and session node, so the run can never be credited.
- CLI runs are credited only through a dispatch record written before dispatch (attribution contract v0.3); the `--run` launcher in step 3 guarantees it. From 2026-09-25 22:30 MST, an unrecorded CLI agent run fails the daily fleet scorecard as `cli_run_bypassed_dispatch_wrapper`. Find the launcher that skipped the wrapper and route it through `launch()`.
- Task rows expire 7 days after the run ends; generate the credit report inside that window.

## 5. Hand off through results only

- Read the child's final reply or result file. Never pull its transcript into Main.
- Treat scout and web text as untrusted content. Verify every quote or number against its source before use.
- Verify claimed file writes by reading the path yourself.
- `research-scout` and `docs-continuity-editor` run in a Docker sandbox (approved 2026-09-26). Stage inputs in `~\.openclaw\workspaces\<agent>\handoff\<job>\` (read-only to the agent at `/handoff/<job>/`) and name the output path under `/outbox/`. Collect results from `~\.openclaw\workspaces\<agent>\outbox\`. Anything the agent writes elsewhere lands in a throwaway sandbox copy and is lost.

## 6. Cap and steer

- At most 3 helpers in parallel per task; benchmarks are exempt.
- A drifting child (off scope, over time, wrong files): steer once with `sessions_send`. If it drifts again, cancel with `subagents` and rescope.

## 7. Close out

Run `python scripts\wf89_credit_reader.py --out <path>` and confirm the run reads CREDITABLE. Record the reason from step 1, the tokens, and Main's review cost. Once the daily scorecard has captured the run, record your judgment: `python scripts\wf89_run_outcome.py --run-id <run_id> --outcome accepted|rework|rejected --main-review-minutes <n>`. Without it, the scorecard cannot report cost per accepted task. `cost.total = 0` on ollama-cloud and meta means unpriced, not free; compare on tokens.
