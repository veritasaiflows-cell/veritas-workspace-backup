# Workflow 52 - Earnings Date Source Confidence and Event Calendar Roll-Forward Automation

## Objective

Harden earnings-date maintenance so stale Event Calendar dates are detected automatically, provider next dates are staged/applied with honest confidence labels, and canonical calendar edits remain bounded to Randall-approved Event Calendar freshness without widening portfolio/deployment authority.

## User request trigger

Opened on 2026-05-10 after Randall asked how to fix the remaining NVDA timing uncertainty and automate:
- stale vault-date detection
- comparison against provider next dates
- staged Event Calendar roll-forward proposals
- confidence labeling as `provider_estimate_unconfirmed`

## Current State

- `scripts/earnings_calendar_enrichment.py` no longer contains hard-coded stale May comparison dates.
- Active timing-sensitive baselines live in `tmp/portfolio-config.json -> earnings_date_watchlist`.
- NVDA remains in that configured timing-sensitive watchlist because the May 20 date is near-term; Randall manually confirmed on 2026-05-10 that the official NVIDIA Investor Relations Events & Presentations page shows May 20, 2026 2:00 PM PT for NVIDIA 1st Quarter FY27 Financial Results.
- Direct NVIDIA IR event-page fetch previously returned 403 in this runtime; current source-confidence probing can reach at least one NVIDIA primary/company surface but may still fail to parse the date from fetched content.
- NVDA is now primary-confirmed in `tmp/portfolio-config.json -> earnings_date_watchlist.NVDA.primary_evidence` based on Randall's manual browser check of the official NVIDIA IR page.
- `scripts/earnings_date_source_confidence.py` now emits a review-only timing-sensitive source-confidence packet from `tmp/portfolio-config.json -> earnings_date_watchlist`, provider evidence, optional browser-sidecar evidence, and configured primary-source probes.
- `scripts/event_calendar_rollforward.py` now emits review-only roll-forward proposals from `tmp/earnings-calendar.json`, `tmp/earnings-date-source-confidence.json`, `tmp/portfolio-config.json`, and `05. Intelligence/Event Calendar.md`.
- Finance chain manifests now run source confidence after earnings enrichment, then Event Calendar roll-forward, then the bounded Event Calendar apply helper in morning, post-close, post-earnings, and Sunday windows.
- Browser confirmation is baked in as an optional sidecar input at `tmp/earnings-date-browser-confirmation.json`; it can upgrade a timing-sensitive date only when it provides official-source evidence with a matching date, URL, and visible matched text.
- Manual config confirmation is also evidence-gated: a bare `primary_confirmed: true` flag is ignored unless matching `primary_evidence` metadata is attached.
- Randall gave hardcoded approval on 2026-05-10 to keep `05. Intelligence/Event Calendar.md` fresh and integrate that maintenance into the daily chain updates.
- `scripts/event_calendar_apply.py` is now live as the bounded apply helper. It updates only the auto-managed provider-estimated roll-forward block plus narrow timing-source wording such as NVDA primary confirmation; it removes stale NVDA confirmation-deadline language once primary evidence is present.
- `05. Intelligence/Event Calendar.md` now carries an auto-managed provider-estimated next-earnings block for 10 staged names, with provider estimates explicitly labeled non-primary-confirmed and no portfolio/deployment/trade authority.

## Last Meaningful Progress

- Added `scripts/event_calendar_rollforward.py`.
- Added `scripts/test_event_calendar_rollforward.py`.
- Added `scripts/earnings_date_source_confidence.py`.
- Added `scripts/test_earnings_date_source_confidence.py`.
- Updated `scripts/chain_manifest.py` so finance chains run source confidence after `earnings_calendar_enrichment.py`, then run the roll-forward packet.
- Updated `scripts/earnings_date_source_confidence.py` to consume optional browser confirmation evidence before falling back to direct primary-source probes.
- Tightened `scripts/earnings_date_source_confidence.py` so manual `primary_confirmed` flags require attached `primary_evidence` before confidence can upgrade.
- Updated `scripts/README.md` to document both review-only helpers and the manual-evidence requirement.
- Added and proved `scripts/event_calendar_apply.py` plus `scripts/test_event_calendar_apply.py`.
- Generated current review/apply artifacts:
  - `tmp/earnings-date-source-confidence.json`
  - `optional Markdown digest beside `tmp/earnings-date-source-confidence.json``
  - `tmp/event-calendar-rollforward.json`
  - `optional Markdown digest beside `tmp/event-calendar-rollforward.json``
  - `tmp/event-calendar-apply.json`
  - `optional Markdown digest beside `tmp/event-calendar-apply.json``

