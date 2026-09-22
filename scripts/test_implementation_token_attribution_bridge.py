from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "implementation_token_attribution_bridge.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("implementation_token_attribution_bridge", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_source_receipt(register: Path, lane: dict, runtime: dict, module) -> None:
    """Seed the same bounded receipt shape issued by the lane importer."""
    body = {
        "source_type": runtime["token_attribution_source"],
        "source_run_id": runtime["run_id"],
        "source_snapshot_fingerprint": runtime["source_snapshot_fingerprint"],
        "session_ref_hash": runtime["session_ref_hash"],
        "lane_id": lane["lane_id"],
        "parent_job_id": runtime["parent_job_id"],
        "phase": runtime["phase"],
        "attempt_correlation_hash": runtime["attempt_correlation"]["key_hash"],
        "model_path": runtime["model_path"],
        "token_attribution_source": runtime["token_attribution_source"],
        "input_token_semantics": runtime["input_token_semantics"],
        "source_input_total_tokens": runtime["source_input_total_tokens"],
        "source_total_tokens_fresh": True,
        "tokens": {
            key: runtime[key]
            for key in ("input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens", "total_tokens")
        },
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"))
    receipt_id = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    binding_id = hashlib.sha256(
        "|".join((body["source_type"], body["source_run_id"])).encode("utf-8")
    ).hexdigest()
    runtime["usage_source_receipt_id"] = receipt_id
    runtime["usage_source_receipt_schema"] = "veritas.model_usage_source_receipt.v1"
    write_json(register.with_suffix(".usage-receipts.json"), {
        "schema": "veritas.model_usage_source_receipts.v1",
        "metadata_only": True,
        "receipts": [{
            "schema": "veritas.model_usage_source_receipt.v1",
            "receipt_id": receipt_id,
            "source_binding_contract_version": "veritas.usage_source_binding.v2",
            "source_binding_id": binding_id,
            "verified_at_utc": module.utc_now(),
            **body,
        }],
    })


def seed(root: Path, module, *, gap_count: int = 2, stamped: bool = False) -> tuple[Path, Path, Path]:
    module.ROOT = root
    module.TMP = root / "tmp"
    token_usage = module.TMP / "token-usage-ledger-current.json"
    register = module.TMP / "concurrent-lane-register.json"
    coding = module.TMP / "coding-outcome-ledger-current.json"
    write_json(token_usage, {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "implementation_token_event_count": 1 if stamped else 0,
            "implementation_token_gap_count": gap_count,
        },
        "validation": {"status": "ok"},
        "implementation_token_gaps": [
            {"lane_id": "WF88::one", "workflow_id": "WF88", "model_path": "openai/gpt-5.5"},
            {"lane_id": "WF74::two", "workflow_id": "WF74", "model_path": "openai/gpt-5.4"},
        ][:gap_count],
    })
    runtime = {
        "task_name": "wf88-one",
        "model_path": "openai/gpt-5.5",
        "model_provider": "openai",
    }
    if stamped:
        runtime.update({
            "run_id": "run-1",
            "session_ref_hash": "session-ref-1",
            "source_snapshot_fingerprint": "snapshot-1",
            "parent_job_id": "parent-1",
            "phase": "implementation",
            "attempt_correlation": {"key_version": "v1", "key_hash": "attempt-correlation-1"},
            "input_token_semantics": "exclusive_cached",
            "input_tokens": 10,
            "cached_input_tokens": 20,
            "cache_write_tokens": 0,
            "output_tokens": 5,
            "total_tokens": 35,
            "token_attribution_source": "codex_native_rollout_jsonl",
            "source_input_total_tokens": 30,
            "source_total_tokens_fresh": True,
            "usage_credit_status": "creditable",
            "usage_creditable": True,
        })
    register_payload = {
        "lanes": [
            {
                "lane_id": "WF88::one",
                "workflow_id": "WF88",
                "workstream_id": "one",
                "status": "complete",
                "ended_at_utc": module.utc_now(),
                "completed_at_utc": module.utc_now(),
                "runtime": runtime,
            }
        ],
        "validation": {"status": "ok"},
    }
    write_json(register, register_payload)
    if stamped:
        write_source_receipt(register, register_payload["lanes"][0], runtime, module)
        # ``write_source_receipt`` adds the opaque receipt id to runtime after
        # the initial fixture write; persist that metadata-only link too.
        write_json(register, register_payload)
    write_json(coding, {"status": "ok", "generated_at_utc": module.utc_now(), "validation": {"status": "ok"}})
    return token_usage, register, coding


