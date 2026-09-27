"""Hermetic safe-capture/full-guard/worker/assembler proofs; no production DB."""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from dataclasses import replace
from contextlib import closing
from pathlib import Path
from unittest import mock

import pytest
import finance_sql_canon_access as canon
import phase3g_recurring_reference_inputs as inputs
from phase3g_safe_capture import Capture, CaptureError
from phase3g_synthetic_fixture import build_fixture


@pytest.fixture
def full(tmp_path):
    root = tmp_path/"fixture"
    return root, build_fixture(root)


def _bundle(root):
    deadline = time.monotonic()+30
    rows = inputs._collect(root, deadline, False)
    raw = inputs.canonical_json_bytes(rows)
    return inputs._BoundCapture(raw,inputs._sha(raw),deadline,False,inputs._SEAL)


def test_full_unmodified_guard_passes_using_captured_bytes(full):
    root, db = full
    capture = Capture(root,time.monotonic()+30)
    with canon._captured_source_reads(capture):
        v = canon.FinanceSqlCanonAccess(db).validate()
    assert v["status"] == "ok", v["errors"]
    assert v["warnings"] == []
    assert v["counts"]["securities"] == 200
    assert len(capture.cache)==2  # baseline hash/json/lineage all use same bytes


def test_pure_assembly_deterministic_full_guard_scope_and_debt(full):
    root, db = full
    bundle = _bundle(root)
    with mock.patch.object(canon, "connect_readonly", side_effect=AssertionError("SQL forbidden")), \
         mock.patch.object(Path, "read_bytes", side_effect=AssertionError("file read forbidden")), \
         mock.patch.object(Path, "write_bytes", side_effect=AssertionError("file write forbidden")), \
         mock.patch.object(subprocess,"Popen",side_effect=AssertionError("worker forbidden")):
        a = inputs.assemble(bundle)
        b = inputs.assemble(bundle)
    assert a == b
    evidence = json.loads(a.evidence)
    scope = json.loads(a.scope)
    assert evidence["tickers"] == ["S000","S001"]
    assert scope["members"][1]["decision_grade_eligible"] is False
    assert scope["eligibility_debt"] == ["S001"]
    assert all(line["lineage_validation_ok"] for line in evidence["lineage"].values())
    # All five canon reference fields, incl. reference_confidence, from the same SQL rows.
    for ticker, line in evidence["lineage"].items():
        names = [f["field_name"] for f in line["fields"]]
        assert len(names) == len(canon.REFERENCE_LEVEL_LINEAGE_FIELDS), ticker
        assert set(names) == canon.REFERENCE_LEVEL_LINEAGE_FIELDS, ticker
        sql_rows = {r["field_name"]: r for r in json.loads(bundle.raw)["lineage_rows"][ticker]}
        for f in line["fields"]:
            src = sql_rows[f["field_name"]]
            assert (f["source_artifact_path"], f["source_artifact_sha256"]) == (
                src["source_artifact_path"], src["source_artifact_sha256"])
    manifest = a.verify(require_production=False)
    assert manifest["database_observation"]["meaning"] == "physical_main_file_observation_only_not_sql_snapshot"
    assert evidence["database_sha256"] == hashlib.sha256(db.read_bytes()).hexdigest()
    assert manifest["snapshot_semantics"] == "single_sql_read_transaction_plus_captured_source_observations"
    with pytest.raises(inputs.ReferenceInputError):
        a.verify()  # synthetic origin cannot become production


def test_complete_worker_acquisition_and_assembly(full):
    root, _ = full
    result = inputs._acquire(root,production=False)
    result.verify(require_production=False)
    assert json.loads(result.evidence)["tickers"] == ["S000","S001"]
    assert result._scope_for_execution(require_production=False).tickers == ("S000","S001")


def test_actual_sealed_consumer_compatibility(full):
    import alert_level_freshness_controller as alert
    from test_tier_entitlement_phase3f_canary import mint
    root,_=full
    assembled=inputs.assemble(_bundle(root))
    scope=assembled._scope_for_execution(require_production=False)
    auth=mint(root,scope=scope,components=("alert_level_freshness",),
              input_hashes={"alert_reference_evidence":hashlib.sha256(assembled.evidence).hexdigest()})
    client,lineage,actual=alert._phase3f_reference_evidence(assembled.evidence,authorization=auth,
                                                        tickers=scope.tickers,allow_missing=True)
    assert actual==hashlib.sha256(assembled.evidence).hexdigest()
    assert client.reference_level("S001").reference_price_low==100
    assert lineage("S001")["lineage_validation_ok"]


@pytest.mark.parametrize("missing",[("reference_levels",),("evidence_freshness",),("lineage_rows",),
                                    ("reference_levels","evidence_freshness","lineage_rows")])
