---
name: "cron-automation-manager"
description: "Production GPT-5.6 cron routing plus preserved bounded Spark canary safeguards."
---

# Cron Automation Manager

## GPT-5.6 Production Cron Routing

Use these production defaults unless a job-specific, validated contract proves a narrower route:

- Keep deterministic command-backed cron jobs model-free.
- Use `openai/gpt-5.6-luna` at low reasoning only for proven deterministic `agentTurn` status, proof, digest, or compact quiet-output jobs.
- Use `openai/gpt-5.6-terra` at medium reasoning for broader interpretive `agentTurn` work that requires synthesis or judgment.
- Do not use `openai/gpt-5.6-sol` for routine cron; reserve Sol for main-session final integration and high-stakes judgment.
- Use `openai/gpt-5.5` as the primary fallback and `openai/gpt-5.4` as the explicit rollback/control route.
- Treat any fallback as a change in evidence source, not an expansion of authority.
- Require scheduler canary proof, prompt-contract validation, output-artifact validation, and clean authority boundaries before promoting a job to Luna or Terra.
- If Luna misses a quiet contract, tool loop, artifact, or validator, stop expansion and route the job to Terra or the approved fallback.

This routing doctrine does not authorize creating, deleting, rescheduling, enabling, disabling, or editing cron jobs. Any schedule or payload mutation still requires the exact approved cron change gate, rollback plan, and post-change proof.

The Spark rules below remain a bounded experimental canary path only. Spark is not the production default and must not displace the Sol/Terra/Luna routing hierarchy without new measured proof and explicit approval.


## Spark Cron Canary And Helper Effort Rule

Use `codex/gpt-5.3-codex-spark` only for bounded, script-owned cron canaries and bounded QA/audit/pre-work helper lanes until monitor proof is clean. Do not migrate cron globally.

### Mandatory Thinking Posture

Every Spark cron job or Spark helper/subagent lane must use `xhigh` thinking.

Reason:

- Spark is cheap enough that lower effort is not worth the quality risk by default.
- The 2026-06-07 WF79 effort comparison showed Spark quality improved materially at `xhigh`.
- Spark high still repeated a path-hallucination family; Spark xhigh produced the best Spark result with clean referenced paths.

Do not lower Spark thinking effort unless repeated measured proof shows lower effort is equally reliable for the same task family.

### Eligible Spark Cron Jobs

Use Spark only for:

- isolated `agentTurn` jobs where scripts do the real work
- exact-command proof refreshers
- known JSON artifact inspection
- compact `NO_REPLY` or status response contracts
- jobs with no external delivery by default
- jobs with no cron/config/auth/runtime mutation
- jobs with no canon/portfolio mutation
- jobs with no paper/live/brokerage/account action
- jobs with no owner approval inference

### Eligible Spark Helper Lanes

Use Spark only for:

- bounded QA/audit/pre-work challenger lanes
- narrow proof/canary lanes
- path/contract sanity checks where main session verifies output
- distinct-output JSON artifacts, unless a later workflow explicitly widens scope

### Do Not Use Spark For

Do not use Spark for:

- primary implementation ownership
- main-session continuation or PM dispatcher judgment
- finance synthesis
- portfolio/canon maintenance judgment
- paper execution readiness interpretation
- weekly multi-skill finance refreshes with broad evidence synthesis
- any job whose correctness depends on nuanced stop-line interpretation rather than script validators
- any lane where a wrong path, fragile command, or over-broad scope would create operational risk without main verification

### Canary Monitoring Pattern

