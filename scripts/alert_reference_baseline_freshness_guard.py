#!/usr/bin/env python3
"""Alert reference baseline freshness guard (read-only, report-only).

From 2026-09-04 to 2026-09-10 the alerts OS emitted zero actionable alerts for
six trading days while every chain stage returned rc=0 and status "ok". The
cause was conflicted provenance in reference_levels: rows split across two
distinct source_artifact_sha256 values, which trips the controller rule
"emit freshness_decay if baseline hash, quote, or level age is stale or
conflicted". A silent alerts OS was indistinguishable from a healthy one.

This guard reports four independent checks so that state cannot recur unseen:

  1. pin_age       baseline pin age against max_level_age_days
  2. provenance    distinct source_artifact_sha256 count (the outage check)
  3. pin_integrity baseline file exists, content sha matches filename and meta,
                   meta row_count matches the actual row count
  4. silent_os     recent chain runs reporting ok with no actionable state

Reporting only. The database is opened read-only; refreshing levels or bands
requires a separate owner-gated apply path outside this script.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

AUTHORITY = {
    "brokerage_or_account_action_allowed": False,
    "capital_deployment_allowed": False,
    "finance_canon_mutation_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
    "paper_or_live_execution_allowed": False,
    "read_only": True,
    "review_only": True,
    "trade_or_execution_allowed": False,
}

SCHEMA = "veritas.alert_reference_baseline_freshness_guard.v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
META_KEY = "alerts_os_reference_baseline_v1"

ACTIONABLE_STATES = ("band_entry", "near_band", "no_chase", "invalidation")
NON_ACTIONABLE_HEALTHY_STATES = ("monitor_only",)
STATUS_ORDER = {"ok": 0, "warn": 1, "critical": 2, "unknown": 2}

DEFAULT_DB = "state/finance/finance-canon.sqlite"
DEFAULT_CHAIN_RUNS = "tmp/alerts-chain-runs"
DEFAULT_OUT_JSON = "tmp/alert-reference-baseline-freshness-guard.json"
DEFAULT_OUT_MD = "tmp/alert-reference-baseline-freshness-guard.md"
DEFAULT_MAX_LEVEL_AGE_DAYS = 14.0
DEFAULT_WARN_LEAD_DAYS = 5.0
DEFAULT_RECENT_RUNS = 4
DECAY_DOMINANT_FRACTION = 0.8
# Longest legitimate gap is a holiday-extended weekend (Wed close to Mon open is
# roughly 113h), so the stop-detection threshold sits above that.
DEFAULT_MAX_CHAIN_RUN_AGE_HOURS = 120.0

SHA256_IN_NAME = re.compile(r"[0-9a-f]{64}", re.IGNORECASE)

REQUIRED_PAYLOAD_KEYS = ("schema", "generated_at_utc", "status", "checks", "authority")


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_iso_utc(value: str) -> dt.datetime:
    text = (value or "").strip()
    if not text:
        raise ValueError("empty timestamp")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = dt.datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def worst(statuses) -> str:
    result = "ok"
    for status in statuses:
        if STATUS_ORDER.get(status, 2) > STATUS_ORDER.get(result, 0):
            result = status
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(131072), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(str(tmp), str(path))


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"database not found: {db_path}")
    uri = f"file:{db_path.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def load_meta(con: sqlite3.Connection) -> dict:
    row = con.execute(
        "SELECT value FROM finance_state_meta WHERE key = ?", (META_KEY,)
    ).fetchone()
    if row is None:
        return {}
    try:
        value = json.loads(row[0])
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def check_provenance(con: sqlite3.Connection, meta: dict) -> dict:
    rows = con.execute(
        """
        SELECT source_artifact_sha256, source_artifact_path, COUNT(*) AS n
        FROM reference_levels
        GROUP BY source_artifact_sha256, source_artifact_path
        ORDER BY n DESC
        """
    ).fetchall()
    total = sum(row[2] for row in rows)
    distinct_sha = {row[0] for row in rows}

    groups = []
    for sha, path, count in rows:
        examples = [
            r[0]
            for r in con.execute(
                "SELECT ticker FROM reference_levels WHERE source_artifact_sha256 IS ? "
                "ORDER BY ticker LIMIT 5",
                (sha,),
            ).fetchall()
        ]
        groups.append(
            {
                "source_artifact_sha256": sha,
                "source_artifact_path": path,
                "row_count": count,
                "example_tickers": examples,
            }
        )

    evidence = {
        "total_rows": total,
        "distinct_sha256_count": len(distinct_sha),
        "groups": groups,
        "meta_baseline_sha256": meta.get("baseline_sha256"),
    }

    if total == 0:
        return dict(
            name="provenance",
            status="critical",
            message="reference_levels is empty; the alerts OS has no reference canon.",
            **evidence,
        )

    if len(distinct_sha) > 1:
        return dict(
            name="provenance",
            status="critical",
            message=(
                f"CONFLICTED PROVENANCE: {len(distinct_sha)} distinct source_artifact_sha256 "
                f"values across {total} rows. This is the exact condition that silenced the "
                f"alerts OS from 2026-09-04 to 2026-09-10. The controller will emit "
                f"freshness_decay on every ticker until a single pin is restored."
            ),
            **evidence,
        )

    table_sha = next(iter(distinct_sha))
    meta_sha = meta.get("baseline_sha256")
    if meta_sha and table_sha != meta_sha:
        return dict(
            name="provenance",
            status="critical",
            message=(
                f"reference_levels pin {table_sha} does not match finance_state_meta "
                f"baseline_sha256 {meta_sha}."
            ),
            **evidence,
        )

    return dict(
        name="provenance",
        status="ok",
        message=f"Single consistent pin across all {total} rows.",
        **evidence,
    )


def check_pin_age(con: sqlite3.Connection, max_age_days: float, warn_lead_days: float, now: dt.datetime) -> dict:
    rows = con.execute(
        "SELECT DISTINCT source_generated_at_utc FROM reference_levels"
    ).fetchall()
    stamps = [r[0] for r in rows if r[0]]

    if not stamps:
        return {
            "name": "pin_age",
            "status": "critical",
            "message": "No source_generated_at_utc found on reference_levels.",
            "distinct_generated_at_utc": [],
        }

    parsed = []
    for stamp in stamps:
        try:
            parsed.append(parse_iso_utc(stamp))
        except ValueError:
            pass
    if not parsed:
        return {
            "name": "pin_age",
            "status": "critical",
            "message": f"source_generated_at_utc values are unparseable: {stamps}",
            "distinct_generated_at_utc": stamps,
        }

    oldest = min(parsed)
    age_days = (now - oldest).total_seconds() / 86400.0
    expires_at = oldest + dt.timedelta(days=max_age_days)
    days_remaining = (expires_at - now).total_seconds() / 86400.0

    evidence = {
        "distinct_generated_at_utc": stamps,
        "oldest_generated_at_utc": oldest.isoformat().replace("+00:00", "Z"),
        "age_days": round(age_days, 3),
        "max_level_age_days": max_age_days,
        "warn_lead_days": warn_lead_days,
        "expires_at_utc": expires_at.isoformat().replace("+00:00", "Z"),
        "days_remaining": round(days_remaining, 3),
    }

    if age_days >= max_age_days:
        status = "critical"
        message = (
            f"Reference levels expired {abs(days_remaining):.2f} days ago "
            f"(age {age_days:.2f}d >= max {max_age_days}d). The controller will emit "
            f"freshness_decay until the baseline is refreshed through the owner-gated apply path."
        )
    elif age_days >= (max_age_days - warn_lead_days):
        status = "warn"
        message = (
            f"Reference levels expire in {days_remaining:.2f} days at "
            f"{evidence['expires_at_utc']}. Schedule an owner-gated refresh."
        )
    else:
        status = "ok"
        message = f"Reference levels fresh; {days_remaining:.2f} days remaining."

    return dict(name="pin_age", status=status, message=message, **evidence)


def check_pin_integrity(con: sqlite3.Connection, meta: dict, repo_root: Path) -> dict:
    row = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT source_artifact_path) FROM reference_levels"
    ).fetchone()
    actual_rows = row[0]
    distinct_paths = row[1]

    pin_path_text = meta.get("baseline_path") or meta.get("path")
    if not pin_path_text:
        pin_row = con.execute(
            "SELECT source_artifact_path FROM reference_levels LIMIT 1"
        ).fetchone()
        pin_path_text = pin_row[0] if pin_row else None

    evidence = {
        "meta_present": bool(meta),
        "meta_row_count": meta.get("row_count"),
        "meta_baseline_sha256": meta.get("baseline_sha256"),
        "meta_lifecycle": meta.get("lifecycle"),
        "actual_row_count": actual_rows,
        "distinct_source_artifact_path_count": distinct_paths,
        "baseline_path": pin_path_text,
    }

    if not meta:
        return dict(
            name="pin_integrity",
            status="critical",
            message=f"finance_state_meta has no row for key {META_KEY}.",
            **evidence,
        )

    if not pin_path_text:
        return dict(
            name="pin_integrity",
            status="critical",
            message="No baseline pin path recorded in meta or reference_levels.",
            **evidence,
        )

    pin_path = repo_root / pin_path_text
    evidence["baseline_file_exists"] = pin_path.exists()
    if not pin_path.exists():
        return dict(
            name="pin_integrity",
            status="critical",
            message=f"Baseline pin file is missing: {pin_path_text}",
            **evidence,
        )

    content_sha = sha256_file(pin_path)
    name_match = SHA256_IN_NAME.search(pin_path.name)
    name_sha = name_match.group(0).lower() if name_match else None
    evidence["baseline_content_sha256"] = content_sha
    evidence["baseline_filename_sha256"] = name_sha

    problems = []
    if name_sha and content_sha != name_sha:
        problems.append(
            f"content sha256 {content_sha} does not match the sha256 in its filename {name_sha}"
        )
    meta_sha = meta.get("baseline_sha256")
    if meta_sha and content_sha != meta_sha:
        problems.append(
            f"content sha256 {content_sha} does not match meta baseline_sha256 {meta_sha}"
        )
    meta_rows = meta.get("row_count")
    if isinstance(meta_rows, int) and meta_rows != actual_rows:
        problems.append(
            f"meta row_count {meta_rows} does not match actual reference_levels row count {actual_rows}"
        )

    if problems:
        return dict(
            name="pin_integrity",
            status="critical",
            message="Baseline pin integrity failed: " + "; ".join(problems),
            problems=problems,
            **evidence,
        )

    return dict(
        name="pin_integrity",
        status="ok",
        message=(
            f"Baseline pin intact: content-addressed sha matches filename and meta, "
            f"{actual_rows} rows."
        ),
        problems=[],
        **evidence,
    )


def extract_state_counts(run: dict) -> tuple[dict, str]:
    """Return (counts, path_used). Primary path is verified against the real schema."""
    summary = run.get("summary")
    if isinstance(summary, dict):
        coherence = summary.get("digest_source_coherence")
        if isinstance(coherence, dict):
            counts = coherence.get("alert_state_counts")
            if isinstance(counts, dict):
                return counts, "summary.digest_source_coherence.alert_state_counts"

    for key in ("alert_state_counts", "state_counts"):
        counts = run.get(key)
        if isinstance(counts, dict):
            return counts, key
        if isinstance(summary, dict) and isinstance(summary.get(key), dict):
            return summary[key], f"summary.{key}"

    return {}, ""


def load_chain_runs(chain_dir: Path) -> tuple[list, list]:
    parsed, unparseable = [], []
    if not chain_dir.is_dir():
        return parsed, unparseable

    for path in sorted(chain_dir.glob("*.json")):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            unparseable.append({"file": rel(path), "reason": f"unreadable: {exc}"})
            continue
        if not isinstance(run, dict):
            unparseable.append({"file": rel(path), "reason": "not a JSON object"})
            continue
        stamp = run.get("generated_at_utc")
        if not stamp:
            unparseable.append({"file": rel(path), "reason": "missing generated_at_utc"})
            continue
        try:
            when = parse_iso_utc(stamp)
        except ValueError:
            unparseable.append({"file": rel(path), "reason": f"bad generated_at_utc {stamp!r}"})
            continue
        counts, counts_path = extract_state_counts(run)
        if not counts:
            unparseable.append({"file": rel(path), "reason": "no alert_state_counts found"})
            continue
        parsed.append(
            {
                "file": rel(path),
                "generated_at_utc": when.isoformat().replace("+00:00", "Z"),
                "_sort": when,
                "status": run.get("status") or run.get("chain_status"),
                "alert_state_counts": counts,
                "counts_path": counts_path,
            }
        )

    # Filenames do NOT sort chronologically: "weekly-" sorts after "post-close-".
    parsed.sort(key=lambda item: item["_sort"])
    for item in parsed:
        item.pop("_sort", None)
    return parsed, unparseable


def check_silent_os(
    chain_dir: Path,
    recent_runs: int,
    now: dt.datetime | None = None,
    max_run_age_hours: float = DEFAULT_MAX_CHAIN_RUN_AGE_HOURS,
) -> dict:
    now = now or utcnow()
    parsed, unparseable = load_chain_runs(chain_dir)
    window = parsed[-recent_runs:] if recent_runs > 0 else []

    evidence = {
        "chain_runs_dir": rel(chain_dir),
        "recent_runs_requested": recent_runs,
        "parsed_run_count": len(parsed),
        "unparseable": unparseable[-10:],
        "unparseable_count": len(unparseable),
        "max_chain_run_age_hours": max_run_age_hours,
        "window": [],
    }

    if not window:
        return dict(
            name="silent_os",
            status="unknown",
            message=f"No parseable chain runs found under {rel(chain_dir)}.",
            newest_run_generated_at_utc=None,
            newest_run_age_hours=None,
            **evidence,
        )

    newest = parse_iso_utc(window[-1]["generated_at_utc"])
    newest_age_hours = (now - newest).total_seconds() / 3600.0
    evidence["newest_run_generated_at_utc"] = window[-1]["generated_at_utc"]
    evidence["newest_run_age_hours"] = round(newest_age_hours, 2)

    # A writer that stopped emitting runs is the purest silent-OS failure: the
    # stale files still parse and still look healthy.
    if newest_age_hours > max_run_age_hours:
        return dict(
            name="silent_os",
            status="warn",
            message=(
                f"Newest chain run is {newest_age_hours:.1f}h old "
                f"({window[-1]['generated_at_utc']}), beyond the {max_run_age_hours}h "
                f"threshold. The alerts chain may have stopped producing runs entirely; "
                f"the remaining files still parse and still look healthy."
            ),
            **evidence,
        )

    silent_candidates = []
    decay_dominant = []
    for run in window:
        counts = run["alert_state_counts"]
        total = sum(v for v in counts.values() if isinstance(v, (int, float)))
        actionable = sum(
            counts.get(state, 0) for state in ACTIONABLE_STATES
        )
        healthy_idle = any(counts.get(state) for state in NON_ACTIONABLE_HEALTHY_STATES)
        decay = counts.get("freshness_decay", 0)
        is_decay_dominant = bool(total) and (decay / total) >= DECAY_DOMINANT_FRACTION

        entry = {
            "file": run["file"],
            "generated_at_utc": run["generated_at_utc"],
            "status": run["status"],
            "counts_path": run["counts_path"],
            "alert_state_counts": counts,
            "actionable_count": actionable,
            "closed_market_monitor_only": healthy_idle,
            "freshness_decay_dominant": is_decay_dominant,
        }
        evidence["window"].append(entry)

        if is_decay_dominant:
            decay_dominant.append(entry)

        status_ok = str(run["status"] or "").lower() in ("ok", "success", "passed")
        # monitor_only is the correct closed-market state and must not count as silent.
        if status_ok and actionable == 0 and not healthy_idle:
            silent_candidates.append(entry)

    evidence["freshness_decay_dominant_runs"] = [e["file"] for e in decay_dominant]
    evidence["silent_run_count"] = len(silent_candidates)

    if silent_candidates and len(silent_candidates) == len(window):
        return dict(
            name="silent_os",
            status="warn",
            message=(
                f"All {len(window)} most recent chain runs reported ok but produced no "
                f"actionable alert state and no closed-market monitor_only state. This is the "
                f"fingerprint of a silently non-functioning alerts OS. Check provenance and "
                f"pin_age above before trusting the green status."
            ),
            **evidence,
        )

    if decay_dominant and len(decay_dominant) == len(window):
        return dict(
            name="silent_os",
            status="warn",
            message=(
                f"All {len(window)} most recent chain runs are freshness_decay dominant. "
                f"The alerts OS is reporting ok while emitting no usable signal."
            ),
            **evidence,
        )

    note = ""
    if decay_dominant:
        note = (
            f" Note: {len(decay_dominant)} run(s) in the window are freshness_decay dominant "
            f"but sit inside an otherwise healthy window."
        )
    return dict(
        name="silent_os",
        status="ok",
        message=f"Recent chain runs show a live alerts OS.{note}",
        **evidence,
    )


def build_payload(args, now: dt.datetime) -> dict:
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = REPO_ROOT / db_path
    chain_dir = Path(args.chain_runs_dir)
    if not chain_dir.is_absolute():
        chain_dir = REPO_ROOT / chain_dir

    con = connect_readonly(db_path)
    try:
        meta = load_meta(con)
        checks = [
            check_pin_age(con, args.max_level_age_days, args.warn_lead_days, now),
            check_provenance(con, meta),
            check_pin_integrity(con, meta, REPO_ROOT),
            check_silent_os(
                chain_dir,
                args.recent_runs,
                now,
                args.max_chain_run_age_hours,
            ),
        ]
    finally:
        con.close()

    overall = worst(check["status"] for check in checks)
    critical = [c["name"] for c in checks if c["status"] == "critical"]
    warnings = [c["name"] for c in checks if c["status"] == "warn"]

    if critical:
        headline = f"CRITICAL: {', '.join(critical)}"
    elif warnings:
        headline = f"WARNING: {', '.join(warnings)}"
    else:
        headline = "Alert reference baseline healthy."

    return {
        "schema": SCHEMA,
        "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
        "status": overall,
        "headline": headline,
        "critical_checks": critical,
        "warning_checks": warnings,
        "database": rel(db_path),
        "checks": checks,
        "authority": dict(AUTHORITY),
    }


def render_markdown(payload: dict) -> str:
    lines = [
        "# Alert Reference Baseline Freshness Guard",
        "",
        f"- Status: **{payload['status']}**",
        f"- Generated: {payload['generated_at_utc']}",
        f"- Database: `{payload['database']}`",
        f"- {payload['headline']}",
        "",
        "| Check | Status | Message |",
        "| --- | --- | --- |",
    ]
    for check in payload["checks"]:
        message = str(check.get("message", "")).replace("|", "\\|")
        lines.append(f"| {check['name']} | {check['status']} | {message} |")
    lines += [
        "",
        "Read-only guard. Reports only; refreshing reference levels requires the",
        "owner-gated apply path. No capital, order, account, or execution authority.",
        "",
    ]
    return "\n".join(lines)


def validate_payload(payload: dict) -> list:
    errors = []
    for key in REQUIRED_PAYLOAD_KEYS:
        if key not in payload:
            errors.append(f"missing key: {key}")
    if payload.get("status") not in ("ok", "warn", "critical"):
        errors.append(f"invalid status: {payload.get('status')!r}")
    checks = payload.get("checks")
    if not isinstance(checks, list) or len(checks) != 4:
        errors.append("expected exactly 4 checks")
    else:
        expected = {"pin_age", "provenance", "pin_integrity", "silent_os"}
        found = {c.get("name") for c in checks}
        if found != expected:
            errors.append(f"check names {sorted(found)} != {sorted(expected)}")
    authority = payload.get("authority") or {}
    if authority.get("read_only") is not True:
        errors.append("authority.read_only must be True")
    for key in (
        "capital_deployment_allowed",
        "trade_or_execution_allowed",
        "finance_canon_mutation_allowed",
        "owner_approval_inferred",
    ):
        if authority.get(key) is not False:
            errors.append(f"authority.{key} must be False")
    return errors


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--chain-runs-dir", default=DEFAULT_CHAIN_RUNS)
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    parser.add_argument("--out-md", default=DEFAULT_OUT_MD)
    parser.add_argument("--max-level-age-days", type=float, default=DEFAULT_MAX_LEVEL_AGE_DAYS)
    parser.add_argument("--warn-lead-days", type=float, default=DEFAULT_WARN_LEAD_DAYS)
    parser.add_argument("--recent-runs", type=int, default=DEFAULT_RECENT_RUNS)
    parser.add_argument(
        "--max-chain-run-age-hours",
        type=float,
        default=DEFAULT_MAX_CHAIN_RUN_AGE_HOURS,
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json", action="store_true", help="print payload to stdout")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    payload = build_payload(args, utcnow())

    out_json = Path(args.out_json)
    if not out_json.is_absolute():
        out_json = REPO_ROOT / out_json

    if args.write:
        atomic_write(out_json, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if args.write_md:
        out_md = Path(args.out_md)
        if not out_md.is_absolute():
            out_md = REPO_ROOT / out_md
        atomic_write(out_md, render_markdown(payload))

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"[{payload['status']}] {payload['headline']}")
        for check in payload["checks"]:
            print(f"  - {check['name']}: {check['status']} - {check['message']}")

    if args.validate:
        target = payload
        if args.write:
            target = json.loads(out_json.read_text(encoding="utf-8"))
        errors = validate_payload(target)
        if errors:
            for err in errors:
                print(f"VALIDATION ERROR: {err}", file=sys.stderr)
            return 3

    # A critical finding is a successful report, not a run failure.
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
