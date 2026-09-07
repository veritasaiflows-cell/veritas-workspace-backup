"""Coherent bounded acquisition and pure v1 reference-evidence assembly.

The deterministic worker is a killable local Python process, NOT an agent.
No providers, policy admission, ledger writes, output publication or scheduling.
Production entry uses the fixed canonical origin; synthetic entry stays marked
non-production. Orchestration MUST require origin/provenance binding separately.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import finance_sql_canon_access as canon
from phase3f_external_canary_approval import canonical_json_bytes, strict_canonical_evidence_json_object
from phase3g_coherent_reference_read import _sql_read_session
from phase3g_safe_capture import Capture, safe_fd

ROOT = Path(__file__).resolve().parents[1]
DATABASE = "state/finance/finance-canon.sqlite"
_SEAL = object()
_MAX_PACKAGE = 20 * 1024 * 1024
# Reaping a killed worker must not borrow from an already-consumed deadline,
# or a loaded host reports worker_termination_unconfirmed for a worker that
# did in fact die. This floor is the 1s reserve _run_worker documents.
_CLEANUP_RESERVE_SECONDS = 1.0


class ReferenceInputError(RuntimeError):
    pass


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _binding(evidence,provenance,scope,capture,expiry,production):
    return _sha(canonical_json_bytes({"evidence":_sha(evidence),"provenance":_sha(provenance),
        "scope":_sha(scope),"capture":_sha(capture),"expiry":expiry,"production":production}))


@dataclass(frozen=True)
class _BoundCapture:
    raw: bytes
    sha256: str
    expires_monotonic: float
    production_origin: bool
    _seal: object = field(repr=False, compare=False)

    def _rows(self):
        if self._seal is not _SEAL or _sha(self.raw) != self.sha256:
            raise ReferenceInputError("capture_binding_invalid")
        if time.monotonic() >= self.expires_monotonic:
            raise ReferenceInputError("capture_expired")
        value = strict_canonical_evidence_json_object(self.raw, maximum_bytes=_MAX_PACKAGE)
        if value.get("production_origin") is not self.production_origin:
            raise ReferenceInputError("capture_origin_invalid")
        if value.get("expires_monotonic") != self.expires_monotonic:
            raise ReferenceInputError("capture_expiry_binding_invalid")
        return value


@dataclass(frozen=True)
class ReferenceInputs:
    evidence: bytes
    provenance: bytes
    scope: bytes
    expires_monotonic: float
    production_origin: bool
    captured_rows: bytes
    binding_sha256: str
    _seal: object = field(repr=False, compare=False)

    def verify(self, *, require_production: bool = True):
        if self._seal is not _SEAL or time.monotonic() >= self.expires_monotonic:
            raise ReferenceInputError("reference_inputs_untrusted_or_expired")
        if self.binding_sha256 != _binding(self.evidence,self.provenance,self.scope,self.captured_rows,
                                           self.expires_monotonic,self.production_origin):
            raise ReferenceInputError("reference_inputs_binding_invalid")
        manifest = strict_canonical_evidence_json_object(self.provenance, maximum_bytes=_MAX_PACKAGE)
        evidence = strict_canonical_evidence_json_object(self.evidence, maximum_bytes=10*1024*1024)
        scope = strict_canonical_evidence_json_object(self.scope, maximum_bytes=10*1024*1024)
        if (manifest["evidence_sha256"] != _sha(self.evidence)
                or manifest["scope_payload_sha256"] != _sha(self.scope)
                or evidence["scope_payload_sha256"] != _sha(self.scope)
                or manifest["scope_fingerprint"] != evidence["scope_fingerprint"]
                or manifest["production_origin"] is not self.production_origin
                or manifest["canonical_capture_sha256"] != _sha(self.captured_rows)
                or (require_production and not self.production_origin)):
            raise ReferenceInputError("reference_inputs_binding_invalid")
        canon.verify_dynamic_entitlement_payload(scope, evidence["scope_fingerprint"])
        if tuple(evidence["tickers"]) != tuple(r["ticker"] for r in scope["members"]):
            raise ReferenceInputError("reference_inputs_scope_mismatch")
        return manifest

    def _scope_for_execution(self, *, require_production: bool = True):
        """Rehydrate the exact selected scope; no second membership selection."""
        self.verify(require_production=require_production)
        rows = strict_canonical_evidence_json_object(self.captured_rows, maximum_bytes=_MAX_PACKAGE)
        payload = rows["scope"]
        if canonical_json_bytes(payload) != self.scope:
            raise ReferenceInputError("reference_inputs_scope_mismatch")
        identities = {k:canon.UniverseMembershipRecord(**v) for k,v in rows["identities"].items()}
        tickers = [m["ticker"] for m in payload["members"]]
        scope = canon.DynamicEntitlementScope(
            source=payload["source"], memberships={t:identities[t] for t in tickers},
            identities=identities, aliases=rows["aliases"], fingerprint=payload["fingerprint"],
            tier_breakdown=payload["tier_breakdown"], integrity_breaches=tuple(payload["integrity_breaches"]),
            envelope_name=payload["envelope_name"], envelope_count=payload["envelope_count"],
            overflow_tickers=tuple(payload["overflow_tickers"]), eligibility_debt=tuple(payload["eligibility_debt"]))
        if canonical_json_bytes(scope.payload()) != self.scope:
            raise ReferenceInputError("reference_inputs_scope_mismatch")
        return scope


def _collect(root: Path, deadline: float, production: bool) -> dict:
    """Worker-only: whole operation is contained by its parent deadline."""
    started = datetime.now(timezone.utc).isoformat()
    started_monotonic = time.monotonic()
    capture = Capture(root, deadline)
    # Pin checked canonical ancestors and main-file identity across SQLite open.
    with safe_fd(root, DATABASE, mutable=True) as db_fd:
        pinned = os.fstat(db_fd)
        physical = capture.read(DATABASE, physical=True)
        if physical is None:
            raise ReferenceInputError("canonical_database_missing")
        with canon._captured_source_reads(capture):
            with _sql_read_session(root / DATABASE, timeout_seconds=min(30.0, max(0.000001, deadline-time.monotonic()))) as session:
                opened = os.stat(root / DATABASE)
                if (pinned.st_dev, pinned.st_ino) != (opened.st_dev, opened.st_ino):
                    raise ReferenceInputError("canonical_database_identity_changed")
                rows = session._capture()._verified_rows()
                # Capture source bytes for scoped lineage while SQL transaction
                # is still held. Guard captures are reused, never rehashed later.
                for lines in rows["lineage_rows"].values():
                    for line in lines:
                        capture.read(line["source_artifact_path"])
    capture.check()
    rows.update({
        "database_path": DATABASE,
        "database_sha256": _sha(physical),
        "database_bytes": len(physical),
        "database_observation": capture.observations[DATABASE],
        "source_observations": {k:v for k,v in capture.observations.items() if k != DATABASE},
        "guard_schema": "finance_sql_canon_access_validation.v1",
        "path_validation": "pinned_nonreparse_local_canonical_path",
        "acquisition_started_at_utc": started,
        "acquisition_finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "acquisition_latency_seconds": time.monotonic() - started_monotonic,
        "acquisition_finished_monotonic": time.monotonic(),
        "production_origin": production,
        "expires_monotonic": deadline,
    })
    capture.check()
    return rows


def _run_worker(command: list[str], request: bytes, deadline: float) -> bytes:
    """Fixed production caller only; no shell. Confirm worker exit on timeout.

    communicate timeout covers partial pipe sends as well as computation/file
    stalls. A 1s cleanup reserve is part of the <=30s acquisition budget. Failure
    to confirm termination is a named containment error, never successful output.
    """
    left = deadline-time.monotonic()
    if left <= 1:
        raise ReferenceInputError("acquisition_deadline_exceeded")
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"})
    try:
        try:
            out, _ = proc.communicate(request, timeout=max(0.001, deadline-time.monotonic()-1))
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.communicate(timeout=max(_CLEANUP_RESERVE_SECONDS, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                raise ReferenceInputError("worker_termination_unconfirmed") from None
            if proc.poll() is None:
                raise ReferenceInputError("worker_termination_unconfirmed")
            raise ReferenceInputError("acquisition_timeout_worker_terminated") from None
        if proc.returncode != 0:
            raise ReferenceInputError("acquisition_system_failure")
        if time.monotonic() >= deadline or len(out) > _MAX_PACKAGE:
            raise ReferenceInputError("acquisition_output_bound_exceeded")
        return out
    finally:
        # KeyboardInterrupt/SystemExit also cannot strand a worker.
        if proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=max(_CLEANUP_RESERVE_SECONDS, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                pass  # original exception remains failure, never publishable
        for stream in (proc.stdin,proc.stdout,proc.stderr):
            if stream is not None:
                stream.close()


def assemble(bundle: _BoundCapture) -> ReferenceInputs:
    """Pure serializer: no SQL, providers, file reads/writes, policy or ledger."""
    if type(bundle) is not _BoundCapture:
        raise ReferenceInputError("capture_binding_invalid")
    rows = bundle._rows()
    if rows["database_path"] != DATABASE or rows["publishable"] is not False:
        raise ReferenceInputError("capture_origin_invalid")
    scope = canonical_json_bytes(rows["scope"])
    fingerprint = canon.verify_dynamic_entitlement_payload(rows["scope"], rows["scope_fingerprint"])
    tickers = tuple(m["ticker"] for m in rows["scope"]["members"])
    for key in ("reference_levels", "evidence_freshness", "lineage_rows", "missing_classes"):
        if not set(rows[key]).issubset(tickers):
            raise ReferenceInputError("capture_foreign_ticker")
    lineage = {}
    debt = {t:list(rows["missing_classes"][t]) for t in tickers}
    wanted = {"reference_price_low", "reference_price_high", "reference_invalidation_level"}
    for ticker, lines in rows["lineage_rows"].items():
        fields = [{k:v for k,v in line.items() if k!="scope_key"}
                  for line in lines if line["field_name"] in wanted]
        checks = []
        for line in fields:
            name = line["source_artifact_path"]
            observation = rows["source_observations"].get(name)
            if observation is None:
                raise ReferenceInputError("source_observation_missing")
            expected = str(line["source_artifact_sha256"] or "").lower()
            matches = bool(expected and observation["sha256"] == expected)
            checks.append(dict(path=name, exists=observation["exists"], expected_sha256=expected or None,
                               actual_sha256=observation["sha256"], hash_matches=matches))
        times = [line["source_generated_at_utc"] for line in fields if line["source_generated_at_utc"]]
        ok = (len(fields)==len(wanted) and {f["field_name"] for f in fields}==wanted
              and all(f["source_status"]=="ok" and f["validator_status"]=="ok" for f in fields)
              and all(c["hash_matches"] for c in checks))
        if not ok:
            debt[ticker].append("lineage_not_ready")
        lineage[ticker] = dict(fields=fields, artifact_checks=checks,
            level_as_of_utc=max(times) if times else None,
            source_paths=sorted({f["source_artifact_path"] for f in fields}), lineage_validation_ok=bool(ok))
    value = dict(schema="veritas.phase3f.alert_reference_evidence.v1", status="ok",
        database_path=DATABASE, database_sha256=rows["database_sha256"], scope_fingerprint=fingerprint,
        scope_payload_sha256=_sha(scope), tickers=list(tickers), reference_levels=rows["reference_levels"],
        evidence_freshness=rows["evidence_freshness"], lineage=lineage, errors=[])
    evidence = canonical_json_bytes(value)
    strict_canonical_evidence_json_object(evidence, maximum_bytes=10*1024*1024)
    readset = {k:rows[k] for k in ("scope","identities","aliases","reference_levels","evidence_freshness","lineage_rows")}
    manifest = dict(schema="veritas.phase3g.reference_provenance.v1",
        status="assembled_with_evidence_debt" if any(debt.values()) else "assembled_not_readiness",
        snapshot_semantics="single_sql_read_transaction_plus_captured_source_observations",
        database_path=DATABASE, database_observation=rows["database_observation"],
        path_validation=rows["path_validation"], guard_schema=rows["guard_schema"], session_id=rows["session_id"],
        acquisition_started_at_utc=rows["acquisition_started_at_utc"], acquisition_finished_at_utc=rows["acquisition_finished_at_utc"],
        acquisition_latency_seconds=rows.get("acquisition_latency_seconds"),
        acquisition_finished_monotonic=rows.get("acquisition_finished_monotonic"),
        database_bytes=rows.get("database_bytes"),
        capture_bytes=len(bundle.raw),
        capture_headroom_bytes=_MAX_PACKAGE - len(bundle.raw),
        source_observation_count=len(rows.get("source_observations") or {}),
        scope_fingerprint=fingerprint, scope_payload_sha256=_sha(scope),
        readset_sha256=_sha(canonical_json_bytes(readset)), source_observations=rows["source_observations"],
        missing_classes=debt, evidence_sha256=_sha(evidence), production_origin=bundle.production_origin,
        canonical_capture_sha256=bundle.sha256,
        consumer_missing_behavior="v1_all_or_none_per_ticker_preserved",
        readiness_claimed=False, provider_authority=False)
    provenance = canonical_json_bytes(manifest)
    result = ReferenceInputs(evidence, provenance, scope,
        bundle.expires_monotonic, bundle.production_origin, bundle.raw,
        _binding(evidence,provenance,scope,bundle.raw,bundle.expires_monotonic,bundle.production_origin),_SEAL)
    result.verify(require_production=False)
    return result


def _acquire(root: Path, *, production: bool, timeout_seconds: float = 30,
             max_scope_count: int | None = None,
             package_lifetime_seconds: float = 600) -> ReferenceInputs:
    if (type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds)
            or not 1 < timeout_seconds <= 30):
        raise ReferenceInputError("acquisition_timeout_invalid")
    if (type(package_lifetime_seconds) not in (int,float) or not math.isfinite(package_lifetime_seconds)
            or not 0 < package_lifetime_seconds <= 3600):
        raise ReferenceInputError("acquisition_package_lifetime_invalid")
    if max_scope_count is not None and (
            # Mirrors the policy absolute ceiling without importing policy here;
            # the numeric bound is threaded in by the policy-authorized caller.
            type(max_scope_count) is not int or not 1 <= max_scope_count <= 512):
        raise ReferenceInputError("acquisition_scope_bound_invalid")
    if production and Path(root) != ROOT:
        raise ReferenceInputError("canonical_origin_invalid")
    deadline = time.monotonic()+timeout_seconds
    request = canonical_json_bytes(dict(root=str(root), production=production, deadline=deadline))
    raw = _run_worker([sys.executable,"-B",str(Path(__file__).resolve()),"--worker"], request, deadline)
    acquired_monotonic = time.monotonic()
    if acquired_monotonic >= deadline:
        raise ReferenceInputError("acquisition_deadline_exceeded")
    # Serialization also runs inside the killed worker, not after timeout checks.
    envelope = strict_canonical_evidence_json_object(raw, maximum_bytes=_MAX_PACKAGE)
    if envelope["production_origin"] is not production:
        raise ReferenceInputError("worker_origin_mismatch")
    evidence=canonical_json_bytes(envelope["evidence"])
    provenance=canonical_json_bytes(envelope["provenance"])
    scope=canonical_json_bytes(envelope["scope"])
    capture=canonical_json_bytes(envelope["capture"])
    # Package lifetime is separate from the SQL acquisition timeout: the kill
    # deadline bounds the worker, while the sealed package stays verifiable
    # until acquired_monotonic + package_lifetime_seconds.
    package_expiry = acquired_monotonic+package_lifetime_seconds
    result = ReferenceInputs(evidence,provenance,scope,package_expiry,production,capture,
                             _binding(evidence,provenance,scope,capture,package_expiry,production),_SEAL)
    result.verify(require_production=production)
    if max_scope_count is not None:
        tickers = strict_canonical_evidence_json_object(evidence, maximum_bytes=10*1024*1024)["tickers"]
        if len(tickers) > max_scope_count:
            raise ReferenceInputError("reference_inputs_scope_overflow")
    if time.monotonic() >= deadline:
        raise ReferenceInputError("acquisition_deadline_exceeded")
    return result


def acquire_reference_inputs(*, timeout_seconds: float = 30, max_scope_count: int | None = None,
                             package_lifetime_seconds: float = 600) -> ReferenceInputs:
    """Canonical read-only acquisition; does not enable orchestration/provider work."""
    return _acquire(ROOT, production=True, timeout_seconds=timeout_seconds,
                    max_scope_count=max_scope_count, package_lifetime_seconds=package_lifetime_seconds)


def _worker():
    request = json.loads(sys.stdin.buffer.read(8192))
    root = Path(request["root"])
    if request["production"] and root != ROOT:
        raise ReferenceInputError("canonical_origin_invalid")
    deadline = request["deadline"]
    rows = _collect(root, deadline, request["production"])
    raw = canonical_json_bytes(rows)
    if len(raw)>_MAX_PACKAGE:
        raise ReferenceInputError("capture_size_exceeded")
    inputs = assemble(_BoundCapture(raw,_sha(raw),deadline,request["production"],_SEAL))
    out = canonical_json_bytes(dict(evidence=json.loads(inputs.evidence), provenance=json.loads(inputs.provenance),
                                    scope=json.loads(inputs.scope), production_origin=inputs.production_origin,
                                    capture=json.loads(inputs.captured_rows)))
    if len(out)>_MAX_PACKAGE or time.monotonic()>=deadline:
        raise ReferenceInputError("acquisition_output_bound_exceeded")
    sys.stdout.buffer.write(out)


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        raise SystemExit("private_worker_only")
    try:
        _worker()
    except Exception:
        sys.stderr.write("reference_input_acquisition_failed\n")
        raise SystemExit(1)
