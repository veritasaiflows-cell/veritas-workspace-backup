"""Hidden-bank deterministic host runner (Spark slice).

Scores any named model on the frozen 12-case visible bank without
exposing hidden keys to the candidate mount.

Modes:
  python scripts/arena_hidden_bank_runner.py --visible V --hidden H \
      --isolation I --out DIR [--model NAME] --dry-run
  python scripts/arena_hidden_bank_runner.py --visible V --hidden H \
      --out DIR [--isolation I] [--model NAME] --grade-file responses.json

Grade-file input shape: {"<instance_id>": "<raw response text>", ...}.
Writes OUT/graded-results.json. Both modes create OUT/candidate-mount/
(visible bank only) and OUT/control/run-contract.json (outside the mount).
Live OpenClaw spawn is out of this slice.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import hashlib
import json
import sys
from pathlib import Path

# Import the generator module for strict JSON + strict equality.
# Do not copy the generator: load the sibling file directly.
_GENERATOR_PATH = Path(__file__).with_name("arena_agentic_expansion.py")
try:
    import importlib.util as _ilu

    _spec = _ilu.spec_from_file_location(
        "arena_agentic_expansion", str(_GENERATOR_PATH)
    )
    if _spec is None or _spec.loader is None:  # pragma: no cover
        raise ImportError("cannot locate arena_agentic_expansion spec")
    _gen = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_gen)
    parse_strict_json_object = _gen.parse_strict_json_object
    strict_equal = _gen.strict_equal
    GENERATOR_VERSION = getattr(_gen, "GENERATOR_VERSION", "unknown")
    ENVELOPE_ID = getattr(_gen, "ENVELOPE_ID", "unknown")
    CANDIDATE_ALLOWLIST = list(getattr(_gen, "CANDIDATE_ALLOWLIST", ["candidate-visible-bank.json"]))
    HIDDEN_FILENAMES = list(getattr(_gen, "HIDDEN_FILENAMES", []))
except Exception as exc:  # fail closed: strict helpers are mandatory
    raise SystemExit(f"runner_unavailable_generator_import: {exc}")


EXPECTED_ALLOWLIST = ["candidate-visible-bank.json"]
EXPECTED_MOUNT_FILENAME = "candidate-visible-bank.json"
HIDDEN_FIELD_TOKENS = ("key", "structure_id", "family_trap", "expected_trace")
FORBIDDEN_VISIBLE_SUBSTRINGS = (
    '"structure_id"',
    '"family_trap"',
    '"expected_trace"',
    '"forbidden_reads"',
)


def _fail(msg: str) -> "NoReturn":
    raise SystemExit(f"runner_fail_closed: {msg}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _fail(f"missing_file:{path}")
    except json.JSONDecodeError as exc:
        _fail(f"invalid_json:{path}:{exc}")
    except OSError as exc:
        _fail(f"unreadable_file:{path}:{exc}")


def check_isolation(isolation: dict) -> None:
    """Enforce the candidate-mount allowlist exactly; fail closed."""
    allowlist = isolation.get("candidate_mount_allowlist")
    if allowlist != EXPECTED_ALLOWLIST:
        _fail(f"allowlist_mismatch:{allowlist!r}")
    # Hidden filenames must never be mountable: none may appear in allowlist.
    for name in HIDDEN_FILENAMES:
        if name in (allowlist or []):
            _fail(f"hidden_in_allowlist:{name}")
    if isolation.get("candidate_visible_only") is not True:
        _fail("isolation_not_visible_only")


def index_cases(doc: dict, label: str) -> dict:
    cases = doc.get("cases")
    if not isinstance(cases, list):
        _fail(f"{label}_cases_not_list")
    out = {}
    for entry in cases:
        if not isinstance(entry, dict):
            _fail(f"{label}_case_not_object")
        iid = entry.get("instance_id")
        if not isinstance(iid, str) or not iid:
            _fail(f"{label}_case_missing_id")
        if iid in out:
            _fail(f"{label}_duplicate_id:{iid}")
        out[iid] = entry
    return out


def check_banks(visible: dict, hidden: dict) -> tuple[dict, dict]:
    vmap = index_cases(visible, "visible")
    hmap = index_cases(hidden, "hidden")
    if len(vmap) != 12 or len(hmap) != 12:
        _fail(f"bank_size:visible={len(vmap)}:hidden={len(hmap)}")
    if set(vmap) != set(hmap):
        missing = sorted(set(hmap) - set(vmap))
        extra = sorted(set(vmap) - set(hmap))
        _fail(f"bank_id_mismatch:missing={missing}:extra={extra}")
    for iid, vcase in vmap.items():
        blob = json.dumps(vcase, sort_keys=True, separators=(",", ":"))
        for token in FORBIDDEN_VISIBLE_SUBSTRINGS:
            if token in blob:
                _fail(f"hidden_leak_visible:{token}:{iid}")
        # The whole hidden key must not appear verbatim inside the visible case.
        key_blob = json.dumps(
            hmap[iid].get("key"), sort_keys=True, separators=(",", ":")
        )
        if key_blob in blob:
            _fail(f"whole_key_leak:{iid}")
        for fn in HIDDEN_FILENAMES:
            if fn in blob:
                _fail(f"hidden_filename_in_visible:{fn}:{iid}")
    return vmap, hmap


def grade_text(visible_case: dict, hidden_case: dict, response_text: str) -> dict:
    """Grade one raw response against hidden['key'] with strict helpers."""
    if not isinstance(hidden_case, dict) or "key" not in hidden_case:
        _fail("hidden_case_missing_key")
    parsed, error = parse_strict_json_object(response_text)
    factual = parsed is not None and bool(strict_equal(parsed, hidden_case["key"]))
    result = {
        "instance_id": hidden_case.get("instance_id"),
        "family": hidden_case.get("family"),
        "json_valid": parsed is not None,
        "factual": factual,
        "strict_pass": parsed is not None and error is None and factual,
        "parse_error": error,
    }
    return result


def build_dry_run(vmap: dict) -> list:
    items = []
    for iid in sorted(vmap):
        vcase = vmap[iid]
        if "prompt" not in vcase or "family" not in vcase:
            _fail(f"visible_case_missing_fields:{iid}")
        entry = {
            "instance_id": iid,
            "family": vcase["family"],
            "prompt": copy.deepcopy(vcase["prompt"]),
        }
        blob = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        for token in HIDDEN_FIELD_TOKENS:
            if f'"{token}"' in blob:
                _fail(f"hidden_field_in_dry_run:{token}:{iid}")
        items.append(entry)
    return items


def write_mount(visible_path: Path, out_dir: Path) -> Path:
    mount = out_dir / "candidate-mount"
    mount.mkdir(parents=True, exist_ok=True)
    # Mount must contain only the visible bank under the allowlisted name.
    for child in sorted(mount.iterdir()):
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            import shutil

            shutil.rmtree(child)
    dest = mount / EXPECTED_MOUNT_FILENAME
    dest.write_bytes(visible_path.read_bytes())
    # Verify: exactly one file, byte-identical to the visible source.
    leftovers = sorted(p.name for p in mount.iterdir())
    if leftovers != [EXPECTED_MOUNT_FILENAME]:
        _fail(f"mount_not_visible_only:{leftovers!r}")
    mounted_bytes = dest.read_bytes()
    mounted_doc = json.loads(mounted_bytes.decode("utf-8"))
    blob = json.dumps(mounted_doc, sort_keys=True, separators=(",", ":"))
    for token in FORBIDDEN_VISIBLE_SUBSTRINGS:
        if token in blob:
            _fail(f"hidden_leak_mount:{token}")
    return mount


def write_contract(
    out_dir: Path,
    model: str,
    visible_bytes: bytes,
    hidden_bytes: bytes,
    isolation_bytes: bytes | None,
) -> Path:
    control = out_dir / "control"
    control.mkdir(parents=True, exist_ok=True)
    contract = {
        "model": model,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "envelope": ENVELOPE_ID,
        "generator_version": GENERATOR_VERSION,
        "visible_sha256": sha256_bytes(visible_bytes),
        "hidden_sha256": sha256_bytes(hidden_bytes),
        "isolation_sha256": sha256_bytes(isolation_bytes) if isolation_bytes else None,
        "mount_allowlist": list(EXPECTED_ALLOWLIST),
        "note": "control-plane artifact; never placed inside candidate-mount",
    }
    dest = control / "run-contract.json"
    dest.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return dest


def load_grade_map(grade_file: Path) -> dict:
    doc = load_json(grade_file)
    if isinstance(doc, dict) and isinstance(doc.get("responses"), dict):
        mapping = doc["responses"]
    elif isinstance(doc, dict):
        mapping = doc
    else:
        _fail("grade_file_not_object_map")
    for key, value in mapping.items():
        if not isinstance(value, str):
            _fail(f"grade_file_value_not_string:{key}")
    return mapping


def run_grade(
    vmap: dict, hmap: dict, mapping: dict, model: str
) -> dict:
    vids, gids = set(vmap), set(mapping)
    if vids != gids:
        _fail(
            f"grade_id_mismatch:missing={sorted(vids - gids)}:extra={sorted(gids - vids)}"
        )
    results = []
    for iid in sorted(vids):
        graded = grade_text(vmap[iid], hmap[iid], mapping[iid])
        results.append(graded)
    passed = sum(1 for r in results if r["strict_pass"])
    return {
        "model": model,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total": len(results),
        "strict_pass_count": passed,
        "results": results,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Deterministic hidden-bank host runner."
    )
    parser.add_argument("--visible", required=True, help="Visible bank JSON path")
    parser.add_argument("--hidden", required=True, help="Hidden bank JSON path")
    parser.add_argument("--isolation", default=None, help="Isolation JSON path")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument("--model", default="unnamed-candidate")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--grade-file", default=None)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.dry_run and args.grade_file:
        _fail("dry_run_and_grade_file_exclusive")
    if not args.dry_run and not args.grade_file:
        _fail("need_dry_run_or_grade_file")
    visible_path = Path(args.visible)
    hidden_path = Path(args.hidden)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    visible_bytes = visible_path.read_bytes() if visible_path.exists() else None
    if visible_bytes is None:
        _fail(f"missing_file:{visible_path}")
    hidden_bytes = hidden_path.read_bytes() if hidden_path.exists() else None
    if hidden_bytes is None:
        _fail(f"missing_file:{hidden_path}")
    try:
        visible = json.loads(visible_bytes.decode("utf-8"))
        hidden = json.loads(hidden_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        _fail(f"invalid_json:{exc}")

    isolation_bytes = None
    if args.isolation:
        isolation_path = Path(args.isolation)
        if not isolation_path.exists():
            _fail(f"missing_file:{isolation_path}")
        isolation_bytes = isolation_path.read_bytes()
        try:
            isolation = json.loads(isolation_bytes.decode("utf-8"))
        except json.JSONDecodeError as exc:
            _fail(f"invalid_json:isolation:{exc}")
        check_isolation(isolation)
    else:
        if not args.dry_run:
            # Grade mode without isolation still enforces bank checks; note it.
            pass

    vmap, hmap = check_banks(visible, hidden)

    mount = write_mount(visible_path, out_dir)
    _ = mount
    write_contract(
        out_dir, args.model, visible_bytes, hidden_bytes, isolation_bytes
    )

    if args.dry_run:
        dry = build_dry_run(vmap)
        (out_dir / "dry-run.json").write_text(
            json.dumps(dry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return 0

    mapping = load_grade_map(Path(args.grade_file))
    graded = run_grade(vmap, hmap, mapping, args.model)
    (out_dir / "graded-results.json").write_text(
        json.dumps(graded, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
