"""Phase 4 inert tier transaction prototype (in-memory simulation only).

Pure state-machine simulation: propose, commit, expire, rollback, recover.
Machines are plain snapshot dicts. Every call deep-copies its inputs and
returns independent copies, so mutating a returned machine, proposal, or
result cannot affect any other snapshot. Nothing is opened or written,
no network is used, and this never presents itself as live guarded-SQL
infrastructure.

Trust limit, stated plainly: this in-process library cannot authenticate
callers, and machine plus journal contents are caller-held, not
tamper-evident. Approval dicts are caller-asserted labels; commit only
checks their shape, binding (lease id, token, readiness hash), approver
kind, and time placement against the journal-bound proposal. The journal
proposal hash is recomputed from content wherever the data is available
and detects accidental drift, not deliberate forgery. Likewise the
proposal readiness hash is format-checked and bound into approvals, but
a proposal is never tied to a live readiness evaluation here. Real
authentication and evidence gating belong to the Main/owner review gate,
not this module.

Vocabulary note: tier/slot/lease/proposal language only.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

VALID_TIERS: tuple[str, ...] = ("A", "B", "C")
APPROVAL_METHOD: str = "human_review_commit"
PROPOSAL_KINDS: tuple[str, ...] = ("proposed", "committed", "rolled_back", "expired")
MACHINE_APPROVERS: frozenset[str] = frozenset({
    "auto_bot", "autobot", "auto", "bot", "system", "machine",
    "scheduler", "cron", "os_monitor", "veritas_os_freshness_monitor",
    "monitor", "freshness_monitor", "os_freshness_monitor",
})
_SYSTEM_REJECT_STEMS: tuple[str, ...] = (
    "cron", "schedul", "monitor", "bot", "auto", "system",
    "machin", "freshness",
)
_READINESS_HASH_RE: Any = re.compile(r"[0-9a-f]{64}")


def _parse_utc(value: Any) -> Optional[datetime]:
    """Parse strict UTC timestamp; naive values are malformed (None)."""
    if not isinstance(value, str) or not value.strip():
        return None
    text: str = value.strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed: datetime = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _normalize_name(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    return "_".join(value.strip().lower().replace("-", "_").split())


def _approver_rejected(value: Any) -> bool:
    """Reject machine-like approvers under common Unicode/text variants."""
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        text: str = unicodedata.normalize("NFKC", value).casefold()
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
        tokens: list[str] = [token for token in "".join(
            ch if ch.isalnum() else " " for ch in text).split() if token]
        if not tokens:
            return False
        if "_".join(tokens) in MACHINE_APPROVERS:
            return True
        joined: str = "".join(tokens)
        return any(stem in joined for stem in _SYSTEM_REJECT_STEMS)
    except Exception:
        return False


def _proposal_hash(proposal: Mapping[str, Any]) -> str:
    try:
        raw: bytes = json.dumps(
            dict(proposal), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, default=str,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return ""
    return hashlib.sha256(raw).hexdigest()


def _copy_machine(machine: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(dict(machine))


def new_machine(slots: Any, *, universe_id: str = "",
                snapshot_id: str = "") -> dict[str, Any]:
    """Build a fresh in-memory machine snapshot from slot rows.

    Duplicate and case-variant ticker rows are never silently dropped:
    the first valid row wins and every skipped row is explicitly reported
    in the machine's row_issues list with reason duplicate_ticker_row,
    case_variant_duplicate_ticker_row, or invalid_ticker_row.
    """
    normalized: dict[str, dict[str, Any]] = {}
    seen_folded: dict[str, str] = {}
    row_issues: list[dict[str, Any]] = []
    try:
        rows: Any = list(slots) if isinstance(slots, (list, tuple)) else []
    except (TypeError, ValueError):
        rows = []
    for row in rows:
        if not isinstance(row, Mapping):
            row_issues.append({"ticker": "", "reason": "invalid_ticker_row"})
            continue
        ticker: Any = row.get("ticker")
        tier: Any = row.get("tier")
        version: Any = row.get("version")
        if not isinstance(ticker, str) or not ticker.strip():
            row_issues.append({"ticker": ticker, "reason": "invalid_ticker_row"})
            continue
        clean: str = ticker.strip()
        if not (
            tier in VALID_TIERS
            and isinstance(version, int) and not isinstance(version, bool)
            and version >= 0
        ):
            row_issues.append({"ticker": clean, "reason": "invalid_ticker_row"})
            continue
        folded: str = clean.casefold()
        if clean in normalized:
            row_issues.append({"ticker": clean, "reason": "duplicate_ticker_row"})
            continue
        if folded in seen_folded:
            row_issues.append({
                "ticker": clean, "reason": "case_variant_duplicate_ticker_row",
                "first_seen": seen_folded[folded],
            })
            continue
        normalized[clean] = {
            "tier": str(tier), "version": int(version), "gen": 0,
        }
        seen_folded[folded] = clean
    return {
        "universe_id": universe_id if isinstance(universe_id, str) else "",
        "snapshot_id": snapshot_id if isinstance(snapshot_id, str) else "",
        "slots": normalized,
        "proposed": {},
        "committed": {},
        "rolled_back": {},
        "expired": {},
        "used_tokens": {},
        "used_leases": {},
        "journal": [],
        "row_issues": row_issues,
    }


def _journal_entries(machine: Mapping[str, Any], kind: str,
                     lease_id: str) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    journal: Any = machine.get("journal")
    if not isinstance(journal, list):
        return found
    for entry in journal:
        if (
            isinstance(entry, Mapping)
            and entry.get("kind") == kind
            and entry.get("lease_id") == lease_id
        ):
            found.append(entry)
    return found


def _proposal_problems(
    machine: Mapping[str, Any], proposal: Any, *, now: datetime,
    exclude_lease: Optional[str] = None,
) -> list[str]:
    try:
        if not isinstance(proposal, Mapping):
            return ["proposal_malformed"]
        reasons: list[str] = []
        required: tuple[str, ...] = (
            "ticker", "expected_prior_tier", "expected_prior_version",
            "expected_prior_gen", "destination_tier", "readiness_hash",
            "universe_id", "snapshot_id", "lease_id", "token",
            "created_at_utc", "expires_at_utc",
            "enrollment_proof", "coverage_proof",
        )
        for key in required:
            if key not in proposal:
                reasons.append(f"proposal_missing_{key}")
        if reasons:
            return reasons
        ticker: Any = proposal.get("ticker")
        dest: Any = proposal.get("destination_tier")
        prior_tier: Any = proposal.get("expected_prior_tier")
        prior_version: Any = proposal.get("expected_prior_version")
        prior_gen: Any = proposal.get("expected_prior_gen")
        if not isinstance(ticker, str) or not ticker.strip():
            reasons.append("ticker_invalid")
        if dest not in VALID_TIERS:
            reasons.append("destination_invalid")
        if prior_tier not in VALID_TIERS:
            reasons.append("expected_prior_tier_invalid")
        if (not isinstance(prior_version, int) or isinstance(prior_version, bool)
                or prior_version < 0):
            reasons.append("expected_prior_version_invalid")
        if (not isinstance(prior_gen, int) or isinstance(prior_gen, bool)
                or prior_gen < 0):
            reasons.append("expected_prior_gen_invalid")
        if (isinstance(dest, str) and isinstance(prior_tier, str)
                and dest == prior_tier and not reasons):
            reasons.append("destination_same_as_prior")
        readiness_hash: Any = proposal.get("readiness_hash")
        if (not isinstance(readiness_hash, str)
                or _READINESS_HASH_RE.fullmatch(readiness_hash.strip()) is None):
            reasons.append("readiness_hash_invalid")
        for key in ("universe_id", "snapshot_id", "lease_id", "token"):
            val: Any = proposal.get(key)
            if not isinstance(val, str) or not val.strip():
                reasons.append(f"proposal_missing_{key}")
        machine_universe: Any = machine.get("universe_id")
        machine_snapshot: Any = machine.get("snapshot_id")
        if (isinstance(machine_universe, str) and machine_universe
                and proposal.get("universe_id") != machine_universe):
            reasons.append("universe_mismatch")
        if (isinstance(machine_snapshot, str) and machine_snapshot
                and proposal.get("snapshot_id") != machine_snapshot):
            reasons.append("snapshot_mismatch")
        created: Optional[datetime] = _parse_utc(proposal.get("created_at_utc"))
        expires: Optional[datetime] = _parse_utc(proposal.get("expires_at_utc"))
        if created is None:
            reasons.append("created_timestamp_invalid")
        if expires is None:
            reasons.append("expiry_timestamp_invalid")
        if created is not None and expires is not None and not expires > created:
            reasons.append("expiry_not_after_created")
        if expires is not None and not now < expires:
            reasons.append("lease_expired")
        enrollment: Any = proposal.get("enrollment_proof")
        if not isinstance(enrollment, Mapping) or enrollment.get("enrolled") is not True:
            reasons.append("enrollment_missing")
        elif enrollment.get("tier") != dest:
            reasons.append("enrollment_tier_mismatch")
        coverage: Any = proposal.get("coverage_proof")
        if not isinstance(coverage, Mapping) or coverage.get("covered") is not True:
            reasons.append("coverage_missing")
        slots: Any = machine.get("slots")
        current: Any = None
        if isinstance(slots, dict) and isinstance(ticker, str):
            try:
                current = slots.get(ticker)
            except (TypeError, ValueError):
                current = None
        if not isinstance(current, Mapping):
            reasons.append("ticker_unknown")
        else:
            if current.get("tier") != prior_tier:
                reasons.append("stale_expected_tier")
            if current.get("version") != prior_version:
                reasons.append("stale_expected_version")
            if current.get("gen") != prior_gen:
                reasons.append("stale_expected_gen")
        lease_id: Any = proposal.get("lease_id")
        token: Any = proposal.get("token")
        if not isinstance(lease_id, str) or not lease_id.strip():
            reasons.append("lease_invalid")
        else:
            proposed: Any = machine.get("proposed")
            try:
                in_proposed: bool = isinstance(proposed, dict) and lease_id in proposed
            except (TypeError, ValueError):
                in_proposed = False
            if in_proposed and lease_id != exclude_lease:
                reasons.append("duplicate_active_lease")
            used_leases: Any = machine.get("used_leases")
            try:
                seen_lease: bool = isinstance(used_leases, dict) and lease_id in used_leases
            except (TypeError, ValueError):
                seen_lease = False
            if seen_lease and lease_id != exclude_lease and not in_proposed:
                reasons.append("lease_id_reuse_rejected")
            # Only unexpired staged proposals hold the ticker lock; committed
            # history and expired staged proposals must not block follow-ups.
            # A staged proposal whose expires_at_utc <= now no longer holds
            # the lock even before expire() is called.
            if isinstance(ticker, str) and ticker:
                staged: Any = machine.get("proposed")
                if isinstance(staged, dict):
                    for other_id, other in staged.items():
                        if other_id == exclude_lease:
                            continue
                        if isinstance(other, Mapping) and other.get("ticker") == ticker:
                            try:
                                other_exp: Optional[datetime] = _parse_utc(
                                    other.get("expires_at_utc"))
                            except Exception:
                                other_exp = None
                            if other_exp is not None and not now < other_exp:
                                continue
                            reasons.append("ticker_lease_active")
                            break
        if isinstance(token, str) and token:
            used_tokens: Any = machine.get("used_tokens")
            try:
                token_seen: bool = isinstance(used_tokens, dict) and token in used_tokens
            except (TypeError, ValueError):
                token_seen = False
            if token_seen and used_tokens[token] != lease_id:
                reasons.append("token_reuse_rejected")
        seen: set[str] = set()
        deduped: list[str] = []
        for code in reasons:
            if code not in seen:
                seen.add(code)
                deduped.append(code)
        return deduped
    except (TypeError, ValueError, AttributeError):
        return ["proposal_malformed"]


def propose(
    machine: Mapping[str, Any], proposal: Mapping[str, Any], *, now_utc: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Stage a proposal; returns independent (new_machine, result) copies."""
    try:
        before: dict[str, Any] = _copy_machine(machine)
        now: Optional[datetime] = _parse_utc(now_utc)
        if now is None:
            return copy.deepcopy(before), {"ok": False, "reasons": ["now_malformed"]}
        problems: list[str] = _proposal_problems(before, proposal, now=now)
        if problems:
            return copy.deepcopy(before), {"ok": False, "reasons": problems}
        lease_id: str = str(proposal["lease_id"])
        token: str = str(proposal["token"])
        stored: dict[str, Any] = copy.deepcopy(dict(proposal))
        after: dict[str, Any] = _copy_machine(before)
        after["proposed"][lease_id] = stored
        if isinstance(after.get("used_tokens"), dict):
            after["used_tokens"][token] = lease_id
        if isinstance(after.get("used_leases"), dict):
            after["used_leases"][lease_id] = str(proposal["ticker"])
        proposal_hash: str = _proposal_hash(stored)
        after["journal"] = list(after.get("journal", [])) + [{
            "kind": "proposed", "lease_id": lease_id,
            "ticker": str(proposal["ticker"]),
            "destination_tier": str(proposal["destination_tier"]),
            "proposal_hash": proposal_hash,
        }]
        return copy.deepcopy(after), {
            "ok": True, "reasons": [], "proposal": copy.deepcopy(stored),
        }
    except Exception:
        try:
            return _copy_machine(machine), {"ok": False, "reasons": ["proposal_malformed"]}
        except Exception:
            return machine, {"ok": False, "reasons": ["proposal_malformed"]}