def test_bridge_blocks_on_missing_post_cutoff_implementation_token_stamps() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=2)
        payload = module.build_payload(token_usage, register, coding)

        assert payload["status"] == "blocked"
        assert payload["validation"]["status"] == "blocked"
        assert payload["summary"]["implementation_token_gap_count"] == 2
        assert payload["summary"]["provider_run_join_ready"] is False
        assert payload["summary"]["gap_resolution_status"] in {"classification_required", "stamp_required"}
        assert payload["privacy_scan"]["status"] == "ok"
        assert payload["authority_boundary"]["captures_raw_prompt"] is False
        assert payload["required_stamping_fields"]
        assert "provider_usage_unavailable" in payload["closeout_enforcement_contract"]["accepted_missing_classifications"]
        assert "raw prompt" in payload["closeout_enforcement_contract"]["must_not_capture"]
        assert "--token-attribution-source" in payload["closeout_stamp_command_template"]
        assert payload["workflow_gap_summary"][0]["workflow_id"] == "WF88"
        assert payload["summary"]["unclassified_runtime_gap_count"] == 1
        assert payload["summary"]["post_cutoff_supported_unresolved_gap_count"] == 1
        assert payload["summary"]["closeout_enforcement_required"] is True
        assert payload["runtime_gap_samples"][0]["completion_cohort"] == "post_cutoff"


def test_bridge_rejects_self_consistent_codex_receipt_without_protected_dispatch_binding() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=0, stamped=True)
        payload = module.build_payload(token_usage, register, coding)

        # A self-consistent workspace receipt is not a protected Codex
        # dispatch binding. The native rollout may be audit-visible, but it
        # cannot close a post-cutover attribution/efficiency gap.
        assert payload["status"] == "blocked"
        assert payload["validation"]["status"] == "blocked"
        assert payload["summary"]["implementation_token_gap_count"] == 1
        assert payload["summary"]["provider_run_join_ready"] is False
        assert payload["summary"]["closeout_enforcement_required"] is True
        assert payload["summary"]["token_stamped_completed_model_lane_count"] == 0
        assert payload["runtime_gap_samples"][0]["usage_source_receipt_verified"] is False


def test_bridge_rejects_self_declared_credit_without_importer_receipt() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=0, stamped=True)
        register.with_suffix(".usage-receipts.json").unlink()
        payload = module.build_payload(token_usage, register, coding)

        assert payload["status"] == "blocked"
        assert payload["summary"]["token_stamped_completed_model_lane_count"] == 0
        assert payload["summary"]["provider_run_join_ready"] is False
        assert payload["runtime_gap_samples"][0]["usage_source_receipt_verified"] is False


def test_bridge_classifies_missing_usage_when_usage_is_unavailable() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=1)
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["runtime"].update({
            "agent_id": "implementation-builder",
            "phase": "implementation",
            "token_attribution_source": "provider_usage_unavailable",
        })
        register.write_text(json.dumps(data), encoding="utf-8")

        payload = module.build_payload(token_usage, register, coding)

        assert payload["summary"]["classified_runtime_gap_count"] == 1
        assert payload["summary"]["unclassified_runtime_gap_count"] == 0
        assert payload["summary"]["new_isolated_implementation_contract_gap_count"] == 1
        assert payload["runtime_gap_samples"][0]["missing_usage_classified"] is True
        assert payload["runtime_gap_samples"][0]["terminal_unavailable"] is False
        assert payload["summary"]["post_cutoff_supported_terminal_unavailable_count"] == 0
        assert payload["summary"]["post_cutoff_supported_unresolved_gap_count"] == 1
        assert payload["summary"]["closeout_enforcement_required"] is True
        assert payload["status"] == "blocked"


