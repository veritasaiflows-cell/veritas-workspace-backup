# Authority Boundaries For Isolated Agents

## Bottom Line

The Agent Knowledge Base and generated bootstrap packets are routing aids. They
are not approval, canon, execution authority, or permission to widen tool,
runtime, customer, finance, or external action boundaries.

## What The Folder Can Do

- Explain how to locate authoritative files.
- Provide reusable role templates.
- Provide assignment and closeout patterns.
- Summarize safe metadata-only self-improvement inputs.
- Point agents to proof packets and validators.

## What The Folder Cannot Do

- Override `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`, live skills, owner notes,
  or validated proof artifacts.
- Grant config, auth, credential, runtime, startup, service, channel, plugin, or
  network mutation authority.
- Grant cron schedule authority.
- Grant external delivery authority.
- Grant customer/public output authority.
- Grant finance, brokerage/account, paper/live execution, cash, sizing, risk, or
  capital deployment authority.
- Turn generated packets into canon.

## Access Model

Each persistent isolated agent has its own configured workspace and `agentDir`.
Its workspace is its default current working directory, not a hard sandbox.
Relative paths resolve inside that agent workspace. Absolute paths can reach
host locations unless sandboxing is enabled and host access is restricted.

Current central KB path:

```text
C:\Users\Veritas\.openclaw\workspace\06. Playbooks\Agent Knowledge Base\
```

If an agent is later sandboxed, do not assume this path remains readable. Use one
of these patterns instead:

- copy or generate a small role-specific digest into that agent workspace
- mount the KB read-only through an explicitly approved sandbox route
- update the bootstrap generator to produce a per-agent task packet

## Owner-Gated Actions

Stop before:

- config, auth, credential, channel, plugin, runtime, startup, service, or network mutation
- cross-agent visibility or agent-to-agent messaging config changes
- external bindings or external delivery
- cron or watchdog schedule creation/mutation
- telemetry capture-depth changes, collector config changes, or external telemetry export
- customer/private/suitability/tax/retirement/brokerage/account data use
- destructive cleanup, archive, delete, or broad file moves
- finance canon/portfolio/cash/sizing/risk mutation outside exact approved gates
- paper/live order submit, cancel, replace, close, sell, or account action

## Proof Standard

An agent handoff is not done until it states:

- objective handled or blocked
- sources read
- files or artifacts changed, if any
- commands or validators run
- stop lines preserved
- owner-gated decisions still needed

