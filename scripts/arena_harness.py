"""Shared harness helpers for ARENA-HARNESS-P0-20260919 (stdlib only).

Owner: Randall. Main integrates/accepts. This module owns deterministic,
host-safe helpers shared by model_arena.py and arena_filework.py:

  - safe run identifiers and bounded paths
  - strict JSON-object parsing (no fences/prose/duplicates/NaN/Infinity,
    recursive nonfinite rejection, ASCII-only transport normalization)
  - transport receipts (expected vs observed prompt, requested vs observed
    model, explicit fallback False; raw SHA256 recorded separately from the
    declared canonical comparison)
  - fail-closed Docker runner (local image ID only, explicit --allow-exec)

Security posture (honest limits): the Docker runner constrains an
untrusted grading workload but sandbox containment is NOT a formal proof
against malicious grader interference. Static regex scans are advisory
only and never imply containment. Nonce markers raise the bar against
trivial print-spoofing but are not formal protection.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import subprocess
import threading
import time
import uuid
from pathlib import Path

HARNESS_SCHEMA = "veritas.arena_harness.v1"
DOCKER_IMAGE = "openclaw-sandbox:bookworm-slim-python-calibration-r1"
DOCKER_BIN = "docker"
SUCCESS_MARKER = "ARENA_PASS"
# Finite caps: candidate container stdout+stderr combined (streamed, never
# buffered unbounded), and host docker-metadata outputs (inspect/rm).
OUTPUT_CAP_BYTES = 1 << 20  # 1 MiB combined candidate stdout+stderr
HOST_META_CAP_BYTES = 65536  # 64 KiB host control-output cap
_CHUNK = 65536

_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_CONTAINER_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

# Candidate stdlib-shadow names rejected as typed invalid artifacts before any
# in-container test run (unittest shim would otherwise load candidate code as
# stdlib). Minimal set covering the shim path plus common stdlib modules.
STDLIB_SHADOW_NAMES = frozenset({
    "unittest.py", "unittest", "os.py", "sys.py", "subprocess.py",
    "json.py", "pathlib.py", "shutil.py", "socket.py", "re.py",
    "hashlib.py", "threading.py", "time.py", "io.py", "collections.py",
    "functools.py", "itertools.py", "typing.py", "dataclasses.py",
    "enum.py", "abc.py", "copy.py", "pickle.py", "sqlite3.py",
})


def is_safe_run_id(run_id: object) -> bool:
    return isinstance(run_id, str) and bool(_RUN_ID_RE.match(run_id))


def assert_safe_run_id(run_id: object) -> str:
    if not is_safe_run_id(run_id):
        raise ValueError(f"unsafe run_id: {run_id!r}")
    return run_id  # type: ignore[return-value]


def sanitize_container_token(s: str) -> str:
    s = _CONTAINER_RE.sub("-", s).strip("-")
    return s[:64] or "x"


def make_container_name(run_id: str, pair_id: str) -> str:
    # Fresh UUID per invocation so cleanup targets exactly the owned container
    # and concurrent grades never share a name. No mutable tag is embedded.
    base = f"arena-{sanitize_container_token(run_id)}-{sanitize_container_token(pair_id.replace('::', '-'))}"
    return f"{base[:120]}-{uuid.uuid4().hex[:12]}"


def is_hex64(s: object) -> bool:
    return isinstance(s, str) and bool(_HEX64_RE.match(s))


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def prompt_filename_for_pair(pair_id: str) -> str:
    """Collision-resistant prompt filename derived from the complete pair ID.

    Sanitized base (<=48 chars) plus 16 hex chars of sha256(pair_id), so long
    identifiers or sanitized-punctuation variants never silently collide.
    """
    if not isinstance(pair_id, str) or not pair_id:
        raise ValueError("unsafe_pair_id:empty")
    if len(pair_id) > 200 or "\x00" in pair_id or "/" in pair_id or "\\" in pair_id:
        raise ValueError(f"unsafe_pair_id:{pair_id[:60]!r}")
    base = _CONTAINER_RE.sub("-", pair_id.replace("::", "__")).strip("-")[:48] or "x"
    digest = sha256_text(pair_id)[:16]
    return f"{base}-{digest}.md"


def make_nonce_marker() -> str:
    """Fresh unpredictable per-grade marker; printed ONLY after asserts pass."""
    return f"{SUCCESS_MARKER}_{secrets.token_hex(16)}"


def check_nonce_marker_line(stdout: object, returncode: object, marker: str) -> bool:
    """Require the exact nonce line plus exit 0; static ARENA_PASS alone fails."""
    if returncode != 0 or not isinstance(stdout, str) or not marker:
        return False
    return any(ln.strip() == marker for ln in stdout.splitlines())


def is_stdlib_shadow_name(name: object) -> bool:
    return isinstance(name, str) and name in STDLIB_SHADOW_NAMES


def canonical_prompt(text: str) -> str:
    """Canonical comparison form.

    Only three normalizations are accepted as `normalized` (never byte-exact):
      1. leading UTF-8 BOM stripped,
      2. CRLF/CR normalized to LF,
      3. exactly one terminal newline made optional.
    Everything else (indentation, truncation, interior whitespace) is a mismatch.
    """
    if not isinstance(text, str):
        raise TypeError("prompt must be str")
    s = text
    if s.startswith("\ufeff"):
        s = s[1:]
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    if s.endswith("\n") and not s.endswith("\n\n"):
        s = s[:-1]
    elif s.endswith("\n"):
        # Collapse exactly one trailing newline; "a\n\n" stays distinct from "a".
        s = s[:-1]
    return s


def make_transport_receipt(expected_prompt: object, observed_prompt: object,
                           requested_model: object, observed_model: object,
                           fallback_observed: object) -> dict:
    """Build a transport receipt comparing complete prompts and exact models.

    Passed requires ALL of:
      - both prompts are str and match byte-exact OR normalized-canonical,
      - requested_model and observed_model are non-empty str and exactly equal,
      - fallback_observed is explicitly False (bool).
    Missing, mismatched, or wrongly typed evidence cannot pass.
    Raw SHA256 values are recorded separately from the canonical comparison.
    """
    rec: dict = {"schema": "veritas.arena_transport_receipt.v1"}
    if isinstance(expected_prompt, str):
        rec["expected_sha256"] = sha256_text(expected_prompt)
        rec["expected_canonical_sha256"] = sha256_text(canonical_prompt(expected_prompt))
    else:
        rec["expected_sha256"] = None
    if isinstance(observed_prompt, str):
        rec["observed_sha256"] = sha256_text(observed_prompt)
        rec["observed_canonical_sha256"] = sha256_text(canonical_prompt(observed_prompt))
    else:
        rec["observed_sha256"] = None
    rec["requested_model"] = requested_model
    rec["observed_model"] = observed_model
    rec["fallback_observed"] = fallback_observed

    if not isinstance(expected_prompt, str) or not isinstance(observed_prompt, str):
        rec.update(passed=False, reason="prompt_missing_or_not_string",
                   byte_exact=False, normalized_match=False, model_exact=False)
        return rec
    byte_exact = expected_prompt == observed_prompt
    try:
        normalized_match = canonical_prompt(expected_prompt) == canonical_prompt(observed_prompt)
    except Exception:
        normalized_match = False
    model_exact = (isinstance(requested_model, str) and isinstance(observed_model, str)
                   and len(requested_model) > 0 and requested_model == observed_model)
    rec["byte_exact"] = bool(byte_exact)
    rec["normalized_match"] = bool(normalized_match)
    rec["model_exact"] = bool(model_exact)

    if fallback_observed is not False:
        # Must be exactly boolean False; True/None/"false"/0 all fail.
        rec.update(passed=False,
                   reason="fallback_not_false" if isinstance(fallback_observed, bool) else "fallback_missing_or_not_bool")
        return rec
    if not model_exact:
        rec.update(passed=False, reason="model_mismatch")
        return rec
    if byte_exact:
        rec.update(passed=True, reason="byte_exact")
        return rec
    if normalized_match:
        rec.update(passed=True, reason="normalized")
        return rec
    rec.update(passed=False, reason="prompt_mismatch")
    return rec


def verify_transport_receipt(rec: object) -> tuple[bool, str]:
    """Re-validate a receipt dict without trusting caller-supplied flags.

    Requires: valid schema, 64-lowercase-hex raw/canonical hashes when present,
    matching typed models, explicit fallback False, and comparison bits
    consistent with the stored hashes. Never honors a bare passed=True.
    Verifies evidence consistency, not authenticity.
    """
    if not isinstance(rec, dict):
        return False, "receipt_not_object"
    if rec.get("schema") != "veritas.arena_transport_receipt.v1":
        return False, "receipt_bad_schema"
    for f in ("expected_sha256", "observed_sha256", "requested_model",
              "observed_model", "fallback_observed",
              "byte_exact", "normalized_match"):
        if f not in rec:
            return False, f"receipt_missing:{f}"
    for hf in ("expected_sha256", "observed_sha256",
               "expected_canonical_sha256", "observed_canonical_sha256"):
        v = rec.get(hf)
        if v is not None and not is_hex64(v):
            return False, f"receipt_bad_hash:{hf}"
    fb = rec.get("fallback_observed")
    if fb is not False:
        return False, "fallback_missing_or_not_bool" if not isinstance(fb, bool) else "fallback_not_false"
    rm, om = rec.get("requested_model"), rec.get("observed_model")
    if not (isinstance(rm, str) and isinstance(om, str) and rm and rm == om):
        return False, "model_mismatch"
    be, nm = rec.get("byte_exact"), rec.get("normalized_match")
    if not isinstance(be, bool) or not isinstance(nm, bool):
        return False, "receipt_bad_comparison_bits"
    ex, ob = rec.get("expected_sha256"), rec.get("observed_sha256")
    ecx, ocx = rec.get("expected_canonical_sha256"), rec.get("observed_canonical_sha256")
    if be is True:
        # byte-exact claims require matching raw hashes when both are present.
        if isinstance(ex, str) and isinstance(ob, str) and ex != ob:
            return False, "prompt_mismatch"
        return True, str(rec.get("reason") or "byte_exact")
    if nm is True:
        if isinstance(ecx, str) and isinstance(ocx, str) and ecx != ocx:
            return False, "prompt_mismatch"
        return True, "normalized"
    return False, str(rec.get("reason") or "prompt_mismatch")


def _reject_constant(v: str):
    raise ValueError(f"non_finite_json:{v}")


def _no_dupes(pairs: list[tuple[str, object]]) -> dict:
    obj: dict = {}
    for k, v in pairs:
        if k in obj:
            raise ValueError(f"duplicate_key:{k}")
        obj[k] = v
    return obj


def _has_nonfinite(v: object) -> bool:
    if isinstance(v, float):
        return not math.isfinite(v)
    if isinstance(v, list):
        return any(_has_nonfinite(x) for x in v)
    if isinstance(v, dict):
        return any(_has_nonfinite(x) for x in v.values())
    return False


def parse_strict_json_object(text: object) -> tuple[dict | None, str | None]:
    """Strict JSON-object parse. Returns (obj, None) or (None, error_reason).

    Rejects: non-string input, fences/prose (no brace extraction), NaN/Infinity
    and overflow-nonfinite (e.g. 1e999 -> inf, recursively), duplicate keys,
    non-object top level, empty input. Transport tolerance is ASCII-only:
    UTF-8 BOM, CRLF -> LF, surrounding ASCII whitespace. A valid JSON string
    value containing backticks is accepted; wrapping prose/fences are rejected.
    Lone CR is NOT normalized (left for the JSON parser to accept/reject).
    """
    if not isinstance(text, str):
        return None, "json_not_string"
    s = text
    if s.startswith("\ufeff"):
        s = s[1:]
    # Declared transport only: CRLF -> LF. Lone CR is left untouched.
    s = s.replace("\r\n", "\n")
    # ASCII-only surrounding whitespace (never strip arbitrary Unicode space).
    stripped = s.strip(" \t\n\r")
    if not stripped:
        return None, "json_empty"
    if not (stripped.startswith("{") and stripped.endswith("}")):
        if "```" in text:
            return None, "json_fenced"
        return None, "json_not_exact_object"
    try:
        obj = json.loads(stripped, object_pairs_hook=_no_dupes,
                         parse_constant=_reject_constant, parse_float=float,
                         parse_int=int)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("duplicate_key:"):
            return None, msg
        if msg.startswith("non_finite_json:"):
            return None, msg
        if "```" in text:
            return None, "json_fenced"
        return None, f"json_parse_error:{msg[:80]}"
    if not isinstance(obj, dict):
        return None, "json_not_object"
    if _has_nonfinite(obj):
        return None, "non_finite_json:overflow"
    return obj, None


def strict_value_equal(a: object, b: object) -> bool:
    """Type-strict equality, recursive for nested dict/list.

    bool never equals int/float (True != 1). int/float cross-compare by value
    (1 == 1.0 preserved). Nested structures compare recursively with the same
    bool-vs-number rule (so {"f": True} != {"f": 1}).
    """
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is bool and type(b) is bool and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        # Nonfinite values are rejected at parse time; be conservative here.
        if isinstance(a, float) and not math.isfinite(a):
            return False
        if isinstance(b, float) and not math.isfinite(b):
            return False
        return a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(strict_value_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(strict_value_equal(a[k], b[k]) for k in a)
    if type(a) is not type(b):
        return False
    return a == b  # type: ignore[comparison-overlap]


def is_safe_relname(name: object) -> bool:
    return (isinstance(name, str) and bool(name) and "/" not in name
            and "\\" not in name and name not in (".", "..")
            and "\x00" not in name and len(name) <= 128)


def ensure_within(root: Path, candidate: Path) -> Path:
    """Resolve candidate and require it to stay within root (symlink-safe)."""
    root_r = root.resolve()
    try:
        cand_r = (root_r / str(candidate) if not Path(candidate).is_absolute()
                  else Path(candidate)).resolve()
    except Exception:
        raise ValueError(f"unsafe_path:{candidate}")
    try:
        cand_r.relative_to(root_r)
    except ValueError:
        raise ValueError(f"path_escape:{candidate}")
    return cand_r


def write_prompt_files(prompt_dir: Path, pairs: list[dict]) -> list[str]:
    """Write one UTF-8 prompt file per pair. Returns relative filenames.

    Collision-resistant names from the complete pair ID (sanitized base +
    16-hex digest). Refuses existing prompt directories/files and duplicate
    derived names; validates pair IDs before writing.
    """
    if prompt_dir.exists() and any(prompt_dir.iterdir()):
        raise ValueError(f"prompt_dir_exists:{prompt_dir}")
    prompt_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    names = []
    for p in pairs:
        pid = p.get("pair_id", "")
        fname = prompt_filename_for_pair(str(pid))
        if fname in seen:
            raise ValueError(f"prompt_name_collision:{fname}")
        seen.add(fname)
        target = prompt_dir / fname
        if target.exists():
            raise ValueError(f"prompt_file_exists:{fname}")
        target.write_text(str(p.get("prompt", "")), encoding="utf-8")
        names.append(fname)
    return names


# ---------------------------------------------------------------------------
# Fail-closed Docker runner (local image ID only, explicit opt-in; --pull never).
# ---------------------------------------------------------------------------

def _run_meta_capped(cmd: list[str], timeout_s: int) -> tuple[int | None, str, str]:
    """Bounded host control-command capture (inspect/rm). Never unbounded."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return None, "", "docker binary not found"
    except Exception:
        return None, "", "docker_meta_spawn_failed"
    timed_out, over_cap, out_b, err_b = _stream_capped(proc, timeout_s, HOST_META_CAP_BYTES)
    if timed_out:
        return None, "", "docker_meta_timeout"
    if over_cap:
        return None, "", "docker_meta_output_limit_exceeded"
    try:
        rc = proc.poll()
    except Exception:
        return None, "", "docker_meta_poll_failed"
    if rc is None:
        return None, "", "docker_meta_no_returncode"
    try:
        out = out_b.decode("utf-8", "replace")
    except Exception:
        out = ""
    try:
        err = err_b.decode("utf-8", "replace")
    except Exception:
        err = ""
    return rc, out, err