def test_synthetic_missing_classes_preserve_consumer_all_or_none(full,missing):
    import alert_level_freshness_controller as alert
    from test_tier_entitlement_phase3f_canary import mint
    root,_=full
    original=_bundle(root)
    rows=original._rows()
    # Explicit test-only material injection; no production acquisition option.
    mapping={"reference_levels":"reference_level","evidence_freshness":"freshness","lineage_rows":"lineage"}
    for key in missing:
        del rows[key]["S001"]
        rows["missing_classes"]["S001"].append(mapping[key])
    raw=inputs.canonical_json_bytes(rows)
    assembled=inputs.assemble(inputs._BoundCapture(raw,inputs._sha(raw),original.expires_monotonic,False,inputs._SEAL))
    scope=assembled._scope_for_execution(require_production=False)
    auth=mint(root,scope=scope,components=("alert_level_freshness",),input_hashes={"alert_reference_evidence":inputs._sha(assembled.evidence)})
    client,lineage,_=alert._phase3f_reference_evidence(assembled.evidence,authorization=auth,tickers=scope.tickers,allow_missing=True)
    assert client.reference_level("S001") is None
    assert client.evidence_freshness("S001") is None
    assert lineage("S001")["fields"]==[]
    assert json.loads(assembled.evidence)["tickers"]==["S000","S001"]


def test_missing_confidence_lineage_row_is_not_ready(full):
    root,_=full
    original=_bundle(root)
    rows=original._rows()
    rows["lineage_rows"]["S001"]=[r for r in rows["lineage_rows"]["S001"]
                                  if r["field_name"]!="reference_confidence"]
    raw=inputs.canonical_json_bytes(rows)
    assembled=inputs.assemble(inputs._BoundCapture(raw,inputs._sha(raw),original.expires_monotonic,False,inputs._SEAL))
    line=json.loads(assembled.evidence)["lineage"]["S001"]
    assert line["lineage_validation_ok"] is False
    assert "reference_confidence" not in {f["field_name"] for f in line["fields"]}
    assert "lineage_not_ready" in json.loads(assembled.provenance)["missing_classes"]["S001"]


@pytest.mark.skipif(os.name!="nt",reason="Windows native junction proof")
def test_actual_windows_reparse_component_zero_content_reads(tmp_path):
    import _winapi
    target=tmp_path/"target"
    target.mkdir()
    (target/"source").write_bytes(b"synthetic")
    link=tmp_path/"junction"
    _winapi.CreateJunction(str(target),str(link))
    try:
        with mock.patch("phase3g_safe_capture.os.read",side_effect=AssertionError("content accessed")) as read:
            with pytest.raises(CaptureError,match="source_path_invalid"):
                Capture(tmp_path,time.monotonic()+10).read("junction/source")
        read.assert_not_called()
    finally:
        link.rmdir()


@pytest.mark.skipif(os.name!="nt",reason="Windows sharing-mode proof")
def test_checked_windows_source_and_ancestor_cannot_be_replaced(tmp_path):
    from phase3g_safe_capture import safe_fd
    parent=tmp_path/"source-dir"; parent.mkdir()
    path=parent/"source"; path.write_bytes(b"original")
    with safe_fd(tmp_path,"source-dir/source") as fd:
        with pytest.raises(OSError):
            path.write_bytes(b"changed")
        with pytest.raises(OSError):
            parent.rename(tmp_path/"moved")
        assert os.read(fd,20)==b"original"


def test_failed_worker_and_malformed_stdout_never_return_inputs(full):
    root,_=full
    with mock.patch.object(inputs,"_run_worker",return_value=b"{bad"):
        with pytest.raises((ValueError,RuntimeError)):
            inputs._acquire(root,production=False)


@pytest.mark.parametrize("mutation",["foreign","nan","wrong_database","missing_observation"])
def test_synthetic_bad_assembly_material_rejected(full,mutation):
    root,_=full
    original=_bundle(root)
    rows=original._rows()
    if mutation=="foreign": rows["reference_levels"]["FOREIGN"]={}
    if mutation=="nan": rows["reference_levels"]["S000"]["reference_price_low"]=float("nan")
    if mutation=="wrong_database": rows["database_path"]="outside.sqlite"
    if mutation=="missing_observation": rows["source_observations"]={}
    with pytest.raises((ValueError,RuntimeError)):
        raw=inputs.canonical_json_bytes(rows)
        inputs.assemble(inputs._BoundCapture(raw,inputs._sha(raw),original.expires_monotonic,False,inputs._SEAL))


@pytest.mark.parametrize("bad", ["../outside", "/outside", "C:\\outside", "C:outside", "\\\\host\\share\\x", "a/../b", "a//b", "a/./b", "a:ads", "a. ", "NUL", "a/CON.json"])
def test_unsafe_paths_zero_content_reads(tmp_path,bad):
    capture=Capture(tmp_path,time.monotonic()+10)
    with mock.patch("phase3g_safe_capture.os.read",side_effect=AssertionError("content accessed")) as read:
        with pytest.raises(CaptureError):
            capture.read(bad)
    read.assert_not_called()


def test_symlink_zero_content_reads(tmp_path):
    target=tmp_path/"target"
    target.write_bytes(b"secret synthetic")
    link=tmp_path/"link"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {type(exc).__name__}")
    with mock.patch("phase3g_safe_capture.os.read",side_effect=AssertionError("content accessed")) as read:
        with pytest.raises((CaptureError,OSError)):
            Capture(tmp_path,time.monotonic()+10).read("link")
    read.assert_not_called()


