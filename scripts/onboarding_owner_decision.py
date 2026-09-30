#!/usr/bin/env python3
"""Owner-decision records for reference-level onboarding. Stdlib only; no network.

A record documents an approval already given; recording one does not grant approval.
The shared cutover approval is a separate, component-specific production gate.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


_TIER_PATH = Path(__file__).resolve().parent / "tier_owner_decision.py"
_TIER_NAME = "_onboarding_tier_owner_decision_" + hashlib.sha256(
    str(_TIER_PATH).encode("utf-8")
).hexdigest()[:16]
_spec = importlib.util.spec_from_file_location(_TIER_NAME, _TIER_PATH)
assert _spec and _spec.loader
_tier = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _tier
_spec.loader.exec_module(_tier)

DecisionRefusal = _tier.DecisionRefusal
_parse_ts = _tier._parse_ts
_ID_RE = _tier._ID_RE
REQUIRED_TEXT = _tier.REQUIRED_TEXT
MAX_VALIDITY_DAYS = _tier.MAX_VALIDITY_DAYS
cutover_gate = _tier.cutover_gate

ONBOARDING_SCHEMA = "veritas.onboarding_owner_decision.v1"
ONBOARDING_DECISIONS_REL = "state/finance/onboarding-decisions"
COMPONENT = "reference_level_onboarding_writer"
MODES = ("insert", "refresh")
_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def decision_path(root: Path, decision_id: str) -> Path:
    if not isinstance(decision_id, str) or not _ID_RE.fullmatch(decision_id):
        raise DecisionRefusal(f"decision_id_invalid:{decision_id!r}")
    base = (root / ONBOARDING_DECISIONS_REL).resolve()
    path = (base / f"{decision_id}.json").resolve()
    try:
        path.relative_to(base)
    except ValueError:
        raise DecisionRefusal(f"onboarding_decision_id_path_escape:{decision_id}") from None
    return path


def validate_record(record: Any, decision_id: str) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != ONBOARDING_SCHEMA:
        raise DecisionRefusal(f"onboarding_decision_schema_invalid:{decision_id}")
    if record.get("decision_id") != decision_id:
        raise DecisionRefusal(f"onboarding_decision_id_mismatch:{decision_id}")
    if record.get("decision") != "approved":
        raise DecisionRefusal(f"onboarding_decision_not_approved:{decision_id}")
    if not isinstance(record.get("ticker"), str) or not _TICKER_RE.fullmatch(record["ticker"]):
        raise DecisionRefusal(f"onboarding_decision_ticker_invalid:{decision_id}")
    if record.get("mode") not in MODES:
        raise DecisionRefusal(f"onboarding_decision_mode_invalid:{decision_id}")
    if (not isinstance(record.get("band_packet_sha256"), str)
            or not _SHA_RE.fullmatch(record["band_packet_sha256"])):
        raise DecisionRefusal(f"onboarding_decision_packet_sha_invalid:{decision_id}")
    value = record.get("as_of")
    try:
        if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
            raise ValueError("not YYYY-MM-DD")
        if dt.date.fromisoformat(value).isoformat() != value:
            raise ValueError("noncanonical date")
    except ValueError:
        raise DecisionRefusal(f"onboarding_decision_as_of_invalid:{decision_id}") from None
    for key in REQUIRED_TEXT:
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise DecisionRefusal(f"onboarding_decision_missing:{key}:{decision_id}")
    try:
        granted = _parse_ts(record.get("granted_at"), "granted_at")
        expires = _parse_ts(record.get("expires_at"), "expires_at")
    except DecisionRefusal as exc:
        raise DecisionRefusal(
            f"onboarding_decision_validity_window_invalid:{decision_id}:{exc}"
        ) from None
    if not granted < expires <= granted + dt.timedelta(days=MAX_VALIDITY_DAYS):
        raise DecisionRefusal(
            f"onboarding_decision_validity_window_invalid:{decision_id} "
            f"(max {MAX_VALIDITY_DAYS} days)"
        )
    return record


def load_decision(root: Path, decision_id: str) -> tuple[dict[str, Any], str]:
    path = decision_path(root, decision_id)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise DecisionRefusal(f"onboarding_decision_record_missing:{decision_id}") from None
    except OSError as exc:
        raise DecisionRefusal(
            f"onboarding_decision_record_unreadable:{decision_id}:{type(exc).__name__}"
        ) from None
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise DecisionRefusal(f"onboarding_decision_record_unreadable:{decision_id}") from None
    return validate_record(record, decision_id), hashlib.sha256(raw).hexdigest()


def decision_digest(record: dict[str, Any]) -> str:
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def bind(record: dict[str, Any], request: dict[str, Any], now: dt.datetime) -> None:
    did = record["decision_id"]
    for field, approved in (
        ("ticker", record["ticker"]),
        ("mode", record["mode"]),
        ("band_packet_sha256", record["band_packet_sha256"]),
        ("as_of", record["as_of"]),
    ):
        if approved != request.get(field):
            raise DecisionRefusal(f"onboarding_decision_binding_mismatch:{did}:{field}")
    if now < _parse_ts(record["granted_at"], "granted_at"):
        raise DecisionRefusal(f"onboarding_decision_not_yet_valid:{did}")
    if now >= _parse_ts(record["expires_at"], "expires_at"):
        raise DecisionRefusal(f"onboarding_decision_expired:{did} at {record['expires_at']}")


def write_record(root: Path, record: dict[str, Any]) -> Path:
    did = record.get("decision_id")
    path = decision_path(root, did)
    validate_record(record, did)
    if path.exists():
        raise DecisionRefusal(f"onboarding_decision_record_exists:{did} (never overwritten)")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "x", encoding="utf-8") as fh:
            fh.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    except FileExistsError:
        raise DecisionRefusal(f"onboarding_decision_record_exists:{did} (never overwritten)") from None
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Record or check a Phase 4 onboarding owner decision")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record", help="record an approval already given")
    rec.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    for flag in ("decision-id", "ticker", "mode", "band-packet-sha256", "as-of",
                 "channel", "message-ref", "grant-text"):
        rec.add_argument("--" + flag, required=True)
    rec.add_argument("--granted-by", default="Randall")
    rec.add_argument("--recorded-by", default="Main")
    rec.add_argument("--granted-at", default=None, help="timezone-aware ISO-8601; default now UTC")
    rec.add_argument("--valid-days", type=int, default=7)
    chk = sub.add_parser("check", help="validate a record and report the cutover gate")
    chk.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    chk.add_argument("decision_id")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.cmd == "record":
            if not 1 <= args.valid_days <= MAX_VALIDITY_DAYS:
                raise DecisionRefusal("onboarding_decision_validity_window_invalid:valid-days")
            granted = (_parse_ts(args.granted_at, "granted_at") if args.granted_at
                       else dt.datetime.now(dt.timezone.utc))
            record = {
                "schema": ONBOARDING_SCHEMA, "decision_id": args.decision_id,
                "decision": "approved", "ticker": args.ticker.upper(), "mode": args.mode,
                "band_packet_sha256": args.band_packet_sha256.lower(), "as_of": args.as_of,
                "granted_by": args.granted_by, "channel": args.channel,
                "message_ref": args.message_ref, "grant_text": args.grant_text,
                "granted_at": granted.isoformat(),
                "expires_at": (granted + dt.timedelta(days=args.valid_days)).isoformat(),
                "recorded_by": args.recorded_by,
                "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            path = write_record(root, record)
            print(json.dumps({"status": "recorded", "path": path.as_posix()}))
        else:
            record, sha = load_decision(root, args.decision_id)
            try:
                gate = {"status": "active",
                        "granted_at": cutover_gate(root, COMPONENT)["granted_at"]}
            except DecisionRefusal as exc:
                gate = {"status": "blocked", "reason": str(exc)}
            print(json.dumps({"status": "valid", "record_sha256": sha,
                              "decision_digest": decision_digest(record),
                              "cutover_gate": gate, "ticker": record["ticker"],
                              "mode": record["mode"], "expires_at": record["expires_at"]},
                             indent=2))
    except DecisionRefusal as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
