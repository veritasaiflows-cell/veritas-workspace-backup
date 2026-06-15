from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import earnings_date_source_confidence as confidence


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_blocked_primary_fetch_preserves_provider_estimate_label(tmp_path: Path, errors: list[str]) -> None:
    config = {
        "earnings_date_watchlist": {
            "NVDA": {"date": "2026-05-20", "primary_confirmed": False},
        },
    }
    earnings = {
        "generated_at_utc": "2026-05-10T16:00:00+00:00",
        "records": [
            {
                "ticker": "NVDA",
                "next_earnings_date": "2026-05-20",
                "source": "yfinance",
                "fetched_at_utc": "2026-05-10T16:00:00+00:00",
            },
        ],
    }
    config_path = tmp_path / "tmp" / "portfolio-config.json"
    earnings_path = tmp_path / "tmp" / "earnings-calendar.json"
    out_json = tmp_path / "tmp" / "earnings-date-source-confidence.json"
    out_md = tmp_path / "tmp" / "earnings-date-source-confidence.md"
    _write_json(config_path, config)
    _write_json(earnings_path, earnings)

    def fake_fetch(_url: str) -> dict[str, Any]:
        return {"fetch_status": "http_error", "http_status": 403, "body": "", "error": "HTTP Error 403: Forbidden"}

    old_paths = (
        confidence.WORKSPACE,
        confidence.CONFIG_PATH,
        confidence.EARNINGS_PATH,
        confidence.BROWSER_CONFIRMATION_PATH,
        confidence.OUT_JSON,
        confidence.OUT_MD,
        confidence.PRIMARY_SOURCE_PROBES,
        confidence.fetch_url,
    )
    try:
        confidence.WORKSPACE = tmp_path
        confidence.CONFIG_PATH = config_path
        confidence.EARNINGS_PATH = earnings_path
        confidence.BROWSER_CONFIRMATION_PATH = tmp_path / "tmp" / "earnings-date-browser-confirmation.json"
        confidence.OUT_JSON = out_json
        confidence.OUT_MD = out_md
        confidence.PRIMARY_SOURCE_PROBES = {
            "NVDA": [{"id": "nvidia_ir_events", "source_type": "company_ir", "url": "https://example.test", "note": "test"}],
        }
        confidence.fetch_url = fake_fetch
        confidence.main()
    finally:
        (
            confidence.WORKSPACE,
            confidence.CONFIG_PATH,
            confidence.EARNINGS_PATH,
            confidence.BROWSER_CONFIRMATION_PATH,
            confidence.OUT_JSON,
            confidence.OUT_MD,
            confidence.PRIMARY_SOURCE_PROBES,
            confidence.fetch_url,
        ) = old_paths

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    records = {row["ticker"]: row for row in payload["records"]}
    nvda = records.get("NVDA", {})
    if nvda.get("source_confidence") != "provider_estimate_unconfirmed":
        errors.append(f"NVDA should remain provider_estimate_unconfirmed: {nvda}")
    if nvda.get("primary_confirmation_status") != "blocked_primary_fetch":
        errors.append(f"NVDA primary status should be blocked_primary_fetch: {nvda}")
    if nvda.get("recommended_action") != "keep_timing_sensitive_until_primary_confirmed":
        errors.append(f"NVDA action should remain timing-sensitive: {nvda}")
    if payload.get("status") != "partial":
        errors.append(f"blocked primary fetch should make packet partial, got {payload.get('status')}")
    sites = nvda.get("verification_sites") or []
    if not any("investor.nvidia.com" in str(site.get("url")) for site in sites):
        errors.append(f"NVDA verification sites should include NVIDIA IR: {sites}")
    if not any("sec.gov" in str(site.get("url")) for site in sites):
        errors.append(f"NVDA verification sites should include SEC fallback: {sites}")
    md = out_md.read_text(encoding="utf-8")
    if "provider_estimate_unconfirmed" not in md or "blocked_primary_fetch" not in md:
        errors.append("markdown output should expose both provider confidence and blocked-primary status")
    if "NVIDIA Investor Relations" not in md:
        errors.append("markdown output should include human-checkable verification sites")


