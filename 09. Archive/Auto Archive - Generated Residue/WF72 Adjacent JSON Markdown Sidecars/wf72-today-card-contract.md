# WF72 Today Card Contract

Status: **draft / review-only / Phase 1 contract only**  
Generated: `2026-05-22T06:18:00Z`  
Target future surface: `01. Dashboards/Today.md`  

This artifact does **not** authorize writing `Today.md`, mutating canon/portfolio files, placing live or paper orders, changing accounts, moving money, or inferring owner approval.

## Purpose

`Today.md` should become a generated daily decision router that answers only:

1. What is actionable or reviewable now?
2. What is blocked and why?
3. What owner decision is needed?
4. What proof is fresh, stale, warning, or degraded?
5. What must not be done?

It must **not** own thesis truth, portfolio weights, entry bands, owner approvals, or execution authority. Canon stays in `Execution Board.md`, `Portfolio Snapshot.md`, and `Coverage and Watchlist.md`; proof stays in `tmp/`.

## Authority flags

| Flag | Required value for Today card |
|---|---:|
| generated report is canonical | `false` |
| Today card can self-apply canon changes | `false` |
| Today card can mutate portfolio/model state | `false` |
| Today card can infer owner approval | `false` |
| Today card can authorize live trade/account action | `false` |
| Today card can authorize paper submit/cancel | `false` |
| Today card can move money | `false` |
| Phase 1 can write `01. Dashboards/Today.md` | `false` |

Standing main-session workspace-maintenance authority is acknowledged only as upstream context. Any real canon/portfolio maintenance still requires exact WF56/WF64 gated apply artifacts, validators, post-apply proof, and main-session integration. Today.md is a router, not an apply surface.

## Source map inspected

| Role | Path | Observed status | Contract use |
|---|---|---|---|
| Current-window index | `tmp/current-window-artifacts.json` | `ok`; 104/104 artifacts present; no missing required roles | source inventory, freshness routing, proof links |
| Morning run summary | `tmp/run-summary-morning.json` | `warning`; chain ok; acceptance passed; critical 0 / warning 1; exec freshness usable with caution | trust banner / degraded presentation flag |
| Capital deployment packets | `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json` | `ok`; 7 review-only packets; apply false; trade/account false | candidate decision items and price-vs-band |
| Capital packet validator | `tmp/capital-deployment-recommendation-validation.json` | `ok`; 7 checked; critical 0 / warning 0 | capital item acceptance gate |
| Dashboard validation | `tmp/dashboard-validation.json` | manual dependency / review required; critical 0 / warning 1; presentation allowed; capital action false | freshness/trust banner |
| Board/canon guardrail | `tmp/board-canon-guardrail.json` | `warning`; critical 0 / warning 11; below-stop and near-stop risks | risk/repair blockers and must-not-do section |
| Intraday router | `tmp/intraday-alerts/delivery-router-status.json` | optional; `GROUPED_DIGEST_READY`; action_needed false; immediate_count 0 | intraday strip when present |

Canonical source links for future renderer: `03. Portfolio/Execution Board.md`, `03. Portfolio/Portfolio Snapshot.md`, and `04. Research/Coverage and Watchlist.md`.

## Required output schema

Top-level fields:

- `schema_version`
- `generated_at_utc`
- `window`
- `status`
- `trust_banner`
- `authority`
- `source_artifacts`
- `validator_status`
- `decision_items`
- `blocked_and_repair_items`
- `owner_decisions_needed`
- `proof_freshness`
- `must_not_do`
- `next_generator_action`

Decision item fields:

- `rank`
- `ticker_or_scope`
- `item_state`
- `recommendation_posture`
- `owner_action_needed`
- `why_now`
- `price_vs_band`
- `freshness_state`
- `validator_state`
- `blockers`
- `proof_links`
- `authority_boundary`

Price-vs-band fields:

- `close`
- `band_low`
- `band_high`
- `entry_band_status`
- `raw_band_status`
- `distance_to_band_pct`
- `below_stop`
- `stop_or_repair_note`
- `no_chase_flag`

## Allowed item states

| State | Meaning | Authority |
|---|---|---|
| `deployable` | Evidence packet is review-ready and price/technical context is inside written entry logic | Owner decision prompt only; never approval |
| `wait` | Candidate may be valid but price/catalyst/freshness/evidence says wait or no-chase | Monitor only |
| `blocked` | Critical missing/stale/conflicting source, explicit stop/risk block, or validator failure | Escalate blocker only |
| `repair` | Canon/source/proof/risk state needs reconciliation before action language | Repair queue only |
| `review_only` | Informational item, alert digest, source cue, or non-self-applying proposal packet | Informational review only |

Mapping rules:

- `owner_decision_required` + `IN_BAND` + validator clean → `deployable`, but label **owner decision required; not approval**.
- `deploy_candidate` + `IN_BAND` → `review_only` or deployable candidate depending on source freshness and explicit owner-action field.
- `ABOVE_BAND_WAIT`, `BELOW_BAND`, or no-chase → `wait`.
- Below-stop with deployment-blocking guardrail → `blocked` or `repair`, ahead of softer watch language.
- Stale/manual-dependency/partial source freshness → degrade confidence and show review-required banner.
- Any required validator critical > 0 or missing required source → `blocked`; suppress deployable language.

## Observed initial fixture candidates

| Ticker | Draft state | Posture | Band status | Close | Band | Required label |
|---|---|---|---|---:|---:|---|
| ETN | `deployable` | owner decision required | IN_BAND | 381.51 | 358.11-401.18 | Owner decision required; not approval |
| VRT | `review_only` | deploy candidate / promotion review | IN_BAND | 323.40 | 286.97-339.27 | Promotion review; stale/review-required; not approval |
| GOOG | `wait` | wait for band | ABOVE_BAND_WAIT | 383.47 | 355.35-378.98 | No-chase / wait for band |
| GS | `wait` | wait for band | ABOVE_BAND_WAIT | 988.17 | 894.64-935.77 | No-chase / wait for band |
| JPM | `wait` | wait for band | BELOW_BAND | 303.00 | 306.82-318.12 | Below band / near-stop context |
| MSFT | `wait` | wait for band | ABOVE_BAND_WAIT | 419.09 | 389.64-412.56 | No-chase / wait for band |
| NVDA | `wait` | wait for band | ABOVE_BAND_WAIT | 219.51 | 198.47-216.66 | No-chase / wait for band |

Risk/repair strip should include board-canon guardrail findings: below-stop `BRK.B`, `ECL`, `LMT`, `LNG`, `META`, `NFLX`, `RTX`, `TMUS`, `VMC`; near-stop `JPM`, `XLF`; deployment-blocking `BRK.B`, `LMT`.

## Stale / degraded behavior

- If `tmp/current-window-artifacts.json` is not `ok`, or required roles are missing, render a **BLOCKED** trust banner and suppress deployable items.
- If run summary is `warning` but `acceptance_passed=true` and critical count is 0, render usable-with-caution and keep owner-review labels.
- If dashboard freshness is `manual_dependency` / `review_required`, presentation can continue, but capital action remains blocked and confidence is degraded.
- If capital recommendation validation has any critical finding, suppress capital decision items.
- If board/canon guardrail has below-stop or near-stop warnings, surface those before action language.
- If the optional intraday router is absent, do not fail the Today card; show `not_available`.
- If the intraday router has `action_needed=true` or `immediate_count>0`, show an alert strip while preserving no-trade/no-account authority flags.

## Validator requirements

Before any prototype writes `01. Dashboards/Today.md`, build `tmp/today-card.json` and validate it with a dedicated validator.

Required validator checks:

1. JSON schema validation for Today-card payload.
2. Required source existence/readability check.
3. Authority invariants: all Today-card execution/canon/apply flags false.
4. Capital recommendation validation must be `ok`, critical 0, before rendering deployable/owner-decision items.
5. Dashboard validation critical count must be 0 for normal presentation.
6. Board/canon guardrail parsed, with below-stop/near-stop risks surfaced before action language.
7. Markdown renderer includes timestamp, source map, authority boundary, stale/degraded banner, proof links, and must-not-do section.

Blocked conditions:

- Missing current-window artifact index.
- Missing capital validator when rendering capital items.
- `trade_execution_allowed=true` anywhere in Today payload.
- `owner_approval_inferred=true` anywhere in Today payload.
- `generated_report_is_canonical=true`.
- Any required validator critical finding.
- Deployable item missing price-vs-band or owner-action-needed fields.

Recommended validation output: `tmp/today-card-validation.json`.

## First prototype plan

1. Build `tmp/today-card.json` from current-window index, run summary, capital packets/validation, dashboard validation, board-canon guardrail, and optional intraday router.
2. Create `scripts/today_card_validator.py` enforcing schema, source freshness, item-state mapping, authority invariants, and blocked conditions.
3. Generate `tmp/today-card.preview.md` first, not `01. Dashboards/Today.md`.
4. Only after validator proof and main-session review, write generated/review-only `01. Dashboards/Today.md` in Phase 3.

## Must not do

- Do not write `01. Dashboards/Today.md` in Phase 1.
- Do not mutate `Execution Board.md`, `Portfolio Snapshot.md`, `Coverage and Watchlist.md`, portfolio config, or canonical owner notes from this contract.
- Do not place, submit, cancel, replace, or recommend automatic live trades.
- Do not infer owner approval from clean validators, in-band price, ranking, or packet quality.
- Do not treat paper-trading approval as live-trading authority.
- Do not hide stale/manual-dependency/source-warning state behind green action language.