def get_local_image_id(image: str = DOCKER_IMAGE) -> tuple[str | None, str]:
    """Resolve the pinned tag to its local sha256 image ID (no pull/network).

    Runs: docker image inspect --format {{.Id}} <tag>, validates sha256:...
    Returns (image_id, error). Callers invoke the exact ID, never the tag.
    """
    rc, out, err = _run_meta_capped(
        [DOCKER_BIN, "image", "inspect", "--format", "{{.Id}}", image], 15)
    if rc is None:
        return None, "missing_docker"
    if rc != 0:
        return None, "missing_image"
    cand = out.strip().splitlines()
    img_id = cand[0].strip() if cand else ""
    if not _IMAGE_ID_RE.match(img_id):
        return None, "missing_image"
    return img_id, ""


def docker_run_args(container_name: str, grade_dir: Path, inner_cmd: list[str],
                    image_id: str | None = None) -> list[str]:
    if not isinstance(image_id, str) or not _IMAGE_ID_RE.match(image_id):
        raise ValueError("missing_image_id: docker_run_args requires inspected sha256 image ID")
    argv = [
        DOCKER_BIN, "run", "--rm", "--pull", "never",
        "--name", container_name,
        "--user", "65534:65534",
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--memory", "512m",
        "--memory-swap", "512m",
        "--cpus", "1",
        "--pids-limit", "64",
        "--tmpfs", "/tmp:rw,size=64m,noexec",
        "-v", f"{grade_dir}:/workspace:ro",
        "-w", "/workspace",
        image_id,
        *inner_cmd,
    ]
    assert argv[argv.index("--pull") + 1] == "never", "docker --pull must be never"
    return argv


