"""Model Arena - standalone, model-agnostic capability bench.

Owner-directed 2026-09-19 (Randall): a lightweight arena reusable for any model
the gateway can resolve (GLM 5.3 Flash, DeepSeek v4.1 Flash, Kimi K3,
Muse Spark 1.3, and whatever ships next). Adding a model is a roster edit, never
a code change.

Deliberately NOT part of the WF88 frontier-capability spine: no frozen fixture
digest, no OpenAI-only transport, no gate thresholds, no attestation. Nothing
here reads or writes WF88 artifacts.

Split of duties, because a plain Python process cannot call sessions_spawn:
  - this script owns everything deterministic: roster, task set, dispatch plan,
    result ingestion, grading, scorecard, validation.
  - the agent layer owns dispatch only: it reads the plan, spawns one subagent
    per (model, task) pair with a model override, and appends one raw result row
    per run. Contract is two JSON files, so the dispatcher can be Main, a cron
    agentTurn, or a human replaying by hand.

Usage:
  python scripts/model_arena.py --plan [--models a,b] [--tasks x,y] [--classes c]
                               [--repeats N] [--run-id ID]
  python scripts/model_arena.py --score --run-id ID [--allow-exec]
  python scripts/model_arena.py --validate

Review-only. No capital, execution, config, credential, or external-delivery
authority. Grading of code_exec tasks runs model-produced code ONLY inside the
pinned local Docker image ID via arena_harness.run_sandboxed_command, opt-in
behind --allow-exec. There is no host-Python fallback; a static safety scan is
advisory only and never implies containment. Honest limit: nonce markers raise
the bar against trivial spoofing, not formal protection against malicious
in-container grader interference.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARENA = ROOT / "data" / "evals" / "model-arena"
ROSTER_PATH = ARENA / "roster.json"
TASKS_PATH = ARENA / "tasks.json"
RESULTS_DIR = ARENA / "results"
PLAN_PATH = ROOT / "tmp" / "model-arena-plan.json"
PLANS_DIR = ROOT / "tmp" / "model-arena-plans"
PROMPTS_ROOT = ROOT / "tmp" / "model-arena-prompts"
SCORECARD_JSON = ROOT / "tmp" / "model-arena-scorecard.json"
SCORECARD_MD = ROOT / "tmp" / "model-arena-scorecard.md"

PHX = timezone(timedelta(hours=-7))
PLAN_SCHEMA = "veritas.model_arena_plan.v1"
RESULT_SCHEMA = "veritas.model_arena_result.v1"
SCORECARD_SCHEMA = "veritas.model_arena_scorecard.v1"
GRADE_MODES = {"code_exec", "static", "json_output"}

EXEC_TIMEOUT_S = 20
UNSAFE_PATTERNS = (
    r"\bimport\s+(os|sys|subprocess|socket|shutil|requests|urllib|ctypes|pathlib)\b",
    r"\bfrom\s+(os|sys|subprocess|socket|shutil|requests|urllib|ctypes|pathlib)\b",
    r"\b__import__\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bopen\s*\(",
)


try:
    from arena_harness import (
        assert_safe_run_id,
        canonical_prompt,
        check_nonce_marker_line,
        check_success_marker,
        is_safe_run_id,
        make_nonce_marker,
        make_transport_receipt,
        parse_strict_json_object,
        prompt_filename_for_pair,
        run_sandboxed_command,
        sha256_text,
        strict_value_equal,
        write_prompt_files,
        is_hex64,
    )
except ImportError:  # pragma: no cover - exercised when scripts/ is on sys.path
    from scripts.arena_harness import (  # type: ignore[no-redef]
        assert_safe_run_id,
        canonical_prompt,
        check_nonce_marker_line,
        check_success_marker,
        is_safe_run_id,
        make_nonce_marker,
        make_transport_receipt,
        parse_strict_json_object,
        prompt_filename_for_pair,
        run_sandboxed_command,
        sha256_text,
        strict_value_equal,
        write_prompt_files,
        is_hex64,
    )


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _select(roster: dict, tasks: dict, args) -> tuple[list, list]:
    all_model_ids = {m["id"] for m in roster["models"]}
    all_task_ids = {t["id"] for t in tasks["tasks"]}
    all_classes = {t["class"] for t in tasks["tasks"]}
    if args.models:
        want = [s.strip() for s in args.models.split(",") if s.strip()]
        unknown = sorted(set(want) - all_model_ids)
        if unknown:
            raise ValueError(f"unknown --models selector(s): {unknown}")
        models = [m for m in roster["models"] if m["id"] in set(want)]
    else:
        models = [m for m in roster["models"] if m.get("enabled")]
    picked = tasks["tasks"]
    if args.classes:
        want_c = [s.strip() for s in args.classes.split(",") if s.strip()]
        unknown_c = sorted(set(want_c) - all_classes)
        if unknown_c:
            raise ValueError(f"unknown --classes selector(s): {unknown_c}")
        picked = [t for t in picked if t["class"] in set(want_c)]
    if args.tasks:
        want_t = [s.strip() for s in args.tasks.split(",") if s.strip()]
        unknown_t = sorted(set(want_t) - all_task_ids)
        if unknown_t:
            raise ValueError(f"unknown --tasks selector(s): {unknown_t}")
        picked = [t for t in picked if t["id"] in set(want_t)]
    return models, picked


def build_plan(args) -> int:
    if not isinstance(args.repeats, int) or isinstance(args.repeats, bool) or args.repeats < 1:
        print("plan FAILED: --repeats must be a positive integer")
        return 1
    roster, tasks = _load(ROSTER_PATH), _load(TASKS_PATH)
    try:
        models, picked = _select(roster, tasks, args)
    except ValueError as e:
        print(f"plan FAILED: {e}")
        return 1
    if not models:
        print("plan FAILED: no models selected (roster has none enabled, or --models matched nothing)")
        return 1
    if not picked:
        print("plan FAILED: no tasks selected")
        return 1

    run_id = args.run_id or f"arena-{datetime.now(PHX):%Y%m%d-%H%M%S}"
    if not is_safe_run_id(run_id):
        print(f"plan FAILED: unsafe run_id {run_id!r} (use [A-Za-z0-9._-], lead alnum, <=64 chars)")
        return 1
    # Refuse to overwrite a previous batch: never silently replace an existing plan
    # or results file for the same run_id.
    per_run_plan = PLANS_DIR / f"model-arena-plan-{run_id}.json"
    existing_results = RESULTS_DIR / f"{run_id}.jsonl"
    if per_run_plan.exists() or existing_results.exists():
        print(f"plan FAILED: run_id={run_id} already exists; pick a fresh --run-id (refusing to overwrite a previous batch)")
        return 1
    if PLAN_PATH.exists():
        try:
            prior = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
            if isinstance(prior, dict) and prior.get("run_id") == run_id:
                print(f"plan FAILED: run_id={run_id} already recorded in {PLAN_PATH.name}; refusing to overwrite")
                return 1
        except (json.JSONDecodeError, OSError):
            pass
    # Validate IDs before any write: bounded, no delimiter collision.
    for m in models:
        mid = str(m.get("id", ""))
        if not mid or len(mid) > 64 or "::" in mid or "/" in mid or "\\" in mid:
            print(f"plan FAILED: unsafe model id {mid!r}")
            return 1
    for t in picked:
        tid = str(t.get("id", ""))
        if not tid or len(tid) > 64 or "::" in tid or "/" in tid or "\\" in tid:
            print(f"plan FAILED: unsafe task id {tid!r}")
            return 1
    pairs = []
    for m in models:
        for t in picked:
            for attempt in range(1, args.repeats + 1):
                pid = f"{m['id']}::{t['id']}::{attempt}"
                try:
                    fname = prompt_filename_for_pair(pid)
                except ValueError as e:
                    print(f"plan FAILED: {e}")
                    return 1
                pairs.append({
                    "pair_id": pid,
                    "model_id": m["id"],
                    "model_path": m["model_path"],
                    "task_id": t["id"],
                    "task_class": t["class"],
                    "attempt": attempt,
                    "prompt": t["prompt"],
                    "prompt_file": fname,
                })

    # Immutable per-run plan: freeze task definitions/grading keys, prompt hashes,
    # model paths, and every planned pair id so scoring never depends on mutable
    # live roster/task files.
    frozen_tasks = []
    for t in picked:
        prompt = t["prompt"]
        frozen_tasks.append({
            "id": t["id"],
            "class": t["class"],
            "prompt": prompt,
            "prompt_sha256": sha256_text(prompt),
            "prompt_canonical_sha256": sha256_text(canonical_prompt(prompt)),
            "grade": t["grade"],
            "grade_sha256": sha256_text(json.dumps(t["grade"], sort_keys=True)),
        })
    plan = {
        "schema": PLAN_SCHEMA,
        "run_id": run_id,
        "generated_at_utc": _now_iso(),
        "task_set_id": tasks["task_set_id"],
        "repeats": args.repeats,
        "models": [{"id": m["id"], "model_path": m["model_path"], "label": m["label"]} for m in models],
        "frozen_tasks": frozen_tasks,
        "planned_pair_ids": [p["pair_id"] for p in pairs],
        "prompt_files_dir": str((PROMPTS_ROOT / run_id).relative_to(ROOT)).replace("\\", "/"),
        "results_path": str((RESULTS_DIR / f"{run_id}.jsonl").relative_to(ROOT)).replace("\\", "/"),
        "dispatch_contract": {
            "how": "For each pair, sessions_spawn(context='isolated', model=<model_path>, task=<prompt>). Send the prompt verbatim; add no system framing, examples, or hints. The candidate receives ONLY the allowlisted prompt text (via --message-file from prompt_files_dir/prompt_file); never send plan grading keys, frozen task definitions, or peer results.",
            "then": "Append one JSON object per line to results_path using result_row_shape below. Record the model the gateway actually resolved (from trusted runtime metadata, never candidate self-attestation), the complete observed prompt, and whether any fallback model applied (fallback_applied must be boolean false when the requested model served). model_applied must be boolean true and observed_model must be the explicit runtime-served model.",
            "message_file": "Each pair's verbatim prompt bytes are frozen under prompt_files_dir/prompt_file (exact per-pair filename recorded in pairs[].prompt_file, UTF-8); dispatch with --message-file <that file> to avoid shell re-encoding.",
            "result_row_shape": {
                "schema": RESULT_SCHEMA,
                "run_id": run_id,
                "pair_id": "<pair_id from this plan>",
                "requested_model": "<model_path from this plan>",
                "resolved_model": "<resolvedModel reported by the spawn>",
                "observed_model": "<explicit model the runtime actually served>",
                "model_applied": True,
                "fallback_applied": False,
                "observed_prompt": "<complete prompt bytes the child actually received>",
                "terminal_outcome": "succeeded|failed|timeout",
                "runtime_ms": 0,
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "output_text": "<verbatim final text from the child>",
                "session_key": "<child session key, for audit>",
                "dispatched_at_utc": "<ISO 8601>",
            },
            "no_spawn_authority": "This plan never authorizes automatic spawning or config changes; the dispatcher acts under its own authority.",
        },
        "pairs": pairs,
    }
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Write prompt files first (refuses existing dirs/files/collisions); fail
    # before persisting any plan bytes on prompt collision.
    try:
        written = write_prompt_files(PROMPTS_ROOT / run_id, pairs)
    except ValueError as e:
        print(f"plan FAILED: {e}")
        return 1
    if sorted(written) != sorted(p["prompt_file"] for p in pairs):
        print("plan FAILED: prompt file record mismatch")
        return 1
    per_run_text = json.dumps(plan, indent=1)
    per_run_plan.write_text(per_run_text, encoding="utf-8")
    # Convenience pointer to the latest plan; the per-run file above is authoritative.
    PLAN_PATH.write_text(per_run_text, encoding="utf-8")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"plan ok run_id={run_id} models={len(models)} tasks={len(picked)} pairs={len(pairs)}")
    print(f"plan   -> {PLAN_PATH.relative_to(ROOT)}")
    print(f"results-> {plan['results_path']}")
    return 0


def _extract_code(text: str) -> str:
    m = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text, re.S)
    return m[0] if m else text


def _strip_fence(text: str) -> str:
    m = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.S)
    return (m[0] if m else text).strip()


def _grade_code_exec(text: str, spec: dict, allow_exec: bool, run_id: str = "", pair_id: str = "") -> tuple[bool, str]:
    code = _extract_code(text).strip()
    if not code:
        return False, "no_code_returned"
    # Advisory static scan only: a regex hit refuses the row, a clean scan
    # proves nothing about containment (enforced by the Docker runner below).
    for pat in UNSAFE_PATTERNS:
        if re.search(pat, code):
            return False, f"refused_unsafe:{pat}"
    if allow_exec is not True:
        return False, "ungraded_exec_disabled"
    # NEVER execute candidate code on the host interpreter. Fail-closed Docker
    # run of the pinned local image ID only; any runner problem is a typed
    # non-pass with no host fallback. Fresh unpredictable nonce is created ONLY
    # here (after asserts are fixed) and required as an exact line plus rc==0,
    # so a trivial print('ARENA_PASS');exit(0) spoof without the nonce fails.
    nonce = make_nonce_marker()
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        td_p = Path(td)
        harness = code + "\n\n" + spec.get("preamble", "") + "\n" + "\n".join(spec["asserts"]) + f"\nprint('{nonce}')\n"
        (td_p / "case.py").write_text(harness, encoding="utf-8")
        res = run_sandboxed_command(td_p, ["python3", "case.py"], EXEC_TIMEOUT_S,
                                    True, run_id or "adhoc", pair_id or "adhoc")
    if res.get("status") != "ok" or res.get("passed") is not True or res.get("returncode") != 0:
        if res.get("status") == "timeout":
            return False, "exec_timeout"
        if res.get("status") == "missing_docker":
            return False, "exec_missing_docker"
        if res.get("status") == "missing_image":
            return False, "exec_missing_image"
        if res.get("status") in ("blocked_exec_disabled", "missing_grade_dir", "bad_command"):
            return False, "ungraded_exec_disabled"
        if res.get("status") == "output_limit_exceeded":
            return False, "exec_output_limit"
        if res.get("status") != "ok":
            return False, str(res.get("reason") or "exec_fail")
        return False, str(res.get("reason") or "exec_fail")
    # Require the fresh nonce exact line plus rc0; static marker alone is spoof.
    if check_nonce_marker_line(res.get("stdout", ""), res.get("returncode"), nonce):
        return True, ""
    err = (res.get("stderr") or "").strip().splitlines()
    # Candidate printed the static marker but not the fresh nonce: spoof/failure.
    return False, ("exec_fail:" + err[-1][:140]) if err else "exec_fail:nonce_missing"


def _grade_static(text: str, spec: dict) -> tuple[bool, str]:
    body = text.strip()
    low = body.lower()
    for tok in spec.get("contains_all", []):
        if tok.lower() not in low:
            return False, f"missing:{tok}"
    for tok in spec.get("contains_none", []):
        if tok.lower() in low:
            return False, f"forbidden:{tok.strip() or 'blank-line'}"
    for group in spec.get("contains_any_groups", []):
        if not any(tok.lower() in low for tok in group):
            return False, f"missing_any_of:{'|'.join(group)}"
    ordered = spec.get("ordered_tokens", [])
    if ordered:
        pos = [low.find(tok.lower()) for tok in ordered]
        if any(p < 0 for p in pos) or pos != sorted(pos):
            return False, "wrong_order:" + ">".join(ordered)
    if "regex_fullmatch" in spec and not re.fullmatch(spec["regex_fullmatch"], body, re.S):
        return False, "shape_mismatch:" + body[:60].replace("\n", "\\n")
    if "max_chars" in spec and len(body) > spec["max_chars"]:
        return False, f"too_long:{len(body)}>{spec['max_chars']}"
    if "max_sentences" in spec:
        n = len([s for s in re.split(r"[.!?]+(?:\s|$)", body) if s.strip()])
        if n > spec["max_sentences"]:
            return False, f"too_many_sentences:{n}>{spec['max_sentences']}"
    return True, ""


def _grade_json(text: str, spec: dict) -> tuple[bool, str]:
    # Strict format gate first (no fences/prose/brace-extraction), kept
    # distinct from task-correctness checks below. Nested bool-vs-number uses
    # recursive strict equality (bool never equals number; 1 == 1.0 kept).
    obj, err = parse_strict_json_object(text)
    if err is not None:
        return False, f"json_format:{err}"
    assert obj is not None
    if not isinstance(obj, dict):
        return False, "json_format:json_not_object"
    missing = [k for k in spec.get("required_keys", []) if k not in obj]
    if missing:
        return False, "missing_keys:" + ",".join(missing)
    for k, v in spec.get("expect_values", {}).items():
        if k not in obj or not strict_value_equal(obj.get(k), v):
            return False, f"wrong_value:{k}={obj.get(k)!r}!={v!r}"
    return True, ""


def _check_receipt(row: dict, expected_prompt: str, requested_model: str) -> tuple[bool, str]:
    """Require a transport receipt: complete expected/observed prompt, exact
    requested/observed model, explicit model_applied True, explicit fallback
    false. Missing, mismatched, or wrongly typed evidence cannot pass. The
    observed model must come from explicit trusted runtime evidence (no
    fallback to resolved_model self-attestation)."""
    if not isinstance(row, dict):
        return False, "receipt_row_not_object"
    if "observed_prompt" not in row or "fallback_applied" not in row:
        return False, "missing_receipt"
    if row.get("model_applied") is not True:
        return False, "model_override_not_applied"
    if not isinstance(row.get("observed_model"), str) or not row.get("observed_model"):
        return False, "receipt_missing_observed_model"
    observed_model = row.get("observed_model")
    rec = make_transport_receipt(expected_prompt, row.get("observed_prompt"),
                                 requested_model, observed_model,
                                 row.get("fallback_applied"))
    if not rec.get("passed"):
        return False, "receipt_" + str(rec.get("reason", "mismatch"))
    return True, str(rec.get("reason", "byte_exact"))


def _grade(row: dict, task: dict, allow_exec: bool, run_id: str = "", pair_id: str = "") -> tuple[bool, str]:
    if row.get("terminal_outcome") != "succeeded":
        return False, "dispatch_" + str(row.get("terminal_outcome"))
    if row.get("model_applied") is not True:
        return False, "model_override_not_applied"
    text = row.get("output_text")
    if not isinstance(text, str) or not text.strip():
        return False, "empty_output"
    # Validate usage shape (never crash on malformed usage).
    usage = row.get("usage", {})
    if usage is not None and not isinstance(usage, dict):
        return False, "malformed_row:bad_usage"
    spec = task["grade"]
    mode = spec["mode"]
    if mode == "code_exec":
        return _grade_code_exec(text, spec, allow_exec, run_id, pair_id or str(row.get("pair_id", "")))
    if mode == "static":
        return _grade_static(text, spec)
    if mode == "json_output":
        return _grade_json(text, spec)
    return False, f"unknown_grade_mode:{mode}"


def _load_frozen_plan(run_id: str) -> dict | None:
    # Immutable per-run plan only. Never fall back to the mutable convenience
    # pointer (PLAN_PATH) when the per-run file is missing/corrupt.
    cand = PLANS_DIR / f"model-arena-plan-{run_id}.json"
    try:
        doc = json.loads(cand.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(doc, dict) and doc.get("run_id") == run_id and doc.get("schema") == PLAN_SCHEMA:
        return doc
    return None


def _validate_frozen_plan(plan: dict) -> list[str]:
    """Check frozen pair/task/model consistency and stored hashes. Returns problems."""
    problems: list[str] = []
    if not isinstance(plan.get("task_set_id"), str):
        problems.append("frozen_plan_missing_task_set")
    frozen = plan.get("frozen_tasks")
    if not isinstance(frozen, list) or not frozen:
        problems.append("frozen_plan_missing_tasks")
        frozen = []
    tasks = {}
    for t in frozen:
        if not isinstance(t, dict) or not isinstance(t.get("id"), str):
            problems.append("frozen_task_malformed")
            continue
        tid = t["id"]
        if tid in tasks:
            problems.append(f"frozen_duplicate_task:{tid}")
        tasks[tid] = t
        prompt = t.get("prompt")
        if not isinstance(prompt, str):
            problems.append(f"frozen_task_bad_prompt:{tid}")
            continue
        if t.get("prompt_sha256") != sha256_text(prompt):
            problems.append(f"frozen_hash_mismatch:prompt:{tid}")
        try:
            if t.get("prompt_canonical_sha256") != sha256_text(canonical_prompt(prompt)):
                problems.append(f"frozen_hash_mismatch:canonical:{tid}")
        except Exception:
            problems.append(f"frozen_hash_error:canonical:{tid}")
        grade = t.get("grade")
        if not isinstance(grade, dict):
            problems.append(f"frozen_task_bad_grade:{tid}")
        elif t.get("grade_sha256") != sha256_text(json.dumps(grade, sort_keys=True)):
            problems.append(f"frozen_hash_mismatch:grade:{tid}")
        for hf in ("prompt_sha256", "prompt_canonical_sha256", "grade_sha256"):
            if not is_hex64(t.get(hf)):
                problems.append(f"frozen_bad_hash_format:{tid}:{hf}")
    planned = plan.get("planned_pair_ids")
    if not isinstance(planned, list) or not planned:
        problems.append("frozen_plan_missing_pairs")
        planned = []
    if len(set(planned)) != len(planned):
        problems.append("frozen_plan_duplicate_pair_ids")
    models = {m["id"]: m for m in plan.get("models", []) if isinstance(m, dict) and isinstance(m.get("id"), str)}
    if not models:
        problems.append("frozen_plan_missing_models")
    for pid in planned:
        parts = pid.split("::") if isinstance(pid, str) else []
        if len(parts) != 3 or not all(parts):
            problems.append(f"frozen_bad_pair_id:{pid!r}")
            continue
        mid, tid = parts[0], parts[1]
        if mid not in models:
            problems.append(f"frozen_unknown_model:{pid}")
        if tid not in tasks:
            problems.append(f"frozen_unknown_task:{pid}")
    return problems


def _parse_result_line(line: str) -> tuple[dict | None, str | None, str | None]:
    """Strict result-row parse: duplicate keys/nonfinite rejected. Returns
    (obj, malformed_kind, error). malformed_kind is 'malformed' for JSON
    failures (preserved as run-level invalid evidence)."""
    obj, err = parse_strict_json_object(line)
    if err is not None:
        return None, "malformed", err
    assert obj is not None
    return obj, None, None


def score(args) -> int:
    if not args.run_id:
        print("score FAILED: --run-id is required")
        return 1
    if not is_safe_run_id(args.run_id):
        print(f"score FAILED: unsafe run_id {args.run_id!r}")
        return 1
    results_path = RESULTS_DIR / f"{args.run_id}.jsonl"
    if not results_path.exists():
        print(f"score FAILED: no results at {results_path.relative_to(ROOT)}; dispatch has not run")
        return 1
    # Score consumes the frozen per-run plan, never mutable live roster/task files.
    plan = _load_frozen_plan(args.run_id)
    if plan is None:
        print(f"score FAILED: no frozen per-run plan for run_id={args.run_id}; run --plan first (refusing live mutable keys)")
        return 1
    frozen_problems = _validate_frozen_plan(plan)
    if frozen_problems:
        print(f"score FAILED: frozen plan for run_id={args.run_id} is inconsistent: {frozen_problems[:8]}")
        return 1
    if plan.get("task_set_id") is None or not plan.get("frozen_tasks") or not plan.get("planned_pair_ids"):
        print(f"score FAILED: frozen plan for run_id={args.run_id} is incomplete")
        return 1
    tasks = {t["id"]: t for t in plan["frozen_tasks"]}
    planned_ids: list[str] = list(plan["planned_pair_ids"])
    planned_set = set(planned_ids)
    if len(planned_set) != len(planned_ids):
        print(f"score FAILED: frozen plan for run_id={args.run_id} has duplicate pair ids")
        return 1
    plan_models = {m["id"]: m for m in plan.get("models", [])}
    # Detect grading-key drift between the frozen plan and the live task file.
    try:
        live = {t["id"]: t for t in _load(TASKS_PATH)["tasks"]}
        drifted = sorted(tid for tid, t in tasks.items()
                         if tid in live and json.dumps(live[tid].get("grade"), sort_keys=True)
                         != json.dumps(t.get("grade"), sort_keys=True))
    except (OSError, json.JSONDecodeError, KeyError):
        drifted = []
    if drifted:
        print(f"score WARNING: live task grading keys drifted since plan freeze for: {drifted[:10]} (frozen plan still authoritative)")

    raw_lines = results_path.read_text(encoding="utf-8").splitlines()
    raw_row_count = sum(1 for ln in raw_lines if ln.strip())
    rows: list = []
    malformed_lines: list[int] = []
    non_object_lines: list[int] = []
    for i, line in enumerate(raw_lines, 1):
        if not line.strip():
            continue
        obj, kind, _err = _parse_result_line(line)
        if kind == "malformed":
            malformed_lines.append(i)
            continue
        assert obj is not None
        if not isinstance(obj, dict):
            non_object_lines.append(i)
            continue
        rows.append(obj)
    if malformed_lines:
        print(f"score WARNING: {len(malformed_lines)} malformed result line(s): {malformed_lines[:10]}")
    if non_object_lines:
        print(f"score WARNING: {len(non_object_lines)} non-object result row(s): {non_object_lines[:10]}")
    if not rows and not planned_ids:
        print("score FAILED: results file has no parseable rows")
        return 1

    # One final outcome per planned pair. Duplicates invalidate that pair
    # (single failed cell), never first-row-wins, never independent trajectories.
    by_pid: dict[str, list[dict]] = {}
    extra_rows: list[dict] = []  # unknown_pair / missing pair_id rows
    for r in rows:
        pid = r.get("pair_id") if isinstance(r, dict) else None
        if not isinstance(pid, str) or not pid:
            extra_rows.append(r)
            continue
        if pid not in planned_set:
            extra_rows.append(r)
            continue
        by_pid.setdefault(pid, []).append(r)

    graded, per_model = [], {}
    fatal_invalid = len(malformed_lines) + len(non_object_lines) + len(extra_rows)

    def _emit(model_id: str, cell: dict) -> None:
        graded.append(cell)
        per_model.setdefault(model_id, []).append(cell)

    for pid in planned_ids:
        parts = pid.split("::")
        model_id = parts[0] if parts else ""
        task_id = parts[1] if len(parts) > 1 else ""
        task = tasks.get(task_id)
        occ = by_pid.get(pid, [])
        if len(occ) > 1:
            g = {"pair_id": pid, "model_id": model_id, "task_id": task_id,
                 "task_class": task["class"] if task else "", "passed": False,
                 "reason": "duplicate_row", "runtime_ms": None,
                 "usage": {}, "resolved_model": None}
            _emit(model_id, g)
            fatal_invalid += 1
            continue
        if not occ:
            g = {"pair_id": pid, "model_id": model_id, "task_id": task_id,
                 "task_class": task.get("class", "") if task else "", "passed": False,
                 "reason": "not_run", "runtime_ms": None, "usage": {},
                 "resolved_model": None}
            _emit(model_id, g)
            continue
        r = occ[0]
        # Wrong schema/run/payload types for a known planned pair are failed
        # cells in the denominator, never omitted.
        if r.get("schema") != RESULT_SCHEMA:
            _emit(model_id, {"pair_id": pid, "model_id": model_id,
                             "task_id": task_id, "task_class": task["class"] if task else "",
                             "passed": False, "reason": "schema_mismatch",
                             "runtime_ms": r.get("runtime_ms") if isinstance(r.get("runtime_ms"), (int, float)) else None,
                             "usage": r.get("usage") if isinstance(r.get("usage"), dict) else {},
                             "resolved_model": r.get("resolved_model")})
            fatal_invalid += 1
            continue
        if r.get("run_id") != args.run_id:
            _emit(model_id, {"pair_id": pid, "model_id": model_id,
                             "task_id": task_id, "task_class": task["class"] if task else "",
                             "passed": False, "reason": "run_mismatch",
                             "runtime_ms": r.get("runtime_ms") if isinstance(r.get("runtime_ms"), (int, float)) else None,
                             "usage": r.get("usage") if isinstance(r.get("usage"), dict) else {},
                             "resolved_model": r.get("resolved_model")})
            fatal_invalid += 1
            continue
        if task is None:
            _emit(model_id, {**r, "passed": False, "reason": f"unknown_task:{task_id}"})
            fatal_invalid += 1
            continue
        ok, reason = _check_receipt(r, task["prompt"],
                                    plan_models.get(model_id, {}).get("model_path", model_id))
        if not ok:
            g = {
                "pair_id": pid, "model_id": model_id, "task_id": task_id,
                "task_class": task["class"], "passed": False, "reason": reason,
                "runtime_ms": r.get("runtime_ms") if isinstance(r.get("runtime_ms"), (int, float)) else None,
                "usage": r.get("usage") if isinstance(r.get("usage"), dict) else {},
                "resolved_model": r.get("resolved_model"),
            }
            _emit(model_id, g)
            continue
        ok, reason = _grade(r, task, args.allow_exec, args.run_id, pid)
        usage = r.get("usage") if isinstance(r.get("usage"), dict) else {}
        rt = r.get("runtime_ms") if isinstance(r.get("runtime_ms"), (int, float)) else None
        g = {
            "pair_id": pid, "model_id": model_id, "task_id": task_id,
            "task_class": task["class"], "passed": ok, "reason": reason,
            "runtime_ms": rt, "usage": usage,
            "resolved_model": r.get("resolved_model"),
        }
        _emit(model_id, g)

    models_out = []
    for model_id, gs in sorted(per_model.items()):
        lat = [g["runtime_ms"] for g in gs if isinstance(g.get("runtime_ms"), (int, float))]
        out_tok = [g["usage"].get("output_tokens") for g in gs if isinstance(g.get("usage"), dict) and isinstance(g["usage"].get("output_tokens"), int)]
        tot_tok = [g["usage"].get("total_tokens") for g in gs if isinstance(g.get("usage"), dict) and isinstance(g["usage"].get("total_tokens"), int)]
        passes = [g for g in gs if g["passed"]]
        by_class = {}
        for g in gs:
            c = by_class.setdefault(g["task_class"], {"n": 0, "passed": 0})
            c["n"] += 1
            c["passed"] += 1 if g["passed"] else 0
        for c in by_class.values():
            c["pass_rate"] = round(c["passed"] / c["n"], 3)

        # Epoch reduction: group attempts of the same task, then reduce.
        # Empirical repeat rates only: any-repeat (ever right) and all-repeat
        # (every attempt right). Heterogeneous attempt counts are NOT a
        # calibrated pass@k estimator; the legacy pass_at_k/pass_all_k keys are
        # retained as aliases of these empirical rates.
        by_task = {}
        for g in gs:
            by_task.setdefault(g["task_id"], []).append(g)
        epochs = max(len(v) for v in by_task.values()) if by_task else 0
        any_pass = sum(1 for v in by_task.values() if any(x["passed"] for x in v))
        all_pass = sum(1 for v in by_task.values() if all(x["passed"] for x in v))
        flaky = sorted(
            ({"task_id": tid,
              "passed": sum(1 for x in v if x["passed"]),
              "attempts": len(v)}
             for tid, v in by_task.items()
             if 0 < sum(1 for x in v if x["passed"]) < len(v)),
            key=lambda d: d["task_id"])

        models_out.append({
            "model_id": model_id,
            "model_path": plan_models.get(model_id, {}).get("model_path"),
            "label": plan_models.get(model_id, {}).get("label", model_id),
            "n": len(gs),
            "passed": len(passes),
            "pass_rate": round(len(passes) / len(gs), 3),
            "tasks": len(by_task),
            "epochs_max": epochs,
            "empirical_any_repeat_rate": round(any_pass / len(by_task), 3) if by_task else None,
            "empirical_all_repeat_rate": round(all_pass / len(by_task), 3) if by_task else None,
            "pass_at_k": round(any_pass / len(by_task), 3) if by_task else None,
            "pass_all_k": round(all_pass / len(by_task), 3) if by_task else None,
            "flaky_tasks": flaky,
            "median_runtime_ms": round(statistics.median(lat)) if lat else None,
            "max_runtime_ms": max(lat) if lat else None,
            "mean_output_tokens": round(statistics.mean(out_tok)) if out_tok else None,
            "total_tokens_spent": sum(tot_tok) if tot_tok else None,
            "total_tokens_per_pass": round(sum(tot_tok) / len(passes)) if tot_tok and passes else None,
            "by_class": dict(sorted(by_class.items())),
            "failures": [{"task_id": g["task_id"], "reason": g["reason"]} for g in gs if not g["passed"]],
        })

    ungraded = sum(1 for g in graded if g.get("reason") == "ungraded_exec_disabled")
    not_run = sum(1 for g in graded if g.get("reason") == "not_run")
    # Fatal evidence inconsistencies: nonzero exit, card marked invalid and
    # non-accepting; never claim valid model rates from a corrupt run.
    card_invalid = bool(malformed_lines or non_object_lines or extra_rows
                        or any(g.get("reason") in ("duplicate_row", "schema_mismatch", "run_mismatch")
                               for g in graded))
    card = {
        "schema": SCORECARD_SCHEMA,
        "run_id": args.run_id,
        "generated_at_utc": _now_iso(),
        "task_set_id": plan["task_set_id"],
        "plan_schema": plan.get("schema"),
        "plan_generated_at_utc": plan.get("generated_at_utc"),
        "live_grading_key_drift": drifted,
        "exec_grading_enabled": bool(args.allow_exec),
        "raw_row_count": raw_row_count,
        "planned_cells": len(planned_ids),
        "rows_graded": len(graded),
        "extra_invalid_rows": len(extra_rows),
        "rows_ungraded_exec_disabled": ungraded,
        "rows_not_run": not_run,
        "rows_malformed_lines": malformed_lines[:20],
        "rows_non_object_lines": non_object_lines[:20],
        "invalid_evidence": card_invalid,
        "accepting": not card_invalid,
        "models": [] if card_invalid else models_out,
        "authority": {"review_only": True, "repair_allowed": False, "owner_approval_inferred": False,
                      "routing_change_authority": False},
        "caveat": "Small-n exploratory bench. It reports what these prompts elicited, not a general capability ranking, and confers no automatic routing change."
                  + (" INVALID run evidence: rates withheld." if card_invalid else ""),
    }
    if not card_invalid:
        card["models"] = models_out
    else:
        card["models_suppressed_due_to_invalid_evidence"] = True
    SCORECARD_JSON.parent.mkdir(parents=True, exist_ok=True)
    # New versioned scorecards per run; historical source evidence is never rewritten.
    versioned_json = SCORECARD_JSON.parent / f"model-arena-scorecard-{args.run_id}.json"
    versioned_md = SCORECARD_JSON.parent / f"model-arena-scorecard-{args.run_id}.md"
    payload = json.dumps(card, indent=1)
    SCORECARD_JSON.write_text(payload, encoding="utf-8")
    SCORECARD_MD.write_text(_render_md(card), encoding="utf-8")
    versioned_json.write_text(payload, encoding="utf-8")
    versioned_md.write_text(_render_md(card), encoding="utf-8")

    if card_invalid:
        print(f"score FAILED run_id={args.run_id}: invalid run evidence "
              f"(malformed={len(malformed_lines)} non_object={len(non_object_lines)} "
              f"extra={len(extra_rows)} fatal_cells={sum(1 for g in graded if g.get('reason') in ('duplicate_row','schema_mismatch','run_mismatch'))}); "
              f"card marked invalid/non-accepting")
        return 2
    print(f"score ok run_id={args.run_id} rows={len(graded)} models={len(models_out)} exec_grading={bool(args.allow_exec)}")
    for m in models_out:
        print(f"  {m['label']:<34} pass {m['passed']}/{m['n']} ({m['pass_rate']:.0%})  "
              f"median {m['median_runtime_ms']}ms  out~{m['mean_output_tokens']} tok")
    if ungraded:
        print(f"  NOTE: {ungraded} code task(s) left ungraded; rerun with --allow-exec to execute them.")
    print(f"  -> {SCORECARD_JSON.relative_to(ROOT)} / {SCORECARD_MD.relative_to(ROOT)}")
    return 0


def _render_md(card: dict) -> str:
    L = [f"# Model Arena scorecard - {card['run_id']}", "",
         f"Task set `{card['task_set_id']}` | generated {card['generated_at_utc']} | "
         f"exec grading: {'on' if card['exec_grading_enabled'] else 'OFF'}", "",
         f"> {card['caveat']}", ""]
    if card.get("invalid_evidence"):
        L += [f"INVALID run evidence: raw_rows={card.get('raw_row_count')} "
              f"planned={card.get('planned_cells')} extra_invalid={card.get('extra_invalid_rows')}. "
              f"Model rates withheld; fix evidence and re-run.", ""]
        return "\n".join(L) + "\n"
    L += ["| Model | Attempts | Rate | Tasks | Epochs | any-repeat | all-repeat | Median ms | Mean out tok | Tokens/pass |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for m in card["models"]:
        pk = "-" if m.get("empirical_any_repeat_rate") is None else f"{m['empirical_any_repeat_rate']:.0%}"
        pak = "-" if m.get("empirical_all_repeat_rate") is None else f"{m['empirical_all_repeat_rate']:.0%}"
        L.append(f"| {m['label']} | {m['passed']}/{m['n']} | {m['pass_rate']:.0%} | "
                 f"{m['tasks']} | {m['epochs_max']} | {pk} | {pak} | "
                 f"{m['median_runtime_ms']} | {m['mean_output_tokens']} | {m['total_tokens_per_pass']} |")
    if card["models"] and max(m["epochs_max"] for m in card["models"]) < 2:
        L += ["", "> Single epoch: any-repeat and all-repeat both equal the raw pass rate and say nothing "
                  "about reliability. Rerun with `--repeats N` to make them meaningful."]
    flakies = [(m["label"], f) for m in card["models"] for f in m["flaky_tasks"]]
    if flakies:
        L += ["", "## Flaky tasks (passed some attempts, failed others)", "",
              "| Model | Task | Passed |", "|---|---|---|"]
        L += [f"| {lab} | {f['task_id']} | {f['passed']}/{f['attempts']} |" for lab, f in flakies]
    L += ["", "## By task class", "", "| Model | Class | Pass rate |", "|---|---|---|"]
    for m in card["models"]:
        for cls, c in m["by_class"].items():
            L.append(f"| {m['label']} | {cls} | {c['passed']}/{c['n']} |")
    fails = [(m["label"], f) for m in card["models"] for f in m["failures"]]
    if fails:
        L += ["", "## Failures", "", "| Model | Task | Reason |", "|---|---|---|"]
        L += [f"| {lab} | {f['task_id']} | `{f['reason']}` |" for lab, f in fails]
    return "\n".join(L) + "\n"


def validate() -> int:
    problems = []
    for path, key in ((ROSTER_PATH, "models"), (TASKS_PATH, "tasks")):
        if not path.exists():
            problems.append(f"missing {path.name}")
            continue
        try:
            doc = _load(path)
        except json.JSONDecodeError as e:
            problems.append(f"{path.name} is not valid JSON: {e.msg}")
            continue
        if key not in doc:
            problems.append(f"{path.name} missing '{key}'")

    if not problems:
        roster = _load(ROSTER_PATH)
        seen = set()
        for m in roster["models"]:
            for f in ("id", "model_path", "label", "enabled"):
                if f not in m:
                    problems.append(f"roster entry {m.get('id', '?')} missing '{f}'")
            if m.get("id") in seen:
                problems.append(f"duplicate roster id {m['id']}")
            seen.add(m.get("id"))
            if m.get("enabled") and not m.get("dispatch_verified_phx"):
                problems.append(f"roster {m['id']} enabled but never dispatch-verified")
            if "::" in str(m.get("id", "")):
                problems.append(f"roster id {m['id']} may not contain '::' (pair_id delimiter)")

        tasks = _load(TASKS_PATH)
        tseen = set()
        for t in tasks["tasks"]:
            tid = t.get("id", "?")
            for f in ("id", "class", "prompt", "grade"):
                if f not in t:
                    problems.append(f"task {tid} missing '{f}'")
            if tid in tseen:
                problems.append(f"duplicate task id {tid}")
            tseen.add(tid)
            if "::" in str(tid):
                problems.append(f"task id {tid} may not contain '::'")
            g = t.get("grade", {})
            if g.get("mode") not in GRADE_MODES:
                problems.append(f"task {tid} has unknown grade mode {g.get('mode')!r}")
            if g.get("mode") == "code_exec" and not g.get("asserts"):
                problems.append(f"task {tid} is code_exec with no asserts")
            if g.get("mode") == "json_output" and not g.get("required_keys"):
                problems.append(f"task {tid} is json_output with no required_keys")

    if problems:
        print("validation FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    r, t = _load(ROSTER_PATH), _load(TASKS_PATH)
    enabled = sum(1 for m in r["models"] if m.get("enabled"))
    classes = sorted({x["class"] for x in t["tasks"]})
    print(f"validation ok: {len(r['models'])} models ({enabled} enabled), "
          f"{len(t['tasks'])} tasks across {len(classes)} classes: {', '.join(classes)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Standalone model-agnostic capability arena.")
    ap.add_argument("--plan", action="store_true", help="emit the dispatch plan for the agent layer")
    ap.add_argument("--score", action="store_true", help="grade a completed run and emit the scorecard")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--run-id")
    ap.add_argument("--models", help="comma-separated roster ids; overrides the enabled flag")
    ap.add_argument("--tasks", help="comma-separated task ids")
    ap.add_argument("--classes", help="comma-separated task classes")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--tasks-file", help="task set filename under data/evals/model-arena/ (default tasks.json)")
    ap.add_argument("--allow-exec", action="store_true",
                    help="execute model-produced code for code_exec tasks (subprocess, %ds timeout, static safety scan first)" % EXEC_TIMEOUT_S)
    args = ap.parse_args()
    if not (args.plan or args.score or args.validate):
        ap.error("pick at least one of --plan / --score / --validate")
    if args.tasks_file:
        global TASKS_PATH
        TASKS_PATH = ARENA / args.tasks_file
        if not TASKS_PATH.exists():
            ap.error(f"task set not found: {TASKS_PATH}")
    rc = 0
    if args.validate:
        rc = validate() or rc
    if args.plan:
        rc = build_plan(args) or rc
    if args.score:
        rc = score(args) or rc
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
