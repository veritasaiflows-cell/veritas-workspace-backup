from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import cron_contract_validator as ccv


def sample_job() -> dict:
    return {
        "id": "job-1",
        "name": "Ops - Sample",
        "enabled": True,
        "description": "sample",
        "schedule": {"cron": "0 * * * *"},
        "payload": {
            "message": "run",
            "model": "openai/gpt-5.4",
            "thinking": "high",
            "timeoutSeconds": 300,
            "lightContext": False,
        },
        "failureAlert": {"after": 1, "mode": "announce"},
    }


def test_compare_contract_ok() -> None:
    contract = {
        "name": "Ops - Sample",
        "enabled": True,
        "payload": {"model": "openai/gpt-5.4", "thinking": "high", "timeoutSeconds": 300},
    }
    result = ccv.compare_contract(contract, sample_job())
    assert result["status"] == "ok"
    assert result["drift"] == []


def test_compare_contract_reports_payload_drift() -> None:
    contract = {
        "name": "Ops - Sample",
        "payload": {"model": "openai/gpt-5.5", "thinking": "high"},
    }
    result = ccv.compare_contract(contract, sample_job())
    assert result["status"] == "drift"
    assert result["drift"][0]["field"] == "payload.model"


def test_compare_contract_supports_nested_delivery_fields() -> None:
    job = sample_job()
    job["delivery"] = {"mode": "none", "bestEffort": True}
    contract = {
        "name": "Ops - Sample",
        "delivery": {"mode": "last", "bestEffort": True},
        "compare_fields": ["delivery.mode", "delivery.bestEffort"],
    }
    result = ccv.compare_contract(contract, job)
    assert result["status"] == "drift"
    assert result["drift"] == [{"field": "delivery.mode", "expected": "last", "actual": "none"}]


def test_missing_live_job_respects_required_flag() -> None:
    result = ccv.compare_contract({"name": "Missing", "required": False}, None)
    assert result["status"] == "missing_live_job"
    assert result["severity"] == "warning"


def test_find_live_job_by_name() -> None:
    assert ccv.find_live_job({"name": "Ops - Sample"}, [sample_job()])["id"] == "job-1"


def test_compare_contract_reports_prompt_bloat() -> None:
    job = sample_job()
    job["payload"]["message"] = "x" * 10
    contract = {"name": "Ops - Sample", "payload": {"message": "x" * 10}}
    result = ccv.compare_contract(contract, job, max_prompt_chars=5)
    assert result["status"] == "ok"
    assert result["prompt_bloat"][0]["source"] == "expected"


def test_system_owned_declaration_detection() -> None:
    assert ccv.is_system_owned_declaration("skill-collection-review:main") is True
    assert ccv.is_system_owned_declaration("skill-collection-review-main") is True
    assert ccv.is_system_owned_declaration("heartbeat:main") is True
    assert ccv.is_system_owned_declaration("Ops - Sample") is False
    assert ccv.is_system_owned_declaration(None) is False


def test_system_projected_prompt_uses_named_allowance_not_workspace_budget() -> None:
    """A runtime-projected monitor prompt over the workspace budget must not
    register as bloat, and the effective budget must stay reported."""
    prompt = "y" * 3199
    job = sample_job()
    job["name"] = "skill-collection-review-main"
    job["declarationKey"] = "skill-collection-review:main"
    job["payload"]["message"] = prompt
    contract = {
        "name": "skill-collection-review-main",
        "declarationKey": "skill-collection-review:main",
        "payload": {"message": prompt},
    }
    result = ccv.compare_contract(contract, job)
    assert result["prompt_bloat"] == []
    assert result["prompt_budget"]["system_owned_declaration"] is True
    assert result["prompt_budget"]["max_prompt_chars"] == ccv.SYSTEM_PROJECTED_MAX_PROMPT_CHARS
    assert result["prompt_budget"]["workspace_default_max_prompt_chars"] == ccv.DEFAULT_MAX_PROMPT_CHARS
    assert result["prompt_shape"]["expected"]["over_char_budget"] is False


