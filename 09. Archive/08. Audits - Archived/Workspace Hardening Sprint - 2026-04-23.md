# Workspace Hardening Sprint - 2026-04-23

## Sprint objective

Tighten the workspace so doctrine, notes, config, generated artifacts, and dashboard surfaces stop drifting into plausible-looking contradictions.

## Phase map

- **Phase 0, Sprint control**: establish this control note and merge all cited audit opportunities into one tracked sprint surface.
- **Phase 1, Doctrine resolution**: remove identity and operating-doctrine ambiguity.
- **Phase 2, Config truth realignment**: make portfolio and risk config match live operating posture.
- **Phase 3, Source-of-truth and dashboard governance**: define precedence, trust semantics, and dashboard dependency rules.
- **Phase 4, Workspace standards and root hygiene**: update governance docs and clean top-level structure.
- **Phase 5, Scripts and tmp cleanup**: remove obsolete helpers and restore clear generated-vs-tooling boundaries.
- **Phase 6, Operating-layer scope tightening**: reduce redundancy across dashboard, briefs, reviews, and trigger surfaces.
- **Phase 7, Validation and closure discipline**: add explicit validation, acceptance checks, and closure tracking.

## Scope coverage checklist

| Item | Scope | Affected files or surfaces | Acceptance criteria | Status |
|---|---|---|---|---|
| 1 | Resolve core doctrine conflict and set hierarchy | `SOUL.md`, `FINANCE_SOUL.MD`, any linked identity/doctrine references | One canonical identity/doctrine remains active, hierarchy is explicit, conflicting persona/session-init guidance is removed or subordinated | resolved 2026-04-23 |
| 2 | Realign portfolio config with live portfolio and risk posture | `tmp/portfolio-config.json`, `03. Portfolio/Portfolio Snapshot.md`, `07. Risk/Risk Rules.md`, `03. Portfolio/Deployment Trigger Sheet.md`, dashboard inputs | Weights, cash, sizing, thresholds, posture labels, and entry-band semantics match the live note layer, and any manual-review fields are documented | resolved 2026-04-23 |
| 3 | Define source-of-truth precedence across note, config, macro, and dashboard layers | `06. Playbooks/Operating Model.md`, `tmp/portfolio-config.json`, `tmp/market-state.json`, dashboard usage notes, relevant portfolio/risk notes | A short written hierarchy states which layer wins for portfolio posture, risk posture, macro readiness, dashboard rendering, event dates, derived summaries, and partial-data propagation | resolved 2026-04-23 |
| 4 | Repair dashboard trust semantics so degraded inputs cannot render as healthy confidence | `scripts/generate_dashboard.py`, `scripts/dashboard-template.html`, `tmp/dashboard-data.json`, dashboard UI | Freshness degrades on partial or missing critical inputs, fake zero fallbacks are removed, and the dashboard visibly distinguishes machine, manual, partial, stale, and missing data | resolved 2026-04-23 |
| 5 | Add dashboard integrity and contradiction checks | `scripts/generate_dashboard.py`, `tmp/dashboard-data.json`, dashboard warning surfaces | Contradictions such as posture-vs-MA state, band math, stop state, earnings sanity, and concentration math are flagged in payload and UI instead of silently rendering | resolved 2026-04-23 |
| 6 | Move dashboard business logic out of presentation and into governed inputs | `scripts/dashboard-template.html`, `scripts/generate_dashboard.py`, `tmp/portfolio-config.json`, `tmp/dashboard-data.json` | Template is mostly rendering-only, interpretation logic lives in Python/config, and hardcoded portfolio/risk semantics are minimized or removed | resolved 2026-04-23 |
| 7 | Set dashboard role and dependency governance inside the broader workflow | dashboard usage notes, `scripts/README.md`, `01. Dashboards/Executive Brief.md`, daily execution card surface, `05. Intelligence/Weekly Positioning Review.md`, event-driven update notes | Dashboard is documented as a derived operating surface with clear trust rules and explicit relationship to weekly, daily, and event-driven note layers | resolved 2026-04-23 |
| 8 | Update workspace standards and related governance docs to match the finance-first vault | `skills/workspace-governor/references/workspace-standards.md`, other workspace policy/playbook docs that still describe the old structure | Written standards reflect the actual numbered finance-first structure, archive policy, and root discipline, with obsolete consulting-era guidance removed | resolved 2026-04-23 |
| 9 | Clean root-level drift and classify every top-level surface | workspace root, `state/`, `Evening Review/`, `templates/`, `veritas-command-center.html`, top-level folder policy docs | Every root item is explicitly classified as canonical, archival, generated, or stray, empty dead weight is removed or relocated, and root policy is tightened | resolved 2026-04-23 |
| 10 | Remove old-branch template residue and stale helper clutter from active paths | `templates/`, `scripts/diagnose.py`, `scripts/diagnose_calendar.py`, `scripts/market_state_refresh_plan.md`, any similar leftovers | Prior-branch templates and superseded diagnostics are archived, rewritten, or removed from active operator surfaces | resolved 2026-04-23 |
| 11 | Restore `tmp/` to a generated-artifacts-first surface | `tmp/`, including `tmp/calc_ma.py`, `tmp/refresh_technicals.py`, `tmp/inspect_fedwatch.py`, current generated JSON artifacts | Helper scripts and scratch utilities no longer live in `tmp/`, and the remaining contents are clearly intentional machine artifacts | resolved 2026-04-23 |
| 12 | Tighten scope boundaries across operating layers to reduce redundancy drift | `01. Dashboards/Executive Brief.md`, `01. Dashboards/This Week.md`, `01. Dashboards/Next Actions.md`, `05. Intelligence/Weekly Positioning Review.md`, daily executive summary surface, dashboard, trigger sheet | Each layer has a short role definition, repeated content is reduced, and the stack answers distinct questions without silent overlap | resolved 2026-04-23 |
| 13 | Improve timing-critical data governance and unresolved manual dependencies | earnings/event date handling, Fed/FedWatch references, `tmp/market-state.json`, related scripts and notes | Timing-critical dates are explicitly cross-checked when unresolved, partial macro data is labeled honestly, and manual dependencies are visible rather than buried | resolved 2026-04-23 |
| 14 | Add validation and closure discipline for recurring drift points | prior audit surfaces, this sprint note, validation hooks between notes/config/generated artifacts | Findings are tracked as resolved, intentionally deferred, or still open, and lightweight validation checks reduce repeat drift | resolved 2026-04-23 |
| 15 | Run final dashboard and workspace acceptance review before declaring the sprint complete | dashboard hardening test cases, this sprint note, affected governance/docs/scripts | Missing-field, partial-feed, stale-source, contradiction, earnings-date, and state-transition tests are run, and the sprint is not closed until results are documented | resolved 2026-04-23 |

