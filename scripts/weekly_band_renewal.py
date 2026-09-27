"""Weekly reference-band renewal under the Option B standing permission.

Owner decision: Randall, Telegram 2026-09-23 ~18:30 MST, "Proceed with
recommendations and option b as a standing permission as proposed."
Standing gate record: state/finance/standing-approvals/band-renewal-option-b.json.

Steps (all paths from ``--root`` at call time):
1. Find the last completed session from Yahoo's SPY daily bars (holiday-safe).
2. Recompute the evaluated-scope matrix (Yahoo-only, repair overlay honoured).
3. Dry-run the gated canon apply against live canon (no mutation).
4. Evaluate the standing gate. Auto-apply only when every condition holds:
   no blocked name, zero invalidation-ordering warnings, dry run clean
   (drift 0, no mutation), and no band edge moving more than 5% for any name.
   Anything else stops and is surfaced for owner review.
5. With ``--apply-if-gated`` and a passing gate: apply with backup, rollback
   record and successor pin in state/finance/baselines, then run the baseline
   freshness guard.
6. Write the review packet (tmp/) and a durable audit record
   (state/finance/renewal-audit/) for every run, applied or not.

Grants nothing beyond that gate: no thesis, capital, order, account,
execution, or delivery authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

GATE_REL = "state/finance/standing-approvals/band-renewal-option-b.json"
AUDIT_DIR_REL = "state/finance/renewal-audit"
PACKET_REL = "tmp/weekly-band-renewal.json"
PACKET_MD_REL = "tmp/weekly-band-renewal.md"
DB_REL = "state/finance/finance-canon.sqlite"
BASELINE_DIR_REL = "state/finance/baselines"
CONTROLLER_REL = "tmp/alert-level-freshness-controller.json"
MAX_EDGE_MOVE = 0.05
NY = ZoneInfo("America/New_York")
SPY_URL = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?interval=1d&range=10d"

Runner = Callable[[list[str], Path], subprocess.CompletedProcess]


def default_runner(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, timeout=900)


def last_completed_session(http_get: Callable[[str], bytes] | None = None, now: datetime | None = None) -> str:
    """Latest SPY daily bar with a close, strictly before today if the session may still be open."""
    raw = (http_get or (lambda u: urlopen(Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=25).read()))(SPY_URL)
    result = json.loads(raw)["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    now_ny = (now or datetime.now(timezone.utc)).astimezone(NY)
    days = []
    for ts, close in zip(result["timestamp"], closes):
        day = datetime.fromtimestamp(int(ts), tz=NY).date()
        if close is None or (day == now_ny.date() and now_ny.hour < 17):
            continue
        days.append(day)
    if not days:
        raise ValueError("no completed SPY session found")
    return max(days).isoformat()


def evaluate_gate(matrix: dict, dryrun: dict | None) -> dict[str, Any]:
    reasons: list[str] = []
    rows = matrix.get("tickers") or {}
    blocked = sorted(t for t, r in rows.items() if r.get("classification") == "blocked")
    ordering = sorted(t for t, r in rows.items() if r.get("invalidation_ordering_warning"))
    moves: dict[str, dict[str, float]] = {}
    over: list[str] = []
    widened, repaired = [], {}
    for t, r in sorted(rows.items()):
        otp = r.get("old_to_proposed") or {}
        old, new = otp.get("old") or {}, otp.get("proposed") or {}
        if new.get("band_floor_applied"):
            widened.append(t)
        if r.get("repaired_session_dates"):
            repaired[t] = r["repaired_session_dates"]
        if not old or not new:
            continue
        move = {}
        raw_move = {}
        for f in ("reference_price_low", "reference_price_high", "reference_invalidation_level"):
            if old.get(f):
                raw = (new[f] - old[f]) / old[f]
                raw_move[f] = raw
                move[f] = round(raw, 4)
        moves[t] = move
        if any(abs(v) > MAX_EDGE_MOVE for v in raw_move.values()):
            over.append(t)
    if blocked:
        reasons.append(f"blocked names: {blocked}")
    if ordering:
        reasons.append(f"invalidation ordering warnings: {ordering}")
    if over:
        reasons.append(f"band edge moved more than {MAX_EDGE_MOVE:.0%}: {over}")
    if not rows:
        reasons.append("empty matrix")
    if dryrun is None:
        reasons.append("dry run failed")
    else:
        if dryrun.get("drift") != 0 or dryrun.get("no_mutation") is not True:
            reasons.append("dry run reported drift or mutation")
    return {"passed": not reasons, "reasons": reasons, "blocked": blocked, "ordering_warnings": ordering,
            "moved_over_limit": over, "floor_widened": widened, "repaired": repaired, "edge_moves": moves}


def _prior_applied_names(root: Path, current_session: str) -> tuple[str | None, list[str], str | None]:
    audit_dir = root / AUDIT_DIR_REL
    candidates = []
    for path in audit_dir.glob("*-applied.json"):
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})-applied\.json", path.name)
        if not match:
            continue
        # Any entry named like an applied record must be a real, dated record.
        # Skipping it would silently compare against an older renewal instead
        # (QA 2026-09-27 PRIOR_AUDIT_NONREGULAR_STALE_FALLBACK), so stop instead.
        try:
            date.fromisoformat(match.group(1))
        except ValueError:
            return None, [], f"applied audit record is invalid: {path.name}: not a calendar date"
        if path.is_symlink() or not path.is_file() or path.resolve().parent != audit_dir.resolve():
            return None, [], f"applied audit record is invalid: {path.name}: not a regular file in the audit directory"
        candidates.append((match.group(1), path))
    if not candidates:
        return None, [], None
    session, path = max(candidates, key=lambda entry: entry[0])
    prefix = f"newest applied audit record is invalid: {path.name}: "
    if session > current_session:
        return None, [], prefix + "future-dated session"
    try:
        prior = json.loads(path.read_bytes())
        if not isinstance(prior, dict):
            raise ValueError("record is not an object")
        if prior.get("applied") is not True or prior.get("status") != "applied":
            raise ValueError("applied/status fields disagree with applied record")
        if prior.get("session") != session:
            raise ValueError("session differs from filename")
        scope = prior.get("scope")
        if isinstance(scope, dict) and "tickers" in scope:
            names = scope["tickers"]
            if not isinstance(names, list):
                raise ValueError("scope.tickers is not a list")
        else:
            gate = prior.get("gate")
            moves = gate.get("edge_moves") if isinstance(gate, dict) else None
            if not isinstance(moves, dict):
                raise ValueError("gate.edge_moves is not a dict")
            names = sorted(moves)
        if not names or any(not isinstance(t, str) or not t for t in names) or len(names) != len(set(names)):
            raise ValueError("names must be unique non-empty strings")
        return session, sorted(names), None
    except (OSError, ValueError, TypeError) as exc:
        return None, [], prefix + str(exc)


def _matrix_scope(matrix: dict) -> dict | None:
    scope = matrix.get("scope")
    if not isinstance(scope, dict):
        return None
    names = scope.get("tickers")
    fingerprint = scope.get("fingerprint")
    if (not isinstance(names, list) or not names or
        any(not isinstance(t, str) or not t for t in names) or names != sorted(set(names)) or
        not isinstance(fingerprint, str) or not fingerprint.strip() or
        type(scope.get("count")) is not int or scope["count"] != len(names) or
        not isinstance(scope.get("tier_breakdown"), dict) or
        not isinstance(matrix.get("tickers"), dict) or sorted(matrix["tickers"]) != names):
        return None
    return scope


def _live_scope_fingerprint(root: Path, resolver) -> str:
    if resolver is None:
        from yahoo_reference_level_matrix import resolve_band_scope
        resolver = resolve_band_scope
    live = resolver(root / DB_REL, workspace_root=root.resolve())
    fingerprint = live["scope"]["fingerprint"]
    if not isinstance(fingerprint, str) or not fingerprint:
        raise ValueError("live scope has no fingerprint")
    return fingerprint


def run(root: Path, *, python: str, apply_if_gated: bool, session: str | None = None,
        runner: Runner = default_runner, http_get=None, now: datetime | None = None,
        scope_resolver=None) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    gate_record = json.loads((root / GATE_REL).read_text(encoding="utf-8"))
    session = session or last_completed_session(http_get, now)
    as_of = (date.fromisoformat(session) + timedelta(days=1)).isoformat()
    stem = f"weekly-renewal-{session}"
    matrix_rel, md_rel, dry_rel = f"tmp/{stem}-matrix.json", f"tmp/{stem}-matrix.md", f"tmp/{stem}-dryrun.json"
    packet: dict[str, Any] = {"schema": "veritas.weekly_band_renewal.v1", "started_at_utc": started,
                              "session": session, "standing_gate": GATE_REL, "gate_active": bool(gate_record.get("active")),
                              "matrix": matrix_rel, "dryrun": dry_rel, "applied": False, "steps": {}}
    gen = runner([python, "scripts/yahoo_reference_level_matrix.py", "--as-of-date", as_of,
                  "--expected-session-date", session, "--json-output", matrix_rel,
                  "--markdown-output", md_rel, "--write"], root)
    packet["steps"]["matrix"] = {"rc": gen.returncode, "tail": (gen.stdout or gen.stderr)[-400:]}
    matrix_sha = None
    try:
        if gen.returncode == 0:
            raw = (root / matrix_rel).read_bytes()
            matrix = json.loads(raw)
            matrix_sha = hashlib.sha256(raw).hexdigest()
        else:
            matrix = {}
    except (OSError, ValueError):
        matrix = {}
    packet["matrix_sha256"] = matrix_sha
    if not isinstance(matrix, dict) or not isinstance(matrix.get("tickers", {}), dict):
        matrix = {}
    scope = _matrix_scope(matrix)
    scope_reasons = []
    if scope is None:
        scope_reasons.append("matrix carries no scope block")
    prior_session, prior_names, prior_error = _prior_applied_names(root, session)
    if prior_error:
        scope_reasons.append(prior_error)
    elif not prior_names:
        scope_reasons.append("no readable prior applied renewal to compare the name list")
    current_names = scope["tickers"] if scope else []
    added = sorted(set(current_names) - set(prior_names)) if scope and prior_names else []
    removed = sorted(set(prior_names) - set(current_names)) if scope and prior_names else []
    if scope and prior_names and current_names != prior_names:
        scope_reasons.append(f"name list changed since last applied renewal ({prior_session}): added {added}, removed {removed}")
    packet["scope"] = {"tickers": current_names, "count": scope["count"] if scope else 0,
                       "fingerprint": scope["fingerprint"] if scope else None,
                       "tier_breakdown": scope["tier_breakdown"] if scope else {},
                       "prior_applied_session": prior_session, "added": added, "removed": removed}
    dryrun = None
    if scope and not scope_reasons:
        try:
            if _live_scope_fingerprint(root, scope_resolver) != scope["fingerprint"]:
                scope_reasons.append("scope changed between matrix generation and apply")
        except Exception as exc:
            scope_reasons.append(f"scope resolution failed: {exc}")
    if scope and not scope_reasons:
        dr = runner([python, "scripts/g6_yahoo32_sql_apply.py", "--dry-run", "--write", "--validate",
                     "--matrix", matrix_rel, "--db", DB_REL, "--baseline-dir", BASELINE_DIR_REL,
                     "--expected-scope-fingerprint", scope["fingerprint"],
                     "--expected-matrix-sha256", matrix_sha, "--verify-live-scope",
                     "--dryrun-path", dry_rel], root)
        packet["steps"]["dryrun"] = {"rc": dr.returncode, "tail": (dr.stdout or dr.stderr)[-400:]}
        if dr.returncode == 0:
            summary = json.loads((root / dry_rel).read_text(encoding="utf-8"))
            dryrun = {"drift": len(summary.get("old_drift_tickers") or []) + len(summary.get("missing_tickers") or []),
                      "no_mutation": summary.get("mutation_performed") is False}
    gate = evaluate_gate(matrix, dryrun)
    if scope_reasons:
        gate["passed"] = False
        gate["reasons"].extend(scope_reasons)
    if not packet["gate_active"]:
        gate["passed"] = False
        gate["reasons"].append("standing gate inactive or revoked")
    packet["gate"] = gate
    if gate["passed"] and apply_if_gated:
        try:
            if _live_scope_fingerprint(root, scope_resolver) != scope["fingerprint"]:
                gate["passed"] = False
                gate["reasons"].append("scope changed between matrix generation and apply")
        except Exception as exc:
            gate["passed"] = False
            gate["reasons"].append(f"scope resolution failed: {exc}")
        if gate["passed"]:
            ap = runner([python, "scripts/g6_yahoo32_sql_apply.py", "--apply", "--write", "--validate",
                         "--matrix", matrix_rel, "--db", DB_REL, "--baseline-dir", BASELINE_DIR_REL,
                         "--expected-scope-fingerprint", scope["fingerprint"],
                         "--expected-matrix-sha256", matrix_sha, "--verify-live-scope"], root)
            packet["steps"]["apply"] = {"rc": ap.returncode, "tail": (ap.stdout or ap.stderr)[-600:]}
            packet["applied"] = ap.returncode == 0
            guard = runner([python, "scripts/alert_reference_baseline_freshness_guard.py", "--validate"], root)
            packet["steps"]["guard"] = {"rc": guard.returncode, "tail": (guard.stdout or guard.stderr)[-600:]}
    packet["status"] = ("applied" if packet["applied"] else
                        "apply_failed" if "apply" in packet["steps"] else
                        "gate_passed_not_applied" if gate["passed"] else "needs_owner_review")
    packet["finished_at_utc"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    packet["authority"] = {"standing_gate_only": True, "thesis_change": False, "capital_or_execution": False,
                           "delivery": False, "owner_approval_inferred_beyond_gate": False}
    (root / PACKET_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / PACKET_REL).write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    (root / PACKET_MD_REL).write_text(render_md(packet), encoding="utf-8")
    audit = root / AUDIT_DIR_REL / f"{session}-{packet['status']}.json"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    return packet


def render_md(p: dict) -> str:
    g = p["gate"]
    lines = [f"# Weekly band renewal - session {p['session']}", "", f"Status: **{p['status']}**", ""]
    s = p.get("scope") or {}
    lines += [f"- Scope: {s.get('count', 0)} names; fingerprint: {(s.get('fingerprint') or '-')[:12]}",
              f"- Added: {s.get('added') or []}; removed: {s.get('removed') or []}",
              f"- Gate passed: {g['passed']}" + ("" if g["passed"] else f" ({'; '.join(g['reasons'])})"),
              f"- Floor-widened: {', '.join(g['floor_widened']) or 'none'}",
              f"- Repaired days: {', '.join(f'{t} {d}' for t, d in g['repaired'].items()) or 'none'}",
              f"- Moved over 5%: {', '.join(g['moved_over_limit']) or 'none'}", ""]
    big = sorted(((t, max(abs(v) for v in m.values())) for t, m in g["edge_moves"].items() if m), key=lambda x: -x[1])[:8]
    lines += ["Largest edge moves: " + ", ".join(f"{t} {v:.1%}" for t, v in big), ""]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Weekly band renewal under the Option B standing gate.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--python", default=sys.executable)
    ap.add_argument("--session", help="override last completed session YYYY-MM-DD")
    ap.add_argument("--apply-if-gated", action="store_true")
    args = ap.parse_args(argv)
    packet = run(Path(args.root), python=args.python, apply_if_gated=args.apply_if_gated, session=args.session)
    print(json.dumps({k: packet[k] for k in ("status", "session", "applied")} | {"reasons": packet["gate"]["reasons"]}, indent=2))
    return 1 if packet["status"] == "apply_failed" else 0


if __name__ == "__main__":
    sys.exit(main())
