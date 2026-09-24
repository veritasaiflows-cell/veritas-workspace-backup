"""Append-only, hash-chained alert event ledger (design: 06. Playbooks/Project
Continuity/Alert Event Ledger Design - 2026-09-23.md).

Records alert *transitions* emitted by the recurring alerts chain so a later
scorer can grade them. It records calls, never positions: no sizing,
allocation, holding, or execution field may be added.

Every path is derived from an explicit ``root`` at call time. ROOT is the
test redirect seam; an import-time path let tests overwrite production
artifacts twice (2026-09-16, 2026-09-23).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCHEMA = "veritas.alert_event_ledger.v1"
LEDGER_REL = "state/finance/ledger/alert-events-v1.jsonl"
HEAD_REL = "state/finance/ledger/alert-events-v1.head.json"
LOCK_REL = "state/finance/ledger/alert-events-v1.lock"
MACRO_REL = "tmp/macro-signal-spine.json"
EARNINGS_REL = "tmp/earnings-calendar.json"
THESIS_REL = "state/finance/thesis"
DISABLED_REL = "state/finance/ledger/DISABLED"
RECEIPT_REL = "tmp/alert-event-ledger-last-append.json"
DESIGN_REL = "06. Playbooks/Project Continuity/Alert Event Ledger Design - 2026-09-23.md"
FUNNEL_VERSION = "funnel-v1"
GENESIS_PREV = "0" * 64
# Mirrors yahoo_reference_level_matrix.BAND_METHODOLOGY_VERSION (a test keeps
# them equal). Renewal applied 2026-09-23 18:13 MST used mech-v3-floor-atr20.
BAND_METHODOLOGY_VERSION = "mech-v3-floor-atr20"
DEFAULT_HORIZON_DAYS = 63

RECORD_TYPES = {
    "genesis", "alert_event", "correction", "redaction", "ticker_retired", "methodology_change",
}
# Price-vs-band geometry drives accuracy events. It is independent of the
# session window, so a name sitting in its band does not "change state" just
# because the market closed and alert_state became monitor_only.
RELATIONSHIP_EVENTS = {
    "band_entry": "entered_band",
    "no_chase": "above_band",
    "near_band": "near_band_entered",
    "invalidation_alert": "invalidation_breached",
    "monitor_only": "relationship_unavailable",
}
DATA_QUALITY_EVENTS = {True: "freshness_decay_entered", False: "freshness_decay_cleared"}
# Fields that must never appear anywhere in a payload.
FORBIDDEN_FIELDS = {
    "position", "positions", "quantity", "shares", "size", "sizing", "allocation", "weight",
    "holding", "holdings", "order", "orders", "cash", "tranche", "execution", "account",
}


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def envelope_hash(record: dict[str, Any]) -> str:
    body = {k: v for k, v in record.items() if k not in ("record_hash", "payload")}
    return sha256_hex(canonical_bytes(body))


def _forbidden_keys(obj: Any) -> list[str]:
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in FORBIDDEN_FIELDS:
                found.append(str(key))
            found.extend(_forbidden_keys(value))
    elif isinstance(obj, list):
        for value in obj:
            found.extend(_forbidden_keys(value))
    return found


def build_record(*, seq: int, prev_hash: str, record_type: str, payload: dict[str, Any],
                 recorded_at_utc: str | None = None) -> dict[str, Any]:
    if record_type not in RECORD_TYPES:
        raise ValueError(f"unknown record_type {record_type!r}")
    bad = _forbidden_keys(payload)
    if bad:
        raise ValueError(f"payload carries forbidden position/execution fields: {sorted(set(bad))}")
    record = {
        "schema": SCHEMA,
        "seq": seq,
        "recorded_at_utc": recorded_at_utc or utc_now(),
        "prev_record_hash": prev_hash,
        "record_type": record_type,
        "payload_sha256": sha256_hex(canonical_bytes(payload)),
        "payload": payload,
    }
    record["record_hash"] = envelope_hash(record)
    return record


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def verify(path: Path, head_path: Path | None = None) -> dict[str, Any]:
    """Walk the chain; any edit, deletion, insertion, or reorder is an error."""
    errors: list[str] = []
    try:
        records = read_records(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "error", "records": 0, "errors": [f"unreadable: {exc}"]}
    prev = GENESIS_PREV
    for index, record in enumerate(records, start=1):
        where = f"line {index}"
        if record.get("schema") != SCHEMA:
            errors.append(f"{where}: schema mismatch")
        if record.get("seq") != index:
            errors.append(f"{where}: seq {record.get('seq')} != {index}")
        if record.get("prev_record_hash") != prev:
            errors.append(f"{where}: prev_record_hash does not match line {index - 1}")
        if record.get("record_hash") != envelope_hash(record):
            errors.append(f"{where}: record_hash does not recompute")
        payload = record.get("payload")
        if payload != {"redacted": True}:
            if record.get("payload_sha256") != sha256_hex(canonical_bytes(payload)):
                errors.append(f"{where}: payload_sha256 does not recompute")
        prev = record.get("record_hash") or ""
    if head_path is not None and head_path.is_file() and records:
        head = json.loads(head_path.read_text(encoding="utf-8"))
        if head.get("seq") != len(records) or head.get("record_hash") != records[-1].get("record_hash"):
            errors.append("head file does not match last record")
    return {"status": "ok" if not errors else "error", "records": len(records),
            "head_record_hash": records[-1]["record_hash"] if records else None, "errors": errors}


@contextmanager
def _file_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            handle.close()


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        raw = path.read_bytes()
        return json.loads(raw.decode("utf-8")), sha256_hex(raw)
    except (OSError, ValueError):
        return None, None


def context_snapshot(root: Path, ticker_dates: dict[str, str] | None = None) -> dict[str, Any]:
    """Macro posture and earnings timing at emission. Missing inputs are
    recorded as null with the reason, never invented."""
    macro, macro_sha = _load_json(root / MACRO_REL)
    earnings, earnings_sha = _load_json(root / EARNINGS_REL)
    posture = (macro or {}).get("summary", {}).get("macro_posture") if macro else None
    next_dates: dict[str, str] = {}
    if earnings and isinstance(earnings.get("records"), list):
        for row in earnings["records"]:
            if isinstance(row, dict) and row.get("ticker") and row.get("next_earnings_date"):
                next_dates[str(row["ticker"])] = str(row["next_earnings_date"])
    theses: dict[str, str] = {}
    thesis_dir = root / THESIS_REL
    if thesis_dir.is_dir():
        for path in sorted(thesis_dir.glob("*.json")):
            record, _ = _load_json(path)
            if record and record.get("status") == "accepted" and record.get("ticker"):
                theses[str(record["ticker"])] = str(record.get("thesis_version") or "unversioned")
    return {
        "thesis_versions": theses,
        "macro_posture": posture,
        "macro_source_sha256": macro_sha,
        "macro_as_of_date": (macro or {}).get("as_of_date"),
        "earnings_source_sha256": earnings_sha,
        "next_earnings_dates": next_dates,
    }


def _days_until(target: str | None, today: str | None) -> int | None:
    try:
        return (date.fromisoformat(str(target)) - date.fromisoformat(str(today)[:10])).days
    except (TypeError, ValueError):
        return None


def last_states(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for record in records:
        payload = record.get("payload") or {}
        if record.get("record_type") == "alert_event" and payload.get("ticker"):
            state[payload["ticker"]] = {
                "relationship": payload.get("new_relationship"),
                "decay": payload.get("freshness_decay"),
                "levels": payload.get("levels_key"),
            }
    return state


def _levels_key(row: dict[str, Any]) -> list[Any]:
    return [row.get("reference_low"), row.get("reference_high"), row.get("invalidation_threshold")]


def derive_events(controller: dict[str, Any], prior: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any], str]]:
    """Return (ticker, row, event) transitions for one controller run."""
    events: list[tuple[str, dict[str, Any], str]] = []
    for row in controller.get("rows") or []:
        ticker = row.get("ticker")
        if not ticker:
            continue
        relationship = row.get("level_relationship_state")
        decay = row.get("alert_state") == "freshness_decay"
        before = prior.get(ticker)
        if before is None:
            events.append((ticker, row, "state_snapshot"))
            continue
        # monitor_only geometry means "not evaluable this cycle" (stale or
        # missing quote), not a price move. Treating it as a state produced
        # invalidation_breached / unavailable flip-flops every few cycles in
        # the 2026-09-23 dry run, so it never counts as a transition and the
        # last evaluable relationship carries forward.
        if relationship == "monitor_only":
            relationship = before.get("relationship")
            row = {**row, "level_relationship_state": relationship}
        if relationship != before.get("relationship"):
            name = RELATIONSHIP_EVENTS.get(str(relationship), "relationship_changed")
            if before.get("relationship") == "invalidation_alert" and relationship != "invalidation_alert":
                name = "invalidation_recovered" if relationship in ("band_entry", "near_band", "no_chase") else name
            events.append((ticker, row, name))
        elif _levels_key(row) != before.get("levels"):
            events.append((ticker, row, "levels_changed"))
        if decay != bool(before.get("decay")):
            events.append((ticker, row, DATA_QUALITY_EVENTS[decay]))
    return events


def event_payload(ticker: str, row: dict[str, Any], event: str, prior: dict[str, Any] | None,
                  provenance: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    quote_date = row.get("quote_data_date")
    next_earnings = context["next_earnings_dates"].get(ticker)
    return {
        "ticker": ticker,
        "event": event,
        "event_class": "data_quality" if event.startswith("freshness_decay") else "accuracy",
        "prior_relationship": (prior or {}).get("relationship"),
        "new_relationship": row.get("level_relationship_state"),
        "alert_state": row.get("alert_state"),
        "freshness_decay": row.get("alert_state") == "freshness_decay",
        "alert_fire_eligible": row.get("alert_fire_eligible"),
        "price": row.get("latest_price"),
        "quote_as_of_utc": row.get("quote_as_of_utc"),
        "quote_data_date": quote_date,
        "market_session_window": row.get("market_session_window"),
        "quote_freshness_status": row.get("quote_freshness_status"),
        "reference_low": row.get("reference_low"),
        "reference_high": row.get("reference_high"),
        "invalidation": row.get("invalidation_threshold"),
        "levels_key": _levels_key(row),
        "level_as_of_utc": row.get("level_as_of_utc"),
        "baseline_source_path": row.get("source_path"),
        "band_methodology_version": provenance.get("band_methodology_version", BAND_METHODOLOGY_VERSION),
        "thesis_version": context.get("thesis_versions", {}).get(ticker),
        "confidence": (row.get("sql_reference") or {}).get("reference_confidence"),
        "macro_posture": context["macro_posture"],
        "macro_source_sha256": context["macro_source_sha256"],
        "next_earnings_date": next_earnings,
        "days_to_earnings": _days_until(next_earnings, quote_date),
        "earnings_source_sha256": context["earnings_source_sha256"],
        "review_window_days": DEFAULT_HORIZON_DAYS,
        "run_id": provenance.get("run_id"),
        "recurring_window": provenance.get("recurring_window"),
        "scope_fingerprint": provenance.get("scope_fingerprint"),
        "controller_sha256": provenance.get("controller_sha256"),
        "digest_key": provenance.get("digest_key"),
        "message_text": provenance.get("message_text"),
        "delivered": bool(provenance.get("delivered", False)),
        "reconstructed": bool(provenance.get("reconstructed", False)),
    }


def append_events(controller: dict[str, Any], provenance: dict[str, Any], *, root: Path,
                  ledger_rel: str = LEDGER_REL, head_rel: str = HEAD_REL,
                  genesis_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Append transitions for one promoted controller run. Idempotent per run_id."""
    ledger = root / ledger_rel
    head = root / head_rel
    run_id = provenance.get("run_id")
    if not run_id:
        raise ValueError("provenance.run_id is required")
    with _file_lock(root / LOCK_REL):
        records = read_records(ledger)
        if any((r.get("payload") or {}).get("run_id") == run_id for r in records):
            return {"status": "ok_duplicate_run", "appended": 0, "run_id": run_id}
        new: list[dict[str, Any]] = []
        prev = records[-1]["record_hash"] if records else GENESIS_PREV
        seq = len(records)
        if not records:
            seq += 1
            genesis = build_record(seq=seq, prev_hash=prev, record_type="genesis",
                                   payload=genesis_payload or {"note": "ledger genesis"})
            new.append(genesis)
            prev = genesis["record_hash"]
        prior = last_states(records)
        context = context_snapshot(root)
        for ticker, row, event in derive_events(controller, prior):
            seq += 1
            payload = event_payload(ticker, row, event, prior.get(ticker), provenance, context)
            record = build_record(seq=seq, prev_hash=prev, record_type="alert_event", payload=payload)
            new.append(record)
            prev = record["record_hash"]
        if new:
            ledger.parent.mkdir(parents=True, exist_ok=True)
            with open(ledger, "ab") as stream:
                for record in new:
                    stream.write(canonical_bytes(record) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            head_tmp = head.with_suffix(".json.tmp")
            head_tmp.write_text(json.dumps({"seq": seq, "record_hash": prev, "updated_at_utc": utc_now()},
                                           indent=2) + "\n", encoding="utf-8")
            os.replace(head_tmp, head)
        return {"status": "ok", "appended": len(new), "run_id": run_id, "head_seq": seq}


def genesis_payload(root: Path, controller: dict[str, Any]) -> dict[str, Any]:
    """What the ledger opened on: design record, baseline pin, methodology,
    thesis schema, and funnel version. Missing inputs are null, never invented."""
    design = root / DESIGN_REL
    pins = sorted({str(r.get("source_path")) for r in controller.get("rows") or [] if r.get("source_path")})
    pin_json, pin_sha = _load_json(root / pins[0]) if len(pins) == 1 else (None, None)
    return {
        "note": "ledger genesis at first live promoted run; no backfill (owner-approved 2026-09-23)",
        "design_record": DESIGN_REL,
        "design_record_sha256": sha256_hex(design.read_bytes()) if design.is_file() else None,
        "baseline_pins": pins,
        "baseline_pin_sha256": pin_sha,
        "baseline_matrix_sha256": (pin_json or {}).get("matrix_sha256"),
        "band_methodology_version": BAND_METHODOLOGY_VERSION,
        "thesis_schema": "veritas.thesis_record.v1",
        "funnel_version": FUNNEL_VERSION,
        "ledger_schema": SCHEMA,
    }


def record_promoted_run(root: Path, controller: dict[str, Any], *, run_id: str, window: str,
                        scope_fingerprint: str | None, controller_sha256: str | None,
                        message: str | None, digest_key: str | None = None) -> dict[str, Any]:
    """Single entry point for the recurring chain after a verified shared
    promotion. Never raises: a ledger failure is returned and written to the
    receipt for the heartbeat, and must not change the alerts run status.
    ``state/finance/ledger/DISABLED`` switches appends off without a code change."""
    try:
        if (root / DISABLED_REL).exists():
            result: dict[str, Any] = {"status": "disabled", "appended": 0, "run_id": run_id}
        else:
            provenance = {
                "run_id": run_id, "recurring_window": window, "scope_fingerprint": scope_fingerprint,
                "controller_sha256": controller_sha256, "digest_key": digest_key, "message_text": message,
                "delivered": False, "band_methodology_version": BAND_METHODOLOGY_VERSION,
            }
            result = append_events(controller, provenance, root=root,
                                   genesis_payload=genesis_payload(root, controller))
            check = verify(root / LEDGER_REL, root / HEAD_REL)
            result["verify"] = {k: check[k] for k in ("status", "records", "head_record_hash")}
            if check["status"] != "ok":
                result["status"] = "error"
                result["errors"] = check["errors"][:5]
    except Exception as exc:  # noqa: BLE001 - isolation is the contract
        result = {"status": "error", "appended": 0, "run_id": run_id, "errors": [f"{type(exc).__name__}: {exc}"]}
    result["recorded_at_utc"] = utc_now()
    try:
        receipt = root / RECEIPT_REL
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        result["receipt_error"] = f"{type(exc).__name__}: {exc}"
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify the alert event ledger (read-only).")
    ap.add_argument("--root", default=".", help="workspace root")
    ap.add_argument("--ledger", default=LEDGER_REL)
    ap.add_argument("--head", default=HEAD_REL)
    args = ap.parse_args(argv)
    root = Path(args.root)
    report = verify(root / args.ledger, root / args.head)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