def test_missing_cached_and_replacement_cannot_change_observed_bytes(tmp_path):
    file=tmp_path/"source.json"
    capture=Capture(tmp_path,time.monotonic()+10)
    assert capture.read("missing.json") is None
    file.write_bytes(b"old")
    assert capture.read("source.json")==b"old"
    file.write_bytes(b"new")
    assert capture.read("source.json")==b"old"
    assert capture.observations["source.json"]["sha256"]==hashlib.sha256(b"old").hexdigest()


def test_source_size_limit_and_permission_failure(tmp_path):
    path=tmp_path/"large"
    with path.open("wb") as f:
        f.truncate(10*1024*1024+1)
    with mock.patch("phase3g_safe_capture.os.read") as read:
        with pytest.raises(CaptureError,match="size_exceeded"):
            Capture(tmp_path,time.monotonic()+10).read("large")
    read.assert_not_called()
    with mock.patch("phase3g_safe_capture.safe_fd",side_effect=PermissionError()):
        with pytest.raises(CaptureError,match="system_failure"):
            Capture(tmp_path,time.monotonic()+10).read("large")


@pytest.mark.parametrize("stage", ["file", "sql", "serialization", "partial_pipe"])
def test_deadline_kills_stalled_worker_and_reaps_it(tmp_path,stage):
    # Deterministic wait injection, not a timer/reminder or production hook.
    pidfile=tmp_path/"pid"
    code="import os,sys,threading; from pathlib import Path; Path(sys.argv[1]).write_text(str(os.getpid())); "
    if stage=="sql":
        code += "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x WHERE n<1000000000) SELECT sum(n) FROM x').fetchone()"
    elif stage=="file":
        # Actual blocking ReadFile/read syscall, with an open writer and no
        # data. The process must be killed; Python thread cancellation cannot
        # release this call. It models a stalled descriptor read in capture.
        code += "r,w=os.pipe(); os.read(r,1)"
    else:
        if stage=="partial_pipe":
            code += "sys.stdout.write('{'); sys.stdout.flush(); "
        code += "threading.Event().wait()"
    processes=[]
    original=inputs.subprocess.Popen
    def remember(*args,**kwargs):
        p=original(*args,**kwargs); processes.append(p); return p
    started=time.monotonic()
    with mock.patch.object(inputs.subprocess,"Popen",remember):
        with pytest.raises(inputs.ReferenceInputError,match="timeout_worker_terminated"):
            inputs._run_worker([sys.executable,"-B","-c",code,str(pidfile)],b"{}",started+2.5)
    assert pidfile.exists()
    assert processes[0].poll() is not None
    assert all(s.closed for s in (processes[0].stdin,processes[0].stdout,processes[0].stderr))
    assert time.monotonic()-started < 3.5


def test_full_guard_failure_returns_no_package(full):
    root, db=full
    with closing(sqlite3.connect(db)) as c:
        c.execute("UPDATE evidence_status SET customer_output_allowed=1 WHERE ticker='S000'")
        c.commit()
    with pytest.raises(inputs.ReferenceInputError,match="acquisition_system_failure"):
        inputs._acquire(root,production=False)


def test_canonical_origin_denied_before_worker(full):
    root,_=full
    with mock.patch.object(inputs,"_run_worker") as worker:
        with pytest.raises(inputs.ReferenceInputError,match="canonical_origin_invalid"):
            inputs._acquire(root,production=True)
    worker.assert_not_called()


def test_bundle_tamper_and_output_binding(full):
    root,_=full
    bundle=_bundle(root)
    for b in (replace(bundle,raw=b"{}"),replace(bundle,_seal=object()),replace(bundle,expires_monotonic=0),
              replace(bundle,expires_monotonic=bundle.expires_monotonic+999),replace(bundle,production_origin=True)):
        with pytest.raises(inputs.ReferenceInputError): inputs.assemble(b)
    result=inputs.assemble(bundle)
    manifest=json.loads(result.provenance); manifest["path_validation"]="forged"
    for r in (replace(result,scope=b"{}"), replace(result,evidence=b"{}"), replace(result,production_origin=True),
              replace(result,provenance=inputs.canonical_json_bytes(manifest)),
              replace(result,expires_monotonic=result.expires_monotonic+999)):
        with pytest.raises((inputs.ReferenceInputError,KeyError,ValueError)):
            r.verify(require_production=False)


def test_wal_file_hash_does_not_identify_snapshot(full):
    root,db=full
    with closing(sqlite3.connect(db)) as writer:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        before=hashlib.sha256(db.read_bytes()).hexdigest()
        writer.execute("UPDATE securities SET name='changed synthetic' WHERE ticker='S000'")
        writer.commit()
        after=hashlib.sha256(db.read_bytes()).hexdigest()
        assert before==after
        assert writer.execute("SELECT name FROM securities WHERE ticker='S000'").fetchone()[0]=='changed synthetic'
