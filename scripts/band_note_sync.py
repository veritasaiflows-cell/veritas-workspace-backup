from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
CONFIG_PATH = TMP / "portfolio-config.json"
NOTE_PATH = WORKSPACE / "03. Portfolio" / "Technical Entry and Invalidation Sheet.md"
OUT_PATH = TMP / "band-note-sync.md"
OUT_JSON_PATH = TMP / "band-note-sync.json"

SECTION_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
BAND_RE = re.compile(r"^- Preferred entry band: \*\*(.+?)\*\*(.*)$")
STOP_RE = re.compile(r"^- Explicit stop: \*\*(.+?)\*\*(.*)$")


@dataclass
class BandMismatch:
    ticker: str
    current_band_line: str | None
    expected_band_line: str | None
    current_stop_line: str | None
    expected_stop_line: str | None
    changed: bool
    note_status: str
    metadata_notice: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare machine entry bands against the canonical technical note and emit exact sync actions.",
    )
    parser.add_argument("--out", default=str(OUT_PATH), help="Output markdown report path.")
    parser.add_argument("--json-out", default=str(OUT_JSON_PATH), help="Output JSON report path.")
    return parser.parse_args()



def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))



def extract_sections(text: str) -> dict[str, list[str]]:
    matches = list(SECTION_RE.finditer(text))
    sections: dict[str, list[str]] = {}
    for idx, match in enumerate(matches):
        ticker = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        sections[ticker] = text[start:end].strip("\n").splitlines()
    return sections



def normalize_num(value: Any) -> str:
    if value is None:
        return ""
    num = float(value)
    if abs(num - round(num)) < 1e-9:
        return str(int(round(num)))
    return f"{num:.2f}"



def build_expected_band_line(low: Any, high: Any, set_date: str | None, current_suffix: str | None) -> str | None:
    if low is None or high is None:
        return None
    suffix = current_suffix if current_suffix is not None else ""
    if set_date and "band updated" not in suffix.lower() and "band initialized" not in suffix.lower():
        suffix = f" (band updated {set_date})"
    return f"- Preferred entry band: **{normalize_num(low)} to {normalize_num(high)}**{suffix}"



def build_expected_stop_line(stop: Any, current_suffix: str | None) -> str | None:
    if stop is None:
        return None
    suffix = current_suffix if current_suffix is not None else ""
    return f"- Explicit stop: **{normalize_num(stop)}**{suffix}"



def split_line(pattern: re.Pattern[str], line: str | None) -> tuple[str | None, str | None]:
    if not line:
        return None, None
    match = pattern.match(line.strip())
    if not match:
        return None, None
    return match.group(1), match.group(2)



