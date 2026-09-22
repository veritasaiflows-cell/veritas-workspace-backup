"""Unified arena intake runner: pure orchestration for the four canonical transports.

This module plans, schedules, adjudicates and cards arena work. It NEVER calls a
model itself. It imports no networking, no subprocess and no gateway client; it
emits dispatch plans and consumes result files that some other, explicitly
authorized transport produced. Live dispatch is intentionally not implemented
here (see `refuse_live_dispatch`).

Canonical transports (locked):
  Surface A - arena-six-20260919 via collectors (sessions_spawn collect=true)
  Surface B - pre-overlay new bank via collectors
  Surface C - overlay-r2 via CLI lab pipe (oxalpha-functional-lab + cli-dispatch.py)
  Surface D - integrated missions 1-3 via spawn sessions with visible mounts

Hard rules encoded here:
  * History stays footnoted precedent: adapters never re-run archived runs.
  * Grading stays per-surface with each surface's own frozen grader.
  * Cross-envelope merging is forbidden; a model card has no merged score.

No prompt text is duplicated into this file. Adapters reference frozen prompts,
runners and graders by path only, and every referenced path is existence-checked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA_VERSION = "veritas.arena_unified_intake.v1"

WORKSPACE = Path(__file__).resolve().parents[1]
ARENA = WORKSPACE / "data" / "evals" / "model-arena"

# --- frozen surface roots (read-only; never modified by this module) ---------
SURFACE_A_DIR = ARENA / "arena-six-20260919"
SURFACE_B_DIR = ARENA / "arena-agentic-v1-20260920"
# Surface C grades against the sealed BANK overlay (4 files) sealed by the
# Board B manifest. The former `arena-agentic-v1-20260920-overlay` target was a
# stale 2-file copy (key-shapes + quarantine only), missing dispatch-
# authorization.json and candidate-isolation.json. Never repoint this away from
# the sealed BANK directory.
SURFACE_C_OVERLAY_DIR = SURFACE_B_DIR / "overlay"
SURFACE_C_PATTERN = (
    ARENA / "results" / "arena-agentic-v1-20260920"
    / "glm53flash-overlay-r2-cli-20260920" / "cli-dispatch.py"
)
SURFACE_D_DIR = ARENA / "arena-integrated-v1-20260920"

SURFACE_A_ENVELOPE = SURFACE_A_DIR / "envelope.json"
SURFACE_A_GRADER = SURFACE_A_DIR / "reference" / "grader.py"
SURFACE_A_KEYS = SURFACE_A_DIR / "reference" / "keys.json"
SURFACE_A_RUNNER = WORKSPACE / "scripts" / "arena_harness.py"

SURFACE_B_VISIBLE_BANK = SURFACE_B_DIR / "candidate-visible-bank.json"
SURFACE_B_HIDDEN_BANK = SURFACE_B_DIR / "hidden-bank.json"
# Packet-lineage snapshot kept for the sealed BANK record. It is an OLDER
# generation of the runner (no overlay/authorization/contamination hardening) and
# cannot reproduce the sealed run's graded-results.json, so it is NOT the grader
# a plan may point at.
SURFACE_B_GRADER_FROZEN = SURFACE_B_DIR / "reference" / "grader-frozen.py"
SURFACE_B_KEYS = SURFACE_B_DIR / "reference" / "keys.json"
SURFACE_B_PROMPTS = SURFACE_B_DIR / "prompts"

# The live grading lineage: `arena_hidden_bank_runner.py` in grade-file form fed by
# the per-run `collect_responses.py`, with exposure=with-fixtures. This is what
# actually produced the sealed overlay run's graded-results.json, so it is the
# grader every surface must reference.
SURFACE_LIVE_GRADER = WORKSPACE / "scripts" / "arena_hidden_bank_runner.py"
SURFACE_B_EXPOSURE = "with-fixtures"

SURFACE_C_KEY_SHAPES = SURFACE_C_OVERLAY_DIR / "key-shapes.json"
SURFACE_C_QUARANTINE = SURFACE_C_OVERLAY_DIR / "quarantine.json"
SURFACE_C_AGENT = "oxalpha-functional-lab"

SURFACE_D_RUNNER = WORKSPACE / "scripts" / "arena_integrated_mission.py"

# The single canonical spend gate. This module reads it and never writes it.
DISPATCH_GATE = SURFACE_B_DIR / "overlay" / "dispatch-authorization.json"

SURFACES = ("A", "B", "C", "D")

DEFAULT_DRYRUN_DIR = WORKSPACE / "tmp" / "unified-intake-dryrun-20260920"


# --- fixed envelope-level output-token budget (Surface A overlay r1) ---------
# A single fixed number for all candidates, never derived per-model (see the
# overlay's why_fixed: a per-model-derived budget would retroactively alter
# conditions for candidates already run and break comparability). 64,000 sits
# ~38% above the largest *successful* observed output (46,288 tokens, Surface
# A family T6; every other family peaks at 10,603) with real headroom, so the
# cap binds only runaway generation, never legitimate reasoning. The 600s
# per-turn wall-clock ceiling stays as a secondary stall backstop only.
DEFAULT_MAX_OUTPUT_TOKENS = 64000
SURFACE_A_TOKEN_OVERLAY = SURFACE_A_DIR / "overlay" / "token-budget-r1.json"

# Stop-reason taxonomy for turns that end without a complete response.
# Anything but "complete" is an operational outcome: reported separately and
# never scored as a factual failure, per the envelope's
# timeout_classification ("operational_not_capability"). A truncation or
# timeout therefore adjudicates to TIMEOUT_EMPTY even when partial text exists,
# UNLESS the grading layer found contamination on the preserved partial text:
# integrity (CONTAMINATED) outranks operational, and transport taint outranks both.
STOP_REASON_COMPLETE = "complete"
OPERATIONAL_STOP_REASONS = frozenset({
    "max_output_tokens", "wall_clock", "provider_error", "empty",
})
STOP_REASONS = frozenset({STOP_REASON_COMPLETE} | OPERATIONAL_STOP_REASONS)


# ---------------------------------------------------------------------------
# 1. Pin-probe receipt validation
# ---------------------------------------------------------------------------

PROBE_KEYS = ("requested", "effective", "modelApplied", "fallbackUsed")


def probe_record(receipt: Any) -> bool:
    """Validate a pin-probe receipt. True only when the pin is proven applied.

    Required shape: {requested, effective, modelApplied, fallbackUsed}.
    Rejects on any mismatch: missing/blank ids, requested != effective,
    modelApplied not exactly True, or fallbackUsed not exactly False.
    A silent provider fallback must never validate a take.
    """
    if not isinstance(receipt, dict):
        return False
    if any(k not in receipt for k in PROBE_KEYS):
        return False
    requested = receipt["requested"]
    effective = receipt["effective"]
    if not isinstance(requested, str) or not requested.strip():
        return False
    if not isinstance(effective, str) or not effective.strip():
        return False
    if requested.strip() != effective.strip():
        return False
    if receipt["modelApplied"] is not True:
        return False
    if receipt["fallbackUsed"] is not False:
        return False
    return True


def make_probe_receipt(model_path: str, applied: bool = True, fallback: bool = False) -> dict:
    """Build a receipt for a requested model (used by the dry-run mock only)."""
    return {
        "requested": model_path,
        "effective": model_path if (applied and not fallback) else f"{model_path}-fallback",
        "modelApplied": bool(applied),
        "fallbackUsed": bool(fallback),
    }


# ---------------------------------------------------------------------------
# 2. Wave scheduler
# ---------------------------------------------------------------------------

def slots_free(running_count: int, max_concurrent: int = 4) -> int:
    """Free lanes given how many are currently running. Never negative."""
    return max(0, int(max_concurrent) - int(running_count))


class WaveScheduler:
    """Deterministic wave planner with a hard concurrency cap and stagger floor.

    A work item is {surface, case_id, rep} plus optional metadata. Items that
    share a non-empty `lane_lock` are serialized: no two items holding the same
    lock land in the same wave, and their input order is preserved. That is how
    Surface D's 3 missions run sequentially on one lane.

    `plan()` emits waves whose lane count never exceeds `max_concurrent`, each
    with a nominal start offset of `wave_index * stagger_s`. `simulate()`
    converts nominal offsets into real admission times under a given lane
    duration, which is how the cap is proven under slow lanes.
    """

    def __init__(self, max_concurrent: int = 4, stagger_s: int = 60,
                 turn_deadline_s: int = 600,
                 max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS) -> None:
        if int(max_concurrent) < 1:
            raise ValueError("max_concurrent must be >= 1")
        if int(stagger_s) < 0:
            raise ValueError("stagger_s must be >= 0")
        self.max_concurrent = int(max_concurrent)
        self.stagger_s = int(stagger_s)
        self.turn_deadline_s = int(turn_deadline_s)
        self.max_output_tokens = int(max_output_tokens)

    def slots_free(self, running_count: int) -> int:
        return slots_free(running_count, self.max_concurrent)

    def admit(self, running_count: int) -> bool:
        """True when one more lane may start right now."""
        return self.slots_free(running_count) > 0

    def plan(self, items: Sequence[dict]) -> dict:
        pending = [dict(it) for it in items]
        waves: list[dict] = []
        wave_index = 0
        while pending:
            taken: list[dict] = []
            deferred: list[dict] = []
            used_locks: set[str] = set()
            for idx, item in enumerate(pending):
                lock = item.get("lane_lock") or f"__item__:{item.get('surface')}:{item.get('case_id')}:{item.get('rep')}:{idx}"
                if len(taken) < self.max_concurrent and lock not in used_locks:
                    used_locks.add(lock)
                    item_timeout = item.get("timeout_s")
                    deadline = (int(item_timeout)
                                if type(item_timeout) is int and item_timeout > 0
                                else self.turn_deadline_s)
                    item_token_budget = item.get("max_output_tokens")
                    token_budget = (int(item_token_budget)
                                    if type(item_token_budget) is int
                                    and item_token_budget > 0
                                    else self.max_output_tokens)
                    lane = {
                        "surface": item.get("surface"),
                        "case_id": item.get("case_id"),
                        "rep": item.get("rep"),
                        "lane_lock": item.get("lane_lock"),
                        "planned_start_s": wave_index * self.stagger_s,
                        "deadline_s": deadline,
                        "timeout_s": deadline,
                        "max_output_tokens": token_budget,
                    }
                    for extra_key in ("turns", "prompt_paths", "runner_path", "grader_path",
                                      "keys_path", "cli", "mission_dir", "mounts"):
                        if extra_key in item:
                            lane[extra_key] = item[extra_key]
                    taken.append(lane)
                else:
                    deferred.append(item)
            if not taken:
                # Unreachable with unique locks, but never silently drop work.
                raise RuntimeError("scheduler stalled: no item admitted in a wave")
            waves.append({
                "wave_index": wave_index,
                "planned_start_s": wave_index * self.stagger_s,
                "lane_count": len(taken),
                "items": taken,
            })
            pending = deferred
            wave_index += 1
        return {
            "schema": SCHEMA_VERSION + ".waves",
            "max_concurrent": self.max_concurrent,
            "stagger_s": self.stagger_s,
            "turn_deadline_s": self.turn_deadline_s,
            "item_count": len(items),
            "wave_count": len(waves),
            "max_lane_count": max((w["lane_count"] for w in waves), default=0),
            "waves": waves,
        }

    def simulate(self, items: Sequence[dict], lane_duration_s: float) -> dict:
        """Real admission times under a lane duration; proves the cap holds.

        Admission respects both the per-wave stagger floor (never starts a lane
        before its nominal offset) and the concurrency cap. Returns actual start
        and end times plus the observed maximum simultaneous lanes.
        """
        plan = self.plan(items)
        ends: list[float] = []
        assignments: list[dict] = []
        for wave in plan["waves"]:
            for lane in wave["items"]:
                start = float(wave["planned_start_s"])
                while True:
                    running = [e for e in ends if e > start]
                    if len(running) < self.max_concurrent:
                        break
                    # Wait for the earliest-finishing lane. min(running) is
                    # strictly greater than start, so this always progresses.
                    start = min(running)
                end = start + float(lane_duration_s)
                ends.append(end)
                assignments.append({
                    "surface": lane["surface"],
                    "case_id": lane["case_id"],
                    "rep": lane["rep"],
                    "wave_index": wave["wave_index"],
                    "planned_start_s": lane["planned_start_s"],
                    "actual_start_s": start,
                    "end_s": end,
                })
        observed = 0
        for a in assignments:
            overlap = sum(
                1 for b in assignments
                if b["actual_start_s"] < a["end_s"] and b["end_s"] > a["actual_start_s"]
            )
            observed = max(observed, overlap)
        return {
            "lane_duration_s": float(lane_duration_s),
            "observed_max_concurrent": observed,
            "cap_respected": observed <= self.max_concurrent,
            "assignments": assignments,
        }


# ---------------------------------------------------------------------------
# 3. Surface adapters (plan-only; no prompt text duplicated)
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _ref(path: Path) -> str:
    """Workspace-relative posix reference for a frozen path."""
    return Path(path).resolve().relative_to(WORKSPACE).as_posix()


def _require(paths: Iterable[Path]) -> None:
    """Fail loudly if a frozen artifact this plan depends on is missing."""
    missing = [str(p) for p in paths if not Path(p).exists()]
    if missing:
        raise FileNotFoundError(f"frozen path(s) missing: {missing}")


def plan_surface_a(model_path: str) -> list[dict]:
    """Surface A: arena-six-20260919, 12 trajectories (6 cases x 2 repetitions)."""
    _require([SURFACE_A_ENVELOPE, SURFACE_A_GRADER, SURFACE_A_KEYS, SURFACE_A_RUNNER])
    envelope = _load_json(SURFACE_A_ENVELOPE)
    reps = int(envelope["scope"]["repetitions_per_candidate"])
    items: list[dict] = []
    for rep in range(1, reps + 1):
        for task in envelope["tasks"]:
            turn_refs = [SURFACE_A_DIR / t for t in task["turns"]]
            _require(turn_refs)
            items.append({
                "surface": "A",
                "case_id": task["id"],
                "rep": rep,
                "lane_lock": None,
                "envelope_id": envelope["envelope_id"],
                "transport": "collectors",
                "turns": [_ref(p) for p in turn_refs],
                "tools_allowed": task.get("tools_allowed", []),
                "runner_path": _ref(SURFACE_A_RUNNER),
                "grader_path": _ref(SURFACE_A_GRADER),
                "keys_path": _ref(SURFACE_A_KEYS),
                "timeout_s": int(envelope["budgets"]["per_turn_wall_clock_s"]),
                # Fixed envelope-level cap; normative record is the overlay at
                # SURFACE_A_TOKEN_OVERLAY (envelope.json itself stays frozen).
                "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
            })
    return items


def plan_surface_b(model_path: str) -> list[dict]:
    """Surface B: pre-overlay new bank, 12 cases, one rep, via collectors."""
    _require([SURFACE_B_HIDDEN_BANK, SURFACE_LIVE_GRADER, SURFACE_B_KEYS, DISPATCH_GATE])
    hidden = _load_json(SURFACE_B_HIDDEN_BANK)
    items: list[dict] = []
    for case in sorted(hidden["cases"], key=lambda c: c["instance_id"]):
        iid = case["instance_id"]
        prompt_json = SURFACE_B_PROMPTS / f"{iid}.json"
        prompt_txt = SURFACE_B_PROMPTS / f"{iid}.txt"
        _require([prompt_json, prompt_txt])
        items.append({
            "surface": "B",
            "case_id": iid,
            "rep": 1,
            "lane_lock": None,
            "envelope_id": hidden["envelope"],
            "family": case.get("family"),
            "transport": "collectors",
            "prompt_paths": [_ref(prompt_json), _ref(prompt_txt)],
            "runner_path": _ref(SURFACE_LIVE_GRADER),
            "grader_path": _ref(SURFACE_LIVE_GRADER),
            "keys_path": _ref(SURFACE_B_KEYS),
            "gate_path": _ref(DISPATCH_GATE),
            "exposure": SURFACE_B_EXPOSURE,
            "timeout_s": 600,
            "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
        })
    return items


def plan_surface_c(model_path: str) -> list[dict]:
    """Surface C: overlay-r2 via the CLI lab pipe (oxalpha-functional-lab).

    Graded by the live runner in grade-file form (fed by the run's own
    `collect_responses.py`) at exposure=with-fixtures -- the lineage that actually
    produced the sealed run's graded-results.json. The sealed packet copy at
    SURFACE_B_GRADER_FROZEN is an older generation and must not be referenced.
    """
    _require([SURFACE_C_KEY_SHAPES, SURFACE_C_QUARANTINE, SURFACE_C_PATTERN,
              SURFACE_LIVE_GRADER])
    key_shapes = _load_json(SURFACE_C_KEY_SHAPES)
    items: list[dict] = []
    for case in sorted(key_shapes["cases"], key=lambda c: c["instance_id"]):
        iid = case["instance_id"]
        prompt_json = SURFACE_B_PROMPTS / f"{iid}.json"
        prompt_txt = SURFACE_B_PROMPTS / f"{iid}.txt"
        _require([prompt_json, prompt_txt])
        items.append({
            "surface": "C",
            "case_id": iid,
            "rep": 1,
            "lane_lock": None,
            "envelope_id": key_shapes["envelope"],
            "family": case.get("family"),
            "transport": "cli-lab-pipe",
            "prompt_paths": [_ref(prompt_json), _ref(prompt_txt)],
            "cli": {
                "agent": SURFACE_C_AGENT,
                "pattern_path": _ref(SURFACE_C_PATTERN),
                "model_path": model_path,
            },
            "grader_path": _ref(SURFACE_LIVE_GRADER),
            "keys_path": _ref(SURFACE_C_KEY_SHAPES),
            "exposure": SURFACE_B_EXPOSURE,
            "timeout_s": 600,
            "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
        })
    return items


def plan_surface_d(model_path: str) -> list[dict]:
    """Surface D: integrated missions 1-3, sequential on a single lane."""
    missions = [
        ("mission-1", SURFACE_D_DIR, SURFACE_D_DIR / "visible"),
        ("mission-2", SURFACE_D_DIR / "mission-2", SURFACE_D_DIR / "mission-2" / "visible"),
        ("mission-3", SURFACE_D_DIR / "mission-3", SURFACE_D_DIR / "mission-3" / "visible"),
    ]
    _require([SURFACE_D_RUNNER])
    items: list[dict] = []
    for order, (mission_id, mission_dir, visible_dir) in enumerate(missions):
        request_md = visible_dir / "request.md"
        contract = mission_dir / "control" / "mission-contract.json"
        _require([request_md, contract, visible_dir])
        items.append({
            "surface": "D",
            "case_id": mission_id,
            "rep": 1,
            "lane_lock": "D-lane-1",
            "ordinal": order,
            "envelope_id": SURFACE_D_DIR.name,
            "transport": "spawn-visible-mount",
            "prompt_paths": [_ref(request_md)],
            "runner_path": _ref(SURFACE_D_RUNNER),
            "grader_path": _ref(contract),
            "mission_dir": _ref(mission_dir),
            "mounts": [_ref(visible_dir)],
            "timeout_s": 600,
            "max_output_tokens": DEFAULT_MAX_OUTPUT_TOKENS,
        })
    return items


ADAPTERS = {
    "A": plan_surface_a,
    "B": plan_surface_b,
    "C": plan_surface_c,
    "D": plan_surface_d,
}


def build_plan(model_path: str) -> dict:
    """Ordered per-surface work-item plan for one model. No dispatch happens here."""
    plan = {
        "schema": SCHEMA_VERSION + ".plan",
        "model_path": model_path,
        "history_policy": "footnoted precedent; archived runs are never re-run",
        "grading_policy": "per-surface frozen grader; cross-envelope merging forbidden",
        "surfaces": {},
    }
    for surface in SURFACES:
        items = ADAPTERS[surface](model_path)
        plan["surfaces"][surface] = {
            "surface": surface,
            "item_count": len(items),
            "items": items,
        }
    return plan


# ---------------------------------------------------------------------------
# 4. Adjudication labels (overlay rescore taxonomy)
# ---------------------------------------------------------------------------

TIMEOUT_EMPTY = "TIMEOUT_EMPTY"
ANSWERED_FAIL = "ANSWERED_FAIL"
INVENTED = "INVENTED"
CONTAMINATED = "CONTAMINATED"
TRANSPORT_TAINT = "TRANSPORT_TAINT"

LABEL_DEFINITIONS = {
    TIMEOUT_EMPTY: "Turn ended without a complete response (truncation, timeout, provider error, or empty); operational, excluded from eligible, never a factual failure.",
    ANSWERED_FAIL: "A response was delivered but failed the frozen grader strictly (wrong, malformed or contract-violating).",
    INVENTED: "The response fabricated content the visible inputs never contained; zeroes the case fail-closed.",
    CONTAMINATED: "The response reproduced hidden-only material, so the case carries no capability signal.",
    TRANSPORT_TAINT: "Dispatch proof is missing or contradicts the request (silent fallback or wrong effective model); quarantines the whole take.",
}

ALL_LABELS = (TIMEOUT_EMPTY, ANSWERED_FAIL, INVENTED, CONTAMINATED, TRANSPORT_TAINT)
QUARANTINE_LABELS = frozenset({TRANSPORT_TAINT, CONTAMINATED})

# Precedence: transport first (it invalidates everything downstream), then
# contamination (integrity outranks operational: a leak that then truncates must
# still quarantine), then the operational outcome, then fabrication, then failure.
_LABEL_PRECEDENCE = (TRANSPORT_TAINT, CONTAMINATED, TIMEOUT_EMPTY, INVENTED, ANSWERED_FAIL)


def adjudicate(record: dict) -> str | None:
    """Map one result record to a label, or None for a clean strict pass.

    Record fields honoured: transport_failed, probe (receipt), stop_reason,
    truncated, response_text, partial_response_text, contaminated, invented,
    strict_pass.

    Precedence is TRANSPORT_TAINT > CONTAMINATED > TIMEOUT_EMPTY > INVENTED >
    ANSWERED_FAIL. Contamination is an integrity signal and is checked before
    the operational outcome: a response that leaks hidden-bank content and then
    hits the token cap must quarantine, never pass as a clean operational turn.
    The `contaminated` flag must already have been populated by the grading
    layer (arena_hidden_bank_runner.grade_text / detect_contamination run on
    the preserved partial_response_text); a precedence reorder alone cannot set
    it. See make_truncated_turn_evidence / attach_truncation_grading.

    A truncated turn whose partial text strictly passes (strict_pass True) still
    adjudicates TIMEOUT_EMPTY (operational, excluded from eligible); the
    preserved-answer signal is surfaced separately via is_truncated_with_pass()
    and the summarize_surface `truncated_with_pass` counter (Gap 2 decision b).
    """
    if record is None:
        return TRANSPORT_TAINT
    if record.get("transport_failed"):
        return TRANSPORT_TAINT
    if "probe" in record and not probe_record(record.get("probe")):
        return TRANSPORT_TAINT
    if record.get("contaminated"):
        return CONTAMINATED
    if is_operational_outcome(record):
        return TIMEOUT_EMPTY
    text = record.get("response_text")
    if not isinstance(text, str) or not text.strip():
        return TIMEOUT_EMPTY
    if record.get("invented"):
        return INVENTED
    if not record.get("strict_pass"):
        return ANSWERED_FAIL
    return None


def is_operational_outcome(record: dict) -> bool:
    """True when a turn ended without a complete response.

    Triggers on an explicit operational stop_reason (max_output_tokens /
    wall_clock / provider_error / empty) or a truncated flag. Partial output
    text, when present, is evidence to preserve, not content to grade.
    """
    if not isinstance(record, dict):
        return False
    if record.get("truncated") is True:
        return True
    stop_reason = record.get("stop_reason")
    return (isinstance(stop_reason, str)
            and stop_reason in OPERATIONAL_STOP_REASONS)


def make_truncated_turn_evidence(partial_text: str | None, usage: dict | None,
                                 stop_reason: str, *, strict_pass: bool = False,
                                 contaminated: bool = False,
                                 invented: bool = False) -> dict:
    """Build the preserved-evidence record for a turn with no complete response.

    Keeps the partial output text and token counts instead of discarding them,
    so a same-model-larger-budget control run later can separate "still
    generating" from "looping". The record adjudicates operational
    (TIMEOUT_EMPTY, never factual) via is_operational_outcome, unless the
    grading layer has set `contaminated` (which outranks it per adjudicate()).

    Integrity wiring (Gap 1): this builder does not itself know the hidden bank,
    so it cannot detect contamination. The caller MUST populate `contaminated`
    (and `strict_pass` / `invented` where known) from the grading layer run on
    the preserved partial text -- i.e. arena_hidden_bank_runner.grade_text /
    detect_contamination(partial_response_text, hidden_only_tokens(...)) -- or
    via attach_truncation_grading() below. A precedence reorder alone is useless
    if nothing ever sets the flag on a truncated record; an unset flag defaults
    to False (clean) here.
    """
    if stop_reason not in OPERATIONAL_STOP_REASONS:
        raise ValueError(f"stop_reason must be operational, got {stop_reason!r}")
    if usage is not None and not isinstance(usage, dict):
        raise ValueError("usage must be a dict of token counts or None")
    text = partial_text if isinstance(partial_text, str) else ""
    return {
        "response_text": text,
        "partial_response_text": text,
        "usage": usage,
        "stop_reason": stop_reason,
        "truncated": True,
        "complete": False,
        "strict_pass": bool(strict_pass),
        "contaminated": bool(contaminated),
        "invented": bool(invented),
    }


def attach_truncation_grading(record: dict, grading: dict | None) -> dict:
    """Copy grading-layer signals onto a truncated evidence record (in place).

    `grading` is the dict produced by running the grading layer on the
    preserved partial text (arena_hidden_bank_runner.grade_text on
    record["partial_response_text"]). Copies the `contaminated`, `invented`,
    and `strict_pass` booleans (plus optional contamination/invented detail
    fields when present) so adjudicate() and summarize_surface() see the same
    integrity/capability signals for truncated turns as for completed ones.
    Returns the same record for chaining. A None grading leaves the record
    untouched.
    """
    if not isinstance(record, dict) or not isinstance(grading, dict):
        return record
    for key in ("contaminated", "invented", "strict_pass"):
        if key in grading:
            record[key] = bool(grading[key])
    for key in ("contamination_severity", "contamination_reasons",
                "contamination_tokens", "invented_content_suspect",
                "invented_tokens"):
        if key in grading:
            record[key] = grading[key]
    return record


def is_truncated_with_pass(record: dict) -> bool:
    """True when an operational (truncated) turn preserved a strict pass.

    Gap 2 decision (b): the turn stays operational (adjudicate() returns
    TIMEOUT_EMPTY and it is excluded from `eligible`), but it is counted
    separately in summarize_surface as `truncated_with_pass` so a correct
    answer that failed to terminate is visibly not the same thing as an empty
    response and can never be silently absorbed into the timeout bucket. The
    `strict_pass` flag must come from the grading layer run on the preserved
    partial text (see make_truncated_turn_evidence).
    """
    if not isinstance(record, dict):
        return False
    return bool(is_operational_outcome(record) and record.get("strict_pass") is True)


def label_definition(label: str) -> str:
    """One-line definition for a label, matching the overlay rescore taxonomy."""
    if label not in LABEL_DEFINITIONS:
        raise KeyError(f"unknown adjudication label: {label}")
    return LABEL_DEFINITIONS[label]


# ---------------------------------------------------------------------------
# 5. Model card writer (per surface; never a merged cross-envelope score)
# ---------------------------------------------------------------------------

CARD_SCHEMA = "veritas.arena_unified_model_card.v1"
FORBIDDEN_CARD_KEYS = (
    "merged_score", "overall_score", "composite_score",
    "cross_envelope_score", "total_score", "unified_score",
)


def summarize_surface(records: Sequence[dict]) -> dict:
    """Per-surface strict/eligible/transport/flags. A taint voids the take whole.

    Denominator rule (Gap 3): operational outcomes (adjudicate() ==
    TIMEOUT_EMPTY, including truncated turns with preserved partial text) are
    EXCLUDED from `eligible`, matching the board canon's second clause
    ("parse_error json_empty denotes the operational timeout and is excluded
    from factual denominators"). So eligible = total - operational_count, and
    strict/eligible measures capability conditional on answered turns; the token
    cap then cannot systematically depress scores as truncation grows. A
    quarantined take still voids whole (eligible 0, take_voided True).

    Gap 2 counter (decision b): truncated turns whose preserved partial text
    strictly passes stay operational but are counted separately as
    `truncated_with_pass` (subset of the operational count) with the
    `eligible_rule` pinned, so they are never silently absorbed into the
    timeout bucket. `truncated_count` counts all truncated/operational turns.
    """
    flags: dict[str, int] = {}
    quarantined = False
    truncated_with_pass = 0
    truncated_count = 0
    for record in records:
        label = adjudicate(record)
        if isinstance(record, dict) and (record.get("truncated") is True
                                         or is_operational_outcome(record)):
            truncated_count += 1
        if label is None:
            continue
        flags[label] = flags.get(label, 0) + 1
        if label in QUARANTINE_LABELS:
            quarantined = True
        if label == TIMEOUT_EMPTY and isinstance(record, dict) \
                and record.get("strict_pass") is True:
            truncated_with_pass += 1
    if quarantined:
        return {
            "total": len(records),
            "strict": 0,
            "eligible": 0,
            "eligible_rule": "operational_excluded; take voided by quarantine",
            "operational_count": flags.get(TIMEOUT_EMPTY, 0),
            "truncated_count": truncated_count,
            "truncated_with_pass": truncated_with_pass,
            "transport": "quarantined",
            "take_voided": True,
            "flags": flags,
        }
    operational = flags.get(TIMEOUT_EMPTY, 0)
    return {
        "total": len(records),
        "strict": sum(1 for r in records if adjudicate(r) is None),
        "eligible": len(records) - operational,
        "eligible_rule": "operational_excluded",
        "operational_count": operational,
        "truncated_count": truncated_count,
        "truncated_with_pass": truncated_with_pass,
        "transport": "clean",
        "take_voided": False,
        "flags": flags,
    }


def build_model_card(model_path: str, probe: dict,
                     surface_summaries: dict[str, dict]) -> dict:
    """Unified model card: one entry per surface, no cross-envelope score."""
    card = {
        "schema": CARD_SCHEMA,
        "model_path": model_path,
        "probe": {
            "valid": probe_record(probe),
            "receipt": probe,
        },
        "surfaces": {},
        "quarantined_surfaces": [],
        "comparability": (
            "Per-surface only. Each surface carries its own frozen envelope, grader "
            "and dispatch conditions; runs across envelopes are not comparable and "
            "no merged cross-envelope score exists or may be derived from this card."
        ),
    }
    for surface in SURFACES:
        summary = surface_summaries.get(surface, {
            "total": 0, "strict": 0, "eligible": 0,
            "transport": "not_run", "take_voided": False, "flags": {},
        })
        card["surfaces"][surface] = {
            "strict": summary.get("strict", 0),
            "eligible": summary.get("eligible", 0),
            "transport": summary.get("transport", "not_run"),
            "take_voided": summary.get("take_voided", False),
            "flags": summary.get("flags", {}),
        }
        if card["surfaces"][surface]["transport"] == "quarantined":
            card["quarantined_surfaces"].append(surface)
    leaked = [k for k in FORBIDDEN_CARD_KEYS if k in card]
    if leaked:
        raise AssertionError(f"model card must not carry merged score keys: {leaked}")
    return card


# ---------------------------------------------------------------------------
# 6. Dry-run executor (mock; canned receipts; one scripted taint injection)
# ---------------------------------------------------------------------------

class MockExecutor:
    """Deterministic canned executor. No model, network, subprocess or gate write.

    Results are synthesised from the work item itself so the dry-run proves the
    orchestration path (probe -> plan -> waves -> adjudicate -> card) without
    spending anything. `taint_surface` / `taint_index` inject exactly one
    scripted transport taint to prove quarantine triggers.
    """

    def __init__(self, model_path: str, taint_surface: str = "C",
                 taint_index: int = 2,
                 truncate: tuple | None = None) -> None:
        self.model_path = model_path
        self.taint_surface = taint_surface
        self.taint_index = int(taint_index)
        # Optional (surface, index[, grading]) tuple that ends as a token-capped
        # turn: partial text plus usage are preserved and the record adjudicates
        # operational (TIMEOUT_EMPTY), never factual -- unless grading carries
        # contaminated=True, in which case integrity outranks operational and the
        # take quarantines. The optional grading dict simulates the grading layer
        # run on the preserved partial text. Off by default.
        self.truncate = truncate
        self.calls = 0

    def probe(self, model_path: str) -> dict:
        return make_probe_receipt(model_path, applied=True, fallback=False)

    def dispatch(self, item: dict, index: int) -> dict:
        self.calls += 1
        receipt = self.probe(item.get("_model_path", self.model_path))
        tainted = (item.get("surface") == self.taint_surface and index == self.taint_index)
        if tainted:
            # Scripted taint: the provider silently fell back, so the pin probe fails.
            receipt = make_probe_receipt(item.get("_model_path", self.model_path),
                                         applied=True, fallback=True)
        if (self.truncate is not None
                and item.get("surface") == self.truncate[0]
                and index == self.truncate[1]):
            # Scripted token-cap truncation: partial text and token counts
            # are preserved, not discarded. An optional third tuple element
            # carries grading-layer signals (strict_pass / contaminated /
            # invented) as if grade_text had run on the partial text.
            grading = self.truncate[2] if len(self.truncate) > 2 else {}
            record = make_truncated_turn_evidence(
                '{"partial": "capped before completion"}',
                {"input_tokens": 512, "output_tokens": DEFAULT_MAX_OUTPUT_TOKENS},
                "max_output_tokens",
                strict_pass=bool((grading or {}).get("strict_pass", False)),
                contaminated=bool((grading or {}).get("contaminated", False)),
                invented=bool((grading or {}).get("invented", False)),
            )
            record.update({
                "surface": item.get("surface"),
                "case_id": item.get("case_id"),
                "rep": item.get("rep"),
                "probe": receipt,
                "transport_failed": False,
                "invented": False,
                "contaminated": False,
                "scripted_taint": False,
                "scripted_truncation": True,
            })
            return record
        return {
            "surface": item.get("surface"),
            "case_id": item.get("case_id"),
            "rep": item.get("rep"),
            "probe": receipt,
            "transport_failed": False,
            "response_text": "" if (index % 7 == 6) else '{"dry_run": "canned"}',
            "strict_pass": (index % 3 == 0),
            "invented": False,
            "contaminated": False,
            "scripted_taint": tainted,
        }


def _flatten_plan_items(plan: dict) -> list[dict]:
    items: list[dict] = []
    for surface in SURFACES:
        items.extend(plan["surfaces"][surface]["items"])
    return items


def _sha256_file(path: Path) -> str | None:
    p = Path(path)
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_gate(gate_path: Path = DISPATCH_GATE) -> dict:
    """Read the canonical spend gate. This module never writes it."""
    doc = _load_json(gate_path)
    return {
        "path": _ref(gate_path),
        "dispatch_ready": doc.get("dispatch_ready"),
        "authorized_by": doc.get("authorized_by"),
        "authorized_at": doc.get("authorized_at"),
        "sha256": _sha256_file(gate_path),
    }


def refuse_live_dispatch(gate: dict) -> None:
    """Live dispatch is out of scope for this build, and gated besides."""
    if not gate.get("dispatch_ready"):
        raise PermissionError(
            "live dispatch refused: dispatch_ready is false in "
            f"{gate.get('path')}; only the owner may release the spend gate"
        )
    raise NotImplementedError(
        "live dispatch is not implemented in this build; owner-named model and "
        "spend authorization are required before any transport is wired"
    )


def run_intake(model_path: str, executor, scheduler: WaveScheduler | None = None,
               lane_duration_s: float = 600.0) -> dict:
    """Probe, plan, schedule, execute (via executor), adjudicate, card.

    The executor is the only thing that could ever reach a transport; in the
    dry-run it is MockExecutor and never leaves this process.
    """
    sched = scheduler or WaveScheduler()
    gate_before = read_gate()

    probe = executor.probe(model_path)
    probe_ok = probe_record(probe)
    if not probe_ok:
        return {
            "schema": SCHEMA_VERSION + ".run",
            "model_path": model_path,
            "probe": {"valid": False, "receipt": probe},
            "status": "probe_rejected",
            "gate": gate_before,
        }

    plan = build_plan(model_path)
    records_by_surface: dict[str, list[dict]] = {s: [] for s in SURFACES}
    waves_by_surface: dict[str, dict] = {}
    sim_by_surface: dict[str, dict] = {}

    for surface in SURFACES:
        items = plan["surfaces"][surface]["items"]
        waves = sched.plan(items)
        waves_by_surface[surface] = waves
        sim_by_surface[surface] = sched.simulate(items, lane_duration_s)
        for index, item in enumerate(items):
            stamped = dict(item)
            stamped["_model_path"] = model_path
            record = executor.dispatch(stamped, index)
            records_by_surface[surface].append(record)

    summaries = {s: summarize_surface(records_by_surface[s]) for s in SURFACES}
    card = build_model_card(model_path, probe, summaries)
    gate_after = read_gate()

    return {
        "schema": SCHEMA_VERSION + ".run",
        "model_path": model_path,
        "status": "dry_run_complete",
        "probe": {"valid": True, "receipt": probe},
        "plan": plan,
        "waves": waves_by_surface,
        "simulation": sim_by_surface,
        "records": records_by_surface,
        "summaries": summaries,
        "card": card,
        "gate_before": gate_before,
        "gate_after": gate_after,
        "gate_intact": gate_before == gate_after,
        "model_calls": 0,
        "live_dispatch": 0,
    }


def run_dry_run(model_path: str, out_dir: Path | None = None,
                scheduler: WaveScheduler | None = None,
                executor: MockExecutor | None = None,
                lane_duration_s: float = 600.0) -> dict:
    """Full dry-run pipeline; writes plan, waves, card and a summary. Spends nothing."""
    out = Path(out_dir) if out_dir else DEFAULT_DRYRUN_DIR
    out.mkdir(parents=True, exist_ok=True)
    ex = executor or MockExecutor(model_path)
    result = run_intake(model_path, ex, scheduler=scheduler, lane_duration_s=lane_duration_s)

    (out / "plan.json").write_text(
        json.dumps(result["plan"], indent=2, sort_keys=False), encoding="utf-8")
    (out / "waves.json").write_text(
        json.dumps({
            "schema": SCHEMA_VERSION + ".waves.bundle",
            "model_path": model_path,
            "by_surface": result["waves"],
            "simulation": result["simulation"],
        }, indent=2, sort_keys=False), encoding="utf-8")
    (out / "model-card.json").write_text(
        json.dumps(result["card"], indent=2, sort_keys=False), encoding="utf-8")

    taint = None
    for surface, records in result["records"].items():
        for index, record in enumerate(records):
            if record.get("scripted_taint"):
                taint = {
                    "surface": surface,
                    "case_id": record.get("case_id"),
                    "index": index,
                    "label": adjudicate(record),
                    "quarantined_surfaces": result["card"]["quarantined_surfaces"],
                }
    summary = {
        "schema": SCHEMA_VERSION + ".dryrun",
        "mode": "dry-run",
        "model_path": model_path,
        "status": result["status"],
        "probe": result["probe"],
        "surfaces": result["summaries"],
        "quarantined_surfaces": result["card"]["quarantined_surfaces"],
        "taint_injection": taint,
        "gate": {
            **result["gate_after"],
            "intact_after_dry_run": result["gate_intact"],
        },
        "spend": {"model_calls": 0, "live_dispatch": 0, "network": 0},
        "outputs": ["plan.json", "waves.json", "model-card.json"],
    }
    (out / "dryrun-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=False), encoding="utf-8")
    return {"result": result, "summary": summary, "out_dir": str(out)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="arena_unified_intake.py",
        description="Unified arena intake orchestration. Emits plans; never calls a model.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", metavar="MODEL_PATH",
                       help="run the full pipeline against a mock executor and write tmp artifacts")
    group.add_argument("--plan-only", metavar="MODEL_PATH",
                       help="write the dispatch plan without executing anything")
    group.add_argument("--gate-status", action="store_true",
                       help="print the canonical spend gate state")
    parser.add_argument("--out", default=None, help="output directory (dry-run)")
    parser.add_argument("--max-concurrent", type=int, default=4)
    parser.add_argument("--stagger-s", type=int, default=60)
    parser.add_argument("--turn-deadline-s", type=int, default=600)
    parser.add_argument("--max-output-tokens", type=int,
                        default=DEFAULT_MAX_OUTPUT_TOKENS)
    args = parser.parse_args(argv)

    if args.gate_status:
        print(json.dumps(read_gate(), indent=2))
        return 0

    scheduler = WaveScheduler(max_concurrent=args.max_concurrent,
                              stagger_s=args.stagger_s,
                              turn_deadline_s=args.turn_deadline_s,
                              max_output_tokens=args.max_output_tokens)

    if args.plan_only:
        plan = build_plan(args.plan_only)
        out = Path(args.out) if args.out else DEFAULT_DRYRUN_DIR
        out.mkdir(parents=True, exist_ok=True)
        (out / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
        for surface in SURFACES:
            items = plan["surfaces"][surface]["items"]
            waves = scheduler.plan(items)
            print(f"surface {surface}: {len(items)} items -> {waves['wave_count']} waves "
                  f"(max lanes {waves['max_lane_count']})")
        print(f"plan written: {out / 'plan.json'}")
        return 0

    outcome = run_dry_run(args.dry_run, out_dir=args.out, scheduler=scheduler)
    summary = outcome["summary"]
    print(f"dry-run {summary['status']} for {summary['model_path']}")
    for surface, s in summary["surfaces"].items():
        print(f"  {surface}: strict={s['strict']} eligible={s['eligible']} "
              f"transport={s['transport']} flags={s['flags']}")
    print(f"  taint: {summary['taint_injection']}")
    print(f"  gate intact: {summary['gate']['intact_after_dry_run']} "
          f"(dispatch_ready={summary['gate']['dispatch_ready']})")
    print(f"  artifacts: {outcome['out_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