def test_bridge_rejects_legacy_unavailable_classification_for_new_isolated_job() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=0, stamped=False)
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["runtime"].update({
            "agent_id": "implementation-builder",
            "phase": "implementation",
            "token_attribution_source": "runtime_usage_unavailable",
        })
        register.write_text(json.dumps(data), encoding="utf-8")

        payload = module.build_payload(token_usage, register, coding)

        assert payload["status"] == "blocked"
        assert payload["summary"]["classified_runtime_gap_count"] == 1
        assert payload["summary"]["new_isolated_implementation_contract_gap_count"] == 1
        assert payload["runtime_gap_samples"][0]["new_isolated_missing_usage_classification_valid"] is False


def test_bridge_classifies_historical_pre_stamping_gaps() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=1)
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["completed_at_utc"] = "2026-06-20T00:00:00Z"
        register.write_text(json.dumps(data), encoding="utf-8")

        payload = module.build_payload(token_usage, register, coding)

        assert payload["summary"]["classified_runtime_gap_count"] == 1
        assert payload["summary"]["unclassified_runtime_gap_count"] == 0
        assert payload["runtime_gap_samples"][0]["missing_usage_classification"] == "historical_pre_token_stamping_unavailable"
        assert payload["summary"]["historical_supported_runtime_gap_count"] == 1


def test_bridge_classifies_historical_pre_closeout_guard_gaps() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=1)
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["completed_at_utc"] = "2026-07-03T19:00:00Z"
        register.write_text(json.dumps(data), encoding="utf-8")

        payload = module.build_payload(token_usage, register, coding)

        assert payload["summary"]["classified_runtime_gap_count"] == 1
        assert payload["summary"]["unclassified_runtime_gap_count"] == 0
        assert payload["runtime_gap_samples"][0]["missing_usage_classification"] == "historical_pre_token_closeout_guard_unavailable"
        assert "historical_pre_token_closeout_guard_unavailable" in payload["closeout_enforcement_contract"]["accepted_missing_classifications"]


def test_bridge_keeps_terminal_unavailable_post_cutoff_rows_warning_grade_when_no_action_required() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=0)
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["completed_at_utc"] = "2026-08-10T00:00:00Z"
        data["lanes"][0]["ended_at_utc"] = "2026-08-10T00:00:00Z"
        data["lanes"][0]["runtime"]["token_attribution_source"] = "provider_usage_unavailable"
        register.write_text(json.dumps(data), encoding="utf-8")

        payload = module.build_payload(token_usage, register, coding)

        assert payload["status"] == "warning"
        assert payload["validation"]["status"] == "warning"
        assert payload["summary"]["gap_resolution_status"] == "terminal_unavailable_only"
        assert payload["summary"]["post_cutoff_supported_terminal_unavailable_count"] == 1
        assert payload["summary"]["action_required_supported_runtime_gap_count"] == 0
        assert "post_cutoff_provider_usage_unavailable_is_not_a_valid_closeout" not in payload["validation"]["errors"]
        assert "post_cutoff_provider_usage_unavailable_terminal_only:1" in payload["validation"]["warnings"]


def test_bridge_backfills_current_chat_runtime_unavailable_before_cutoff() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=1)
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["completed_at_utc"] = "2026-07-06T18:00:00Z"
        data["lanes"][0]["runtime"]["session_label"] = "webchat-main"
        data["lanes"][0]["runtime"]["token_closeout_status"] = "missing_usage_classification_required"
        register.write_text(json.dumps(data), encoding="utf-8")

        payload = module.build_payload(token_usage, register, coding)

        assert payload["summary"]["classified_runtime_gap_count"] == 1
        assert payload["summary"]["unclassified_runtime_gap_count"] == 0
        assert payload["runtime_gap_samples"][0]["missing_usage_classification"] == "current_chat_runtime_unavailable"


def test_bridge_keeps_future_current_chat_gap_unclassified_without_explicit_stamp() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=1)
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["completed_at_utc"] = "2026-07-07T00:00:00Z"
        data["lanes"][0]["runtime"]["session_label"] = "webchat-main"
        data["lanes"][0]["runtime"]["token_closeout_status"] = "missing_usage_classification_required"
        register.write_text(json.dumps(data), encoding="utf-8")

        payload = module.build_payload(token_usage, register, coding)

        assert payload["summary"]["unclassified_runtime_gap_count"] == 1
        assert payload["runtime_gap_samples"][0]["missing_usage_classification"] is None


