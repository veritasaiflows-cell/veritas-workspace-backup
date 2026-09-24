"""Weekly fundamentals refresh and thesis review flags for the evaluated scope.

Owner-approved 2026-09-23 (Randall: "Proceed with next steps as recommended").
1. Refresh review-only fundamentals for every name in the live controller
   scope (so Phase 4 rotation is followed automatically).
2. Validate thesis records and flag, per name in scope:
   - missing_thesis: no accepted thesis (monitor-only; draft needed)
   - review_overdue: accepted thesis past review_due
   - new_quarter: fundamentals report a fiscal quarter newer than the one
     the thesis was written against (fundamentals_period_end)
   - invalid: the record fails validation
3. Refresh the recommendation funnel (tmp/recommendation-funnel.json).
Writes tmp/thesis-review.json. Never edits theses or canon; Main surfaces the
flags to Randall and drafts updates for his acceptance.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable

import thesis_record_validator as validator

CONTROLLER_REL = "tmp/alert-level-freshness-controller.json"
FUNDAMENTALS_REL = "tmp/fundamental-metrics-current.json"
REVIEW_REL = "tmp/thesis-review.json"

Runner = Callable[[list[str], Path], subprocess.CompletedProcess]


def default_runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, timeout=1500)


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def build_review(root: Path, today: date | None = None) -> dict:
    scope = sorted({r.get("ticker") for r in load(root / CONTROLLER_REL).get("rows") or [] if r.get("ticker")})
    fundamentals = {r["ticker"]: r for r in load(root / FUNDAMENTALS_REL).get("rows") or [] if r.get("ticker")}
    validation = validator.validate_dir(root, today=today)
    records = {r["ticker"]: r for r in validation["results"]}
    thesis_dir = root / validator.THESIS_REL
    flags: dict[str, list[str]] = {}
    for ticker in scope:
        result = records.get(ticker)
        f: list[str] = []
        if result is None or result.get("status") != "accepted":
            f.append("missing_thesis")
        else:
            if not result["valid"]:
                f.append("invalid")
            if result.get("review_overdue"):
                f.append("review_overdue")
            record = load(thesis_dir / f"{ticker}.json")
            seen = record.get("fundamentals_period_end")
            latest = (fundamentals.get(ticker) or {}).get("period_end")
            if latest and (not seen or str(latest) > str(seen)):
                f.append("new_quarter")
        if f:
            flags[ticker] = f
    return {
        "schema": "veritas.thesis_review.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope_count": len(scope),
        "eligible": sorted(t for t in scope if t in validation["eligible"]),
        "flags": flags,
        "counts": {k: sum(1 for v in flags.values() if k in v)
                   for k in ("missing_thesis", "review_overdue", "new_quarter", "invalid")},
        "status": "error" if not scope else "attention" if any(
            k in v for v in flags.values() for k in ("review_overdue", "new_quarter", "invalid")) else "ok",
        "authority": {"thesis_edit": False, "canon_write": False, "owner_approval_inferred": False},
    }


def run(root: Path, *, python: str, refresh: bool = True, runner: Runner = default_runner) -> dict:
    steps = {}
    scope = sorted({r.get("ticker") for r in load(root / CONTROLLER_REL).get("rows") or [] if r.get("ticker")})
    if refresh and scope:
        res = runner([python, "scripts/fundamental_metrics_refresh.py", "--tickers", *scope, "--merge-existing"], root)
        steps["fundamentals_refresh"] = {"rc": res.returncode, "tail": (res.stdout or res.stderr)[-400:]}
    review = build_review(root)
    # Recommendation funnel refresh (owner-approved weekly recommendation review).
    fun = runner([python, "scripts/recommendation_funnel.py", "--write"], root)
    steps["recommendation_funnel"] = {"rc": fun.returncode, "tail": (fun.stdout or fun.stderr)[-400:]}
    review["steps"] = steps
    if steps.get("fundamentals_refresh", {}).get("rc", 0) != 0:
        review["status"] = "error"
    (root / REVIEW_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / REVIEW_REL).write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    return review


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Weekly fundamentals refresh + thesis review flags.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--no-refresh", action="store_true")
    args = ap.parse_args(argv)
    review = run(Path(args.root), python=args.python, refresh=not args.no_refresh)
    print(json.dumps({k: review[k] for k in ("status", "scope_count", "eligible", "counts")}, indent=2))
    return 1 if review["status"] == "error" else 0


if __name__ == "__main__":
    sys.exit(main())
