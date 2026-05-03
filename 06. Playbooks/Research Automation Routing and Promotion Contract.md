# Research Automation Routing and Promotion Contract

## Purpose
Define where an approved research packet may go and, just as importantly, where it must not go.

## Core rule
Routing is surface selection, not truth mutation.
Promotion into a review surface is not permission to rewrite a canonical note.

## Allowed routes

### 1. No route
Use when:
- materiality is too low
- confidence is too weak
- the event is duplicate / stale / already reflected
- the packet would only add noise

### 2. Archive / digest only
Use when:
- the item is real but low urgency
- it belongs in a weekly summary, not a live operating surface

### 3. Dashboard watch / review item
Use when:
- the item is medium materiality
- it affects what Randall should look at next
- it does not yet justify thesis or posture mutation

### 4. Weekly intelligence input
Use when:
- the item matters to regime, theme, or medium-horizon thesis maintenance
- immediacy is lower than same-session dashboard review

### 5. Thesis-review queue
Use when:
- the item is high materiality
- the evidence challenges or strengthens an active thesis materially
- a human decision is required before any posture change

### 6. Canonical freshness patch candidate
Use only when:
- the item is high-confidence
- the target issue is freshness/alignment, not a new thesis judgment
- the affected note is stale relative to already-approved evidence or owner surfaces

## Not allowed in v1
- direct promotion into Trigger Sheet action-state changes
- direct promotion into Portfolio Snapshot weight or posture changes
- direct macro-regime wording changes from packet output alone
- automatic queue movement based on packet output
- canonical note mutation without explicit approval

## Routing matrix
| Confidence | Materiality | Default route |
|---|---|---|
| low | any | stop / no route |
| medium | low | archive / digest only |
| medium | medium | dashboard watch or weekly intelligence |
| medium | high | thesis-review queue only if contradiction is explicit; otherwise stop for review |
| high | low | archive / digest only |
| high | medium | dashboard watch or weekly intelligence |
| high | high or critical | thesis-review queue; freshness patch candidate only if the issue is clearly mechanical/alignment-only |

## Handoff posture by surface
- **Dashboard / workbook / weekly brief** -> review surfaces only
- **Thesis-review queue** -> human-decision intake surface only
- **Freshness patch candidate** -> proposal surface only
- **Canonical note** -> manual approval required

## Stop lines
Stop instead of routing when:
- the packet would create a second truth layer
- routing would smuggle in a deployment or thesis judgment
- the note target is not clearly owned
- macro/policy degradation makes the interpretation unsafe
- the event is based on stale secondary-source chains

## Acceptance use
This contract is approved for Workflow 16A when:
- each route has explicit eligibility logic
- not-allowed routes remain explicit
- review surfaces stay distinct from truth owners
- freshness patch candidacy is constrained to alignment/mechanical issues
