# WF89 Attribution Contract v0.3 - ACCEPTED

Status: ACCEPTED by Randall (Telegram 2026-09-24 20:40 MST: "Draft rules approved"). Written 2026-09-24 ~21:00 Phoenix by Veritas Main; draft preserved at `attribution-contract-v0.3-draft.md`. The reader binds CLI rows by default (`--no-cli` opts out). Extends v0.2 (`coder-attribution-20260910/attribution-contract-v0.2.md`); v0.2 semantics for `runtime='subagent'` are unchanged except the S1 join-key fix below.

## Why

`openclaw agent --agent X` runs are stored as `task_runs.runtime='cli'` with no `subagent_runs` row and `label=NULL`. Under v0.2 they could never be credited, so the builder (which must dispatch via CLI to reach its Docker sandbox) was structurally invisible to accounting.

## S1 fix (applies to v0.2 too)

Join `subagent_runs` to `task_runs` on `payload_json.taskRunId`, not `subagent_runs.run_id`. Re-announced runs get a new registry `run_id` (`announce:requester-settle:...`). More than one registry row per `taskRunId` = MISMATCH (fail closed). Effect on 2026-09-24 live store: 27 rows INCOMPLETE -> CREDITABLE, 0 new MISMATCH.

## CLI binding (new)

1. **Dispatch record, written by Main before dispatch.** `scripts/wf89_dispatch_record.py` writes `state/wf89-dispatch-records/<dispatch_id>.json` (schema `veritas.wf89_dispatch_record.v1`): `agent_id`, full `session_key` (`agent:<id>:<key>`), non-empty `label`, `task_text_sha256` = sha256 of the message text with surrounding whitespace stripped (the task store keeps it stripped), `created_at_ms`, `dispatcher=main`. Exclusive create; never overwritten.
2. **Bind.** Exactly one `runtime='cli'` task row with the same `agent_id` and `child_session_key`, `created_at >= created_at_ms`, and identical normalized task-text hash. 0 matches = PENDING. >1 = MISMATCH. A row older than the record cannot be claimed.
3. **Witness + usage.** Identical to v0.2 (executor `session_nodes` -> `session_windows` -> `trajectory_runtime_events` `model.completed` usage for the run id within the bound window). Label comes from the dispatch record.
4. **Unrecorded CLI rows** are counted per agent and never credited.

## Threats and limits

- The dispatch record is Main-written and workspace-local; it proves Main *intended* the dispatch, not that no one else ran the same text on the same key. The hash + key + time window makes accidental collisions implausible; a deliberate forger with workspace write access is out of scope (same trust level as Main).
- `cost.total = 0` for ollama-cloud and meta providers means "not priced by the provider", not "free". Cost comparisons across lanes must use tokens until pricing is attached.
- Task rows expire 7 days after end (documented, not configurable: `docs/automation/tasks.md` "Retention"). Credit reports must be generated inside that window and kept as artifacts.
- `cleanup:"delete"` children lose their registry row and session node. Their transcripts survive as `*.deleted.<ts>` archives (`docs/tools/subagents/tool-reference.md`), which may support *observable-only* usage recovery, never credit.

## Proof (2026-09-24)

- Tests: `scripts/test_wf89_credit_reader.py` 15 + `scripts/test_wf89_cli_attribution.py` 8 = 23 passed.
- Live builder run `8a95105a-80f6-466e-805c-fd16fb1f6c88` (job `builder-credit-20260924`, dispatch `1da81f34-...`): CREDITABLE, label from record, 112,665 tokens, model muse-spark-1.3-contributor.
- Live scout spawn `3a8433bf-a874-40a4-94f2-c38a71824f96` (`cleanup:"keep"`): CREDITABLE via v0.2 path, 585,284 tokens.

## Owner decision

Accepted 2026-09-24 20:40 MST. Nothing in v0.3 changes config, runtime, or authority; credit remains accounting evidence only, never approval.
