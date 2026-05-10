# Executive Brief

## Role

This is the fastest high-level operating view for Randall and Veritas.

Use it to answer:
- what matters now
- what is trusted enough for review
- what needs owner judgment
- what workflow or data risk is blocking cleaner action

Boundary:
- this is an orientation surface, not canonical truth
- dashboards summarize; owner notes decide
- no trade, portfolio, deployment, or approval authority is inferred here

Canonical owners:
- deployment state: [[03. Portfolio/Deployment Trigger Sheet]]
- portfolio posture: [[03. Portfolio/Portfolio Snapshot]]
- technical discipline: [[03. Portfolio/Technical Entry and Invalidation Sheet]]
- weekly stance: [[05. Intelligence/Weekly Positioning Review]]
- macro/risk: [[02. Markets/Macro Regime Dashboard]] and [[07. Risk/Risk Rules]]
- workflow order: [[06. Playbooks/OpenClaw Parallel Pilot Queue]]

## Current reality

The system is stronger than it was this morning, but it is not clean enough to loosen authority.

Today's work tightened the truth architecture: post-close authority vocabulary, run-summary terminal semantics, Command Center visibility, stale-source fail-soft classification, regime-scoring ownership, state-history pathing, retrieval metadata, reinstall recovery, and tmp/script boundary controls all moved forward.

Finance posture remains owner-gated:
- **JPM** and **ETN** are the current deployable-now / conditional-add names in the owner layer.
- **ETN** must stay disciplined inside its written band; no chase above the band.
- **NVDA** is wait / no-chase after the fresh rerun showed it above band.
- **GS / MSFT / GOOG** remain review-first / almost-deployable context, not automatic deployment.
- **XOM** remains repair/bench/do-not-touch until follow-through and evidence improve.

## Trust state

- Dashboard validation is structurally usable, but source trust is **partial / review_required**.
- Policy and credit data still carry FRED/runtime dependency issues; do not treat macro precision as clean.
- Telegram is enabled only as a setup-pending exception; delivery is not proven.
- WF40 security automation is warning-grade and still needs one clean ordinary scheduled repeat before closure.
- Workspace boundary warnings are now mostly cleanup residue: root `backups/` plus six executable helpers in `tmp/` pending owner-approved archive cleanup.

## Current next move

1. Keep finance decisions in the owner notes: read the Trigger Sheet, Portfolio Snapshot, Technical Sheet, and Risk Rules before treating any dashboard state as actionable.
2. Wait for the next ordinary WF40 scheduled security proof; do not close WF40 from the controlled rerun alone.
3. Run the WF43 durable state-history append/validate proof before wiring any consumer to `data/state-history/state-history-v1.jsonl`.
4. Archive the six `tmp/*.py` helpers only after owner approval and manifest/hashes under WF50.
5. Keep WF49 operator-gated until the exposed FRED key is rotated/replaced outside chat and runtime persistence is handled safely.

## Operating rule

Freshness and truth beat convenience. If a source is partial, manual, stale, setup-pending, or warning-grade, say that plainly and route to the owner surface instead of cleaning up the story.

## Navigation

Read in this order:
1. [[01. Dashboards/Executive Brief]]
2. [[01. Dashboards/This Week]]
3. [[01. Dashboards/Next Actions]]
4. [[05. Intelligence/Weekly Positioning Review]]
5. [[03. Portfolio/Deployment Trigger Sheet]]
6. [[03. Portfolio/Portfolio Snapshot]]
7. [[03. Portfolio/Technical Entry and Invalidation Sheet]]
8. [[02. Markets/Macro Regime Dashboard]]
9. [[07. Risk/Risk Rules]]

## Last updated

- 2026-05-09 — tightened after the WF40/WF43/WF48/WF50 and retrieval/runtime hardening session. Reframed this as a lean orientation surface: owner notes govern finance truth, source trust is partial/review-required, WF40 remains scheduled-repeat pending, WF43 durable proof remains pending, and cleanup/credential residue stays owner-gated.
