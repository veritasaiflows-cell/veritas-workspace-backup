# Workflow 68 - Intraday Alert Engine and Advisor Surface

## Objective
- Turn Veritas from batch-only research/governance into a bounded intraday alerting and advisor surface without widening live trade/account authority. As of Randall's 2026-05-19 21:23 MST instruction, WF68 may hand advisor-derived paper buy/sell packages to WF67 for paper-only execution under guardrails and main-session capital-package notification.
- Build the three missing primitives identified by the 2026-05-19 Workspace Audit: intraday data/event triggers, alert taxonomy/rate limits, and decision-packet delivery into the attended/current OpenClaw surface.

## Current State
- Opened 2026-05-19 from the Workspace Audit - Veritas Finance OS.
- Canonical audit input is now filed at `08. Audits/Financial Advisor and Real-Time Alerting Readiness Audit - 2026-05-19.md`.
- 2026-05-19 Randall direction, now superseded as the primary workspace goal by the 2026-05-29 Retail Investor Finance Intelligence SaaS pivot: FA/advisor-grade monitoring and real-time/intraday alerting remains a finance-engine lane, but WF75/P0 retail SaaS is the unifying product goal. WF68 should now support customer-safe notification/alert concepts only through fixture-first, non-executing, privacy/source/compliance-gated product work.
- Telegram shadow delivery is now owner-approved for Randall-only WF68 market decision alerts after the 2026-06-01 discussion. It is delivery-only for fresh `EXECUTION_PACKET_READY` packets and blocker visibility; Discord/Signal/email remain blocked, and no Telegram message can imply approval, paper execution, live trading, account action, portfolio/canon mutation, or risk-rule change authority.
- 2026-06-19 SQL/JSON cutover note: WF68 may read guarded SQL-canon plus JSON proof packets for internal alert classification and freshness/routing context, but alert output remains review-only/shadow-gated. SQL/JSON rows cannot create execution packets, customer delivery, channel expansion, paper/live execution, portfolio/canon mutation, or owner approval.
- Existing strengths to preserve: evidence discipline, stale-data downgrades, owner-gated trading boundary, Execution Board/Coverage/Snapshot truth ownership, WF63/WF67 paper/live isolation, WF55 outcome gate, WF41 event router, WF58 capital recommendation packets, and WF66 why-stack evidence.
- 2026-05-19 Phase 0 implementation proof: alert packet schema, validator, ETN forced-alert fixture, intentionally invalid authority/missing-freshness fixture, and targeted validator test now exist. Independent QA passed with one clarity fix; fixture owner-surface reference now points to the ETN detailed section/context plus `tmp/portfolio-config.json` exact machine-readable band/stop to avoid table-row ambiguity. Proof passed after fix: `python -m py_compile scripts\intraday_alert_packet_validator.py scripts\test_intraday_alert_packet_validator.py`; `python scripts\intraday_alert_packet_validator.py --write` returned `status=ok`; `python scripts\test_intraday_alert_packet_validator.py` passed; invalid fixture validation returned `status=error` for missing freshness and true paper authority.
- 2026-05-19 Phase 1 implementation proof: `scripts/intraday_quote_snapshot_proof.py` proves a read-only Alpaca market-data GET snapshot path at `https://data.alpaca.markets/v2/stocks/snapshots` using paper-named credentials only. Proof artifacts: `tmp/intraday-alerts/quote-snapshot-proof.json`, `.md`, and `quote-snapshot-proof-validation.json`. Main/QA fix required post-close quotes marked `current_but_not_intraday_fresh` to degrade to `no_fire_or_monitor_only`; validation is `status=ok`, `critical_count=0`, `warning_count=10` for non-intraday-fresh quotes, authority flags hard-false, no raw headers/bodies/secrets persisted, no brokerage endpoint/order/account path used.
- 2026-05-19 Phase 2 implementation proof: `scripts/intraday_alert_trigger_engine.py` and `scripts/test_intraday_alert_trigger_engine.py` now implement/test the thin trigger engine over Phase 1 quote proof + `tmp/portfolio-config.json` + sanitized ETN paper-state input. Current artifact `tmp/intraday-alerts/current-alerts.json/.md` emits 0 actionable alert packets and 10 no-fire/monitor-only rows because all quotes are `current_but_not_intraday_fresh`; ETN paper state is recorded as a monitor-only placeholder. Proof passed: py_compile, trigger-engine targeted tests, trigger-engine run, packet validator, packet validator tests, and independent QA. Non-blocking residue: before expanding beyond Core 10, non-Core active-paper symbols without bands should be surfaced explicitly as no-fire/monitor-only instead of silently dropped.
- 2026-05-19 WF68 prerequisite repair: the daily canon-drift freshness gate found 11 critical ETN/GOOG band/stop/prose drift findings that could make trigger alerts unsafe. A bounded standing-approved canon/prose sync repaired `03. Portfolio/Execution Board.md` and `tmp/portfolio-config.json`; backups were written under `tmp/canon-drift-repair-backup-*`; main validation now shows `canon_drift_freshness_gate.py --write --strict-exit` ok 0/0, stale-intelligence guardrail ok 0/0, portfolio config strict ok 0 warnings, and dashboard validation exit 0.
- 2026-05-19 Phase 3 implementation proof: `scripts/intraday_alert_main_handoff.py` and targeted tests now build main-session handoff artifacts from either `current-alerts.json` or a single validated alert packet. Current no-alert handoff writes `tmp/intraday-alerts/main-session-handoff.json/.md` with `status=NO_REPLY`; forced ETN fixture writes `forced-main-session-handoff.json/.md` with `status=ALERT_READY`, `highest_severity=HIGH`, packet path, compact user-facing message, and hard owner-gated boundary. Independent QA passed. This is artifact-proof only: actual `systemEvent`/cron/runtime wiring remains future owner-gated work and was not implemented.
- 2026-05-19 Phase 4 implementation proof: `scripts/intraday_alert_advisor_enricher.py` and targeted tests now enrich the forced ETN handoff into `tmp/intraday-alerts/advisor-alert-packet.json/.md` with WF58 recommendation context, WF66 official-source/manual-required context, thesis, entry band/price, stop/invalidation, no-chase, source freshness/trust limits, risk/concentration note, owner action required, and WF55 outcome-link placeholder. Validation ok 0 critical / 0 warning and independent QA passed after `Active Workflows.md` was updated. Probability claims remain blocked; actual WF55/Call Log writeback remains Phase 5.
- 2026-05-19 Phase 4 implementation proof: `scripts/intraday_alert_advisor_enricher.py` and `scripts/test_intraday_alert_advisor_enricher.py` now attach WF58 recommendation context and WF66/official-source why-stack context to the existing Phase 3 artifact handoff. Forced ETN proof writes `tmp/intraday-alerts/advisor-alert-packet.json/.md` with `status=ADVISOR_READY`, thesis, entry band/price, stop/invalidation, source freshness, WF58 recommendation posture, WF66 official-source/manual-required status, concentration/risk note, owner action required, and explicit no live/paper/order/account/canon/portfolio/cron/channel/config authority. Validation artifact `tmp/intraday-alerts/advisor-alert-packet-validation.json` is `status=ok`, 0 critical / 0 warning. Proof passed: `python -m py_compile scripts\intraday_alert_advisor_enricher.py scripts\test_intraday_alert_advisor_enricher.py`; `python scripts\test_intraday_alert_advisor_enricher.py`; `python scripts\intraday_alert_advisor_enricher.py --handoff tmp\intraday-alerts\forced-main-session-handoff.json --output-json tmp\intraday-alerts\advisor-alert-packet.json --output-md tmp\intraday-alerts\advisor-alert-packet.md --validation-output tmp\intraday-alerts\advisor-alert-packet-validation.json`.
- 2026-05-19 Phase 5 implementation proof: `scripts/intraday_alert_outcome_link.py` and `scripts/test_intraday_alert_outcome_link.py` now create/validate a proposal-only WF55 outcome-link artifact from the Phase 4 advisor packet. Output `tmp/intraday-alerts/advisor-alert-outcome-link.json/.md` records the forced ETN packet id, ticker, trigger, advisor recommendation posture, owner decision placeholder, action/no-action placeholder, timestamp, follow-up window, realized-outcome placeholder, WF55/Call Log proposal state, source artifact hash, and hard-false authority block. Validation `tmp/intraday-alerts/advisor-alert-outcome-link-validation.json` is ok 0 critical / 0 warning. No Call Log/state-history append was applied; probability/modeling claims remain blocked.
- 2026-05-19 Phase 6 implementation proof: `scripts/daily_review_objects.py`, `scripts/portfolio_mutation_proposal_generator.py`, `scripts/capital_deployment_recommendation_validator.py`, and `scripts/intraday_alert_advisor_enricher.py` now prevent live written-band/advisor contradictions. In-band conditional-review candidates cannot be labeled `wait_for_band`; live written-band status is separated from proposed-band/reclaim status; validators fail `IN_BAND` + `wait_for_band` and above-band false-green combinations; advisor packets record observed alert entry status. ETN regenerated as `DEPLOYABLE NOW` / `IN_BAND` with `recommended_action=owner_decision_required` and advisor `recommendation_posture=owner_decision_required`; GOOG/MSFT remain `ABOVE_BAND_WAIT` / no-chase, with MSFT's `BELOW_RECLAIM_STOP` preserved only as proposed/reclaim context. Proof passed: py_compile, targeted daily review/proposal/advisor/outcome tests, dashboard validation, daily-review regeneration, capital recommendation generation/validator ok 0/0, advisor enricher ok 0/0, and outcome-link regeneration ok 0/0.
- 2026-05-19 Phase 7 design proof: proposal-only runtime handoff design artifacts now exist at `tmp/intraday-alerts/runtime-handoff-design.json/.md`, with validator `scripts/intraday_alert_runtime_handoff_validator.py` and validation artifact `tmp/intraday-alerts/runtime-handoff-design-validation.json`. The design proposes a future two-job pattern only: isolated read-only WF68 producer plus paired main-session `systemEvent` handoff/fallback. It explicitly preserves `NO_REPLY` quiet behavior, `ALERT_READY` changed-alert behavior, stale/current-but-not-intraday-fresh no-fire downgrade, main-session fallback/watchdog visibility, failure/action-needed reporting, and approval gates before any runtime mutation. Proof passed: `python -m py_compile scripts\intraday_alert_runtime_handoff_validator.py`; `python scripts\intraday_alert_runtime_handoff_validator.py --write` returned status ok 0 critical / 0 warning. No cron/systemEvent/channel/config/auth/runtime/brokerage/paper-trading/portfolio/canon/Call Log mutation was applied; actual runtime wiring remains owner-gated and blocked.
- 2026-05-19 runtime wiring phased design proof: `tmp/intraday-alerts/runtime-wiring-phase-plan.json/.md` now completes the exact Cron/SystemEvent wiring design without applying it. The plan recommends updating the existing intraday watcher pair in place (`a9f14c77-9223-4760-9e8e-e83417708b38` producer at `5,35 6-12 * * 1-5`; `a6b30d94-629f-44f6-b9c7-e3bd16f25a44` main handoff at `8,38 6-12 * * 1-5`) to avoid duplicate market-hours writers. It defines phases 0-6: preflight, shadow runtime-status artifact, exact job preview, manual pre-enable proof, owner-approved apply, post-enable validation, and pilot observation. Validation `scripts/wf68_runtime_wiring_plan_validator.py --write` is ok 0 critical / 0 warning. No cron/systemEvent mutation was applied; apply remains blocked pending Randall approval of exact job patches.
- 2026-05-19 runtime enablement proof: Randall approved applying the WF68 in-place cron updates at 17:28 MST. The existing intraday watcher pair was updated in place rather than duplicated. Producer `a9f14c77-9223-4760-9e8e-e83417708b38` is now `Finance - WF68 Intraday Alert Producer`, isolated, `5,35 6-12 * * 1-5` America/Phoenix, running `scripts\wf68_intraday_alert_producer.py` with read/exec only and delivery none. Handoff `a6b30d94-629f-44f6-b9c7-e3bd16f25a44` is now `Finance - Main Session WF68 Intraday Alert Handoff`, main `systemEvent`, `8,38 6-12 * * 1-5`, reporting only `ALERT_READY`, stale/missing/failed/action-needed states, or exact `NO_REPLY`. Post-enable validation artifact `tmp/intraday-alerts/runtime-post-enable-validation.json/.md` is `status=ok`: forced producer run `manual:a9f14c77-9223-4760-9e8e-e83417708b38:1779237079250:1` completed ok; `runtime-handoff-status.json` is `status=ok`, `handoff_status=NO_REPLY`, `action_needed=false`, `authority_clean=true`; `main-session-handoff.json` is `NO_REPLY`; trigger validation is ok with 0 actionable alerts; quote validation has 0 critical / 10 warning stale-freshness downgrades; no authority expansion occurred. Pilot observation during the next ordinary market-hours window remains the next runtime acceptance step.
- 2026-05-20 market-hours pilot repair/proof: first ordinary pilot surfaced a real runtime blocker: quote `received_at_utc` was truncated to whole seconds while Alpaca source timestamps include fractional/nanosecond precision, causing one valid alert to fail `source_timestamp_after_received_at`; advisor enrichment also could not resolve `current-alerts.json#alerts[...]` collection refs and produced missing thesis/boundary validation errors for current handoff alerts. Fixed `scripts/intraday_quote_snapshot_proof.py` to preserve sub-second receive precision; fixed `scripts/intraday_alert_advisor_enricher.py` to resolve collection-fragment packet refs and keep missing-ticker recommendation context hard-false for trade/account action; tightened `scripts/test_intraday_alert_advisor_enricher.py` so the quiet-path test uses an explicit temp `NO_REPLY` handoff instead of mutable live artifacts. Proof passed: py_compile, targeted advisor-enricher tests, and `python scripts\wf68_intraday_alert_producer.py`. Current runtime status is `ok`, `handoff_status=ALERT_READY`, `action_needed=true`, `validation_bad=[]`, `authority_clean=true`; trigger validation ok for 10/10 packets; advisor validation ok 0 critical / 0 warning over 10 alerts; outcome-link validation ok 10 records / 0 findings. Current alerts are review-only and include CRITICAL stop breaches for JPM/LMT/BRK.B/BKNG, HIGH in-band review for ETN/AMZN, and MONITOR no-chase states for GOOG/MSFT/XOM/NVDA. No order, paper execution, account action, canon/portfolio mutation, Call Log/state-history append, config/channel mutation, or approval inference occurred.
- 2026-05-21 trade-ready delivery policy update: Randall narrowed immediate WF68 alerts to only in-band trade-ready recommendation packets with sizing, price, stop/reference, and a one-word approval contract. Added `scripts/intraday_alert_delivery_router.py` and `scripts/test_intraday_alert_delivery_router.py`; patched `scripts/wf68_intraday_alert_producer.py` so the runtime handoff is `EXECUTION_PACKET_READY` only when the router creates immediate paper execution recommendation packets, `GROUPED_DIGEST_READY` for non-immediate stop/no-chase/monitor/not-ready alerts, and `NO_REPLY` when quiet. Updated main handoff cron `a6b30d94-629f-44f6-b9c7-e3bd16f25a44`; added weekday 13:10 MST grouped digest handoff `f8418a21-1231-48ee-9135-b530e170cfbc`. Proof passed: py_compile, router targeted tests, manual router generation over the prior advisor packet, and manual full producer ok/NO_REPLY after market. Boundary preserved: recommendation packets only; no live execution, no paper execution without exact approval plus WF67 request/guard/kill-switch/audit, no portfolio/canon/cash/sizing/sleeve/risk-rule mutation, and no owner-approval inference.
- 2026-05-21 evidence-adequacy contract hardening: `scripts/intraday_alert_advisor_enricher.py` now adds `official_evidence_adequacy` to each advisor decision packet with latest official evidence, captured adjusted EPS/guidance/growth/margin/orders-backlog/management/acquisition facts, missing/manual-required fields, blockers, and an explicit sufficient/insufficient decision for downstream paper-execution recommendation packaging. `scripts/intraday_alert_delivery_router.py` now blocks/downgrades otherwise in-band packets when official evidence adequacy is missing or insufficient; `scripts/capital_deployment_recommendation_validator.py` now critical-fails in-band deploy/execution candidates that lack current/manual-confirmed official evidence, captured official fact context, or have unresolved official fields. Closeout now consumes 20 validated official captures after the CAT/CVX/PLTR/AMD/LLY/META/PH/GE batch-2 expansion, and `not_applicable` fields are explicitly addressed without being treated as numeric captures. Proof passed: py_compile, targeted advisor/router/not-applicable tests, advisor enricher regeneration, router regeneration, `capital_deployment_recommendation_validator.py --write`, and router status `GROUPED_DIGEST_READY` with no immediate packet because no current packet met trade-ready/evidence criteria. Boundary preserved: evidence gates recommendation packaging only; no live/paper order, account action, portfolio/canon mutation, or owner-approval inference.
- 2026-06-01 Telegram shadow pilot enablement: added `scripts/wf68_telegram_notifier.py` and `scripts/test_wf68_telegram_notifier.py`; created cron `67c3eeaf-4040-4be4-a2b3-7a6dd3280baf` (`Finance - WF68 Telegram Shadow Alert Notifier`) at `10,40 6-12 * * 1-5` America/Phoenix. The notifier reads `runtime-handoff-status.json` and `delivery-router-status.json`, sends through `openclaw message send --channel telegram --target 8650152206 --message ...` only when packets are fresh and authority-clean, and writes `tmp/intraday-alerts/telegram-notifier-status.json/.md`. Manual cron proof completed ok and blocked the stale June 1 execution packet (`artifact_stale:545.2min_gt_45min`, `sent_count=0`), so no old alert was sent. Reply contract in shadow mode is `REVIEW` or `PREPARE`; `APPROVE` is not active. Boundary preserved: no paper/live order submission or cancellation, brokerage/account mutation, money movement, live endpoint/credential use, canon/portfolio/sizing/sleeve/cash/risk-rule mutation, or owner-approval inference.
- 2026-05-19 Phase 1 read-only market-data proof passed for Alpaca market data using paper-named credentials and GET-only sanitized snapshots. New proof script/artifacts: `scripts/intraday_quote_snapshot_proof.py`, `tmp/intraday-alerts/quote-snapshot-proof.json`, `tmp/intraday-alerts/quote-snapshot-proof.md`, and `tmp/intraday-alerts/quote-snapshot-proof-validation.json`. Proof command: `python -m py_compile scripts\intraday_quote_snapshot_proof.py`; `python scripts\intraday_quote_snapshot_proof.py` returned `status=ok`. The proof covered first 10 tracked-universe symbols including ETN (`ETN`, `JPM`, `GOOG`, `MSFT`, `LMT`, `BRK.B`, `XOM`, `NVDA`, `AMZN`, `BKNG`), persisted provider/source timestamps/received time/price/bid/ask only, and persisted no secrets/raw headers/raw bodies. Freshness was `current_but_not_intraday_fresh` because the run occurred after the regular close; Phase 2 must treat stale/missing quotes as no-fire/monitor-only and not as a trigger-green state.
- 2026-05-19 Phase 2 implementation proof: `scripts/intraday_alert_trigger_engine.py` now consumes `tmp/intraday-alerts/quote-snapshot-proof.json`, `tmp/portfolio-config.json`, and sanitized WF67 paper result state to produce review-only `tmp/intraday-alerts/current-alerts.json`, `.md`, and `trigger-engine-validation.json`. The v1 engine tracks Core 10 plus active paper-position symbols, emits packets only for fresh/current quote evidence, and hard no-fires `current_but_not_intraday_fresh` / stale / missing / partial / ambiguous inputs. Targeted tests cover in-band entry, below-stop, above-no-chase, stale/no-fire, duplicate suppression, and paper-fill state-change placeholder. Proof passed: `python -m py_compile scripts\intraday_alert_trigger_engine.py scripts\test_intraday_alert_trigger_engine.py`; `python scripts\test_intraday_alert_trigger_engine.py`; `python scripts\intraday_alert_trigger_engine.py`; `python scripts\intraday_alert_packet_validator.py --write`; `python scripts\test_intraday_alert_packet_validator.py`. Current live artifact emitted 0 alert packets, 10 no-fire/monitor-only rows because quotes are `current_but_not_intraday_fresh`, and one ETN paper-state placeholder (`pending_new`); authority remains hard-false with no paper/live order, account, brokerage, canonical/portfolio, cron/channel/config, sizing/sleeve/cash/risk-rule mutation, or inferred owner approval.
- 2026-05-19 Phase 3 implementation proof: `scripts/intraday_alert_main_handoff.py` and `scripts/test_intraday_alert_main_handoff.py` now create a reliable OpenClaw/main-session handoff artifact surface without external channels or config/cron mutation. Current no-alert input writes `tmp/intraday-alerts/main-session-handoff.json/.md` with `status=NO_REPLY`, `alert_count=0`, no-fire count 10, and quiet/no-noise instructions. Forced ETN fixture writes `tmp/intraday-alerts/forced-main-session-handoff.json/.md` with `status=ALERT_READY`, `highest_severity=HIGH`, packet path `tmp\intraday-alerts\forced-alert-fixture.etn.json`, compact user-facing summary, and hard-false authority. Actual `systemEvent` injection was not attempted because this phase avoided cron/config/channel mutation; proof is artifact-level main-session consumption contract only. Proof passed: `python -m py_compile scripts\intraday_alert_main_handoff.py scripts\test_intraday_alert_main_handoff.py scripts\intraday_alert_packet_validator.py scripts\intraday_alert_trigger_engine.py`; `python scripts\test_intraday_alert_main_handoff.py`; `python scripts\intraday_alert_main_handoff.py --input tmp\intraday-alerts\current-alerts.json ...`; `python scripts\intraday_alert_main_handoff.py --input tmp\intraday-alerts\forced-alert-fixture.etn.json ...`; `python scripts\intraday_alert_packet_validator.py tmp\intraday-alerts\forced-alert-fixture.etn.json --write`.

