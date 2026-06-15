"""Guard that compiled Go validator binaries are not stale relative to their source.

A fixed validator that was never recompiled will silently emit wrong results
(see 2026-06-07 audit: finance-sql-boundary-lint and sql-schema-drift-lint were
false-blocking on a healthy 200-row universe because the binary predated its
source fix). This guard compares each `scripts/go/bin/<name>.exe` against the
newest source it depends on (its own `cmd/<name>` directory plus the shared
`internal/` tree and module files) and flags any binary older than its source.

Review-only. Detects staleness; it does not build anything.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

WORKSPACE = Path(__file__).resolve().parents[1]
GO_ROOT = WORKSPACE / "scripts" / "go"
CMD_ROOT = GO_ROOT / "cmd"
BIN_ROOT = GO_ROOT / "bin"
INTERNAL_ROOT = GO_ROOT / "internal"
TMP = WORKSPACE / "tmp"
OUT_JSON = TMP / "go-binary-freshness-guard.json"
OUT_MD = OUT_JSON.with_suffix(".md")

AUTHORITY = {
    "posture": "read_only_go_binary_freshness_guard",
    "review_only": True,
    "builds_binaries": False,
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "paper_or_live_trade_allowed": False,
    "account_or_credential_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path)


def newest_source(paths: list[Path]) -> tuple[float, str]:
    """Return (max_mtime, relpath) across all non-test .go files under the given roots."""
    newest_mtime = 0.0
    newest_path = ""
    candidates: list[Path] = []
    for root in paths:
        if root.is_file():
            candidates.append(root)
        elif root.is_dir():
            candidates.extend(root.rglob("*.go"))
    for src in candidates:
        if src.name.endswith("_test.go"):
            continue
        mtime = src.stat().st_mtime
        if mtime > newest_mtime:
            newest_mtime = mtime
            newest_path = rel(src)
    return newest_mtime, newest_path


def build_packet() -> dict[str, Any]:
    # Shared sources every binary depends on: the whole internal tree + module files.
    shared_roots = [INTERNAL_ROOT, GO_ROOT / "go.mod", GO_ROOT / "go.sum"]
    shared_mtime, shared_path = newest_source(shared_roots)

    binaries: list[dict[str, Any]] = []
    stale: list[str] = []
    missing: list[str] = []

    cmd_dirs = sorted(p for p in CMD_ROOT.iterdir() if p.is_dir())
    for cmd_dir in cmd_dirs:
        name = cmd_dir.name
        binary = BIN_ROOT / f"{name}.exe"
        cmd_mtime, cmd_path = newest_source([cmd_dir])
        src_mtime = max(cmd_mtime, shared_mtime)
        src_path = cmd_path if cmd_mtime >= shared_mtime else shared_path

        record: dict[str, Any] = {
            "binary": f"scripts/go/bin/{name}.exe",
            "binary_exists": binary.exists(),
            "newest_source": src_path,
        }
        if not binary.exists():
            record["status"] = "critical"
            record["reason"] = "binary_missing"
            missing.append(name)
        else:
            bin_mtime = binary.stat().st_mtime
            age_lag_s = round(src_mtime - bin_mtime, 1)
            record.update(
                {
                    "binary_mtime_utc": datetime.fromtimestamp(bin_mtime, timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "source_mtime_utc": datetime.fromtimestamp(src_mtime, timezone.utc)
                    .replace(microsecond=0)
                    .isoformat()
                    .replace("+00:00", "Z"),
                    "source_newer_than_binary_seconds": age_lag_s,
                }
            )
            if src_mtime > bin_mtime:
                record["status"] = "critical"
                record["reason"] = "binary_older_than_source_rebuild_required"
                stale.append(name)
            else:
                record["status"] = "ok"
        binaries.append(record)

    critical = [f"missing_binary:{n}" for n in missing] + [f"stale_binary:{n}" for n in stale]
    status = "critical" if critical else "ok"
    return {
        "schema_version": 1,
        "status": status,
        "generated_at_utc": utc_now(),
        "authority": AUTHORITY,
        "binary_count": len(binaries),
        "stale_count": len(stale),
        "missing_count": len(missing),
        "binaries": binaries,
        "critical_findings": critical,
        "remediation": "cd scripts\\go; foreach ($c in Get-ChildItem cmd -Directory) { go build -o (Join-Path bin ($c.Name + '.exe')) ('.\\cmd\\' + $c.Name) }",
        "operator_action": "NO_ESCALATION_NEEDED" if status == "ok" else "MAIN_HANDOFF_REQUIRED",
    }


def build_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Go Binary Freshness Guard",
        "",
        f"- Status: `{packet['status']}`",
        f"- Generated: `{packet['generated_at_utc']}`",
        f"- Binaries: `{packet['binary_count']}` | stale: `{packet['stale_count']}` | missing: `{packet['missing_count']}`",
        "",
        "## Binaries",
        "",
    ]
    for b in packet["binaries"]:
        detail = b.get("reason", "fresh")
        lines.append(f"- `{b['binary']}`: `{b['status']}` ({detail})")
    if packet["critical_findings"]:
        lines.extend(["", "## Remediation", "", f"`{packet['remediation']}`"])
    lines.extend(["", "## Boundary", "", "Read-only freshness detection. This guard does not build binaries."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect stale compiled Go validator binaries.")
    parser.add_argument("--write", action="store_true", help="Write JSON proof artifact.")
    parser.add_argument("--write-md", action="store_true", help="Write Markdown proof artifact.")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero when any binary is stale or missing.")
    args = parser.parse_args()

    packet = build_packet()
    if args.write:
        atomic_write_json(OUT_JSON, packet)
    if args.write_md:
        atomic_write_text(OUT_MD, build_markdown(packet))

    print(
        json.dumps(
            {
                "status": packet["status"],
                "out": rel(OUT_JSON),
                "stale_count": packet["stale_count"],
                "missing_count": packet["missing_count"],
                "critical": packet["critical_findings"],
            },
            indent=2,
        )
    )
    if args.validate and packet["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