## Acceptance result

- Final acceptance review completed on 2026-04-23.
- Acceptance harness: `scripts/test_dashboard_acceptance.py`
- Acceptance report: `tmp/dashboard-acceptance-report.json`
- Result: 6 of 6 acceptance tests passed.
- Post-acceptance live-state check: `python scripts/generate_dashboard.py` and `python scripts/validate_dashboard_state.py --write` both completed successfully, with 0 critical and 2 warning findings.
- Remaining warnings are external or manual dependencies that are now explicitly surfaced, not hidden internal drift: manual Fed or FedWatch dependency and timing-sensitive earnings date confirmation.
- Sprint status: implementation complete and acceptance complete.

## Notes

- Duplicate opportunities across the tightening plan, audit, and dashboard hardening plan were merged into the checklist above instead of being tracked twice.
- Dashboard hardening is treated as a dependency-governance stream inside the broader workspace sprint, not a separate truth system.
- Phase 0 only establishes control and coverage. No later-phase cleanup is performed in this note.
- Phase 1 was resolved on 2026-04-23 by making `SOUL.md` the sole governing identity/doctrine file, converting `FINANCE_SOUL.MD` into subordinate finance doctrine, and adding explicit hierarchy language in the active doctrine references.
- Phase 2 was resolved on 2026-04-23 by bringing `tmp/portfolio-config.json` into line with the current portfolio snapshot, deployment trigger sheet, and risk rules, removing stale concentration semantics, and documenting manual-review fields directly inside the config so dashboard consumers can see what remains human-maintained.
- Phase 3 was resolved on 2026-04-23 by placing the source-of-truth hierarchy in `06. Playbooks/Operating Model.md`, making the dashboard explicitly subordinate to canonical notes, defining `tmp/portfolio-config.json` as a governed machine mirror, defining `tmp/market-state.json` as the macro-readiness evidence source, and requiring partial, stale, missing, manual, and unconfirmed states to propagate downstream instead of being smoothed away.
- Phase 4 was resolved on 2026-04-23 by rewriting the workspace-governor standards around the live finance-first numbered structure, documenting archive and generated-artifact policy, removing obsolete template assumptions from local guidance, and aligning dashboard-path references with `tmp/veritas-command-center.html` as the staged render target.
- Phase 6 was resolved on 2026-04-23 by adding explicit role boundaries to the dashboard, weekly, portfolio, and operating-model notes; trimming duplicated ticker-level detail out of the derived dashboard layer; keeping the deployment trigger sheet as the canonical action-state surface; and clarifying that the portfolio snapshot owns allocations while the weekly positioning review owns the weekly operating map.

