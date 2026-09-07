#!/usr/bin/env python3
"""Focused tests for interactive_training_builder.py."""
from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path

import interactive_training_builder as builder


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_sample_module_validates() -> None:
    module = builder.build_sample_module()
    errors = builder.validate_module(module)
    assert_true(errors == [], f"expected clean sample module, got {errors}")
    assert_true(module["authority_boundary"]["internal_training_only"] is True, "internal training flag missing")
    for key in builder.BLOCKED_AUTHORITY_FLAGS:
        assert_true(module["authority_boundary"][key] is False, f"blocked flag not false: {key}")


def test_html_runtime_markers() -> None:
    module = builder.build_sample_module()
    html_text = builder.render_html(module)
    errors = builder.validate_outputs(html_text, module)
    assert_true(errors == [], f"expected clean HTML validation, got {errors}")
    for marker in [
        "localStorage",
        "downloadEvents",
        "reviewed_boundary",
        "aria-live=\"polite\"",
        "ArrowRight",
        "LMSInitialize",
        "localLedgerEnabled",
    ]:
        assert_true(marker in html_text, f"missing marker {marker}")


def test_scorm_manifest_and_zip() -> None:
    module = builder.build_sample_module()
    html_text = builder.render_html(module)
    xapi_seed = builder.seed_xapi_statements(module)
    manifest = builder.render_scorm_manifest(module)
    assert_true("<manifest" in manifest, "SCORM manifest missing root")
    assert_true("index.html" in manifest, "SCORM manifest missing launch file")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "sample.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr("index.html", html_text)
            package.writestr("module.json", json.dumps(module))
            package.writestr("xapi-seed.json", json.dumps(xapi_seed))
            package.writestr("imsmanifest.xml", manifest)
        with zipfile.ZipFile(path) as package:
            names = set(package.namelist())
        assert_true({"index.html", "module.json", "xapi-seed.json", "imsmanifest.xml"}.issubset(names), "zip missing files")


def test_build_manifest_counts() -> None:
    manifest = builder.build(write=False)
    assert_true(manifest["status"] == "ok", f"manifest not ok: {manifest}")
    assert_true(manifest["counts"]["modules"] == 5, "builder should produce sample, HVAC, SEC, OTEL, and OpenClaw Day 1 modules")
    assert_true(manifest["counts"]["interactions"] >= 39, "modules should include practice interactions across domains")
    assert_true(manifest["counts"]["components"] >= 9, "component library should expose reusable authoring parts")
    assert_true(manifest["capabilities"]["xapi_style_events"] is True, "xAPI capability missing")
    assert_true(manifest["capabilities"]["local_xapi_ledger_optional"] is True, "local xAPI ledger capability missing")
    assert_true(manifest["capabilities"]["scorm_runtime_api_adapter"] is True, "SCORM runtime adapter missing")
    assert_true(manifest["capabilities"]["scorm_local_smoke_validator"] is True, "SCORM smoke capability missing")
    assert_true(manifest["capabilities"]["authoring_checklist"] is True, "authoring checklist capability missing")
    assert_true(manifest["capabilities"]["component_library"] is True, "component library capability missing")
    assert_true(manifest["capabilities"]["external_lms_lrs_configured"] is False, "external LRS must remain false")


def test_hvac_module_conversion() -> None:
    module = builder.build_hvac_module()
    errors = builder.validate_module(module)
    assert_true(errors == [], f"expected clean HVAC module, got {errors}")
    assert_true(len(module["interactions"]) >= 15, "HVAC module should include source simulations plus checks")
    assert_true(module["authority_boundary"]["customer_outreach_approved"] is False, "outreach must remain blocked")
    assert_true("source_stack" in module, "source stack pointer missing")


def test_sec_evidence_module_boundaries() -> None:
    module = builder.build_sec_evidence_module()
    errors = builder.validate_module(module)
    assert_true(errors == [], f"expected clean SEC module, got {errors}")
    assert_true(len(module["lessons"]) >= 3, "SEC module should cover evidence, environment, and handoff")
    assert_true(len(module["interactions"]) >= 9, "SEC module should include enough practice checks")
    for key in [
        "live_sec_retrieval_approved",
        "venv_rebuild_approved",
        "portfolio_canon_mutation_approved",
        "trade_account_action_approved",
        "capital_deployment_approved",
    ]:
        assert_true(module["authority_boundary"][key] is False, f"SEC authority must remain false: {key}")
    html_text = builder.render_html(module)
    assert_true("SEC Evidence Review Practice Lab" in html_text, "SEC module title missing from HTML")
    assert_true("sec_env_audit_validator.py" in html_text, "SEC environment validator command missing")
    assert_true("\\`python scripts" in html_text, "template-literal command text should be escaped")


