import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

now = datetime.now(ZoneInfo("America/Phoenix")).isoformat()
ws = Path(r"C:\Users\Veritas\.openclaw\workspace")
r2 = ws / "data/evals/model-arena/results/arena-agentic-v1-20260920/minimax-m3-overlay-r2-20260920"
pre = ws / "data/evals/model-arena/results/arena-agentic-v1-20260920/minimax-m3-20260920"
six = ws / "data/evals/model-arena/results/arena-six-20260919/minimax-m3-20260920"
g2 = json.loads((r2 / "graded-results.json").read_text(encoding="utf-8"))
d2 = json.loads((r2 / "dimensional-rescore.json").read_text(encoding="utf-8"))
gp = json.loads((pre / "graded-results.json").read_text(encoding="utf-8"))
dp = json.loads((pre / "dimensional-rescore.json").read_text(encoding="utf-8"))
gs = json.loads((six / "graded-results.json").read_text(encoding="utf-8"))
board = {
    "schema": "veritas.arena_minimax_m3_three_envelope.v1",
    "model": "ollama-cloud/minimax-m3:cloud",
    "model_applied": True,
    "fallback_applied": False,
    "closed_at": now,
    "envelopes": {
        "arena-six-20260919": {
            "strict": gs["strict_pass_ratio"],
            "note": "T3/T4/T5 both reps pass; T1 and T2 fail both; T6 both operational timeout not retried",
        },
        "arena-agentic-v1-pre-overlay": {
            "strict": f"{gp.get('strict_pass_count')}/12",
            "json_valid": gp.get("json_valid_count"),
            "dimensional": dp.get("dimensional_score"),
            "note": "visible-only floor; not comparable to overlay-r2",
        },
        "arena-agentic-v1-overlay-r2": {
            "strict": f"{g2.get('strict_pass_count')}/12",
            "dimensional": d2.get("dimensional_score"),
            "family_scores": d2.get("family_scores"),
            "misses": ["T1 36072319", "T5 23273237"],
            "note": "not comparable to pre-overlay or arena-six",
        },
    },
    "routing_effect": "none",
    "authority": "No routing, configuration, role, or execution authority follows.",
}
(r2 / "three-envelope-board.json").write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")
(pre / "report.md").write_text(
    "# MiniMax M3 — pre-overlay hidden bank\n\n**0/12 strict**. Floor effect. Dimensional 0.0.\n",
    encoding="utf-8",
)
(r2 / "report.md").write_text(
    "# MiniMax M3 — overlay-r2\n\n**10/12 strict**, dimensional 0.889, 12/12 JSON, 0 traps.\nMisses: T1 36072319, T5 23273237. Both T6 passed.\n",
    encoding="utf-8",
)
(six / "report.md").write_text(
    "# MiniMax M3 — arena-six original\n\n**6/12 strict**. Pass both reps: T3, T4, T5. Fail both: T1, T2. T6 both operational timeout (630s), not retried.\n",
    encoding="utf-8",
)
print(json.dumps(board["envelopes"], indent=2))
