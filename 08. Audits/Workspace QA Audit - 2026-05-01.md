# Workspace QA Audit - 2026-05-01

## Scope

Independent bounded QA pass after Workflows 1-3.

Reviewed:
- workflow contract in `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- doctrine files (`AGENTS.md`, `SOUL.md`, `TOOLS.md`)
- current daily continuity in `memory/2026-05-01.md`
- representative operator/workspace skills
- active script/control surfaces tied to finance chains and workspace integrity

This audit does **not** redesign the whole automation architecture and does **not** change auth/network posture.

## Main finding

Workflows 1-3 materially improved the trust spine, but the workspace still has four real residual debt clusters:
1. trust-gate enforcement is still partly procedural rather than hard-enforced
2. atomic-write hardening is incomplete across important producers
3. schema-guard gains have not fully propagated through downstream consumers
4. control-surface/runtime reliability still requires operator skepticism

## Concrete residual risks

### 1. Canonical-note trust gates are not enforced end-to-end

The current chain still allows canonical note mutation before the trust summary is finalized.

Evidence:
- `scripts/run_summary_refresh.py` writes `canonical_note_mutation_allowed: False`
- but in `scripts/run_finance_refresh_chain.py` the Sunday chain runs `weekly_macro_snapshot.py`, `weekly_intelligence_brief.py`, `postmarket_snapshot.py`, and `daily_executive_brief.py` **before** `run_summary_refresh.py`
- `scripts/weekly_macro_snapshot.py` writes directly to `05. Intelligence/Weekly Macro Snapshots/...`
- `scripts/weekly_intelligence_brief.py` bootstraps/appends directly to `05. Intelligence/Weekly Intelligence Brief.md`

Why this matters:
- the workspace has a stated warning-grade internal-only trust contract
- the downstream trust object says canonical mutation is not allowed, but that rule currently lands after some canonical writes already happened
- this is orchestration drift, not just a wording issue

Bounded implication:
- next hardening pass should either move trust adjudication earlier or make note writers explicitly fail closed unless an upstream allow signal exists

### 2. Atomic-write coverage is still uneven on meaningful outputs

Workflow 2 reduced the highest-risk backlog, but important producers still write directly.

Examples:
- `scripts/technical_refresh.py`
- `scripts/trigger_sheet_refresh.py`
- `scripts/earnings_calendar_enrichment.py`
- `scripts/post_earnings_prep.py`
- `scripts/post_earnings_note_targets.py`
- `scripts/generate_dashboard.py`
- `scripts/dashboard_run_summary_consumer.py`
- `scripts/weekly_macro_snapshot.py`
- `scripts/weekly_intelligence_brief.py`
- `scripts/weekly_review_skeleton.py`

Why this matters:
- several of these files feed the active dashboard, weekly intelligence layer, or cross-note orchestration state
- a partial/interrupted write can still leave the system with mixed-surface truth even after the earlier migrations
- residual debt is now narrower, but it is still real

Bounded implication:
- treat the remaining producers as a ranked backlog instead of assuming the integrity pass is effectively done

### 3. Schema-guard gains have not propagated through all downstream consumers

Workflow 3 improved shared guards, but some consumers still assume happy-path shapes after load.

Evidence:
- `scripts/dashboard_core.py` still uses a local raw `json.loads` wrapper instead of the shared artifact loader path
- `scripts/trigger_sheet_refresh.py` still loads critical artifacts with direct `json.loads` and then assumes structures like `rec["ticker"]` in downstream maps
- daily continuity already notes broader residual raw nested-shape assumptions outside the Workflow 3 patch boundary

Why this matters:
- upstream degrade-to-partial behavior is only fully useful if downstream consumers also normalize malformed or non-dict payloads consistently
- one weak consumer can reintroduce crashy or misleading behavior even when upstream producers are more honest

Bounded implication:
- the next schema pass should focus on downstream consumers of `technical`, `deployment`, `earnings`, and dashboard payload artifacts rather than reopening every producer

### 4. Control-surface reliability remains a live operational risk

Evidence:
- `Workflow 10 — Subagent/session lifecycle reliability review` was added to the queue for a real control-surface inconsistency
- today’s continuity note records the earlier 3B subagent failure as a transient gateway websocket close (`1006`)

Why this matters:
- detached-lane completion state is still not something to trust blindly
- orchestration QA must verify artifacts and workspace state, not just session state

Bounded implication:
- keep treating runtime/session state as advisory until Workflow 10 closes the gap

## What improved enough to trust more

- Workflow 1 removed the policy-formatting crash path and made the missing-policy branch more honest
- Workflow 2 reduced high-value direct-write exposure in several key daily producers
- Workflow 3 established a better shared pattern for payload guards and partial-trust degradation

That is real progress. The system is better than it was this morning. It is just not clean enough yet to declare the trust spine finished.

## Recommended next tightening order

1. Hard-enforce canonical-note gating in the chain before weekly/canonical writers run
2. Run one more ranked atomic-write pass against remaining dashboard/weekly/note producers
3. Run a downstream-consumer schema pass on `dashboard_core.py`, `trigger_sheet_refresh.py`, and nearby dashboard consumers
4. Keep Workflow 10 active until session/control-surface behavior is proven, not merely observed once

## Bottom line

The workspace is no longer in the most fragile state, but it still has real integrity debt where trust policy, write semantics, and orchestration control do not fully line up.

The next gains should come from closing those specific gaps, not from broad architecture churn.
