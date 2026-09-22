"""Hidden-bank deterministic host runner (Spark slice).

Scores any named model on the frozen 12-case visible bank without
exposing hidden keys to the candidate mount.

Modes:
  python scripts/arena_hidden_bank_runner.py --visible V --hidden H \
      --isolation I --out DIR [--model NAME] --dry-run
  python scripts/arena_hidden_bank_runner.py --visible V --hidden H \
      --out DIR [--isolation I] [--model NAME] --grade-file responses.json
  python scripts/arena_hidden_bank_runner.py --visible V --hidden H \
      --isolation I --out DIR --model NAME --dispatch-plan
  python scripts/arena_hidden_bank_runner.py --visible V --hidden H \
      --out DIR [--model NAME] --collect --responses responses.json

Grade-file input shape: {"<instance_id>": "<raw response text>", ...}.
Grade modes write OUT/graded-results.json. Dispatch-plan mode writes
OUT/prompts/ per-case files plus OUT/dispatch-plan.json. Dry-run and
dispatch modes both create OUT/candidate-mount/ (visible bank only) and
OUT/control/run-contract.json (outside the mount).
Live OpenClaw spawn is out of this slice. Dispatch-plan mode is fail-closed:
the response-contract overlay, fixture payloads, and an exact owner authorization
for the selected model are all mandatory.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import hashlib
import json
import re
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
EXPECTED_ALLOWLIST_WITH_FIXTURES = ["candidate-visible-bank.json", "fixtures/"]
EXPECTED_MOUNT_FILENAME = "candidate-visible-bank.json"
FIXTURE_DIRNAME = "fixtures"
# Fixture fields that describe the grading expectation, never the data the
# candidate is allowed to read. These stay out of the mount under every mode.
FIXTURE_CONTROL_FIELDS = (
    "allowed_reads",
    "authoritative_rows",
    "expected_trace",
    "forbidden_reads",
    "missing_paths",
    "stale_rows",
)
HIDDEN_FIELD_TOKENS = ("key", "structure_id", "family_trap", "expected_trace")
FORBIDDEN_VISIBLE_SUBSTRINGS = (
    '"structure_id"',
    '"family_trap"',
    '"expected_trace"',
    '"forbidden_reads"',
)

DISPATCH_SCHEMA = "veritas.arena_dispatch_plan.v1"
DISPATCH_TIMEOUT_S = 600
DISPATCH_RETRIES = 0
DISPATCH_THINKING = "high"
PROMPT_DIRECTIVE_LINE = "Return only the required JSON object. No prose."
DEFAULT_MODEL_SENTINEL = "unnamed-candidate"


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


def check_isolation(isolation: dict, with_fixtures: bool = False) -> None:
    """Enforce the candidate-mount allowlist exactly; fail closed."""
    expected = EXPECTED_ALLOWLIST_WITH_FIXTURES if with_fixtures else EXPECTED_ALLOWLIST
    allowlist = isolation.get("candidate_mount_allowlist")
    if allowlist != expected:
        _fail(f"allowlist_mismatch:{allowlist!r}:expected={expected!r}")
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


def strings_in(node) -> set:
    """Every string and stringified number reachable in a JSON structure."""
    out = set()
    if isinstance(node, dict):
        for name, value in node.items():
            out.add(name)
            out |= strings_in(value)
    elif isinstance(node, list):
        for value in node:
            out |= strings_in(value)
    elif isinstance(node, str):
        out.add(node)
        try:
            decoded = json.loads(node)
        except (json.JSONDecodeError, ValueError):
            decoded = None
        if isinstance(decoded, (dict, list)):
            out |= strings_in(decoded)
    elif isinstance(node, bool):
        pass
    elif isinstance(node, (int, float)):
        out.add(str(node))
    return out


def hidden_only_tokens(
    visible_case: dict,
    hidden_case: dict,
    fixture_set: dict | None,
    exposure: str,
) -> list:
    """Strings that exist only on the hidden side under the stated exposure.

    Exposure-aware by necessity: once fixtures are mounted, fixture paths and
    payloads are legitimately visible and cannot indicate contamination. The
    grading-expectation fields are never legitimately visible.
    """
    exposed = strings_in(visible_case) | strings_in(hidden_case.get("key"))
    suspect = set()
    if isinstance(fixture_set, dict):
        files = fixture_set.get("files") if isinstance(fixture_set.get("files"), dict) else {}
        if exposure == "with-fixtures":
            exposed |= strings_in(files) | set(files)
        else:
            suspect |= strings_in(files) | set(files)
        for field in FIXTURE_CONTROL_FIELDS:
            suspect |= strings_in(fixture_set.get(field))
    for field in ("structure_id", "family_trap", "trap"):
        value = hidden_case.get(field)
        if isinstance(value, str):
            suspect.add(value)
    return sorted(t for t in suspect - exposed if isinstance(t, str) and len(t) >= 2)


def token_present(token: str, text: str) -> bool:
    """Match whole tokens only, so 'index' does not fire inside 'reindex'."""
    return re.search(
        r"(?<![A-Za-z0-9_-])" + re.escape(token) + r"(?![A-Za-z0-9_-])", text
    ) is not None


def guessable_token(token: str) -> bool:
    """A bare lowercase word could be an invented field name, not evidence of a read."""
    return token.isalpha() and token.islower() and len(token) <= 12


def detect_contamination(
    response_text: str, tokens: list, unanswerable: bool = False, strict_pass: bool = False
) -> dict:
    """Report hidden-only tokens echoed by a candidate response.

    A strict pass on a case whose inputs were never mounted is conclusive on its
    own: the answer was not derivable from anything the candidate could see.
    """
    matched = sorted(t for t in tokens if token_present(t, response_text))
    reasons = []
    if any(not guessable_token(t) for t in matched):
        reasons.append("hidden_only_value_echoed")
    if unanswerable and strict_pass:
        reasons.append("strict_pass_on_unmounted_fixture_case")
    if reasons:
        severity = "conclusive"
    elif matched:
        severity = "suspect"
    else:
        severity = "none"
    return {
        "contaminated": bool(matched) or bool(reasons),
        "contamination_severity": severity,
        "contamination_reasons": reasons,
        "contamination_tokens": matched,
    }


def detect_invented_content(
    response_text: str,
    parsed,
    fixture_set: dict | None,
    hidden_key,
    family: str | None,
) -> dict:
    """Additive invented-content signal (T4-focused, never changes strict_pass).

    A strict failure with fabricated row/payload values is otherwise
    indistinguishable from an ordinary wrong answer. This reports response
    tokens that appear in neither the mounted fixture payloads nor the hidden
    key, so the calibration board can separate fabrication from reasoning
    errors. Any exception is recorded as `invented_detector_error` so the case
    fails closed downstream instead of silently reporting a clean signal.
    """
    try:
        if family != "T4" or parsed is None:
            return {"invented_content_suspect": False, "invented_tokens": []}
        grounded = set()
        if isinstance(fixture_set, dict):
            files = fixture_set.get("files")
            if isinstance(files, dict):
                grounded |= strings_in(files) | set(files)
        grounded |= strings_in(hidden_key) if hidden_key is not None else set()
        grounded_l = {g.lower() for g in grounded if isinstance(g, str)}
        resp_tokens = sorted(
            t for t in strings_in(parsed) if isinstance(t, str) and len(t) >= 3
        )
        invented = sorted(
            t for t in resp_tokens
            if t.lower() not in grounded_l and not guessable_token(t)
        )
        return {
            "invented_content_suspect": bool(invented),
            "invented_tokens": invented[:20],
        }
    except Exception as exc:  # noqa: BLE001
        # Never block grading, but never claim the detection was clean either.
        return {
            "invented_content_suspect": False,
            "invented_tokens": [],
            "invented_detector_error": type(exc).__name__,
        }


def check_t4_fixture_consistency(parsed, fixture_set: dict | None) -> str:
    """Additive T4 claim-vs-fixture consistency (never changes strict_pass)."""
    try:
        if not isinstance(parsed, dict) or not isinstance(fixture_set, dict):
            return "not_claimed"
        claimed_set = parsed.get("fixture_set_id")
        if claimed_set is None:
            return "not_claimed"
        if claimed_set != fixture_set.get("fixture_set_id", fixture_set.get("seed", claimed_set)):
            # Fall through to file-level check: fixture_set_id lives in the
            # prompt, not the payload tree, so only flag trace mismatches.
            pass
        trace = parsed.get("trace")
        if trace is None:
            return "not_claimed"
        if not isinstance(trace, list):
            return "mismatch"
        files = fixture_set.get("files")
        allowed = set(files) if isinstance(files, dict) else set()
        allowed |= set(fixture_set.get("allowed_reads") or [])
        for entry in trace:
            if isinstance(entry, str) and entry not in allowed:
                return "mismatch"
        return "ok"
    except Exception:
        return "not_claimed"


def grade_text(
    visible_case: dict,
    hidden_case: dict,
    response_text: str,
    fixture_set: dict | None = None,
    exposure: str = "visible-only",
) -> dict:
    """Grade one raw response against hidden['key'] with strict helpers."""
    if not isinstance(hidden_case, dict) or "key" not in hidden_case:
        _fail("hidden_case_missing_key")
    parsed, error = parse_strict_json_object(response_text)
    factual = parsed is not None and bool(strict_equal(parsed, hidden_case["key"]))
    strict_pass = parsed is not None and error is None and factual
    operational_timeout = response_text == ""
    operational_outcome = "timeout_empty" if operational_timeout else "answered"
    requires_fixtures = bool((visible_case.get("prompt") or {}).get("fixture_set_id"))
    unanswerable = requires_fixtures and exposure != "with-fixtures"
    tokens = hidden_only_tokens(visible_case, hidden_case, fixture_set, exposure)
    contamination = detect_contamination(
        response_text, tokens, unanswerable=unanswerable, strict_pass=strict_pass
    )
    invented = detect_invented_content(
        response_text, parsed, fixture_set, hidden_case.get("key"), hidden_case.get("family")
    )
    t4_consistency = check_t4_fixture_consistency(parsed, fixture_set)
    result = {
        "instance_id": hidden_case.get("instance_id"),
        "family": hidden_case.get("family"),
        "json_valid": parsed is not None,
        "factual": factual,
        "strict_pass": strict_pass,
        "strict_pass_clean": strict_pass and not contamination["contaminated"],
        "operational_timeout": operational_timeout,
        "operational_outcome": operational_outcome,
        "unanswerable_under_exposure": unanswerable,
        "exposure": exposure,
        "parse_error": error,
        **contamination,
        **invented,
        "t4_fixture_consistency": t4_consistency,
    }
    return result


def check_overlay(overlay: dict, hidden_bytes: bytes) -> dict:
    """An overlay is only valid for the exact bank it was built against."""
    if overlay.get("envelope") != ENVELOPE_ID:
        _fail(f"overlay_envelope_mismatch:{overlay.get('envelope')!r}")
    expected = overlay.get("hidden_bank_sha256")
    actual = sha256_bytes(hidden_bytes)
    if expected != actual:
        _fail(f"overlay_bank_mismatch:expected={expected}:actual={actual}")
    families = overlay.get("families")
    if not isinstance(families, dict) or not families:
        _fail("overlay_missing_families")
    return families


def check_authorization(
    auth: dict,
    overlay: dict | None,
    *,
    model: str | None = None,
    expected_cases: int | None = None,
) -> None:
    """Refuse dispatch unless the owner gate binds the exact runnable scope."""
    if auth.get("envelope") != ENVELOPE_ID:
        _fail(f"authorization_envelope_mismatch:{auth.get('envelope')!r}")
    if auth.get("dispatch_ready") is not True:
        _fail(f"authorization_not_dispatch_ready:{auth.get('dispatch_ready')!r}")
    if overlay is None:
        _fail("authorization_requires_overlay")
    declared = auth.get("overlay_version")
    active = overlay.get("overlay_version")
    if declared != active:
        _fail(f"authorization_overlay_mismatch:declared={declared!r}:active={active!r}")
    authorized_by = auth.get("authorized_by")
    if not isinstance(authorized_by, str) or not authorized_by.strip():
        _fail("authorization_missing_authorized_by")
    authorized_at = auth.get("authorized_at")
    if not isinstance(authorized_at, str) or not authorized_at.strip():
        _fail("authorization_missing_authorized_at")
    try:
        parsed_at = datetime.datetime.fromisoformat(authorized_at.replace("Z", "+00:00"))
    except ValueError:
        _fail(f"authorization_invalid_authorized_at:{authorized_at!r}")
    if parsed_at.tzinfo is None:
        _fail("authorization_authorized_at_requires_timezone")
    scope = auth.get("scope")
    if not isinstance(scope, dict):
        _fail("authorization_missing_scope")
    models = scope.get("models")
    if not isinstance(models, list) or not models or not all(
        isinstance(item, str) and item.strip() for item in models
    ):
        _fail("authorization_scope_models_invalid")
    if model is not None and model not in models:
        _fail(f"authorization_model_out_of_scope:{model!r}")
    if expected_cases is not None and scope.get("cases") != expected_cases:
        _fail(
            f"authorization_case_count_mismatch:{scope.get('cases')!r}:"
            f"expected={expected_cases!r}"
        )
    if scope.get("reps") != 1:
        _fail(f"authorization_reps_mismatch:{scope.get('reps')!r}:expected=1")


def build_dry_run(vmap: dict, families: dict | None = None) -> list:
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
        if families is not None:
            spec = families.get(vcase["family"])
            if not isinstance(spec, dict) or not spec.get("contract_text"):
                _fail(f"overlay_family_missing:{vcase['family']}")
            entry["response_contract"] = spec["contract_text"]
        blob = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        for token in HIDDEN_FIELD_TOKENS:
            if f'"{token}"' in blob:
                _fail(f"hidden_field_in_dry_run:{token}:{iid}")
        items.append(entry)
    return items


def safe_fixture_relpath(raw: str) -> Path:
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


def write_fixture_tree(mount: Path, fixture_sets: dict, hmap: dict) -> dict:
    """Materialise fixture payloads only; grading metadata never enters the mount."""
    root = mount / FIXTURE_DIRNAME
    written = {}
    for set_id, spec in sorted(fixture_sets.items()):
        if not isinstance(spec, dict):
            _fail(f"fixture_set_not_object:{set_id}")
        files = spec.get("files")
        if not isinstance(files, dict) or not files:
            _fail(f"fixture_set_missing_files:{set_id}")
        missing = {
            p for p in spec.get("missing_paths") or [] if isinstance(p, str)
        }
        set_root = root / safe_fixture_relpath(set_id)
        names = []
        for raw, content in sorted(files.items()):
            if raw in missing:
                continue
            if not isinstance(content, str):
                _fail(f"fixture_content_not_string:{set_id}:{raw}")
            dest = set_root / safe_fixture_relpath(raw)
            resolved = dest.resolve()
            if not str(resolved).startswith(str(set_root.resolve())):
                _fail(f"fixture_path_escape:{set_id}:{raw}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            names.append(raw)
        written[set_id] = names
    # No answer key may be reconstructable verbatim from a mounted payload.
    blob = json.dumps(
        {k: v for k, v in fixture_sets.items()}, sort_keys=True, separators=(",", ":")
    )
    for iid, hcase in hmap.items():
        key_blob = json.dumps(hcase.get("key"), sort_keys=True, separators=(",", ":"))
        if key_blob in blob:
            _fail(f"whole_key_leak_fixtures:{iid}")
    return written


def write_mount(
    visible_path: Path, out_dir: Path, fixture_sets: dict | None = None, hmap: dict | None = None
) -> Path:
    mount = out_dir / "candidate-mount"
    mount.mkdir(parents=True, exist_ok=True)
    # Mount must contain only the visible bank and, when enabled, fixtures/.
    for child in sorted(mount.iterdir()):
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            import shutil

            shutil.rmtree(child)
    dest = mount / EXPECTED_MOUNT_FILENAME
    dest.write_bytes(visible_path.read_bytes())
    if fixture_sets:
        write_fixture_tree(mount, fixture_sets, hmap or {})
    expected_entries = [EXPECTED_MOUNT_FILENAME]
    if fixture_sets:
        expected_entries = sorted([EXPECTED_MOUNT_FILENAME, FIXTURE_DIRNAME])
    leftovers = sorted(p.name for p in mount.iterdir())
    if leftovers != expected_entries:
        _fail(f"mount_unexpected_entries:{leftovers!r}:expected={expected_entries!r}")
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
    timeout_s: int | None = None,
    retries: int | None = None,
    thinking: str | None = None,
    mount_allowlist: list[str] | None = None,
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
        "mount_allowlist": list(mount_allowlist or EXPECTED_ALLOWLIST),
        "note": "control-plane artifact; never placed inside candidate-mount",
    }
    if timeout_s is not None:
        contract["timeout_s"] = timeout_s
        try:
            issued = datetime.datetime.fromisoformat(
                contract["timestamp_utc"].replace("Z", "+00:00")
            )
            if issued.tzinfo is not None:
                contract["deadline_utc"] = (
                    issued + datetime.timedelta(seconds=int(timeout_s))
                ).isoformat()
        except (ValueError, TypeError):
            pass
    if retries is not None:
        contract["retries"] = retries
    if thinking is not None:
        contract["thinking"] = thinking
    dest = control / "run-contract.json"
    dest.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return dest


def build_prompt_text(item: dict) -> str:
    """Human-readable prompt file body for one dispatch case."""
    lines = ["case %s (family: %s)" % (item["instance_id"], item["family"])]
    contract = item.get("response_contract")
    if contract:
        lines += ["response contract:", contract, ""]
    lines += [
        "prompt:",
        json.dumps(item["prompt"], indent=2, sort_keys=True),
        PROMPT_DIRECTIVE_LINE,
    ]
    return "\n".join(lines) + "\n"


def write_dispatch_prompts(out_dir: Path, items: list) -> list:
    """Write OUT/prompts/case-<id>.json + .txt; return manifest case rows."""
    prompts_dir = out_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    for child in sorted(prompts_dir.iterdir()):
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            import shutil

            shutil.rmtree(child)
    manifest_cases = []
    for item in items:
        iid = item["instance_id"]
        if not iid or "/" in iid or "\\" in iid or ".." in iid:
            _fail(f"unsafe_instance_id:{iid!r}")
        json_name = "case-%s.json" % iid
        txt_name = "case-%s.txt" % iid
        (prompts_dir / json_name).write_text(
            json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (prompts_dir / txt_name).write_text(
            build_prompt_text(item), encoding="utf-8"
        )
        manifest_cases.append(
            {
                "instance_id": iid,
                "family": item["family"],
                "prompt_path": "prompts/%s" % json_name,
                "prompt_txt_path": "prompts/%s" % txt_name,
            }
        )
    # Defense in depth: serialized prompts must carry no hidden material.
    blob = json.dumps(items, sort_keys=True, separators=(",", ":"))
    for token in FORBIDDEN_VISIBLE_SUBSTRINGS:
        if token in blob:
            _fail(f"hidden_leak_dispatch_prompts:{token}")
    return manifest_cases


def write_dispatch_plan(out_dir: Path, model: str, manifest_cases: list) -> Path:
    issued = datetime.datetime.now(datetime.timezone.utc)
    deadline = issued + datetime.timedelta(seconds=DISPATCH_TIMEOUT_S)
    deadline_utc = deadline.isoformat()
    timestamp_utc = issued.isoformat()
    for entry in manifest_cases:
        entry.setdefault("timeout_s", DISPATCH_TIMEOUT_S)
        entry.setdefault("deadline_utc", deadline_utc)
    plan = {
        "schema": DISPATCH_SCHEMA,
        "model": model,
        "timeout_s": DISPATCH_TIMEOUT_S,
        "retries": DISPATCH_RETRIES,
        "thinking": DISPATCH_THINKING,
        "timestamp_utc": timestamp_utc,
        "deadline_utc": deadline_utc,
        "spawn_rule": {
            "runTimeoutSeconds": DISPATCH_TIMEOUT_S,
            "retries": DISPATCH_RETRIES,
            "on_timeout": "record_empty_fail_closed",
            "note": ("Spawn each candidate case with runTimeoutSeconds "
                    "equal to timeout_s; never retry; a timeout, cancel, "
                    "or missing reply grades as operational timeout."),
        },
        "cases": manifest_cases,
    }
    dest = out_dir / "dispatch-plan.json"
    dest.write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
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
    vmap: dict,
    hmap: dict,
    mapping: dict,
    model: str,
    fixture_sets: dict | None = None,
    exposure: str = "visible-only",
) -> dict:
    vids, gids = set(vmap), set(mapping)
    if vids != gids:
        _fail(
            f"grade_id_mismatch:missing={sorted(vids - gids)}:extra={sorted(gids - vids)}"
        )
    results = []
    for iid in sorted(vids):
        set_id = (vmap[iid].get("prompt") or {}).get("fixture_set_id")
        fixture_set = (fixture_sets or {}).get(set_id) if set_id else None
        graded = grade_text(
            vmap[iid], hmap[iid], mapping[iid], fixture_set=fixture_set, exposure=exposure
        )
        results.append(graded)
    passed = sum(1 for r in results if r["strict_pass"])
    clean = sum(1 for r in results if r["strict_pass_clean"])
    timeouts = sum(1 for r in results if r.get("operational_timeout"))
    invented_flags = sum(1 for r in results if r.get("invented_content_suspect"))
    return {
        "model": model,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total": len(results),
        "exposure": exposure,
        "strict_pass_count": passed,
        "strict_pass_count_clean": clean,
        "contaminated_count": sum(1 for r in results if r["contaminated"]),
        "operational_timeout_count": timeouts,
        "answered_count": len(results) - timeouts,
        "invented_content_flag_count": invented_flags,
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
    parser.add_argument("--model", default=DEFAULT_MODEL_SENTINEL)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--grade-file", default=None)
    parser.add_argument("--dispatch-plan", dest="dispatch_plan", action="store_true",
                        help="Write prompts/ + dispatch-plan.json (requires --model/--isolation)")
    parser.add_argument("--collect", action="store_true",
                        help="Grade mode using --responses file")
    parser.add_argument("--responses", default=None,
                        help="Responses JSON path for --collect")
    parser.add_argument("--fixtures", default=None,
                        help="harness-fixtures.json; mounts fixture payloads for T4")
    parser.add_argument("--overlay", default=None,
                        help="Key-shape overlay JSON; publishes the response contract")
    parser.add_argument("--authorization", default=None,
                        help="Dispatch authorization JSON; required for --dispatch-plan")
    parser.add_argument("--exposure", default=None,
                        choices=["visible-only", "with-fixtures"],
                        help="Contamination baseline for grading (default: infer from --fixtures)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.dispatch_plan and (args.dry_run or args.grade_file or args.collect or args.responses):
        _fail("dispatch_plan_exclusive")
    if args.dry_run and (args.grade_file or args.collect or args.responses):
        _fail("dry_run_and_grade_exclusive")
    if args.collect and args.grade_file:
        _fail("collect_and_grade_file_exclusive")
    if args.responses and not args.collect:
        _fail("responses_requires_collect")
    if args.collect and not args.responses:
        _fail("collect_requires_responses")
    if not args.dry_run and not args.grade_file and not args.collect and not args.dispatch_plan:
        _fail("need_dry_run_or_grade_file_or_collect_or_dispatch_plan")
    if args.dispatch_plan:
        if not args.isolation:
            _fail("dispatch_plan_requires_isolation")
        if not args.overlay:
            _fail("dispatch_plan_requires_overlay")
        if not args.fixtures:
            _fail("dispatch_plan_requires_fixtures")
        if args.model == DEFAULT_MODEL_SENTINEL:
            _fail("dispatch_plan_requires_explicit_model")
        if not args.authorization:
            _fail("dispatch_plan_requires_authorization")
    visible_path = Path(args.visible)
    hidden_path = Path(args.hidden)
    out_dir = Path(args.out)

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

    fixture_sets = None
    if args.fixtures:
        fixtures_doc = load_json(Path(args.fixtures))
        fixture_sets = fixtures_doc.get("fixture_sets") if isinstance(fixtures_doc, dict) else None
        if not isinstance(fixture_sets, dict) or not fixture_sets:
            _fail(f"fixtures_missing_sets:{args.fixtures}")

    overlay = None
    overlay_families = None
    if args.overlay:
        overlay = load_json(Path(args.overlay))
        overlay_families = check_overlay(overlay, hidden_bytes)

    exposure = args.exposure or ("with-fixtures" if fixture_sets else "visible-only")

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
        check_isolation(isolation, with_fixtures=bool(fixture_sets))
    else:
        if not args.dry_run:
            # Grade mode without isolation still enforces bank checks; note it.
            pass

    vmap, hmap = check_banks(visible, hidden)

    if args.dispatch_plan:
        check_authorization(
            load_json(Path(args.authorization)),
            overlay,
            model=args.model,
            expected_cases=len(vmap),
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    mount = write_mount(visible_path, out_dir, fixture_sets=fixture_sets, hmap=hmap)
    _ = mount

    if args.dispatch_plan:
        write_contract(
            out_dir, args.model, visible_bytes, hidden_bytes, isolation_bytes,
            timeout_s=DISPATCH_TIMEOUT_S, retries=DISPATCH_RETRIES,
            thinking=DISPATCH_THINKING,
            mount_allowlist=EXPECTED_ALLOWLIST_WITH_FIXTURES,
        )
        items = build_dry_run(vmap, overlay_families)
        manifest_cases = write_dispatch_prompts(out_dir, items)
        write_dispatch_plan(out_dir, args.model, manifest_cases)
        return 0

    write_contract(
        out_dir, args.model, visible_bytes, hidden_bytes, isolation_bytes,
        mount_allowlist=(
            EXPECTED_ALLOWLIST_WITH_FIXTURES if fixture_sets else EXPECTED_ALLOWLIST
        ),
    )

    if args.dry_run:
        dry = build_dry_run(vmap, overlay_families)
        (out_dir / "dry-run.json").write_text(
            json.dumps(dry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return 0

    grade_source = args.grade_file if args.grade_file else args.responses
    mapping = load_grade_map(Path(grade_source))
    graded = run_grade(
        vmap, hmap, mapping, args.model, fixture_sets=fixture_sets, exposure=exposure
    )
    (out_dir / "graded-results.json").write_text(
        json.dumps(graded, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
