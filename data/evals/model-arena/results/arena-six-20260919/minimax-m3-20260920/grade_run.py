"""Grade MiniMax M3 arena-six transports with the frozen grader."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = Path(r"C:\Users\Veritas\.openclaw\workspace")
REF = ROOT / "data/evals/model-arena/arena-six-20260919/reference"
sys.path.insert(0, str(REF))
from grader import grade, grade_trajectory  # noqa: E402

KEYS = json.loads((REF / "keys.json").read_text(encoding="utf-8"))
T4_TRACE = [
    "arena-six-inputs-20260919/recovery/primary.json",
    "arena-six-inputs-20260919/recovery/index.json",
    "arena-six-inputs-20260919/recovery/payload-a.json",
    "arena-six-inputs-20260919/recovery/mirror/payload-b.json",
]
T4_FORBIDDEN = ["arena-six-inputs-20260919/recovery/archive/old-payload.json"]
CASES = [
    ("T1-settlement-cascade", 1),
    ("T2-event-revert-ambiguity", 4),
    ("T3-evidence-retraction-chain", 1),
    ("T4-multihop-read-recovery", 1),
    ("T5-handoff-authority-control", 2),
    ("T6-induction-and-planning", 1),
]


def extract_text(path: Path) -> tuple[str, str, str | None]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if not raw.strip():
        return "", "empty", None
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        return raw, "json_error", None
    payloads = ((doc.get("result") or {}).get("payloads") or [])
    text = payloads[0].get("text") if payloads else ""
    meta = ((doc.get("result") or {}).get("meta") or {})
    am = meta.get("agentMeta") or {}
    rec = am.get("terminalReceipt") or {}
    eff = rec.get("effective") or {}
    model = eff.get("model") or am.get("model")
    status = "ok" if doc.get("status") == "ok" else str(doc.get("status"))
    return text or "", status, model


def key_for(case: str, turn: int):
    blob = KEYS[case]
    turn_key = f"turn{turn}"
    if isinstance(blob, dict) and turn_key in blob:
        return blob[turn_key]
    return blob


def main() -> int:
    turn_grades = []
    trajs = []
    for case, nturns in CASES:
        for rep in (1, 2):
            turn_results = []
            eligible = True
            for turn in range(1, nturns + 1):
                identity = {
                    "model_slot": "minimax-m3",
                    "requested_model": "ollama-cloud/minimax-m3:cloud",
                    "case": case,
                    "repetition": rep,
                    "turn": turn,
                }
                if case == "T4-multihop-read-recovery":
                    t4 = json.loads((RUN / f"t4-r{rep}-response.json").read_text(encoding="utf-8"))
                    text = t4["text"]
                    status = "ok"
                    model = t4.get("model")
                    g = grade(
                        case,
                        text,
                        key_for(case, turn),
                        tool_trace=T4_TRACE,
                        expected_trace=T4_TRACE,
                        forbidden_reads=T4_FORBIDDEN,
                    )
                elif case == "T6-induction-and-planning":
                    path = RUN / f"transport-{case}-r{rep}-t{turn}.json"
                    if not path.exists():
                        row = {
                            "identity": identity,
                            "operational_eligible": False,
                            "operational_status": "timeout",
                            "grader": None,
                            "capability_dimensions": {
                                "factual": None,
                                "format": None,
                                "tools": None,
                            },
                            "combined_strict_pass": False,
                        }
                        turn_grades.append(row)
                        eligible = False
                        continue
                    text, status, model = extract_text(path)
                    g = grade(case, text, key_for(case, turn))
                else:
                    path = RUN / f"transport-{case}-r{rep}-t{turn}.json"
                    text, status, model = extract_text(path)
                    g = grade(case, text, key_for(case, turn))
                identity["observed_model"] = model
                row = {
                    "identity": identity,
                    "operational_eligible": status == "ok",
                    "operational_status": status,
                    "grader": g,
                    "capability_dimensions": {
                        "factual": g["factual"] if status == "ok" else None,
                        "format": g["format"] if status == "ok" else None,
                        "tools": g.get("tools"),
                    },
                    "combined_strict_pass": bool(status == "ok" and g["strict_pass"]),
                }
                turn_grades.append(row)
                turn_results.append(g)
            if eligible and turn_results:
                trajs.append(grade_trajectory(case, turn_results) | {"repetition": rep})
            else:
                trajs.append({
                    "case": case,
                    "repetition": rep,
                    "strict_pass": False,
                    "operational_timeout": case.startswith("T6"),
                })
    planned = 12
    strict = sum(1 for t in trajs if t.get("strict_pass"))
    report = {
        "schema": "veritas.arena_six_candidate_graded_results.v1",
        "envelope_id": "arena-six-20260919",
        "model": "ollama-cloud/minimax-m3:cloud",
        "planned_trajectories": planned,
        "strict_pass_count": strict,
        "strict_pass_ratio": f"{strict}/{planned}",
        "trajectories": trajs,
        "turn_grades": turn_grades,
        "limits": [
            "T6 both reps recorded operational timeout (subprocess 630s); not retried",
            "T4 traces reconstructed from session reads; archive not read",
            "CLI lab route for non-T4; T4 used isolated MiniMax spawn with staged fixtures",
        ],
    }
    (RUN / "graded-results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "strict": f"{strict}/{planned}",
        "traj": [
            {"case": t.get("case"), "rep": t.get("repetition"), "strict": t.get("strict_pass"), "timeout": t.get("operational_timeout")}
            for t in trajs
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