def _approval_problems(approval: Any, *, record: Mapping[str, Any],
                       now: datetime) -> list[str]:
    try:
        if not isinstance(approval, Mapping):
            return ["approval_malformed"]
        reasons: list[str] = []
        approver: Any = approval.get("approver")
        if not isinstance(approver, str) or not approver.strip():
            reasons.append("approval_approver_missing")
        elif _approver_rejected(approver):
            reasons.append("approval_machine_approver_rejected")
        if approval.get("lease_id") != record.get("lease_id"):
            reasons.append("approval_lease_mismatch")
        if approval.get("token") != record.get("token"):
            reasons.append("approval_token_mismatch")
        if approval.get("readiness_hash") != record.get("readiness_hash"):
            reasons.append("approval_readiness_mismatch")
        approved: Optional[datetime] = _parse_utc(approval.get("approved_at_utc"))
        created: Optional[datetime] = _parse_utc(record.get("created_at_utc"))
        expires: Optional[datetime] = _parse_utc(record.get("expires_at_utc"))
        if approved is None:
            reasons.append("approval_timestamp_invalid")
        else:
            if approved > now:
                reasons.append("approval_in_future")
            if created is not None and approved < created:
                reasons.append("approval_before_proposal")
            if expires is not None and not approved < expires:
                reasons.append("approval_after_expiry")
        if approval.get("method") != APPROVAL_METHOD:
            reasons.append("approval_method_invalid")
        if approval.get("automatic") is True:
            reasons.append("approval_automatic_rejected")
        return reasons
    except (TypeError, ValueError, AttributeError):
        return ["approval_malformed"]


