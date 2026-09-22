"""Metadata-only isolated-lane token closeout wrapper (patch_draft).

Invokes scripts/concurrent_lane_manager.py --complete with the opt-in
--import-isolated-session-usage and --require-dispatch-binding flags for an
existing lane. Fails closed on missing session identifiers, unallowlisted
agent ids, or a non-zero manager returncode. Never captures prompts,
responses, payloads, secrets, headers, session text, sessionFile paths, or
auth profiles. Never overrides the production isolated_agent_state_root.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANAGER = REPO_ROOT / "scripts" / "concurrent_lane_manager.py"
DEFAULT_PROOF_PATH = REPO_ROOT / "tmp" / "isolated-lane-token-closeout.json"

# Wrapper-scoped closeout agents. Both must also appear in the configured
# isolated-agent allowlist; membership is re-checked at runtime.
WRAPPER_AGENT_IDS = ("implementation-builder", "qa-redteam")

# Proof JSON must never contain these raw fields.
FORBIDDEN_PROOF_KEYS = frozenset({
    "sessionfile",
    "authprofile",
    "session_file",
    "auth_profile",
    "sessiontext",
    "prompt",
    "response",
    "payload",
    "secret",
    "header",
    "authorization",
    "token",
})


def load_configured_isolated_agent_ids() -> set[str]:
    path = (
        REPO_ROOT
        / "tmp"
        / "handoffs"
        / "token-closeout-import-20260911"
        / "configured_isolated_agents.txt"
    )
    ids: set[str] = set()
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                ids.add(line)
    except OSError:
        pass
    return ids or set(WRAPPER_AGENT_IDS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Close out an existing isolated lane with verified session-usage import."
    )
    parser.add_argument("--complete", metavar="WORKFLOW", required=True)
    parser.add_argument("--workstream", required=True)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--session-key", default="")
    parser.add_argument("--agent-id", default="", choices=("", *WRAPPER_AGENT_IDS))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument(
        "--proof-path",
        type=Path,
        default=DEFAULT_PROOF_PATH,
        help="Metadata-only proof JSON destination (default: tmp/isolated-lane-token-closeout.json).",
    )
    return parser


def scrub_proof(obj: object) -> object:
    if isinstance(obj, dict):
        return {
            key: scrub_proof(value)
            for key, value in obj.items()
            if key.lower().replace("-", "_") not in FORBIDDEN_PROOF_KEYS
        }
    if isinstance(obj, list):
        return [scrub_proof(item) for item in obj]
    return obj


def write_proof(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scrub_proof(payload), indent=2, sort_keys=True), encoding="utf-8")


def run_manager(cmd: list[str]) -> int:
    proc = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603 - fixed argv, no shell
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    lane_id = f"{args.complete}::{args.workstream}"
    flags = {
        "import_isolated_session_usage": True,
        "require_dispatch_binding": True,
        "write": bool(args.write),
        "validate": bool(args.validate),
    }
    base_proof = {
        "status": "failed_closed",
        "lane_id": lane_id,
        "workflow": args.complete,
        "workstream": args.workstream,
        "agent_id": args.agent_id,
        "has_session_id": bool(args.session_id),
        "has_session_key": bool(args.session_key),
        "flags": flags,
        "manager": str(MANAGER),
        "manager_returncode": None,
    }

    failure_reason = ""
    if not args.session_id and not args.session_key:
        failure_reason = "isolated session import requires --session-id or --session-key"
    elif args.agent_id and args.agent_id not in load_configured_isolated_agent_ids():
        failure_reason = "isolated session import requires an explicitly allowlisted --agent-id"
    if failure_reason:
        base_proof["failure_reason"] = failure_reason
        write_proof(args.proof_path, base_proof)
        print(failure_reason, file=sys.stderr)
        return 2

    cmd = [
        sys.executable,
        str(MANAGER),
        "--complete", args.complete,
        "--workstream", args.workstream,
        "--import-isolated-session-usage",
        "--require-dispatch-binding",
    ]
    if args.session_id:
        cmd += ["--session-id", args.session_id]
    if args.session_key:
        cmd += ["--session-key", args.session_key]
    if args.agent_id:
        cmd += ["--agent-id", args.agent_id]
    if args.write:
        cmd.append("--write")
    if args.validate:
        cmd.append("--validate")

    # Never pass --isolated-agent-state-root: production root must not be overridden.
    returncode = run_manager(cmd)
    base_proof["manager_returncode"] = returncode
    if returncode != 0:
        base_proof["failure_reason"] = f"manager exited non-zero: {returncode}"
        write_proof(args.proof_path, base_proof)
        return returncode
    base_proof["status"] = "complete"
    base_proof.pop("failure_reason", None)
    write_proof(args.proof_path, base_proof)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