## Scope
- Intraday market-data polling, initially via Alpaca market data if paper endpoint/data access proves available and safe.
- Event trigger detection over existing owner truth surfaces:
  - price enters/reclaims/breaches written bands
  - stop/reference invalidation breach
  - no-chase/upper-band breach
  - volatility or gap move large enough to affect written thesis/risk
  - catalyst window open/close
  - paper-position/fill/outcome state change
- Alert packet contract:
  - ticker/event/severity
  - source timestamp and freshness
  - owner-surface links
  - thesis/why-stack/invalidation
  - action type: `review`, `prepare_packet`, `owner_decision_required`, or `no_action`
  - authority block preserving no trade/account action and no inferred approval
- Alert dedup/rate limits aligned with `HEARTBEAT.md`: useful signal, no noise.

## Retail SaaS Role Under Current P0 Goal

As of 2026-05-29, Retail Investor Finance Intelligence SaaS is the P0 product goal. WF68 is no longer the top workspace goal by itself; it is a gated alert/notification engine lane feeding the retail SaaS architecture.

Supporting lanes should be sequenced by how directly they unblock safe retail-investor intelligence delivery:
1. **WF75/P0 retail SaaS** - fixture-only customer demo, customer-safe export contract, and executable no-leak/no-unsupported-claim validator.
2. **WF68 alert/notification lane** - alert packet schema, read-only intraday data proof, quiet/noise rules, and future customer-safe notification concepts.
3. **WF55** - outcome retention and probability readiness gate; win-rate/probability/expected-return claims remain blocked.
4. **WF70/WF66/WF77/WF78** - official evidence, why-stack, router, and scaleout inputs that make alerts decision-grade without exposing internal proof surfaces.
5. **WF67/WF63** - internal paper-position visibility and simulation guardrails only; no customer-facing execution or brokerage/account connection for MVP.
6. **OS cleanup** - only when it reduces startup cost/drift for the retail SaaS and finance-engine truth surfaces.

