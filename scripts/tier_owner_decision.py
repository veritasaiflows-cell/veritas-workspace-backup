#!/usr/bin/env python3
"""Owner-decision records and the cutover gate for Phase 4 tier writes.

Two separate proofs, both required before scripts/tier_membership_writer.py may
mutate a non-fixture canon (Tier Entitlement contract, "Authority separation":
the authorization check and the membership write are separate proof steps):

1. Cutover gate - state/finance/standing-approvals/phase4-tier-cutover.json with
   id "phase4-tier-cutover", active=true and "tier_membership_writer" in
   covers. It does not exist until Randall approves the cutover. Without it
   every production apply and rollback refuses.

2. Owner decision - one record per ticker per tier change under
   state/finance/tier-decisions/<decision_id>.json, written by Main when Randall
   approves that specific change (channel + message reference + his words). It
   binds ticker, from/to tier, decision-card id and the exact proposal-packet
   sha256, carries an expiry, and is consumed once by the transaction journal.

Records are evidence of an approval Randall gave; creating one never implies it.
`record` refuses to overwrite, and a record is only valid for the exact card and
packet it names.

stdlib only. No network.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

DECISION_SCHEMA = "veritas.tier_owner_decision.v1"
DECISIONS_REL = "state/finance/tier-decisions"
CUTOVER_REL = "state/finance/standing-approvals/phase4-tier-cutover.json"
CUTOVER_ID = "phase4-tier-cutover"
MAX_VALIDITY_DAYS = 14
ALLOWED_TRANSITIONS = {("A", "B"), ("B", "A"), ("B", "C"), ("C", "B")}
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{5,95}$")
REQUIRED_TEXT = ("granted_by", "channel", "message_ref", "grant_text", "recorded_by")


class DecisionRefusal(Exception):
    """The decision or gate does not authorize the requested write."""


def _parse_ts(value: Any, label: str) -> _dt.datetime:
    try:
        moment = _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise DecisionRefusal(f"{label}_invalid:{value}") from None
    if moment.tzinfo is None:
        raise DecisionRefusal(f"{label}_needs_timezone:{value}")
    return moment


def cutover_gate(root: Path, component: str = "tier_membership_writer") -> dict[str, Any]:
    """Return the active cutover approval or raise. Absent file = not approved."""
    path = root / CUTOVER_REL
    if not path.is_file():
        raise DecisionRefusal("cutover_not_approved: no " + CUTOVER_REL)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DecisionRefusal(f"cutover_record_unreadable:{type(exc).__name__}") from None
    if not isinstance(record, dict) or record.get("id") != CUTOVER_ID:
        raise DecisionRefusal("cutover_record_wrong_id")
    if record.get("active") is not True:
        raise DecisionRefusal("cutover_not_active")
    covers = record.get("covers")
    if not isinstance(covers, list) or component not in covers:
        raise DecisionRefusal(f"cutover_does_not_cover:{component}")
    for key in ("granted_by", "granted_at", "grant_text"):
        if not str(record.get(key) or "").strip():
            raise DecisionRefusal(f"cutover_record_missing:{key}")
    return record


def decision_path(root: Path, decision_id: str) -> Path:
    if not isinstance(decision_id, str) or not _ID_RE.match(decision_id):
        raise DecisionRefusal(f"decision_id_invalid:{decision_id!r}")
    base = (root / DECISIONS_REL).resolve()
    path = (base / f"{decision_id}.json").resolve()
    path.relative_to(base)
    return path


def validate_record(record: Any, decision_id: str) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("schema") != DECISION_SCHEMA:
        raise DecisionRefusal(f"decision_schema_invalid:{decision_id}")
    if record.get("decision_id") != decision_id:
        raise DecisionRefusal(f"decision_id_mismatch:{decision_id}")
    if record.get("decision") != "approved":
        raise DecisionRefusal(f"decision_not_approved:{decision_id}")
    ticker = str(record.get("ticker") or "").upper()
    frm = str(record.get("from_tier") or "").upper()
    to = str(record.get("to_tier") or "").upper()
    if not ticker or (frm, to) not in ALLOWED_TRANSITIONS:
        raise DecisionRefusal(f"decision_transition_invalid:{decision_id} {ticker} {frm}->{to}")
    sha = str(record.get("proposal_packet_sha256") or "").lower()
    if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise DecisionRefusal(f"decision_packet_sha_invalid:{decision_id}")
    if not str(record.get("card_id") or "").strip():
        raise DecisionRefusal(f"decision_card_id_missing:{decision_id}")
    for key in REQUIRED_TEXT:
        if not str(record.get(key) or "").strip():
            raise DecisionRefusal(f"decision_missing:{key}:{decision_id}")
    granted = _parse_ts(record.get("granted_at"), "granted_at")
    expires = _parse_ts(record.get("expires_at"), "expires_at")
    if not granted < expires <= granted + _dt.timedelta(days=MAX_VALIDITY_DAYS):
        raise DecisionRefusal(f"decision_validity_window_invalid:{decision_id} (max {MAX_VALIDITY_DAYS} days)")
    return record


def load_decision(root: Path, decision_id: str) -> tuple[dict[str, Any], str]:
    """Return (record, sha256 of the record file) or raise."""
    path = decision_path(root, decision_id)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise DecisionRefusal(f"decision_record_missing:{decision_id}") from None
    try:
        record = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise DecisionRefusal(f"decision_record_unreadable:{decision_id}") from None
    return validate_record(record, decision_id), hashlib.sha256(raw).hexdigest()


def bind(record: dict[str, Any], entry: dict[str, Any], now: _dt.datetime) -> None:
    """Require the writer's decision entry to be exactly what the owner approved."""
    did = record["decision_id"]
    pairs = (
        ("ticker", str(record["ticker"]).upper(), entry.get("ticker")),
        ("from_tier", str(record["from_tier"]).upper(), entry.get("from_tier")),
        ("to_tier", str(record["to_tier"]).upper(), entry.get("to_tier")),
        ("card_id", str(record["card_id"]), entry.get("card_id")),
        ("proposal_packet_sha256", str(record["proposal_packet_sha256"]).lower(), entry.get("proposal_packet_sha256")),
    )
    for field, approved, requested in pairs:
        if approved != requested:
            raise DecisionRefusal(f"decision_binding_mismatch:{did}:{field}")
    if now < _parse_ts(record["granted_at"], "granted_at"):
        raise DecisionRefusal(f"decision_not_yet_valid:{did}")
    if now >= _parse_ts(record["expires_at"], "expires_at"):
        raise DecisionRefusal(f"decision_expired:{did} at {record['expires_at']}")


