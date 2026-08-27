"""Guard that compiled Go validator binaries are not stale relative to their source.

A fixed validator that was never recompiled will silently emit wrong results
(see 2026-06-07 audit: finance-sql-boundary-lint and sql-schema-drift-lint were
false-blocking on a healthy 200-row universe because the binary predated its
source fix). This guard compares each `scripts/go/bin/<name>.exe` against the
newest source in its actual local Go dependency graph plus the module files.
Dependency resolution is fail-closed so an incomplete graph cannot emit green.

Review-only. Detects staleness; it does not build anything.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from time import perf_counter
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

GO_PACKAGE_SOURCE_FIELDS = (
    "GoFiles",
    "CgoFiles",
    "CFiles",
    "CXXFiles",
    "MFiles",
    "HFiles",
    "FFiles",
    "SFiles",
    "SwigFiles",
    "SwigCXXFiles",
    "SysoFiles",
    "EmbedFiles",
)
GO_LIST_TIMEOUT_SECONDS = 120
GO_LIST_ALL_COMMANDS_TARGET = "./cmd/..."


class DependencyResolutionError(RuntimeError):
    """Raised when the local dependency graph cannot be proven."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path)


def newest_source(paths: list[Path]) -> tuple[float, str]:
    """Return ``(max_mtime, relpath)`` across explicit files or source roots."""
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


def _json_objects(raw: str) -> list[dict[str, Any]]:
    """Decode the concatenated JSON objects emitted by ``go list -json``."""

    decoder = json.JSONDecoder()
    offset = 0
    objects: list[dict[str, Any]] = []
    while offset < len(raw):
        while offset < len(raw) and raw[offset].isspace():
            offset += 1
        if offset >= len(raw):
            break
        try:
            value, offset = decoder.raw_decode(raw, offset)
        except json.JSONDecodeError as exc:
            raise DependencyResolutionError(f"go_list_invalid_json:{exc.msg}") from exc
        if not isinstance(value, dict):
            raise DependencyResolutionError("go_list_non_object_payload")
        objects.append(value)
    if not objects:
        raise DependencyResolutionError("go_list_empty_payload")
    return objects


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _error_detail(value: str, limit: int = 500) -> str:
    compact = " ".join(value.split())
    return compact[:limit] if compact else "no_error_detail"


