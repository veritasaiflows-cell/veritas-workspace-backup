# Financial Canon Cron Authority Scan

Status: **complete review-only scan**. No canonical files were edited.

## Bottom line

Randall's broader approval supports **cron generating and validating** bounded portfolio/canon maintenance artifacts, but it does **not** justify broad cron direct-apply. The safe expansion path is: proposal → semantic preview → verifier/guardrails → main-session exact gated apply.

Three narrow direct-apply cron paths already exist in the finance chain and should be treated as grandfathered/category-specific, not a precedent for broader apply:

1. `event_calendar_apply.py --apply` — Event Calendar only, approved 2026-05-10.
2. `auto_apply_entry_band_maintenance.py --apply` — machine-eligible entry-band maintenance only.
3. `canon_volatile_execution_board_sync.py --apply --strict-exit` — volatile Execution Board/table/parser/date/prose freshness sync only.

## Cron-safe allowlist

| Category | Cron posture | Exact scripts | Output / write surface | Required gates | Stop lines |
|---|---|---|---|---|---|
| Canonical note patch proposals | Generate only | `canonical_note_patch_proposal.py --write`; `canonical_freshness_patch.py`; `portfolio_snapshot_patch_proposal.py --write` | `tmp/canonical-note-patch-proposal.*`; `tmp/research-automation/freshness-patch-candidates-*.json`; `tmp/portfolio-snapshot-patch-proposal.*` | `board_canon_guardrail.py --write`; `stale_intelligence_guardrail.py --write`; full-portfolio view validation | `cron_apply_allowed=false`; no sizing/weight/cash/sleeve/promotion/demotion/approval/execution/trade changes |
| Portfolio mutation proposal generation | Generate only | `portfolio_mutation_proposal_generator.py --window <window> --write`; `portfolio_mutation_proposal_verifier.py` | `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`; verifier reports | proposal schema, capital recommendation, pro-forma risk, authority vocabulary, patch scope, canonical-status invariant validators | proposal packets must keep authority flags false; clean validation is not approval |
| Semantic patch/preview bundle | Generate and validate only | `portfolio_mutation_semantic_patch_generator.py`; `portfolio_mutation_semantic_preview_bundle.py`; `portfolio_mutation_exact_patch_generator.py`; preview mode of `portfolio_mutation_apply_helper.py` | `tmp/portfolio-mutation-proposals/semantic-patch-material/*`; `patch-previews/*`; `semantic-preview-bundle.*` | `proposal_patch_scope_validator.py`; `portfolio_mutation_patch_preview_validator.py`; source freshness/manual-dependency gates | no owner-file write; `sleeve`, `sizing`, `sector_posture` remain preview-only; `entry_band`/`ticker_state` are apply-trial candidates only |
| Event Calendar maintenance | Existing narrow apply OK | `event_calendar_rollforward.py`; `event_calendar_apply.py --apply` | `05. Intelligence/Event Calendar.md`; `tmp/event-calendar-apply.*` | rollforward `status` ok/partial; warnings empty; marker/anchor present; source confidence carried | Event Calendar only; provider estimates labeled; no portfolio/deployment/watchlist/trade authority |
| Machine-eligible entry-band maintenance | Existing narrow apply; do not broaden | `band_refresh.py`; `auto_apply_entry_band_maintenance.py --apply` | `tmp/portfolio-config.json`; `03. Portfolio/Execution Board.md`; `tmp/auto-band-apply.*` | `canonical_apply_eligible=true`; `earnings_state=CLEAR`; supported method; `IN_BAND`/`NEAR_BAND`; low/high/stop present; ticker section exists | unsupported/frozen/incomplete proposals block; no sizing/sleeve/cash/risk-rule/execution/trade/account authority |
| Volatile Execution Board freshness sync | Existing narrow apply; keep strict | `canon_volatile_execution_board_sync.py --apply --strict-exit` | `03. Portfolio/Execution Board.md`; Snapshot date/header only; config prose numeric sync; `tmp/canon-volatile-execution-board-sync.*` | required artifacts: config, technical refresh, deployment check, trigger sheet; then `canon_drift_freshness_gate.py --write --strict-exit` | volatile freshness only; skipped rows block under strict; no judgment-field expansion |
| Guardrails / post-apply reporting | Reporting and dry-run validation | `board_canon_guardrail.py --write`; `stale_intelligence_guardrail.py --write`; `canon_drift_freshness_gate.py --write --strict-exit`; `validate_canonical_ownership.py`; `post_apply_validation_chain.py --write`; `post_apply_board_snapshot_config_coherence.py --write` | `tmp/*guardrail*`; `tmp/canonical-ownership-validation.json`; `tmp/post-apply-validation-chain.json` | critical findings block; execute mode requires valid approval artifact | validator output is not approval; routine cron should not use `post_apply_validation_chain.py --execute` |

## Main-session-only / blocked

- Actual WF64/WF56 owner-file applies through `portfolio_mutation_apply_helper.py --apply`, `portfolio_mutation_scoped_apply_helper.py --execute`, or `post_apply_validation_chain.py --execute` stay **main-session-only** unless a future exact category-specific cron gate is explicitly promoted.
- `sleeve`, `sizing`, and `sector_posture` direct apply stay main-session-only because they are portfolio-construction semantics, even though they are standing-approved maintenance categories.
- Cash targets, risk-rule thresholds, execution entitlement, promotion/demotion, and material ticker-state changes need separately scoped approval.
- Brokerage/live/paper trading/account/money/credential actions are outside this cron authority scan and remain blocked by SOUL/USER/WF67 boundaries.
- Deletes, moves, archives, config/auth/channel/service changes remain owner-gated.

## Recommended cron movement

Move **more proof generation** to cron, not more direct apply:

1. Add/confirm a semantic-preview-bundle cron pass for selected tickers/categories.
2. Add/confirm `portfolio_mutation_proposal_verifier.py` after proposal generation.
3. Generate standing-approval templates/reports only; never flip approval or apply from cron.
4. Keep routine `post_apply_validation_chain.py` in `--write` dry-run mode. Use `--execute` only after main-session approval-gated apply.