def commit(
    machine: Mapping[str, Any],
    *,
    lease_id: str,
    token: str,
    approval: Mapping[str, Any],
    now_utc: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Commit a journal-bound staged proposal; exact replay is idempotent."""
    try:
        before: dict[str, Any] = _copy_machine(machine)
        now: Optional[datetime] = _parse_utc(now_utc)
        if now is None:
            return copy.deepcopy(before), {"ok": False, "reasons": ["now_malformed"]}
        if not isinstance(lease_id, str) or not lease_id.strip():
            return copy.deepcopy(before), {"ok": False, "reasons": ["lease_invalid"]}
        committed: Any = before.get("committed")
        if isinstance(committed, dict) and lease_id in committed:
            prior: Any = committed[lease_id]
            same_token: bool = isinstance(prior, Mapping) and prior.get("token") == token
            try:
                same_approval: bool = (isinstance(prior, Mapping)
                                       and prior.get("approval") == dict(approval or {}))
            except (TypeError, ValueError, AttributeError):
                same_approval = False
            if same_token and same_approval:
                slot: Any = None
                if isinstance(prior, Mapping):
                    slots: Any = before.get("slots")
                    if isinstance(slots, dict):
                        try:
                            slot = copy.deepcopy(slots.get(prior.get("ticker")))
                        except (TypeError, ValueError):
                            slot = None
                return copy.deepcopy(before), {"ok": True, "reasons": [],
                                               "replay": True, "slot": slot}
            return copy.deepcopy(before), {"ok": False, "reasons": ["conflicting_replay"]}
        proposed: Any = before.get("proposed")
        if not isinstance(proposed, dict):
            return copy.deepcopy(before), {"ok": False, "reasons": ["no_valid_proposal"]}
        try:
            record: Any = proposed.get(lease_id)
        except (TypeError, ValueError):
            return copy.deepcopy(before), {"ok": False, "reasons": ["no_valid_proposal"]}
        if not isinstance(record, Mapping):
            return copy.deepcopy(before), {"ok": False, "reasons": ["no_valid_proposal"]}
        if record.get("token") != token:
            return copy.deepcopy(before), {"ok": False, "reasons": ["lease_token_mismatch"]}
        proposed_lines: list[Mapping[str, Any]] = _journal_entries(
            before, "proposed", lease_id)
        if len(proposed_lines) != 1:
            return copy.deepcopy(before), {"ok": False, "reasons": ["journal_mismatch"]}
        if proposed_lines[0].get("proposal_hash") != _proposal_hash(record):
            return copy.deepcopy(before), {"ok": False, "reasons": ["journal_mismatch"]}
        recheck: list[str] = _proposal_problems(before, record, now=now,
                                                exclude_lease=lease_id)
        if recheck:
            return copy.deepcopy(before), {"ok": False, "reasons": recheck}
        approval_problems: list[str] = _approval_problems(approval, record=record,
                                                           now=now)
        if approval_problems:
            return copy.deepcopy(before), {"ok": False, "reasons": approval_problems}
        ticker: Any = record.get("ticker")
        slots: Any = before.get("slots")
        current: Any = None
        if isinstance(slots, dict) and isinstance(ticker, str):
            try:
                current = slots.get(ticker)
            except (TypeError, ValueError):
                current = None
        if not isinstance(current, Mapping):
            return copy.deepcopy(before), {"ok": False, "reasons": ["ticker_unknown"]}
        if current.get("tier") != record.get("expected_prior_tier"):
            return copy.deepcopy(before), {"ok": False, "reasons": ["stale_expected_tier"]}
        if current.get("version") != record.get("expected_prior_version"):
            return copy.deepcopy(before), {"ok": False, "reasons": ["stale_expected_version"]}
        if current.get("gen") != record.get("expected_prior_gen"):
            return copy.deepcopy(before), {"ok": False, "reasons": ["stale_expected_gen"]}
        after: dict[str, Any] = _copy_machine(before)
        next_version: int = int(current["version"]) + 1
        next_gen: int = int(current["gen"]) + 1
        after["slots"][str(ticker)] = {"tier": str(record["destination_tier"]),
                                       "version": next_version, "gen": next_gen}
        entry: dict[str, Any] = {
            "lease_id": lease_id, "ticker": str(ticker), "token": token,
            "proposal": copy.deepcopy(dict(record)),
            "approval": copy.deepcopy(dict(approval)),
            "prior_tier": current["tier"], "prior_version": current["version"],
            "prior_gen": current["gen"],
            "next_tier": str(record["destination_tier"]),
            "next_version": next_version, "next_gen": next_gen,
        }
        del after["proposed"][lease_id]
        after["committed"][lease_id] = entry
        after["journal"] = list(after.get("journal", [])) + [{
            "kind": "committed", "lease_id": lease_id, "ticker": str(ticker),
            "proposal_hash": _proposal_hash(record),
            "prior_tier": current["tier"], "prior_version": current["version"],
            "prior_gen": current["gen"],
            "next_tier": str(record["destination_tier"]),
            "next_version": next_version, "next_gen": next_gen,
        }]
        return copy.deepcopy(after), {"ok": True, "reasons": [], "replay": False,
                                      "slot": copy.deepcopy(after["slots"][str(ticker)])}
    except Exception:
        try:
            return _copy_machine(machine), {"ok": False, "reasons": ["commit_malformed"]}
        except Exception:
            return machine, {"ok": False, "reasons": ["commit_malformed"]}


def expire(
    machine: Mapping[str, Any], *, now_utc: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Expire staged proposals past their timeout; slots stay unchanged."""
    try:
        before: dict[str, Any] = _copy_machine(machine)
        now: Optional[datetime] = _parse_utc(now_utc)
        if now is None:
            return copy.deepcopy(before), {"ok": False, "reasons": ["now_malformed"]}
        after: dict[str, Any] = _copy_machine(before)
        if not isinstance(after.get("proposed"), dict):
            return copy.deepcopy(before), {"ok": False,
                                           "reasons": ["expire_state_malformed"]}
        if not isinstance(after.get("expired"), dict):
            after["expired"] = {}
        expired_now: list[str] = []
        for lease_id, record in list(after.get("proposed", {}).items()):
            expires: Optional[datetime] = (_parse_utc(record.get("expires_at_utc"))
                                           if isinstance(record, Mapping) else None)
            if expires is None or not now < expires:
                expired_now.append(lease_id)
                after["expired"][lease_id] = record
                del after["proposed"][lease_id]
                try:
                    _ph: str = (_proposal_hash(record)
                               if isinstance(record, Mapping) else "")
                except Exception:
                    _ph = ""
                after["journal"] = list(after.get("journal", [])) + [{
                    "kind": "expired", "lease_id": lease_id,
                    "ticker": str(record.get("ticker")) if isinstance(record, Mapping) else "",
                    "proposal_hash": _ph,
                }]
        return copy.deepcopy(after), {"ok": True, "reasons": [], "expired": expired_now,
                                      "slots_unchanged": True}
    except Exception:
        try:
            return _copy_machine(machine), {"ok": False, "reasons": ["expire_malformed"]}
        except Exception:
            return machine, {"ok": False, "reasons": ["expire_malformed"]}


def _valid_tier_version_gen(entry: Mapping[str, Any], prefix: str) -> bool:
    tier: Any = entry.get(f"{prefix}_tier")
    version: Any = entry.get(f"{prefix}_version")
    gen: Any = entry.get(f"{prefix}_gen")
    return (
        tier in VALID_TIERS
        and isinstance(version, int) and not isinstance(version, bool) and version >= 0
        and isinstance(gen, int) and not isinstance(gen, bool) and gen >= 0
    )


def rollback(
    machine: Mapping[str, Any], *, lease_id: str, token: str, now_utc: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Exact inverse of a journal-bound committed entry; gen stays monotonic.

    Only the latest undisturbed commit on a ticker is directly reversible:
    the live slot must still equal the commit's next tier/version/gen.
    Further unwinding needs a fresh proposal; rollback never walks history.
    """
    try:
        before: dict[str, Any] = _copy_machine(machine)
        now: Optional[datetime] = _parse_utc(now_utc)
        if now is None:
            return copy.deepcopy(before), {"ok": False, "reasons": ["now_malformed"]}
        committed: Any = before.get("committed")
        if not isinstance(committed, dict):
            return copy.deepcopy(before), {"ok": False,
                                           "reasons": ["no_committed_transaction"]}
        try:
            entry: Any = committed.get(lease_id)
        except (TypeError, ValueError):
            return copy.deepcopy(before), {"ok": False,
                                           "reasons": ["no_committed_transaction"]}
        if not isinstance(entry, Mapping):
            return copy.deepcopy(before), {"ok": False,
                                           "reasons": ["no_committed_transaction"]}
        if entry.get("token") != token:
            return copy.deepcopy(before), {"ok": False,
                                           "reasons": ["lease_token_mismatch"]}
        stored_proposal: Any = entry.get("proposal")
        if not isinstance(stored_proposal, Mapping):
            return copy.deepcopy(before), {"ok": False, "reasons": ["journal_mismatch"]}
        entry_hash: str = _proposal_hash(stored_proposal)
        commit_lines: list[Mapping[str, Any]] = _journal_entries(
            before, "committed", lease_id)
        if len(commit_lines) != 1:
            return copy.deepcopy(before), {"ok": False, "reasons": ["journal_mismatch"]}
        commit_line: Mapping[str, Any] = commit_lines[0]
        if commit_line.get("proposal_hash") != entry_hash:
            return copy.deepcopy(before), {"ok": False, "reasons": ["journal_mismatch"]}
        if commit_line.get("ticker") != entry.get("ticker"):
            return copy.deepcopy(before), {"ok": False, "reasons": ["journal_mismatch"]}
        proposed_lines: list[Mapping[str, Any]] = _journal_entries(
            before, "proposed", lease_id)
        if not any(line.get("proposal_hash") == entry_hash for line in proposed_lines):
            return copy.deepcopy(before), {"ok": False, "reasons": ["journal_mismatch"]}
        if not _valid_tier_version_gen(entry, "prior"):
            return copy.deepcopy(before), {"ok": False,
                                           "reasons": ["commit_record_invalid"]}
        if not _valid_tier_version_gen(entry, "next"):
            return copy.deepcopy(before), {"ok": False,
                                           "reasons": ["commit_record_invalid"]}
        if (entry.get("prior_tier") != stored_proposal.get("expected_prior_tier")
                or entry.get("prior_version") != stored_proposal.get("expected_prior_version")
                or entry.get("prior_gen") != stored_proposal.get("expected_prior_gen")):
            return copy.deepcopy(before), {"ok": False, "reasons": ["journal_mismatch"]}
        if (entry.get("next_tier") != stored_proposal.get("destination_tier")
                or entry.get("next_version") != int(entry["prior_version"]) + 1
                or entry.get("next_gen") != int(entry["prior_gen"]) + 1):
            return copy.deepcopy(before), {"ok": False, "reasons": ["journal_mismatch"]}
        for key in ("prior_tier", "prior_version", "prior_gen",
                    "next_tier", "next_version", "next_gen"):
            if commit_line.get(key) != entry.get(key):
                return copy.deepcopy(before), {"ok": False,
                                               "reasons": ["journal_mismatch"]}
        ticker: Any = entry.get("ticker")
        current: Any = None
        if isinstance(before.get("slots"), dict) and isinstance(ticker, str):
            try:
                current = before["slots"].get(ticker)
            except (TypeError, ValueError):
                current = None
        if not isinstance(current, Mapping):
            return copy.deepcopy(before), {"ok": False, "reasons": ["ticker_unknown"]}
        if (current.get("tier") != entry.get("next_tier")
                or current.get("version") != entry.get("next_version")
                or current.get("gen") != entry.get("next_gen")):
            return copy.deepcopy(before), {"ok": False,
                                           "reasons": ["rollback_cross_version_rejected"]}
        if current.get("tier") != stored_proposal.get("destination_tier"):
            return copy.deepcopy(before), {"ok": False, "reasons": ["journal_mismatch"]}
        after: dict[str, Any] = _copy_machine(before)
        restored_gen: int = int(current["gen"]) + 1
        after["slots"][str(ticker)] = {"tier": entry["prior_tier"],
                                       "version": entry["prior_version"],
                                       "gen": restored_gen}
        rolled: dict[str, Any] = copy.deepcopy(dict(entry))
        del after["committed"][lease_id]
        after["rolled_back"][lease_id] = rolled
        after["journal"] = list(after.get("journal", [])) + [{
            "kind": "rolled_back", "lease_id": lease_id, "ticker": str(ticker),
            "proposal_hash": entry_hash,
            "prior_tier": entry["prior_tier"], "prior_version": entry["prior_version"],
            "prior_gen": entry["prior_gen"],
            "next_tier": entry["next_tier"], "next_version": entry["next_version"],
            "next_gen": entry["next_gen"],
        }]
        return copy.deepcopy(after), {
            "ok": True, "reasons": [],
            "slot": copy.deepcopy(after["slots"][str(ticker)]),
        }
    except Exception:
        try:
            return _copy_machine(machine), {"ok": False,
                                            "reasons": ["rollback_malformed"]}
        except Exception:
            return machine, {"ok": False, "reasons": ["rollback_malformed"]}


def _commit_line_valid(line: Mapping[str, Any]) -> bool:
    for key in ("prior_tier", "next_tier"):
        if line.get(key) not in VALID_TIERS:
            return False
    for key in ("prior_version", "next_version", "prior_gen", "next_gen"):
        val: Any = line.get(key)
        if not isinstance(val, int) or isinstance(val, bool) or val < 0:
            return False
    try:
        return (int(line["next_version"]) == int(line["prior_version"]) + 1
                and int(line["next_gen"]) == int(line["prior_gen"]) + 1)
    except (TypeError, ValueError):
        return False


def recover(journal: Any) -> dict[str, Any]:
    """Replay an in-memory journal per lease; illegal sequences fail closed.

    Sequential commits on one ticker are accepted only when the next
    commit's prior tier/version/gen equals the previous holder's next
    values, then the holder hands off to the new lease. True
    same-prior/concurrent commits are rejected. After a rollback the
    chain continues against the restored values (prior tier/version with
    gen one past the rolled-back next gen); further unwinding needs a
    fresh proposal. Ticker/hash/prior/next are validated on committed,
    rolled_back and expired entries; committed/rolled_back entries must
    carry proposal_hash. In-flight proposed leases are reported as
    needs_reversal with a non-ok status.
    """
    counts: dict[str, int] = {
        "proposed": 0, "committed": 0, "rolled_back": 0, "expired": 0,
        "malformed": 0, "blocked": 0,
    }
    reasons: list[str] = []
    leases: dict[str, str] = {}
    lease_ticker: dict[str, str] = {}
    lease_hash: dict[str, str] = {}
    lease_prior: dict[str, tuple] = {}
    lease_next: dict[str, tuple] = {}
    committed_holder: dict[str, str] = {}
    holder_next: dict[str, tuple] = {}
    ticker_baseline: dict[str, tuple] = {}
    if not isinstance(journal, (list, tuple)):
        return {"status": "error", "counts": counts,
                "reasons": ["journal_malformed"], "leases": leases}

    def _block(index: int, lease_id: str, code: str) -> None:
        counts["blocked"] += 1
        leases[lease_id] = "blocked"
        reasons.append(f"entry_{index}_{code}")
        holder: Any = committed_holder.get(lease_ticker.get(lease_id, ""))
        if holder == lease_id:
            try:
                del committed_holder[lease_ticker[lease_id]]
            except KeyError:
                pass
            try:
                del holder_next[lease_ticker[lease_id]]
            except KeyError:
                pass

    def _tvg(entry: Mapping[str, Any], prefix: str) -> Optional[tuple]:
        try:
            t: Any = entry.get(f"{prefix}_tier")
            v: Any = entry.get(f"{prefix}_version")
            g: Any = entry.get(f"{prefix}_gen")
        except (TypeError, ValueError, AttributeError):
            return None
        if (t in VALID_TIERS and isinstance(v, int) and not isinstance(v, bool)
                and v >= 0 and isinstance(g, int) and not isinstance(g, bool)
                and g >= 0):
            return (t, int(v), int(g))
        return None

    for index, entry in enumerate(journal):
        if not isinstance(entry, Mapping):
            counts["malformed"] += 1
            reasons.append(f"entry_{index}_malformed")
            continue
        kind: Any = entry.get("kind")
        lease_id: Any = entry.get("lease_id")
        ticker: Any = entry.get("ticker")
        if (kind not in PROPOSAL_KINDS or not isinstance(lease_id, str)
                or not lease_id.strip() or not isinstance(ticker, str)
                or not ticker.strip()):
            counts["malformed"] += 1
            reasons.append(f"entry_{index}_malformed")
            continue
        phash: Any = entry.get("proposal_hash")
        phash_str: str = phash if isinstance(phash, str) else ""
        state: Optional[str] = leases.get(lease_id)
        if kind == "proposed":
            if not phash_str.strip():
                counts["blocked"] += 1
                leases[lease_id] = "blocked"
                reasons.append(f"entry_{index}_proposal_hash_missing_blocked")
                continue
            if state is None:
                leases[lease_id] = "proposed"
                lease_ticker[lease_id] = ticker
                lease_hash[lease_id] = phash_str
                counts["proposed"] += 1
            else:
                _block(index, lease_id, "duplicate_proposal_blocked")
        elif kind == "committed":
            if state != "proposed":
                counts["blocked"] += 1
                leases[lease_id] = "blocked"
                if state == "committed":
                    reasons.append(f"entry_{index}_duplicate_commit_blocked")
                else:
                    reasons.append(f"entry_{index}_orphan_commit_blocked")
                continue
            if not phash_str.strip():
                _block(index, lease_id, "proposal_hash_missing_blocked")
                continue
            if lease_ticker.get(lease_id) != ticker:
                _block(index, lease_id, "ticker_changed_blocked")
                continue
            if phash_str and lease_hash.get(lease_id) and phash_str != lease_hash[lease_id]:
                _block(index, lease_id, "hash_changed_blocked")
                continue
            if not _commit_line_valid(entry):
                _block(index, lease_id, "commit_record_blocked")
                continue
            prior_t: Optional[tuple] = _tvg(entry, "prior")
            next_t: Optional[tuple] = _tvg(entry, "next")
            if prior_t is None or next_t is None:
                _block(index, lease_id, "commit_record_blocked")
                continue
            holder: Optional[str] = committed_holder.get(ticker)
            if holder is not None and holder != lease_id:
                expected: Optional[tuple] = holder_next.get(ticker)
                if expected is None or prior_t != expected:
                    _block(index, lease_id, "concurrent_commit_blocked")
                    continue
            elif holder is None:
                baseline: Optional[tuple] = ticker_baseline.get(ticker)
                if baseline is not None and prior_t != baseline:
                    _block(index, lease_id, "stale_prior_blocked")
                    continue
            leases[lease_id] = "committed"
            committed_holder[ticker] = lease_id
            holder_next[ticker] = next_t
            lease_prior[lease_id] = prior_t
            lease_next[lease_id] = next_t
            if ticker in ticker_baseline:
                del ticker_baseline[ticker]
            counts["committed"] += 1
        elif kind == "rolled_back":
            if state != "committed":
                counts["blocked"] += 1
                leases[lease_id] = "blocked"
                reasons.append(f"entry_{index}_rollback_without_commit_blocked")
                continue
            if not phash_str.strip():
                _block(index, lease_id, "proposal_hash_missing_blocked")
                continue
            if lease_ticker.get(lease_id) != ticker:
                _block(index, lease_id, "ticker_changed_blocked")
                continue
            if phash_str and lease_hash.get(lease_id) and phash_str != lease_hash[lease_id]:
                _block(index, lease_id, "hash_changed_blocked")
                continue
            if committed_holder.get(ticker) != lease_id:
                _block(index, lease_id, "rollback_not_current_holder_blocked")
                continue
            entry_prior: Optional[tuple] = _tvg(entry, "prior")
            entry_next: Optional[tuple] = _tvg(entry, "next")
            if entry_prior is not None and lease_prior.get(lease_id) is not None:
                if entry_prior != lease_prior[lease_id]:
                    _block(index, lease_id, "rollback_prior_mismatch_blocked")
                    continue
            if entry_next is not None and lease_next.get(lease_id) is not None:
                if entry_next != lease_next[lease_id]:
                    _block(index, lease_id, "rollback_next_mismatch_blocked")
                    continue
            stored_prior: Optional[tuple] = lease_prior.get(lease_id, entry_prior)
            stored_next: Optional[tuple] = lease_next.get(lease_id, entry_next)
            leases[lease_id] = "rolled_back"
            if committed_holder.get(ticker) == lease_id:
                del committed_holder[ticker]
                try:
                    del holder_next[ticker]
                except KeyError:
                    pass
            if stored_prior is not None and stored_next is not None:
                ticker_baseline[ticker] = (
                    stored_prior[0], stored_prior[1], stored_next[2] + 1)
            counts["rolled_back"] += 1
        elif kind == "expired":
            if state != "proposed":
                counts["blocked"] += 1
                leases[lease_id] = "blocked"
                reasons.append(f"entry_{index}_expiry_without_proposal_blocked")
                continue
            if lease_ticker.get(lease_id) != ticker:
                _block(index, lease_id, "ticker_changed_blocked")
                continue
            if not phash_str.strip():
                _block(index, lease_id, "proposal_hash_missing_blocked")
                continue
            if phash_str != lease_hash.get(lease_id):
                _block(index, lease_id, "hash_changed_blocked")
                continue
            entry_prior_e: Optional[tuple] = _tvg(entry, "prior")
            entry_next_e: Optional[tuple] = _tvg(entry, "next")
            if entry_prior_e is not None or entry_next_e is not None:
                if entry_prior_e is None or entry_next_e is None:
                    _block(index, lease_id, "expiry_record_blocked")
                    continue
            leases[lease_id] = "expired"
            counts["expired"] += 1
    for _lid, _st in list(leases.items()):
        if _st == "proposed":
            leases[_lid] = "needs_reversal"
            reasons.append(f"{_lid}_needs_reversal")
    bad: bool = (counts["malformed"] > 0 or counts["blocked"] > 0
                 or any(s == "needs_reversal" for s in leases.values()))
    status: str = "error" if bad else "ok"
    if bad and "journal_has_problems" not in reasons:
        reasons.append("journal_has_problems")
    return {"status": status, "counts": counts, "reasons": reasons,
            "leases": dict(leases)}
