"""Run-scoped deterministic grader for Surface A raw transport responses."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

RUN = Path(__file__).resolve().parent
ARENA = RUN.parents[1]
sys.path.insert(0, str(ARENA / "reference"))
from grader import grade, grade_trajectory  # noqa: E402


def turn_key(case_id: str, turn: int, keys: dict[str, Any]) -> Any:
    case_key = keys[case_id]
    if case_id in {"T2-event-revert-ambiguity", "T5-handoff-authority-control"}:
        return case_key[f"turn{turn}"]
    return case_key


def main() -> int:
    envelope = json.loads((ARENA / "envelope.json").read_text(encoding="utf-8"))
    keys = json.loads((ARENA / "reference" / "keys.json").read_text(encoding="utf-8"))
    responses = json.loads((RUN / "A-responses.json").read_text(encoding="utf-8"))
    task_map = {task["id"]: task for task in envelope["tasks"]}
    turn_grades: list[dict[str, Any]] = []
    trajectory_grades: list[dict[str, Any]] = []
    operational_notes: list[str] = []
    for trajectory in responses["trajectories"]:
        case_id = trajectory["case"]
        rep = int(trajectory["rep"])
        task = task_map[case_id]
        expected_turns = len(task["turns"])
        turns_by_number = {int(row["turn"]): row for row in trajectory.get("turns", [])}
        per_turn: list[dict[str, Any]] = []
        for number in range(1, expected_turns + 1):
            row = turns_by_number.get(number)
            if row is None:
                result = {
                    "case": case_id, "json_valid": False, "parse_error": "missing_response",
                    "format": False, "factual": False, "tools": None,
                    "tool_findings": [], "strict_pass": False,
                }
                status = "missing"
                tool_violation = False
            else:
                result = grade(
                    case_id, row.get("response_text", ""), turn_key(case_id, number, keys),
                    tool_trace=trajectory.get("tool_trace", []),
                    expected_trace=task.get("expected_trace"),
                    forbidden_reads=task.get("forbidden_reads", ()),
                )
                status = row.get("operational_status")
                tool_violation = bool((row.get("transport") or {}).get("tool_violation"))
                if tool_violation:
                    result["tool_findings"] = list(result.get("tool_findings") or []) + ["unexpected_tool_call"]
                    result["tools"] = False
                    result["strict_pass"] = False
            result["identity"] = {
                "model_slot": "opus55-fullchain", "requested_model": responses["model"],
                "case": case_id, "repetition": rep, "turn": number,
            }
            result["operational_eligible"] = status == "ok"
            result["operational_status"] = status
            result["transport_valid"] = status == "ok"
            per_turn.append(result)
            turn_grades.append(result)
        trajectory_result = grade_trajectory(case_id, per_turn)
        trajectory_result["identity"] = {"case": case_id, "repetition": rep}
        trajectory_result["operational_eligible"] = all(t["operational_eligible"] for t in per_turn)
        trajectory_result["operational_status"] = trajectory.get("operational_status")
        trajectory_grades.append(trajectory_result)
        if not trajectory_result["operational_eligible"]:
            operational_notes.append(f"{case_id}-r{rep}:{trajectory_result['operational_status']}")
    eligible_turns = [turn for turn in turn_grades if turn["operational_eligible"]]
    eligible_trajectories = [row for row in trajectory_grades if row["operational_eligible"]]
    scored = {
        "planned_trajectories": len(trajectory_grades),
        "eligible_trajectories": len(eligible_trajectories),
        "strict_trajectories": sum(row["strict_pass"] for row in eligible_trajectories),
        "planned_turns": len(turn_grades),
        "eligible_turns": len(eligible_turns),
        "factual_turns": sum(turn["factual"] for turn in eligible_turns),
        "format_turns": sum(turn["format"] for turn in eligible_turns),
        "strict_turns": sum(turn["strict_pass"] for turn in eligible_turns),
        "operational_exclusions": operational_notes,
    }
    (RUN / "turns-graded.json").write_text(
        json.dumps({"turn_grades": turn_grades, "trajectory_grades": trajectory_grades, "summary": scored}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (RUN / "operational-adjudication.json").write_text(
        json.dumps({
            "planned_trajectories": scored["planned_trajectories"],
            "eligible_trajectories": scored["eligible_trajectories"],
            "planned_turns": scored["planned_turns"],
            "eligible_turns": scored["eligible_turns"],
            "operational_status": "all ok" if not operational_notes else "operational exclusions",
            "notes": operational_notes,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(scored, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
