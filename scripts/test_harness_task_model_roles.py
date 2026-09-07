#!/usr/bin/env python3
"""Hermetic witness tests for the bounded task-scoped model-role contract (r6 + role-validator-integration a1).

Lineage: HARNESS-CONVERGENCE-20260905 legacy attempt8/retry7 preserved; slice
role-validator-integration attempt1/retry0 (root cc5db797-83c7-462e-ae26-5ce5af695995).
Muse a1 expiry repair (test-only): deterministic process-local clock scoped onto the
imported production contract module (production validator bytes unchanged), fresh unique
run directory strictly beneath role-test-witness (legacy shutil.rmtree(WITNESS) removed),
and expired_contract strengthened to a matching approval/contract pair at/after expiry
asserting SPECIFIC contract_expired (never generic expiry_mismatch).
Muse r2 bounded repair (test-only, Main findings M1-M4): no PASS depends on the
real wall clock (fixed test dependency only; live-expiry proof belongs to Main);
expired negative revalidates PREVIOUSLY VALID project/packet under the changed
fixed clock at builder/router/standalone-linter with nested contract_expired;
unresolved ancestor symlink/reparse checks with atomic run-dir allocation;
guaranteed clock/anchor cleanup and canonical before-after checks on every path
plus per-run state reset for repeated main() invocation.
Predecessor: scripts/test_harness_task_model_roles.py (frozen r6 sha cb17ad8797b38557305c1b3624e539b0e1f89d26ed8c939ff19ae7d8941f001d).
a1 change ONLY: --applied-root omitted derives the installed workspace root from
this file's location (parent.parent live; ancestor walk for staged proof copies);
explicit --applied-root still overrides. Witness derivation from the applied root,
all 24 cases, v2 approval binding, and canonical before/after invariants unchanged.
Mode: applied-witness ONLY. Imports the ACTUAL live applied router/linter/contract
code bytes from --applied-root/scripts (no reapply, no replacements.json, no
PRE-APPLY baseline hashes), read-only verifies the canonical live owner-approval
hash FIRST, then stages every mutable approval/register/contract fixture under a
hermetic witness root strictly beneath <applied-root>/tmp/harness-convergence-20260905/main/role-test-witness (r5 fix: r4 derived WITNESS from the script location, which resolves to <applied-root>/witness after a live install; r5 derives it from --applied-root and fail-closes on escape).

Hard-kill / concurrent-reader safety (Kimi r3 rejection fix): applied-mode tests
NEVER write/delete/rename canonical live files, even briefly. After importing
live modules, this file overrides in-process module path constants so ALL test
filesystem anchors point at witness copies:
  router: ROOT, TMP, PROJECT_DIR, LANE_REGISTER, COHORT_LEDGER,
          PERSISTENT_SCOPED_EVIDENCE_ROOT
  linter: ROOT, TMP, DEFAULT_REGISTER, DEFAULT_OUT
The actual function/code objects remain live imported bytes; only the anchors
move. Originals are restored after the run. Canonical live approval/register
hashes are asserted unchanged before/after.

Coverage (24 cases = 23 preserved + witness_root_scoped): positive valid Kimi/Opus/Muse task-child routes
through real build_project -> validate_project -> packet_subset -> linter
preflight, plus default behavior; negatives for missing/tampered approval,
wrong root/scope, expiry, malformed/unknown metadata, child-claims-Main,
persistent masquerade, missing/reordered review, absent/wrong actual evidence
and HIGH effort, and unsafe paths. No hook-absent skip: any missing hook is a FAIL.

Convention: self-running script (``python <file> --applied-root .``), exit 0/1, not pytest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
OUT_DIR = HERE.parent.parent  # provenance only; r6 MUST NOT derive WITNESS from this.
# r4 defect: OUT_DIR=HERE.parent.parent resolves to <applied-root>/witness after a
# live install (scripts/ lives at the root), escaping task-scoped output and writing
# 9 files/188602 bytes to workspace/witness (incident evidence preserved at
# tmp/harness-convergence-20260905/main/role-test-witness-misplaced-a1).
# r5 derives the witness root from --applied-root ONLY (resolved in
# setup_applied_witness) and fail-closes on any escape.
TASK_TMP_REL = "tmp/harness-convergence-20260905/main"
WITNESS_DIR_NAME = "role-test-witness"
WITNESS_CONTRACT_SUFFIX = "tmp/harness-convergence-20260905/muse-role-contract-r6/witness"
WITNESS: Path | None = None
WITNESS_SCRIPTS: Path | None = None
WITNESS_CONTRACT_DIR: Path | None = None

APPROVAL_REL = "tmp/harness-convergence-20260905/role-inputs/owner-approval-snapshot-v2.json"
APPROVAL_SHA = "026056bef54e8247066a2acce67725fbd743e22c12c9a1e499197bc9b941cd43"
CONTRACT_REL = "tmp/harness-convergence-20260905/muse-role-contract-r1/scratch/contract.json"
APPLIED_CONTRACT_REL = "tmp/harness-convergence-20260905/muse-role-contract-r3/scratch/contract.json"
WITNESS_CONTRACT_REL = "tmp/harness-convergence-20260905/muse-role-contract-r4/witness/contract.json"
REGISTER_REL = "tmp/concurrent-lane-register.json"
FIXED_NOW = datetime(2026, 9, 5, 22, 12, 0, tzinfo=timezone.utc)
# a1 hermetic clock: FIXED_NOW sits inside the frozen approval window
# (valid_until 2026-09-06T05:12:00Z); LATE_CLOCK sits after it for the
# strengthened expired_contract case. Production validator bytes are NEVER
# touched: only this test's process-local reference to the imported contract
# module's ``datetime`` dependency is scoped and restored.
LATE_CLOCK = datetime(2026, 9, 7, 0, 0, 0, tzinfo=timezone.utc)
_CLOCK_NOW: datetime | None = None
_REAL_CONTRACT_DATETIME: Any = None
_CLOCK_PATCHED = False


class _FixedDateTime(datetime):
    """Test-local datetime subclass routing .now() to the deterministic clock."""

    @classmethod
    def now(cls, tz=None):  # noqa: D102
        if _CLOCK_NOW is None:
            return super().now(tz)
        if tz is None:
            return _CLOCK_NOW.replace(tzinfo=None)
        return _CLOCK_NOW.astimezone(tz)


def _install_fixed_clock(value: datetime) -> bool:
    """Scope the deterministic clock onto the imported contract module. Idempotent."""
    global _CLOCK_NOW, _REAL_CONTRACT_DATETIME, _CLOCK_PATCHED
    if contract is None:
        fail("deterministic clock requires the imported live contract module")
        return False
    if not _CLOCK_PATCHED:
        _REAL_CONTRACT_DATETIME = contract.datetime
        contract.datetime = _FixedDateTime
        _CLOCK_PATCHED = True
    _CLOCK_NOW = value
    return True


def _restore_clock() -> None:
    """Restore the real clock dependency on the imported contract module."""
    global _CLOCK_NOW, _REAL_CONTRACT_DATETIME, _CLOCK_PATCHED
    _CLOCK_NOW = None
    if _CLOCK_PATCHED:
        if contract is not None and _REAL_CONTRACT_DATETIME is not None:
            try:
                contract.datetime = _REAL_CONTRACT_DATETIME
            except Exception as exc:  # noqa: BLE001
                fail(f"clock restore failed: {type(exc).__name__}: {exc}")
                return
        else:
            fail("clock restore incomplete: live module or saved datetime missing while patch flag set")
            return
    _REAL_CONTRACT_DATETIME = None
    _CLOCK_PATCHED = False


def _restore_clock_silent() -> None:
    """Best-effort clock reset for main() entry (repeated invocation). Never records."""
    global _CLOCK_NOW, _REAL_CONTRACT_DATETIME, _CLOCK_PATCHED
    _CLOCK_NOW = None
    if _CLOCK_PATCHED and contract is not None and _REAL_CONTRACT_DATETIME is not None:
        try:
            contract.datetime = _REAL_CONTRACT_DATETIME
        except Exception:
            pass
    _REAL_CONTRACT_DATETIME = None
    _CLOCK_PATCHED = False

FAILURES: list[str] = []
router = None
linter = None
contract = None
APPLIED_ROOT: Path | None = None
LIVE_APPROVAL_BEFORE: str | None = None
LIVE_REGISTER_BEFORE: str | None = None
_SAVED_ANCHORS: list[tuple[Any, str, Any]] = []


def fail(message: str) -> None:
    FAILURES.append(message)


def expect(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _snapshot_anchor(module: Any, name: str, witness_value: Any) -> None:
    if hasattr(module, name):
        _SAVED_ANCHORS.append((module, name, getattr(module, name)))
        setattr(module, name, witness_value)


def _apply_witness_anchors() -> None:
    """Point all test filesystem anchors at the witness root (in-process only)."""
    global _SAVED_ANCHORS
    _SAVED_ANCHORS = []
    assert router is not None and linter is not None
    assert WITNESS is not None and WITNESS_SCRIPTS is not None and WITNESS_CONTRACT_DIR is not None
    w_tmp = WITNESS / "tmp"
    _snapshot_anchor(router, "ROOT", WITNESS)
    _snapshot_anchor(router, "TMP", w_tmp)
    _snapshot_anchor(router, "PROJECT_DIR", w_tmp / "projects")
    _snapshot_anchor(router, "LANE_REGISTER", w_tmp / "concurrent-lane-register.json")
    _snapshot_anchor(router, "COHORT_LEDGER", w_tmp / "efficiency-cohort-ledger.json")
    _snapshot_anchor(router, "PERSISTENT_SCOPED_EVIDENCE_ROOT", w_tmp / "implementation-builder-scoped-worktree")
    _snapshot_anchor(linter, "ROOT", WITNESS)
    _snapshot_anchor(linter, "TMP", w_tmp)
    _snapshot_anchor(linter, "DEFAULT_REGISTER", w_tmp / "concurrent-lane-register.json")
    _snapshot_anchor(linter, "DEFAULT_OUT", w_tmp / "long-work-packet-linter.json")


def _restore_anchors() -> None:
    errors = 0
    for module, name, original in reversed(_SAVED_ANCHORS):
        try:
            setattr(module, name, original)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            fail(f"anchor restore failed for {type(module).__name__}.{name}: {type(exc).__name__}: {exc}")
    _SAVED_ANCHORS.clear()
    if errors:
        fail(f"{errors} anchor(s) failed restoration; run state may be polluted")


def _default_applied_root() -> str:
    """No-arg default: installed workspace root derived from this file's location.

    Live install: <root>/scripts/<file>, so parent.parent IS the applied root.
    Staged proof copy (tmp/.../muse-role-validator-a1/scripts/<file>): walk
    ancestors upward to the first directory holding the applied-tree markers.
    Explicit --applied-root always overrides this. Witness derivation (from the
    applied root) is unchanged (r5 rule); WITNESS is never derived from __file__.
    """
    here = Path(__file__).resolve()
    candidates = [here.parent.parent, *list(here.parents)[2:]]
    for candidate in candidates:
        if ((candidate / "scripts/project_implementation_router.py").is_file()
                and (candidate / APPROVAL_REL).is_file()):
            return str(candidate)
    return str(here.parent.parent)


def _redirect_kind(prefix: Path) -> tuple[bool, str | None]:
    """Classify one UNRESOLVED path prefix: (existed, redirect-kind-or-None).

    Uses os.lstat (never follows links). Detects POSIX symlinks via the mode
    and Windows junctions/symlinks/reparse points via st_file_attributes
    FILE_ATTRIBUTE_REPARSE_POINT (0x400), with Path.is_symlink() as backup.
    A missing prefix reports (False, None) so not-yet-created run children
    are skippable; an lstat failure on an existing prefix is fail-closed.
    """
    try:
        st = os.lstat(prefix)
    except FileNotFoundError:
        return False, None
    except Exception as exc:  # noqa: BLE001
        return True, f"lstat-failed:{type(exc).__name__}"
    if stat.S_ISLNK(st.st_mode):
        return True, "symlink"
    if (getattr(st, "st_file_attributes", 0) or 0) & 0x400:
        return True, "windows-reparse-point"
    try:
        if prefix.is_symlink():
            return True, "symlink"
    except Exception:
        pass
    return True, None


def _check_unresolved_ancestors(candidate: Path, stop: Path, label: str) -> bool:
    """Fail-closed redirect check over UNRESOLVED ancestor components.

    Walks every path prefix of ``candidate`` strictly below ``stop`` without
    resolving anything, so a symlink/junction/reparse identity cannot
    disappear before containment is decided. Existing prefixes must not be
    redirects; missing (not-yet-created) prefixes are skipped.
    """
    try:
        parts = candidate.parts
        base = stop.parts
    except Exception as exc:  # noqa: BLE001
        fail(f"{label}: ancestor walk failed: {type(exc).__name__}: {exc}")
        return False
    if len(parts) <= len(base) or tuple(parts[:len(base)]) != tuple(base):
        fail(f"{label}: path is not beneath the approved stop: {candidate}")
        return False
    for depth in range(len(base) + 1, len(parts) + 1):
        prefix = Path(*parts[:depth])
        existed, kind = _redirect_kind(prefix)
        if kind is not None:
            fail(f"{label}: unresolved ancestor is a {kind}: {prefix}")
            return False
    return True


def setup_applied_witness(root_arg: str) -> bool:
    """Import LIVE applied modules read-only; redirect anchors to witness. No live writes."""
    global router, linter, contract, APPLIED_ROOT, LIVE_APPROVAL_BEFORE, LIVE_REGISTER_BEFORE, WITNESS, WITNESS_SCRIPTS, WITNESS_CONTRACT_DIR
    try:
        candidate = Path(root_arg)
        root = candidate.resolve() if candidate.is_absolute() else (Path.cwd() / candidate).resolve()
        if not root.is_dir():
            fail(f"applied root is not a directory: {root}")
            return False
        for rel in ("scripts/project_implementation_router.py", "scripts/long_work_packet_linter.py",
                    "scripts/task_scoped_model_role_contract.py", APPROVAL_REL):
            if not (root / rel).is_file():
                fail(f"applied root missing required file: {rel}")
                return False
        # Read-only verify of canonical live bytes FIRST (no mutation yet).
        live_approval = (root / APPROVAL_REL).read_bytes()
        if sha256_bytes(live_approval) != APPROVAL_SHA:
            fail("live approval bytes do not match trusted frozen hash")
            return False
        LIVE_APPROVAL_BEFORE = sha256_bytes(live_approval)
        reg_live = root / REGISTER_REL
        LIVE_REGISTER_BEFORE = sha256_bytes(reg_live.read_bytes()) if reg_live.is_file() else "absent"
        sys.path.insert(0, str(root / "scripts"))
        for mod in ("project_implementation_router", "long_work_packet_linter", "task_scoped_model_role_contract"):
            sys.modules.pop(mod, None)
        import project_implementation_router as _router  # noqa: E402
        import long_work_packet_linter as _linter  # noqa: E402
        import task_scoped_model_role_contract as _contract  # noqa: E402
        router, linter, contract = _router, _linter, _contract
        for name in ("build_task_role_fragment", "validate_task_role_fragment"):
            if not hasattr(router, name):
                fail(f"live router hook absent after apply: {name}")
                return False
        if not hasattr(linter, "validate_task_role_in_packet"):
            fail("live linter hook absent after apply: validate_task_role_in_packet")
            return False
        if getattr(contract, "ROOT_OBJECTIVE_ID", None) != "cc5db797-83c7-462e-ae26-5ce5af695995":
            fail("live contract root objective mismatch")
            return False
        APPLIED_ROOT = root
        # r5 witness-root derivation: strictly beneath the approved task tmp.
        # a2-fix (Sol high): guard UNRESOLVED lexical ancestors BEFORE any
        # .resolve(). Resolving task_tmp/witness first erases a Windows
        # junction/reparse identity in an ancestor and defeats containment.
        # Lexical child paths stay beneath root until the guard has examined
        # the original unresolved ancestors; only then resolve and check
        # containment under the applied root before any fixture creation.
        task_tmp_lex = root / TASK_TMP_REL
        witness_lex = task_tmp_lex / WITNESS_DIR_NAME
        if witness_lex.parent != task_tmp_lex or witness_lex.name != WITNESS_DIR_NAME:
            fail(f"witness root escaped task tmp: {witness_lex}")
            return False
        if not _check_unresolved_ancestors(witness_lex, root, "witness base"):
            return False
        try:
            task_tmp = task_tmp_lex.resolve()
            witness = witness_lex.resolve()
            root_resolved = root.resolve()
            forbidden_witness = (root / "witness").resolve()
        except Exception as exc:  # noqa: BLE001
            fail(f"witness resolve failed: {type(exc).__name__}: {exc}")
            return False
        if witness.parent != task_tmp or witness.name != WITNESS_DIR_NAME:
            fail(f"witness root escaped task tmp: {witness}")
            return False
        if witness == forbidden_witness:
            fail(f"witness root must never be <applied-root>/witness: {witness}")
            return False
        if witness == root_resolved or not str(witness).startswith(str(task_tmp)):
            fail(f"witness root outside approved task tmp: {witness}")
            return False
        # a1: the witness directory and every existing file are PRESERVED. The
        # legacy shutil.rmtree(WITNESS) is removed and must never execute.
        # Mutable fixtures stage into a fresh unique run child strictly beneath
        # the witness base; existing runs are never reused or deleted.
        try:
            witness.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # noqa: BLE001
            fail(f"witness base could not be prepared (preserved, not deleted): {witness}: {type(exc).__name__}: {exc}")
            return False
        if not _check_unresolved_ancestors(witness, root, "witness base (post-create)"):
            return False
        task_tmp_resolved = task_tmp.resolve()
        witness_resolved = witness.resolve()
        if witness_resolved.parent != task_tmp_resolved or witness_resolved.name != WITNESS_DIR_NAME:
            fail(f"resolved witness base escaped task tmp: {witness_resolved}")
            return False
        # r2/M1: deterministic fixed-clock stamp only (no wall-clock
        # dependency, not even for uniqueness); pid+nonce disambiguate and
        # os.mkdir(exist_ok=False) is the atomic allocator (M3: never
        # check-then-reuse, never parents/exist_ok on the run dir itself).
        stamp = FIXED_NOW.strftime("%Y%m%dT%H%M%SZ")
        fresh: Path | None = None
        for nonce in range(1000):
            suffix = f"run-{stamp}-pid{os.getpid()}-{nonce:03d}"
            candidate = witness / suffix
            if not _check_unresolved_ancestors(candidate, root, f"run candidate {suffix}"):
                return False
            try:
                candidate.mkdir(parents=False, exist_ok=False)
            except FileExistsError:
                continue
            except Exception as exc:  # noqa: BLE001
                fail(f"run directory atomic create failed for {suffix}: {type(exc).__name__}: {exc}")
                return False
            try:
                resolved = candidate.resolve()
            except Exception as exc:  # noqa: BLE001
                fail(f"run directory resolve failed for {suffix}: {type(exc).__name__}: {exc}")
                try:
                    candidate.rmdir()
                except Exception:
                    pass
                return False
            if resolved.parent != witness_resolved or resolved == forbidden_witness or resolved == root.resolve():
                fail(f"run directory escaped approved witness scope: {resolved}")
                try:
                    candidate.rmdir()
                except Exception:
                    pass
                return False
            fresh = candidate
            break
        if fresh is None:
            fail("could not allocate a fresh unique run directory beneath the witness root")
            return False
        WITNESS = fresh
        WITNESS_SCRIPTS = WITNESS / "scripts"
        WITNESS_CONTRACT_DIR = WITNESS / WITNESS_CONTRACT_SUFFIX
        # a1: scope the deterministic fixed clock onto the imported production
        # contract module (process-local only; production validator bytes
        # untouched). Setup failure below restores clock and anchors.
        if not _install_fixed_clock(FIXED_NOW):
            return False

        def _fail_setup(message: str) -> bool:
            # r2/M4: any setup failure AFTER the clock/anchor patch restores
            # both (recording restore failures) instead of returning early.
            fail(message)
            try:
                _restore_anchors()
            except Exception as exc:  # noqa: BLE001
                fail(f"setup cleanup anchor restore raised {type(exc).__name__}: {exc}")
            try:
                _restore_clock()
            except Exception as exc:  # noqa: BLE001
                fail(f"setup cleanup clock restore raised {type(exc).__name__}: {exc}")
            return False
        # Stage hermetic witness tree strictly inside the fresh run dir.
        # The forbidden <applied-root>/witness path is never created, listed,
        # written, or deleted here; escape fail-closes above.
        assert WITNESS is not None
        (WITNESS / APPROVAL_REL).parent.mkdir(parents=True, exist_ok=True)
        (WITNESS / APPROVAL_REL).write_bytes(live_approval)
        (WITNESS / REGISTER_REL).parent.mkdir(parents=True, exist_ok=True)
        WITNESS_CONTRACT_DIR.mkdir(parents=True, exist_ok=True)
        WITNESS_SCRIPTS.mkdir(parents=True, exist_ok=True)
        # Read-only existence fixtures: exercised code stats closeout proof
        # artifacts relative to module ROOT (now the witness). Stage
        # byte-identical COPIES for existence checks only; imports still
        # resolve to the live tree (live scripts dir precedes sys.path).
        for _rel in ("scripts/project_implementation_router.py",):
            _dest = WITNESS / _rel
            _dest.parent.mkdir(parents=True, exist_ok=True)
            _dest.write_bytes((root / _rel).read_bytes())
        _apply_witness_anchors()
        # Sanity: anchors must no longer reference the canonical tree.
        for label, path in (("router.ROOT", router.ROOT), ("router.LANE_REGISTER", router.LANE_REGISTER),
                            ("linter.ROOT", linter.ROOT)):
            if str(root) in str(path) and str(WITNESS) not in str(path):
                return _fail_setup(f"anchor still points at canonical tree: {label}={path}")
        # Sanity: the deterministic clock must reach the imported production
        # contract code (validator bytes untouched; process-local only).
        try:
            tick = contract.datetime.now(timezone.utc)
        except Exception:
            tick = None
        if tick != FIXED_NOW:
            return _fail_setup(f"deterministic clock did not reach imported contract code: {tick}")
        return True
    except Exception as exc:  # noqa: BLE001
        try:
            _restore_anchors()
        except Exception:
            pass
        try:
            _restore_clock()
        except Exception:
            pass
        fail(f"setup_applied_witness raised {type(exc).__name__}: {exc}")
        return False


def _approval_file() -> Path:
    """Witness approval fixture ONLY (never the canonical live file)."""
    return WITNESS / APPROVAL_REL


def _lane_register_file() -> Path:
    """Witness lane-register ONLY (never the canonical live file)."""
    return WITNESS / REGISTER_REL


def write_contract(payload: dict, name: str = "contract.json") -> str:
    dest = WITNESS_CONTRACT_DIR / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(dest.relative_to(WITNESS)).replace("\\", "/")


def base_args(**overrides):
    import argparse
    args = argparse.Namespace(
        title="Harness role slice probe", description="Runtime ops review probe",
        slug="role-slice-probe", project_id="role-slice-probe-001",
        workflow_id="HARNESS-CONVERGENCE-20260905", workstream="role-probe",
        task_shape="routing", authority_class="review_only", write_scope="no_write",
        helper_fit="main_only", validation_budget="micro", write_mode="read_only",
        leased_path=[], frontdoor_proof=["skills/disciplined-implementation/SKILL.md"],
        read_first=["skills/disciplined-implementation/SKILL.md"],
        validation_command=["python scripts\\project_implementation_router.py --example --write --validate"],
        stop_line=[], route_owner="disciplined-implementation", model=None,
        expected_role=None, trust_label=None, smoke_proof=None, resource_reason=None,
        expected_thinking=None, expected_execution_backend=None, context_budget="narrow",
        route_reason="bounded harness-convergence slice probe",
        model_free_command=["python scripts\\test_project_implementation_router.py"],
        model_free_proof=["scripts/test_project_implementation_router.py"],
        allow_codex_native=False, native_dispatch_proof=None, main_only_reason="final-integration probe",
        main_sol_use_case=None, main_sol_reason=None, main_terra_approval_ref=None,
        persistent_transport_ready=False, persistent_transport_proof=None,
        persistent_lane_mode="patch_draft", measurement_cohort_binding=None,
        include_efficiency_observation=False, actual_model_path=None, actual_thinking=None,
        actual_execution_backend=None, actual_route_verified=False, status="planned",
        proof_artifact=[], helper_outputs_reviewed=False, main_verified=False,
        main_accepted=False, packet_stage="preflight", out=None, example=False,
        write=False, validate=True, task_role_contract=None, task_child_role=None,
        task_actual_model=None, task_actual_thinking=None, task_actual_backend=None,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def contract_codes(result: dict) -> set[str]:
    codes = set()
    for item in result.get("errors", []):
        codes.add(item.get("code", "?"))
    return codes


def full_preflight(args) -> tuple[dict, dict, dict]:
    project = router.build_project(args)
    validation = router.validate_project(project, stage="preflight")
    packet = router.packet_subset(project)
    register: dict = {}
    linted = linter.validate_packet(packet, stage="preflight", register=register)
    return project, validation, linted


# ---------------- positives (real full path) ----------------

def test_default_unchanged() -> None:
    project, validation, linted = full_preflight(base_args())
    expect("task_role_contract" not in project.get("model_route", {}), "default model_route must not carry task fragment")
    expect(validation["status"] in {"ok", "warning"}, f"default preflight must pass: {validation['status']}")
    expect(linted["status"] in {"ok", "warning"}, f"default linter must pass: {linted['status']}")


def test_valid_child(role: str, model: str, thinking: str) -> None:
    ref = write_contract(contract.expected_contract())
    project, validation, linted = full_preflight(base_args(task_role_contract=ref, task_child_role=role))
    fragment = project.get("model_route", {}).get("task_role_contract", {})
    expect(fragment.get("status") == "ok", f"{role}: fragment must be ok: {fragment.get('errors')}")
    typed = fragment.get("task_child_route", {})
    expect(typed.get("model") == model, f"{role}: typed model must be {model}")
    expect(typed.get("execution_backend") == "main_session_tool_loop", f"{role}: typed backend must be task tool loop")
    expect(validation["status"] in {"ok", "warning"}, f"{role}: preflight must pass: {validation['status']} {validation.get('errors')}")
    expect(linted["status"] in {"ok", "warning"}, f"{role}: linter must pass: {linted['status']} {linted.get('validation', {}).get('errors')}")


def test_closeout_positive() -> None:
    ref = write_contract(contract.expected_contract())
    args = base_args(
        task_role_contract=ref, task_child_role="coder",
        task_actual_model="meta/muse-spark-1.3-contributor", task_actual_thinking="medium",
        task_actual_backend="main_session_tool_loop",
        helper_outputs_reviewed=True, main_verified=True, proof_artifact=["scripts/project_implementation_router.py"],
    )
    project = router.build_project(args)
    expected = {
        "model_path": project["model_route"].get("expected_model_path"),
        "thinking": project["model_route"].get("expected_thinking"),
        "execution_backend": project["model_route"].get("execution_backend"),
    }
    args.actual_model_path = expected["model_path"]
    args.actual_thinking = expected["thinking"]
    args.actual_execution_backend = expected["execution_backend"]
    args.actual_route_verified = True
    project = router.build_project(args)
    lane_id = f"{str(project['workflow_id']).upper()}::{str(project['workstream_id']).lower()}"
    register = {"lanes": [{"lane_id": lane_id, "status": "complete", "allowed_writes": []}]}
    reg_file = _lane_register_file()
    assert reg_file == WITNESS / REGISTER_REL, "witness register must be the hermetic copy"
    assert reg_file != APPLIED_ROOT / REGISTER_REL, "witness register must never be the canonical live file"
    reg_file.parent.mkdir(parents=True, exist_ok=True)
    reg_file.write_text(json.dumps(register), encoding="utf-8")
    try:
        validation = router.validate_project(project, stage="closeout")
        expect(validation["status"] in {"ok", "warning"}, f"closeout positive must pass: {validation['status']} {validation.get('errors')}")
    finally:
        try:
            reg_file.unlink()
        except FileNotFoundError:
            pass


def test_witness_root_scoped() -> None:
    """a1 guard: fresh unique run dir strictly beneath the preserved witness base."""
    assert APPLIED_ROOT is not None and WITNESS is not None
    task_tmp = (APPLIED_ROOT / TASK_TMP_REL).resolve()
    base = (task_tmp / WITNESS_DIR_NAME).resolve()
    witness = WITNESS.resolve()
    expect(witness.parent == base and witness.name.startswith("run-"),
           f"witness must be a fresh run child of <root>/{TASK_TMP_REL}/{WITNESS_DIR_NAME}: {witness}")
    expect(not WITNESS.is_symlink(), "witness run dir must not be a symlink/reparse point")
    expect(witness != (APPLIED_ROOT / "witness").resolve(), "witness must not be <applied-root>/witness")
    expect(witness != APPLIED_ROOT.resolve(), "witness must not be the applied root itself")
    expect(str(witness).startswith(str(task_tmp)), f"witness must stay inside task tmp: {witness}")
    for label, path in (("WITNESS_SCRIPTS", WITNESS_SCRIPTS), ("WITNESS_CONTRACT_DIR", WITNESS_CONTRACT_DIR)):
        expect(path is not None and str(Path(str(path)).resolve()).startswith(str(witness)),
               f"{label} must stay inside the witness root: {path}")
    expect(WITNESS_CONTRACT_DIR == WITNESS / WITNESS_CONTRACT_SUFFIX, "contract dir must derive from the witness root")
    # Hermetic-clock proof (fixed test dependency only): imported production
    # code sees FIXED_NOW. PASS never depends on the real wall clock; the
    # separate live-expiry proof belongs to Main, not this suite.
    expect(contract.datetime.now(timezone.utc) == FIXED_NOW, "imported contract code must see the fixed test clock")
    expect(_CLOCK_PATCHED and _CLOCK_NOW == FIXED_NOW, "deterministic clock must be installed at FIXED_NOW")


# ---------------- negatives (real full path unless noted) ----------------

def test_missing_contract_file() -> None:
    _, validation, _ = full_preflight(base_args(
        task_role_contract="tmp/harness-convergence-20260905/muse-role-contract-r4/witness/nope.json",
        task_child_role="coder"))
    expect(validation["status"] == "error", "missing contract file must fail preflight")
    expect(any("task_role" in (e.get("code", "")) for e in validation.get("errors", [])), "missing contract must raise task-role finding")


def test_tampered_approval() -> None:
    target = _approval_file()
    assert target == WITNESS / APPROVAL_REL, "must mutate witness approval only"
    assert target != APPLIED_ROOT / APPROVAL_REL, "must never touch canonical live approval"
    held = target.read_bytes()
    bad = bytearray(held)
    bad[-16] ^= 0x01
    target.write_bytes(bytes(bad))
    try:
        ref = write_contract(contract.expected_contract())
        _, validation, _ = full_preflight(base_args(task_role_contract=ref, task_child_role="coder"))
        expect(validation["status"] == "error", "tampered approval must fail preflight")
    finally:
        target.write_bytes(held)


def test_absent_approval() -> None:
    target = _approval_file()
    assert target == WITNESS / APPROVAL_REL, "must mutate witness approval only"
    assert target != APPLIED_ROOT / APPROVAL_REL, "must never touch canonical live approval"
    held = target.read_bytes()
    target.unlink()
    try:
        ref = write_contract(contract.expected_contract())
        _, validation, _ = full_preflight(base_args(task_role_contract=ref, task_child_role="coder"))
        expect(validation["status"] == "error", "absent approval must fail preflight")
    finally:
        target.write_bytes(held)


def _standalone_valid_packet() -> dict:
    ref = write_contract(contract.expected_contract())
    project, validation, _ = full_preflight(base_args(task_role_contract=ref, task_child_role="coder"))
    expect(validation["status"] in {"ok", "warning"}, f"standalone setup preflight must pass: {validation.get('errors')}")
    return router.packet_subset(project)


def test_standalone_linter_valid() -> None:
    packet = _standalone_valid_packet()
    linted = linter.validate_packet(packet, stage="preflight", register={})
    expect(linted["status"] in {"ok", "warning"}, f"standalone valid packet must pass linter: {linted.get('validation', {}).get('errors')}")


def test_standalone_linter_approval_tampered() -> None:
    packet = _standalone_valid_packet()
    target = _approval_file()
    held = target.read_bytes()
    bad = bytearray(held)
    bad[-16] ^= 0x01
    target.write_bytes(bytes(bad))
    try:
        linted = linter.validate_packet(packet, stage="preflight", register={})
        expect(linted["status"] == "error", "standalone tampered approval must fail linter")
        expect(any(e.get("code") == "task_role_approval_unverified" for e in linted.get("validation", {}).get("errors", [])),
               f"tampered standalone must raise task_role_approval_unverified: {linted.get('validation', {}).get('errors')}")
    finally:
        target.write_bytes(held)


def test_standalone_linter_approval_missing() -> None:
    packet = _standalone_valid_packet()
    target = _approval_file()
    held = target.read_bytes()
    target.unlink()
    try:
        linted = linter.validate_packet(packet, stage="preflight", register={})
        expect(linted["status"] == "error", "standalone missing approval must fail linter")
        expect(any(e.get("code") == "task_role_approval_unverified" for e in linted.get("validation", {}).get("errors", [])),
               f"missing standalone must raise task_role_approval_unverified: {linted.get('validation', {}).get('errors')}")
    finally:
        target.write_bytes(held)


def test_out_of_scope_lease() -> None:
    ref = write_contract(contract.expected_contract())
    _, validation, _ = full_preflight(base_args(
        task_role_contract=ref, task_child_role="coder", write_mode="leased",
        leased_path=["skills/some-skill/SKILL.md"]))
    expect(validation["status"] == "error", "out-of-scope lease must fail preflight")


def test_expired_contract() -> None:
    # r2/M2: structural expiry revalidation of PREVIOUSLY VALID artifacts
    # under a changed fixed clock. Phase A builds a valid project+packet
    # under FIXED_NOW; phase B moves ONLY the clock to LATE_CLOCK and
    # revalidates the prior-valid artifacts through the builder, the router
    # revalidation path, and the standalone linter. Every layer must report
    # the SPECIFIC nested contract_expired -- never a reused build-invalid
    # fragment and never a generic expiry_mismatch/expiry_widened. The
    # witness approval fixture must be byte-identical before and after.
    # No wall-clock dependency anywhere: boundary checks use explicit now=.
    approval_target = _approval_file()
    approval_before = approval_target.read_bytes()
    ref_valid = write_contract(contract.expected_contract(), "expiry_prior_valid.json")
    prior_project = router.build_project(base_args(task_role_contract=ref_valid, task_child_role="coder"))
    prior_fragment = prior_project.get("model_route", {}).get("task_role_contract", {})
    expect(prior_fragment.get("status") == "ok", f"phase-A build under fixed clock must be valid: {prior_fragment.get('errors')}")
    prior_packet = router.packet_subset(prior_project)
    _install_fixed_clock(LATE_CLOCK)
    try:
        # Builder layer: a fresh build under the late clock fails closed with
        # the specific time-based code.
        ref_late = write_contract(contract.expected_contract(), "expiry_late_build.json")
        late_project = router.build_project(base_args(task_role_contract=ref_late, task_child_role="coder"))
        late_fragment = late_project.get("model_route", {}).get("task_role_contract", {})
        late_codes = contract_codes({"errors": late_fragment.get("errors", [])})
        expect(late_fragment.get("status") == "error", "late-clock build must yield an invalid fragment")
        expect("contract_expired" in late_codes, f"late build must report SPECIFIC contract_expired: {sorted(late_codes)}")
        expect(not ({"expiry_mismatch", "expiry_widened"} & late_codes), f"matching pair must not fail generically: {sorted(late_codes)}")
        # Router layer: revalidate the PREVIOUSLY VALID project (fresh
        # structural revalidation, not the late-build fragment).
        revalidation = router.validate_project(prior_project, stage="preflight")
        expect(revalidation["status"] == "error", "router must fail the prior-valid project under the late clock")
        nested: set[str] = set()
        for item in revalidation.get("errors", []):
            for inner in (item.get("errors") or []):
                if isinstance(inner, dict):
                    nested.add(inner.get("code", "?"))
            for inner in ((item.get("detail") or {}).get("errors") or []):
                if isinstance(inner, dict):
                    nested.add(inner.get("code", "?"))
        expect("contract_expired" in nested, f"router revalidation must surface nested contract_expired: {sorted(nested)}")
        expect(not ({"expiry_mismatch", "expiry_widened"} & nested), f"router revalidation must not fail generically: {sorted(nested)}")
        # Standalone linter layer: revalidate the PREVIOUSLY VALID packet.
        linted = linter.validate_packet(prior_packet, stage="preflight", register={})
        expect(linted["status"] == "error", "linter must fail the prior-valid packet under the late clock")
        lint_nested: set[str] = set()
        for item in linted.get("validation", {}).get("errors", []):
            for inner in (item.get("errors") or []):
                if isinstance(inner, dict):
                    lint_nested.add(inner.get("code", "?"))
            for inner in ((item.get("detail") or {}).get("errors") or []):
                if isinstance(inner, dict):
                    lint_nested.add(inner.get("code", "?"))
        expect("contract_expired" in lint_nested, f"linter must surface nested contract_expired: {sorted(lint_nested)}")
        expect(not ({"expiry_mismatch", "expiry_widened"} & lint_nested), f"linter must not fail generically: {sorted(lint_nested)}")
    finally:
        _install_fixed_clock(FIXED_NOW)
    expect(contract.datetime.now(timezone.utc) == FIXED_NOW, "deterministic clock must be back at FIXED_NOW after expiry phases")
    expect(approval_target.read_bytes() == approval_before, "witness approval fixture must be untouched by expiry revalidation")
    # Restoration proof: the same prior-valid artifacts pass again.
    revalidation_ok = router.validate_project(prior_project, stage="preflight")
    expect(revalidation_ok["status"] in {"ok", "warning"}, f"restored clock must pass the prior-valid project: {revalidation_ok.get('errors')}")
    linted_ok = linter.validate_packet(prior_packet, stage="preflight", register={})
    expect(linted_ok["status"] in {"ok", "warning"}, f"restored clock must pass the prior-valid packet: {linted_ok.get('validation', {}).get('errors')}")
    # Boundary proof (unit-level via explicit now=, no fixtures, no clock
    # patch, no wall clock): the exact expiry instant is expired (until <=
    # now fails closed); one second before it is valid.
    until = contract.parse_until(contract.VALID_UNTIL_UTC)
    assert until is not None
    at = contract.validate_task_role_contract(contract.expected_contract(), now=until)
    expect("contract_expired" in contract_codes(at), "exact expiry instant must be expired (fail-closed boundary)")
    just_before = contract.validate_task_role_contract(contract.expected_contract(), now=until - timedelta(seconds=1))
    expect(just_before["status"] == "ok", f"one second before expiry must validate: {just_before.get('errors')}")


def test_malformed_and_unknown() -> None:
    payload = contract.expected_contract()
    payload["valid_until_utc"] = "soon"
    ref = write_contract(payload, "malformed.json")
    _, validation, _ = full_preflight(base_args(task_role_contract=ref, task_child_role="coder"))
    expect(validation["status"] == "error", "malformed expiry must fail preflight")
    payload = contract.expected_contract()
    payload["grant_admin"] = True
    payload["role_map"] = dict(payload["role_map"])
    payload["role_map"]["super_admin"] = {"requested_model": "x"}
    ref = write_contract(payload, "unknown.json")
    _, validation, _ = full_preflight(base_args(task_role_contract=ref, task_child_role="coder"))
    expect(validation["status"] == "error", "unknown field/role must fail preflight")


def test_wrong_root() -> None:
    payload = contract.expected_contract()
    payload["root_objective_id"] = "00000000-0000-0000-0000-000000000000"
    ref = write_contract(payload, "badroot.json")
    _, validation, _ = full_preflight(base_args(task_role_contract=ref, task_child_role="coder"))
    expect(validation["status"] == "error", "wrong root must fail preflight")


def test_child_claims_main() -> None:
    ref = write_contract(contract.expected_contract())
    _, validation, _ = full_preflight(base_args(task_role_contract=ref, task_child_role="main_integrator"))
    expect(validation["status"] == "error", "child claiming Main must fail preflight")
    expect(any(e.get("code") == "child_claims_main_acceptance" for e in validation.get("errors", [])),
           "child-claims-Main must raise child_claims_main_acceptance")


def test_persistent_masquerade_linter() -> None:
    ref = write_contract(contract.expected_contract())
    project, validation, _ = full_preflight(base_args(task_role_contract=ref, task_child_role="code_reviewer"))
    expect(validation["status"] in {"ok", "warning"}, "masquerade setup preflight must pass first")
    packet = router.packet_subset(project)
    packet["model_route"] = dict(packet["model_route"])
    packet["model_route"]["execution_backend"] = "persistent_isolated_agent"
    linted = linter.validate_packet(packet, stage="preflight", register={})
    expect(linted["status"] == "error", "persistent masquerade packet must fail linter")
    expect(any(e.get("code") == "persistent_masquerade" for e in linted.get("validation", {}).get("errors", [])),
           "masquerade must raise persistent_masquerade")


def test_review_sequence() -> None:
    payload = contract.expected_contract()
    del payload["review_sequence"]
    ref = write_contract(payload, "noseq.json")
    _, validation, _ = full_preflight(base_args(task_role_contract=ref, task_child_role="coder"))
    expect(validation["status"] == "error", "missing review sequence must fail")
    payload = contract.expected_contract()
    payload["review_sequence"] = ["qa", "code_reviewer", "coder", "main_integration_final_judgment"]
    ref = write_contract(payload, "badseq.json")
    _, validation, _ = full_preflight(base_args(task_role_contract=ref, task_child_role="coder"))
    expect(validation["status"] == "error", "reordered review sequence must fail")


def test_closeout_negatives() -> None:
    ref = write_contract(contract.expected_contract())

    def closeout_with(child: str, model, thinking, backend) -> dict:
        args = base_args(
            task_role_contract=ref, task_child_role=child,
            task_actual_model=model, task_actual_thinking=thinking, task_actual_backend=backend,
            helper_outputs_reviewed=True, main_verified=True,
            proof_artifact=["scripts/project_implementation_router.py"])
        project = router.build_project(args)
        return router.validate_project(project, stage="closeout")

    no_actual = closeout_with("qa", None, None, None)
    expect(no_actual["status"] == "error", "absent task actuals must fail closeout")
    expect(any(e.get("code") == "task_child_actual_missing" for e in no_actual.get("errors", [])), "absent actuals code")
    medium = closeout_with("qa", "anthropic/claude-opus-5", "medium", "main_session_tool_loop")
    expect(medium["status"] == "error", "medium Opus effort must fail closeout")
    expect(any(e.get("code") == "actual_thinking_not_high" for e in medium.get("errors", [])), "medium effort code")
    wrong = closeout_with("code_reviewer", "kimi/k9", "medium", "main_session_tool_loop")
    expect(wrong["status"] == "error", "wrong actual model must fail closeout")
    expect(any(e.get("code") == "actual_model_mismatch" for e in wrong.get("errors", [])), "wrong model code")
    high_ok = closeout_with("qa", "claude-cli/claude-opus-5", "high", "main_session_tool_loop")
    expect(not any(e.get("code") in {"actual_model_mismatch", "actual_thinking_not_high"} for e in high_ok.get("errors", [])),
           f"observed-backend HIGH qa evidence must satisfy role evidence: {high_ok.get('errors')}")
    # r6: observed Ollama Cloud backend is accepted ONLY for code_reviewer; the
    # requested identity for code_reviewer stays direct kimi/k3 (see
    # valid_code_reviewer typed-model assertion). Other roles must fail closed.
    reviewer_observed = closeout_with("code_reviewer", "ollama-cloud/kimi-k3:cloud", "medium", "main_session_tool_loop")
    expect(not any(e.get("code") == "actual_model_mismatch" for e in reviewer_observed.get("errors", [])),
           f"observed ollama-cloud backend must satisfy code_reviewer evidence: {reviewer_observed.get('errors')}")
    coder_misuse = closeout_with("coder", "ollama-cloud/kimi-k3:cloud", "medium", "main_session_tool_loop")
    expect(coder_misuse["status"] == "error", "ollama-cloud reviewer backend must fail for coder")
    expect(any(e.get("code") == "actual_model_mismatch" for e in coder_misuse.get("errors", [])), "coder misuse code")
    qa_misuse = closeout_with("qa", "ollama-cloud/kimi-k3:cloud", "high", "main_session_tool_loop")
    expect(qa_misuse["status"] == "error", "ollama-cloud reviewer backend must fail for qa")
    expect(any(e.get("code") == "actual_model_mismatch" for e in qa_misuse.get("errors", [])), "qa misuse code")


def test_unknown_role_evidence_unit() -> None:
    result = contract.validate_actual_route_evidence(
        {"model": "x", "thinking": "high", "execution_backend": "main_session_tool_loop"}, role="super_admin")
    expect(result["status"] == "error" and "unknown_role" in contract_codes(result), "unknown role evidence must fail")


def test_unsafe_cli_refs() -> None:
    for evil in ("../evil.json", "/tmp/evil.json", "C:/evil.json", "tmp\\evil.json", "..\\evil.json"):
        _, validation, _ = full_preflight(base_args(task_role_contract=evil, task_child_role="coder"))
        expect(validation["status"] == "error", f"unsafe CLI ref must fail: {evil}")


def test_traversal_rewrite_rejected_unit() -> None:
    for evil in ("./../x.json", "a/../../b.json", "a\\b.json", "a:b.json"):
        expect(contract.traversal_syntax_rejected(evil) is not None, f"traversal syntax must be rejected pre-normalization: {evil}")
    expect(contract.traversal_syntax_rejected(CONTRACT_REL) is None, "exact workspace-relative ref must pass raw check")
    expect(contract.traversal_syntax_rejected(APPLIED_CONTRACT_REL) is None, "applied-live workspace-relative ref must pass raw check")
    expect(contract.traversal_syntax_rejected(WITNESS_CONTRACT_REL) is None, "witness workspace-relative ref must pass raw check")
    expect(contract.traversal_syntax_rejected(APPROVAL_REL) is None, "v2 approval workspace-relative ref must pass raw check")
    expect(contract.traversal_syntax_rejected("tmp/harness-convergence-20260905/muse-role-contract-r6/witness/contract.json") is None, "r6 witness workspace-relative ref must pass raw check")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Task-role contract hermetic witness tests (applied-witness only).")
    parser.add_argument("--applied-root", default=None, help="Workspace root holding the APPLIED patched scripts; when omitted, derived from this file's location (live parent.parent; staged copies walk ancestors). Explicit value always overrides.")
    ns, _ = parser.parse_known_args(argv)
    if ns.applied_root is None:
        applied_arg = _default_applied_root()
        print(f"applied-root omitted; derived from test file location: {applied_arg}")
    else:
        applied_arg = ns.applied_root
    # r2/M4: repeated in-process invocation resets per-run state first, so a
    # second main() call never inherits failures, anchors, or clock patches.
    FAILURES.clear()
    _SAVED_ANCHORS.clear()
    _restore_clock_silent()
    setup_ok = setup_applied_witness(applied_arg)
    print(f"mode=applied-witness root={APPLIED_ROOT} witness={WITNESS}")
    print(f"live_approval_before={LIVE_APPROVAL_BEFORE} live_register_before={LIVE_REGISTER_BEFORE}")
    cases = [
        ("witness_root_scoped", test_witness_root_scoped),
        ("default_unchanged", test_default_unchanged),
        ("valid_coder", lambda: test_valid_child("coder", "meta/muse-spark-1.3-contributor", "medium")),
        ("valid_code_reviewer", lambda: test_valid_child("code_reviewer", "kimi/k3", "medium")),
        ("valid_qa", lambda: test_valid_child("qa", "anthropic/claude-opus-5", "high")),
        ("valid_plan_challenger", lambda: test_valid_child("plan_challenger", "anthropic/claude-opus-5", "high")),
        ("closeout_positive", test_closeout_positive),
        ("missing_contract_file", test_missing_contract_file),
        ("tampered_approval", test_tampered_approval),
        ("absent_approval", test_absent_approval),
        ("standalone_linter_valid", test_standalone_linter_valid),
        ("standalone_linter_approval_tampered", test_standalone_linter_approval_tampered),
        ("standalone_linter_approval_missing", test_standalone_linter_approval_missing),
        ("out_of_scope_lease", test_out_of_scope_lease),
        ("expired_contract", test_expired_contract),
        ("malformed_and_unknown", test_malformed_and_unknown),
        ("wrong_root", test_wrong_root),
        ("child_claims_main", test_child_claims_main),
        ("persistent_masquerade_linter", test_persistent_masquerade_linter),
        ("review_sequence", test_review_sequence),
        ("closeout_negatives", test_closeout_negatives),
        ("unknown_role_evidence_unit", test_unknown_role_evidence_unit),
        ("unsafe_cli_refs", test_unsafe_cli_refs),
        ("traversal_rewrite_rejected_unit", test_traversal_rewrite_rejected_unit),
    ]
    passed = 0
    executed = 0
    try:
        if not setup_ok:
            fail("setup_applied_witness reported failure; cases skipped, cleanup/canonical checks still run")
        else:
            for name, case in cases:
                executed += 1
                before = len(FAILURES)
                try:
                    case()
                except Exception as exc:  # noqa: BLE001
                    fail(f"{name} raised {type(exc).__name__}: {exc}")
                if len(FAILURES) == before:
                    passed += 1
                else:
                    print(f"CASE-FAIL {name}")
    finally:
        # r2/M4: cleanup AND canonical before-after checks run for EVERY
        # path (setup false, setup exception, case exception). Restore
        # failures are recorded, never swallowed into a clean pass.
        try:
            _restore_anchors()
        except Exception as exc:  # noqa: BLE001
            fail(f"main cleanup anchor restore raised {type(exc).__name__}: {exc}")
        try:
            _restore_clock()
        except Exception as exc:  # noqa: BLE001
            fail(f"main cleanup clock restore raised {type(exc).__name__}: {exc}")
        # Read-only re-verify canonical live bytes are untouched.
        if APPLIED_ROOT is not None and LIVE_APPROVAL_BEFORE is not None:
            try:
                live_approval_after = sha256_bytes((APPLIED_ROOT / APPROVAL_REL).read_bytes())
                reg_live = APPLIED_ROOT / REGISTER_REL
                live_register_after = sha256_bytes(reg_live.read_bytes()) if reg_live.is_file() else "absent"
                print(f"live_approval_after={live_approval_after} live_register_after={live_register_after}")
                expect(live_approval_after == LIVE_APPROVAL_BEFORE, "canonical live approval hash changed during witness run")
                expect(live_register_after == LIVE_REGISTER_BEFORE, "canonical live register hash changed during witness run")
            except Exception as exc:  # noqa: BLE001
                fail(f"canonical after-check raised {type(exc).__name__}: {exc}")
        else:
            fail("canonical after-check unavailable: applied root unknown (setup failed before root lock)")
    # a2-fix (Sol medium): report the real executed count. Setup failure
    # means zero cases executed: tests=0 passed=0 skipped=0 with the nonzero
    # exit that fail() above already guarantees. The nominal path executes
    # exactly len(cases) with no skips; exception cases count as executed.
    print(f"tests={executed} failures={len(FAILURES)} skipped=0 passed={passed}")
    for item in FAILURES:
        print(f"FAIL {item}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
