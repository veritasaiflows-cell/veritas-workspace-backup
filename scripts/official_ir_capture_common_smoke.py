from __future__ import annotations

import json
import tempfile
from pathlib import Path

from official_ir_capture_common import (
    AUTHORITY,
    build_capture_document,
    claim,
    first_excerpt,
    html_to_text,
    write_json,
    write_md,
)


def main() -> int:
    raw = "<html><body><p>Adjusted EPS was $1.23.</p><p>Guidance remains unchanged.</p></body></html>"
    text = html_to_text(raw)
    meta = {
        "company_name": "Smoke Test Co.",
        "period_end": "2026-03-31",
        "source_url": "https://example.com/official-release.htm",
        "filing_url": "https://example.com/filing-index.htm",
        "accession_number": "0000000000-26-000001",
        "source_title": "Smoke Test Official Release",
        "source_type": "sec_8k_exhibit_99_1",
    }
    captures = {
        "adjusted_eps": claim(meta["source_url"], "official_captured", {"adjusted_eps": 1.23}, "Smoke section", first_excerpt(text, "Adjusted EPS")),
        "guidance": claim(meta["source_url"], "official_captured", "unchanged", "Smoke guidance", first_excerpt(text, "Guidance")),
    }
    data = build_capture_document(
        ticker="SMOKE",
        meta=meta,
        captures=captures,
        text=text,
        raw_html=raw,
        summary_note="Review-only smoke proof; no authority beyond official-source artifact generation.",
    )
    assert data["review_only"] is True
    assert data["resolved_for_apply"] is False
    assert data["authority"] == AUTHORITY
    assert data["authority"]["trade_or_account_action_allowed"] is False
    assert data["captures"]["adjusted_eps"]["period"] == "2026-03-31"
    assert data["summary"]["apply_ready"] is False
    assert data["source"]["source_text_sha256"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_json(tmp_path / "smoke.json", data)
        write_md(tmp_path / "smoke.md", data)
        loaded = json.loads((tmp_path / "smoke.json").read_text(encoding="utf-8"))
        assert loaded["ticker"] == "SMOKE"
        assert "no owner approval" in (tmp_path / "smoke.md").read_text(encoding="utf-8")
    print(json.dumps({"status": "ok", "checked": "official_ir_capture_common"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
