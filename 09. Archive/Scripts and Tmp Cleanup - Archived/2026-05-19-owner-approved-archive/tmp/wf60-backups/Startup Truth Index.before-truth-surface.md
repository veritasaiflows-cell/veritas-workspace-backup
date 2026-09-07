# Startup Truth Index

## Purpose

This is the thin startup and post-compaction pickup map for Veritas.

Use it to recover orientation without rereading every large control file. It points to canonical owners; it does not replace them.

## Authority rule

- This file is an orientation index, not canonical portfolio truth.
- If this file conflicts with an owner note, the owner note wins.
- If this file conflicts with `06. Playbooks/Active Workflows.md` on workflow state, `Active Workflows.md` wins.
- If this file conflicts with `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`, or `MEMORY.md`, the doctrine hierarchy wins.

## Read order after compaction

Minimum recovery path:

1. `SOUL.md` / `USER.md` / `TOOLS.md` if not already present in context.
2. This file.
3. `06. Playbooks/Active Workflows.md` for live workflow truth.
4. Today's daily note in `memory/YYYY-MM-DD.md` for material deltas.
5. Only then drill into owner notes or artifacts required by the user's current task.

Do not reread the full finance/navigation stack unless the task requires current finance judgment.

## Current live workflow truth

Primary live surface:
- `06. Playbooks/Active Workflows.md`

Current active workflow priorities:
- **WF58** - dashboard freshness, entry-band automation, capital recommendations, and discrepancy resolver.
- **WF59** - continuity and compaction hardening, opened to reduce compaction pain and file sprawl.

Current active sidecars:
- workspace simplification / portfolio communication layer
- Active Workflows migration

Blocked/operator-gated surfaces:
- WF49 FRED runtime environment persistence
- WF50 tmp helper archive cleanup
- root backup cleanup

## Current finance truth surfaces

Use these as canonical owner notes, not generated `tmp/` artifacts:

- Deployment state: `03. Portfolio/Deployment Trigger Sheet.md`
- Portfolio posture/model weights: `03. Portfolio/Portfolio Snapshot.md`
- Technical bands/stops/repair state: `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- Watchlist navigation/state labels: `02. Markets/Watchlist.md`
- Risk rules: `07. Risk/Risk Rules.md`
- Weekly operating map: `05. Intelligence/Weekly Positioning Review.md`
- Macro regime: `02. Markets/Macro Regime Dashboard.md`

## Current finance posture snapshot

As of the May 12 close surfaces:

- ETN remains first capital-deployment priority, manual-only.
- MSFT is owner-promoted deployable-now / staged manual candidate; below-200-day context argues for tranche discipline, not full-size execution.
- JPM is deployable-now on refreshed surfaces but still secondary until explicit capital sequencing.
- NVDA is wait / no-chase.
- GOOG and GS are almost deployable.
- BRK.B, LMT, XOM, and watch-lane LNG remain repair/bench/do-not-touch as applicable.
- Direct Tech is at the 25% single-sector cap; broader AI-power correlation discipline remains active.

Boundary:
- no trade, account action, owner-approval inference, sizing/sleeve/cash/risk-rule mutation, or execution entitlement is granted by any generated artifact.

## Current proof/artifact pointers

Generated proof/navigation surfaces:

- `tmp/dashboard-validation.json`
- `tmp/current-window-artifacts.json`
- `tmp/deployment-readiness-surface.json`
- `tmp/full-portfolio-view.*`
- `tmp/finance-discrepancy-resolver.*`
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`
- `tmp/run-chain-post-close.json`
- `tmp/run-summary-post-close.json`
- `tmp/auto-band-apply.*`
- `tmp/reference-band-note-sync.*`

Trust rule:
- generated artifacts are evidence/proof/review surfaces, not portfolio canon.

## Continuity model

Use this hierarchy to avoid file sprawl:

1. `Active Workflows.md` = live workflow status.
2. One continuity note per active workflow = durable pickup state.
3. `memory/YYYY-MM-DD.md` = daily factual deltas only.
4. `MEMORY.md` = durable preferences/decisions only.
5. `tmp/` = generated proof, reports, proposals, and review packets.
6. `09. Archive/` = owner-approved retired material only.

New file rule:
- create a new durable file only when it is an owner surface, active workflow continuity note, final audit, reusable procedure, or durable research note.
- otherwise append to the existing owner surface, write one daily bullet, or generate under `tmp/`.

## Config/compaction posture

WF59 owns current compaction review.

Current Phase I finding:
- no explicit `agents.defaults.compaction` object is currently configured, so defaults are in effect.
- staged config work should be proposal-first and validated by dry-run before applying.
- runtime config mutation outside the workspace remains approval-gated unless explicitly authorized.

Key candidate knobs:
- `agents.defaults.compaction.reserveTokensFloor`
- `agents.defaults.compaction.keepRecentTokens`
- `agents.defaults.compaction.recentTurnsPreserve`
- `agents.defaults.compaction.maxHistoryShare`
- `agents.defaults.compaction.truncateAfterCompaction`
- `agents.defaults.compaction.maxActiveTranscriptBytes`

## Startup behavior rule

After compaction, prefer this file plus `Active Workflows.md` before broad vault reads. Drill into full files only for the current task.