1. Pick one or two low-risk isolated jobs with recent successful baseline runs.
2. Set `payload.model` to `codex/gpt-5.3-codex-spark` and `payload.thinking` to `xhigh`.
3. Preserve schedule, session target, delivery, timeout, and stop lines.
4. Record baseline model, required thinking posture, and duration in a monitor artifact.
5. Let jobs run in their natural window; do not force market-window finance jobs just to test model routing.
6. Validate with `python scripts\cron_spark_canary_monitor.py --write --validate` plus `tmp/cron-freshness-spine.json` and recent cron run history.
7. If monitor status is blocked, roll the canary jobs back to the prior model before expanding.
8. Expand only after at least one clean natural run per canary and no missed warnings, false `NO_REPLY`, duration regression, path/command hallucination, or authority drift.

## Cron Long-Work Status Rule

Cron may refresh long-work status packets and run explicitly contracted, review-only bounded slices. Cron must not use long-work status as approval, execution, or mutation authority.

Use the long-work runtime when a scheduled or cron-adjacent command may exceed normal foreground tool limits, including:

- provider-backed vector memory indexing
- broad finance refresh chains
- OTEL multi-window summaries
- runtime/token scorecards
- heavy validator bundles
- PM or WF proof refreshes that span many artifacts

Required pattern:

1. Contract the job as review-only/proof-only.
2. Run it in bounded slices with checkpointed status.
3. Write `tmp\long-work-job-status-packet.json` after each meaningful state change.
4. Keep exact resume commands in the status packet.
5. Let WF88 or the owning workflow route resumable, warning, stale, or blocked jobs.
6. Do not mutate cron schedules from the status packet alone.

Canonical status command:

```powershell
python scripts\long_work_job_status_packet.py --write --write-md --validate
```

Canonical provider-backed indexing pattern:

```powershell
python scripts\vector_memory_ollama_job_runner.py start --profile medium --embedding-provider ollama --embedding-model nomic-embed-text:latest --max-seconds 60 --batch-size 8 --write --validate
python scripts\vector_memory_ollama_job_runner.py resume --job-id <job-id> --max-seconds 60 --batch-size 8 --write --validate
```

## Cron Interpretation

Interpret long-work status this way:

- `complete` plus validation `ok`: usable proof.
- `complete` plus validation `warning`: usable only with warning stated.
- `resumable`: not failed; schedule or main can resume if the job is contracted.
- `running`: monitor, do not duplicate the writer.
- `blocked`: route repair or owner decision.
- `stale`: refresh status before claiming current truth.

## Finance And Runtime Use

Finance scripts, runtime ledgers, OTEL digests, and token scorecards should publish checkpoint status when they are long enough to risk session or tool timeout. This improves continuity without widening finance authority.

## Boundary

These cron rules authorize bounded model/canary selection, status refresh, and review/proof/routing only. They do not authorize cron expansion, cron schedule mutation, external delivery, config/auth/runtime/channel/service mutation, telemetry capture expansion, finance/canon/portfolio/cash/sizing/risk mutation, paper/live/brokerage/account action, implementation ownership, delete/archive/apply actions, or owner approval inference.

## Prompt-Contract Lint Pattern

Cron may be designed to refresh prompt-book lint and eval-gap proof only after a separate cron schedule/change gate approves it.

Allowed review-only commands:

```powershell
python scripts\prompt_book_registry.py --write --write-md --validate
python scripts\prompt_book_eval_fixtures.py --write --write-md --validate
python scripts\prompt_book_linter.py --write --validate
python scripts\prompt_book_eval_gap_packet.py --write --write-md --validate
python scripts\prompt_book_pm_job_packet.py --write --write-md --validate
```

The cron prompt-contract check should require objective, source artifacts, allowed tools, forbidden tools, output schema, proof, stop lines, eval status, and authority boundary for prompt families or helper packets.

A cron proof refresh may report zero eval gaps or future prompt-book debt. It must remain review-only unless a separate owner-approved schedule/payload gate exists.

Stop lines: no schedule mutation from this proposal alone, no raw prompt/response/tool payload capture, no skill/doctrine auto-apply, no finance/canon/portfolio mutation, no paper/live/account action, no runtime/config/channel mutation, no external delivery, and no owner approval inference.