## Phase 4 root classification and disposition

| Root surface | Classification | Disposition |
|---|---|---|
| `.clawhub/` | generated or staged | kept in root as tool-managed metadata |
| `.git/` | canonical active | kept in root as repo infrastructure |
| `.gitignore` | canonical active | kept in root as repo control |
| `.obsidian/` | canonical active | kept in root as vault infrastructure |
| `.openclaw/` | canonical active | kept in root as OpenClaw infrastructure |
| `01. Dashboards/` | canonical active | kept |
| `02. Markets/` | canonical active | kept |
| `03. Portfolio/` | canonical active | kept |
| `04. Research/` | canonical active | kept |
| `05. Intelligence/` | canonical active | kept |
| `06. Playbooks/` | canonical active | kept |
| `07. Risk/` | canonical active | kept |
| `08. Audits/` | canonical active | kept |
| `09. Archive/` | archival | kept as the archive sink |
| `AGENTS.md` | canonical active | kept |
| `CLAUDE.md` | canonical active | kept by explicit workspace decision |
| `Continuity Protocol.md` | canonical active | kept |
| `Evening Review/` | stray | moved to `09. Archive/Evening Review - Archived/` |
| `FINANCE_SOUL.MD` | canonical active | kept |
| `HEARTBEAT.md` | canonical active | kept |
| `Home.md` | canonical active | kept |
| `IDENTITY.md` | canonical active | kept |
| `memory/` | canonical active | kept |
| `MEMORY.md` | canonical active | kept |
| `scripts/` | canonical active | kept |
| `skills/` | canonical active | kept |
| `SOUL.md` | canonical active | kept |
| `state/` | stray | removed as empty dead weight |
| `templates/` | stray | archived content to `09. Archive/Templates - Archived/`, then removed root folder |
| `tmp/` | generated or staged | kept as the machine-artifact surface |
| `TOOLS.md` | canonical active | kept |
| `USER.md` | canonical active | kept |
| `veritas-command-center.html` | generated or staged | moved to `tmp/veritas-command-center.html` and root copy removed |

