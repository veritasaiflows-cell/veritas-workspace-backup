"""Agentic file-work arena.

Unlike model_arena.py, nothing here grades chat text. Each model is handed a real
directory containing real broken code and real tools, and is graded on the state of
the files it leaves behind plus the authoritative test suite.

  python scripts\\arena_filework.py --prepare --run-id fw-YYYYMMDD
  python scripts\\arena_filework.py --grade   --run-id fw-YYYYMMDD

Honest limit: container controls constrain the grading workload but are not a
formal proof against malicious in-container grader interference.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from arena_harness import (
        check_nonce_marker_line,
        ensure_within,
        is_safe_relname,
        is_safe_run_id,
        is_stdlib_shadow_name,
        make_nonce_marker,
        run_sandboxed_command,
        sha256_text,
    )
except ImportError:  # pragma: no cover
    from scripts.arena_harness import (  # type: ignore[no-redef]
        check_nonce_marker_line,
        ensure_within,
        is_safe_relname,
        is_safe_run_id,
        is_stdlib_shadow_name,
        make_nonce_marker,
        run_sandboxed_command,
        sha256_text,
    )

MARKER_SCHEMA = "veritas.arena_filework_marker.v1"

ROOT = Path(__file__).resolve().parent.parent
ARENA = ROOT / "data" / "evals" / "model-arena"
TASKS_DIR = ARENA / "tasks-v3"
TASKS_PATH = TASKS_DIR / "tasks-v3.json"
ROSTER_PATH = ARENA / "roster.json"
RUNS_ROOT = ROOT / "tmp" / "arena-v3"
PLAN_PATH = ROOT / "tmp" / "arena-filework-plan.json"
PLANS_DIR = ROOT / "tmp" / "arena-filework-plans"
CARD_JSON = ROOT / "tmp" / "arena-filework-scorecard.json"
CARD_MD = ROOT / "tmp" / "arena-filework-scorecard.md"

IGNORED = {"__pycache__", ".pytest_cache"}
VERIFY_TIMEOUT_S = 120
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _workdir(run_id: str, model_id: str, task_id: str) -> Path:
    return RUNS_ROOT / run_id / model_id / task_id


def _visible(d: Path) -> list[str]:
    return sorted(p.name for p in d.iterdir() if p.name not in IGNORED)


def _is_safe_id(s: object) -> bool:
    return isinstance(s, str) and bool(_ID_RE.match(s)) and "::" not in s


def _seed_hashes(seed_dir: Path) -> dict[str, str]:
    out = {}
    for f in sorted(seed_dir.iterdir()):
        if f.is_file() and not f.is_symlink():
            out[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def _reject_seed_links(seed_dir: Path) -> str | None:
    """Reject symlinks/junctions/reparse/escapes in seed before ANY copy/read."""
    if not seed_dir.is_dir():
        return f"seed_missing:{seed_dir.name}"
    for p in seed_dir.iterdir():
        if p.is_symlink():
            return f"seed_symlink:{p.name}"
        if not is_safe_relname(p.name):
            return f"seed_unsafe_name:{p.name}"
        try:
            ensure_within(seed_dir, p)
        except ValueError:
            return f"seed_escape:{p.name}"
    return None


def _per_run_plan_path(run_id: str) -> Path:
    return PLANS_DIR / f"arena-filework-plan-{run_id}.json"


def _load_filework_plan(run_id: str) -> dict | None:
    # Immutable per-run plan only; never fall back to a mutable convenience
    # pointer when the per-run file is missing/corrupt, so fw1 still grades
    # after fw2 is prepared.
    cand = _per_run_plan_path(run_id)
    try:
        doc = json.loads(cand.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(doc, dict) and doc.get("run_id") == run_id:
        return doc
    return None


def prepare(args) -> int:
    if not is_safe_run_id(args.run_id):
        print(f"prepare FAILED: unsafe run_id {args.run_id!r}")
        return 1
    tasks = _load(TASKS_PATH)
    roster = _load(ROSTER_PATH)["models"]
    wanted = set(args.models.split(",")) if args.models else None
    if wanted:
        if any(not _is_safe_id(w) for w in wanted):
            print("prepare FAILED: unsafe --models selector")
            return 1
        known = {m["id"] for m in roster}
        unknown = sorted(wanted - known)
        if unknown:
            print(f"prepare FAILED: unknown --models selector(s): {unknown}")
            return 1
    models = [m for m in roster if (m["id"] in wanted if wanted else m.get("enabled"))]
    only = set(args.tasks.split(",")) if args.tasks else None
    if only:
        if any(not _is_safe_id(w) for w in only):
            print("prepare FAILED: unsafe --tasks selector")
            return 1
        known_t = {t["id"] for t in tasks["tasks"]}
        unknown_t = sorted(only - known_t)
        if unknown_t:
            print(f"prepare FAILED: unknown --tasks selector(s): {unknown_t}")
            return 1
    picked = [t for t in tasks["tasks"] if (t["id"] in only if only else True)]
    if not models or not picked:
        print("prepare FAILED: no models or no tasks selected")
        return 1
    for m in models:
        if not _is_safe_id(m.get("id")) or not isinstance(m.get("model_path"), str):
            print(f"prepare FAILED: unsafe model id {m.get('id')!r}")
            return 1
    for t in picked:
        if not _is_safe_id(t.get("id")):
            print(f"prepare FAILED: unsafe task id {t.get('id')!r}")
            return 1
    # Refuse an existing run instead of deleting it: destructive restaging is out
    # of scope and prior candidate work is user-owned.
    run_root = RUNS_ROOT / args.run_id
    if run_root.exists():
        print(f"prepare FAILED: run dir already exists at {run_root}; pick a fresh --run-id (refusing to delete prior work)")
        return 1
    if _per_run_plan_path(args.run_id).exists():
        print(f"prepare FAILED: per-run plan already exists for {args.run_id}; refusing to overwrite")
        return 1

    pairs = []
    frozen_tasks = []
    for m in models:
        for t in picked:
            seed_dir = TASKS_DIR / t["dir"] / "seed"
            bad = _reject_seed_links(seed_dir)
            if bad:
                print(f"prepare FAILED: {bad}")
                return 1
            wd = _workdir(args.run_id, m["id"], t["id"])
            if wd.exists():
                print(f"prepare FAILED: workdir already exists at {wd}; refusing to delete (fresh --run-id required)")
                return 1
            wd.parent.mkdir(parents=True, exist_ok=True)
            # No following of outside links during copytree: seed was
            # pre-scanned for symlinks; copy file bytes explicitly.
            wd.mkdir(parents=True, exist_ok=False)
            for f in sorted(seed_dir.iterdir()):
                if f.is_file() and not f.is_symlink() and f.name not in IGNORED:
                    if not is_safe_relname(f.name):
                        print(f"prepare FAILED: unsafe seed name {f.name!r}")
                        return 1
                    (wd / f.name).write_bytes(f.read_bytes())
            pair_id = f"{m['id']}::{t['id']}"
            prompt = (TASKS_DIR / t["dir"] / "prompt.md").read_text(encoding="utf-8")
            pairs.append({
                "pair_id": pair_id,
                "model_id": m["id"],
                "model_path": m["model_path"],
                "task_id": t["id"],
                "workdir": str(wd),
                "prompt": prompt.replace("{PAIR_ID}", pair_id).replace("{WORKDIR}", str(wd)),
                "attachments": [
                    {"name": f.name, "mimeType": "text/x-python", "encoding": "utf8",
                     "content": f.read_text(encoding="utf-8")}
                    for f in sorted(seed_dir.iterdir())
                    if f.is_file() and not f.is_symlink() and is_safe_relname(f.name)
                ],
            })
    for t in picked:
        seed_dir = TASKS_DIR / t["dir"] / "seed"
        frozen_tasks.append({
            "id": t["id"], "dir": t["dir"],
            "grade": t.get("verify"),
            "grade_sha256": sha256_text(json.dumps(t.get("verify"), sort_keys=True)),
            "protected_files": list(t.get("protected_files", [])),
            "diff_budget": json.loads(json.dumps(t.get("diff_budget"))) if t.get("diff_budget") is not None else None,
            "forbidden_tokens": list(t.get("forbidden_tokens")) if t.get("forbidden_tokens") is not None else None,
            "seed_hashes": _seed_hashes(seed_dir),
        })

    plan = {
        "schema": "veritas.model_arena_filework_plan.v1",
        "run_id": args.run_id,
        "generated_at_utc": _now(),
        "task_set_id": _load(TASKS_PATH)["task_set_id"],
        "frozen_tasks": frozen_tasks,
        "models": [{"id": m["id"], "model_path": m["model_path"],
                    "label": m.get("label", m["id"])} for m in models],
        "dispatch_contract": {
            "agent_id": "implementation-builder",
            "note": "Dispatch must originate from an OpenClaw-runtime session under its own authority. This plan never auto-spawns children or changes config.",
            "spawn_args": {
                "agentId": "implementation-builder",
                "model": "<model_path from this plan (frozen)>",
                "context": "isolated",
                "mode": "run",
                "collect": True,
                "task": "<prompt from this plan, verbatim>",
            },
            "note_paths": "Children run with tools.exec.host=sandbox and cannot reach host paths. "
                          "Seed files are staged by prepare; edited files are harvested back from "
                          "the sandbox mirror via --harvest. Attachment transport is supported only "
                          "where the runtime documents it; absence is reported, never assumed.",
            "marker_contract": "Each child writes PAIR.txt containing exactly two lines: "
                               f"<run_id>\\n<pair_id> (schema {MARKER_SCHEMA}). Markers bound to a "
                               "different run_id, ambiguous duplicates, or paths escaping the sandbox "
                               "root are rejected, never newest-wins.",
        },
        "pairs": pairs,
        "authority": {"review_only": True, "routing_change_authority": False},
    }
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    per_run_text = json.dumps(plan, indent=1)
    _per_run_plan_path(args.run_id).write_text(per_run_text, encoding="utf-8")
    # Convenience pointer only; harvest/grade always load the per-run file.
    PLAN_PATH.write_text(per_run_text, encoding="utf-8")
    print(f"prepare ok run_id={args.run_id} pairs={len(pairs)}")
    for p in pairs:
        print(f"  {p['pair_id']:<45} -> {p['workdir']}")
    print(f"  -> {PLAN_PATH.relative_to(ROOT)}")
    return 0


SANDBOX_ROOT = Path.home() / ".openclaw" / "sandboxes"


def _read_marker(marker: Path, run_id: str, by_pair: dict) -> str | None:
    """Validate a PAIR.txt marker. Returns the pair_id or None with a printed reason."""
    try:
        root_r = SANDBOX_ROOT.resolve()
        marker_r = marker.resolve()
        try:
            marker_r.relative_to(root_r)
        except ValueError:
            print(f"  marker REJECTED (path escape): {marker}")
            return None
        if marker.is_symlink():
            print(f"  marker REJECTED (symlink): {marker}")
            return None
        text = marker.read_text(encoding="utf-8")
    except (OSError, ValueError) as e:
        print(f"  marker REJECTED (unreadable {marker}): {e}")
        return None
    lines = text.strip().splitlines()
    if len(lines) != 2:
        print(f"  marker REJECTED (expected '<run_id>\\n<pair_id>', got {len(lines)} lines): {marker}")
        return None
    m_run, pid = lines[0].strip(), lines[1].strip()
    if m_run != run_id:
        print(f"  marker REJECTED (run mismatch {m_run!r} != {run_id!r}): {marker}")
        return None
    if pid not in by_pair:
        print(f"  marker REJECTED (unknown pair {pid!r}): {marker}")
        return None
    return pid


def harvest(args) -> int:
    """Pull each child's edited files out of its sandbox mirror into the run dir.

    Children cannot write to host paths, so the sandbox is the only place their work
    exists. Each child drops a PAIR.txt marker bound to (run_id, pair_id); ambiguous
    duplicates and path/symlink escapes are rejected rather than newest-wins.
    Missing/ambiguous/stale/invalid harvests return nonzero with typed per-pair
    statuses (never a bare 'harvest ok').
    """
    if not is_safe_run_id(args.run_id):
        print(f"harvest FAILED: unsafe run_id {args.run_id!r}")
        return 1
    plan = _load_filework_plan(args.run_id)
    if plan is None:
        print(f"harvest FAILED: no frozen per-run plan for run_id={args.run_id}")
        return 1
    by_pair = {p["pair_id"]: p for p in plan["pairs"]}

    hits: dict[str, list[Path]] = {}
    if SANDBOX_ROOT.exists():
        for marker in SANDBOX_ROOT.glob("*/**/PAIR.txt"):
            pid = _read_marker(marker, args.run_id, by_pair)
            if pid is not None:
                hits.setdefault(pid, []).append(marker)

    statuses: dict[str, str] = {}
    harvested = 0
    for pid, pair in by_pair.items():
        markers = hits.get(pid, [])
        wd = Path(pair["workdir"])
        if not markers:
            statuses[pid] = "missing_marker"
            print(f"  {pid:<45} MISSING MARKER - nothing harvested")
            continue
        if len(markers) > 1:
            statuses[pid] = "ambiguous_markers"
            print(f"  {pid:<45} AMBIGUOUS ({len(markers)} markers) - nothing harvested")
            continue
        marker = markers[0]
        src = marker.parent
        names = [a["name"] for a in pair["attachments"] if is_safe_relname(a.get("name"))]
        # Reject linked/escaping input before ANY candidate content read/copy.
        try:
            ensure_within(src, src)
            ensure_within(wd.parent, wd)
        except ValueError:
            statuses[pid] = "path_escape"
            print(f"  {pid:<45} REJECTED escape")
            continue
        copied = []
        rejected = False
        for name in names:
            f = src / name
            try:
                if f.is_symlink() or not f.is_file():
                    continue
                ensure_within(src, f)
            except ValueError:
                print(f"  {pid:<45} REJECTED escape: {name}")
                rejected = True
                continue
            try:
                ensure_within(wd.parent, wd / name)
            except ValueError:
                print(f"  {pid:<45} REJECTED escape: {name}")
                rejected = True
                continue
            shutil.copyfile(f, wd / name)
            copied.append(name)
        if rejected:
            statuses[pid] = "invalid_input"
            continue
        # Stale check: harvested workdir must contain at least the seed names.
        if not any((wd / n).exists() for n in names):
            statuses[pid] = "stale_harvest"
            print(f"  {pid:<45} STALE - nothing usable harvested")
            continue
        statuses[pid] = "harvested"
        harvested += 1
        print(f"  {pid:<45} <- {src}  files={copied or 'NONE'}")

    bad = {k: v for k, v in statuses.items() if v != "harvested"}
    if bad:
        print(f"harvest INCOMPLETE run_id={args.run_id} harvested={harvested}/{len(by_pair)} "
              f"statuses={json.dumps(bad, sort_keys=True)}")
        return 2
    print(f"harvest ok run_id={args.run_id} pairs_with_output={harvested}/{len(by_pair)}")
    return 0


def _count_changed_lines(before: str, after: str) -> int:
    diff = difflib.unified_diff(before.rstrip().splitlines(), after.rstrip().splitlines(), n=0)
    return sum(1 for ln in diff
               if (ln.startswith("+") or ln.startswith("-"))
               and not ln.startswith(("+++", "---")))


def _write_unittest_shim(grade_dir: Path, module: str, nonce: str) -> Path:
    """Trusted shim: loads stdlib unittest, counts tests, prints nonce on success."""
    shim = grade_dir / "_arena_shim.py"
    shim.write_text(
        "import sys, unittest\n"
        f"MODULE={module!r}\n"
        f"NONCE={nonce!r}\n"
        "loader=unittest.TestLoader()\n"
        "suite=loader.loadTestsFromName(MODULE)\n"
        "count=suite.countTestCases()\n"
        "print(f'ARENA_TESTS:{count}')\n"
        "if count<=0:\n"
        "    print('ARENA_NO_TESTS'); sys.exit(2)\n"
        "res=unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)\n"
        "if res.wasSuccessful():\n"
        f"    print(NONCE)\n"
        "    sys.exit(0)\n"
        "sys.exit(1)\n",
        encoding="utf-8")
    return shim


def _grade_pair(task: dict, wd: Path) -> dict:
    seed = TASKS_DIR / task["dir"] / "seed"
    out: dict = {"workdir": str(wd)}

    if not wd.exists():
        return {**out, "passed": False, "clean": False, "reason": "workdir_missing"}

    present = set(_visible(wd))
    try:
        seed_names = set(_visible(seed))
    except OSError:
        return {**out, "passed": False, "clean": False, "reason": "seed_missing"}
    out["extra_files_created"] = sorted(present - seed_names)
    out["files_deleted"] = sorted(seed_names - present)

    # Did the model touch a file it was told not to touch? A stripped trailing newline is
    # a file-writing artifact, not an attempt to weaken the suite, so it is reported
    # separately -- conflating the two would turn a clean run into a false cheating verdict.
    tampered, cosmetic = [], []
    for name in task.get("protected_files", []):
        if not is_safe_relname(name):
            tampered.append(name)
            continue
        cur, orig = wd / name, seed / name
        if cur.is_symlink():
            tampered.append(name)
            continue
        if not cur.exists():
            tampered.append(name)
            continue
        try:
            a, b = cur.read_text(encoding="utf-8"), orig.read_text(encoding="utf-8")
        except OSError:
            tampered.append(name)
            continue
        if a == b:
            continue
        (cosmetic if a.rstrip() == b.rstrip() else tampered).append(name)
    out["protected_files_modified"] = tampered
    out["protected_files_whitespace_only"] = cosmetic

    # Size of the edit, as a discipline signal separate from correctness. A multi-file task
    # budgets the sum across every file it is allowed to touch, so collateral edits to a
    # module the change never needed count against it.
    budget = task.get("diff_budget") or {}
    if budget:
        names = budget.get("files") or [budget["file"]]
        per_file, total = {}, 0
        for f in names:
            if not is_safe_relname(f):
                continue
            after = (wd / f).read_text(encoding="utf-8") if (wd / f).exists() and not (wd / f).is_symlink() else ""
            before = (seed / f).read_text(encoding="utf-8")
            n = _count_changed_lines(before, after)
            per_file[f] = n
            total += n
        out["changed_lines"] = total
        out["changed_lines_by_file"] = per_file
        out["diff_budget"] = budget["max_changed_lines"]
        out["within_diff_budget"] = total <= budget["max_changed_lines"]

    # A rename is only finished when no caller still points at the old name. Tests cannot
    # catch a stale reference in a module they never import, so scan the files directly.
    tokens = task.get("forbidden_tokens") or []
    if tokens:
        stale = []
        protected = set(task.get("protected_files", []))
        for name in _visible(wd):
            if name in protected or not name.endswith(".py"):
                continue
            if not is_safe_relname(name):
                continue
            body = (wd / name).read_text(encoding="utf-8", errors="replace")
            stale += [f"{name}:{tok}" for tok in tokens if tok in body]
        out["stale_references"] = sorted(stale)

    # Reject stdlib-shadow filenames/packages before any test run.
    for name in _visible(wd):
        if is_stdlib_shadow_name(name):
            out.update(verify_returncode=None, verify_tail=[f"stdlib_shadow:{name}"],
                       tests_passed=False, exec_status="stdlib_shadow",
                       passed=False, clean=False, reason="stdlib_shadow")
            return out

    allow_exec = bool(globals().get("_GRADE_ALLOW_EXEC", False))
    run_tag = str(globals().get("_GRADE_RUN_ID", "filework"))
    # Restore protected files ONLY inside a disposable grading copy; candidate
    # submission bytes on disk are never mutated here.
    with tempfile.TemporaryDirectory(prefix="arena-grade-") as td:
        grade_dir = Path(td) / "work"
        # No following outside links during copytree: copy bytes explicitly.
        grade_dir.mkdir(parents=True)
        for name in _visible(wd):
            if not is_safe_relname(name):
                continue
            src_f = wd / name
            if src_f.is_symlink() or not src_f.is_file():
                continue
            (grade_dir / name).write_bytes(src_f.read_bytes())
        if task["verify"].get("restore_protected_before_verify", True):
            for name in task.get("protected_files", []):
                if not is_safe_relname(name):
                    continue
                shutil.copyfile(seed / name, grade_dir / name)
        # Re-check shadows inside the grading copy (candidate may have added
        # a package dir shadowing stdlib).
        for name in _visible(grade_dir):
            if is_stdlib_shadow_name(name):
                out.update(verify_returncode=None, verify_tail=[f"stdlib_shadow:{name}"],
                           tests_passed=False, exec_status="stdlib_shadow")
                break
        else:
            if allow_exec is not True:
                out["verify_returncode"] = None
                out["verify_tail"] = ["candidate tests require --allow-exec (sandboxed Docker runner)"]
                out["tests_passed"] = False
                out["exec_status"] = "blocked_exec_disabled"
            else:
                module = task["verify"]["module"]
                nonce = make_nonce_marker()
                _write_unittest_shim(grade_dir, module, nonce)
                try:
                    res = run_sandboxed_command(
                        grade_dir, ["python3", "_arena_shim.py"],
                        VERIFY_TIMEOUT_S, True, run_tag, f"{wd.parent.name}::{task.get('id', wd.name)}")
                except Exception as e:
                    out["verify_returncode"] = None
                    out["verify_tail"] = [f"runner_error:{str(e)[:140]}"]
                    out["tests_passed"] = False
                    out["exec_status"] = "runner_error"
                    res = None
                if res is not None:
                    out["exec_status"] = res.get("status")
                    if res.get("status") == "timeout":
                        out["verify_returncode"] = None
                        out["verify_tail"] = ["verify_timeout"]
                        out["tests_passed"] = False
                    elif res.get("status") in ("missing_docker", "missing_image"):
                        out["verify_returncode"] = res.get("returncode")
                        out["verify_tail"] = [(res.get("stderr") or res.get("status", ""))[-200:]]
                        out["tests_passed"] = False
                    elif res.get("status") == "output_limit_exceeded":
                        # Output-cap with rc0 is still a non-pass.
                        out["verify_returncode"] = res.get("returncode")
                        out["verify_tail"] = ["output_limit_exceeded"]
                        out["tests_passed"] = False
                    else:
                        tail = ((res.get("stderr") or res.get("stdout")) or "").strip().splitlines()
                        out["verify_returncode"] = res.get("returncode")
                        out["verify_tail"] = tail[-4:] if tail else []
                        # Require status==ok AND passed AND rc0 AND fresh nonce
                        # exact line (unittest success alone never suffices).
                        out["tests_passed"] = (
                            res.get("status") == "ok" and res.get("passed") is True
                            and res.get("returncode") == 0
                            and check_nonce_marker_line(res.get("stdout", ""), res.get("returncode"), nonce))

    # A surviving stale reference is a real defect the suite cannot see, so it fails the
    # task outright rather than counting as untidiness.
    stale = out.get("stale_references") or []
    out["passed"] = bool(out.get("tests_passed") and not tampered and not stale)
    out["clean"] = bool(out["passed"]
                        and not out["extra_files_created"]
                        and not out["files_deleted"]
                        and out.get("within_diff_budget", True))
    if not out["passed"]:
        out["reason"] = ("protected_file_modified" if tampered
                         else "stdlib_shadow" if out.get("exec_status") == "stdlib_shadow"
                         else "ungraded_exec_disabled" if out.get("exec_status") == "blocked_exec_disabled"
                         else "verify_timeout" if out.get("exec_status") == "timeout"
                         else "verify_missing_runner" if out.get("exec_status") in ("missing_docker", "missing_image")
                         else "verify_output_limit" if out.get("exec_status") == "output_limit_exceeded"
                         else "verify_runner_error" if out.get("exec_status") == "runner_error"
                         else "stale_reference" if stale and out.get("tests_passed")
                         else "tests_failed")
    elif not out["clean"]:
        out["reason"] = "passed_but_undisciplined"
    else:
        out["reason"] = "ok"
    return out


def _usage_by_pair(path: Path) -> dict[str, dict]:
    """Read per-pair token/runtime records from a dispatch log.

    Token counts come from agents_wait and runtime from subagents(action=list), so a
    dispatcher transcribing either verbatim yields camelCase; hand-written records are
    snake_case. Accept both rather than silently scoring zero tokens.
    """
    raw = _load(path)
    rows = raw if isinstance(raw, list) else raw.get("pairs", [])
    out = {}
    for row in rows:
        pid = row.get("pair_id")
        if not pid:
            continue
        pick = lambda *keys: next((row[k] for k in keys if isinstance(row.get(k), (int, float))), None)
        inp = pick("input_tokens", "inputTokens")
        outp = pick("output_tokens", "outputTokens")
        out[pid] = {
            "input_tokens": inp,
            "output_tokens": outp,
            # subagents' totalTokens has been observed equal to input alone, so derive it.
            "total_tokens": None if inp is None or outp is None else inp + outp,
            "runtime_ms": pick("runtime_ms", "runtimeMs"),
        }
    return out


def _usd(roster_entry: dict, inp, outp):
    """Cost in USD, or None. Prices only ever come from an explicit roster field."""
    pin = roster_entry.get("usd_per_1m_input")
    pout = roster_entry.get("usd_per_1m_output")
    if pin is None or pout is None or inp is None or outp is None:
        return None
    return round(inp / 1_000_000 * pin + outp / 1_000_000 * pout, 4)


def grade(args) -> int:
    if not is_safe_run_id(args.run_id):
        print(f"grade FAILED: unsafe run_id {args.run_id!r}")
        return 1
    plan = _load_filework_plan(args.run_id)
    if plan is None:
        print(f"grade FAILED: no frozen per-run plan for run_id={args.run_id}")
        return 1
    # Use frozen task definitions/model paths; verify protected seed hashes
    # rather than silently accepting mutable live grading keys.
    frozen = {t["id"]: t for t in plan.get("frozen_tasks", [])}
    roster = {m["id"]: m for m in plan.get("models", [])}
    try:
        live_tasks = {t["id"]: t for t in _load(TASKS_PATH)["tasks"]}
    except (OSError, KeyError, json.JSONDecodeError):
        live_tasks = {}
    for tid, ft in frozen.items():
        lt = live_tasks.get(tid)
        if lt is not None and json.dumps(lt.get("verify"), sort_keys=True) != json.dumps(ft.get("grade"), sort_keys=True):
            print(f"grade WARNING: live grading keys drifted for {tid}; frozen plan authoritative")
        try:
            grade_canonical = json.dumps(ft.get("grade"), sort_keys=True)
        except (TypeError, ValueError):
            print(f"grade FAILED: frozen grade unserializable for {tid}")
            return 1
        if not isinstance(ft.get("grade_sha256"), str) or sha256_text(grade_canonical) != ft.get("grade_sha256"):
            print(f"grade FAILED: frozen grade hash mismatch for {tid}")
            return 1
        if "diff_budget" not in ft or "forbidden_tokens" not in ft:
            print(f"grade FAILED: incomplete frozen policy for {tid}; re-prepare run")
            return 1
        fdir = ft.get("dir")
        if not isinstance(fdir, str) or not is_safe_relname(fdir):
            print(f"grade FAILED: unsafe frozen dir for {tid}")
            return 1
        seed_dir = TASKS_DIR / fdir / "seed"
        bad = _reject_seed_links(seed_dir)
        if bad:
            print(f"grade FAILED: {bad} for {tid}")
            return 1
        expected = ft.get("seed_hashes")
        if not isinstance(expected, dict) or not expected:
            print(f"grade FAILED: missing frozen seed hashes for {tid}")
            return 1
        for name, h in expected.items():
            if not isinstance(name, str) or not is_safe_relname(name):
                print(f"grade FAILED: unsafe frozen seed entry for {tid}:{name!r}")
                return 1
            if not isinstance(h, str) or not h:
                print(f"grade FAILED: missing frozen seed hash for {tid}:{name}")
                return 1
            cur = seed_dir / name
            if cur.is_symlink() or not cur.is_file():
                print(f"grade FAILED: seed hash missing for {tid}:{name}")
                return 1
            try:
                ensure_within(seed_dir, cur)
            except ValueError:
                print(f"grade FAILED: seed_escape:{name} for {tid}")
                return 1
            if hashlib.sha256(cur.read_bytes()).hexdigest() != h:
                print(f"grade FAILED: seed hash drift for {tid}:{name}")
                return 1
        try:
            live_names = {p.name for p in seed_dir.iterdir() if p.is_file() and not p.is_symlink()}
        except OSError:
            print(f"grade FAILED: seed unreadable for {tid}")
            return 1
        for name in sorted(live_names):
            if name in IGNORED:
                continue
            if not is_safe_relname(name) or name not in expected:
                print(f"grade FAILED: unexpected seed entry for {tid}:{name}")
                return 1
    # Capability-only by default: --usage is optional; accounting attached only when supplied.
    usage = _usage_by_pair(Path(args.usage)) if getattr(args, "usage", None) else {}
    globals()["_GRADE_ALLOW_EXEC"] = bool(getattr(args, "allow_exec", False))
    globals()["_GRADE_RUN_ID"] = args.run_id
    run_root = RUNS_ROOT / args.run_id
    if not run_root.exists():
        print(f"grade FAILED: no run dir at {run_root}; run --prepare first")
        return 1
    if not getattr(args, "allow_exec", False):
        print("grade NOTE: capability-only (candidate tests blocked without --allow-exec; sandboxed Docker runner required)")

    # Point TASKS_DIR lookups at frozen records for grading.
    results = []
    for model_dir in sorted(p for p in run_root.iterdir() if p.is_dir()):
        for task_dir in sorted(p for p in model_dir.iterdir() if p.is_dir()):
            ft = frozen.get(task_dir.name)
            if ft is None:
                continue
            # Rebuild the minimal task view the grader needs from frozen data.
            # Live policy is diagnostic only and never consumed here.
            task = {"id": task_dir.name, "dir": ft.get("dir"),
                    "protected_files": ft.get("protected_files", []),
                    "diff_budget": ft.get("diff_budget"),
                    "forbidden_tokens": ft.get("forbidden_tokens"),
                    "verify": ft.get("grade")}
            if not task["dir"] or not task["verify"]:
                continue
            pair_id = f"{model_dir.name}::{task_dir.name}"
            # One bad pair (timeout/missing module/runner failure) must never
            # lose the other pair records: typed non-pass, keep going.
            try:
                # Temporarily point TASKS_DIR at the frozen dir layout for seed reads.
                r = _grade_pair(task, task_dir)
            except Exception as e:
                r = {"workdir": str(task_dir), "passed": False, "clean": False,
                     "reason": f"grader_error:{str(e)[:120]}",
                     "verify_returncode": None, "verify_tail": [],
                     "tests_passed": False}
            r.update({"model_id": model_dir.name, "task_id": task_dir.name,
                      "pair_id": pair_id,
                      "label": roster.get(model_dir.name, {}).get("label", model_dir.name)})
            u = usage.get(pair_id)
            if u:
                r["usage"] = dict(u, usd=_usd(roster.get(model_dir.name, {}),
                                              u["input_tokens"], u["output_tokens"]))
            results.append(r)

    if not results:
        print("grade FAILED: no gradable pairs found")
        return 1

    by_model: dict[str, list[dict]] = {}
    for r in results:
        by_model.setdefault(r["model_id"], []).append(r)

    models_out = []
    for mid, rs in sorted(by_model.items()):
        # Cost per accepted change: spend across every attempt, divided by the attempts
        # that were actually acceptable. Failed and undisciplined work still cost tokens,
        # so a model that is cheap per call but needs two tries is not cheap.
        us = [r["usage"] for r in rs if r.get("usage")]
        accepted = sum(1 for r in rs if r["reason"] == "ok")
        tot = sum(u["total_tokens"] for u in us if u["total_tokens"] is not None) or None
        usd = sum(u["usd"] for u in us if u["usd"] is not None) or None
        ms = sum(u["runtime_ms"] for u in us if u["runtime_ms"] is not None) or None
        models_out.append({
            "model_id": mid,
            "label": roster.get(mid, {}).get("label", mid),
            "n": len(rs),
            "passed": sum(1 for r in rs if r["passed"]),
            "clean": sum(1 for r in rs if r["clean"]),
            "accepted": accepted,
            "tampered": sum(1 for r in rs if r.get("protected_files_modified")),
            "over_budget": sum(1 for r in rs if r.get("within_diff_budget") is False),
            "stale_refs": sum(1 for r in rs if r.get("stale_references")),
            "usage_rows": len(us),
            "total_tokens": tot,
            "total_usd": None if usd is None else round(usd, 4),
            "total_runtime_ms": ms,
            "tokens_per_accepted_change": None if not (tot and accepted) else round(tot / accepted),
            "usd_per_accepted_change": None if not (usd and accepted) else round(usd / accepted, 4),
            "results": rs,
        })

    card = {
        "schema": "veritas.model_arena_filework_scorecard.v1",
        "run_id": args.run_id,
        "generated_at_utc": _now(),
        "task_set_id": plan.get("task_set_id"),
        "models": models_out,
        "authority": {"review_only": True, "routing_change_authority": False},
        "caveat": "Graded from files on disk and a restored authoritative test suite. Model chat text "
                  "was not used as evidence. Small-n exploratory bench; confers no routing change.",
    }
    CARD_JSON.write_text(json.dumps(card, indent=1), encoding="utf-8")
    CARD_MD.write_text(_render(card), encoding="utf-8")
    print(f"grade ok run_id={args.run_id} pairs={len(results)}")
    for m in models_out:
        print(f"  {m['label']:<34} pass {m['passed']}/{m['n']}  clean {m['clean']}/{m['n']}  "
              f"tampered {m['tampered']}  over-budget {m['over_budget']}")
    print(f"  -> {CARD_JSON.relative_to(ROOT)} / {CARD_MD.relative_to(ROOT)}")
    return 0


def _render(card: dict) -> str:
    L = [f"# Agentic file-work scorecard - {card['run_id']}", "",
         f"Task set `{card['task_set_id']}` | generated {card['generated_at_utc']}", "",
         f"> {card['caveat']}", "",
         "| Model | Passed | Clean | Accepted | Tampered | Over diff budget | Stale refs |",
         "|---|---|---|---|---|---|---|"]
    for m in card["models"]:
        L.append(f"| {m['label']} | {m['passed']}/{m['n']} | {m['clean']}/{m['n']} | "
                 f"{m.get('accepted', '-')}/{m['n']} | "
                 f"{m['tampered']} | {m['over_budget']} | {m.get('stale_refs', 0)} |")

    if any(m.get("usage_rows") for m in card["models"]):
        L += ["", "## Cost per accepted change", "",
              "| Model | Usage rows | Total tokens | Tokens / accepted | USD / accepted | Total runtime |",
              "|---|---|---|---|---|---|"]
        for m in card["models"]:
            ms = m.get("total_runtime_ms")
            L.append(f"| {m['label']} | {m.get('usage_rows', 0)}/{m['n']} | "
                     f"{m.get('total_tokens') or '-'} | "
                     f"{m.get('tokens_per_accepted_change') or '-'} | "
                     f"{m.get('usd_per_accepted_change') or 'no price set'} | "
                     f"{'-' if ms is None else f'{ms / 1000:.0f}s'} |")
        L += ["", "USD is blank unless the roster entry carries explicit "
                  "`usd_per_1m_input` / `usd_per_1m_output`. No prices are inferred."]

    L += ["", "## Per task", "",
          "| Model | Task | Tests | Protected | Changed lines | Stale refs | Extra files | Tokens | Verdict |",
          "|---|---|---|---|---|---|---|---|---|"]
    for m in card["models"]:
        for r in m["results"]:
            u = r.get("usage") or {}
            L.append(
                f"| {m['label']} | {r['task_id']} | {'pass' if r.get('tests_passed') else 'FAIL'} | "
                f"{'TAMPERED' if r.get('protected_files_modified') else ('intact (ws)' if r.get('protected_files_whitespace_only') else 'intact')} | "
                f"{r.get('changed_lines', '-')}/{r.get('diff_budget', '-')} | "
                f"{', '.join(r.get('stale_references') or []) or 'none'} | "
                f"{', '.join(r.get('extra_files_created') or []) or 'none'} | "
                f"{u.get('total_tokens') or '-'} | `{r['reason']}` |")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Agentic file-work arena.")
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--harvest", action="store_true")
    ap.add_argument("--grade", action="store_true")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--models", help="comma-separated roster ids; overrides the enabled flag")
    ap.add_argument("--tasks", help="comma-separated task ids")
    ap.add_argument("--usage", default=None,
                    help="optional dispatch-log path for token/runtime accounting; --grade is capability-only without it")
    ap.add_argument("--allow-exec", action="store_true",
                    help="run candidate tests ONLY inside the pinned local sandboxed Docker image ID (default: blocked/ungraded)")
    args = ap.parse_args()
    if args.prepare:
        return prepare(args)
    if args.harvest:
        return harvest(args)
    if args.grade:
        return grade(args)
    ap.error("choose --prepare, --harvest or --grade")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