def test_bare_config_primary_confirmed_flag_does_not_upgrade_without_evidence(tmp_path: Path, errors: list[str]) -> None:
    config = {
        "earnings_date_watchlist": {
            "NVDA": {"date": "2026-05-20", "primary_confirmed": True},
        },
    }
    earnings = {
        "generated_at_utc": "2026-05-10T16:00:00+00:00",
        "records": [
            {
                "ticker": "NVDA",
                "next_earnings_date": "2026-05-20",
                "source": "yfinance",
                "fetched_at_utc": "2026-05-10T16:00:00+00:00",
            },
        ],
    }
    config_path = tmp_path / "tmp" / "portfolio-config.json"
    earnings_path = tmp_path / "tmp" / "earnings-calendar.json"
    out_json = tmp_path / "tmp" / "earnings-date-source-confidence.json"
    out_md = tmp_path / "tmp" / "earnings-date-source-confidence.md"
    _write_json(config_path, config)
    _write_json(earnings_path, earnings)

    def fake_fetch(_url: str) -> dict[str, Any]:
        return {"fetch_status": "ok", "http_status": 200, "body": "NVIDIA investor relations", "error": None}

    old_paths = (
        confidence.WORKSPACE,
        confidence.CONFIG_PATH,
        confidence.EARNINGS_PATH,
        confidence.BROWSER_CONFIRMATION_PATH,
        confidence.OUT_JSON,
        confidence.OUT_MD,
        confidence.PRIMARY_SOURCE_PROBES,
        confidence.fetch_url,
    )
    try:
        confidence.WORKSPACE = tmp_path
        confidence.CONFIG_PATH = config_path
        confidence.EARNINGS_PATH = earnings_path
        confidence.BROWSER_CONFIRMATION_PATH = tmp_path / "tmp" / "earnings-date-browser-confirmation.json"
        confidence.OUT_JSON = out_json
        confidence.OUT_MD = out_md
        confidence.PRIMARY_SOURCE_PROBES = {
            "NVDA": [{"id": "nvidia_ir_events", "source_type": "company_ir", "url": "https://example.test", "note": "test"}],
        }
        confidence.fetch_url = fake_fetch
        confidence.main()
    finally:
        (
            confidence.WORKSPACE,
            confidence.CONFIG_PATH,
            confidence.EARNINGS_PATH,
            confidence.BROWSER_CONFIRMATION_PATH,
            confidence.OUT_JSON,
            confidence.OUT_MD,
            confidence.PRIMARY_SOURCE_PROBES,
            confidence.fetch_url,
        ) = old_paths

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    nvda = {row["ticker"]: row for row in payload["records"]}.get("NVDA", {})
    if nvda.get("source_confidence") != "provider_estimate_unconfirmed":
        errors.append(f"bare primary_confirmed flag should not upgrade confidence: {nvda}")
    if nvda.get("configured_primary_evidence_valid") is not False:
        errors.append(f"bare primary_confirmed flag should have invalid evidence: {nvda}")
    if "primary_confirmed flag ignored" not in " ".join(payload.get("warnings", [])):
        errors.append(f"packet should warn about ignored primary_confirmed flag: {payload.get('warnings')}")


def test_config_primary_evidence_can_primary_confirm(tmp_path: Path, errors: list[str]) -> None:
    config = {
        "earnings_date_watchlist": {
            "NVDA": {
                "date": "2026-05-20",
                "primary_confirmed": True,
                "primary_evidence": {
                    "date": "2026-05-20",
                    "source_type": "company_ir",
                    "url": "https://investor.nvidia.com/events-and-presentations/events-and-presentations/default.aspx",
                    "matched_text": "NVIDIA Q1 FY2027 financial results conference call May 20, 2026",
                },
            },
        },
    }
    earnings = {
        "generated_at_utc": "2026-05-10T16:00:00+00:00",
        "records": [
            {
                "ticker": "NVDA",
                "next_earnings_date": "2026-05-20",
                "source": "yfinance",
                "fetched_at_utc": "2026-05-10T16:00:00+00:00",
            },
        ],
    }
    config_path = tmp_path / "tmp" / "portfolio-config.json"
    earnings_path = tmp_path / "tmp" / "earnings-calendar.json"
    out_json = tmp_path / "tmp" / "earnings-date-source-confidence.json"
    out_md = tmp_path / "tmp" / "earnings-date-source-confidence.md"
    _write_json(config_path, config)
    _write_json(earnings_path, earnings)

    def fake_fetch(_url: str) -> dict[str, Any]:
        return {"fetch_status": "ok", "http_status": 200, "body": "NVIDIA investor relations", "error": None}

    old_paths = (
        confidence.WORKSPACE,
        confidence.CONFIG_PATH,
        confidence.EARNINGS_PATH,
        confidence.BROWSER_CONFIRMATION_PATH,
        confidence.OUT_JSON,
        confidence.OUT_MD,
        confidence.PRIMARY_SOURCE_PROBES,
        confidence.fetch_url,
    )
    try:
        confidence.WORKSPACE = tmp_path
        confidence.CONFIG_PATH = config_path
        confidence.EARNINGS_PATH = earnings_path
        confidence.BROWSER_CONFIRMATION_PATH = tmp_path / "tmp" / "earnings-date-browser-confirmation.json"
        confidence.OUT_JSON = out_json
        confidence.OUT_MD = out_md
        confidence.PRIMARY_SOURCE_PROBES = {
            "NVDA": [{"id": "nvidia_ir_events", "source_type": "company_ir", "url": "https://example.test", "note": "test"}],
        }
        confidence.fetch_url = fake_fetch
        confidence.main()
    finally:
        (
            confidence.WORKSPACE,
            confidence.CONFIG_PATH,
            confidence.EARNINGS_PATH,
            confidence.BROWSER_CONFIRMATION_PATH,
            confidence.OUT_JSON,
            confidence.OUT_MD,
            confidence.PRIMARY_SOURCE_PROBES,
            confidence.fetch_url,
        ) = old_paths

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    nvda = {row["ticker"]: row for row in payload["records"]}.get("NVDA", {})
    if nvda.get("source_confidence") != "primary_confirmed":
        errors.append(f"valid config primary_evidence should primary-confirm NVDA: {nvda}")
    if nvda.get("configured_primary_evidence_valid") is not True:
        errors.append(f"valid config primary_evidence should be recorded as valid: {nvda}")
    if nvda.get("recommended_action") != "eligible_to_mark_primary_confirmed":
        errors.append(f"valid primary evidence should be eligible for marking: {nvda}")