def _stream_capped(proc, timeout_s: int, cap: int = OUTPUT_CAP_BYTES
                   ) -> tuple[bool, bool, bytes, bytes]:
    """Stream proc stdout/stderr with a finite combined cap.

    Drains BOTH streams through EOF after fast process exit, then evaluates
    the cap on the final drained bytes (never marks success before the final
    cap assessment). Returns (timed_out, over_cap, out, err). Never buffers
    unbounded: readers stop at cap+one-chunk; the process is killed on cap
    breach or deadline expiry.
    """
    out = bytearray()
    err = bytearray()
    lock = threading.Lock()
    over = threading.Event()

    def _read(stream, buf: bytearray):
        try:
            while True:
                chunk = stream.read(_CHUNK)
                if not chunk:
                    break
                with lock:
                    # Keep one chunk past cap to detect breach, then stop.
                    room = (cap + _CHUNK) - (len(out) + len(err))
                    if room <= 0:
                        over.set()
                        break
                    buf += chunk[:room]
                    if len(out) + len(err) > cap:
                        over.set()
                        break
                if over.is_set():
                    break
        except Exception:
            pass

    readers = [threading.Thread(target=_read, args=(proc.stdout, out), daemon=True),
               threading.Thread(target=_read, args=(proc.stderr, err), daemon=True)]
    for t in readers:
        t.start()
    deadline = time.monotonic() + timeout_s
    timed_out = False
    while True:
        try:
            rc = proc.poll()
        except Exception:
            rc = None
        if rc is not None:
            break  # process exited; fall through to EOF drain below
        if over.is_set():
            break
        if time.monotonic() >= deadline:
            timed_out = True
            break
        time.sleep(0.02)
    if timed_out or over.is_set():
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
    # Drain both streams through EOF after exit (bounded join for delayed EOF).
    for t in readers:
        remaining = max(0.0, deadline - time.monotonic())
        t.join(timeout=(remaining if not (timed_out or over.is_set()) else 10))
    final_over = bool(over.is_set() or (len(out) + len(err) > cap))
    if final_over and not timed_out:
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass
    try:
        if proc.stdout:
            proc.stdout.close()
    except Exception:
        pass
    try:
        if proc.stderr:
            proc.stderr.close()
    except Exception:
        pass
    return timed_out, final_over, bytes(out), bytes(err)


