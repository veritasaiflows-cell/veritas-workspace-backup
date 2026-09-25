#!/usr/bin/env python3
"""WF89 plan item 2: fleet grant manifest + drift check (read-only on config).

Every agent's authority (tools allow/deny, fs/exec/elevated, sandbox mode,
workspace access, Docker binds and hardening, model pin, skills, spawn and
agent-to-agent reach) is extracted from ~/.openclaw/openclaw.json into a
canonical per-agent grant with a fingerprint. The owner-facing ledger
state/agent-grants/grant-ledger.json records the accepted grant per agent and,
for every *notable* (risk-bearing) grant, the approval reference behind it.

  check   compare live config to the ledger; exit 1 on ANY unrecorded change
          (added/removed agent, changed grant, new notable grant). Notable
          grants recorded without a real approval are reported as WARN.
  record  accept the live grant for one agent into the ledger. Refuses when a
          new notable grant appears unless --approval-ref names the approval.
  approve attach an owner approval to an already-recorded notable grant
          (refused if the live value has drifted from the ledger).
  init    create the ledger from live config plus a provenance file (once).

Never writes openclaw.json. Sandbox env values are stored only as sha256.
The ledger is evidence of what was approved; it grants nothing by itself.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

CONFIG = Path.home() / ".openclaw" / "openclaw.json"
WORKSPACE = Path(__file__).resolve().parent.parent
LEDGER = WORKSPACE / "state" / "agent-grants" / "grant-ledger.json"
LEDGER_SCHEMA = "veritas.wf89_grant_ledger.v1"
GLOBAL_ID = "_global"
UNPROVENANCED = "UNPROVENANCED"
COSMETIC_KEYS = ("identity", "name")
WRITE_TOOLS = {"write", "edit", "apply_patch"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def fingerprint(obj: object) -> str:
    return sha(json.dumps(obj, sort_keys=True, separators=(",", ":")))


def extract(config: dict) -> dict[str, dict]:
    """Per-agent canonical grants plus a _global entry for fleet-wide reach."""
    agents = (config.get("agents") or {})
    out: dict[str, dict] = {}
    for agent_id, entry in (agents.get("entries") or {}).items():
        g = copy.deepcopy(entry)
        for k in COSMETIC_KEYS:
            g.pop(k, None)
        env = (((g.get("sandbox") or {}).get("docker") or {}).get("env"))
        if isinstance(env, dict):
            g["sandbox"]["docker"]["env"] = {k: "sha256:" + sha(str(v)) for k, v in env.items()}
        out[agent_id] = g
    tools = config.get("tools") or {}
    out[GLOBAL_ID] = {
        "tools.profile": tools.get("profile"),
        "tools.agentToAgent": tools.get("agentToAgent"),
        "tools.sessions": tools.get("sessions"),
        "tools.sessions_spawn": tools.get("sessions_spawn"),
        "agents.defaults.subagents": (agents.get("defaults") or {}).get("subagents"),
        "agents.defaults.maxConcurrent": (agents.get("defaults") or {}).get("maxConcurrent"),
    }
    return out


def notable(agent_id: str, g: dict) -> dict[str, object]:
    """Risk-bearing grants, keyed by a stable flag name. Values are recorded so
    a change of value (e.g. network none -> bridge) is itself drift."""
    f: dict[str, object] = {}
    if agent_id == GLOBAL_ID:
        a2a = g.get("tools.agentToAgent") or {}
        if a2a.get("enabled"):
            f["agentToAgent.allow"] = sorted(a2a.get("allow") or [])
        vis = (g.get("tools.sessions") or {}).get("visibility")
        if vis and vis != "self":
            f["sessions.visibility"] = vis
        return f
    tools = g.get("tools") or {}
    allow = set(tools.get("allow") or [])
    sb = g.get("sandbox") or {}
    dk = sb.get("docker") or {}
    sandboxed = sb.get("mode") in ("all", "non-main") and bool(sb.get("backend"))
    if allow & WRITE_TOOLS:
        f["tools.write"] = sorted(allow & WRITE_TOOLS)
    if "exec" in allow:
        f["tools.exec"] = (tools.get("exec") or {}).get("host", "host-default")
    if (tools.get("elevated") or {}).get("enabled"):
        f["tools.elevated"] = True
    if (tools.get("fs") or {}).get("workspaceOnly") is False:
        f["fs.workspaceOnly=false"] = "sandboxed" if sandboxed else "HOST"
    if allow & (WRITE_TOOLS | {"exec"}) and not sandboxed:
        f["unsandboxed.write_or_exec"] = sorted(allow & (WRITE_TOOLS | {"exec"}))
    cc = (tools.get("message") or {}).get("crossContext") or {}
    if cc.get("allowWithinProvider") or cc.get("allowAcrossProviders"):
        f["message.crossContext"] = cc
    if (g.get("subagents") or {}).get("allowAgents"):
        f["subagents.allowAgents"] = sorted(g["subagents"]["allowAgents"])
    if sb:
        if sb.get("workspaceAccess") not in (None, "none"):
            f["sandbox.workspaceAccess"] = sb.get("workspaceAccess")
        if dk.get("dangerouslyAllowExternalBindSources"):
            f["docker.dangerouslyAllowExternalBindSources"] = True
        rw = [b for b in (dk.get("binds") or []) if str(b).endswith(":rw")]
        if rw:
            f["docker.binds.rw"] = rw
        if dk.get("network") not in (None, "none"):
            f["docker.network"] = dk.get("network")
        if dk.get("readOnlyRoot") is not True:
            f["docker.readOnlyRoot!=true"] = dk.get("readOnlyRoot")
        if "ALL" not in (dk.get("capDrop") or []):
            f["docker.capDrop!=ALL"] = dk.get("capDrop")
        if str(dk.get("user", "")).split(":")[0] in ("", "0", "root"):
            f["docker.user=root"] = dk.get("user")
    return f


def diff_paths(a: object, b: object, path: str = "") -> list[str]:
    if isinstance(a, dict) and isinstance(b, dict):
        out: list[str] = []
        for k in sorted(set(a) | set(b)):
            p = f"{path}.{k}" if path else str(k)
            if k not in a:
                out.append(f"+{p}")
            elif k not in b:
                out.append(f"-{p}")
            else:
                out.extend(diff_paths(a[k], b[k], p))
        return out
    return [] if a == b else [f"~{path or '<root>'}"]


def live_view(config: dict) -> dict[str, dict]:
    grants = extract(config)
    return {aid: {"fingerprint": fingerprint(g), "grant": g, "notable": notable(aid, g)}
            for aid, g in grants.items()}


def check(config: dict, ledger: dict) -> dict:
    live = live_view(config)
    rec = ledger.get("agents") or {}
    fails: list[dict] = []
    warns: list[dict] = []
    for aid in sorted(set(live) | set(rec)):
        if aid not in rec:
            fails.append({"agent": aid, "drift": "agent_added", "notable": live[aid]["notable"]})
            continue
        if aid not in live:
            fails.append({"agent": aid, "drift": "agent_removed"})
            continue
        L, R = live[aid], rec[aid]
        if L["fingerprint"] != R["fingerprint"]:
            fails.append({"agent": aid, "drift": "grant_changed",
                          "paths": diff_paths(R["grant"], L["grant"]),
                          "notable_now": L["notable"]})
        for flag, info in (R.get("notable") or {}).items():
            if str(info.get("approval_ref", "")).startswith(UNPROVENANCED):
                warns.append({"agent": aid, "notable": flag, "value": info.get("value"),
                              "approval_ref": info.get("approval_ref")})
    return {"schema": "veritas.wf89_grant_check.v1", "checked_at_utc": utc_now(),
            "status": "FAIL" if fails else ("WARN" if warns else "PASS"),
            "agents_checked": len(live), "drift": fails, "unprovenanced_notable": warns}


def ledger_entry(view: dict, approvals: dict[str, str], record_ref: str) -> dict:
    return {"fingerprint": view["fingerprint"], "grant": view["grant"],
            "recorded_at_utc": utc_now(), "record_ref": record_ref,
            "notable": {flag: {"value": val, "approval_ref": approvals.get(flag) or
                               f"{UNPROVENANCED}: present before the grant ledger existed; owner review pending"}
                        for flag, val in view["notable"].items()}}


def init_ledger(config: dict, provenance: dict, record_ref: str) -> dict:
    live = live_view(config)
    return {"schema": LEDGER_SCHEMA, "created_at_utc": utc_now(),
            "posture": "evidence of approved grants; grants nothing; openclaw.json stays the runtime authority",
            "agents": {aid: ledger_entry(v, provenance.get(aid) or {}, record_ref)
                       for aid, v in sorted(live.items())},
            "history": [{"at_utc": utc_now(), "action": "init", "record_ref": record_ref}]}


def record(config: dict, ledger: dict, agent_id: str, record_ref: str,
           approval_ref: str | None) -> dict:
    live = live_view(config)
    if agent_id not in live:
        raise ValueError(f"agent {agent_id!r} not in live config (use record_removal semantics manually)")
    if not record_ref.strip():
        raise ValueError("--record-ref is required")
    view = live[agent_id]
    old = (ledger.get("agents") or {}).get(agent_id)
    old_notable = (old or {}).get("notable") or {}
    approvals: dict[str, str] = {}
    unapproved_new = []
    for flag, val in view["notable"].items():
        prev = old_notable.get(flag)
        if prev is not None and prev.get("value") == val:
            approvals[flag] = prev["approval_ref"]
        elif approval_ref:
            approvals[flag] = approval_ref
        else:
            unapproved_new.append(flag)
    if unapproved_new:
        raise PermissionError(f"new or changed notable grant(s) {unapproved_new} need --approval-ref")
    new = copy.deepcopy(ledger)
    new["agents"][agent_id] = ledger_entry(view, approvals, record_ref)
    new["history"].append({"at_utc": utc_now(), "action": "record", "agent": agent_id,
                           "old_fingerprint": (old or {}).get("fingerprint"),
                           "new_fingerprint": view["fingerprint"],
                           "paths": diff_paths((old or {}).get("grant") or {}, view["grant"]),
                           "record_ref": record_ref, "approval_ref": approval_ref})
    return new


def approve(config: dict, ledger: dict, agent_id: str, flag: str, approval_ref: str) -> dict:
    """Attach an owner approval to an already-recorded notable grant. Refuses if
    the live value differs from the ledger (that is drift: use record)."""
    if not approval_ref.strip() or approval_ref.startswith(UNPROVENANCED):
        raise ValueError("a real --approval-ref is required")
    entry = (ledger.get("agents") or {}).get(agent_id) or {}
    rec_flag = (entry.get("notable") or {}).get(flag)
    if rec_flag is None:
        raise ValueError(f"{agent_id}: no recorded notable grant {flag!r}")
    live = live_view(config).get(agent_id)
    if live is None or live["notable"].get(flag) != rec_flag["value"]:
        raise PermissionError(f"{agent_id}.{flag}: live value differs from ledger; record the drift first")
    new = copy.deepcopy(ledger)
    new["agents"][agent_id]["notable"][flag]["approval_ref"] = approval_ref
    new["history"].append({"at_utc": utc_now(), "action": "approve", "agent": agent_id,
                           "flag": flag, "previous_ref": rec_flag["approval_ref"],
                           "approval_ref": approval_ref})
    return new


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(p: Path, obj: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WF89 fleet grant manifest + drift check")
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--ledger", default=str(LEDGER))
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--out", default=None)
    i = sub.add_parser("init")
    i.add_argument("--provenance", required=True)
    i.add_argument("--record-ref", required=True)
    r = sub.add_parser("record")
    r.add_argument("--agent", required=True)
    r.add_argument("--record-ref", required=True)
    r.add_argument("--approval-ref", default=None)
    ap_ = sub.add_parser("approve")
    ap_.add_argument("--agent", required=True)
    ap_.add_argument("--flag", required=True)
    ap_.add_argument("--approval-ref", required=True)
    args = ap.parse_args(argv)
    config = load_json(Path(args.config))
    ledger_path = Path(args.ledger)
    if args.cmd == "init":
        if ledger_path.exists():
            print(json.dumps({"status": "error", "error": "ledger exists; use record"}))
            return 2
        write_json(ledger_path, init_ledger(config, load_json(Path(args.provenance)), args.record_ref))
        print(json.dumps({"status": "ok", "ledger": str(ledger_path)}))
        return 0
    ledger = load_json(ledger_path)
    if args.cmd == "approve":
        try:
            write_json(ledger_path, approve(config, ledger, args.agent, args.flag, args.approval_ref))
        except (ValueError, PermissionError) as exc:
            print(json.dumps({"status": "refused", "error": str(exc)}))
            return 2
        print(json.dumps({"status": "ok", "agent": args.agent, "flag": args.flag}))
        return 0
    if args.cmd == "record":
        try:
            write_json(ledger_path, record(config, ledger, args.agent, args.record_ref, args.approval_ref))
        except (ValueError, PermissionError) as exc:
            print(json.dumps({"status": "refused", "error": str(exc)}))
            return 2
        print(json.dumps({"status": "ok", "agent": args.agent}))
        return 0
    result = check(config, ledger)
    if args.out:
        write_json(Path(args.out), result)
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
