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

When the current task involves automation, helper lanes, workflow advancement, implementation, audit, closeout, or proof-heavy validation, also read:
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
- `skills/disciplined-implementation/SKILL.md` when changing scripts, validators, manifests, workflow code, or boot/control surfaces.

Do not reread the full finance/navigation stack unless the task requires current finance judgment.

Implementation posture:
- Treat Veritas as a self-contained operating system with departments, owner truth surfaces, validators, queues, boot files, and hard finance/security boundaries.
- Reuse or extend existing scripts/helpers/validators/control surfaces before adding new ones.
- Prefer system-correct flattening over local-only small diffs when the local fix would leave duplicate truth, orphan scripts, or extra boot overhead.

## Current live workflow truth

Primary live surface:
- `06. Playbooks/Active Workflows.md`

Current active workflow priorities:
- **WF64** - Bounded Portfolio Agent Cron Architecture. Standing-approved autonomous workspace portfolio/canon maintenance posture is active through exact gated apply paths; cron remains proposal/verifier-first until repeated proof supports a narrower direct-apply category.
- **WF63** - Alpaca Paper Trading Readiness. Phase 1 GET-only proof is clean and now serves as the read-only paper endpoint/isolation foundation for WF67; no-submit guardrails remain active outside the exact WF67 wrapper and scoped paper-trade/pilot artifacts.
- **WF67** - Alpaca Paper Execution Guardrail. Paper-only submit/cancel is approved only through WF63/WF67 guardrails. First submit/cancel pilot completed cleanly; current active paper pilots include ETN passive accepted/unfilled and MSFT marketable-limit accepted/unfilled pending post-open reconciliation. Live trading, live endpoints/credentials, money movement, account mutation, replacement/close/liquidation paths, and inferred approval remain blocked.
- **WF58 / WF56** - dashboard/capital-recommendation surfaces and gated portfolio mutation helpers are subordinate to WF64/WF63/WF67 monitoring and exact-gated apply paths; generated packets and semantic bundles are not self-applying.

Current active sidecars:
- workspace simplification / portfolio communication layer
- Active Workflows migration
- WF72/WF73 OS restructure integration: Today-card prototype, boot/queue compression, department routing, script consolidation, and canon cleanup proposals remain review/proof-first until main-session apply gates are satisfied.

Blocked/operator-gated surfaces:
- WF49 FRED runtime environment persistence
- WF50 tmp helper archive cleanup
- root backup cleanup

## Current finance truth surfaces

Use these as canonical owner notes, not generated `tmp/` artifacts:

- Execution state, bands, stops, repair state: `03. Portfolio/Execution Board.md`
- Portfolio posture/model weights: `03. Portfolio/Portfolio Snapshot.md`
- Research universe/thesis/watchlist membership: `04. Research/Coverage and Watchlist.md`
- Risk rules: `07. Risk/Risk Rules.md`
- Weekly operating map: `05. Intelligence/Weekly Positioning Review.md`
- Macro regime: `02. Markets/Macro Regime Dashboard.md`

## Current finance posture snapshot

Use the latest `Active Workflows.md`, `03. Portfolio/Execution Board.md`, `03. Portfolio/Portfolio Snapshot.md`, `tmp/market-state.json`, `tmp/deployment-readiness-surface.json`, and `tmp/current-window-artifacts.*` before making any finance-state claim.

Known material posture from the latest continuity:
- JPM uses the formal trigger-review band **306.82-318.12** with **301.17** as near-term invalidation/reference stop and is currently **below stop / do not touch**, not deployable.
- ETN has standing-approved workspace maintenance proof for entry-band semantic sync, but no trade/account action authority.
- WF64/WF56 proposal, semantic preview, approval artifact, and post-apply proof surfaces are evidence/control surfaces only unless an exact gated apply path validates the named change.
- Generated dashboards/packets do not grant owner approval, deployment entitlement, sizing/risk authority, or trade/account action.

Boundary:
- Randall approved opening WF63 on 2026-05-14 as the Alpaca Paper Trading Readiness lane and explicitly approved Alpaca paper-only submit/cancel authority on 2026-05-17. WF63 remains the GET-only/isolation foundation; all paper submit/cancel routes through WF67 only, using exact paper endpoint `https://paper-api.alpaca.markets`, paper-specific credential names, fresh kill switch, scoped request artifact, wrapper/validator proof, redacted audit log, and post-submit/cancel reconciliation. Live trading, live credentials/endpoints, brokerage/account mutation, money movement, replacement/close/liquidation paths, and inferred approval remain blocked.
- Randall approved the guarded WF58/WF56 portfolio note/model mutation workflow on 2026-05-14 and expanded standing workspace-maintenance authority on 2026-05-16. Veritas / the main session may apply exact validator-backed portfolio/canon maintenance for `entry_band`, `earnings_state`, `ticker_state`, `sleeve`, `sizing`, and `sector_posture` only inside approved gates with exact artifacts, preview hash, standing/scoped approval artifact, validators, backups/rollback, post-apply proof, and audit trail.
- Generated capital recommendation packets and semantic preview bundles are still not self-applying: per-packet `owner_approval_granted=false`, `apply_allowed=false`, `canonical_mutation_allowed=false`, `portfolio_mutation_allowed=false`, and `trade_or_account_action_allowed=false` remain required unless a separate exact apply artifact exists and passes its validators.
- Financial-advisor posture is active through `veritas-financial-planning-pass`: Veritas is Randall's bounded financial advisor inside the workspace and may synthesize goals, constraints, risk, liquidity, concentration, macro, fundamentals, technicals, and official-source evidence into recommendations, portfolio-adjustment proposals, and exact main-session workspace portfolio/canon maintenance applies when WF64/WF56 standing-approved gates pass. This does not grant external owner approval, execution entitlement, brokerage/account action, trade authority, money movement, or ungated portfolio/canon mutation.
- Trade/account action, brokerage orders, money movement, and unscoped execution entitlement remain blocked.

## Current proof/artifact pointers

Generated proof/navigation surfaces:

- `tmp/dashboard-validation.json`
- `tmp/current-window-artifacts.json`
- `tmp/deployment-readiness-surface.json`
- `tmp/full-portfolio-view.*`
- `tmp/finance-discrepancy-resolver.*`
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.md`
- `tmp/capital-deployment-recommendation-validation.json`
- `tmp/run-chain-post-close.json`
- `tmp/run-summary-post-close.json`
- `tmp/auto-band-apply.*`
- `tmp/reference-band-note-sync.*`
- `tmp/alpaca-paper-readiness/phase-0-policy.json`
- `tmp/alpaca-paper-readiness/wf63-readiness-report.json`
- `tmp/alpaca-paper-readiness/phase-6-paper-execution-approval.json`
- `tmp/alpaca-paper-readiness/paper-execution-guard-validation.json`
- `tmp/alpaca-paper-readiness/paper-position-reconciliation.wf67-filled-position-001.json`
- `tmp/sec-skill-smoke-test-report.json`
- `tmp/dashboard-data.json`
- `tmp/veritas-command-center.html`

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

Truth-surface conflict procedure:
- use `06. Playbooks/Operating Procedures/Portfolio Truth Surface Ownership Procedure.md` when portfolio notes, generated artifacts, dashboards, or workflow surfaces disagree.

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