def write_record(root: Path, record: dict[str, Any]) -> Path:
    did = record.get("decision_id")
    path = decision_path(root, str(did))
    validate_record(record, str(did))
    if path.exists():
        raise DecisionRefusal(f"decision_record_exists:{did} (records are never overwritten)")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Record or check a Phase 4 tier owner decision")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record", help="write one decision record for an approval Randall gave")
    rec.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    for flag in ("decision-id", "ticker", "from-tier", "to-tier", "card-id", "proposal-packet-sha256",
                 "channel", "message-ref", "grant-text", "granted-at"):
        rec.add_argument("--" + flag, required=True)
    rec.add_argument("--granted-by", default="Randall")
    rec.add_argument("--valid-days", type=int, default=7)
    chk = sub.add_parser("check", help="validate a record and report the cutover gate")
    chk.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    chk.add_argument("--decision-id", required=True)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.cmd == "record":
            granted = _parse_ts(args.granted_at, "granted_at")
            record = {
                "schema": DECISION_SCHEMA,
                "decision_id": args.decision_id,
                "decision": "approved",
                "ticker": args.ticker.upper(),
                "from_tier": args.from_tier.upper(),
                "to_tier": args.to_tier.upper(),
                "card_id": args.card_id,
                "proposal_packet_sha256": args.proposal_packet_sha256.lower(),
                "granted_by": args.granted_by,
                "channel": args.channel,
                "message_ref": args.message_ref,
                "grant_text": args.grant_text,
                "granted_at": granted.isoformat(),
                "expires_at": (granted + _dt.timedelta(days=args.valid_days)).isoformat(),
                "recorded_by": "Main",
                "recorded_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            }
            path = write_record(root, record)
            print(json.dumps({"status": "recorded", "path": path.as_posix()}))
        else:
            record, sha = load_decision(root, args.decision_id)
            try:
                gate = {"status": "active", "granted_at": cutover_gate(root)["granted_at"]}
            except DecisionRefusal as exc:
                gate = {"status": "blocked", "reason": str(exc)}
            print(json.dumps({"status": "valid", "record_sha256": sha, "cutover_gate": gate,
                              "ticker": record["ticker"], "transition": f"{record['from_tier']}->{record['to_tier']}",
                              "expires_at": record["expires_at"]}, indent=2))
    except DecisionRefusal as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
