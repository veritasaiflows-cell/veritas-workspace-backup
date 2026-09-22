"""Gateway Outage Sentinel ("restart guard") - owner-directed 2026-09-18.

Detects gateway outages from missed-run gaps and classifies them against the
G8 five-session observation windows (declared 2026-09-16, restart rules in the
G8 declaration). Corroborates gaps with Windows System event-log reboot events
(41 unexpected, 1074 planned, 6005 started, 6006/6008 stopped), which are
readable from the unelevated shell (proven 2026-09-16).

Durable outage log: data/state-history/gateway-outage-log.jsonl (append-only).
State: state/gateway-outage-sentinel.json. Run artifact: tmp/gateway-outage-sentinel.json.

Exit codes: 0 = ok / overnight-risk / benign (run recorded); 1 = a gap
overlapped 06:00-13:00 Phoenix on a declared session day (voiding class;
drives the cron failure alert to the owner).

Review-only: no repair, no config mutation, no finance/canon/execution
authority, no owner-approval inference. Phoenix observes no DST, so a fixed
UTC-7 offset is correct year-round.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "state" / "gateway-outage-sentinel.json"
ARTIFACT_PATH = ROOT / "tmp" / "gateway-outage-sentinel.json"
LOG_PATH = ROOT / "data" / "state-history" / "gateway-outage-log.jsonl"

PHX = timezone(timedelta(hours=-7))
SCHEMA = "veritas.gateway_outage_sentinel.v1"

DECLARED_SESSIONS = {"2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23"}
CLOSED_MARKET_OBS = "2026-09-20"
TOLERANCE = timedelta(minutes=20)  # job cadence is 15m; >20m means a missed run
REBOOT_EVENT_IDS = {41, 1074, 6005, 6006, 6008}


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def classify_gap(start_utc: datetime, end_utc: datetime) -> tuple[str, list, list, bool]:
    """Classify a gap against G8 windows. Returns (class, voiding_days, overnight_days, obs_day_touched)."""
    s, e = start_utc.astimezone(PHX), end_utc.astimezone(PHX)
    voiding, overnight = [], []
    obs_day = False
    day = s.date()
    while day <= e.date():
        day_start = datetime.combine(day, time(0, 0), PHX)
        day_end = day_start + timedelta(days=1)
        b, en = max(day_start, s), min(day_end, e)
        if b < en:
            iso = day.isoformat()
            obs_b = day_start + timedelta(hours=6)
            obs_e = day_start + timedelta(hours=13)
            ov = min(en, obs_e) - max(b, obs_b)
            if ov > timedelta(0) and iso in DECLARED_SESSIONS:
                voiding.append({"date": iso, "observation_overlap_minutes": round(ov.total_seconds() / 60, 1)})
            if ov > timedelta(0) and iso == CLOSED_MARKET_OBS:
                obs_day = True
            on = min(en, obs_b) - b
            if on > timedelta(0):
                overnight.append({"date": iso, "overnight_overlap_minutes": round(on.total_seconds() / 60, 1)})
        day += timedelta(days=1)
    if voiding:
        return "voiding", voiding, overnight, obs_day
    if overnight:
        return "overnight_risk", voiding, overnight, obs_day
    return "benign", voiding, overnight, obs_day


def corroborate_reboots(start_utc: datetime, end_utc: datetime) -> list:
    """Best-effort Windows System event-log pull for reboot events inside the gap."""
    q = (
        "Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,1074,6005,6006,6008; "
        f"StartTime=[datetime]'{start_utc:%Y-%m-%d %H:%M:%S}'; EndTime=[datetime]'{end_utc:%Y-%m-%d %H:%M:%S}'}} "
        "-MaxEvents 10 -ErrorAction SilentlyContinue | Select-Object TimeCreated, Id, ProviderName | ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", q], capture_output=True, text=True, timeout=30)
        if out.returncode != 0 or not out.stdout.strip():
            return []
        data = json.loads(out.stdout)
        rows = data if isinstance(data, list) else [data]
        return [{"event_time_utc": r["TimeCreated"], "event_id": r["Id"], "provider": r.get("ProviderName", "")} for r in rows]
    except Exception:
        return []  # corroboration is evidence, never a gate


def append_log(row: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def run_detection() -> int:
    t = now_utc()
    state = {}
    if STATE_PATH.exists():
        state = json.load(open(STATE_PATH, encoding="utf-8"))
    last = state.get("last_seen_utc")
    gap = None
    cls, voiding, overnight, obs_day = "ok", [], [], False
    corrob = []
    if last:
        start = datetime.fromisoformat(last)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if t - start > TOLERANCE:
            gap = {"start_utc": start.isoformat(), "end_utc": t.isoformat(), "gap_minutes": round((t - start).total_seconds() / 60, 1)}
            cls, voiding, overnight, obs_day = classify_gap(start, t)
            corrob = corroborate_reboots(start, t)
            append_log({
                "schema": SCHEMA, "detected_at_utc": t.isoformat(), "gap": gap,
                "classification": cls, "voiding_days": voiding, "overnight_days": overnight,
                "closed_market_observation_day_touched": obs_day,
                "reboot_events": corrob,
            })
    state = {"schema": SCHEMA, "last_seen_utc": t.isoformat()}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    json.dump(state, open(STATE_PATH, "w", encoding="utf-8"), indent=1)
    artifact = {
        "schema": SCHEMA, "generated_at_utc": t.isoformat(), "status": "ok" if cls in ("ok", "benign", "overnight_risk") else cls,
        "last_run_classification": cls, "gap": gap, "voiding_days": voiding, "overnight_days": overnight,
        "closed_market_observation_day_touched": obs_day, "reboot_events": corrob,
        "declared_sessions": sorted(DECLARED_SESSIONS), "tolerance_minutes": int(TOLERANCE.total_seconds() / 60),
        "authority": {"review_only": True, "repair_allowed": False, "owner_approval_inferred": False},
    }
    json.dump(artifact, open(ARTIFACT_PATH, "w", encoding="utf-8"), indent=1)
    print(f"sentinel ok classification={cls} voiding={voiding} overnight={overnight}")
    if cls == "voiding":
        print("VOIDING-CLASS OUTAGE: declared-session observation window overlapped; G8 five-session count restarts.")
        return 1
    return 0


def validate() -> int:
    problems = []
    if STATE_PATH.exists():
        s = json.load(open(STATE_PATH, encoding="utf-8"))
        if s.get("schema") != SCHEMA or "last_seen_utc" not in s:
            problems.append("state file schema invalid")
    if ARTIFACT_PATH.exists():
        a = json.load(open(ARTIFACT_PATH, encoding="utf-8"))
        if a.get("schema") != SCHEMA:
            problems.append("artifact schema invalid")
    if problems:
        print("validation FAILED:", "; ".join(problems))
        return 1
    print("validation ok: sentinel state/artifact schemas present and valid")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--validate", action="store_true")
    args = ap.parse_args()
    rc = 0
    if args.write:
        rc = run_detection() or rc
    if args.validate:
        rc = validate() or rc
    return rc


if __name__ == "__main__":
    raise SystemExit(main())