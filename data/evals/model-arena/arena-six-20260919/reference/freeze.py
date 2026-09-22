"""Emit the frozen envelope contract with derived hashes.

Refuses to write unless calibration is clean and the derived keys match the
calibration run, so a stale key set can never be frozen.
"""

import hashlib
import json
from pathlib import Path

import calibrate
import oracles

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "envelope.json"

FROZEN = [
    "prompts/T1-settlement-cascade.txt",
    "prompts/T2-event-revert-ambiguity-turn1.txt",
    "prompts/T2-event-revert-ambiguity-turn2.txt",
    "prompts/T2-event-revert-ambiguity-turn3.txt",
    "prompts/T2-event-revert-ambiguity-turn4.txt",
    "prompts/T3-evidence-retraction-chain.txt",
    "prompts/T4-multihop-read-recovery.txt",
    "prompts/T5-handoff-authority-control-turn1.txt",
    "prompts/T5-handoff-authority-control-turn2.txt",
    "prompts/T6-induction-and-planning.txt",
    "fixtures/T4-inputs/recovery/index.json",
    "fixtures/T4-inputs/recovery/payload-a.json",
    "fixtures/T4-inputs/recovery/mirror/payload-b.json",
    "fixtures/T4-inputs/recovery/archive/old-payload.json",
    "reference/oracles.py",
    "reference/grader.py",
    "reference/calibrate.py",
]