def normalize_band_text(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = text.replace("–", "to")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.lower()



def find_line(lines: list[str], prefix: str) -> str | None:
    for line in lines:
        if line.startswith(prefix):
            return line
    return None



def compare_ticker(ticker: str, band: dict[str, Any], section_lines: list[str] | None) -> BandMismatch:
    current_band_line = None
    current_stop_line = None
    expected_band_line = None
    expected_stop_line = None

    if section_lines is None:
        return BandMismatch(ticker, None, None, None, None, False, "missing section in note")

    current_band_line = find_line(section_lines, "- Preferred entry band:")
    current_stop_line = find_line(section_lines, "- Explicit stop:")

    current_band_text, band_suffix = split_line(BAND_RE, current_band_line)
    current_stop_text, stop_suffix = split_line(STOP_RE, current_stop_line)

    expected_band_line = build_expected_band_line(
        band.get("low"), band.get("high"), band.get("band_last_set"), band_suffix
    )
    expected_stop_line = build_expected_stop_line(band.get("stop"), stop_suffix)

    expected_band_text = f"{normalize_num(band.get('low'))} to {normalize_num(band.get('high'))}" if band.get("low") is not None and band.get("high") is not None else None
    expected_stop_text = normalize_num(band.get("stop")) if band.get("stop") is not None else None

    changed = False
    if expected_band_text and normalize_band_text(current_band_text) != normalize_band_text(expected_band_text):
        changed = True
    if expected_stop_text and normalize_band_text(current_stop_text) != normalize_band_text(expected_stop_text):
        changed = True

    metadata_notice = None
    if not changed and current_band_line and expected_band_line and current_band_line.strip() != expected_band_line.strip():
        metadata_notice = "band/stop levels align; suffix wording or update annotation differs"

    if current_band_line is None or current_stop_line is None:
        note_status = "missing band/stop line"
    elif changed:
        note_status = "sync needed"
    else:
        note_status = "already aligned"

    return BandMismatch(
        ticker=ticker,
        current_band_line=current_band_line,
        expected_band_line=expected_band_line,
        current_stop_line=current_stop_line,
        expected_stop_line=expected_stop_line,
        changed=changed,
        note_status=note_status,
        metadata_notice=metadata_notice,
    )



def build_report(mismatches: list[BandMismatch]) -> str:
    generated_at = datetime.now(timezone.utc).isoformat()
    needs_sync = [m for m in mismatches if m.changed or m.note_status != "already aligned"]
    metadata_only = [m for m in mismatches if not m.changed and m.metadata_notice]
    lines = [
        "# Band Note Sync",
        f"Generated at: {generated_at}",
        f"Canonical note: `{NOTE_PATH.relative_to(WORKSPACE)}`",
        "",
        "This report does not edit the note. It shows exact band/stop lines that should be synced manually or via a later gated helper.",
        "",
        f"Names reviewed: {len(mismatches)}",
        f"Names needing sync or review: {len(needs_sync)}",
        "",
    ]
    for item in needs_sync:
        lines.extend([
            f"## {item.ticker}",
            f"Status: {item.note_status}",
            "",
        ])
        if item.current_band_line:
            lines.append(f"Current band line: `{item.current_band_line}`")
        if item.expected_band_line:
            lines.append(f"Expected band line: `{item.expected_band_line}`")
        if item.current_stop_line:
            lines.append(f"Current stop line: `{item.current_stop_line}`")
        if item.expected_stop_line:
            lines.append(f"Expected stop line: `{item.expected_stop_line}`")
        if item.metadata_notice:
            lines.append(f"Note: {item.metadata_notice}")
        lines.append("")
    if metadata_only:
        lines.extend(["## Metadata-only differences", ""])
        for item in metadata_only:
            lines.append(f"- {item.ticker}: {item.metadata_notice}")
        lines.append("")
    if not needs_sync:
        lines.append("All tracked note band/stop values already align with portfolio-config.json.")
    return "\n".join(lines) + "\n"


def mismatch_to_dict(item: BandMismatch) -> dict[str, Any]:
    return {
        "ticker": item.ticker,
        "current_band_line": item.current_band_line,
        "expected_band_line": item.expected_band_line,
        "current_stop_line": item.current_stop_line,
        "expected_stop_line": item.expected_stop_line,
        "changed": item.changed,
        "note_status": item.note_status,
        "metadata_notice": item.metadata_notice,
    }


def build_json_report(mismatches: list[BandMismatch]) -> dict[str, Any]:
    needs_sync = [m for m in mismatches if m.changed or m.note_status != "already aligned"]
    missing_sections = [m.ticker for m in mismatches if m.note_status == "missing section in note"]
    metadata_only = [m for m in mismatches if not m.changed and m.metadata_notice]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_note": str(NOTE_PATH.relative_to(WORKSPACE)).replace("\\", "/"),
        "summary": {
            "reviewed": len(mismatches),
            "needs_sync": len(needs_sync),
            "missing_sections": len(missing_sections),
            "metadata_only": len(metadata_only),
        },
        "missing_section_tickers": missing_sections,
        "needs_sync_tickers": [m.ticker for m in needs_sync],
        "mismatches": [mismatch_to_dict(m) for m in mismatches],
    }



def main() -> int:
    args = parse_args()
    config = load_json(CONFIG_PATH)
    note_text = NOTE_PATH.read_text(encoding="utf-8")
    sections = extract_sections(note_text)
    entry_bands = config.get("entry_bands") or {}

    mismatches: list[BandMismatch] = []
    for ticker, band in entry_bands.items():
        if not isinstance(band, dict):
            continue
        if band.get("low") is None and band.get("high") is None and band.get("stop") is None:
            continue
        mismatches.append(compare_ticker(ticker, band, sections.get(ticker)))

    report = build_report(mismatches)
    out_path = Path(args.out)
    out_json_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(out_path, report, encoding="utf-8")
    atomic_write_json(out_json_path, build_json_report(mismatches), indent=2)
    needs_sync = sum(1 for m in mismatches if m.changed or m.note_status != "already aligned")
    print({
        "status": "ok",
        "out": str(out_path),
        "json_out": str(out_json_path),
        "reviewed": len(mismatches),
        "needs_sync": needs_sync,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