Deprioritize WF68 work that does not directly improve safe retail-investor alerts, evidence quality, stale-data disclosure, outcome measurement, or safety boundaries.

## Phased Plan

### Phase 0 - Contract and boundaries
- Define alert taxonomy: `CRITICAL`, `HIGH`, `MONITOR`, `INFO`.
- Define quiet/noise rules, dedupe keys, stale-data downgrade rules, and owner-gated authority language.
- Define packet schema and validator before any scheduler runs.

Acceptance gate:
- Schema + validator reject missing freshness, missing authority block, missing owner-surface reference, or any trade/account/approval implication.
- Status 2026-05-19: **Phase 0 implemented / proof-clean** for the local packet contract. Validator additionally rejects missing source timestamp, stale represented data, ambiguous represented data, missing dedupe/rate-limit contract, and true hard-authority flags for live trade/account action, paper trade, canonical note mutation, portfolio mutation, owner approval inference, and sizing/sleeve/cash/risk-rule changes.

### Phase 1 - Intraday data proof
- Prove a read-only intraday quote/snapshot path, preferably Alpaca market data if available under paper-safe configuration.
- Persist only sanitized quote snapshots/alert inputs under `tmp/`, with source timestamp and no secrets/raw headers.
- If Alpaca data is unavailable, stop with a provider-gap report instead of faking realtime.