def _decode_evidence(b: bytes, limit_chars: int = 4000) -> str:
    return b.decode("utf-8", "replace")[-limit_chars:]


def run_sandboxed_command(grade_dir: Path, inner_cmd: list[str], timeout_s: int,
                          allow_exec: bool, run_id: str, pair_id: str) -> dict:
    """Run inner_cmd inside the pinned local image ID. Fail closed, no host fallback.

    Resolves the mutable tag to its local sha256 ID via
    `docker image inspect --format {{.Id}}` (validated), invokes that exact ID,
    never pulls. Fresh UUID invocation names; ONLY the owned container is ever
    removed, on timeout/output-cap/error. Candidate stdout/stderr are STREAMED
    with a finite 1 MiB combined cap; cap breach kills the process and returns
    a typed non-pass even when rc==0. Host inspect/rm outputs are capped.
    Returns dict with status one of: blocked_exec_disabled, missing_grade_dir,
    bad_command, missing_docker, missing_image, timeout, output_limit_exceeded,
    nonzero, ok. No --pull/install/network is attempted.
    """
    if allow_exec is not True:
        return {"status": "blocked_exec_disabled", "passed": False,
                "reason": "ungraded_exec_disabled", "returncode": None,
                "stdout": "", "stderr": ""}
    if not isinstance(grade_dir, Path) or not grade_dir.is_dir():
        return {"status": "missing_grade_dir", "passed": False,
                "reason": "missing_grade_dir", "returncode": None,
                "stdout": "", "stderr": ""}
    if not inner_cmd or not all(isinstance(c, str) and c for c in inner_cmd):
        return {"status": "bad_command", "passed": False, "reason": "bad_command",
                "returncode": None, "stdout": "", "stderr": ""}
    if not (isinstance(timeout_s, int) and timeout_s > 0):
        timeout_s = 20
    name = make_container_name(run_id, pair_id)
    image_id, img_err = get_local_image_id(DOCKER_IMAGE)
    if image_id is None:
        if img_err == "missing_docker":
            return {"status": "missing_docker", "passed": False, "reason": "missing_docker",
                    "returncode": None, "stdout": "", "stderr": "docker binary not found"}
        return {"status": "missing_image", "passed": False, "reason": "missing_image",
                "returncode": 1, "stdout": "", "stderr": ""}
    try:
        proc = subprocess.Popen(docker_run_args(name, grade_dir, inner_cmd, image_id),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return {"status": "missing_docker", "passed": False, "reason": "missing_docker",
                "returncode": None, "stdout": "", "stderr": ""}
    timed_out, over_cap, out_b, err_b = _stream_capped(proc, timeout_s)
    if over_cap:
        _cleanup_exact_container(name)
        return {"status": "output_limit_exceeded", "passed": False,
                "reason": "output_limit_exceeded",
                "returncode": proc.poll(),
                "stdout": _decode_evidence(out_b), "stderr": _decode_evidence(err_b)}
    if timed_out:
        _cleanup_exact_container(name)
        return {"status": "timeout", "passed": False, "reason": "exec_timeout",
                "returncode": None,
                "stdout": _decode_evidence(out_b), "stderr": _decode_evidence(err_b)}
    stdout = _decode_evidence(out_b)
    stderr = _decode_evidence(err_b, 2000)
    try:
        p_returncode = proc.poll()
    except Exception:
        p_returncode = None
    if p_returncode != 0:
        _cleanup_exact_container(name)
        return {"status": "nonzero", "passed": False,
                "reason": "exec_fail:" + (stderr.strip().splitlines()[-1][:140] if stderr.strip() else f"rc={p_returncode}"),
                "returncode": p_returncode, "stdout": stdout, "stderr": stderr}
    return {"status": "ok", "passed": True, "reason": "",
            "returncode": 0, "stdout": stdout, "stderr": stderr}


def _cleanup_exact_container(name: str) -> None:
    """Remove ONLY the exact named container; never touch unrelated containers."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name or ""):
        return
    try:
        _run_meta_capped([DOCKER_BIN, "rm", "-f", name], 15)
    except Exception:
        pass


def check_success_marker(stdout: object, returncode: object,
                         marker: str = SUCCESS_MARKER) -> bool:
    """Marker counts only with exit 0; a printed marker plus failing exit fails."""
    return returncode == 0 and isinstance(stdout, str) and marker in stdout
