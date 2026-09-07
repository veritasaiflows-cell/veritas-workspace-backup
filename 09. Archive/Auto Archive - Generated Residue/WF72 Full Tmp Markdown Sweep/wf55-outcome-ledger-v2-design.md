# WF55 Outcome Ledger v2 Design

- Generated UTC: `2026-05-24T23:24:00Z`
- Status: **design-ready / review-only**
- Current WF55 state: **NOT_READY**
- Durable writes performed by this pass: **none**

## Bottom line

WF55 needs a real append-only outcome ledger before any future analytics lane can be considered. The v2 design keeps known-at-time snapshots immutable, records later owner decisions and outcomes as separate evidence rows, and bridges Call Log, WF67 paper-only lifecycle evidence, and WF68 alert follow-up without creating portfolio, approval, paper, live, or account authority.

## Current evidence state

- `tmp/probability-readiness-report.json`: `NOT_READY`
- `data/state-history/state-history-v1.jsonl`: 18 rows, 13.08-day span
- `data/state-history/outcome-updates-v1.jsonl`: 5 realized outcome rows, 0 owner-decision rows
- `04. Research/Call Log.md`: 12 legacy calls reconciled; NVDA #3, BRK.B #8, and VRT #10 remain incomplete/open
- WF68 bridge: proposal-only; no appendable event yet because later owner action/no-action or follow-up evidence is absent

## Proposed ledger files

| Surface | Role |
|---|---|
| `data/state-history/state-history-v1.jsonl` | Existing known-at-time snapshot log; unchanged |
| `data/state-history/outcome-updates-v1.jsonl` | Existing v1 sidecar; unchanged in next slice |
| `data/state-history/outcome-ledger-v2.jsonl` | Future append-only v2 ledger, not written in next slice |
| `tmp/wf55-outcome-ledger-v2-migration-preview.json` | Next-slice preview artifact |
| `tmp/wf55-outcome-ledger-v2-validation.json` | Next-slice validation report |

## Append-only v2 schema

Each row should be `row_type=outcome_ledger_event_v2` with:

- identity: `ledger_event_id`, `event_family`, `event_subtype`, `linked_capture_run_id`, `linked_snapshot_captured_at_utc`
- timing: `observed_at_utc`, `recorded_at_utc`; both must be after the linked snapshot
- target: `ticker`, `object_id`, `question_id`
- payload: family-specific evidence fields
- authority: all hard-false, including no portfolio/canon/deployment/watchlist/paper/live/account/trade authority
- provenance: source artifact path, hash, generated timestamp, status, and validation artifacts

Duplicate natural keys are blocked unless the new row explicitly supersedes a prior ledger event. Prior rows are never edited.

## Event families

| Family | Purpose | Key rule |
|---|---|---|
| `owner_decision` | Explicit owner reviewed/approved/deferred/rejected/no-action evidence | Never infer approval from validators, rankings, or packet quality |
| `call_log_resolution` | Call Log close/void/supersession evidence | Original call text must remain preserved before append |
| `paper_lifecycle` | WF67 paper-only observations | Redacted paper evidence only; no live endpoint/account data |
| `band_stop_outcome` | Later band/stop/reclaim observations | Must link to a prior snapshot and source artifact |
| `post_event_drift` | Earnings/alert/thesis follow-up | Evidence summary required; no predictive claim |

## Owner-decision capture route

Recommendation: **both Call Log and structured sidecar**.

1. Detect explicit owner-decision evidence from reviewed workspace artifacts or owner instruction already present in the workspace.
2. Generate a proposal artifact with decision text, scope, object ID, linked capture run, and source hash.
3. If a Call Log row changes, patch only `Status`, `Outcome`, `Date Closed`, and `Notes`; preserve original call text.
4. Append an `owner_decision` v2 event only after validation proves timestamps, linked snapshot, authority false fields, and provenance.
5. Keep WF55 `NOT_READY` until formal readiness gates clear later.

## Call Log bridge

- Existing human-readable surface: `04. Research/Call Log.md`
- Current open rows to monitor: `NVDA #3`, `BRK.B #8`, `VRT #10`
- Append v2 `call_log_resolution` rows only for closed, voided, or superseded rows with evidence.
- `Voided` and `Superseded` rows must be non-scoreable.
- Incomplete rows stay open until later evidence exists.

## Paper outcome bridge

Scope is WF67 paper-only evidence. This design authorizes **no paper order**, **no live order**, and **no account action**.

Rules:

- accept only redacted WF67 reconciliation artifacts with paper endpoint proof and source hash
- map lifecycle evidence to explicit `paper_*` event subtypes, not thesis labels
- require paper/live isolation validation before proposal generation
- append later closed/filled/cancelled/expired/rejected/observed states only when evidence exists
- never treat paper evidence as portfolio, approval, or live execution authority

## Validation gates

Minimum implementation proof:

```text
python -m py_compile scripts\state_history_capture.py scripts\state_history_outcome_update.py scripts\probability_readiness_validator.py
python scripts\test_state_history_capture.py
python scripts\test_state_history_outcome_update.py
python scripts\state_history_capture.py validate
python scripts\state_history_outcome_update.py validate
python scripts\probability_readiness_validator.py --write
```

New v2 validator must fail closed on:

- bad JSONL
- missing linked snapshot
- timestamps not after linked snapshot
- missing source hash
- authority field set true
- duplicate natural key without supersession
- live endpoint or credentials in paper rows
- Call Log append without original-call preservation proof
- forbidden predictive/performance wording outside WF55 readiness tooling names

## Migration/backfill strategy

1. Build a preview from existing v1 sidecar rows and reconciled Call Log evidence.
2. Validate preview only; do not write durable v2 JSONL in the next slice.
3. Mark WF68 bridge as `no_append_yet` metadata, not a row.
4. Main session reviews preview.
5. If later approved, write v2 backfill once with a manifest hash while preserving v1 unchanged.

Non-backfillable now:

- WF68 alert bridge: no later owner action/no-action or follow-up evidence yet.
- Open Call Log rows: NVDA #3, BRK.B #8, VRT #10.

## Exact next implementation slice

**Slice:** `WF55 v2 preview builder and validator, no durable v2 append`

Change only:

- `scripts/wf55_outcome_ledger_v2.py`
- `scripts/test_wf55_outcome_ledger_v2.py`

Script may write only:

- `tmp/wf55-outcome-ledger-v2-migration-preview.json`
- `tmp/wf55-outcome-ledger-v2-validation.json`

Do **not** mutate:

- `data/state-history/outcome-ledger-v2.jsonl`
- `data/state-history/outcome-updates-v1.jsonl`
- `data/state-history/state-history-v1.jsonl`
- `04. Research/Call Log.md`
- portfolio/canon notes
- brokerage, paper, live, or account surfaces

## Acceptance criteria

- Compile and unit tests pass.
- Tests cover valid v1 paper conversion, valid Call Log conversion, duplicate block, supersession allowed, timestamp block, authority true block, live-endpoint block, and blocked wording block.
- Preview contains existing appendable v1 rows plus separate blocked candidates.
- Validation report has 0 critical findings.
- WF55 remains `NOT_READY` / review-only.
- No durable JSONL, Call Log, portfolio, canon, paper, live, or account mutation occurs.
