#!/usr/bin/env python3
"""Focused telemetry summary consumer tests (wiring, adversarial, learning-stale, bounded-read)."""
from __future__ import annotations
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from otel_ops_control import build_telemetry_context, load_telemetry_summary, build_actions, _bounded_read_text, TELEMETRY_SUMMARY_MAX_BYTES
from otel_learning_loop import revalidate_telemetry_context, otel_health_summary, build_recommendations
def expect(c, m, e):
    if not c:
        e.append(m)
def main():
    e = []
    with TemporaryDirectory() as tmp:
        td = Path(tmp)
        def w(o, n):
            p = td / n
            p.write_text(json.dumps(o), encoding="utf-8")
            return p
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        probe = {"schema": "veritas.otel_runtime_metadata_probe.v1", "generated_at_utc": now, "status": "ok", "validation": {"status": "ok"}, "forbidden_findings": [], "blocked_markers": {}, "summary": {"runtime_metadata_observed": True, "allowed_field_count": 5, "raw_content_marker_count": 0, "secret_or_header_marker_count": 0, "metadata_depth_approved_enabled": False, "file_exporter_observed": True, "debug_log_observed": False, "runtime_metadata_learning_ready": True}}
        depth = {"schema": "veritas.otel_token_cost_metadata_depth_owner_packet.v1", "generated_at_utc": now, "status": "owner_decision_pending", "validation": {"status": "warning"}, "patch_would_change_token_or_cost_coverage": False}
        pp, dp = w(probe, "p.json"), w(depth, "d.json")
        ctx = build_telemetry_context(pp, dp)
        expect(ctx["status"] == "ok", "ctx ok", e)
        acts = build_actions({"event_count": 1}, {"binds_loopback_4318": True}, {"status": "ok"}, {"status": "ok"}, ctx)
        expect(any(a["id"] == "otel_telemetry_summary_fresh" for a in acts), "fresh wired to actions", e)
        fresh = [a for a in acts if a["id"] == "otel_telemetry_summary_fresh"]
        expect(fresh and "allowed_fields=5" in str(fresh[0].get("rationale", "")) and "owner_gated_depth_no_approval" in str(fresh[0].get("rationale", "")), "payload wiring uses whitelisted scalars + owner-gated note", e)
        ctxm = build_telemetry_context(td / "missing.json", dp)
        actsm = build_actions({}, {}, {"status": "ok"}, {}, ctxm)
        expect(any(a["id"] == "otel_telemetry_summary_stale_or_missing" for a in actsm), "missing wired fail-closed", e)
        bad_depth = dict(depth)
        bad_depth["summary"] = {"x": 1}
        expect("depth_summary_unexpected" in str(load_telemetry_summary(w(bad_depth, "bd.json"), "veritas.otel_token_cost_metadata_depth_owner_packet.v1")["reason"]), "depth summary rejected (NO summary object)", e)
        clean_depth = dict(depth)
        clean_depth["status"] = "ok"
        expect("depth_status_not_owner_gated" in str(load_telemetry_summary(w(clean_depth, "cd.json"), "veritas.otel_token_cost_metadata_depth_owner_packet.v1")["reason"]), "depth never clean", e)
        # bounded-read regression: requested size must be limit+1
        seen = {}
        orig_open = io.open if hasattr(io, "open") else open
        class Spy(io.BufferedReader):
            pass
        import builtins
        real_open = builtins.open
        def spy_open(p, mode="r", *a, **k):
            fh = real_open(p, mode, *a, **k)
            if "b" in str(mode):
                outer = fh
                class W:
                    def __init__(self, f):
                        self._f = f
                    def read(self, n=-1):
                        seen["n"] = n
                        return self._f.read(n)
                    def __enter__(self):
                        self._f.__enter__()
                        return self
                    def __exit__(self, *x):
                        return self._f.__exit__(*x)
                    def __getattr__(self, k):
                        return getattr(self._f, k)
                return W(outer)
            return fh
        builtins.open = spy_open
        try:
            load_telemetry_summary(pp, "veritas.otel_runtime_metadata_probe.v1")
        finally:
            builtins.open = real_open
        expect(seen.get("n") == TELEMETRY_SUMMARY_MAX_BYTES + 1, "bounded read requests limit+1, got " + str(seen.get("n")), e)
        src = Path("scripts/otel_ops_control.py").read_text(encoding="utf-8") if Path("scripts/otel_ops_control.py").exists() else ""
        # scratch-patched source check happens in runner; here check loaded module source
        import otel_ops_control as O
        import inspect
        expect(".read(limit + 1)" in inspect.getsource(O._bounded_read_text), "bounded stream read limit+1 present", e)
        expect("read_bytes()" not in inspect.getsource(O.load_telemetry_summary), "no unbounded read_bytes in loader", e)
        expect('errors="ignore"' not in inspect.getsource(O.load_telemetry_summary), "strict decoding only", e)
        emb = {"runtime_probe": {"present": True, "fresh": True, "valid": True, "reason": "fresh_valid", "generated_at_utc": now, "scalars": probe["summary"]}, "token_depth": {"present": True, "fresh": True, "valid": True, "reason": "fresh_valid_owner_gated", "generated_at_utc": now, "status": "owner_decision_pending", "owner_gated": True}}
        rv = revalidate_telemetry_context(emb)
        expect(rv["valid"] is True, "learning fresh valid", e)
        emb2 = {"runtime_probe": dict(emb["runtime_probe"]), "token_depth": dict(emb["token_depth"])}
        emb2["runtime_probe"] = dict(emb["runtime_probe"])
        emb2["runtime_probe"]["generated_at_utc"] = "2020-01-01T00:00:00Z"
        expect("stale" in str(revalidate_telemetry_context(emb2)["reason"]), "learning stale revalidated at consume time", e)
        h = otel_health_summary({"telemetry_context": emb, "status": "ok"}, {"trend_indicators": {}})
        expect(h["telemetry_fresh_valid"] is True, "health wires telemetry", e)
        recs = build_recommendations({"token_coverage_ratio": 1.0, "cost_coverage_ratio": 1.0}, {}, h, {}, {"cron": {}, "workflow_advancement": {}}, {}, {})
        expect(any(r["id"] == "otel_token_depth_owner_gated" for r in recs), "owner-gated rec, not approval", e)
        expect(not any("approve" in str(r.get("decision", "")).lower() and "gated" not in str(r.get("decision", "")).lower() for r in recs if r["id"] == "otel_token_depth_owner_gated"), "no approval inference", e)
        hm = otel_health_summary({}, {})
        recm = build_recommendations({}, {}, hm, {}, {}, {}, {})
        expect(any(r["id"] == "otel_telemetry_stale_or_missing" for r in recm), "stale rec", e)
        hp = dict(probe)
        hp["summary"] = dict(probe["summary"])
        hp["summary"]["runtime_metadata_observed"] = 1
        expect("whitelist_type_invalid" in str(load_telemetry_summary(w(hp, "hp.json"), probe["schema"])["reason"]), "bool strict", e)
    if e:
        print("telemetry_consumer_tests_failed")
        [print("- " + x) for x in e]
        return 1
    print("telemetry_consumer_tests_passed")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