## Outstanding

1. Extend source-confidence probes only where high-quality primary sources are known and parseable.
   - Preferred order: company IR / company release / SEC filing first, then credible secondary/provider dates.
   - If primary fetch is blocked by 403, bot protection, or inconclusive content, keep the provider date as unconfirmed and visible.
2. Implement/verify the actual browser runner when browser tooling is available in the scheduled runtime.
   - It should populate `tmp/earnings-date-browser-confirmation.json` only for unresolved timing-sensitive names.
   - It must stop on CAPTCHA/login/bot challenges rather than bypassing them.
3. Add dashboard/run-summary visibility for Event Calendar apply status or pending roll-forward proposals if they matter operationally.

## Blockers / Trust Gaps

- NVIDIA direct automation probing may still fail to confirm the May 20 date from fetched content because prior IR fetches showed 403/bot-protection risk, but Randall's manual browser check confirmed the official IR page date.
- yfinance is useful provider evidence but not canonical truth.
- Browser evidence is accepted only as a captured official-source confirmation artifact; a page visit, secondary source, or provider page is not enough.
- Event Calendar canonical mutation is now approved only for bounded freshness maintenance through `scripts/event_calendar_apply.py`; no silent portfolio, deployment, watchlist, sizing, trade, or owner-approval authority is authorized.
- Primary confirmation needs accessible company/SEC evidence, official browser-confirmation evidence, or explicit operator-provided `primary_evidence`; accepting provider-estimated wording is a separate caveated-calendar decision and must not be labeled primary-confirmed.
- Future earnings-date discrepancy responses must include sites Randall can check, prioritizing company IR/events pages, company newsroom/press releases, and SEC EDGAR.

## Next Action

WF52 is implemented for the bounded Event Calendar freshness path. Follow-up is limited to scheduled-runtime browser-runner verification and optional dashboard/run-summary visibility for Event Calendar apply status.

## Key Files

- `scripts/earnings_calendar_enrichment.py` - provider earnings-date refresh and timing-sensitive baseline comparison.
- `scripts/earnings_date_source_confidence.py` - review-only source-confidence packet for timing-sensitive earnings dates; consumes optional browser confirmation evidence.
- `scripts/test_earnings_date_source_confidence.py` - regression coverage for blocked primary fetches preserving provider-estimate confidence, bare config flags failing closed, valid manual primary evidence, and official browser evidence.
- `scripts/event_calendar_rollforward.py` - review-only roll-forward proposal generator.
- `scripts/test_event_calendar_rollforward.py` - regression coverage for stale vault-date detection and confidence labeling.
- `scripts/event_calendar_apply.py` - bounded Event Calendar apply helper approved for daily-chain freshness maintenance.
- `scripts/test_event_calendar_apply.py` - regression coverage for provider-estimate caveats, NVDA primary-confirmation cleanup, and same-day Last Updated idempotency.
- `tmp/portfolio-config.json` - machine-readable control layer, including `earnings_date_watchlist`.
- `tmp/earnings-calendar.json` - yfinance/provider evidence.
- `tmp/earnings-date-browser-confirmation.json` - optional official-source browser evidence sidecar; absent by default until browser runtime is verified.
- `tmp/earnings-date-source-confidence.json` - source-confidence result consumed before Event Calendar roll-forward.
- `tmp/event-calendar-rollforward.json` - staged roll-forward proposals.
- `optional Markdown digest beside `tmp/event-calendar-rollforward.json`` - human-readable review surface.
- `05. Intelligence/Event Calendar.md` - canonical human-readable catalyst calendar and interpretation layer.

