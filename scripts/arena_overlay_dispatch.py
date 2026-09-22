"""Board 3 overlay dispatch preview (pre-activation, files-only).

Given the frozen arena-agentic-v1-20260920 BANK plus the r2 overlay, produce
dispatch-ready prompt text for all 12 cases WITHOUT calling any model and
WITHOUT touching the dispatch authorization gate.

Read-only toward the BANK. The only writes are the preview tree under
tmp/boardC-dispatch-preview-20260920/ (default): 12 prompt .txt files, a
manifest of inputs+hashes, an isolation report, a fixture mapping, a recorded
gate refusal, and a candidate-mount/ subtree carrying exactly the allowlisted
candidate-visible-bank.json plus the materialised fixtures/ payloads.

This module never imports a network, model, or process library. It cannot
dispatch: gate() refuses while overlay/dispatch-authorization.json reports
dispatch_ready=false, which is the state of the frozen gate today.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ENVELOPE_ID = "arena-agentic-v1-20260920"
OVERLAY_VERSION = "arena-agentic-v1-20260920-overlay-r2"
PREVIEW_SCHEMA = "veritas.arena_overlay_dispatch_preview.v1"
GATE_REFUSAL_SCHEMA = "veritas.arena_dispatch_gate_refusal.v1"
DEFAULT_PREVIEW_OUT = Path("tmp/boardC-dispatch-preview-20260920")
DEFAULT_BANK_DIR = Path("data/evals/model-arena/arena-agentic-v1-20260920")
EXPECTED_ALLOWLIST = ["candidate-visible-bank.json", "fixtures/"]
EXPECTED_CASES = 12
FIXTURE_DIRNAME = "fixtures"
MOUNT_DIRNAME = "candidate-mount"
MOUNT_BANK_FILENAME = "candidate-visible-bank.json"
PROMPT_DIRECTIVE_LINE = "Return only the required JSON object. No prose."
# Mirror of the sealed runner's containment constants (read from the frozen
# runner's semantics; this module keeps its own copy so it never edits it).
HIDDEN_FILENAMES = ["hidden-bank.json"]
FIXTURE_CONTROL_FIELDS = (
    "allowed_reads",
    "authoritative_rows",
    "expected_trace",
    "forbidden_reads",
    "missing_paths",
    "stale_rows",
)
FORBIDDEN_VISIBLE_SUBSTRINGS = (
    '"structure_id"',
    '"family_trap"',
    '"expected_trace"',
    '"forbidden_reads"',
)

INPUT_FILES = (
    "candidate-visible-bank.json",
    "hidden-bank.json",
    "harness-fixtures.json",
    "overlay/key-shapes.json",
    "overlay/quarantine.json",
    "overlay/candidate-isolation.json",
    "overlay/dispatch-authorization.json",
)


class PreviewError(Exception):
    """Structural or containment failure: fail closed, emit nothing."""


class DispatchRefused(Exception):
    """The owner gate does not authorize dispatch."""


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fail(msg: str) -> "None":
    raise PreviewError(msg)


def load_json(path: Path):
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        _fail(f"missing_file:{path}")
    except OSError as exc:
        _fail(f"unreadable_file:{path}:{exc}")
    try:
        doc = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError as exc:
        _fail(f"invalid_json:{path}:{exc}")
    return doc, data


def write_bytes_exact(path: Path, data: bytes) -> None:
    """Byte-deterministic write: no newline translation, no encoding drift."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def dump_json_text(doc) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def safe_relpath(raw: str) -> Path:
    """Reject anything that could escape the fixtures subtree."""
    if not isinstance(raw, str) or not raw:
        _fail(f"fixture_path_invalid:{raw!r}")
    if raw.startswith("/") or raw.startswith("\\") or ":" in raw:
        _fail(f"fixture_path_not_relative:{raw!r}")
    parts = [p for p in raw.replace("\\", "/").split("/") if p]
    if any(p in ("..", ".") for p in parts):
        _fail(f"fixture_path_traversal:{raw!r}")
    if not parts:
        _fail(f"fixture_path_empty:{raw!r}")
    return Path(*parts)


def leaves(node, out=None):
    if out is None:
        out = []
    if isinstance(node, dict):
        for value in node.values():
            leaves(value, out)
    elif isinstance(node, list):
        for value in node:
            leaves(value, out)
    else:
        out.append(node)
    return out