Acceptance gate:
- Read-only data proof passes, secrets are not persisted, and stale/missing/current-but-not-intraday-fresh quotes degrade alerts instead of firing false-green events.
- Status 2026-05-19: **Phase 1 implemented / proof-clean with freshness downgrade**. Market-data GET path works, but because the run was post-close, all 10 snapshots are `current_but_not_intraday_fresh`; Phase 2 must treat that state as no-fire or monitor-only until genuinely fresh intraday quotes exist.
- Status 2026-05-19: **Phase 1 implemented / proof-clean** for Alpaca market-data GET snapshots with hard-false authority and sanitized artifacts. Current artifact freshness is post-close/current, not live-market fresh; trigger logic must preserve freshness downgrades.
- Status 2026-05-19: **Phase 2 implemented / proof-clean** for a local review-only trigger engine over Core 10 plus active sanitized paper state. Current output intentionally no-fired all price alerts because the Phase 1 quotes are `current_but_not_intraday_fresh`; fresh/current forced test fixtures prove HIGH/CRITICAL/MONITOR packet behavior and duplicate suppression without widening authority.

### Phase 2 - Trigger engine v1
- Implement thin trigger logic over the Execution Board / portfolio config / paper-position surfaces.
- Start with Core 10 plus active paper positions, not all 44 coverage names.
- Produce alert packets only; no canonical mutation and no paper/live order.