def test_workspace_prompt_keeps_default_budget() -> None:
    """The allowance must stay scoped to platform-projected declarations."""
    prompt = "y" * 3199
    job = sample_job()
    job["payload"]["message"] = prompt
    contract = {"name": "Ops - Sample", "payload": {"message": prompt}}
    result = ccv.compare_contract(contract, job)
    assert result["prompt_bloat"][0]["source"] == "expected"
    assert result["prompt_budget"]["system_owned_declaration"] is False
    assert result["prompt_budget"]["max_prompt_chars"] == ccv.DEFAULT_MAX_PROMPT_CHARS


def test_system_projected_prompt_still_flags_true_oversize() -> None:
    """The larger allowance is a budget, not an exemption: a genuinely
    oversized projected prompt must still surface as bloat."""
    prompt = "z" * (ccv.SYSTEM_PROJECTED_MAX_PROMPT_CHARS + 1)
    job = sample_job()
    job["declarationKey"] = "skill-collection-review:main"
    job["payload"]["message"] = prompt
    contract = {
        "declarationKey": "skill-collection-review:main",
        "payload": {"message": prompt},
    }
    result = ccv.compare_contract(contract, job)
    assert result["prompt_bloat"][0]["source"] == "expected"


def test_compare_contract_detects_multiline_truncation() -> None:
    job = sample_job()
    job["payload"]["message"] = "first line"
    contract = {"name": "Ops - Sample", "payload": {"message": "first line\nsecond line"}}
    result = ccv.compare_contract(contract, job)
    assert result["status"] == "drift"
    assert result["multiline_live_intact"] is False


def test_compare_contract_blocks_unsupported_fable_route() -> None:
    job = sample_job()
    job["payload"]["model"] = "claude-cli/claude-fable-5"
    contract = {"name": "Ops - Sample", "payload": {"model": "claude-cli/claude-fable-5"}}
    result = ccv.compare_contract(contract, job)
    assert result["status"] == "unsupported_model"
    assert result["severity"] == "error"
    assert result["unsupported_model_routes"][0]["model"] == "claude-cli/claude-fable-5"


def test_compare_contract_blocks_quiet_only_agentturn_prompt() -> None:
    message = (
        "QUIET CRON OUTPUT RULE (hard): this job uses delivery.mode=none. "
        "When the success/no-action path says NO_REPLY, your entire final response must be exactly NO_REPLY."
    )
    job = sample_job()
    job["payload"]["kind"] = "agentTurn"
    job["payload"]["message"] = message
    contract = {"name": "Ops - Sample", "payload": {"kind": "agentTurn", "message": message}}
    result = ccv.compare_contract(contract, job)
    assert result["status"] == "prompt_integrity_error"
    assert result["severity"] == "error"
    assert result["prompt_integrity_findings"][0]["issue"] == "quiet_only_agentturn_prompt"


def test_prompt_integrity_allows_quiet_rule_with_task_body() -> None:
    job = sample_job()
    job["payload"]["kind"] = "agentTurn"
    job["payload"]["message"] = (
        "QUIET CRON OUTPUT RULE (hard): reply exactly NO_REPLY on success.\n\n"
        "Work in C:\\Users\\Veritas\\.openclaw\\workspace.\n"
        "Objective: run proof.\n"
        "Execute exactly: python scripts\\sample.py --write --validate"
    )
    assert ccv.prompt_integrity_findings(job, source="live") == []


