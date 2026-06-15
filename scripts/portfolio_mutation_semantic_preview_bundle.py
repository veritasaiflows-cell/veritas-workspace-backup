from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_apply_helper as apply_helper
import portfolio_mutation_patch_preview_validator as patch_validator
import portfolio_mutation_semantic_patch_generator as semantic_generator
import proposal_patch_scope_validator as scope_validator

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "tmp" / "portfolio-mutation-proposals" / "semantic-preview-bundle.json"
OUT_MD = ROOT / "tmp" / "portfolio-mutation-proposals" / "semantic-preview-bundle.md"
CATEGORIES = semantic_generator.SUPPORTED_CATEGORIES


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path | None) -> str | None:
    if path is None:
        return None
    return str(path.relative_to(ROOT)).replace("\\", "/")


def build_category(bundle_path: Path, ticker: str, category: str, write_material: bool) -> dict[str, Any]:
    record: dict[str, Any] = {"category": category, "ticker": ticker, "status": "blocked"}
    try:
        packet = semantic_generator.build_augmented_packet(bundle_path, None, ticker, category)
        validation = semantic_generator.validation_summary(packet, bundle_path)
        material_json = material_md = None
        if write_material:
            material_json, material_md = semantic_generator.write_outputs(packet, category)
        preview = apply_helper.build_preview(material_json if material_json else bundle_path, packet.get("proposal_id"), "post-close") if material_json else None
        preview_json = preview_md = None
        if preview and write_material:
            preview_json, preview_md = apply_helper.write_outputs(preview)
        scope_report = scope_validator.build_report(material_json if material_json else bundle_path) if material_json else None
        patch_report = patch_validator.build_report(material_json if material_json else bundle_path, packet.get("proposal_id")) if material_json else None
        critical = int(validation.get("critical_count") or 0)
        critical += int((scope_report or {}).get("summary", {}).get("critical") or 0)
        critical += int((patch_report or {}).get("summary", {}).get("critical") or 0)
        change = (packet.get("exact_patch_preview") or {}).get("changes", [{}])[0]
        record.update({
            "status": "ok" if critical == 0 else "blocked",
            "proposal_id": packet.get("proposal_id"),
            "target_file": change.get("target_file"),
            "old_text_len": len(str(change.get("old_text") or "")),
            "new_text_len": len(str(change.get("new_text") or "")),
            "material_json": rel(material_json),
            "material_md": rel(material_md),
            "preview_json": rel(preview_json),
            "preview_md": rel(preview_md),
            "scope_status": (scope_report or {}).get("status"),
            "patch_preview_status": (patch_report or {}).get("status"),
            "critical": critical,
            "writes_performed": False,
        })
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "semantic note already current" in message:
            record.update({"status": "already_current", "error": message[:500], "critical": 0, "writes_performed": False})
        else:
            record.update({"status": "blocked", "error": message[:500], "critical": 1, "writes_performed": False})
    return record


def build_bundle(tickers: list[str] | str, categories: list[str], write_material: bool) -> dict[str, Any]:
    if isinstance(tickers, str):
        tickers = [tickers]
    bundle_path = ROOT / "tmp" / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
    rows = [
        build_category(bundle_path, ticker.upper(), category, write_material)
        for ticker in tickers
        for category in categories
    ]
    critical = sum(int(row.get("critical") or 0) for row in rows)
    generated_ok = sum(1 for row in rows if row.get("status") == "ok")
    already_current = sum(1 for row in rows if row.get("status") == "already_current")
    ok = generated_ok + already_current
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": "ok" if critical == 0 else "blocked",
        "tickers": tickers,
        "ticker": tickers[0] if len(tickers) == 1 else "MULTI",
        "authority": {
            "preview_only": True,
            "writes_performed": False,
            "owner_file_write_allowed_by_bundle": False,
            "standing_or_scoped_approval_required_before_apply": True,
            "trade_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            "tickers_requested": len(tickers),
            "categories_requested": len(categories),
            "rows_checked": len(rows),
            "categories_ok": ok,
            "freshly_generated_ok": generated_ok,
            "already_current": already_current,
            "critical": critical,
        },
        "categories": rows,
        "next_gate": "For any useful non-duplicative category, create a standing/scoped approval artifact from the material + preview, then use the approval-gated apply helper and post-apply validation chain.",
    }


def write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# WF64 Semantic Preview Bundle",
        "",
        f"- Generated: `{report['generated_at_utc']}`",
        f"- Ticker(s): `{', '.join(report.get('tickers') or [report.get('ticker')])}`",
        f"- Status: **{report['status']}**",
        "- Authority: preview-only; no owner-file writes; standing/scoped approval required before apply; no external financial action authority.",
        "",
        "| Category | Status | Target | Material | Preview | Critical |",
        "|---|---|---|---|---|---:|",
    ]
    for row in report.get("categories") or []:
        target = row.get("target_file") or "already current"
        material = row.get("material_json") or "not regenerated"
        preview = row.get("preview_json") or "not regenerated"
        lines.append(
            f"| `{row.get('category')}` | {row.get('status')} | `{target}` | `{material}` | `{preview}` | {row.get('critical')} |"
        )
    lines.extend(["", "## Next gate", "", str(report.get("next_gate") or "")])
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a WF64 semantic preview bundle/report for requested maintenance categories.")
    parser.add_argument("--ticker", default="ETN", help="Single ticker to preview; retained for compatibility.")
    parser.add_argument("--tickers", nargs="+", help="Optional multi-ticker pilot set.")
    parser.add_argument("--categories", nargs="+", default=list(CATEGORIES), choices=CATEGORIES)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    tickers = [item.upper() for item in (args.tickers or [args.ticker])]
    report = build_bundle(tickers, list(args.categories), args.write)
    if args.write:
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        write_markdown(report)
        print(f"wrote {OUT_JSON}")
        print(f"wrote {OUT_MD}")
    print(json.dumps({"status": report["status"], **report["summary"], "writes_performed": False}, indent=2))
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