Acceptance gate:
- Tests cover in-band entry, below-stop, above-no-chase, stale quote, duplicate alert suppression, and paper-fill state change.
- Status 2026-05-19: **Phase 2 implemented / QA-pass**. Current post-close quote input correctly emits no actionable alerts and records no-fire/monitor-only rows. Trigger expansion beyond Core 10 should first fix the non-Core active-paper missing-band no-fire edge.

### Phase 3 - Main-session alert handoff
- Route alert packets into the current/main OpenClaw surface using reliable main-session systemEvent/handoff patterns, not isolated-run delivery assumptions.
- Include compact decision packets, not long reports.
- `NO_REPLY`/quiet behavior allowed only when no material alert exists.

Acceptance gate:
- Manual forced alert reaches main/session surface with correct severity, packet path, owner-gated boundary, and no channel dependency.
- Status 2026-05-19: **Phase 3 implemented / QA-pass as artifact-proof**. Forced handoff artifact is alert-ready and current no-alert artifact is `NO_REPLY`; actual `systemEvent`/cron wiring is not yet implemented and remains separately owner-gated.
- Status 2026-05-19: **Phase 3 artifact-proof implemented / actual systemEvent not injected**. The main-session consumption contract is now represented by `tmp/intraday-alerts/forced-main-session-handoff.json/.md` for the manual forced alert and `tmp/intraday-alerts/main-session-handoff.json/.md` for no-alert quiet behavior. This proves the no-channel artifact handoff surface; a future actual systemEvent hook remains a separate cron/runtime wiring decision.

