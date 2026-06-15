#!/usr/bin/env python3
"""Local voice-note transcription helper for OpenClaw inbound media.

Default use:
    python scripts\\local_audio_transcriber.py --write --pretty

This helper resolves the newest local inbound audio file, bootstraps a local
Node/Whisper runtime if needed, and writes one transcript JSON. Audio stays on
the local machine; package/model downloads may occur only when the local cache
is missing and bootstrap is allowed.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
OPENCLAW_HOME = Path(os.environ.get("OPENCLAW_HOME", str(Path.home() / ".openclaw")))
INBOUND_MEDIA_DIR = OPENCLAW_HOME / "media" / "inbound"
TOOLS_DIR = ROOT / "tmp" / "audio-tools"
TRANSCRIPT_DIR = ROOT / "tmp" / "audio-transcripts"
NODE_HELPER = ROOT / "scripts" / "local_audio_transcriber_node.mjs"
DEFAULT_OUT = TRANSCRIPT_DIR / "latest-audio-transcript.json"
DEFAULT_MODEL = "Xenova/whisper-base.en"
DEPENDENCIES = ("ffmpeg-static", "@xenova/transformers", "wavefile")
AUDIO_EXTENSIONS = {".ogg", ".oga", ".opus", ".mp3", ".wav", ".m4a", ".webm"}

AUTHORITY_BOUNDARY = {
    "local_audio_read_allowed": True,
    "local_transcription_allowed": True,
    "external_transcription_upload_allowed": False,
    "telegram_message_send_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "config_auth_runtime_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def newest_inbound_audio(media_dir: Path = INBOUND_MEDIA_DIR) -> Path:
    if not media_dir.exists():
        raise FileNotFoundError(f"inbound_media_dir_not_found:{media_dir}")
    candidates = [
        path
        for path in media_dir.iterdir()
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    ]
    if not candidates:
        raise FileNotFoundError(f"no_inbound_audio_found:{media_dir}")
    return max(candidates, key=lambda item: item.stat().st_mtime)


def resolve_audio_path(value: str | None, *, latest: bool = False, media_dir: Path = INBOUND_MEDIA_DIR) -> Path:
    if latest or not value:
        return newest_inbound_audio(media_dir)

    raw = value.strip().strip('"')
    if raw.startswith("media://inbound/"):
        raw = raw.removeprefix("media://inbound/")
        return media_dir / raw
    if raw.startswith("inbound/"):
        return media_dir / raw.removeprefix("inbound/")

    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return path


def which_or_fail(name: str) -> str:
    found = shutil.which(name) or shutil.which(f"{name}.cmd") or shutil.which(f"{name}.ps1")
    if not found:
        raise RuntimeError(f"missing_runtime:{name}")
    return found


def dependency_ready(tools_dir: Path = TOOLS_DIR) -> bool:
    modules = tools_dir / "node_modules"
    return all((modules / dep).exists() for dep in DEPENDENCIES)


def bootstrap_tools(*, allow: bool, tools_dir: Path = TOOLS_DIR) -> dict[str, Any]:
    if dependency_ready(tools_dir):
        return {"status": "ready", "installed": False, "tools_dir": rel(tools_dir)}
    if not allow:
        return {
            "status": "missing",
            "installed": False,
            "tools_dir": rel(tools_dir),
            "install_command": f"npm install --prefix {tools_dir} {' '.join(DEPENDENCIES)}",
        }

    npm = which_or_fail("npm")
    tools_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [npm, "install", "--prefix", str(tools_dir), *DEPENDENCIES],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "status": "install_failed",
            "installed": False,
            "tools_dir": rel(tools_dir),
            "returncode": proc.returncode,
            "stderr_tail": proc.stderr[-2000:],
            "stdout_tail": proc.stdout[-1000:],
        }
    return {
        "status": "ready",
        "installed": True,
        "tools_dir": rel(tools_dir),
        "stdout_tail": proc.stdout[-1000:],
    }


def run_node_transcriber(audio_path: Path, *, model: str, timeout: int, keep_wav: bool = False) -> dict[str, Any]:
    node = which_or_fail("node")
    cmd = [
        node,
        str(NODE_HELPER),
        "--input",
        str(audio_path),
        "--model",
        model,
        "--tools-dir",
        str(TOOLS_DIR),
        "--cache-dir",
        str(TOOLS_DIR / ".cache"),
    ]
    if keep_wav:
        cmd.append("--keep-wav")
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False, timeout=timeout)
    if proc.returncode != 0:
        return {
            "status": "transcription_failed",
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-1000:],
            "stderr_tail": proc.stderr[-3000:],
        }
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        return {
            "status": "transcription_parse_failed",
            "error": str(exc),
            "stdout_tail": proc.stdout[-3000:],
            "stderr_tail": proc.stderr[-3000:],
        }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    warnings: list[str] = []
    audio_path = resolve_audio_path(args.audio, latest=args.latest)
    if not audio_path.exists():
        raise FileNotFoundError(f"audio_not_found:{audio_path}")
    if audio_path.suffix.lower() not in AUDIO_EXTENSIONS:
        warnings.append(f"unusual_audio_extension:{audio_path.suffix}")

    bootstrap = bootstrap_tools(allow=not args.no_bootstrap)
    if bootstrap["status"] != "ready":
        status = "blocked_missing_local_audio_tools"
        transcript: dict[str, Any] = {"status": status, "text": ""}
    elif args.dry_run:
        status = "ok"
        transcript = {"status": "dry_run", "text": ""}
    else:
        transcript = run_node_transcriber(audio_path, model=args.model, timeout=args.timeout, keep_wav=args.keep_wav)
        status = "ok" if transcript.get("status") == "ok" else str(transcript.get("status", "blocked"))

    payload = {
        "schema": "veritas.local_audio_transcriber.v1",
        "generated_at_utc": utc_now(),
        "status": status,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "input": {
            "requested_audio": args.audio,
            "latest": args.latest or not args.audio,
            "resolved_audio_path": str(audio_path.resolve()),
            "resolved_audio_path_relative": rel(audio_path),
            "size_bytes": audio_path.stat().st_size,
            "modified_utc": datetime.fromtimestamp(audio_path.stat().st_mtime, timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        },
        "local_tooling": bootstrap,
        "transcription": transcript,
        "summary": {
            "text": str(transcript.get("text", "")).strip(),
            "model": args.model,
            "local_only": True,
            "next_safe_action": "Use the transcript text in the visible reply; do not upload audio externally unless Randall explicitly approves.",
        },
        "warnings": warnings,
    }
    if args.validate and status != "ok":
        payload["validation_error"] = status
    return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe local OpenClaw inbound audio with a local Whisper model.")
    parser.add_argument("audio", nargs="?", help="Audio path, media://inbound/<file>, or omit for newest inbound audio.")
    parser.add_argument("--latest", action="store_true", help="Use newest audio file in ~/.openclaw/media/inbound.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Transformers.js ASR model.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Transcript JSON output path when --write is set.")
    parser.add_argument("--write", action="store_true", help="Write transcript JSON.")
    parser.add_argument("--pretty", action="store_true", help="Print compact human-readable output.")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero if transcription did not return text.")
    parser.add_argument("--dry-run", action="store_true", help="Resolve input and tooling without transcribing.")
    parser.add_argument("--no-bootstrap", action="store_true", help="Do not install local Node transcription dependencies if missing.")
    parser.add_argument("--keep-wav", action="store_true", help="Keep converted scratch WAV for debugging.")
    parser.add_argument("--timeout", type=int, default=180, help="Node transcription timeout in seconds.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    payload = build_payload(args)
    if args.write:
        atomic_write_json(args.out, payload)
    if args.pretty:
        text = payload["summary"]["text"]
        print(f"status={payload['status']}")
        print(f"audio={payload['input']['resolved_audio_path_relative']}")
        print(f"model={payload['summary']['model']}")
        print(f"text={text}")
        if args.write:
            print(f"out={rel(Path(args.out))}")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    if args.validate and payload["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
