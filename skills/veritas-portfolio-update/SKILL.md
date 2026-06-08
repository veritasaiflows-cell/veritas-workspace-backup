---
name: veritas-portfolio-update
description: Orchestrate the operational synchronization of the portfolio board. Use this to reconcile script artifacts with the live note layer, detect stale entry bands and earnings-blocker transitions, and keep the Execution Board, Portfolio Snapshot, and Coverage and Watchlist aligned with their real ownership boundaries.
---

# Veritas Portfolio Update

This skill owns operational coherence.

Its job is to keep the note layer and machine layer aligned without creating duplicate truth.
It does **not** decide investment conviction by itself.
It ensures the infrastructure for conviction is current, consistent, and honest.

Authority update:
- Veritas / the main session may apply exact, validator-backed portfolio note/model adjustments for the bounded categories `entry_band`, `earnings_state`, `ticker_state`, `sleeve`, `sizing`, and `sector_posture` only within approved gates.
- Approved band-maintenance doctrine: the system owns fresh reference bands and routine technical entry-band/stop maintenance when the proposal is source-fresh, posture-preserving, `canonical_apply_eligible=true`, and validator-clean. Randall handles exceptions, policy changes, invalidation/reclaim judgment, and capital/execution decisions.
- Routine freshness/status sync remains narrower than high-consequence portfolio mutation.
- Brokerage/account/order/money-movement actions remain blocked no matter how clean the note/model gate is.
- Planner/advisor posture is separate from board sync: use `veritas-financial-planning-pass` for holistic recommendations across goals, liquidity, drawdown tolerance, concentration, and tax/legal/outside-account constraints; this skill only synchronizes owned workspace truth surfaces.

Core rule:
- scripts surface evidence and drift
- notes own canonical judgment
- each note should only be updated for the information it actually owns

## When to use this skill

Use when:
- Randall asks to refresh the board, update the portfolio, refresh entry bands, or sync the coverage/watchlist / portfolio notes
- a morning or post-close chain has run and the note layer needs to catch up
- band drift, earnings blockers, or status transitions are likely
- post-earnings sync changed the execution picture and the broader board needs coherence work

Do not use this for initial deep research on a new name.
Do not use it to overwrite judgment notes with raw machine output.

## Primary inputs

Run the smallest relevant refresh first:
- `python scripts/run_finance_refresh_chain.py morning`
- or `python scripts/run_finance_refresh_chain.py post-close`

Then inspect, as relevant:
- `tmp/trigger-sheet.json`
- `tmp/deployment-readiness-surface.json`
- `tmp/band-proposals.json`
- `tmp/band-update-log.txt`
- `tmp/deployment-check.json`
- `tmp/earnings-calendar.json`
- `tmp/technical-refresh.json`
- `tmp/portfolio-config.json`
- `tmp/dashboard-validation.json`

If key artifacts are stale, partial, or warning-heavy, downgrade confidence before touching the note layer.

## Real note ownership in this vault

### `03. Portfolio/Execution Board.md`
Owns:
- entry bands
- support / resistance
- stop / invalidation logic
- technical readiness framing
- deployable / almost deployable / blocked / do not touch state
- gate-based action logic
- operational blocker status

### `03. Portfolio/Portfolio Snapshot.md`
Owns:
- overall posture
- draft weights
- sleeve role
- portfolio-level implications and concentration

### `04. Research/Coverage and Watchlist.md`
Owns:
- active tracking universe membership
- coverage tier
- high-level coverage/watch state
- execution-board pointer

Important vault rule:
- `Coverage and Watchlist.md` is the consolidated universe/thesis surface, not a live price board
- do **not** turn it back into a duplicated execution board
- only update it when membership, tier, state label, or source pointer changed materially

### `01. Dashboards/Executive Brief.md`
Owns:
- orientation summary
- what matters now
- highest-level trust and focus surface

Only update this when the sync materially changes the board.
Do not churn it for routine quantitative housekeeping.

## Required audit pass before edits

Before updating notes, identify operational friction:

1. **Band drift / staleness**
   - check `tmp/band-proposals.json`
   - if `canonical_apply_eligible=true`, routine posture-preserving technical maintenance may be applied by `auto_apply_entry_band_maintenance.py --apply`
   - if `needs_review=true` but not `canonical_apply_eligible=true`, treat the band as an exception requiring review
   - do not silently push level changes that alter posture, state, sleeve/sizing/cash/risk, invalidation/reclaim judgment, or execution entitlement
   - for any newly promoted or portfolio-review ticker, verify numeric band propagation in `tmp/portfolio-config.json`, `tmp/deployment-check.json`, and `tmp/dashboard-data.json`; sentinel labels such as `WATCH_DEFINED_INITIAL`, `WATCH_PULLBACK_INITIAL`, or `TBD` mean the promotion is not complete

2. **Earnings blockers**
   - compare `tmp/earnings-calendar.json` and `tmp/trigger-sheet.json`
   - if a name is near band but inside a timing-sensitive earnings window, it should stay blocked or become blocked

3. **Ghost or orphan names**
   - every tracked name in the board should have a coherent home in the machine layer
   - every materially active name in `Portfolio Snapshot` and `Coverage and Watchlist` should map cleanly to the Execution Board

