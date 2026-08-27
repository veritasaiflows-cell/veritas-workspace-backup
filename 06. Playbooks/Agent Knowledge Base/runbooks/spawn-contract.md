# Isolated-Agent Assignment Contract

Use this contract before asking a persistent isolated agent or sub-agent to do
material work.

## Required Fields

```text
Objective:
Owner workflow:
Authority class:
Agent:
Model route:
Read first:
Allowed writes:
Forbidden writes:
Tool boundaries:
Deliverable format:
Proof commands:
Stop lines:
Closeout destination:
```

## Authority Classes

- `read_only`: inspect, summarize, and report only.
- `workspace_scoped`: write only inside the assigned workspace or named files.
- `review_only`: critique, recommend, and prepare proof; no external action.
- `owner_gated`: prepare an approval artifact and stop.
- `runtime_sensitive`: inspect/propose only unless exact runtime approval exists.
- `finance_sensitive`: review-only unless exact finance gate and proof exist.

## Minimal Prompt Template

```text
<Agent>, handle this bounded task.

Objective: <specific outcome>
Owner workflow: <WF## or route>
Authority class: <class>
Read first:
- <path>
- <path>

Allowed writes:
- <path or "none">

Forbidden:
- config/auth/runtime/channel/credential changes
- cron schedule mutation
- external/customer/public delivery
- finance/account/paper/live execution
- destructive cleanup

Return:
- bottom line
- sources read
- findings or changed files
- proof commands run
- stop lines preserved
- owner-gated decisions still needed
```

## Stop Conditions

Stop and return a blocker when:

- the task asks for a broader write scope than the contract gives
- a source file is missing and cannot be safely substituted
- the agent would need credentials, runtime config, external delivery, cron,
  customer data, finance execution, or destructive action
- generated packets conflict with higher doctrine or owner artifacts
- the requested output would imply readiness or approval not proven by artifacts