### Phase 4 - Advisor integration
- Attach WF66 why-stack and WF58 recommendation context to each actionable alert.
- Alerts recommend review/prepare/owner-decision steps. Paper buy/sell execution may occur only by handing an advisor-derived package to WF67 under the standing paper-only approval, scoped request artifact, fresh kill switch, guard validation, audit log, and main-session capital-package notification; WF68 itself does not use live endpoints or brokerage/account authority.
- Feed resolved alerts/outcomes into WF55/Call Log.

Acceptance gate:
- At least one alert demonstrates thesis/invalidation/entry/stop/source freshness and later outcome linkage without probability claims.
- Status 2026-05-19: **Phase 4 implemented / QA-pass as artifact-proof** using the forced ETN alert. Advisor packet is `ADVISOR_READY`; outcome linkage is a placeholder only and probability claims are blocked until WF55 is proof-clean.
- Status 2026-05-19: **Phase 4 implemented / proof-clean as artifact-proof** using the forced ETN handoff. Actual WF55/Call Log outcome writeback is not implemented yet; Phase 5 should add append-only outcome linkage without probability claims.

### Phase 5 - Outcome-link proposal
- Convert advisor alerts into WF55/Call Log outcome-link proposal artifacts.
- Preserve known-at-time alert context and append/reconcile later only through a reviewed WF55 pass.
- Keep probability/modeling claims blocked until WF55 retention is proof-clean.

Acceptance gate:
- Outcome-link artifact records packet_id, ticker, alert trigger, advisor recommendation posture, owner decision placeholder, action/no-action placeholder, timestamp, follow-up window, realized-outcome placeholder, source provenance/hash, and hard-false authority.
- Status 2026-05-19: **Phase 5 implemented / proof-clean as artifact-proof**. `tmp/intraday-alerts/advisor-alert-outcome-link.json/.md` and validation exist; no canonical Call Log mutation or state-history append was applied.

### Phase 6 - Advisory surface contradiction cleanup
- Clean action-language and dashboard/advisory contradictions before any runtime wiring.
- Preserve review-only/owner-gated semantics when a ticker is in band but still has source/trust/risk blockers.

Acceptance gate:
- In-band candidates must not be labeled `wait_for_band`; unresolved blockers should route to `owner_decision_required` / review-only language.
- Above-band/no-chase candidates must not render as clean deployable-now.
- Status 2026-05-19: **Phase 6 implemented / proof-clean as artifact-proof**. Live written-band status is now separated from proposed-band/reclaim status; `daily_review_objects.py` maps in-band `conditional_pullback_review` capital packets to `owner_decision_required`; validators reject `IN_BAND` + `wait_for_band` and above-band false-green action language; regenerated ETN capital/advisor/outcome-link artifacts now show `IN_BAND` + `owner_decision_required`, not `wait_for_band`. GOOG/MSFT current artifacts remain no-chase/above-band rather than false-green deployable.

## Dependencies
- WF55 - Probability Readiness and Outcome Retention Gate: outcome/call-log feedback loop.
- WF41 - Market Intelligence Event Intake and Materiality Router: event/materiality routing semantics.
- WF58 - Dashboard Freshness / capital recommendation packets: advisory packet context.
- WF63/WF67 - Alpaca paper/read-only proof and paper position reconciliation.
- WF66 - why-aware evidence bridge.

