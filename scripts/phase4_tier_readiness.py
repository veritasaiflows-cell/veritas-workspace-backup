"""Phase 4 per-name tier readiness evaluation (inert decision infrastructure).

Pure, deterministic, side-effect free. Evaluates promotion/readiness
evidence and returns recommendation evidence only. It never mutates a
tier, never writes a DB/file, never touches network, and never approves
anything. Prior effective tier stays authoritative pending explicit
review/commit handled elsewhere. Callers receive fresh plain dicts and
lists on every call; mutating a returned object cannot affect later
calls because no state is retained between calls.

Trust limit, stated plainly: readiness results are plain caller-held
dicts. Eligibility and promotion recompute the evidence hash from the
evidence mapping and check ticker/universe/snapshot binding, which
catches stale, mismatched, or internally inconsistent results, but this
in-process library cannot authenticate who evaluated the evidence. Real
trust belongs to the Main/owner review gate, not this module.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping, Optional

VALID_TIERS: tuple[str, ...] = ("A", "B", "C")
BAND_MAX_AGE_DAYS: int = 7
CONTEXT_MAX_AGE_DAYS: int = 30
ELIGIBILITY_MAX_AGE_DAYS: int = 7
ELIGIBILITY_MAX_AGE_CEILING: int = 7
MIN_VALID_BARS: int = 252
MAX_REPAIRED_BARS: int = 2
DEMOTION_MIN_OBSERVATION_DAYS: int = 21
DEMOTION_MIN_OBSERVATIONS: int = 5
DEMOTION_ALLOWED_BASES: frozenset[str] = frozenset({
    "thesis_impairment",
    "reduced_materiality",
    "fundamental_deterioration",
    "materiality_decline",
    "catalyst_exhaustion",
})
DEMOTION_SYSTEM_ACTORS: frozenset[str] = frozenset({
    "veritas_os_freshness_monitor",
    "os_monitor",
    "freshness_monitor",
    "system",
    "auto",
    "autobot",
    "auto_bot",
    "bot",
    "machine",
    "scheduler",
    "cron",
    "monitor",
    "os_freshness_monitor",
})
_HASH_RE: Any = re.compile(r"[0-9a-f]{64}")
_SYSTEM_REJECT_STEMS: tuple[str, ...] = (
    "cron", "schedul", "monitor", "bot", "auto", "system",
    "machin", "freshness",
)
_DECAY_REJECT_SUBSTRINGS: tuple[str, ...] = (
    "stale", "fresh", "missing", "gap", "update",
)


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


def _parse_date(value: Any) -> Optional[date]:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, TypeError, AttributeError):
        return None


def _finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (ValueError, TypeError, OverflowError):
        return False


def _valid_max_age(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value)) and 0 < float(value) <= ELIGIBILITY_MAX_AGE_CEILING
    except (ValueError, TypeError, OverflowError):
        return False


def canonical_evidence_hash(evidence: Mapping[str, Any]) -> str:
    """Deterministic sha256 over canonical JSON of the evidence mapping."""
    try:
        raw: bytes = json.dumps(
            evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return "unhashable"
    return hashlib.sha256(raw).hexdigest()


def _methodology_supported(methodology: Any) -> bool:
    if not isinstance(methodology, str):
        return False
    m: str = methodology.strip()
    return (
        m == "mech-v3-floor-atr20"
        or m.startswith("mech-v3-floor-atr20-")
        or m.startswith("mech-v3-floor-atr20+")
        or m.startswith("mech-v4")
    )


@dataclass(frozen=True)
class ReadinessProvenance:
    universe_id: str
    snapshot_id: str
    now_utc: str
    evidence_hash: str


def _normalize_basis(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    return "_".join(value.strip().lower().replace("-", "_").split())


def evaluate_readiness(
    evidence: Mapping[str, Any],
    *,
    now_utc: str,
    universe_id: str,
    snapshot_id: str,
    expected_ticker: str,
    expected_pin_id: str,
    prior_tier: Optional[str] = None,
    prior_version: Optional[int] = None,
) -> dict[str, Any]:
    """Evaluate every readiness gate; fail closed with exact reasons.

    expected_ticker and expected_pin_id are required: the evidence must
    carry the expected ticker identity and the band pin must equal the
    expected pin. Thesis and band sub-objects must each carry the same
    ticker. Returns fresh plain dicts/lists on every call.
    """
    reasons: list[str] = []
    now: Optional[datetime] = _parse_utc(now_utc)
    if now is None:
        reasons.append("now_malformed")
    if not isinstance(universe_id, str) or not universe_id.strip():
        reasons.append("universe_identity_missing")
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        reasons.append("snapshot_identity_missing")
    if not isinstance(evidence, Mapping):
        reasons.append("evidence_malformed")
        evidence = {}

    def _sub(name: str) -> Mapping[str, Any]:
        sub: Any = evidence.get(name)
        return sub if isinstance(sub, Mapping) else {}

    ticker: Any = evidence.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        reasons.append("ticker_missing")
        ticker = ""
    else:
        ticker = ticker.strip()
    if not isinstance(expected_ticker, str) or not expected_ticker.strip():
        reasons.append("ticker_mismatch")
    elif ticker != expected_ticker.strip():
        reasons.append("ticker_mismatch")

    if prior_tier is not None and prior_tier not in VALID_TIERS:
        reasons.append("prior_tier_invalid")
    if prior_version is not None and (
        not isinstance(prior_version, int)
        or isinstance(prior_version, bool)
        or prior_version < 0
    ):
        reasons.append("prior_version_invalid")

    # 1. Accepted in-date thesis.
    thesis: Mapping[str, Any] = _sub("thesis")
    if not thesis:
        reasons.append("thesis_missing")
    else:
        if thesis.get("status") != "accepted":
            reasons.append("thesis_not_accepted")
        due: Optional[date] = _parse_date(thesis.get("review_due"))
        if due is None:
            reasons.append("thesis_review_due_malformed")
        elif now is not None and due < now.date():
            reasons.append("thesis_overdue")
        if thesis.get("ticker") != ticker or not ticker:
            reasons.append("ticker_mismatch")

    # 2-4. Fresh pin-bound band with confidence; geometry; width >= ATR20.
    band: Mapping[str, Any] = _sub("band")
    if not band:
        reasons.append("band_missing")
    else:
        gen: Optional[datetime] = _parse_utc(band.get("generated_at_utc"))
        if gen is None:
            reasons.append("band_timestamp_malformed")
        elif now is not None and (now - gen).total_seconds() < 0:
            reasons.append("band_timestamp_in_future")
        elif now is not None and (now - gen).total_seconds() > BAND_MAX_AGE_DAYS * 86400:
            reasons.append("band_stale")
        if band.get("pinned") is not True:
            reasons.append("band_not_pin_bound")
        pin_id: Any = band.get("pin_id")
        if not isinstance(pin_id, str) or not pin_id.strip():
            reasons.append("band_not_pin_bound")
        elif (not isinstance(expected_pin_id, str)
                or pin_id.strip() != expected_pin_id.strip()):
            reasons.append("band_pin_mismatch")
        confidence: Any = band.get("confidence")
        if confidence is None or isinstance(confidence, bool):
            reasons.append("band_confidence_missing")
        elif not _finite_number(confidence):
            reasons.append("band_confidence_malformed")
        elif not 0 <= float(confidence) <= 1:
            reasons.append("band_confidence_out_of_range")
        if not _methodology_supported(band.get("methodology")):
            reasons.append("band_methodology_unsupported")
        if band.get("ticker") != ticker or not ticker:
            reasons.append("ticker_mismatch")
        low: Any = band.get("low")
        high: Any = band.get("high")
        inv: Any = band.get("invalidation")
        atr: Any = band.get("atr20")
        if not all(_finite_number(v) for v in (low, high, inv, atr)):
            reasons.append("band_levels_malformed")
        else:
            if float(low) <= 0 or float(high) <= 0 or float(inv) <= 0:
                reasons.append("band_levels_malformed")
            elif not (float(inv) < float(low) < float(high)):
                reasons.append("invalidation_geometry_invalid")
            if not float(atr) > 0:
                reasons.append("atr20_malformed")
            elif float(high) - float(low) < float(atr):
                reasons.append("band_width_below_atr20")

    # 5. Bars and repairs incl. boundaries.
    bars: Mapping[str, Any] = _sub("bars")
    valid_bars: Any = bars.get("valid_bars")
    repaired: Any = bars.get("repaired_bars")
    if not isinstance(valid_bars, int) or isinstance(valid_bars, bool):
        reasons.append("bars_malformed")
    elif valid_bars < MIN_VALID_BARS:
        reasons.append("bars_insufficient")
    if not isinstance(repaired, int) or isinstance(repaired, bool):
        reasons.append("repairs_malformed")
    elif repaired < 0:
        reasons.append("repairs_malformed")
    elif repaired > MAX_REPAIRED_BARS:
        reasons.append("repairs_exceeded")

    # 6. Earnings + macro/regime present and fresh.
    for key in ("earnings", "macro"):
        ctx: Mapping[str, Any] = _sub(key)
        if not ctx or ctx.get("present") is not True:
            reasons.append(f"{key}_missing")
            continue
        upd: Optional[datetime] = _parse_utc(ctx.get("updated_at_utc"))
        if upd is None:
            reasons.append(f"{key}_timestamp_malformed")
        elif now is not None and (now - upd).total_seconds() < 0:
            reasons.append(f"{key}_timestamp_in_future")
        elif now is not None and (now - upd).total_seconds() > CONTEXT_MAX_AGE_DAYS * 86400:
            reasons.append(f"{key}_stale")

    # 7. Sector ETF benchmark assigned.
    bench: Mapping[str, Any] = _sub("benchmark")
    etf: Any = bench.get("sector_etf")
    if not isinstance(etf, str) or not etf.strip():
        reasons.append("benchmark_missing")

    # 8. Ledger state_snapshot on first evaluation.
    ledger: Mapping[str, Any] = _sub("ledger")
    if ledger.get("has_state_snapshot") is not True:
        reasons.append("ledger_snapshot_missing")

    seen: set[str] = set()
    deduped: list[str] = []
    for code in reasons:
        if code not in seen:
            seen.add(code)
            deduped.append(code)

    ready: bool = len(deduped) == 0
    try:
        evidence_hash: str = canonical_evidence_hash(evidence)
    except (TypeError, ValueError):
        evidence_hash = "unhashable"
    if evidence_hash == "unhashable" and "evidence_malformed" not in deduped:
        deduped.append("evidence_malformed")
        ready = False

    provenance_obj: ReadinessProvenance = ReadinessProvenance(
        universe_id=universe_id if isinstance(universe_id, str) else "",
        snapshot_id=snapshot_id if isinstance(snapshot_id, str) else "",
        now_utc=now_utc if isinstance(now_utc, str) else "",
        evidence_hash=evidence_hash,
    )
    return {
        "ready": ready,
        "reasons": list(deduped),
        "provenance": dict(asdict(provenance_obj)),
        "ticker": ticker,
        "prior_effective_tier": prior_tier,
        "prior_effective_version": prior_version,
        "recommendation_eligible": bool(ready),
        "evidence_hash": evidence_hash,
    }


def prior_tier_authority(prior_tier: Any, prior_version: Any) -> dict[str, Any]:
    """Prior effective tier stays authoritative; readiness never mutates it."""
    reasons: list[str] = []
    if prior_tier not in VALID_TIERS:
        reasons.append("prior_tier_invalid")
    if (
        not isinstance(prior_version, int)
        or isinstance(prior_version, bool)
        or prior_version < 0
    ):
        reasons.append("prior_version_invalid")
    if reasons:
        return {
            "tier": prior_tier,
            "version": prior_version,
            "authoritative": False,
            "reasons": reasons,
            "note": "invalid prior rejected; no tier change implied",
        }
    return {
        "tier": prior_tier,
        "version": prior_version,
        "authoritative": True,
        "reasons": [],
        "note": "recommendation evidence only; tier change needs explicit review/commit",
    }


def _readiness_freshness(
    readiness: Any, evidence: Any, *, now_utc: str, max_age_days: Any,
    expected_ticker: Any, universe_id: Any, snapshot_id: Any,
    expected_pin_id: Any,
) -> list[str]:
    problems: list[str] = []
    if not _valid_max_age(max_age_days):
        return ["readiness_max_age_malformed"]
    if not isinstance(expected_pin_id, str) or not expected_pin_id.strip():
        return ["readiness_expected_pin_missing"]
    if not isinstance(readiness, Mapping):
        return ["readiness_missing"]
    if readiness.get("ready") is not True:
        detail: Any = readiness.get("reasons")
        return list(detail) if isinstance(detail, list) and detail else ["readiness_not_ready"]
    if readiness.get("reasons") != []:
        return ["readiness_not_ready"]
    provenance: Any = readiness.get("provenance")
    if not isinstance(provenance, Mapping):
        return ["readiness_provenance_missing"]
    for key in ("universe_id", "snapshot_id", "now_utc", "evidence_hash"):
        val: Any = provenance.get(key)
        if not isinstance(val, str) or not val.strip():
            return ["readiness_provenance_missing"]
    evidence_hash: Any = readiness.get("evidence_hash")
    if not isinstance(evidence_hash, str) or _HASH_RE.fullmatch(evidence_hash) is None:
        return ["readiness_inconsistent"]
    if evidence_hash != provenance.get("evidence_hash"):
        return ["readiness_inconsistent"]
    if not isinstance(evidence, Mapping):
        return ["readiness_inconsistent"]
    try:
        recomputed: str = canonical_evidence_hash(evidence)
    except (TypeError, ValueError):
        return ["readiness_inconsistent"]
    if recomputed != evidence_hash:
        return ["readiness_inconsistent"]
    if not isinstance(expected_ticker, str) or readiness.get("ticker") != expected_ticker:
        return ["readiness_ticker_mismatch"]
    if provenance.get("universe_id") != universe_id:
        return ["readiness_universe_mismatch"]
    if provenance.get("snapshot_id") != snapshot_id:
        return ["readiness_snapshot_mismatch"]
    now: Optional[datetime] = _parse_utc(now_utc)
    issued: Optional[datetime] = _parse_utc(provenance.get("now_utc"))
    if now is None:
        return ["now_malformed"]
    if issued is None:
        return ["readiness_timestamp_malformed"]
    age_seconds: float = (now - issued).total_seconds()
    if age_seconds < 0:
        return ["readiness_timestamp_in_future"]
    try:
        limit: float = float(max_age_days) * 86400
    except (TypeError, ValueError, OverflowError):
        return ["readiness_max_age_malformed"]
    if age_seconds > limit:
        problems.append("readiness_stale")
    # HIGH binding: re-run evaluate_readiness from the supplied evidence at
    # the eligibility/promotion now_utc and require exact agreement. This
    # catches ready/reasons flips, ticker/universe/snapshot relabels, time
    # shifts, and hand-built hash-valid garbage evidence. Hashes detect
    # drift/inconsistency only; Main/owner remains the authority gate.
    try:
        prior_t: Any = readiness.get("prior_effective_tier")
        prior_v: Any = readiness.get("prior_effective_version")
        if prior_t not in VALID_TIERS:
            prior_t = None
        if (not isinstance(prior_v, int) or isinstance(prior_v, bool)
                or prior_v < 0):
            prior_v = None
        reeval: Any = evaluate_readiness(
            evidence, now_utc=now_utc,
            universe_id=universe_id if isinstance(universe_id, str) else "",
            snapshot_id=snapshot_id if isinstance(snapshot_id, str) else "",
            expected_ticker=expected_ticker if isinstance(expected_ticker, str) else "",
            expected_pin_id=expected_pin_id,
            prior_tier=prior_t, prior_version=prior_v,
        )
    except Exception:
        problems.append("readiness_reevaluation_failed")
        return problems
    if (not isinstance(reeval, dict) or reeval.get("ready") is not True
            or reeval.get("reasons") != []):
        problems.append("readiness_reevaluation_failed")
        return problems
    for _key in ("ready", "reasons", "ticker", "evidence_hash"):
        if reeval.get(_key) != readiness.get(_key):
            problems.append("readiness_binding_mismatch")
            return problems
    _prov2: Any = reeval.get("provenance")
    if (not isinstance(_prov2, Mapping)
            or _prov2.get("universe_id") != provenance.get("universe_id")
            or _prov2.get("snapshot_id") != provenance.get("snapshot_id")):
        problems.append("readiness_binding_mismatch")
        return problems
    return problems


def recommendation_eligibility(
    readiness: Mapping[str, Any], evidence: Mapping[str, Any], *,
    now_utc: str, max_age_days: Any = ELIGIBILITY_MAX_AGE_DAYS,
    expected_ticker: str, universe_id: str, snapshot_id: str,
    expected_pin_id: str,
) -> dict[str, Any]:
    """Eligible only for a fresh, hash-consistent, identity-bound result.

    Re-runs evaluate_readiness from the supplied evidence at now_utc with
    the required identity/pin inputs and requires re-evaluated ready=True
    with empty reasons plus exact agreement on ready, reasons, ticker,
    evidence_hash, universe_id and snapshot_id. Caller-held objects are
    not authenticated; Main/owner remains the authority gate.
    """
    problems: list[str] = _readiness_freshness(
        readiness, evidence, now_utc=now_utc, max_age_days=max_age_days,
        expected_ticker=expected_ticker, universe_id=universe_id,
        snapshot_id=snapshot_id, expected_pin_id=expected_pin_id,
    )
    if problems:
        return {"eligible": False, "reasons": problems}
    return {"eligible": True, "reasons": []}


def evaluate_promotion(
    readiness: Mapping[str, Any], evidence: Mapping[str, Any],
    qualifier: Mapping[str, Any], *, now_utc: str,
    max_age_days: Any = ELIGIBILITY_MAX_AGE_DAYS,
    expected_ticker: str, universe_id: str, snapshot_id: str,
    expected_pin_id: str,
) -> dict[str, Any]:
    """Promotion needs a fresh bound ready result plus strong evidence.

    Applies the same re-evaluation binding as recommendation_eligibility
    before checking qualifier strength/review.
    """
    problems: list[str] = _readiness_freshness(
        readiness, evidence, now_utc=now_utc, max_age_days=max_age_days,
        expected_ticker=expected_ticker, universe_id=universe_id,
        snapshot_id=snapshot_id, expected_pin_id=expected_pin_id,
    )
    if problems:
        return {"allowed": False, "reasons": ["readiness_not_ready"] + problems}
    if not isinstance(qualifier, Mapping):
        return {"allowed": False, "reasons": ["qualifier_malformed"]}
    reasons: list[str] = []
    if qualifier.get("evidence_strength") != "strong":
        reasons.append("promotion_requires_strong_evidence")
    if qualifier.get("review") != "explicit":
        reasons.append("promotion_requires_explicit_review")
    return {"allowed": len(reasons) == 0, "reasons": reasons}


def _actor_rejected(value: Any) -> bool:
    """Reject machine-like actors under unicode/format/punctuation variance.

    NFKC/casefold, strip format characters, normalize non-alphanumerics
    into tokens. Rejects cron/scheduler/monitor/bot/auto/system/machine
    stems and joined forms containing freshness.
    """
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        text: str = unicodedata.normalize("NFKC", value).casefold()
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
        cleaned: str = "".join(ch if ch.isalnum() else " " for ch in text)
        tokens: list[str] = [t for t in cleaned.split() if t]
        if not tokens:
            return False
        joined: str = "".join(tokens)
        legacy: str = "_".join(tokens)
        if legacy in DEMOTION_SYSTEM_ACTORS:
            return True
        for stem in _SYSTEM_REJECT_STEMS:
            if stem in joined:
                return True
        return False
    except Exception:
        return False


def evaluate_demotion(claim: Mapping[str, Any]) -> dict[str, Any]:
    """Demotion: allowlisted basis only; sustained independent proof needed.

    Allowed bases: sustained thesis impairment or reduced materiality and
    the closely related deterioration/materiality/catalyst kinds below.
    A basis list containing any non-allowlisted entry fails closed.
    Thresholds always come from module constants; claim-supplied minimums
    are ignored. Malformed input returns reasons and never raises.
    """
    try:
        if not isinstance(claim, Mapping):
            return {"allowed": False, "reasons": ["claim_malformed"]}
        basis: Any = claim.get("basis")
        impairment: Any = claim.get("impairment")
        if not isinstance(basis, list) or not basis:
            return {"allowed": False, "reasons": ["demotion_basis_missing"]}
        if not isinstance(impairment, Mapping):
            return {"allowed": False, "reasons": ["impairment_missing"]}
        normalized: list[str] = []
        for entry in basis:
            norm: Optional[str] = _normalize_basis(entry)
            if norm is None:
                return {"allowed": False, "reasons": ["demotion_basis_malformed"]}
            normalized.append(norm)
        unknown: list[str] = [b for b in normalized if b not in DEMOTION_ALLOWED_BASES]
        if unknown:
            if any("stale" in b or "fresh" in b or "gap" in b or "missing" in b
                   for b in unknown):
                return {"allowed": False, "reasons": ["demotion_staleness_insufficient"]}
            return {"allowed": False, "reasons": ["demotion_basis_unknown"]}
        reasons: list[str] = []
        if impairment.get("beneficiary") is not False:
            reasons.append("demotion_beneficiary_attestation_missing")
        source: Any = impairment.get("source")
        if not isinstance(source, str) or not source.strip():
            reasons.append("demotion_source_missing")
        elif _actor_rejected(source):
            reasons.append("demotion_system_source_rejected")
        proponent: Any = impairment.get("proponent")
        if not isinstance(proponent, str) or not proponent.strip():
            reasons.append("demotion_proponent_missing")
        elif _actor_rejected(proponent):
            reasons.append("demotion_system_proponent_rejected")
        reason_code: Any = impairment.get("reason_code")
        if not isinstance(reason_code, str) or not reason_code.strip():
            reasons.append("demotion_reason_code_missing")
        else:
            try:
                code_text: str = unicodedata.normalize("NFKC", reason_code).casefold()
            except Exception:
                code_text = ""
            code_text = "".join(
                ch for ch in code_text if unicodedata.category(ch) != "Cf")
            code_joined: str = "".join(
                ch if ch.isalnum() else "" for ch in code_text)
            if any(s in code_joined for s in _DECAY_REJECT_SUBSTRINGS):
                reasons.append("demotion_reason_code_invalid")
        if impairment.get("sustained") is not True:
            reasons.append("demotion_requires_sustained_impairment")
        days: Any = impairment.get("observation_days")
        obs: Any = impairment.get("observations")
        if (
            not isinstance(days, int)
            or isinstance(days, bool)
            or days < DEMOTION_MIN_OBSERVATION_DAYS
        ):
            reasons.append("demotion_insufficient_duration")
        if (
            not isinstance(obs, int)
            or isinstance(obs, bool)
            or obs < DEMOTION_MIN_OBSERVATIONS
        ):
            reasons.append("demotion_insufficient_observations")
        return {"allowed": len(reasons) == 0, "reasons": reasons}
    except Exception:
        return {"allowed": False, "reasons": ["claim_malformed"]}