4. **State contradictions**
   - if artifact outputs and `Execution Board` imply different postures, resolve the contradiction explicitly
   - do not smooth over it

5. **Manual judgment preservation**
   - if the note layer contains a deliberate human/agent judgment call, preserve it unless the new evidence truly breaks it

## Synchronized update order

Use this order unless there is a concrete reason not to.

### Phase A — Execution foundation
Update `03. Portfolio/Execution Board.md` first when:
- entry bands changed
- support/resistance changed materially
- stop/invalidation changed materially
- repair-mode framing changed materially

Rules:
- if using `tmp/band-update-log.txt`, preserve note readability rather than pasting blindly
- never update a band without also updating its effective freshness / review context
- for routine eligible maintenance, prefer `auto_apply_entry_band_maintenance.py --apply`; it updates the current table-format Execution Board and parser-compatible sections with audit proof
- if the technical picture is still underdefined, say so rather than faking precision

### Phase B — Execution layer
Update `03. Portfolio/Execution Board.md` second.

This is where you sync:
- action state
- blocker status
- action readiness
- gate-based why

Rules:
- use the note's actual state vocabulary, not generic machine labels
- if the machine layer and note layer disagree, explain why
- a strong company is not enough to upgrade state without timing support

### Phase C — Portfolio posture
Update `03. Portfolio/Portfolio Snapshot.md` third when the sync changes:
- posture
- weight relevance
- concentration
- sleeve role
- current priority order

Do not rewrite the whole note for small level changes that belong only in the technical or trigger layer.

### Phase D — Coverage/watchlist index
Update `04. Research/Coverage and Watchlist.md` only when needed.

Allowed reasons:
- a name enters or leaves the active tracking universe
- coverage tier changes materially
- high-level coverage/watch state changes materially
- execution-board pointer needs correction

Do not sync live prices, entry distances, or action-state commentary into this file.

### Phase E — Orientation surface
Update `01. Dashboards/Executive Brief.md` only if the board meaningfully changed.

Examples:
- several bands refreshed and priority order changed
- a key name moved from blocked to actionable
- a major earnings blocker / repair-mode shift changed the operating focus
- concentration or risk posture changed materially

Routine board maintenance alone is not enough reason to rewrite this note.

## Governance rules

- **No silent sync**: if a ticker is removed from `tmp/portfolio-config.json`, do not just delete it from notes; move it to bench, archive, or otherwise explain the change.
- **Judgment wins over automation**: raw script output does not outrank deliberate note-layer judgment.
- **No duplicate truth**: do not make Coverage and Watchlist, Snapshot, and Execution Board all carry the same information.
- **Preserve warnings**: if timing is unconfirmed, a band is stale, or validation is warning-heavy, that uncertainty should survive the sync.
- **Smallest necessary update**: update only the notes whose owned content actually changed.
- **Exact gated apply only**: `entry_band`, `earnings_state`, `ticker_state`, `sleeve`, `sizing`, and `sector_posture` adjustments require exact old/new patch material, validator proof, and an approved gate unless they are inside a separately documented auto-maintenance allowlist.
- **No advisor laundering**: do not let board-sync labels imply personalized financial, tax, legal, account, or execution advice. Board state can support a recommendation, but owner action remains separately gated.

## Verification gate

Every meaningful board update should conclude with:
- `python scripts/validate_portfolio_config.py --strict`
- `python scripts/deployment_check.py`
- `python scripts/generate_dashboard.py`
- `python scripts/validate_dashboard_state.py --write`

If contradictions remain, surface them honestly.
Do not claim the board is clean if validation still says otherwise.

Promotion-specific closure: portfolio-review names must render as `PROMOTION REVIEW` / review-only, not `DEPLOYABLE NOW`, unless an exact owner-approved deployment/model gate exists. Numeric entry bands and stops must appear in dashboard/deployment consumers before the promotion is called complete.

## Execution procedure

When Randall asks to refresh the board or update the portfolio:

1. **Research**
   - run the relevant refresh chain
   - read the current artifacts
2. **Audit**
   - identify stale bands, earnings blocks, contradictions, and true update targets
   - state a brief sync plan if the work is broad enough to justify one
3. **Action**
   - update notes in the synchronized order
   - touch only the notes that actually own changed information
4. **Validation**
   - run `python scripts/validate_dashboard_state.py --write`
5. **Report**
   - say what changed materially
   - say what remains unresolved

## Quality standard

A production-grade board refresh should leave behind:
- no silent contradiction between Execution Board, Portfolio Snapshot, and Coverage and Watchlist
- no accidental Coverage and Watchlist drift back into duplicated execution detail
- explicit handling of stale bands and earnings blockers
- an updated orientation surface only when the board actually changed enough to warrant it

The goal is not to make every note look busy.
The goal is to keep the operating board trustworthy.

## Bounded portfolio-agent routing

Generalized autonomous workspace portfolio/canon maintenance for `entry_band`, `earnings_state`, `ticker_state`, `sleeve`, `sizing`, `sector_posture`, and related artifacts routes through `veritas-bounded-portfolio-agent` plus WF64/WF56 exact apply gates. This skill still owns portfolio board/snapshot sync judgment; the bounded-agent skill owns the autonomous apply operating loop and stop lines.
