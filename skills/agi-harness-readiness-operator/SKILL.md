---
name: "agi-harness-readiness-operator"
description: "Assess AGI/ASI harness readiness from local gates, including prompt-book and token-efficiency evidence; no authority expansion."
---

# AGI Harness Readiness Operator

Use this skill when Randall asks about AGI/ASI harness readiness, agent self-improvement readiness, autonomy maturity, or what to modify in the local agent OS to move toward a stronger harness.

## Purpose

Produce a grounded, review-only readiness judgment from local proof surfaces and run serious autonomy-adjacent work through a repeatable harness loop. The target is not to claim AGI or ASI. The target is to assess and improve whether the agent OS can remember, checkpoint, delegate, verify, self-review, recover, and escalate owner-gated decisions without expanding authority.

## AGI Harness Mode

For serious multi-step work, explicitly run this sequence:

1. State the objective in concrete terms.
2. State the authority boundary and autonomy level.
3. Retrieve memory and exact source/proof surfaces.
4. Make a short plan with acceptance proof.
5. Open or reuse a checkpoint/lane when writes, helpers, or long work are involved.
6. Execute the smallest safe local step.
7. Verify with validators or direct artifact proof.
8. Log the outcome and remaining risk.
9. Update continuity or memory when the result changes durable state.

Do not treat this sequence as permission to act externally. It is a harness discipline, not an autonomy grant.

## First Read

Read or refresh these surfaces before making readiness claims:

- `tmp/agi-harness-readiness-packet.json`
- `tmp/agi-os-eval-gate-packet.json`
- `tmp/implementation-token-attribution-bridge.json`
- `tmp/cron-control-packet.json`
- `tmp/cron-freshness-spine.json`
- `tmp/otel-ops-control.json`
- `tmp/vector-memory-graph-packet.json`
- `tmp/agent-message-ledger-current.json`
- checkpoint packets for WF74-WF88, WF84-WF85, and implementation closeout when relevant

For an inspection-only phase-entry question:

1. Open the phase plan, latest acceptance, and preparation contract; distinguish preparation authority, activation requirements, and eventual outcome criteria before interpreting the overall harness grade.
2. Compare upstream packet timestamps and run `python scripts\agi_harness_readiness_packet.py --validate` without write flags for an in-memory gate summary. This recomposes existing sources; it does not refresh stale upstream evidence. Report remaining source-age limits.
3. Check relevant live automation state through `automations` list/get, then verify OTEL health separately using `tmp/otel-ops-control.json` and a read-only connection check to its declared endpoint. Separate scheduler completion, producer validation, and collector reachability: a successful digest may retain non-blocking diagnostic failures. Report a failed connection as unreachable, not a proven process death.

When a persisted readiness refresh is needed, run:

```powershell
python scripts\agi_harness_readiness_packet.py --write --write-md --validate
```

For a persisted refresh with warning or blocked cron/OTEL gates, refresh only proof artifacts first:

```powershell
python scripts\otel_ops_control.py --write --write-db --multi-window --validate
python scripts\cron_freshness_spine.py --write --validate
python scripts\cron_control_packet.py --write --validate
python scripts\agi_harness_readiness_packet.py --write --write-md --validate
```

Restarting collectors, changing cron schedules, changing runtime config, or widening telemetry capture requires exact owner approval.

If token attribution state is stale, refresh in this order:

```powershell
python scripts\coding_outcome_ledger.py --write --validate
python scripts\token_usage_ledger.py --write --write-md --validate
python scripts\implementation_token_attribution_bridge.py --write --write-md --validate
python scripts\agi_os_eval_gate_packet.py --write --validate
python scripts\agi_harness_readiness_packet.py --write --write-md --validate
```

## Readiness Interpretation

Report the packet as follows:

- `ready_review_only`: local proof is clean enough for review-only harness claims; no autonomy expansion is implied.
- `partial_ready_review_only_with_warnings`: useful harness progress exists, but one or more proof/runtime/cron/eval gates still need work.
- `not_ready_blocked`: a required proof surface is missing, blocked, or authority widened.

Always name the blocking or warning gate. Do not compress warnings into a vague score.

## Core Gates

Check and explain these domains:

- AGI OS eval gates: whether outcome-aware eval gates pass.
- Token attribution: whether implementation token gaps are stamped or explicitly classified unavailable.
- Cron/OTEL operations: whether local automation and telemetry are healthy; runtime/service fixes are owner-gated.
- Memory graph: whether graph/vector memory has source/workflow/action edges.
- Checkpointed execution: whether major chains have checkpoint proof.
- Helper auditability: whether helper lanes have auditable ledger events.
- Authority boundary: whether the packet preserves review-only limits.

## Autonomy Levels

Use these levels in recommendations:

- L0 answer only: safe for normal questions.
- L1 inspect and summarize: safe for local reads and proof review.
- L2 produce proof or recommendation: safe for review-only packets, proposals, and validation output.
- L3 apply reversible local workspace changes: requires lane lease, exact write scope, validation, and rollback-aware closeout.
- L4 external, capital, runtime, account, or authority-expanding action: owner-gated and blocked without exact approval plus the matching guard path.

## Checkpoint Rules

Use checkpointed execution when a task touches more than one durable artifact, spawns or consumes helper work, modifies scripts/contracts/skills, changes validator behavior, or could be confused with authority expansion.

A valid checkpoint names:

- workflow and workstream
- exact allowed writes
- first-read surfaces
- acceptance commands
- stop lines
- proof artifacts
- closeout note

## Boundaries

Never infer approval from readiness. This skill does not permit:

- model self-modification or model-training claims
- raw prompt, raw response, raw tool payload, secret, or header capture
- cron schedule mutation or runtime/collector config changes
- finance canon, portfolio, cash, sizing, paper, live, brokerage, account, customer, or external action
- applying skill proposals without explicit owner approval
- claiming AGI/ASI capability from local harness scaffolding

## Output Contract

Answer with:

1. Bottom-line readiness state.
2. Gate summary with pass/warning/fail counts.
3. Exact warnings/blockers and whether they are code-owned or owner-gated.
4. Next safe action set.
5. Authority boundary reminder when the result could be misread as autonomy approval.

Keep the response concise, blunt, and evidence-first.

## Prompt Book Readiness Evidence

When AGI-harness or ASI/RSI-style work involves reusable prompts, self-prompts, helper packets, or internal challenge-solving loops, check prompt-book proof before claiming the loop is reusable.

Use the four-stage readiness subset in [Prompt Book Operations, procedure step 2](../veritas-prompt-book-operator/SKILL.md#procedure). That skill owns refresh ordering and output paths; do not run its metadata-edit or skill-apply branches merely to assess readiness.

Interpretation:

- Registry `ok` means the prompt family set is visible and bounded.
- Eval gaps mean the loop is not fully regression-covered.
- Zero eval gaps means current prompt-book entries have metadata fixture coverage; it does not prove AGI/ASI, model training, self-modifying weights, authority expansion, or autonomous deployment.

## Token Efficiency And Ticker-Card Fallback Proof

When the readiness question involves token-efficiency promotion, changed-only prefilters, or ticker-card freshness fallback proof, inspect these review-only surfaces before claiming promotion readiness:

- `tmp/token-efficiency-review-packet.json`
- `tmp/cron-efficiency-review-runner.json`
- `tmp/pm-autonomous-worker-predispatch-prefilter.json`
- `tmp/ticker-card-freshness-owner-runner-prefilter.json`
- `tmp/agi-os-eval-gate-packet.json`
- `tmp/agi-harness-readiness-packet.json`

Refresh order when stale:

```powershell
python scripts\cron_efficiency_review_runner.py --write --validate
python scripts\agi_os_eval_gate_packet.py --write --validate
python scripts\agi_harness_readiness_packet.py --write --write-md --validate
```

For ticker-card freshness runner promotion claims, the fallback proof must show unchanged-input skip behavior, no model/agent turn spawned, validation `ok`, and a Phoenix market-date bucket in the signature so the skip cannot cross market days.

This is review-only proof. It does not mutate live cron schedules, live cron payloads, runtime config, model routes, finance/canon, portfolio, paper/live, brokerage/account, customer/external surfaces, raw prompt/response/tool payload capture, or approval state.
