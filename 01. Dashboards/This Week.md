# This Week

## Role in the stack

This note defines the current operating outcomes.

Use it to answer:
- what has to be true by the end of this operating window?
- what would count as real progress?
- what should not be widened yet?

Boundary:
- short outcome map only
- not a deployment board
- not a catalyst calendar
- not a workflow registry

## Current operating window

The work has shifted from building more surfaces to making the existing surfaces truthful, fresh, and owner-gated.

The main objective is not more automation for its own sake. It is cleaner decision support: fewer fake-green states, better freshness labels, clearer ownership boundaries, and faster retrieval without script clutter.

## Primary outcome

Finish this operating window with a tighter Veritas OS:
- live dashboards route back to canonical owner notes instead of becoming a second portfolio truth layer
- scheduled/security automation proves itself through ordinary repeat runs, not just controlled reruns
- durable state history exists only after append/validate proof
- retrieval metadata and SQLite/Obsidian lookup help us find evidence faster without replacing source Markdown/JSON
- scratch helpers and generated residue are classified, archived, or promoted only when they truly reduce drift

## Current priorities

1. **Keep capital deployment owner-gated**
   - Use [[03. Portfolio/Deployment Trigger Sheet]], [[03. Portfolio/Portfolio Snapshot]], [[03. Portfolio/Technical Entry and Invalidation Sheet]], and [[07. Risk/Risk Rules]] for real state.
   - Treat dashboard and generated artifacts as review support only.
   - JPM and ETN are the current owner-layer deployable/conditional-add names; NVDA remains wait/no-chase.

2. **Close WF40 honestly, not prematurely**
   - Controlled proof is warning-grade and no longer critical.
   - Closure still requires the next ordinary scheduled run to repeat cleanly.
   - Telegram, owner-allow visibility, and runtime/security warnings stay explicit.

3. **Prove WF43 durable state history before consumer wiring**
   - Approved path: `data/state-history/state-history-v1.jsonl`.
   - Next proof is compile/test, sample row, append durable row, validate JSONL, and inspect provenance/authority.
   - No model-driven deployment, hindsight rewriting, or owner-approval inference.

4. **Keep retrieval useful but subordinate**
   - Use `workspace_index.py` / `artifact_index.py` as locators, not truth authorities.
   - SQL and retrieval hits must route back to source notes/artifacts before judgment.
   - `## Retrieval Notes` blocks should help future lookup without creating bureaucratic sludge.

5. **Clean script/tmp boundaries without clutter**
   - The six `tmp/*.py` helpers should not be promoted as standalone scripts.
   - The useful model-routing drift idea was folded into `workspace_governance_truth_check.py`.
   - WF50 owns archive cleanup after owner approval.

6. **Keep credential/runtime work operator-gated**
   - FRED runtime persistence remains WF49.
   - The exposed FRED key should be rotated/replaced outside chat before persistent runtime work.

## Success condition

A successful window means:
- WF40 either repeats cleanly or remains open with a named blocker
- WF43 has a validated first durable row or remains explicitly proof-pending
- dashboards stay lean and owner-subordinate
- source trust remains visible as partial/review-required where appropriate
- tmp/script cleanup has an owner-approved archive path, not hidden clutter
- no workflow widens into execution, sizing, canonical mutation, or approval inference

## Things to avoid

- calling controlled reruns the same as scheduled proof
- treating clean dashboard validation as clean source trust
- promoting scratch scripts just because they were useful once
- creating a second market-data truth surface
- letting convenience override provenance, freshness, or owner approval

## Last updated

- 2026-05-09 — rewritten after the runtime/retrieval/workflow hardening session to focus on truth, freshness, owner-gated deployment, scheduled-proof discipline, durable state-history proof, and low-clutter cleanup.