def test_object_expected_artifact_path_is_normalized_and_metadata_preserved() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifact = root / "tmp" / "proof.json"
        artifact.parent.mkdir(parents=True)
        artifact.write_text("{}", encoding="utf-8")
        original_root = ccv.ROOT
        ccv.ROOT = root
        try:
            contract = {
                "name": "Ops - Sample",
                "expected_artifacts": [
                    {"path": "tmp\\proof.json", "role": "proof", "required": True, "blocking": False},
                    {"path": "", "role": "invalid", "required": False, "blocking": False},
                    {},
                ],
            }
            result = ccv.compare_contract(contract, sample_job())
        finally:
            ccv.ROOT = original_root
        proof, invalid, empty_object = result["expected_artifacts"]
        assert proof == {
            "path": "tmp/proof.json",
            "role": "proof",
            "required": True,
            "blocking": False,
            "exists": True,
            "valid_path": True,
        }
        assert invalid["path"] == ""
        assert invalid["valid_path"] is False
        assert invalid not in result["missing_expected_artifacts"]
        assert empty_object == {"path": "", "exists": False, "valid_path": False}
        assert empty_object in result["missing_expected_artifacts"]


def past_utc_iso(hours: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def test_completed_one_shot_past_due_delete_after_run() -> None:
    contract = {
        "name": "Finance - Monday Market Hours G6 Proof",
        "schedule": {"kind": "at", "at": past_utc_iso(-2)},
        "deleteAfterRun": True,
    }
    result = ccv.compare_contract(contract, None)
    assert result["status"] == "completed_one_shot"
    assert result["severity"] == "info"
    assert result["drift"] == []
    assert result["scheduled_at_utc"] == contract["schedule"]["at"]


def test_future_one_shot_delete_after_run_stays_missing() -> None:
    contract = {
        "name": "Finance - Baseline Renewal Gate Preflight",
        "schedule": {"kind": "at", "at": past_utc_iso(48)},
        "deleteAfterRun": True,
    }
    result = ccv.compare_contract(contract, None)
    assert result["status"] == "missing_live_job"
    assert result["severity"] == "error"


def test_past_due_one_shot_without_delete_after_run_stays_missing() -> None:
    contract = {
        "name": "Follow-up: Future Session Packet re-check",
        "schedule": {"kind": "at", "at": past_utc_iso(-2)},
    }
    result = ccv.compare_contract(contract, None)
    assert result["status"] == "missing_live_job"
    assert result["severity"] == "error"


def test_recurring_cron_without_live_job_stays_missing() -> None:
    contract = {
        "name": "Ops - Sample",
        "schedule": {"kind": "cron", "expr": "0 * * * *"},
    }
    result = ccv.compare_contract(contract, None)
    assert result["status"] == "missing_live_job"
    assert result["severity"] == "error"


def build_args(contract_dir: Path, live_file: Path) -> argparse.Namespace:
    return argparse.Namespace(
        contract_dir=contract_dir,
        live_file=live_file,
        contract=None,
        max_prompt_chars=ccv.DEFAULT_MAX_PROMPT_CHARS,
        max_message_lines=ccv.DEFAULT_MAX_MESSAGE_LINES,
        require_contracts=True,
        fail_on_drift=True,
        fail_on_prompt_bloat=False,
    )


def test_summary_reports_detected_routes_separately_from_configured_denylist() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        contract_dir = root / "contracts"
        contract_dir.mkdir()
        contract_path = contract_dir / "sample.json"
        live_path = root / "live.json"
        contract = {
            "job_id": "job-1",
            "name": "Ops - Sample",
            "payload": {"model": "openai/gpt-5.4", "thinking": "high", "timeoutSeconds": 300},
        }
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        live_path.write_text(json.dumps({"jobs": [sample_job()]}), encoding="utf-8")
        clean = ccv.build_payload(build_args(contract_dir, live_path))
        assert clean["summary"]["unsupported_model_route_count"] == 0
        assert clean["summary"]["unsupported_model_routes"] == []
        assert clean["summary"]["configured_unsupported_model_routes"] == sorted(ccv.UNSUPPORTED_MODEL_ROUTES)

        contract["payload"]["model"] = "claude-cli/claude-fable-5"
        live = sample_job()
        live["payload"]["model"] = "claude-cli/claude-fable-5"
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        live_path.write_text(json.dumps({"jobs": [live]}), encoding="utf-8")
        detected = ccv.build_payload(build_args(contract_dir, live_path))
        routes = detected["summary"]["unsupported_model_routes"]
        assert detected["summary"]["unsupported_model_route_count"] == len(routes) == 1
        assert routes[0]["model"] == "claude-cli/claude-fable-5"
        assert routes[0]["detection_count"] == 2
        assert routes[0]["sources"] == ["contract", "live"]


def test_contract_prompt_integrity_error_makes_validation_non_ok() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        contract_dir = root / "contracts"
        contract_dir.mkdir()
        contract_path = contract_dir / "sample.json"
        live_path = root / "live.json"
        quiet_only = (
            "QUIET CRON OUTPUT RULE (hard): delivery.mode=none; "
            "on success reply exactly NO_REPLY."
        )
        contract_path.write_text(json.dumps({
            "job_id": "job-1",
            "name": "Ops - Sample",
            "payload": {"kind": "agentTurn", "message": quiet_only},
            "compare_fields": ["enabled"],
        }), encoding="utf-8")
        live = sample_job()
        live["payload"]["kind"] = "agentTurn"
        live["payload"]["message"] = "Objective: refresh proof. Execute exactly: python scripts\\sample.py --write --validate"
        live_path.write_text(json.dumps({"jobs": [live]}), encoding="utf-8")
        payload = ccv.build_payload(build_args(contract_dir, live_path))
        assert payload["summary"]["contract_prompt_integrity_error_count"] == 1
        assert payload["summary"]["live_prompt_integrity_error_count"] == 0
        assert payload["contract_prompt_integrity_findings"][0]["issue"] == "quiet_only_agentturn_prompt"
        assert payload["status"] == "error"
        assert payload["validation"]["status"] == "error"
        assert "cron_contract_prompt_integrity_error_present" in payload["validation"]["errors"]


GOOD_TRIGGER = (
    "const res = await exec({ command: 'check' });\n"
    "const status = String(res?.aggregated ?? '').trim();\n"
    "json({ fire: status !== trigger.state?.status, state: { status } });"
)
# Shape of the WF74 gate trigger before the 2026-09-25 fix.
OLD_GATE_TRIGGER = (
    "let raw='';\n"
    "try{const r=await exec({command:cmd});raw=(r&&typeof r==='object')?(r.stdout||r.output||r.text||JSON.stringify(r)):String(r||'');}catch(e){}\n"
    "const prev=(typeof state!=='undefined'&&state&&state.sig)?state.sig:null;\n"
    "return{fire:false,state:{sig:prev}};"
)


def trigger_job(script: str | None) -> dict:
    job = sample_job()
    if script is not None:
        job["trigger"] = {"script": script}
    return job


def test_trigger_lint_accepts_documented_shape() -> None:
    assert ccv.trigger_integrity_findings(trigger_job(GOOD_TRIGGER), source="live") == []


def test_trigger_lint_flags_old_gate_shape() -> None:
    issues = {f["issue"] for f in ccv.trigger_integrity_findings(trigger_job(OLD_GATE_TRIGGER), source="live")}
    assert issues == {"trigger_exec_output_not_aggregated", "trigger_bare_state_read"}


def test_trigger_lint_ignores_comments_and_state_keys() -> None:
    script = (
        "// previous state. is read from trigger.state; never call exec() on stdout\n"
        "/* tools.call('exec') was the old envelope */\n"
        "const state = { n: trigger.state?.n ?? 0 };\n"
        "json({ fire: false, state });"
    )
    assert ccv.trigger_integrity_findings(trigger_job(script), source="live") == []


def test_trigger_lint_flags_legacy_envelope() -> None:
    script = "const r = await tools.call('exec', {command: 'x'}); const out = r.result.details.aggregated;"
    issues = {f["issue"] for f in ccv.trigger_integrity_findings(trigger_job(script), source="live")}
    assert issues == {"trigger_legacy_tools_call_exec"}


def test_trigger_sha_pin_matches_and_drifts() -> None:
    contract = {"name": "Ops - Sample", "trigger_script_sha256": ccv.trigger_script_sha256(GOOD_TRIGGER)}
    assert ccv.compare_contract(contract, trigger_job(GOOD_TRIGGER))["status"] == "ok"
    changed = ccv.compare_contract(contract, trigger_job(GOOD_TRIGGER + "\n"))
    assert changed["status"] == "drift"
    assert changed["drift"][0]["field"] == "trigger.script_sha256"
    removed = ccv.compare_contract(contract, trigger_job(None))
    assert removed["drift"][0]["actual"] is None


def test_trigger_verbatim_pin_compared_without_compare_field() -> None:
    contract = {"name": "Ops - Sample", "trigger": {"script": GOOD_TRIGGER}, "compare_fields": ["enabled"]}
    assert ccv.compare_contract(contract, trigger_job(GOOD_TRIGGER))["status"] == "ok"
    result = ccv.compare_contract(contract, trigger_job(GOOD_TRIGGER.replace("status", "s")))
    assert [d["field"] for d in result["drift"]] == ["trigger.script"]


def test_unpinned_live_trigger_is_drift() -> None:
    result = ccv.compare_contract({"name": "Ops - Sample"}, trigger_job(GOOD_TRIGGER))
    assert result["status"] == "drift"
    assert result["drift"][0]["reason"] == "live job has a trigger script the contract does not pin"


def test_trigger_integrity_error_makes_validation_non_ok() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        contract_dir = root / "contracts"
        contract_dir.mkdir()
        live_path = root / "live.json"
        (contract_dir / "sample.json").write_text(json.dumps({
            "job_id": "job-1",
            "name": "Ops - Sample",
            "trigger_script_sha256": ccv.trigger_script_sha256(OLD_GATE_TRIGGER),
            "compare_fields": ["enabled"],
        }), encoding="utf-8")
        live_path.write_text(json.dumps({"jobs": [trigger_job(OLD_GATE_TRIGGER)]}), encoding="utf-8")
        payload = ccv.build_payload(build_args(contract_dir, live_path))
        assert payload["contracts"][0]["status"] == "trigger_integrity_error"
        assert payload["summary"]["live_trigger_job_count"] == 1
        assert payload["summary"]["live_trigger_integrity_error_count"] == 2
        assert payload["summary"]["contract_trigger_integrity_error_count"] == 0
        assert payload["validation"]["status"] == "error"
        assert "cron_trigger_integrity_error_present" in payload["validation"]["errors"]


if __name__ == "__main__":
    test_compare_contract_ok()
    test_compare_contract_reports_payload_drift()
    test_compare_contract_supports_nested_delivery_fields()
    test_missing_live_job_respects_required_flag()
    test_find_live_job_by_name()
    test_compare_contract_reports_prompt_bloat()
    test_system_owned_declaration_detection()
    test_system_projected_prompt_uses_named_allowance_not_workspace_budget()
    test_workspace_prompt_keeps_default_budget()
    test_system_projected_prompt_still_flags_true_oversize()
    test_compare_contract_detects_multiline_truncation()
    test_compare_contract_blocks_unsupported_fable_route()
    test_compare_contract_blocks_quiet_only_agentturn_prompt()
    test_prompt_integrity_allows_quiet_rule_with_task_body()
    test_object_expected_artifact_path_is_normalized_and_metadata_preserved()
    test_summary_reports_detected_routes_separately_from_configured_denylist()
    test_contract_prompt_integrity_error_makes_validation_non_ok()
    test_completed_one_shot_past_due_delete_after_run()
    test_future_one_shot_delete_after_run_stays_missing()
    test_past_due_one_shot_without_delete_after_run_stays_missing()
    test_recurring_cron_without_live_job_stays_missing()
    test_trigger_lint_accepts_documented_shape()
    test_trigger_lint_flags_old_gate_shape()
    test_trigger_lint_ignores_comments_and_state_keys()
    test_trigger_lint_flags_legacy_envelope()
    test_trigger_sha_pin_matches_and_drifts()
    test_trigger_verbatim_pin_compared_without_compare_field()
    test_unpinned_live_trigger_is_drift()
    test_trigger_integrity_error_makes_validation_non_ok()
    print("ok")
