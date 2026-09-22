#!/usr/bin/env python3
"""Scoped-writeback dispatch preflight for persistent isolated agents.

Deterministic, model-free gate for scoped_worktree_implementation lanes under
veritas-isolated-agent-contract. Attachment-readback proofs keep the 24-hour
freshness rule; scoped-writeback proofs use 7-day event-keyed validity: the
proof stays valid until the agent's sandbox/tool configuration drifts.

Checks (any failure blocks, fail-closed):
  1. proof exists, parses, schema/status ok
  2. capabilities.scoped_worktree_implementation is true
  3. proof age <= 7 days (observed_at_utc)
  4. live agent sandbox+tools config fingerprint matches proof-attested fingerprint
  5. sandbox image inspectable (Docker daemon alive)
  6. every read-write bind-mount source path exists on the host

Usage:
  python scripts/scoped_writeback_preflight.py --agent implementation-builder [--proof PATH]
  python scripts/scoped_writeback_preflight.py --agent implementation-builder --print-fingerprint

Prints strict JSON verdict (veritas.scoped_writeback_preflight.v1).
Exit 0 = ok, 1 = blocked/error.
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

SCHEMA = "veritas.scoped_writeback_preflight.v1"
PROOF_SCHEMA = "veritas.persistent_transport_proof.v1"
MAX_PROOF_AGE_DAYS = 7


def load_config():
    path = os.environ.get(
        "OPENCLAW_CONFIG_PATH",
        os.path.join(os.path.expanduser("~"), ".openclaw", "openclaw.json"),
    )
    with open(path, "r", encoding="utf-8-sig") as fh:
        return json.load(fh), path


def agent_entry(config, agent_id):
    entries = (config.get("agents") or {}).get("entries") or {}
    if agent_id not in entries:
        raise KeyError(f"agent '{agent_id}' not in agents.entries")
    return entries[agent_id]


def config_fingerprint(entry):
    """Hash the config surface that defines the scoped-writeback capability."""
    material = {
        "sandbox": entry.get("sandbox"),
        "tools": entry.get("tools"),
    }
    canon = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def parse_bind_host(bind):
    """Return (host_path, is_rw) for a docker bind string.

    Windows form:  C:\\path\\dir:/container/path:rw
    POSIX form:    /host/path:/container/path:ro
    """
    parts = bind.split(":")
    if len(parts) >= 2 and len(parts[0]) == 1 and parts[0].isalpha():
        host = parts[0] + ":" + parts[1]
        rest = parts[2:]
    else:
        host = parts[0]
        rest = parts[1:]
    opts = rest[1:] if len(rest) > 1 else []
    is_rw = "rw" in opts or "ro" not in opts
    return host, is_rw


def latest_proof_path(agent_id):
    ws = os.path.join(os.path.expanduser("~"), ".openclaw", "workspace")
    tmp = os.path.join(ws, "tmp")
    prefix = f"{agent_id}-transport-proof-"
    candidates = []
    if os.path.isdir(tmp):
        for name in os.listdir(tmp):
            if name.startswith(prefix) and name.endswith(".json") and "superseded" not in name:
                candidates.append(os.path.join(tmp, name))
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def verdict(status, agent_id, checks, reason, proof_path=None):
    out = {
        "schema": SCHEMA,
        "status": status,
        "agent_id": agent_id,
        "proof_path": proof_path,
        "checks": checks,
        "reason": reason,
        "observed_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    }
    print(json.dumps(out, indent=2))
    return 0 if status == "ok" else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--proof", default=None)
    ap.add_argument("--print-fingerprint", action="store_true")
    args = ap.parse_args()

    try:
        config, _ = load_config()
        entry = agent_entry(config, args.agent)
    except Exception as exc:
        return verdict("blocked", args.agent, {}, f"config load failed: {exc}")

    live_fp = config_fingerprint(entry)
    if args.print_fingerprint:
        print(json.dumps({"agent_id": args.agent, "config_fingerprint": live_fp}))
        return 0

    checks = {}
    proof_path = args.proof or latest_proof_path(args.agent)
    if not proof_path or not os.path.isfile(proof_path):
        return verdict("blocked", args.agent, checks, "no proof file found", proof_path)

    try:
        with open(proof_path, "r", encoding="utf-8-sig") as fh:
            proof = json.load(fh)
    except Exception as exc:
        return verdict("blocked", args.agent, checks, f"proof parse failed: {exc}", proof_path)

    checks["schema_status"] = proof.get("schema") == PROOF_SCHEMA and proof.get("status") == "ok"
    checks["capability"] = bool(
        (proof.get("capabilities") or {}).get("scoped_worktree_implementation")
    )
    checks["agent_match"] = proof.get("agent_id") == args.agent

    age_ok = False
    try:
        observed = datetime.datetime.strptime(
            proof["observed_at_utc"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=datetime.timezone.utc)
        age_ok = (datetime.datetime.now(datetime.timezone.utc) - observed) <= datetime.timedelta(
            days=MAX_PROOF_AGE_DAYS
        )
    except Exception:
        age_ok = False
    checks["age_within_7d"] = age_ok

    attested_fp = ((proof.get("evidence") or {}).get("config_fingerprint") or {}).get("sha256")
    checks["config_fingerprint_match"] = bool(attested_fp) and attested_fp == live_fp

    sandbox = entry.get("sandbox") or {}
    docker_cfg = sandbox.get("docker") or {}
    image = docker_cfg.get("image")
    image_ok = False
    if image:
        try:
            proc = subprocess.run(
                ["docker", "image", "inspect", image],
                capture_output=True,
                timeout=20,
            )
            image_ok = proc.returncode == 0
        except Exception:
            image_ok = False
    checks["docker_image_present"] = image_ok

    rw_sources = []
    for bind in docker_cfg.get("binds") or []:
        host, is_rw = parse_bind_host(bind)
        if is_rw:
            rw_sources.append(host)
    checks["rw_bind_sources_exist"] = bool(rw_sources) and all(
        os.path.exists(h) for h in rw_sources
    )

    if all(checks.values()):
        return verdict("ok", args.agent, checks, "scoped writeback valid (7-day event-keyed)", proof_path)
    failed = [k for k, v in checks.items() if not v]
    return verdict(
        "blocked",
        args.agent,
        checks,
        "failed checks: " + ",".join(failed) + "; re-prove writeback before dispatch",
        proof_path,
    )


if __name__ == "__main__":
    sys.exit(main())
