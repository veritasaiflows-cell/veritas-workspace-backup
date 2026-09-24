# Alert Event Ledger Design - 2026-09-23

Owner: Main. Requested by Randall in Telegram on 2026-09-23 at 16:33 America/Phoenix: *"Proceed as recommended"* (retention forever, no deletion, ledger before band redesign).

Status: **design approved 2026-09-23 16:45 MST; writer built and dry-run; live wiring pending owner go-ahead.** It grants no implementation-into-live-chain, schedule, canon, capital, order, brokerage, account, paper, live-execution, external-delivery, or publication authority. Nothing is wired into the recurring chain until Randall approves this record. Source finding: `Alerts OS Audit and Monetization Readiness - 2026-09-23.md` section 5.5 (O-1).

## Purpose

Build the alerts OS's first verifiable track record. Today the OS writes no outcome rows, so no accuracy claim can be made or checked, and history cannot be backfilled. The ledger records every alert *event* the OS emits, immutably, so a later scorer (O-2) can grade it.

The ledger records calls, not positions. It carries no sizing, allocation, holding, or execution field and must never gain one.

## Owner policy (decided 2026-09-23)

1. **Retention: permanent.** No time-based expiry. A track record with gaps cannot be trusted.
2. **No deletion.** Errors are fixed by appending a `correction` record that references the original by sequence and hash, with a reason. The original stays.
3. **One redaction exception.** If a record ever contains a secret, credential, or private account data, its payload may be replaced by a `redacted` marker. The chain stays valid because the chain hashes the payload hash, not the payload (see Integrity). Each redaction needs explicit owner approval and appends a `redaction` record.
4. **Ticker retirement** appends a `ticker_retired` record; prior records stay.
5. **Ledger retirement** freezes and archives the files; never deletes them.
6. **Bands are not a prerequisite.** Current mechanical bands are logged as `band_methodology_version = mech-v2-lowanchor` (support20/SMA50 range, invalidation = range low − 1.5×ATR20 after D9-A). Improved bands ship as new labeled versions and are scored separately.
7. **Not a product claim.** No performance figure derived from mechanical-band records may be presented externally.

## Storage

- Path: `state/finance/ledger/alert-events-v1.jsonl` (one JSON object per line, UTF-8, LF). Never under `tmp/`: the 2026-09-22 tmp cleanup already silently broke a finance dependency once.
- Head file: `state/finance/ledger/alert-events-v1.head.json` holding `{seq, record_hash, updated_at_utc}` for fast append and verification.
- Size: 32 names, edge-triggered, ~1.8 KB per record; measured dry run implies about 25–40 MB/year (see build status below). No rotation needed; if ever required, rotate by year with the new file's first record chaining to the old file's last hash.
- Backup: covered by the workspace backup repo; the ledger file must be excluded from any tmp/archive cleanup allowlist.

## Record schema (v1)

Envelope (hashed fields):

| Field | Meaning |
|---|---|
| `schema` | `veritas.alert_event_ledger.v1` |
| `seq` | monotonically increasing integer, starts at 1, no gaps |
| `recorded_at_utc` | writer clock at append |
| `prev_record_hash` | `record_hash` of seq−1; genesis uses 64 zeros |
| `record_type` | `alert_event` \| `correction` \| `redaction` \| `ticker_retired` \| `methodology_change` \| `genesis` |
| `payload_sha256` | sha256 of canonical payload bytes |
| `record_hash` | sha256 of canonical envelope bytes excluding `record_hash` and `payload` |
| `payload` | object below (replaced by `{"redacted": true}` only under policy 3) |

`alert_event` payload:

- identity: `ticker`, `event` (see Events), `prior_state`, `new_state`
- market: `price`, `quote_as_of_utc`, `quote_data_date`, `market_session_window`, `quote_freshness_status`
- levels: `reference_low`, `reference_high`, `invalidation`, `level_as_of_utc`, `baseline_pin_sha256`, `band_methodology_version`
- thesis: `thesis_version` (null until T-1 lands; null is recorded, never invented), `confidence` (null until B-1)
- context at emission, recorded even though not yet used by bands: `macro_regime_label` from `tmp/macro-signal-spine.json`, `days_to_earnings` from `tmp/earnings-calendar.json`, source hashes for both
- `horizon`: `review_window_days` default 63
- provenance: `run_id`, `recurring_window`, `scope_fingerprint`, `controller_sha256`, `chain_build_sha256_lf` (controller + chain LF-normalized)
- delivery: `digest_key`, `message_text` (exact text if sent), `delivered` (bool)

Canonical bytes = `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`.

## Events (edge-triggered)

The controller is level-based: a name in band reports `band_entry` every run. The ledger records only transitions, computed against the last `alert_event` for that ticker in the ledger itself (the ledger is its own state; no side file):

- `entered_band`, `exited_band_up`, `exited_band_down`
- `invalidation_breached`, `invalidation_recovered`
- `near_band_entered`
- `freshness_decay_entered`, `freshness_decay_cleared` (data-quality events; scored separately, excluded from accuracy stats)
- `levels_changed` (baseline renewal moved the band while state is unchanged)

First observation per ticker writes a `state_snapshot` event so every later transition has a recorded prior.

## Writer and integration point

