#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sec_env_audit_validator.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sec_env_audit_validator", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_user_agent_guard_rejects_placeholder(errors: list[str]) -> None:
    module = load_module()
    findings = module.validate_user_agent(module.PLACEHOLDER_USER_AGENT)
    codes = {finding["code"] for finding in findings}
    expect("user_agent_placeholder" in codes, "placeholder User-Agent should fail", errors)
    expect("user_agent_unexpected" in codes, "unexpected User-Agent should fail", errors)


def test_user_agent_guard_accepts_expected_value(errors: list[str]) -> None:
    module = load_module()
    findings = module.validate_user_agent(module.EXPECTED_USER_AGENT)
    expect(not findings, f"expected User-Agent should pass: {findings}", errors)


def test_parse_json_from_noisy_output(errors: list[str]) -> None:
    module = load_module()
    parsed = module.parse_json_from_output('INFO before\n{"method_count": 17, "user_agent": "ok"}\nINFO after\n')
    expect(parsed is not None, "JSON line should be parsed from noisy output", errors)
    expect(parsed.get("method_count") == 17, "method_count should be preserved", errors)


def test_current_workspace_sec_env_audit_is_ok(errors: list[str]) -> None:
    module = load_module()
    payload = module.build_payload(ROOT)
    expect(payload["status"] == "ok", f"current workspace SEC env audit should pass: {payload['validation']}", errors)
    expect(payload["summary"]["method_count"] >= module.MIN_METHOD_COUNT, "SEC Tools method count should meet minimum", errors)
    expect(payload["summary"]["user_agent"] == module.EXPECTED_USER_AGENT, "SEC User-Agent should match expected value", errors)


def main() -> int:
    errors: list[str] = []
    for test in (
        test_user_agent_guard_rejects_placeholder,
        test_user_agent_guard_accepts_expected_value,
        test_parse_json_from_noisy_output,
        test_current_workspace_sec_env_audit_is_ok,
    ):
        try:
            test(errors)
        except Exception as exc:
            errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: sec_env_audit_validator tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
