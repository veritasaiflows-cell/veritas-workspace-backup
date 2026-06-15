from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import wf78_500_ticker_reputation_gate as reputation
import wf78_batch_manifest as manifest
import wf78_batch_pipeline as pipeline
import wf78_batch_source_selector as selector
import wf78_batch_tier_c_import_gate as import_gate


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pipeline_args(batch: str) -> argparse.Namespace:
    return argparse.Namespace(
        batch=batch,
        write=False,
        validate=True,
        out=pipeline.DEFAULT_OUT,
        apply=False,
        owner_approval_reference="",
        approval_ref="",
        timeout_seconds=1.0,
        sec_timeout_seconds=1.0,
        retries=0,
        backoff_seconds=0.0,
        min_provider_success_rate=0.9,
        user_agent="Veritas OpenClaw Test",
        skip_provider_probe=True,
        skip_sec_fetch=True,
    )


def import_args(batch: str, apply: bool = False, approval: str = "") -> argparse.Namespace:
    return argparse.Namespace(
        batch=batch,
        apply=apply,
        owner_approval_reference=approval,
        approval_ref="",
    )


def main() -> int:
    errors: list[str] = []

    try:
        manifest.parse_batch_label("300-399")
        errors.append("malformed batch boundary should fail")
    except ValueError:
        pass
    try:
        manifest.parse_batch_label("301-400")
    except ValueError as exc:
        errors.append(f"valid batch rejected: {exc}")

    spec = manifest.batch_spec("301-400")
    expect(spec.candidate_rank_start == 101 and spec.candidate_rank_end == 200, "301-400 candidate ranks must be 101-200", errors)

    source = selector.build_report("301-400")
    summary = source["summary"]
    first = source["candidate_rows"][0]
    last = source["candidate_rows"][-1]
    expect(source["status"] == "ok", "source selector should be ok", errors)
    expect(summary["candidate_count"] == 100, "source selector must return 100 rows", errors)
    expect(first["scaleout_candidate_rank"] == 101, "301-400 first source rank must be 101", errors)
    expect(last["scaleout_candidate_rank"] == 200, "301-400 last source rank must be 200", errors)
    expect(first["target_rank"] == 301, "301-400 first target rank must be 301", errors)

    before_universe = sha256(manifest.DEFAULT_UNIVERSE)
    pipe = pipeline.build_report(pipeline_args("301-400"))
    after_universe = sha256(manifest.DEFAULT_UNIVERSE)
    expect(before_universe == after_universe, "report-only pipeline must not mutate universe-v1.json", errors)
    expect(pipe["status"] in {"ok_with_repair_required", "ok_decision_ready", "ok"}, f"unexpected pipeline status {pipe['status']}", errors)
    expect(pipe["summary"]["apply_mode_used"] is False, "pipeline apply mode must be false by default", errors)
    expect(pipe["summary"]["write_performed"] is False, "pipeline must not write universe by default", errors)

    planned = import_gate.build_report(import_args("301-400"))
    expect(planned["status"] in {"planned", "ok_already_imported_tier_c_only"}, f"planned import gate unexpected status {planned['status']}", errors)
    expect(planned["apply_mode_used"] is False, "planned import gate must not use apply", errors)
    expect(planned["write_performed"] is False, "planned import gate must not write", errors)

    blocked_apply = import_gate.build_report(import_args("301-400", apply=True, approval=""))
    expect(blocked_apply["status"] == "blocked", "apply without approval must block", errors)
    expect(blocked_apply["write_performed"] is False, "blocked apply must not write", errors)

    rep = reputation.build_report(argparse.Namespace())
    expect(rep["status"] == "ok", "reputation gate should remain ok", errors)
    labels = {row["batch_label"]: row for row in rep["batch_plan"]}
    expect("301-400" in labels, "reputation batch plan must include 301-400", errors)
    expect(rep["summary"]["row_count"] == 500, "reputation gate must keep 500 rows", errors)
    expect(rep["summary"]["current_baseline_count"] in {200, 300, 400, 500}, "baseline count must stay supported", errors)

    if errors:
        print("wf78_batch_pipeline_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf78_batch_pipeline_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
