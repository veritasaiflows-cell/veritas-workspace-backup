#!/usr/bin/env python3
"""Detect Skill Workshop copies shadowed by a higher-precedence skill copy.

OpenClaw loads a skill name from the highest-precedence source: workspace
`skills/` (priority 1) beats the agent Workshop directory
`agents/<id>/agent/workshop-skills` (priority 5; docs/tools/skills.md, Loading
order). Skill Workshop applies and the autonomous collection reviewer write only
the Workshop directory, so when a name exists in both places their edits never
load, and edits to the loaded copy never reach the Workshop copy. On 2026-09-25
this had silently split 12 skills (WF89).

For every configured agent this compares each Workshop skill directory with the
same-named directory in that agent's workspace `skills/`, byte-for-byte after
CRLF normalization. A differing pair is `diverged`. A diverged pair whose exact
(loaded, workshop) content hashes are recorded in the acknowledgement file is
`acknowledged` (known, with a reason); any other diverged pair is `new` and makes
`--validate` exit 1 so the daily cron raises its failure alert.

Read-only on OpenClaw config and skills. Writes only the report and, with
`acknowledge`, the acknowledgement file. Never copies, merges or deletes skills.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = Path.home() / ".openclaw"
CONFIG = STATE_DIR / "openclaw.json"
OUT = ROOT / "tmp" / "skill-shadow-check.json"
ACK = ROOT / "state" / "skill-shadow-acknowledged.json"
SCHEMA = "veritas.skill_shadow_check.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def tree_hash(root: Path) -> str:
    """Hash every file under a skill directory, CRLF-normalized, path-ordered."""
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(".") or "/." in rel:
            continue
        digest.update(rel.encode("utf-8") + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def file_delta(loaded: Path, workshop: Path) -> dict[str, list[str]]:
    def files(root: Path) -> dict[str, bytes]:
        return {
            p.relative_to(root).as_posix(): p.read_bytes().replace(b"\r\n", b"\n")
            for p in root.rglob("*") if p.is_file()
        }
    a, b = files(loaded), files(workshop)
    return {
        "changed": sorted(f for f in set(a) & set(b) if a[f] != b[f]),
        "workshop_only": sorted(set(b) - set(a)),
        "loaded_only": sorted(set(a) - set(b)),
    }


def agent_pairs(config_path: Path, state_dir: Path) -> list[dict[str, Any]]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    agents = config.get("agents") or {}
    entries = agents.get("entries") or agents.get("list") or {}
    items = entries.items() if isinstance(entries, dict) else [(e.get("id"), e) for e in entries]
    default_ws = (agents.get("defaults") or {}).get("workspace")
    pairs = []
    for agent_id, entry in items:
        if not agent_id:
            continue
        workspace = entry.get("workspace") or default_ws
        agent_dir = entry.get("agentDir") or str(state_dir / "agents" / agent_id / "agent")
        pairs.append({
            "agent_id": agent_id,
            "workshop_dir": Path(agent_dir) / "workshop-skills",
            "loaded_dir": Path(workspace) / "skills" if workspace else None,
        })
    return pairs


def load_ack(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": "veritas.skill_shadow_acknowledged.v1", "entries": []}
    return json.loads(path.read_text(encoding="utf-8"))


def ack_key(agent_id: str, skill: str, loaded_hash: str, workshop_hash: str) -> str:
    return f"{agent_id}|{skill}|{loaded_hash}|{workshop_hash}"


def build(config_path: Path, state_dir: Path, ack_path: Path) -> dict[str, Any]:
    acked = {e.get("key"): e for e in load_ack(ack_path).get("entries", [])}
    rows: list[dict[str, Any]] = []
    for pair in agent_pairs(config_path, state_dir):
        workshop, loaded = pair["workshop_dir"], pair["loaded_dir"]
        if not workshop.is_dir() or loaded is None:
            continue
        for skill_dir in sorted(p for p in workshop.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
            shadow = loaded / skill_dir.name
            if not shadow.is_dir():
                continue
            lh, wh = tree_hash(shadow), tree_hash(skill_dir)
            if lh == wh:
                status = "identical"
            else:
                key = ack_key(pair["agent_id"], skill_dir.name, lh, wh)
                status = "acknowledged" if key in acked else "new"
            row = {
                "agent_id": pair["agent_id"],
                "skill": skill_dir.name,
                "status": status,
                "loaded_path": shadow.as_posix(),
                "workshop_path": skill_dir.as_posix(),
                "loaded_hash": lh,
                "workshop_hash": wh,
            }
            if status != "identical":
                row["delta"] = file_delta(shadow, skill_dir)
            if status == "acknowledged":
                row["acknowledged_reason"] = acked[ack_key(pair["agent_id"], skill_dir.name, lh, wh)].get("reason")
            rows.append(row)
    new = [r for r in rows if r["status"] == "new"]
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in ("identical", "acknowledged", "new")}
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "error" if new else "ok",
        "summary": {"shadowed_pairs": len(rows), **counts},
        "rows": rows,
        "next_action": (
            "Publish the Workshop change into the loaded copy (or stage the matching Workshop update), "
            "then acknowledge only a reviewed, intentional difference."
            if new else "No new shadowed divergence."
        ),
        "authority_boundary": {"read_only_skills": True, "copies_or_merges": False, "owner_approval_inferred": False},
        "validation": {"status": "error" if new else "ok", "errors": [f"new_shadowed_divergence:{r['agent_id']}/{r['skill']}" for r in new], "warnings": []},
    }


def acknowledge(payload: dict[str, Any], ack_path: Path, reason: str, skills: list[str] | None) -> int:
    data = load_ack(ack_path)
    keys = {e.get("key") for e in data["entries"]}
    added = 0
    for row in payload["rows"]:
        if row["status"] != "new" or (skills and row["skill"] not in skills):
            continue
        key = ack_key(row["agent_id"], row["skill"], row["loaded_hash"], row["workshop_hash"])
        if key in keys:
            continue
        data["entries"].append({"key": key, "agent_id": row["agent_id"], "skill": row["skill"], "reason": reason, "acknowledged_at_utc": utc_now()})
        added += 1
    ack_path.parent.mkdir(parents=True, exist_ok=True)
    ack_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return added


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", nargs="?", choices=["check", "acknowledge"], default="check")
    ap.add_argument("--config", type=Path, default=CONFIG)
    ap.add_argument("--state-dir", type=Path, default=STATE_DIR)
    ap.add_argument("--ack", type=Path, default=ACK)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--reason", default="")
    ap.add_argument("--skill", action="append")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--validate", action="store_true")
    args = ap.parse_args(argv)
    payload = build(args.config, args.state_dir, args.ack)
    if args.command == "acknowledge":
        if not args.reason.strip():
            print("acknowledge requires --reason", file=sys.stderr)
            return 2
        added = acknowledge(payload, args.ack, args.reason.strip(), args.skill)
        print(f"acknowledged={added}")
        payload = build(args.config, args.state_dir, args.ack)
    if args.write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    s = payload["summary"]
    print(f"status={payload['status']} shadowed={s['shadowed_pairs']} identical={s['identical']} acknowledged={s['acknowledged']} new={s['new']}")
    if args.validate and payload["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