## Stop Lines
- No live trading, live endpoint/credential use, brokerage/account mutation, money movement, or account settings changes.
- No live submit/cancel from this workflow. Paper submit/cancel/sell may be routed only through WF67's approved paper wrapper after an advisor/capital package, scoped request artifact, fresh kill switch, validator-clean guard, audit log, and main-session capital-package notification.
- No owner approval inference from alert severity, score, validator success, or packet quality. The 2026-05-19 standing approval covers paper-only advisor packages under WF67; it does not authorize live trading or unscoped paper orders.
- No canonical finance note or portfolio mutation from alert generation.
- No broad external news/firehose intake until source policy and rate/noise controls are explicitly approved.
- No channel/auth/config/runtime mutation without explicit owner approval and a security/runtime posture review.
- Stop if intraday data is stale/missing/ambiguous or cannot prove read-only behavior.

## 2026-05-20 Alpaca Market Data Expansion Recommendation

Randall approved proceeding with the Alpaca intelligence recommendations. WF68 should treat Alpaca market data as the primary intraday data spine while preserving read-only authority:

- **Core v1:** latest quotes, snapshots, latest trades, minute bars, daily/previous daily bars, bid/ask spread, source timestamp, freshness class, and no-fire downgrade reasons.
- **Operational context:** market calendar/clock for market-hours cron behavior and stale-data interpretation.
- **Review-only expansion:** Alpaca news and market movers may feed a secondary event/intelligence queue after source/noise controls exist; they do not outrank company IR/SEC evidence and do not authorize action.
- **Later optional context:** corporate actions for data hygiene, options data if enabled for positioning/sentiment research only, and crypto data only if a regulated crypto context is explicitly added.

Implementation should harden `scripts/intraday_quote_snapshot_proof.py` / `scripts/wf68_intraday_alert_producer.py` into a stable `alpaca_market_data_spine` artifact rather than expanding triggers blindly. Acceptance requires sanitized artifacts, no secret/raw header/body persistence, GET-only market-data endpoint use, freshness/spread validation, no brokerage endpoint use, and unchanged hard-false authority flags.

## Next Action
- Observe the next market-hours WF68 Telegram shadow run and confirm fresh `EXECUTION_PACKET_READY` packets deliver while stale/noisy states remain quiet or blocker-only. If Randall replies `PREPARE`, create a WF67 paper request artifact and guard proof only; keep execution blocked until exact approval, fresh kill switch, WF67 guard validation, paper wrapper, and redacted audit are complete. In parallel, build WF68 market-data spine v2 around Alpaca quotes/snapshots/bars/spread/calendar. Do not add Discord/Signal/email, live orders, account mutation, canonical/portfolio mutation, Call Log/state-history mutation from alerts, unapproved channel/config/auth mutation, or owner-approval inference.