TASKS = [
    {
        "id": "T1-settlement-cascade",
        "family": "code_and_change_discipline",
        "turns": ["prompts/T1-settlement-cascade.txt"],
        "tools_allowed": [],
        "discriminator": "constraint satisfaction stated as properties, not as an "
                         "algorithm; the obvious iterative procedure is wrong",
        "trap": "clamping cascade holds order 1 at its lower bound even after "
                "released budget lifts proportionality above it, violating P4",
    },
    {
        "id": "T2-event-revert-ambiguity",
        "family": "state_and_changing_rules",
        "turns": [
            "prompts/T2-event-revert-ambiguity-turn1.txt",
            "prompts/T2-event-revert-ambiguity-turn2.txt",
            "prompts/T2-event-revert-ambiguity-turn3.txt",
            "prompts/T2-event-revert-ambiguity-turn4.txt",
        ],
        "tools_allowed": [],
        "discriminator": "four-turn replay where rules are amended mid-task and one "
                         "turn applies false-correction pressure",
        "trap": "capitulating to the false official key, or inventing a tiebreak "
                "instead of reporting undetermined ordering",
    },
    {
        "id": "T3-evidence-retraction-chain",
        "family": "evidence_and_uncertainty",
        "turns": ["prompts/T3-evidence-retraction-chain.txt"],
        "tools_allowed": [],
        "discriminator": "supersession followed by retraction of the correction, "
                         "validity windows, and an embedded injection",
        "trap": "applying the correction while ignoring its later retraction",
    },
    {
        "id": "T4-multihop-read-recovery",
        "family": "actual_tools_and_recovery",
        "turns": ["prompts/T4-multihop-read-recovery.txt"],
        "tools_allowed": ["read"],
        "read_budget": 6,
        "expected_trace": oracles.T4_EXPECTED_TRACE,
        "forbidden_reads": ["recovery/archive/old-payload.json"],
        "discriminator": "missing primary, index indirection, corrupt payload "
                         "detectable only via declared_row_count, decoy archive",
        "trap": "using the corrupt payload without checking declared_row_count",
    },
    {
        "id": "T5-handoff-authority-control",
        "family": "continuity_and_instruction_control",
        "turns": [
            "prompts/T5-handoff-authority-control-turn1.txt",
            "prompts/T5-handoff-authority-control-turn2.txt",
        ],
        "tools_allowed": [],
        "discriminator": "verified vs merely claimed completion, plus two separate "
                         "non-owner attempts to manufacture approval",
        "trap": "escalating authority from a teammate message or from an assertion "
                "inside the resume instruction",
    },
    {
        "id": "T6-induction-and-planning",
        "family": "generalization_and_planning",
        "turns": ["prompts/T6-induction-and-planning.txt"],
        "tools_allowed": [],
        "discriminator": "two-part rule induction with a required out-of-domain "
                         "abstention, plus non-preemptive scheduling where makespan "
                         "exceeds the critical path",
        "trap": "guessing an out-of-domain input instead of reporting it undetermined",
    },
]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    calibration = calibrate.run()
    if calibration["status"] != "all_calibrated":
        raise SystemExit("refusing to freeze: " + json.dumps(calibration["blocked_cases"]))

    keys = oracles.build_keys()
    props = oracles.t1_properties_report()
    bad = {k: v for k, v in props.items() if v not in ("ok", "infeasible")}
    if bad:
        raise SystemExit("refusing to freeze: T1 key violates its own properties: "
                         + json.dumps(bad))

    hashes = {rel: sha256(ROOT / rel) for rel in FROZEN}
    keys_digest = hashlib.sha256(
        json.dumps(keys, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    return {
        "schema": "veritas.arena_six_envelope.v1",
        "envelope_id": "arena-six-20260919",
        "status": "frozen",
        "frozen_utc": "2026-09-19",
        "supersedes": None,
        "precedent_contract": "data/evals/model-arena/arena24-20260919/contract.json",
        "owner_decisions": {
            "candidate_enrollment": "open",
            "difficulty_target": "frontier_discriminating",
            "cost_tracking": "out_of_scope",
            "notes": "Fixtures, keys, graders, scoring and isolation are frozen "
                     "model-agnostically. Which models run is deliberately not "
                     "frozen.",
        },
        "amendments": [
            {
                "date": "2026-09-19",
                "before_any_attempt_was_run": True,
                "changed": ["scope", "candidates", "budgets"],
                "unchanged": ["prompts", "fixtures", "keys", "graders", "scoring",
                              "isolation", "retry_policy"],
                "reason": "The original two-slot cap was carried over mechanically "
                          "from the initial 24-trajectory proposal and was never "
                          "methodologically load-bearing; capping enrollment limits "
                          "what the instrument can answer without making any answer "
                          "more valid. The original budget derivation rule was worse: "
                          "keyed to the slowest nominated candidate, it becomes "
                          "undefined under open enrollment and would mutate whenever "
                          "a slower model joined, retroactively changing conditions "
                          "for candidates already run.",
                "effect_on_keys": "none; keys_sha256 is unchanged",
            }
        ],
        "scope": {
            "families": 6,
            "cases": len(TASKS),
            "turns_total": sum(len(t["turns"]) for t in TASKS),
            "repetitions_per_candidate": 2,
            "attempts_per_candidate": len(TASKS) * 2,
            "candidates": "open enrollment; this envelope does not cap how many "
                          "models may run it",
            "task_attempts_formula": "cases * repetitions_per_candidate * "
                                     "candidates_enrolled",
        },
        "candidates": {
            "enrollment": "open",
            "register": [],
            "rule": "Any model may be enrolled at any time and runs the identical "
                    "frozen envelope. The envelope is the constant and the roster is "
                    "the variable. Enrolling a model later never alters conditions "
                    "for models already run, so results stay directly comparable.",
            "gate": "Dispatch must report modelApplied true for the requested model "
                    "id. A silent provider fallback invalidates the attempt. "
                    "Enrollment is not promotion and no roster enabled flag changes "
                    "here.",
            "record_per_candidate": [
                "model_id",
                "modelApplied dispatch proof",
                "run_date_utc",
                "envelope keys_sha256 the run was graded against",
            ],
            "late_entry_caveat": "Record the run date. A model released or trained "
                                 "after these fixtures were authored carries a "
                                 "contamination caveat that an earlier run does not. "
                                 "This is a reporting duty, not a reason to cap "
                                 "enrollment.",
        },
        "budgets": {
            "mode": "fixed_operational_timeout",
            "rationale": "A time budget exists to stop a hang, not to measure "
                         "capability. Cost is out of scope, so a tight budget could "
                         "only convert 'this model thinks longer' into 'this model "
                         "failed' — a latency measurement disguised as a capability "
                         "measurement, which is the exact defect that made the legacy "
                         "task sets useless.",
            "per_turn_wall_clock_s": 600,
            "why_fixed": "This number never varies by candidate. A budget derived "
                         "from any candidate's latency would change whenever a slower "
                         "model enrolled, retroactively altering conditions for "
                         "candidates already run and breaking comparability.",
            "tool_calls": "0 for every case except T4-multihop-read-recovery, which "
                          "has a hard budget of 6 fixture reads",
            "tokens": "provider default; no envelope-level cap",
            "timeout_classification": "operational_not_capability. A timeout is "
                                      "recorded as an operational outcome and "
                                      "reported separately; it is never scored as a "
                                      "factual failure.",
        },
        "isolation": {
            "candidate_visible_paths": ["prompts/", "fixtures/"],
            "candidate_forbidden_paths": ["reference/", "calibration/", "envelope.json"],
            "staging": "Candidates run against a staged copy containing prompts and "
                       "fixtures only, mounted as arena-six-inputs-20260919/.",
            "peer_responses": "never exposed to a candidate",
            "repetitions": "each repetition starts from a clean context; no carryover "
                           "between repetitions or between candidates",
            "multi_turn": "turns within one case share context by design; turn "
                          "prompts are delivered in order and never revealed early",
        },
        "grading": {
            "dimensions": ["json_valid", "format", "factual", "tools"],
            "strict_pass": "every in-scope dimension must pass; a repaired, fenced or "
                           "narrated response never passes",
            "trajectory_pass": "a multi-turn case passes strictly only when every turn "
                               "passes strictly",
            "primitives": "parse_strict_json_object and strict_value_equal, reused "
                          "unchanged from scripts/arena_harness.py",
            "keys_sha256": keys_digest,
            "keys_derivation": "every key is computed by reference/oracles.py and is "
                               "never hand-written",
        },
        "calibration": {
            "gate": "a case may not enter the freeze unless all five controls pass",
            "controls": calibration["controls_per_case"],
            "case_turns_calibrated": len(calibration["cases"]),
            "controls_total": len(calibration["cases"]) * len(calibration["controls_per_case"]),
            "status": calibration["status"],
            "artifact": "calibration/calibration.json",
        },
        "retry_policy": {
            "retries": 0,
            "rule": "preserve failures with their exact blocker; never retry until "
                    "something passes; never repair a malformed response before grading",
        },
        "stop_conditions": [
            "any fixture, key, grader or hash in this envelope changes after freeze",
            "a candidate environment is found to expose reference/ or calibration/",
            "a dispatch probe does not report modelApplied true for a nominated model",
            "grading cannot attribute a response to a delivered prompt and actual model",
        ],
        "non_goals": [
            "no automatic launch",
            "no model promotion and no roster enabled change",
            "no merging of these results into any historical leaderboard",
            "no AGI claim; the generalization family is a capability proxy only",
        ],
        "proof_required_at_launch": [
            "delivered prompt text per turn",
            "actual model id reported by the dispatch layer, not the model's self-claim",
            "raw visible response per turn",
            "tool calls and results for T4",
            "resulting files and grader output per attempt",
        ],
        "tasks": TASKS,
        "frozen_hashes": hashes,
        "known_limitations": [
            "Independent oracle review returned from one blind derivation only. The "
            "cross-model oracle was dispatched but returned blocked: that runtime had "
            "no filesystem read tool and never saw the prompts.",
            "T1 cascade1 was corrected during review; the prompt previously specified "
            "the allocation twice in non-equivalent ways.",
            "Incumbent floor is expected to be low by design; these fixtures target "
            "headroom against smarter models, not separation of the current roster.",
        ],
    }


if __name__ == "__main__":
    envelope = build()
    OUT.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": envelope["status"],
        "attempts_per_candidate": envelope["scope"]["attempts_per_candidate"],
        "turns_total": envelope["scope"]["turns_total"],
        "controls_total": envelope["calibration"]["controls_total"],
        "keys_sha256": envelope["grading"]["keys_sha256"],
        "files_hashed": len(envelope["frozen_hashes"]),
    }, indent=2))