def test_otel_proof_validator_module_boundaries() -> None:
    module = builder.build_otel_proof_validator_module()
    errors = builder.validate_module(module)
    assert_true(errors == [], f"expected clean OTEL module, got {errors}")
    assert_true(len(module["lessons"]) >= 3, "OTEL module should cover proof, windows, and boundaries")
    assert_true(len(module["interactions"]) >= 10, "OTEL module should include enough practice checks")
    for key in [
        "collector_config_mutation_approved",
        "runtime_config_mutation_approved",
        "cron_schedule_mutation_approved",
        "telemetry_capture_depth_expansion_approved",
        "external_telemetry_export_approved",
        "raw_prompt_tool_payload_capture_approved",
        "finance_canon_portfolio_mutation_approved",
        "paper_live_account_action_approved",
    ]:
        assert_true(module["authority_boundary"][key] is False, f"OTEL authority must remain false: {key}")
    html_text = builder.render_html(module)
    assert_true("OTEL Proof Validator Practice Lab" in html_text, "OTEL module title missing from HTML")
    assert_true("otel_ops_control.py" in html_text, "OTEL control command missing")
    assert_true("tmp\\\\otel-ops-control.json" in html_text, "OTEL control packet path missing")
    assert_true("collector config edits" in html_text, "OTEL boundary prompt missing")


def test_openclaw_day1_module_boundaries() -> None:
    module = builder.build_openclaw_day1_module()
    errors = builder.validate_module(module)
    assert_true(errors == [], f"expected clean OpenClaw Day 1 module, got {errors}")
    assert_true(len(module["lessons"]) >= 2, "Day 1 should teach parts and inspect-only limits")
    assert_true(len(module["interactions"]) >= 5, "Day 1 should include enough practice checks")
    assert_true(any(item.get("type") == "screen_recording" for item in module["interactions"]), "Day 1 should include a Control UI capture card")
    for key in [
        "runtime_config_mutation_approved",
        "channel_expansion_approved",
        "gateway_update_approved",
        "pairing_or_allowlist_mutation_approved",
    ]:
        assert_true(module["authority_boundary"][key] is False, f"Day 1 authority must remain false: {key}")
    html_text = builder.render_html(module)
    assert_true("OpenClaw Day 1: Gateway, Session, and Control UI" in html_text, "Day 1 title missing from HTML")
    assert_true("127.0.0.1:18789" in html_text, "Control UI bind address missing")
    clip = [item for item in module["interactions"] if item.get("type") == "screen_recording"][0]
    assert_true(clip.get("walkthrough_src") == "walkthroughs/openclaw-day1.html", "Day 1 should embed the teaching walkthrough")
    assert_true("walkthrough-frame" in html_text, "Day 1 HTML should embed the walkthrough iframe")
    assert_true("You do not record anything" in html_text, "Day 1 should tell the learner not to record")


def test_authoring_resources_render() -> None:
    library = builder.component_library()
    checklist = builder.render_authoring_checklist(library)
    library_md = builder.render_component_library_md(library)
    assert_true(library["status"] == "ok", "component library should be ok")
    assert_true(len(library["components"]) >= 9, "component library should list reusable parts")
    assert_true("scenario" in checklist, "authoring checklist should mention interaction types")
    assert_true("interactive_training_scorm_smoke_validator.py" in checklist, "authoring checklist should include SCORM proof")
    assert_true("Boundary Acknowledgement" in library_md, "component library markdown should include boundary component")


def test_sample_module_screen_recording() -> None:
    module = builder.build_sample_module()
    clips = [item for item in module["interactions"] if item.get("type") == "screen_recording"]
    assert_true(len(clips) == 1, f"sample module should include one screen_recording, got {len(clips)}")
    assert_true(len(clips[0].get("capture_hint", "")) >= 10, "screen_recording needs a capture_hint")
    errors = builder.validate_module(module)
    assert_true(errors == [], f"expected clean sample module, got {errors}")


def test_screen_recording_html_player() -> None:
    module = builder.build_sample_module()
    html_text = builder.render_html(module)
    for marker in ["media-card", "Mark clip reviewed", "prefers-color-scheme: dark"]:
        assert_true(marker in html_text, f"missing marker {marker}")


def test_screen_recording_rejects_remote_src() -> None:
    module = builder.build_sample_module()
    for item in module["interactions"]:
        if item.get("type") == "screen_recording":
            item["video_src"] = "https://example.com/clip.mp4"
    errors = builder.validate_module(module)
    assert_true(any("screen_recording" in error for error in errors), f"remote video_src should be rejected, got {errors}")


def main() -> int:
    tests = [
        test_sample_module_validates,
        test_sample_module_screen_recording,
        test_screen_recording_html_player,
        test_screen_recording_rejects_remote_src,
        test_html_runtime_markers,
        test_scorm_manifest_and_zip,
        test_build_manifest_counts,
        test_hvac_module_conversion,
        test_sec_evidence_module_boundaries,
        test_otel_proof_validator_module_boundaries,
        test_openclaw_day1_module_boundaries,
        test_authoring_resources_render,
    ]
    for test in tests:
        test()
    print(json.dumps({"status": "ok", "tests": len(tests)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