def test_partial_stamp_is_not_counted_complete_even_when_ledger_reports_no_gap() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=0, stamped=False)
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["runtime"].update({
            "input_tokens": 10,
            "token_attribution_source": "provider_usage",
        })
        register.write_text(json.dumps(data), encoding="utf-8")
        payload = module.build_payload(token_usage, register, coding)
        assert payload["summary"]["token_stamped_completed_model_lane_count"] == 0
        assert payload["summary"]["attribution_incomplete_lane_count"] == 1
        assert payload["summary"]["runtime_gap_total_count"] == 1
        assert payload["runtime_gap_samples"][0]["token_closeout_status"] == "attribution_incomplete"


def test_new_isolated_implementation_partial_stamp_blocks() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=0, stamped=False)
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["runtime"].update({
            "agent_id": "implementation-builder",
            "phase": "implementation",
            "input_tokens": 10,
            "token_attribution_source": "provider_usage",
        })
        register.write_text(json.dumps(data), encoding="utf-8")
        payload = module.build_payload(token_usage, register, coding)
        assert payload["status"] == "blocked"
        assert payload["validation"]["status"] == "blocked"
        assert payload["summary"]["new_isolated_implementation_contract_gap_count"] == 1
        assert payload["summary"]["new_attribution_grade_contract_gap_count"] == 1


def test_new_native_implementation_partial_complete_and_unavailable_contract() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=0, stamped=False)
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["runtime"].update({
            "phase": "implementation",
            "input_tokens": 10,
            "token_attribution_source": "provider_usage",
        })
        register.write_text(json.dumps(data), encoding="utf-8")
        payload = module.build_payload(token_usage, register, coding)
        assert payload["status"] == "blocked"
        assert payload["summary"]["new_isolated_implementation_contract_gap_count"] == 0
        assert payload["summary"]["new_attribution_grade_contract_gap_count"] == 1
        assert payload["runtime_gap_samples"][0]["token_closeout_status"] == "attribution_incomplete"

    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=0, stamped=True)
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["runtime"]["phase"] = "build"
        register.write_text(json.dumps(data), encoding="utf-8")
        payload = module.build_payload(token_usage, register, coding)
        # A phase change alters the parent/lane/attempt binding.  It cannot
        # reuse an earlier importer receipt, even when every token field is
        # otherwise still present.
        assert payload["validation"]["status"] == "blocked"
        assert payload["summary"]["attribution_grade_completed_model_lane_count"] == 0
        assert payload["summary"]["new_attribution_grade_contract_gap_count"] == 1
        assert payload["runtime_gap_samples"][0]["usage_source_receipt_verified"] is False

    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=0, stamped=False)
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["runtime"].update({
            "phase": "repair",
            "token_attribution_source": "provider_usage_unavailable",
        })
        register.write_text(json.dumps(data), encoding="utf-8")
        payload = module.build_payload(token_usage, register, coding)
        assert payload["validation"]["status"] == "blocked"
        assert payload["summary"]["classified_runtime_gap_count"] == 1
        assert payload["summary"]["new_attribution_grade_contract_gap_count"] == 1


def test_partial_tokens_cannot_hide_behind_provider_unavailable_classification() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=0, stamped=False)
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["runtime"].update({
            "phase": "integration",
            "input_tokens": 10,
            "token_attribution_source": "provider_usage_unavailable",
        })
        register.write_text(json.dumps(data), encoding="utf-8")
        payload = module.build_payload(token_usage, register, coding)
        assert payload["validation"]["status"] == "blocked"
        assert payload["summary"]["classified_runtime_gap_count"] == 1
        assert payload["summary"]["new_attribution_grade_contract_gap_count"] == 1
        assert payload["runtime_gap_samples"][0]["new_attribution_grade_missing_usage_classification_valid"] is False
        assert payload["runtime_gap_samples"][0]["terminal_unavailable"] is False
        assert payload["summary"]["post_cutoff_supported_unresolved_gap_count"] == 1