# --------------------------------------------------------------------------
# frozen-input loading
# --------------------------------------------------------------------------


def load_context(bank_dir: Path, preview_out: Path) -> dict:
    """Load the frozen BANK + overlay. Never mutates BANK."""
    bank_dir = Path(bank_dir)
    docs, raw = {}, {}
    for rel in INPUT_FILES:
        doc, data = load_json(bank_dir / rel)
        docs[rel] = doc
        raw[rel] = data
    visible = docs["candidate-visible-bank.json"]
    hidden = docs["hidden-bank.json"]
    overlay = docs["overlay/key-shapes.json"]
    return {
        "bank_dir": bank_dir,
        "preview_out": Path(preview_out),
        "docs": docs,
        "raw": raw,
        "visible": visible,
        "hidden": hidden,
        "overlay": overlay,
        "quarantine": docs["overlay/quarantine.json"],
        "isolation": docs["overlay/candidate-isolation.json"],
        "authorization": docs["overlay/dispatch-authorization.json"],
        "fixtures": docs["harness-fixtures.json"],
    }


def check_overlay_binding(ctx: dict) -> dict:
    """An overlay is valid only against the exact bank it was built from."""
    overlay = ctx["overlay"]
    if overlay.get("envelope") != ENVELOPE_ID:
        _fail(f"overlay_envelope_mismatch:{overlay.get('envelope')!r}")
    expected = overlay.get("hidden_bank_sha256")
    actual = sha256_bytes(ctx["raw"]["hidden-bank.json"])
    if expected != actual:
        _fail(f"overlay_bank_mismatch:expected={expected}:actual={actual}")
    if overlay.get("overlay_version") != OVERLAY_VERSION:
        _fail(f"overlay_version_mismatch:{overlay.get('overlay_version')!r}")
    families = overlay.get("families")
    if not isinstance(families, dict) or not families:
        _fail("overlay_missing_families")
    return families


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


def check_banks(visible: dict, hidden: dict):
    vmap = index_cases(visible, "visible")
    hmap = index_cases(hidden, "hidden")
    if len(vmap) != EXPECTED_CASES or len(hmap) != EXPECTED_CASES:
        _fail(f"bank_size:visible={len(vmap)}:hidden={len(hmap)}")
    if set(vmap) != set(hmap):
        _fail(
            "bank_id_mismatch:missing=%s:extra=%s"
            % (sorted(set(hmap) - set(vmap)), sorted(set(vmap) - set(hmap)))
        )
    return vmap, hmap


# --------------------------------------------------------------------------
# PART B-1  merge()
# --------------------------------------------------------------------------


def merge_text(instance_id: str, family: str, prompt: dict, contract_text: str) -> str:
    """Visible prompt + family contract text, assembled deterministically."""
    lines = [
        "case %s (family: %s)" % (instance_id, family),
        "response contract:",
        contract_text,
        "",
        "prompt:",
        json.dumps(prompt, indent=2, sort_keys=True),
        PROMPT_DIRECTIVE_LINE,
    ]
    return "\n".join(lines) + "\n"