- New module `scripts/alert_event_ledger.py`: `append_events(controller, provenance, *, root)` and `verify(path) -> report`. All paths derive from `root` at call time (the 2026-09-16 and 2026-09-23 test-pollution lesson: ROOT is the seam, never an import-time TMP).
- Called from the recurring branch after `_promote_recurring_shared_outputs` returns `ok`, so only promoted, validated controller output is ledgered. Wrapped like the D8 receipts: a ledger failure is reported and alerts the heartbeat but never fails an alerts run that already completed.
- Single writer, file lock around read-head → compute → append → fsync → update head. Idempotency key `(run_id, ticker, event)`; a replayed run appends nothing.
- Weekly Sunday run: context events only; no quote-driven transitions from stale closed-market data unless levels changed.

## Integrity checks

- `verify` walks the file: seq contiguous, each `prev_record_hash` matches, each `record_hash` recomputes, each non-redacted `payload_sha256` recomputes, head file matches last line.
- Daily read-only verification job (added through `cron-automation-manager` only after approval) writes `tmp/alert-event-ledger-verify.json`; any break is P1.
- Optional later (owner-gated, off-machine): publish the daily head hash externally for third-party-checkable timestamps. Not in v1.

## Tests required before wiring

1. Chain verifies; tampering any payload byte, envelope field, or deleting/reordering a line fails `verify`.
2. Redaction keeps the chain valid; payload-hash recomputation is skipped only for `redacted` payloads.
3. Edge-triggering: repeated identical state appends nothing; each transition appends exactly one record.
4. Idempotent replay of the same `run_id`.
5. Containment: a test with redirected ROOT leaves the production ledger byte-identical and mtime-unchanged.
6. Ledger failure does not change the alerts run status.
7. Schema contains no position, sizing, allocation, or execution field (negative assertion).

## Build order

1. Writer + verify + tests, run against retained `tmp/phase3f-policy-runs` history as a dry run (no production file).
2. Owner review of the dry-run output.
3. Wire into the recurring branch; genesis record carries this document's sha256 and the current baseline pin.
4. Daily verification job (separate approval).
5. O-2 scorer reads the ledger: SPY + sector ETF at 5/21/63 trading days, max adverse excursion before invalidation.

## Open questions for Randall

- Genesis date: first live run after approval (recommended) vs. backfilling today's retained runs as `reconstructed` records clearly flagged as non-contemporaneous (recommended: no backfill; contemporaneity is the point).
- Whether `freshness_decay` events belong in this ledger or a separate data-quality ledger (recommended: same ledger, excluded from accuracy stats by event type).

## Owner decisions and build status (2026-09-23 16:45 MST)

Randall approved the design and both recommendations: genesis at the first live run after approval (no backfill), and data-quality events kept in the same ledger but excluded from accuracy stats.

Built (not wired): `scripts/alert_event_ledger.py` (writer + read-only `verify` CLI) and `scripts/test_alert_event_ledger.py` (9 tests: edge-triggering, levels/data-quality events, context without invention, idempotent replay, tamper detection incl. edit/delete/reorder/truncation-via-head, redaction, forbidden position fields, redirected-ROOT containment, unevaluable-cycle carry-forward). Test 6 (ledger failure cannot change run status) belongs to the wiring step.

Dry run over all 240 retained recurring runs (2026-09-15 to 09-23), written only to `tmp/ledger-dryrun-20260923/`: 528 records, chain verifies ok.

Findings that changed the design:
1. **Unevaluable cycles are not transitions.** The first pass recorded NFLX flipping `invalidation_breached` ↔ `relationship_unavailable` every few cycles on 09-18. A `monitor_only` geometry means "no usable quote this cycle", so the last evaluable relationship now carries forward. Invalidation events fell from 19 to 7.
2. **Size estimate corrected.** About 1.8 KB per record and roughly 20–40 accuracy events per session, so the ledger will run about 25–40 MB/year, not the <5 MB first quoted. Still small; permanent retention stands.
3. **Data-quality events dominate volume** (294 of 496 events), mostly the pre-fix session-boundary decay cycles. Expected to fall with the 09-20 boundary fix and the 09-23 closed-market tolerance; measure after one live week before adding any debounce.
4. **Narrow bands create churn** (e.g. NFLX band 75.03–75.79, about 1% wide). This is a band-quality issue for the thesis/context lane, not a ledger issue; the ledger records it faithfully under `mech-v2-lowanchor`.

Next: wiring into the recurring branch after `_promote_recurring_shared_outputs` returns ok, with the failure-isolation test, then genesis on the first live run. Wiring touches `run_alerts_recommendations_chain.py` / `phase3g_dynamic_execution.py`; it needs Randall's go-ahead on the wiring diff.

## Wiring diff for owner review (2026-09-23 ~22:00 MST)

`tmp/ledger-wiring-20260923/ledger-wiring.diff` (sha256 prefix `61745ae8a93c05b2`), not applied. `run_alerts_recommendations_chain.py`: `_record_alert_ledger()` after `shared_promotion` status `ok` (duplicates and failures are not ledgered), result in the proof and return value, never changes run status; promotion coherence now checks the promoted ROOT targets. Writer side (committed in `2e083ea9`): `record_promoted_run()`, genesis payload, thesis versions, methodology `mech-v3-floor-atr20`, receipt `tmp/alert-event-ledger-last-append.json`, kill switch `state/finance/ledger/DISABLED`. Tests: 3 wiring (append under redirected ROOT, failure isolation, kill switch) + 14 ledger. Open gap: nothing yet alerts the heartbeat from the receipt.
