# Deterministic Heartbeat — 2026-10-01

## Objective
Healthy/no-delta priority monitoring must run before any model invocation, silently; preserve genuine attention and promised task-completion handling. This replaces recurring Main heartbeat cadence, not event-driven wakes or the unrelated sentinel/PM jobs.

## Authority
Fresh authenticated Control UI owner `gateway-owner`, 2026-10-01 20:34 Phoenix: “Proceed to make heartbeat deterministic.” Do not attribute this authorization to Randall. Existing finance/account/execution boundaries remain unchanged.

## Current state
**Replacement jobs are enabled. Config cadence is 0m. The stored heartbeat job row has not reconciled.** zai/glm-5.3 QA accepted the applied watcher. Producer `fa2e582f-6899-4c80-b084-907845ef27ec` and watcher `5d9f20f9-d27a-4875-8ed9-9f007487c510` are enabled. Canaries passed, including a labeled SELF-TEST wake that was restored to the real NO_DELTA receipt. `agents.defaults.heartbeat.every` is `0m` and the config command said it applies without restart. Job `heartbeat-main` still shows `everyMs` 21600000 and next run `1790973217302`. No restart was performed.

- Corrected frozen packet verified by receiver hashes and Main comparison; no mount/config changes.
- First Builder code attempt timed out without source. Bounded retry returned watcher/test; both children settled, no work still running. Source copied without Main-authored repair.
- Actual-applied Node tests fail (exit 1, `FAIL: nodelta quiet`): test mock returns the wrong read shape. Integration probe with the real read envelope is quiet, but repeat-age-only changes incorrectly wake; legitimate `no_priority`/empty-selection receipts are also rejected. Additional state/fault bounds need review. Complete findings: `tmp/heartbeat-deterministic-20261001/main-rejection-a2.json`.
- GLM receiver readback verified, Main rehashed all six frozen QA files before/after review. Receiver cannot execute hashes, stated explicitly. Independent actual-applied a2 review **REJECT** confirmed four defects: incorrect read mock, healthy empty window falsely waking, repeat-only NEW/BLOCKED attention, and oversized/arbitrary state. Main accepted these findings, not the source.
- One bounded Muse repair a3 had a fresh independently computed six-file receiver hash canary (49,817 bytes). Exact lease/role/model established. Returned draft still fails Main pre-application probes: unchanged faults wake `[true,false,true]` within two minutes because suppressed faults clear their own saved identity; populated malformed empty-id selection with tampered authority is silently accepted. Draft not applied; no Main-authored source repair. Full two-file delivery is retained in sanitized child history; watcher also materialized under `tmp/heartbeat-deterministic-20261001/draft-a3/`.
- Rework cap reached: stop repeating the broad Muse bundle. No fresh acceptance QA was spent on the known-failing a3 draft. Recommended owner decision: task-scoped GPT-6.1 Sol **in the isolated Builder**, narrower fault-state/selection repair, keeping GLM independent QA and all persistent defaults unchanged. This override is **not yet approved**.
- Unchanged bridge regression passes and collaborator preimage hashes match; no production observation aging by tests.
- Fresh live automation schema now exposes `add`; earlier owner-manual creation gate is superseded. Use exact idempotent declarations and disabled canaries only after source acceptance. No CLI/RPC, unrelated-job repurposing or duplicate creations.
- Installed product docs explicitly confirm `heartbeat.every=0m` stops only recurring cadence, preserving targeted event/completion turns (`docs/gateway/heartbeat.md`, lines 23-29, 96-104). Script payload `state`/`notify`/`wake` semantics are documented (`docs/automation/cron-jobs/payloads.md`, lines 193-216). Native behavior still needs runtime canaries.

## Next action
Do not restart the gateway without an explicit owner decision. Recheck `heartbeat-main` after 13:33 Phoenix. If that slot still runs a model heartbeat, the 0m config did not reconcile the stored job. Rollback is `openclaw config set agents.defaults.heartbeat.every 6h` and disable only the two new jobs.

## Intended cutover (not approval or proof of deployment)
1. Native six-hour command producer invokes the unchanged heartbeat-only dry-run bridge.
2. One-minute read-only script watcher returns state only for valid `NO_DELTA`; bounded review-only attention otherwise, with dedupe/fault cadence.
3. Only after both jobs are verified: custodian patches only `agents.defaults.heartbeat.every` to `0m`, preserving all other config and event-driven completion handling. Verify the managed monitor reconciles; no unapproved restart.
4. Rollback restores only `every=6h` and disables only the two replacement jobs.

## Proof and pickup
- `tmp/heartbeat-deterministic-20261001/checkpoint.json` — exact current attempt and blocker.
- `tmp/heartbeat-deterministic-20261001/cutover-plan.json` — disabled-job specifications and sequence.
- `tmp/heartbeat-deterministic-20261001/source-manifest.json` / `builder-transport-proof.json` — verified immutable input.
- `tmp/heartbeat-deterministic-20261001/preimages.json` — original source nonexistence/protected collaborator hashes.
- `applied-source-a2.json`, `applied-test-a2.json`, `integration-probe-a2.json`, `main-rejection-a2.json` in the same proof directory — exact failed applied-source pickup.
- `qa-source-manifest-a2.json`, `qa-readback-a1.json`, `qa-verdict-a2.json` — verified supplied source/readback and independent rejection, receiver hash-execution limitation explicit.
- `builder-repair-manifest-a3.json`, `builder-repair-readback-a3.json`, `repair-lease-a3.json` — completed bounded repair transport/lease proof.
- `main-rejection-a3.json`, `draft-a3/probe.json`, `repair-lane-blocked-a3.json` — second substantive failure, no-application proof, released lease. Broad retry is stopped.
- `opus55-owner-model-choice.json`, `opus55-eligibility.json`, `opus55-route-blocker.json` — exact approved task model, verified router rejection and authority boundary; no Opus dispatch or receiver/runtime success.
- Lane transitioned to blocked and lease released; active admission ok, but post-write agent-message-ledger refresh failed (token ledger refreshed). Administrative acceptance is not clean; do not infer terminal completion.

## Limits
Source acceptance and acceptance-QA remain unproven; completed independent a2 QA rejected. Live quiet/attention enqueue behavior, event-driven cutover, recurring savings, and successful Main handling remain unproven. Queue acceptance is not end-to-end review completion. Historical terminal lane-register metadata debt is separate; active task admission was ok. Do not turn a receipt into repair, canon, capital, account, or execution authority.