def test_official_browser_evidence_can_primary_confirm_without_probe(tmp_path: Path, errors: list[str]) -> None:
    config = {
        "earnings_date_watchlist": {
            "NVDA": {"date": "2026-05-20", "primary_confirmed": False},
        },
    }
    earnings = {
        "generated_at_utc": "2026-05-10T16:00:00+00:00",
        "records": [
            {
                "ticker": "NVDA",
                "next_earnings_date": "2026-05-20",
                "source": "yfinance",
                "fetched_at_utc": "2026-05-10T16:00:00+00:00",
            },
        ],
    }
    browser = {
        "generated_at_utc": "2026-05-10T16:05:00Z",
        "authority": "review_only_no_canonical_mutation",
        "records": [
            {
                "ticker": "NVDA",
                "confirmation_status": "primary_confirmed",
                "source_type": "company_ir",
                "evidence_date": "2026-05-20",
                "url": "https://investor.nvidia.com/events-and-presentations/events-and-presentations/default.aspx",
                "page_title": "NVIDIA Investor Events",
                "matched_text": "NVIDIA Q1 FY2027 financial results conference call May 20, 2026",
            },
        ],
    }
    config_path = tmp_path / "tmp" / "portfolio-config.json"
    earnings_path = tmp_path / "tmp" / "earnings-calendar.json"
    browser_path = tmp_path / "tmp" / "earnings-date-browser-confirmation.json"
    out_json = tmp_path / "tmp" / "earnings-date-source-confidence.json"
    out_md = tmp_path / "tmp" / "earnings-date-source-confidence.md"
    _write_json(config_path, config)
    _write_json(earnings_path, earnings)
    _write_json(browser_path, browser)

    def failing_fetch(_url: str) -> dict[str, Any]:
        errors.append("primary URL probe should not run when official browser evidence already confirms")
        return {"fetch_status": "http_error", "http_status": 403, "body": "", "error": "unexpected"}

    old_paths = (
        confidence.WORKSPACE,
        confidence.CONFIG_PATH,
        confidence.EARNINGS_PATH,
        confidence.BROWSER_CONFIRMATION_PATH,
        confidence.OUT_JSON,
        confidence.OUT_MD,
        confidence.PRIMARY_SOURCE_PROBES,
        confidence.fetch_url,
    )
    try:
        confidence.WORKSPACE = tmp_path
        confidence.CONFIG_PATH = config_path
        confidence.EARNINGS_PATH = earnings_path
        confidence.BROWSER_CONFIRMATION_PATH = browser_path
        confidence.OUT_JSON = out_json
        confidence.OUT_MD = out_md
        confidence.PRIMARY_SOURCE_PROBES = {
            "NVDA": [{"id": "nvidia_ir_events", "source_type": "company_ir", "url": "https://example.test", "note": "test"}],
        }
        confidence.fetch_url = failing_fetch
        confidence.main()
    finally:
        (
            confidence.WORKSPACE,
            confidence.CONFIG_PATH,
            confidence.EARNINGS_PATH,
            confidence.BROWSER_CONFIRMATION_PATH,
            confidence.OUT_JSON,
            confidence.OUT_MD,
            confidence.PRIMARY_SOURCE_PROBES,
            confidence.fetch_url,
        ) = old_paths

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    nvda = {row["ticker"]: row for row in payload["records"]}.get("NVDA", {})
    if nvda.get("source_confidence") != "primary_confirmed":
        errors.append(f"official browser evidence should primary-confirm NVDA: {nvda}")
    if nvda.get("primary_confirmation_status") != "browser_primary_confirmed":
        errors.append(f"NVDA primary status should show browser_primary_confirmed: {nvda}")
    if nvda.get("recommended_action") != "eligible_to_mark_primary_confirmed":
        errors.append(f"primary-confirmed browser evidence should be eligible for marking: {nvda}")
    if payload.get("status") != "ok":
        errors.append(f"browser-confirmed packet should be ok, got {payload.get('status')}: {payload.get('warnings')}")


def main() -> int:
    errors: list[str] = []
    with TemporaryDirectory() as tmp:
        test_blocked_primary_fetch_preserves_provider_estimate_label(Path(tmp), errors)
    with TemporaryDirectory() as tmp:
        test_bare_config_primary_confirmed_flag_does_not_upgrade_without_evidence(Path(tmp), errors)
    with TemporaryDirectory() as tmp:
        test_config_primary_evidence_can_primary_confirm(Path(tmp), errors)
    with TemporaryDirectory() as tmp:
        test_official_browser_evidence_can_primary_confirm_without_probe(Path(tmp), errors)
    if errors:
        print("earnings_date_source_confidence_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("earnings_date_source_confidence_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