def test_phase_null_provider_unavailable_rows_are_terminal_but_visible() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=0, stamped=False)
        data = json.loads(register.read_text(encoding="utf-8"))
        template = data["lanes"][0]
        lanes = []
        for index, workflow in enumerate(("WF74", "WF88", "MEMORY"), start=1):
            lane = json.loads(json.dumps(template))
            lane["lane_id"] = f"{workflow}::terminal-unavailable-{index}"
            lane["workflow_id"] = workflow
            lane["workstream_id"] = f"terminal-unavailable-{index}"
            lane["runtime"]["task_name"] = f"terminal-unavailable-{index}"
            lane["runtime"]["token_attribution_source"] = "provider_usage_unavailable"
            lane["runtime"].pop("phase", None)
            lanes.append(lane)
        data["lanes"] = lanes
        register.write_text(json.dumps(data), encoding="utf-8")

        payload = module.build_payload(token_usage, register, coding)

        summary = payload["summary"]
        assert summary["implementation_token_gap_count"] == 3
        assert summary["supported_runtime_gap_count"] == 3
        assert summary["post_cutoff_supported_runtime_gap_count"] == 3
        assert summary["post_cutoff_supported_terminal_unavailable_count"] == 0
        assert summary["post_cutoff_supported_unresolved_gap_count"] == 3
        assert summary["post_cutoff_supported_missing_phase_count"] == 3
        assert summary["gap_resolution_status"] == "stamp_required"
        assert summary["closeout_enforcement_required"] is True
        assert summary["attribution_grade_closeout_ready"] is False
        assert payload["privacy_scan"]["status"] == "ok"
        assert all(row["completion_cohort"] == "post_cutoff" for row in payload["runtime_gap_samples"])
        assert all(row["terminal_unavailable"] is False for row in payload["runtime_gap_samples"])
        assert "post_cutoff_supported_missing_phase_count:3" in payload["validation"]["warnings"]


def test_cache_write_usage_is_exact_but_rate_unavailable() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=0, stamped=True)
        data = json.loads(register.read_text(encoding="utf-8"))
        runtime = data["lanes"][0]["runtime"]
        runtime["cache_write_tokens"] = 2
        runtime["total_tokens"] = 37
        # Model a new bounded source observation rather than mutating the
        # usage fields behind an old source receipt.
        runtime["source_snapshot_fingerprint"] = "snapshot-2"
        write_source_receipt(register, data["lanes"][0], runtime, module)
        register.write_text(json.dumps(data), encoding="utf-8")
        payload = module.build_payload(token_usage, register, coding)
        assert payload["validation"]["status"] == "blocked"
        assert payload["summary"]["attribution_grade_completed_model_lane_count"] == 0
        assert payload["summary"]["pricing_grade_completed_model_lane_count"] == 0
        # It remains an audit-visible rate limitation, but receives no
        # attribution/pricing/efficiency credit above.
        assert payload["summary"]["usage_exact_rate_unavailable_lane_count"] == 1


def test_timestampless_complete_model_lane_cannot_be_historical_or_ready() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, register, coding = seed(Path(tmpdir), module, gap_count=0, stamped=False)
        data = json.loads(register.read_text(encoding="utf-8"))
        lane = data["lanes"][0]
        lane.pop("completed_at_utc", None)
        lane.pop("ended_at_utc", None)
        lane["runtime"].update({
            "input_token_semantics": "exclusive_cached",
            "input_tokens": 10,
            "cached_input_tokens": 20,
            "cache_write_tokens": 0,
            "output_tokens": 5,
            "total_tokens": 35,
            "source_input_total_tokens": 30,
            "source_total_tokens_fresh": True,
            "token_attribution_source": "provider_usage",
            "usage_creditable": False,
            "usage_credit_status": "blocked",
        })
        register.write_text(json.dumps(data), encoding="utf-8")
        payload = module.build_payload(token_usage, register, coding)
        assert module.new_attribution_grade_contract(lane) is True
        assert payload["status"] == "blocked"
        assert payload["summary"]["attribution_grade_completed_model_lane_count"] == 0
        assert payload["summary"]["closeout_enforcement_required"] is True