- Item 10 was fully resolved on 2026-04-23 by archiving the superseded helper clutter out of `scripts/` and `tmp/`, then narrowing `scripts/README.md` to the supported active tooling surface only.
- Item 11 was resolved on 2026-04-23 by removing helper scripts and scratch raw artifacts from `tmp/`, leaving the folder as an intentional generated-artifacts and staged-render surface.
- Item 4 was resolved on 2026-04-23 by moving dashboard trust classification into `scripts/generate_dashboard.py`, emitting governed source-level trust states into `tmp/dashboard-data.json`, removing healthy-looking numeric fallbacks from the template, and adding a visible dashboard trust panel that surfaces manual, partial, stale, missing, and unconfirmed inputs.
- Item 5 was resolved on 2026-04-23 by adding generator-side integrity checks for MA posture consistency, entry-band math, stop-state math, deployment-state conflicts, earnings sanity, concentration math, and timing-sensitive dependencies, then surfacing the resulting warnings in both `tmp/dashboard-validation.json` and the rendered dashboard UI.
- Item 6 was resolved on 2026-04-23 by moving trust evaluation, action-card readiness logic, compliance checks, deployment summaries, and warning synthesis into `scripts/generate_dashboard.py`, leaving `scripts/dashboard-template.html` as a thin presentation layer over governed payload objects.
- Item 13 was resolved on 2026-04-23 by tightening timing-critical governance in `05. Intelligence/Event Calendar.md`, preserving manual Fed and FedWatch dependencies as explicit dashboard trust degraders, and surfacing unconfirmed earnings-date changes as visible manual-dependency items instead of burying them in warnings.
- Item 14 was resolved on 2026-04-23 by adding `scripts/validate_dashboard_state.py`, writing `tmp/dashboard-validation.json`, updating operating docs to include the validator in the closure loop, and recording the remaining warning-state items as surfaced unresolved dependencies rather than silent drift.
- Validation pass on 2026-04-23: `python scripts/generate_dashboard.py` completed successfully, and `python scripts/validate_dashboard_state.py --write` reported 0 critical and 2 warning findings after the BRK.B numeric-band mismatch was corrected in `tmp/portfolio-config.json`. The remaining warnings are surfaced external/manual dependencies, not hidden internal drift: macro manual dependency and timing-sensitive earnings date changes.
- Item 15 was resolved on 2026-04-23 after the final acceptance pass confirmed: no critical dashboard contradictions, degraded trust states render visibly as `usable_with_caution` instead of healthy, the validator runs successfully and writes `tmp/dashboard-validation.json`, the dashboard render still completes, and the remaining warnings are explicitly surfaced operator dependencies rather than silent system conflicts.
- Formal acceptance cases now live in `scripts/test_dashboard_acceptance.py` and passed on 2026-04-23 for: missing market field, partial macro feed, stale source, contradiction surfacing, earnings-date change visibility, and coherent blocker or stop or in-band state transition behavior.

## Phase 5 cleanup disposition

Archived to `09. Archive/Scripts and Tmp Cleanup - Archived/`:
- `scripts/diagnose.py`
- `scripts/diagnose_calendar.py`
- `scripts/market_state_refresh_plan.md`
- `tmp/calc_ma.py`
- `tmp/refresh_technicals.py`
- `tmp/inspect_fedwatch.py`
- `tmp/refresh_technicals_raw.json`
- `tmp/technicals-2026-04-19.json`

Retained as active in `scripts/`:
- `technical_refresh.py`
- `market_state_refresh.py`
- `deployment_check.py`
- `earnings_calendar_enrichment.py`
- `trigger_sheet_refresh.py`
- `post_earnings_prep.py`
- `post_earnings_note_targets.py`
- `generate_dashboard.py`
- `run_finance_refresh_chain.py`
- `dashboard-template.html`
- `prompts/post_earnings_vault_update_v1.md`

Retained as intentional generated or staged outputs in `tmp/`:
- `technical-refresh.json`
- `market-state.json`
- `deployment-check.json`
- `earnings-calendar.json`
- `trigger-sheet.json`
- `post-earnings-prep.json`
- `post-earnings-note-targets.json`
- `portfolio-config.json`
- `dashboard-data.json`
- `dashboard-delta.json`
- `dashboard-last.json`
- `veritas-command-center.html`