## Key Files
- `03. Portfolio/Execution Board.md` - band/stop/action owner surface.
- `tmp/portfolio-config.json` - machine-readable execution/reference bands.
- `tmp/alpaca-paper-readiness/*` - paper proof/position/fill surfaces.
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json` - review-only advisory context.
- `tmp/capital-deployment-recommendation-validation.json` - authority validation context.
- `tmp/intraday-alerts/alert-packet.schema.json` - Phase 0 packet schema/contract.
- `tmp/intraday-alerts/forced-alert-fixture.etn.json` - valid forced ETN alert fixture.
- `tmp/intraday-alerts/invalid-authority-fixture.sample.json` - intentionally invalid regression/proof fixture.
- `scripts/intraday_alert_packet_validator.py` - Phase 0 validator.
- `scripts/test_intraday_alert_packet_validator.py` - targeted validator behavior proof.
- `scripts/intraday_quote_snapshot_proof.py` - Phase 1 read-only Alpaca market-data quote/snapshot proof.
- `tmp/intraday-alerts/quote-snapshot-proof.json` - sanitized Phase 1 quote/snapshot proof artifact.
- `tmp/intraday-alerts/quote-snapshot-proof.md` - human-readable Phase 1 quote/snapshot proof artifact.
- `tmp/intraday-alerts/quote-snapshot-proof-validation.json` - Phase 1 proof validation artifact.
- `scripts/intraday_alert_trigger_engine.py` - Phase 2 review-only trigger engine over sanitized quote proof, portfolio bands/stops, and paper-state placeholder input.
- `scripts/test_intraday_alert_trigger_engine.py` - targeted Phase 2 trigger behavior proof.
- `tmp/intraday-alerts/current-alerts.json` - current Phase 2 alert/no-fire artifact.
- `tmp/intraday-alerts/current-alerts.md` - human-readable current Phase 2 alert/no-fire artifact.
- `tmp/intraday-alerts/trigger-engine-validation.json` - Phase 2 trigger output validation/proof artifact.
- `scripts/intraday_alert_main_handoff.py` - Phase 3 main-session/OpenClaw handoff artifact builder for current-alerts collections or single forced alert packets.
- `scripts/test_intraday_alert_main_handoff.py` - targeted Phase 3 handoff behavior proof.
- `tmp/intraday-alerts/main-session-handoff.json` - current no-alert `NO_REPLY` handoff artifact.
- `tmp/intraday-alerts/main-session-handoff.md` - human-readable current no-alert handoff artifact.
- `tmp/intraday-alerts/forced-main-session-handoff.json` - forced ETN alert handoff proof artifact.
- `tmp/intraday-alerts/forced-main-session-handoff.md` - human-readable forced ETN alert handoff proof artifact.
- `scripts/intraday_alert_advisor_enricher.py` - Phase 4 advisor enricher attaching WF58 recommendation context and WF66/official-source why-stack context to actionable handoffs while preserving no-authority boundaries.
- `scripts/test_intraday_alert_advisor_enricher.py` - targeted Phase 4 advisor-enricher behavior proof.
- `tmp/intraday-alerts/advisor-alert-packet.json` - forced ETN advisor alert proof packet.
- `tmp/intraday-alerts/advisor-alert-packet.md` - human-readable forced ETN advisor alert proof packet.
- `tmp/intraday-alerts/advisor-alert-packet-validation.json` - Phase 4 advisor packet validation/proof artifact.
- `scripts/intraday_alert_outcome_link.py` - Phase 5 WF55/Call Log outcome-link proposal builder for advisor alerts.
- `scripts/test_intraday_alert_outcome_link.py` - targeted Phase 5 outcome-link behavior proof.
- `tmp/intraday-alerts/advisor-alert-outcome-link.json` - Phase 5 proposal-only outcome-link artifact.
- `tmp/intraday-alerts/advisor-alert-outcome-link.md` - human-readable Phase 5 outcome-link artifact.
- `tmp/intraday-alerts/advisor-alert-outcome-link-validation.json` - Phase 5 validation/proof artifact.
- `tmp/intraday-alerts/runtime-handoff-design.json` - Phase 7 proposal-only runtime handoff design artifact; no cron/systemEvent mutation authority.
- `tmp/intraday-alerts/runtime-handoff-design.md` - human-readable Phase 7 runtime handoff design.
- `tmp/intraday-alerts/runtime-handoff-design-validation.json` - Phase 7 design validation/proof artifact.
- `scripts/intraday_alert_runtime_handoff_validator.py` - validates the Phase 7 design boundary, input/output contract, quiet/noise behavior, fallback/watchdog, failure visibility, approval gates, and hard-false authority.
- `scripts/wf68_intraday_alert_producer.py` - deterministic runtime producer wrapper used by the enabled WF68 producer cron job.
- `tmp/intraday-alerts/runtime-handoff-status.json` - latest runtime wrapper status, including handoff status, action-needed state, and authority-clean proof.
- `tmp/intraday-alerts/runtime-handoff-status.md` - human-readable latest runtime wrapper status.
- `scripts/wf68_telegram_notifier.py` - Telegram shadow notifier for fresh WF68 `EXECUTION_PACKET_READY` packets and blocker visibility only; no execution or approval authority.
- `scripts/test_wf68_telegram_notifier.py` - targeted notifier proof for fresh dry-run, stale block, and quiet `NO_REPLY` behavior.
- `tmp/intraday-alerts/telegram-notifier-status.json` - latest notifier proof, send/blocker status, message preview, and authority block.
- `tmp/intraday-alerts/telegram-notifier-status.md` - human-readable latest notifier proof.
- `tmp/intraday-alerts/runtime-post-enable-validation.json` - post-enable cron/runtime validation proof for the owner-approved in-place cron updates.
- `tmp/intraday-alerts/runtime-post-enable-validation.md` - human-readable post-enable validation summary.

## Checkpoint Decision
- Open as the primary alerting/advisor-upgrade workflow.
- Historical 2026-05-19 decision: promote FA/advisor-grade monitoring + alerting to the primary workspace goal.
- Supersession 2026-05-29: Retail Investor Finance Intelligence SaaS is now the primary product/workspace goal; WF68 remains an engine lane for bounded alerting and customer-safe notification concepts.
- Treat delivery-channel restoration as gated and separate for now; prove the advisor loop inside OpenClaw first, then revisit a single push channel only through explicit owner approval and security controls.


## WF68 delivery-channel approval packet - 2026-05-24

- Advisor validation blocker `in_band_alert_labeled_wait_for_band:4` was cleared by refreshing the advisor packet against current recommendation context. Current internal runtime proof is clean and quiet: `tmp/intraday-alerts/runtime-handoff-status.json` shows `status=ok`, `handoff_status=NO_REPLY`, `action_needed=false`, and `authority_clean=true`.
- Created owner-decision packet `tmp/wf68-delivery-channel-approval-packet.json/.md`. Recommended first path is local Control UI/current-session delivery-only pilot; artifact-only mode remains safe; any named external channel requires separate provider/recipient/rate/redaction/rollback approval.
- Boundary preserved: no delivery apply, no config/auth/channel/service mutation, no live or paper execution, no brokerage/account action, no money movement, no canon/portfolio/Call Log mutation, no probability claims, and no owner-approval inference.
- Next action: Randall chooses delivery path A/B/C from the packet; until approved, WF68 remains artifact/runtime-only and market-hours observation continues.

## 2026-06-05 deployment-state contract migration dependency

WF68 current-alert and advisor packets consume deployment/action status from the broader dashboard/deployment stack. Randall asked to slim duplicated state fields after XOM exposed `workflow_state`, `machine_state`, and `action_state` together.

Plan owner: `06. Playbooks/Project Continuity/Deployment State Contract Migration.md`.

WF68 role:
- Continue reading legacy fields until the shared contract is additive and validated.
- Prefer canonical user-facing state labels in Telegram/status output once the helper exists.
- Do not allow the migration to weaken stale-data, no-chase, below-stop, review-only, owner-approval, paper/live, or account-action boundaries.

Acceptance addition:
- WF68 validates cleanly after any state-contract change, including `wf68_intraday_alert_producer.py`, trigger validation, advisor packet validation, and delivery-router status.
