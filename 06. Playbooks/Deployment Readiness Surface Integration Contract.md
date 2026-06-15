# Deployment Readiness Surface Integration Contract

## Phase 6 decision

For v1, keep the deployment-readiness surface as an operator JSON artifact plus protocol-level guidance.

Approved now:
- `tmp/deployment-readiness-surface.json`
- operator use through `06. Playbooks/Deployment Readiness Morning Operating Cadence.md`
- contradiction routing through the helper packet contract

Not approved now:
- a new dashboard panel presented as decision-grade truth
- workbook promotion that could be mistaken for canonical deployment judgment
- any direct apply helper that mutates the Execution Board

## Why this is the right boundary now

- The Execution Board already owns deployment judgment
- Macro/policy trust is still degraded enough that a second surfaced board would create false confidence faster than it would reduce friction
- The main unresolved timing-sensitive case (`NVDA`) proves that in-band machine posture still cannot speak last by itself

## Surface ranking rule

Authority order:
1. `03. Portfolio/Execution Board.md`
2. reviewed machine contradictions explicitly resolved by the operator
3. `tmp/deployment-readiness-surface.json`
4. raw ranking or raw trigger output beneath the surface

A lower layer may never silently outrank a higher one.

## Low-risk gating decision

No autonomous apply helper is approved in this phase.

The only future candidate for low-risk gating would be a proposal-only helper that drafts mechanical freshness/parity patches for operator review. Even that future helper must:
- write proposals only
- never edit canonical deployment notes directly
- show exact before/after text
- stop when a change would alter the actual deployment judgment rather than freshness wording

## Validation rule

A deployment-readiness artifact is valid for operator use only if:
- the matched run summary is terminal and clean enough for bounded review
- `canonical_note_mutation_allowed = false` remains explicit for scheduled windows
- any surfaced positive state can be cross-checked back to the Execution Board without ambiguity

If any of those fail, the artifact remains evidence only and may not be treated as an operator board.

## Reopen trigger for wider integration

Reopen this decision only if:
- daily use proves the JSON artifact is useful but too hidden
- the Execution Board and contradiction routing stay clean across repeated windows
- timing/date residue is narrow and consistently fail-closed
- there is a concrete need for visibility that does not require a second truth layer
