---
name: "ic-swarm-orchestrator"
description: "Require verified Opus challenger routing for serious finance gates."
---

# IC Swarm Orchestrator Update - Verified Opus Challenger Gates

## Serious Finance Workflow Opus Gate

For serious finance workflow contracts, trade-grade OS promotion gates, authority-sensitive decision-card systems, and WF84/WF85-class work, the challenger lane should use the verified model path `claude-cli/claude-opus-4-8` when available.

This is a challenger/reviewer requirement, not a routine implementation default. Use Opus for false-ready detection, authority-drift review, state-precedence critique, source/freshness gate critique, and schema/contract stress testing before promotion or card-generation gates.

## Required Verification

After spawning or routing the challenger lane, verify the actual subagent/session registry model path. A label containing `Opus` is not sufficient proof.

Acceptance rule:
- If the registry model is exactly `claude-cli/claude-opus-4-8`, the lane may count as Opus challenger proof.
- If the registry model differs, the lane may still be useful, but classify it as standard challenger evidence and do not count it as Opus acceptance proof.
- If Opus is unavailable, record the fallback reason and keep the same bounded challenger contract.

## Handoff Packet Requirement

For WF84/WF85-class spawns, include these fields in the handoff:

```text
Required model: claude-cli/claude-opus-4-8
Role: read-only challenger / authority-drift reviewer
Verification: after spawn, confirm actual registry model path equals required model
Fallback: if mismatched/unavailable, classify as standard challenger output, not Opus proof
Stop lines: no capital/trade/paper/live/account action, no canon/portfolio mutation, no owner approval inference
```

## Closeout Requirement

The final synthesis should state:
- expected challenger model
- actual verified model path
- whether the lane counts as Opus proof
- key accepted/rejected challenger findings
- any remaining downgraded trust state

This complements the existing lane-register handshake. It does not replace lane leasing, exact allowed-write declarations, runtime metadata stamping, proof artifacts, or main-session verification.

## Boundary

Challenger/review routing only. This does not authorize capital deployment, trade/order execution, paper/live/account action, portfolio/canon mutation, config/runtime mutation, autonomous spawning, or owner approval inference.
