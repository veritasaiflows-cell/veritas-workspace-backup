"""Bounded wall-clock enforcement for live arena candidate dispatches.

Problem: scripts/arena_hidden_bank_runner.py writes timeout_s=600 into the
dispatch plan/contract, but nothing killed or timed out a stuck candidate
subagent (observed 2026-09-20: a GLM Flash T6 abstention case ran 18+ min
with no reply). This module is the deterministic half of the enforcement
path:

  plan deadlines  ->  agent spawn rule  ->  stuck detection  ->  fail-closed grading

- Plan deadlines: --dispatch-plan now stamps a top-level ``deadline_utc``
  (timestamp_utc + timeout_s) plus per-case ``deadline_utc``/``timeout_s``
  and a ``spawn_rule`` block. The run contract mirrors ``deadline_utc``
  whenever ``timeout_s`` is recorded.
- Agent spawn rule (enforced by the dispatcher, not by this file): spawn
  each candidate case with ``runTimeoutSeconds`` equal to the plan
  ``timeout_s`` (600), zero retries. A timeout, cancel, or missing reply
  is recorded as an empty-string response, never retried, never left
  pending.
- Stuck detection + fail-closed grading: this script checks a partial
  responses map against plan deadlines and finalizes it for
  ``--collect`` grading. Missing or overdue cases become ``""``, which
  the runner already grades as ``operational_timeout=True`` /
  ``operational_outcome=timeout_empty`` (never a factual pass).

This file is stdlib-only, reads no hidden bank, and touches no capital,
brokerage, account, order, or execution path. Fail-closed throughout:
any malformed plan, response map, or timestamp refuses instead of
guessing.

Usage:
  python scripts/arena_dispatch_enforcer.py --plan dispatch-plan.json \\
      --responses partial-responses.json --out responses.final.json \\
      --audit timeout-audit.json [--now 2026-09-20T21:00:00Z]
  python scripts/arena_dispatch_enforcer.py --plan dispatch-plan.json \\
      --check --responses partial-responses.json [--now ISO]
  python scripts/arena_dispatch_enforcer.py --plan dispatch-plan.json \\
      --init --out dispatch-state.json

Exit codes: 0 ok (check: no stuck/overdue), 2 check found stuck or overdue
cases, 1 fail-closed refusal.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

ENFORCER_VERSION = "arena-dispatch-enforcer-v1"
EXPECTED_PLAN_SCHEMA = "veritas.arena_dispatch_plan.v1"
AUDIT_SCHEMA = "veritas.arena_dispatch_timeout_audit.v1"
STATE_SCHEMA = "veritas.arena_dispatch_state.v1"


def _fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    raise SystemExit(f"enforcer_fail_closed: {msg}")


def parse_iso_aware(raw: str, label: str) -> datetime.datetime:
    if not isinstance(raw, str) or not raw.strip():
        _fail(f"{label}_missing")
    try:
        parsed = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        _fail(f"{label}_invalid:{raw!r}")
    if parsed.tzinfo is None:
        _fail(f"{label}_requires_timezone:{raw!r}")
    return parsed


def load_json(path: Path, label: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _fail(f"missing_file:{path}")
    except json.JSONDecodeError as exc:
        _fail(f"invalid_json:{label}:{exc}")
    except OSError as exc:
        _fail(f"unreadable_file:{label}:{exc}")


def effective_plan_deadline(plan: dict) -> datetime.datetime:
    timeout_s = plan.get("timeout_s")
    if not isinstance(timeout_s, int) or timeout_s <= 0:
        _fail(f"plan_timeout_invalid:{timeout_s!r}")
    if plan.get("retries", 0) != 0:
        _fail(f"plan_retries_must_be_zero:{plan.get('retries')!r}")
    declared = plan.get("deadline_utc")
    if declared is not None:
        return parse_iso_aware(declared, "plan_deadline_utc")
    issued = plan.get("timestamp_utc")
    if issued is None:
        _fail("plan_missing_timestamp_and_deadline")
    base = parse_iso_aware(issued, "plan_timestamp_utc")
    return base + datetime.timedelta(seconds=timeout_s)


def case_deadline(case: dict, fallback: datetime.datetime, index: int) -> datetime.datetime:
    declared = case.get("deadline_utc")
    if declared is not None:
        return parse_iso_aware(declared, f"case_deadline_utc[{index}]")
    timeout_s = case.get("timeout_s")
    if timeout_s is not None:
        if not isinstance(timeout_s, int) or timeout_s <= 0:
            _fail(f"case_timeout_invalid[{index}]:{timeout_s!r}")
    return fallback


def check_plan(plan: dict) -> list:
    if not isinstance(plan, dict):
        _fail("plan_not_object")
    if plan.get("schema") != EXPECTED_PLAN_SCHEMA:
        _fail(f"plan_schema_mismatch:{plan.get('schema')!r}")
    cases = plan.get("cases")
    if not isinstance(cases, list) or not cases:
        _fail("plan_cases_missing_or_empty")
    seen = set()
    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            _fail(f"plan_case_not_object[{idx}]")
        iid = case.get("instance_id")
        if not isinstance(iid, str) or not iid:
            _fail(f"plan_case_missing_id[{idx}]")
        if iid in seen:
            _fail(f"plan_duplicate_id:{iid}")
        seen.add(iid)
    return cases


def load_responses(path: Path) -> dict:
    doc = load_json(path, "responses")
    mapping = doc.get("responses") if isinstance(doc, dict) and isinstance(doc.get("responses"), dict) else doc
    if not isinstance(mapping, dict):
        _fail("responses_not_object_map")
    for key, value in mapping.items():
        if not isinstance(value, str):
            _fail(f"responses_value_not_string:{key}")
    return mapping


def classify(plan: dict, responses: dict, now: datetime.datetime) -> dict:
    cases = check_plan(plan)
    plan_deadline = effective_plan_deadline(plan)
    answered, pending, overdue = [], [], []
    per_case = []
    for idx, case in enumerate(cases):
        iid = case["instance_id"]
        deadline = case_deadline(case, plan_deadline, idx)
        text = responses.get(iid)
        has_answer = isinstance(text, str) and text != ""
        if has_answer:
            # A late answer is still an answer: the model replied. Record
            # lateness additively; grading of content is the runner's job.
            status = "answered_late" if now > deadline else "answered"
            answered.append(iid)
        elif now > deadline:
            status = "overdue_timeout"
            overdue.append(iid)
        else:
            status = "pending"
            pending.append(iid)
        per_case.append({
            "instance_id": iid,
            "family": case.get("family"),
            "deadline_utc": deadline.isoformat(),
            "status": status,
        })
    return {
        "answered": sorted(answered),
        "pending": sorted(pending),
        "overdue": sorted(overdue),
        "per_case": per_case,
        "plan_deadline_utc": plan_deadline.isoformat(),
    }


def finalize(plan: dict, responses: dict, now: datetime.datetime) -> tuple:
    verdict = classify(plan, responses, now)
    final = dict(responses)
    timed_out = []
    for row in verdict["per_case"]:
        iid = row["instance_id"]
        if row["status"] == "overdue_timeout" or iid not in final:
            # Fail-closed: a missing slot can never become a factual pass.
            # An overdue slot is frozen to "" even if a late reply arrives
            # after finalization; rerun finalize to re-evaluate instead of
            # editing the finalized map by hand.
            if not isinstance(final.get(iid), str) or final.get(iid) == "" or row["status"] == "overdue_timeout":
                final[iid] = ""
                timed_out.append(iid)
    # Refuse to silently drop unknown ids: they indicate a wrong plan pairing.
    plan_ids = {c["instance_id"] for c in plan["cases"]}
    extra = sorted(set(final) - plan_ids)
    if extra:
        _fail(f"responses_extra_ids:{extra}")
    missing = sorted(plan_ids - set(final))
    if missing:  # pragma: no cover - classify already covers, defense in depth
        _fail(f"responses_missing_ids:{missing}")
    for key, value in final.items():
        if not isinstance(value, str):
            _fail(f"final_value_not_string:{key}")
    audit = {
        "schema": AUDIT_SCHEMA,
        "enforcer_version": ENFORCER_VERSION,
        "plan_schema": plan.get("schema"),
        "plan_model": plan.get("model"),
        "plan_timeout_s": plan.get("timeout_s"),
        "plan_deadline_utc": verdict["plan_deadline_utc"],
        "now_utc": now.isoformat(),
        "total": len(plan_ids),
        "answered_count": len(verdict["answered"]),
        "pending_count": len(verdict["pending"]),
        "operational_timeout_count": len(timed_out),
        "timed_out_ids": sorted(timed_out),
        "stuck_ids": sorted(verdict["overdue"]),
        "pending_ids": verdict["pending"],
        "answered_ids": verdict["answered"],
        "grading_note": ("Timed-out slots are empty strings: the runner grades "
                         "them as operational_timeout/timeout_empty, never as "
                         "factual passes."),
    }
    return final, audit


def build_state(plan: dict) -> dict:
    cases = check_plan(plan)
    plan_deadline = effective_plan_deadline(plan)
    rows = []
    for idx, case in enumerate(cases):
        deadline = case_deadline(case, plan_deadline, idx)
        rows.append({
            "instance_id": case["instance_id"],
            "family": case.get("family"),
            "status": "pending",
            "timeout_s": case.get("timeout_s", plan.get("timeout_s")),
            "deadline_utc": deadline.isoformat(),
            "dispatched_at": None,
            "session_key": None,
        })
    return {
        "schema": STATE_SCHEMA,
        "enforcer_version": ENFORCER_VERSION,
        "plan_schema": plan.get("schema"),
        "plan_model": plan.get("model"),
        "plan_timeout_s": plan.get("timeout_s"),
        "plan_deadline_utc": plan_deadline.isoformat(),
        "cases": rows,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Arena dispatch wall-clock enforcer.")
    parser.add_argument("--plan", required=True, help="dispatch-plan.json path")
    parser.add_argument("--responses", default=None, help="Partial responses JSON path")
    parser.add_argument("--out", default=None, help="Finalized responses output path")
    parser.add_argument("--audit", default=None, help="Timeout audit output path")
    parser.add_argument("--check", action="store_true", help="Report stuck/overdue without writing")
    parser.add_argument("--init", action="store_true", help="Write initial dispatch-state.json")
    parser.add_argument("--now", default=None, help="Override now (ISO-8601 with timezone)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    plan = load_json(Path(args.plan), "plan")
    now = parse_iso_aware(args.now, "now") if args.now else datetime.datetime.now(datetime.timezone.utc)
    if args.init:
        if args.check or args.responses or args.audit:
            _fail("init_exclusive")
        if not args.out:
            _fail("init_requires_out")
        state = build_state(plan)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"state": str(out), "total": len(state["cases"]),
                          "plan_deadline_utc": state["plan_deadline_utc"]}, indent=2))
        return 0
    if args.check and args.out:
        _fail("check_does_not_write")
    if not args.responses:
        _fail("responses_required")
    responses = load_responses(Path(args.responses))
    if args.check:
        verdict = classify(plan, responses, now)
        print(json.dumps({
            "now_utc": now.isoformat(),
            "plan_deadline_utc": verdict["plan_deadline_utc"],
            "answered": len(verdict["answered"]),
            "pending": len(verdict["pending"]),
            "overdue": len(verdict["overdue"]),
            "stuck_ids": verdict["overdue"],
            "pending_ids": verdict["pending"],
        }, indent=2, sort_keys=True))
        return 2 if verdict["overdue"] else 0
    if not args.out or not args.audit:
        _fail("finalize_requires_out_and_audit")
    final, audit = finalize(plan, responses, now)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(final, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit_path = Path(args.audit)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: audit[k] for k in (
        "total", "answered_count", "pending_count",
        "operational_timeout_count", "timed_out_ids")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