def test_bridge_credit_reader_join_resolves_a_supported_gap() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        token_usage, register, coding = seed(root, module, gap_count=2, stamped=False)
        # Give the unstamped lane a provider run id: exactly the case the WF89
        # credit reader can resolve deterministically.
        data = json.loads(register.read_text(encoding="utf-8"))
        data["lanes"][0]["runtime"]["run_id"] = "run-credit-1"
        register.write_text(json.dumps(data), encoding="utf-8")
        credit = root / "tmp" / "wf89-credit-reader-current.json"
        write_json(credit, {
            "schema": "veritas.wf89_credit_reader.v1",
            "total_scanned": 2,
            "counts": {"CREDITABLE": 1},
            "records": [{
                "task_id": "t1",
                "run_id": "run-credit-1",
                "label": "wf88-one",
                "status": "succeeded",
                "state": "CREDITABLE",
                "verified": True,
                "usage": {"input": 100, "output": 40, "total": 140, "cost_total": 0.02},
                "usage_event_count": 1,
            }],
        })

        payload = module.build_payload(token_usage, register, coding, credit_reader_path=credit)

        assert payload["summary"]["credit_reader_status"] == "ok"
        assert payload["summary"]["credit_reader_creditable_run_count"] == 1
        assert payload["summary"]["credit_reader_resolved_runtime_gap_count"] == 1
        assert payload["summary"]["credit_reader_matched_usage_totals"]["total"] == 140
        assert all(row.get("lane_id") != "WF88::one" for row in payload["runtime_gap_samples"])


def test_bridge_stays_fail_closed_when_credit_reader_artifact_is_missing_or_invalid() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        token_usage, register, coding = seed(root, module, gap_count=2, stamped=False)

        missing = module.build_payload(token_usage, register, coding, credit_reader_path=root / "tmp" / "absent.json")
        assert missing["summary"]["credit_reader_status"] == "unavailable"
        assert missing["summary"]["credit_reader_resolved_runtime_gap_count"] == 0
        assert missing["summary"]["runtime_gap_total_count"] >= 1

        bad = root / "tmp" / "bad.json"
        write_json(bad, {"schema": "some.other.schema"})
        invalid = module.build_payload(token_usage, register, coding, credit_reader_path=bad)
        assert invalid["summary"]["credit_reader_status"] == "schema_mismatch"
        assert "credit_reader_artifact_schema_mismatch" in invalid["validation"]["warnings"]
        # Reader problems are warnings only; they never create errors or widen authority.
        assert all(not error.startswith("credit_reader") for error in invalid["validation"]["errors"])


if __name__ == "__main__":
    test_bridge_blocks_on_missing_post_cutoff_implementation_token_stamps()
    test_bridge_rejects_self_consistent_codex_receipt_without_protected_dispatch_binding()
    test_bridge_rejects_self_declared_credit_without_importer_receipt()
    test_bridge_classifies_missing_usage_when_usage_is_unavailable()
    test_bridge_rejects_legacy_unavailable_classification_for_new_isolated_job()
    test_bridge_classifies_historical_pre_stamping_gaps()
    test_bridge_classifies_historical_pre_closeout_guard_gaps()
    test_bridge_keeps_terminal_unavailable_post_cutoff_rows_warning_grade_when_no_action_required()
    test_bridge_backfills_current_chat_runtime_unavailable_before_cutoff()
    test_bridge_keeps_future_current_chat_gap_unclassified_without_explicit_stamp()
    test_partial_stamp_is_not_counted_complete_even_when_ledger_reports_no_gap()
    test_new_isolated_implementation_partial_stamp_blocks()
    test_new_native_implementation_partial_complete_and_unavailable_contract()
    test_partial_tokens_cannot_hide_behind_provider_unavailable_classification()
    test_phase_null_provider_unavailable_rows_are_terminal_but_visible()
    test_cache_write_usage_is_exact_but_rate_unavailable()
    test_timestampless_complete_model_lane_cannot_be_historical_or_ready()
    test_bridge_credit_reader_join_resolves_a_supported_gap()
    test_bridge_stays_fail_closed_when_credit_reader_artifact_is_missing_or_invalid()
    print("implementation token attribution bridge tests passed")
