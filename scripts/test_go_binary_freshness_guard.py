from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

import go_binary_freshness_guard as guard


pytestmark = pytest.mark.skipif(shutil.which("go") is None, reason="Go is required for dependency resolution")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def set_mtime(path: Path, value: float) -> None:
    os.utime(path, (value, value))


def module_fixture(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    go_root = tmp_path / "go"
    files = {
        "go_mod": go_root / "go.mod",
        "go_sum": go_root / "go.sum",
        "main": go_root / "cmd" / "sample" / "main.go",
        "used": go_root / "internal" / "used" / "used.go",
        "unrelated": go_root / "internal" / "unrelated" / "unrelated.go",
        "binary": go_root / "bin" / "sample.exe",
    }
    write(files["go_mod"], "module example.test/freshness\n\ngo 1.22\n")
    write(files["go_sum"], "")
    write(
        files["main"],
        'package main\n\nimport "example.test/freshness/internal/used"\n\nfunc main() { used.Use() }\n',
    )
    write(files["used"], "package used\n\nfunc Use() {}\n")
    write(files["unrelated"], "package unrelated\n\nfunc Ignore() {}\n")
    write(files["binary"], "compiled-placeholder")
    for path in files.values():
        set_mtime(path, 1_700_000_000)
    set_mtime(files["binary"], 1_700_000_100)
    return go_root, files


def add_second_command(go_root: Path, files: dict[str, Path]) -> None:
    second_main = go_root / "cmd" / "second" / "main.go"
    second_binary = go_root / "bin" / "second.exe"
    write(
        second_main,
        'package main\n\nimport "example.test/freshness/internal/used"\n\nfunc main() { used.Use() }\n',
    )
    write(second_binary, "compiled-placeholder")
    set_mtime(second_main, 1_700_000_000)
    set_mtime(second_binary, 1_700_000_100)


def record(packet: dict, name: str = "sample") -> dict:
    return next(item for item in packet["binaries"] if Path(item["binary"]).stem == name)


def test_unrelated_internal_package_does_not_stale_binary(tmp_path: Path) -> None:
    go_root, files = module_fixture(tmp_path)
    set_mtime(files["unrelated"], 1_700_000_200)

    packet = guard.build_packet(go_root)

    assert packet["status"] == "ok"
    assert packet["stale_count"] == 0
    assert record(packet)["dependency_source_count"] == 4
    assert record(packet)["local_dependency_package_count"] == 2


def test_actual_dependency_stales_binary(tmp_path: Path) -> None:
    go_root, files = module_fixture(tmp_path)
    set_mtime(files["used"], 1_700_000_200)

    packet = guard.build_packet(go_root)

    assert packet["status"] == "critical"
    assert packet["stale_count"] == 1
    assert packet["critical_findings"] == ["stale_binary:sample"]
    assert record(packet)["reason"] == "binary_older_than_source_rebuild_required"


def test_missing_binary_remains_critical(tmp_path: Path) -> None:
    go_root, files = module_fixture(tmp_path)
    files["binary"].unlink()

    packet = guard.build_packet(go_root)

    assert packet["status"] == "critical"
    assert packet["missing_count"] == 1
    assert packet["critical_findings"] == ["missing_binary:sample"]
    assert record(packet)["reason"] == "binary_missing"


@pytest.mark.parametrize("module_file", ["go_mod", "go_sum"])
def test_module_file_change_stales_binary(tmp_path: Path, module_file: str) -> None:
    go_root, files = module_fixture(tmp_path)
    set_mtime(files[module_file], 1_700_000_200)

    packet = guard.build_packet(go_root)

    assert packet["status"] == "critical"
    assert packet["stale_count"] == 1
    assert record(packet)["newest_source"].endswith(Path(files[module_file]).name)


def test_build_packet_resolves_all_commands_in_one_go_list_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    go_root, files = module_fixture(tmp_path)
    add_second_command(go_root, files)
    original_run = guard.subprocess.run
    calls: list[list[str]] = []

    def spy_run(args: list[str], *args_tail: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return original_run(args, *args_tail, **kwargs)

    monkeypatch.setattr(guard.subprocess, "run", spy_run)

    packet = guard.build_packet(go_root)

    assert packet["status"] == "ok"
    assert len(calls) == 1
    assert calls[0][-1] == "./cmd/..."
    assert packet["dependency_discovery"]["command_count"] == 2
    assert packet["dependency_discovery"]["mode"] == "single_go_list_all_commands"


def test_dependency_resolution_failure_is_inconclusive(tmp_path: Path) -> None:
    go_root, files = module_fixture(tmp_path)
    write(
        files["main"],
        'package main\n\nimport "example.test/freshness/internal/missing"\n\nfunc main() {}\n',
    )
    set_mtime(files["main"], 1_700_000_000)

    packet = guard.build_packet(go_root)

    assert packet["status"] == "inconclusive"
    assert packet["dependency_resolution_error_count"] == 1
    assert packet["critical_findings"] == []
    assert "dependency_resolution_inconclusive:sample" in packet["inconclusive_findings"]
    assert record(packet)["reason"] == "dependency_resolution_inconclusive"
    assert record(packet)["dependency_resolution_status"] == "inconclusive"


def test_dependency_resolution_timeout_is_inconclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    go_root, _ = module_fixture(tmp_path)

    def timeout_run(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(["go", "list"], guard.GO_LIST_TIMEOUT_SECONDS)

    monkeypatch.setattr(guard.subprocess, "run", timeout_run)

    packet = guard.build_packet(go_root)

    assert packet["status"] == "inconclusive"
    assert packet["critical_findings"] == []
    assert packet["dependency_discovery"]["status"] == "inconclusive"
    assert "go_list_timed_out" in str(packet["dependency_discovery"]["error"])
