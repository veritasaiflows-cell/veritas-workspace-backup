#!/usr/bin/env python3
"""Local-only screen-recording capture helper for interactive training.

Inventories local clips under training/interactive-training-builder/recordings/,
writes a manifest plus a $0 capture README, and emits validation proof. It never
uploads media, never configures an LMS/LRS, and never opens a GUI during
validate/write. The optional --open-tool flag tries to launch the Windows
Snipping Tool screen recorder and degrades to printed steps on failure.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text


ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "training" / "interactive-training-builder"
RECORDINGS = TRAINING / "recordings"
MANIFEST = RECORDINGS / "manifest.json"
README = RECORDINGS / "README.md"
GITKEEP = RECORDINGS / ".gitkeep"
PROOF = ROOT / "tmp" / "interactive-training-screen-capture-proof.json"

CLIP_EXTENSIONS = {".webm", ".mp4"}
CLIP_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,80}\.(webm|mp4)$")

CAPTURE_STEPS = [
    "Press Win+Shift+R or open Snipping Tool and switch to video capture.",
    "Record the walkthrough (keep it short and free of customer data or credentials).",
    "Save the file under training/interactive-training-builder/recordings/ as .webm or .mp4.",
    "Rerun python scripts\\interactive_training_screen_capture.py --write --validate, then rebuild the training modules.",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def is_safe_clip_name(name: str) -> bool:
    if not isinstance(name, str) or not name:
        return False
    if "://" in name or ".." in name or "\\" in name:
        return False
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        return False
    return CLIP_NAME_RE.match(name) is not None


def inventory_recordings(recordings_dir: Path = RECORDINGS) -> tuple[list[dict[str, Any]], list[str]]:
    clips: list[dict[str, Any]] = []
    warnings: list[str] = []
    if not recordings_dir.exists():
        return clips, warnings
    for path in sorted(recordings_dir.iterdir()):
        if not path.is_file():
            continue
        if path.name in {"manifest.json", "README.md", ".gitkeep"}:
            continue
        if path.suffix.lower() in CLIP_EXTENSIONS and is_safe_clip_name(path.name):
            clips.append(
                {
                    "file": f"recordings/{path.name}",
                    "name": path.name,
                    "size_bytes": path.stat().st_size,
                }
            )
        else:
            warnings.append(f"unrecognized_recording_file:{path.name}")
    return clips, warnings


def render_recordings_readme(clips: list[dict[str, Any]]) -> str:
    lines = [
        "# Local Screen Recordings ($0)",
        "",
        "Local clips for the interactive training modules live in this folder.",
        "No LMS, no YouTube, no upload: everything stays on this machine.",
        "",
        "## Capture (Windows, $0)",
        "",
    ]
    for index, step in enumerate(CAPTURE_STEPS, start=1):
        lines.append(f"{index}. {step}")
    lines.extend(
        [
            "",
            "## Current clips",
            "",
        ]
    )
    if clips:
        for clip in clips:
            lines.append(f"- `{clip['file']}` ({clip['size_bytes']} bytes)")
    else:
        lines.append("- None yet. Modules render a capture placeholder until a clip lands here.")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Local files only.",
            "- No external upload, LMS, LRS, or public delivery.",
            "- No customer data, credentials, or account action in clips.",
            "",
        ]
    )
    return "\n".join(lines)


def build(write: bool = False, recordings_dir: Path = RECORDINGS, proof_path: Path = PROOF) -> dict[str, Any]:
    clips, warnings = inventory_recordings(recordings_dir)
    errors: list[str] = []
    for clip in clips:
        if not is_safe_clip_name(clip["name"]):
            errors.append(f"unsafe_clip_name:{clip['name']}")
    proof = {
        "schema": "veritas.interactive_training_screen_capture_proof.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if not errors else "blocked",
        "recordings_dir": rel(recordings_dir),
        "manifest": rel(recordings_dir / "manifest.json"),
        "clips": clips,
        "counts": {"clips": len(clips)},
        "validation": {"errors": errors, "warnings": warnings},
        "capture_steps": CAPTURE_STEPS,
        "authority_boundary": {
            "local_files_only": True,
            "external_upload_allowed": False,
            "lms_configured": False,
            "customer_data_allowed": False,
        },
    }
    if write:
        recordings_dir.mkdir(parents=True, exist_ok=True)
        manifest_payload = {
            "schema": "veritas.interactive_training_recordings_manifest.v1",
            "generated_at_utc": proof["generated_at_utc"],
            "clips": clips,
            "counts": proof["counts"],
            "authority_boundary": proof["authority_boundary"],
        }
        atomic_write_json(recordings_dir / "manifest.json", manifest_payload)
        atomic_write_text(recordings_dir / "README.md", render_recordings_readme(clips))
        gitkeep = recordings_dir / ".gitkeep"
        if not gitkeep.exists():
            atomic_write_text(gitkeep, "")
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(proof_path, proof)
    return proof


def open_capture_tool() -> dict[str, Any]:
    """Best-effort launch of the Windows Snipping Tool screen recorder.

    Never raises: returns a status dict and prints fallback steps instead.
    """
    attempts = [
        ("ms-screenclip-protocol", ["explorer.exe", "ms-screenclip:"]),
        ("snipping-tool", ["snippingtool.exe"]),
    ]
    last_error = "launch failed"
    for label, command in attempts:
        try:
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # noqa: S603
            return {"status": "launched", "via": label, "steps": CAPTURE_STEPS}
        except Exception as exc:  # noqa: BLE001 - best-effort GUI launch
            last_error = f"{label}: {exc}"
    return {
        "status": "unavailable",
        "via": None,
        "error": last_error,
        "steps": CAPTURE_STEPS,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--open-tool", action="store_true")
    args = parser.parse_args()
    if args.open_tool:
        print(json.dumps(open_capture_tool(), indent=2, sort_keys=True))
        return 0
    proof = build(write=args.write)
    print(json.dumps(proof, indent=2, sort_keys=True))
    if args.validate and proof["validation"]["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