def _run_go_list(
    go_root: Path,
    target: str,
    *,
    go_executable: str,
) -> list[dict[str, Any]]:
    """Resolve a Go package graph once, without changing module state."""

    try:
        completed = subprocess.run(
            [go_executable, "list", "-mod=readonly", "-deps", "-json", target],
            cwd=go_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=GO_LIST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise DependencyResolutionError(
            f"go_list_timed_out:after_{GO_LIST_TIMEOUT_SECONDS}s:{_error_detail(str(exc))}"
        ) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise DependencyResolutionError(f"go_list_launch_failed:{_error_detail(str(exc))}") from exc
    if completed.returncode != 0:
        detail = completed.stderr or completed.stdout
        raise DependencyResolutionError(
            f"go_list_failed:exit_{completed.returncode}:{_error_detail(detail)}"
        )
    return _json_objects(completed.stdout)


def _sources_for_command(
    go_root: Path,
    cmd_dir: Path,
    package_by_import_path: dict[str, dict[str, Any]],
) -> tuple[list[Path], list[str]]:
    """Collect actual local source files for one command from a resolved graph."""

    command_package = next(
        (
            package
            for package in package_by_import_path.values()
            if Path(str(package.get("Dir") or "")).resolve() == cmd_dir.resolve()
        ),
        None,
    )
    if command_package is None:
        raise DependencyResolutionError(f"command_not_in_go_list_output:{cmd_dir.name}")

    command_import_path = command_package.get("ImportPath")
    dependencies = command_package.get("Deps")
    if not isinstance(command_import_path, str) or not command_import_path:
        raise DependencyResolutionError(f"command_import_path_missing:{cmd_dir.name}")
    if not isinstance(dependencies, list) or not all(isinstance(dep, str) and dep for dep in dependencies):
        raise DependencyResolutionError(f"go_list_invalid_deps:{cmd_dir.name}")

    import_paths = set(dependencies)
    import_paths.add(command_import_path)
    sources: set[Path] = set()
    local_packages: set[str] = set()
    resolved_root = go_root.resolve()

    for import_path in import_paths:
        package = package_by_import_path.get(import_path)
        if package is None:
            continue
        package_dir_raw = package.get("Dir")
        if not isinstance(package_dir_raw, str) or not package_dir_raw:
            raise DependencyResolutionError(f"go_list_package_dir_missing:{cmd_dir.name}:{import_path}")
        package_dir = Path(package_dir_raw).resolve()
        if not _is_within(package_dir, resolved_root):
            continue
        local_packages.add(import_path)
        for field in GO_PACKAGE_SOURCE_FIELDS:
            names = package.get(field, [])
            if not isinstance(names, list):
                raise DependencyResolutionError(f"go_list_invalid_{field}:{cmd_dir.name}")
            for name in names:
                if not isinstance(name, str) or not name:
                    raise DependencyResolutionError(f"go_list_invalid_{field}_entry:{cmd_dir.name}")
                candidate = (package_dir / name).resolve()
                if _is_within(candidate, resolved_root) and candidate.is_file():
                    sources.add(candidate)

    # Keep command and module ownership explicit even if future Go output changes.
    sources.update(
        source.resolve()
        for source in cmd_dir.rglob("*.go")
        if source.is_file() and not source.name.endswith("_test.go")
    )
    go_mod = go_root / "go.mod"
    if not go_mod.is_file():
        raise DependencyResolutionError("go_mod_missing")
    sources.add(go_mod.resolve())
    go_sum = go_root / "go.sum"
    if go_sum.is_file():
        sources.add(go_sum.resolve())

    if not any(_is_within(source, cmd_dir) and source.suffix == ".go" for source in sources):
        raise DependencyResolutionError(f"command_source_missing:{cmd_dir.name}")
    return sorted(sources, key=lambda path: str(path).casefold()), sorted(local_packages)


def resolve_all_local_dependency_sources(
    go_root: Path,
    cmd_dirs: list[Path],
    *,
    go_executable: str = "go",
) -> dict[str, tuple[list[Path], list[str]]]:
    """Resolve every command from one Go graph scan.

    Running ``go list`` once avoids re-resolving the same module graph once per
    binary. The per-command source set remains exact because it is filtered by
    that command's ``Deps`` list.
    """

    packages = _run_go_list(
        go_root,
        GO_LIST_ALL_COMMANDS_TARGET,
        go_executable=go_executable,
    )
    resolved_root = go_root.resolve()
    package_by_import_path: dict[str, dict[str, Any]] = {}
    for package in packages:
        package_dir_raw = package.get("Dir")
        import_path = package.get("ImportPath")
        if not isinstance(package_dir_raw, str) or not package_dir_raw:
            continue
        if not isinstance(import_path, str) or not import_path:
            continue
        if _is_within(Path(package_dir_raw).resolve(), resolved_root):
            package_by_import_path[import_path] = package

    return {
        cmd_dir.name: _sources_for_command(go_root, cmd_dir, package_by_import_path)
        for cmd_dir in cmd_dirs
    }


def resolve_local_dependency_sources(
    go_root: Path,
    cmd_dir: Path,
    *,
    go_executable: str = "go",
) -> tuple[list[Path], list[str]]:
    """Resolve local files used to build one command without mutating the module.

    ``go list`` owns build-tag and import resolution. Only packages rooted inside
    this module are freshness inputs; standard-library and downloaded module
    cache mtimes must not stale locally built validators.
    """

    packages = _run_go_list(
        go_root,
        f"./cmd/{cmd_dir.name}",
        go_executable=go_executable,
    )
    resolved_root = go_root.resolve()
    package_by_import_path = {
        str(package["ImportPath"]): package
        for package in packages
        if isinstance(package.get("ImportPath"), str)
        and isinstance(package.get("Dir"), str)
        and _is_within(Path(str(package["Dir"])).resolve(), resolved_root)
    }
    return _sources_for_command(go_root, cmd_dir, package_by_import_path)


def build_packet(
    go_root: Path = GO_ROOT,
    *,
    go_executable: str = "go",
) -> dict[str, Any]:
    cmd_root = go_root / "cmd"
    bin_root = go_root / "bin"
    binaries: list[dict[str, Any]] = []
    stale: list[str] = []
    missing: list[str] = []
    resolution_failures: list[str] = []

    cmd_dirs = sorted(p for p in cmd_root.iterdir() if p.is_dir())
    dependency_sources_by_command: dict[str, tuple[list[Path], list[str]]] = {}
    resolution_error = ""
    discovery_started = perf_counter()
    try:
        dependency_sources_by_command = resolve_all_local_dependency_sources(
            go_root,
            cmd_dirs,
            go_executable=go_executable,
        )
    except DependencyResolutionError as exc:
        resolution_error = str(exc)
    discovery_elapsed_ms = round((perf_counter() - discovery_started) * 1000)

    for cmd_dir in cmd_dirs:
        name = cmd_dir.name
        binary = bin_root / f"{name}.exe"
        dependency_error = ""
        dependency_sources: list[Path] = []
        local_packages: list[str] = []
        try:
            dependency_sources, local_packages = dependency_sources_by_command[cmd_dir.name]
        except KeyError:
            dependency_error = resolution_error or f"command_dependency_result_missing:{cmd_dir.name}"
            resolution_failures.append(name)

        src_mtime, src_path = newest_source(dependency_sources)

        record: dict[str, Any] = {
            "binary": rel(binary),
            "binary_exists": binary.exists(),
            "newest_source": src_path,
            "dependency_resolution_status": "inconclusive" if dependency_error else "ok",
            "dependency_source_count": len(dependency_sources),
            "local_dependency_package_count": len(local_packages),
        }
        if dependency_error:
            record["dependency_resolution_error"] = dependency_error
        if not binary.exists():
            record["status"] = "critical"
            record["reason"] = "binary_missing"
            missing.append(name)
        elif dependency_error:
            record["status"] = "inconclusive"
            record["reason"] = "dependency_resolution_inconclusive"
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

    critical = (
        [f"missing_binary:{n}" for n in missing]
        + [f"stale_binary:{n}" for n in stale]
    )
    inconclusive = [f"dependency_resolution_inconclusive:{n}" for n in resolution_failures]
    status = "critical" if critical else "inconclusive" if inconclusive else "ok"
    return {
        "schema_version": 1,
        "status": status,
        "generated_at_utc": utc_now(),
        "authority": AUTHORITY,
        "binary_count": len(binaries),
        "stale_count": len(stale),
        "missing_count": len(missing),
        "dependency_resolution_error_count": len(resolution_failures),
        "dependency_discovery": {
            "status": "inconclusive" if resolution_error else "ok",
            "mode": "single_go_list_all_commands",
            "target": GO_LIST_ALL_COMMANDS_TARGET,
            "command_count": len(cmd_dirs),
            "elapsed_ms": discovery_elapsed_ms,
            "timeout_seconds": GO_LIST_TIMEOUT_SECONDS,
            "error": resolution_error or None,
        },
        "binaries": binaries,
        "critical_findings": critical,
        "inconclusive_findings": inconclusive,
        "remediation": "cd scripts\\go; foreach ($c in Get-ChildItem cmd -Directory) { go build -o (Join-Path bin ($c.Name + '.exe')) ('.\\cmd\\' + $c.Name) }",
        "operator_action": "NO_ESCALATION_NEEDED" if status == "ok" else "MAIN_HANDOFF_REQUIRED",
    }


def build_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Go Binary Freshness Guard",
        "",
        f"- Status: `{packet['status']}`",
        f"- Generated: `{packet['generated_at_utc']}`",
        f"- Binaries: `{packet['binary_count']}` | stale: `{packet['stale_count']}` | missing: `{packet['missing_count']}` | unresolved: `{packet['dependency_resolution_error_count']}`",
        "",
        "## Binaries",
        "",
    ]
    for b in packet["binaries"]:
        detail = b.get("reason", "fresh")
        lines.append(f"- `{b['binary']}`: `{b['status']}` ({detail})")
    if packet["critical_findings"]:
        lines.extend(["", "## Remediation", "", f"`{packet['remediation']}`"])
    if packet["inconclusive_findings"]:
        lines.extend(["", "## Inconclusive", ""])
        lines.extend(f"- `{finding}`" for finding in packet["inconclusive_findings"])
    lines.extend(["", "## Boundary", "", "Read-only freshness detection. This guard does not build binaries."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect stale compiled Go validator binaries.")
    parser.add_argument("--write", action="store_true", help="Write JSON proof artifact.")
    parser.add_argument("--write-md", action="store_true", help="Write Markdown proof artifact.")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Exit non-zero when freshness is not proven (stale, missing, or dependency resolution inconclusive).",
    )
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