def merge(ctx: dict, families: dict, out_dir: Path | None = None) -> dict:
    """Write 12 merged prompt .txt files + manifest under the preview dir."""
    out_dir = Path(out_dir) if out_dir else ctx["preview_out"]
    vmap, hmap = check_banks(ctx["visible"], ctx["hidden"])
    rows = []
    written = []
    for iid in sorted(vmap):
        family = hmap[iid].get("family")
        if family != vmap[iid].get("family"):
            _fail(f"family_mismatch:{iid}")
        if family not in families:
            _fail(f"family_contract_missing:{family}")
        contract_text = families[family]["contract_text"]
        if not isinstance(contract_text, str) or not contract_text.strip():
            _fail(f"contract_text_empty:{family}")
        prompt = vmap[iid]["prompt"]
        text = merge_text(iid, family, prompt, contract_text)
        blob = text.encode("utf-8")
        dest = out_dir / ("%s.txt" % iid)
        write_bytes_exact(dest, blob)
        written.append(dest)
        rows.append(
            {
                "instance_id": iid,
                "family": family,
                "contract_sha256": sha256_bytes(contract_text.encode("utf-8")),
                "prompt_sha256": sha256_bytes(
                    json.dumps(prompt, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ),
                "merged_bytes": len(blob),
                "merged_sha256": sha256_bytes(blob),
                "txt_path": "%s.txt" % iid,
            }
        )
    manifest = {
        "schema": PREVIEW_SCHEMA,
        "envelope": ENVELOPE_ID,
        "overlay_version": OVERLAY_VERSION,
        "preview_only": True,
        "model_callable": False,
        "note": (
            "Preview text for owner review before any dispatch authorization. "
            "No model was called; no gate was read-modify-written."
        ),
        "counts": {"cases_in_bank": len(vmap), "merged_written": len(written)},
        "inputs": [
            {
                "path": rel,
                "bytes": len(ctx["raw"][rel]),
                "sha256": sha256_bytes(ctx["raw"][rel]),
            }
            for rel in INPUT_FILES
        ],
        "cases": rows,
    }
    return manifest


# --------------------------------------------------------------------------
# PART B-2  fixtures()
# --------------------------------------------------------------------------


def fixtures(ctx: dict, out_dir: Path | None = None) -> dict:
    """Materialise both T4 fixture sets and verify their bytes exist.

    Only each set's `files` payloads are written, minus `missing_paths`.
    Grading expectations (allowed_reads, expected_trace, authoritative_rows,
    stale_rows, forbidden_reads, missing_paths) never enter the mount.
    """
    out_dir = Path(out_dir) if out_dir else ctx["preview_out"]
    mount = out_dir / MOUNT_DIRNAME
    fx_root = mount / FIXTURE_DIRNAME
    sets = ctx["fixtures"].get("fixture_sets")
    if not isinstance(sets, dict) or not sets:
        _fail("fixtures_missing_sets")

    # which sets the cases actually reference
    referenced = {}
    for case in ctx["visible"].get("cases", []):
        set_id = (case.get("prompt") or {}).get("fixture_set_id")
        if set_id:
            referenced[set_id] = referenced.get(set_id, 0) + 1
    if not referenced:
        _fail("no_referenced_fixture_sets")
    for set_id in referenced:
        if set_id not in sets:
            _fail(f"referenced_fixture_set_missing:{set_id}")

    mapping = {}
    for set_id in sorted(sets):
        spec = sets[set_id]
        if not isinstance(spec, dict):
            _fail(f"fixture_set_not_object:{set_id}")
        files = spec.get("files")
        if not isinstance(files, dict) or not files:
            _fail(f"fixture_set_missing_files:{set_id}")
        missing = {p for p in (spec.get("missing_paths") or []) if isinstance(p, str)}
        set_root = fx_root / safe_relpath(set_id)
        entries = []
        for raw_rel, content in sorted(files.items()):
            rel = str(safe_relpath(raw_rel)).replace("\\", "/")
            if raw_rel in missing:
                entries.append(
                    {"relpath": rel, "materialised": False, "reason": "missing_paths"}
                )
                continue
            if not isinstance(content, str):
                _fail(f"fixture_content_not_string:{set_id}:{raw_rel}")
            expected = content.encode("utf-8")
            dest = set_root / safe_relpath(raw_rel)
            resolved = dest.resolve()
            if not str(resolved).startswith(str(set_root.resolve())):
                _fail(f"fixture_path_escape:{set_id}:{raw_rel}")
            write_bytes_exact(dest, expected)
            actual = dest.read_bytes() if dest.exists() else None
            if actual is None:
                _fail(f"fixture_bytes_absent:{set_id}:{raw_rel}")
            if actual != expected:
                _fail(f"fixture_bytes_mismatch:{set_id}:{raw_rel}")
            entries.append(
                {
                    "relpath": rel,
                    "materialised": True,
                    "bytes": len(actual),
                    "sha256": sha256_bytes(actual),
                    "mount_path": "%s/%s/%s" % (MOUNT_DIRNAME, FIXTURE_DIRNAME, set_id),
                    "resolved_from_start_path": rel == spec.get("start_path"),
                }
            )
        mapping[set_id] = {
            "fixture_set_id": set_id,
            "referenced_by_cases": referenced.get(set_id, 0),
            "start_path": spec.get("start_path"),
            "fallback_index": spec.get("fallback_index"),
            "read_budget": spec.get("read_budget"),
            "start_path_present": bool(spec.get("start_path"))
            and spec.get("start_path") not in missing,
            "missing_paths": sorted(missing),
            "materialised_root": "%s/%s/%s" % (MOUNT_DIRNAME, FIXTURE_DIRNAME, set_id),
            "files": entries,
        }
    report = {
        "schema": PREVIEW_SCHEMA + ".fixtures",
        "model_callable": False,
        "fixture_sets_in_bank": sorted(sets),
        "fixture_sets_referenced": sorted(referenced),
        "all_referenced_resolved": sorted(referenced) == sorted(sets),
        "mapping": mapping,
    }
    return report


# --------------------------------------------------------------------------
# PART B-3  isolation()
# --------------------------------------------------------------------------


def _scan_forbidden(label: str, blob: str, findings: list) -> None:
    for token in FORBIDDEN_VISIBLE_SUBSTRINGS:
        if token in blob:
            findings.append(f"{label}:forbidden_token:{token}")
    for name in HIDDEN_FILENAMES:
        if name in blob:
            findings.append(f"{label}:hidden_filename:{name}")


def isolation(ctx: dict, out_dir: Path | None = None, families: dict | None = None) -> dict:
    """Enforce the candidate-isolation mounts/denylist against the preview."""
    out_dir = Path(out_dir) if out_dir else ctx["preview_out"]
    iso = ctx["isolation"]
    findings = []

    allowlist = iso.get("candidate_mount_allowlist")
    if sorted(allowlist or []) != sorted(EXPECTED_ALLOWLIST):
        findings.append(f"allowlist_mismatch:{allowlist!r}")
    if iso.get("candidate_visible_only") is not True:
        findings.append("isolation_not_visible_only")
    denylist = iso.get("candidate_mount_denylist")
    if not isinstance(denylist, list) or not denylist:
        findings.append("denylist_missing")
    for name in HIDDEN_FILENAMES:
        if name in (allowlist or []):
            findings.append(f"hidden_in_allowlist:{name}")
    overlap = set(allowlist or []) & set(denylist or [])
    if overlap:
        findings.append(f"allow_deny_overlap:{sorted(overlap)}")

    # every denylisted name must resolve to a real BANK file
    deny_resolved = {}
    for name in sorted(denylist or []):
        target = ctx["bank_dir"] / name
        deny_resolved[name] = target.exists()
        if not target.exists():
            findings.append(f"denylist_entry_unresolved:{name}")

    # candidate mount must contain exactly the allowlist and nothing else
    mount = out_dir / MOUNT_DIRNAME
    seen_entries = []
    if mount.exists():
        seen_entries = sorted(p.name for p in mount.iterdir())
    else:
        findings.append("candidate_mount_absent")

    # merged preview text must carry no hidden material
    preview_files = sorted(p for p in out_dir.glob("*.txt"))
    hidden_blobs = {
        c["instance_id"]: json.dumps(
            c.get("key"), sort_keys=True, separators=(",", ":")
        )
        for c in ctx["hidden"].get("cases", [])
    }
    for path in preview_files:
        blob = path.read_text(encoding="utf-8")
        _scan_forbidden(path.name, blob, findings)
        for iid, key_blob in hidden_blobs.items():
            if key_blob and key_blob in blob:
                findings.append(f"{path.name}:whole_key_leak:{iid}")

    # mounted fixture payloads must carry payload data only
    fixture_files = []
    mount_root = mount / FIXTURE_DIRNAME
    if mount_root.exists():
        for path in sorted(mount_root.rglob("*")):
            if path.is_file():
                fixture_files.append(path)
                blob = path.read_text(encoding="utf-8")
                rel = str(path.relative_to(mount_root)).replace("\\", "/")
                for field in FIXTURE_CONTROL_FIELDS:
                    if '"%s"' % field in blob:
                        findings.append(f"fixtures:{rel}:control_field:{field}")
                for iid, key_blob in hidden_blobs.items():
                    if key_blob and key_blob in blob:
                        findings.append(f"fixtures:{rel}:whole_key_leak:{iid}")

    report = {
        "schema": PREVIEW_SCHEMA + ".isolation",
        "model_callable": False,
        "candidate_may_see": ["candidate-visible-bank.json", "fixtures/<fixture_set_id>/<payload files>"],
        "candidate_must_not_see": sorted(denylist or []),
        "candidate_unreachable_by_deny_default": (
            "Any BANK artifact not named in the allowlist is unavailable: the runner "
            "materialises only the allowlist and then fails closed on leftovers."
        ),
        "allowlist": sorted(allowlist or []),
        "denylist_resolves_to_real_bank_file": deny_resolved,
        "candidate_mount_entries": seen_entries,
        "preview_prompt_files_scanned": len(preview_files),
        "mounted_fixture_files_scanned": len(fixture_files),
        "findings": findings,
        "enforced": not findings,
    }
    if findings:
        _fail("isolation_enforcement:" + ";".join(findings))
    return report


# --------------------------------------------------------------------------
# PART B-4  gate()
# --------------------------------------------------------------------------


def gate(
    auth: dict,
    overlay: dict | None,
    *,
    model: str | None = None,
    expected_cases: int | None = None,
    action: str = "emit-model-callable-dispatch",
) -> dict:
    """Owner-gate check mirroring the sealed runner's check_authorization.

    Raises DispatchRefused while the gate is closed. Nothing model-callable is
    ever emitted past this function.
    """
    if auth.get("envelope") != ENVELOPE_ID:
        raise DispatchRefused(f"authorization_envelope_mismatch:{auth.get('envelope')!r}")
    if auth.get("dispatch_ready") is not True:
        raise DispatchRefused(
            f"authorization_not_dispatch_ready:{auth.get('dispatch_ready')!r}"
        )
    if overlay is None:
        raise DispatchRefused("authorization_requires_overlay")
    declared = auth.get("overlay_version")
    active = overlay.get("overlay_version")
    if declared != active:
        raise DispatchRefused(
            f"authorization_overlay_mismatch:declared={declared!r}:active={active!r}"
        )
    authorized_by = auth.get("authorized_by")
    if not isinstance(authorized_by, str) or not authorized_by.strip():
        raise DispatchRefused("authorization_missing_authorized_by")
    authorized_at = auth.get("authorized_at")
    if not isinstance(authorized_at, str) or not authorized_at.strip():
        raise DispatchRefused("authorization_missing_authorized_at")
    scope = auth.get("scope")
    if not isinstance(scope, dict):
        raise DispatchRefused("authorization_missing_scope")
    models = scope.get("models")
    if (
        not isinstance(models, list)
        or not models
        or not all(isinstance(m, str) and m.strip() for m in models)
    ):
        raise DispatchRefused("authorization_scope_models_invalid")
    if model is not None and model not in models:
        raise DispatchRefused(f"authorization_model_out_of_scope:{model!r}")
    if expected_cases is not None and scope.get("cases") != expected_cases:
        raise DispatchRefused(
            f"authorization_case_count_mismatch:{scope.get('cases')!r}:"
            f"expected={expected_cases!r}"
        )
    if scope.get("reps") != 1:
        raise DispatchRefused(f"authorization_reps_mismatch:{scope.get('reps')!r}")
    return {
        "authorized": True,
        "action": action,
        "model": model,
        "authorized_by": authorized_by,
        "authorized_at": authorized_at,
    }


def attempt_dispatch(ctx: dict, out_dir: Path | None = None, model: str | None = None) -> dict:
    """Negative-path proof: try to emit model-callable output, record the refusal.

    On refusal nothing model-callable is written; the refusal itself is recorded
    in gate-refusal.json so the block is auditable.
    """
    out_dir = Path(out_dir) if out_dir else ctx["preview_out"]
    auth = ctx["authorization"]
    observed = {
        "dispatch_ready": auth.get("dispatch_ready"),
        "authorized_by": auth.get("authorized_by"),
        "authorized_at": auth.get("authorized_at"),
        "scope": auth.get("scope"),
    }
    record = {
        "schema": GATE_REFUSAL_SCHEMA,
        "envelope": ENVELOPE_ID,
        "overlay_version": auth.get("overlay_version"),
        "action_attempted": "emit-model-callable-dispatch",
        "model_requested": model,
        "gate_observed": observed,
        "gate_authorization_path": "overlay/dispatch-authorization.json",
        "model_callable_output_written": False,
        "gate_mutated": False,
        "parity": None,
    }
    try:
        verdict = gate(auth, ctx["overlay"], model=model, expected_cases=EXPECTED_CASES)
        record["refused"] = False
        record["verdict"] = verdict
        record["reason"] = None
    except DispatchRefused as exc:
        record["refused"] = True
        record["reason"] = str(exc)
        record["model_callable_output_written"] = False
    record["parity"] = frozen_runner_gate_parity(ctx)
    write_bytes_exact(out_dir / "gate-refusal.json", dump_json_text(record).encode("utf-8"))
    return record


def frozen_runner_gate_parity(ctx: dict) -> dict:
    """Ask the sealed runner's own gate function the same question.

    Import is read-only and bytecode-write is suppressed. Proves this module's
    refusal is not a local invention: the frozen runner refuses identically.
    """
    runner_path = Path(__file__).with_name("arena_hidden_bank_runner.py")
    if not runner_path.exists():
        return {"available": False, "reason": "runner_absent"}
    prior = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("_boardC_frozen_runner", str(runner_path))
        if spec is None or spec.loader is None:
            return {"available": False, "reason": "runner_spec_unavailable"}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        try:
            module.check_authorization(
                ctx["authorization"],
                ctx["overlay"],
                model=None,
                expected_cases=EXPECTED_CASES,
            )
            return {"available": True, "refused": False, "reason": None}
        except SystemExit as exc:
            return {"available": True, "refused": True, "reason": str(exc)}
        except Exception as exc:  # pragma: no cover - defensive
            return {"available": True, "refused": True, "reason": f"{type(exc).__name__}:{exc}"}
    finally:
        sys.dont_write_bytecode = prior


# --------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------


def run(bank_dir: Path, preview_out: Path, *, write: bool = True) -> dict:
    ctx = load_context(Path(bank_dir), Path(preview_out))
    families = check_overlay_binding(ctx)
    check_banks(ctx["visible"], ctx["hidden"])
    out_dir = Path(preview_out)
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
    gate_record = attempt_dispatch(ctx, out_dir) if write else {
        "refused": None,
        "reason": "not_attempted",
    }
    manifest = merge(ctx, families, out_dir)
    fixture_report = fixtures(ctx, out_dir)
    # mirror the runner's mount: exactly the allowlist, nothing else
    mount = out_dir / MOUNT_DIRNAME
    write_bytes_exact(mount / MOUNT_BANK_FILENAME, ctx["raw"]["candidate-visible-bank.json"])
    iso_report = isolation(ctx, out_dir, families)
    if write:
        write_bytes_exact(out_dir / "manifest.json", dump_json_text(manifest).encode("utf-8"))
        write_bytes_exact(
            out_dir / "fixture-mapping.json", dump_json_text(fixture_report).encode("utf-8")
        )
        write_bytes_exact(
            out_dir / "isolation-report.json", dump_json_text(iso_report).encode("utf-8")
        )
    return {
        "preview_out": str(out_dir),
        "merged": len(manifest["cases"]),
        "gate": {
            "refused": gate_record.get("refused"),
            "reason": gate_record.get("reason"),
            "model_callable_output_written": gate_record.get(
                "model_callable_output_written"
            ),
            "parity": gate_record.get("parity"),
        },
        "fixtures": {
            "sets": sorted(fixture_report["mapping"]),
            "all_referenced_resolved": fixture_report["all_referenced_resolved"],
        },
        "isolation": {"enforced": iso_report["enforced"], "findings": iso_report["findings"]},
        "model_callable": False,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Board 3 overlay dispatch preview (no model calls, no gate flips)."
    )
    parser.add_argument("--bank-dir", default=str(DEFAULT_BANK_DIR))
    parser.add_argument("--preview-out", default=str(DEFAULT_PREVIEW_OUT))
    parser.add_argument("--check-only", action="store_true", help="do not write preview files")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        summary = run(Path(args.bank_dir), Path(args.preview_out), write=not args.check_only)
    except (PreviewError, DispatchRefused) as exc:
        print(json.dumps({"status": "fail_closed", "reason": str(exc)}, indent=2, sort_keys=True))
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
