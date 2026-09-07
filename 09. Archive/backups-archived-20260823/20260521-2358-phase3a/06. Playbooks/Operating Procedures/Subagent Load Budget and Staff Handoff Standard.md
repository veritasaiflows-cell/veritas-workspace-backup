# Subagent Load Budget and Staff Handoff Standard

## Purpose
Prevent new sessions/helper lanes from being overloaded with the entire workspace, stale history, or unclear authority. Use small, file-grounded handoffs by staff lane.

## Core Rule
A helper lane should receive only the doctrine slice, owner surfaces, exact task files, stop lines, output contract, and proof requirements needed for its assignment.

## Default Load Budget
- Doctrine: cite `SOUL.md`/`AGENTS.md` boundaries in the handoff, but do not paste broad doctrine unless needed.
- Skills: read at most one relevant skill up front unless the lane explicitly needs multiple domains.
- Files-to-read-first: 3-8 exact files for normal lanes; 10-15 max for broad audit lanes.
- Outputs: one summary artifact or final response plus exact proof paths.
- Runtime: use fresh isolated sessions by default; use forked context only when transcript context is truly required.
- Ownership: no two helper lanes may write the same canonical owner surface.

## Required Handoff Fields
Every helper-lane prompt should include:

1. **Staff lane / role**
2. **Objective**
3. **Files to read first**
4. **Allowed actions**
5. **Forbidden actions / stop lines**
6. **Output contract**
7. **Acceptance proof**
8. **Timeout / partial-output expectation**
9. **Merge expectation** - read-only, patch proposal, artifact write, or implementation
10. **Authority boundary** - especially finance/trading/config/destructive boundaries

## Staff Lane Defaults

| Staff lane | Typical files-to-read-first | Default merge mode |
|---|---|---|
| Official Source Desk | WF70 note, company source metadata, target capture scripts/artifacts | Artifact or patch proposal |
| Advisor Alert Desk | WF68 note, alert artifacts, Execution Board, WF67 guardrails | Artifact/implementation with tests |
| Analytics / Probability Desk | WF69, WF55, state-history artifacts, validators | Artifact/validator; no probability claims |
| Portfolio / Canon Steward | Execution Board, Portfolio Snapshot, WF56/WF58/WF64, validators | Exact gated patch proposal or bounded apply if approved |
| OS Operator / Automation Desk | Active Workflows, target continuity note, runtime docs, relevant scripts | Patch proposal/implementation; config gated |
| Independent QA Desk | Target files/artifacts only plus governing boundaries | Read-only report unless explicitly scoped |

## Anti-Overload Rules
- Do not ask a helper lane to read all of `memory/`, all workflows, all scripts, and all finance notes unless it is explicitly a broad audit lane.
- Do not combine implementation, QA, workflow governance, finance judgment, and archive cleanup in one helper.
- Do not ask a helper to decide final queue priority; Veritas main integrates.
- Do not let a helper infer owner approval from validation success.
- Do not give write access to a helper lane touching canonical finance notes unless the scope, target files, and validators are exact.

## Closeout Standard
A helper closeout must state:
- what it inspected
- what it changed or did not change
- proof/tests/validators
- blockers/trust gaps
- exact next action
- whether output is safe to merge, needs audit, or is review-only

## Security Boundary
Config/auth/channel/network/service/credential changes are never helper-default. They require explicit owner approval and main-session review.