## Automation / Refresh Path

Current safe phase: **scheduled bounded Event Calendar freshness maintenance**.

Recommended chain order:
1. `earnings_calendar_enrichment.py`
2. optional browser confirmation sidecar for unresolved timing-sensitive dates only, writing `tmp/earnings-date-browser-confirmation.json`
3. `earnings_date_source_confidence.py`
4. `event_calendar_rollforward.py`
5. `event_calendar_apply.py --apply`

Do not make browser confirmation a hard daily-chain dependency until the browser runtime is verified and repeated proof shows it fails closed without hanging or widening access.

Automated now:
- detect stale Event Calendar rows for tracked tickers
- compare against provider next earnings dates
- stage source-confidence packets for timing-sensitive dates
- consume optional official-source browser confirmation evidence when present
- stage roll-forward proposals
- apply the auto-managed Event Calendar roll-forward block as caveated provider-estimated dates
- update NVDA primary-confirmed wording when valid primary evidence is attached
- remove stale NVDA timing-deadline language after primary confirmation
- label proposal confidence as `provider_estimate_unconfirmed` unless explicitly primary-confirmed by official probe/browser evidence or valid attached `primary_evidence`

Still gated:
- primary-source confirmation claims without official/company/SEC evidence or valid operator-provided `primary_evidence`
- Event Calendar edits outside the bounded auto-managed roll-forward/timing-source scope
- the actual browser runner until browser tooling is verified in the scheduled/runtime environment
- downstream deployment or portfolio implications

## Acceptance Gates

- `python -m py_compile scripts\earnings_date_source_confidence.py scripts\test_earnings_date_source_confidence.py scripts\event_calendar_rollforward.py scripts\test_event_calendar_rollforward.py scripts\event_calendar_apply.py scripts\test_event_calendar_apply.py scripts\chain_manifest.py`
- `python scripts\test_earnings_date_source_confidence.py`
- `python scripts\test_event_calendar_rollforward.py`
- `python scripts\test_event_calendar_apply.py`
- `python scripts\earnings_date_source_confidence.py`
- `python scripts\event_calendar_rollforward.py`
- `python scripts\event_calendar_apply.py --apply`
- `python scripts\run_finance_refresh_chain.py morning --dry-run`
- `python scripts\run_finance_refresh_chain.py post-close --dry-run`
- `python scripts\run_finance_refresh_chain.py post-earnings --dry-run`
- `python scripts\run_finance_refresh_chain.py sunday --dry-run`
- No stale hard-coded date baselines remain in `earnings_calendar_enrichment.py`.
- Roll-forward proposals preserve confidence ceilings and do not mutate canonical notes.
- Bare manual `primary_confirmed` flags fail closed unless matching `primary_evidence` metadata is present.
- NVDA remains visible as timing-sensitive, but the May 20 date is now primary-confirmed from Randall's official NVIDIA IR browser evidence.

## 2026-05-10 Orchestration Update
- Controlled post-close real-chain proof passed without waiting for scheduled chain.
- Proof commands passed: py_compile, `scripts/test_event_calendar_apply.py`, and `python scripts\run_finance_refresh_chain.py post-close`.
- `tmp/run-chain-post-close.json` shows `status=ok`, `exit_code=0`.
- `tmp/event-calendar-apply.json` shows `status=ok`, `mode=apply`, `changed=true`, `applied_rollforward_count=10`, and `nvda_primary_confirmed=true`.
- Authority remained bounded: Event Calendar mutation only; no portfolio/deployment/watchlist/trade/account/owner-approval authority widened.
- Main artifact: `tmp/wf52-real-chain-proof-report.json` / `.md`.
- Closure judgment: WF52 is implemented for the approved bounded Event Calendar freshness path. Scheduled proof is residual/optional; browser-runner verification remains a separate follow-up.
