"""Graphify-backed code-structure router for Veritas.

Thin derivation layer. Does not mutate canonical workflow state, SQL, portfolio,
memory, wiki, or capsules. Queries the locally-built Graphify graphs under
tmp/graphify-*-pilot/graphify-out/graph.json and returns compact edges.

Usage from workflow_router.py or other scripts:

    from lib.graphify_router import GraphifyRouter
    router = GraphifyRouter()
    result = router.affected("workflow_router.py")

Command-line:

    python scripts/lib/graphify_router.py affected workflow_router.py
    python scripts/lib/graphify_router.py explain workflow_router.py scripts/lib/workflow_control.py
    python scripts/lib/graphify_router.py path "finance_intelligence_state.py" "sql_canon_front_door_readiness_packet.py"
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TMP = ROOT / "tmp"

GRAPHS = {
    "scripts": TMP / "graphify-scripts-pilot" / "graphify-out" / "graph.json",
    "skills": TMP / "graphify-skills-pilot" / "graphify-out" / "graph.json",
    "skills-md": TMP / "graphify-test3-hostagent" / "graphify-out" / "graph.json",
}

GRAPHIFY_BIN = "graphify"


class GraphifyError(Exception):
    pass


class GraphifyRouter:
    """Read-only query interface to local Graphify graphs."""

    def __init__(self, graphs: dict[str, Path] | None = None) -> None:
        self.graphs = {k: Path(v) for k, v in (graphs or GRAPHS).items()}
        self._check_bin()

    def _check_bin(self) -> None:
        if shutil.which(GRAPHIFY_BIN) is None:
            raise GraphifyError(f"{GRAPHIFY_BIN} not found on PATH")

    def _run(self, subcommand: str, *args: str, graph: Path) -> dict[str, Any]:
        if not graph.exists():
            raise GraphifyError(f"graph not found: {graph}")
        cmd = [GRAPHIFY_BIN, subcommand, *args, "--graph", str(graph)]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise GraphifyError(f"graphify timed out after 120s: {cmd}") from exc
        except Exception as exc:
            raise GraphifyError(f"failed to run graphify: {cmd}") from exc

        if proc.returncode != 0 and not proc.stdout.strip():
            raise GraphifyError(f"graphify error: {proc.stderr.strip() or proc.stdout.strip()}")

        # Some graphify subcommands emit plain text; others may emit nothing.
        # We normalize both cases into a structured dict.
        return {
            "command": cmd,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }

    def affected(self, node: str, graph_name: str = "scripts") -> dict[str, Any]:
        """Reverse dependency traversal: what depends on node?"""
        return self._run("affected", node, graph=self.graphs[graph_name])

    def explain(self, node: str, graph_name: str = "scripts") -> dict[str, Any]:
        """What is this node and what are its immediate relationships?"""
        return self._run("explain", node, graph=self.graphs[graph_name])

    def path(self, source: str, target: str, graph_name: str = "scripts") -> dict[str, Any]:
        """Path query between two nodes."""
        return self._run("path", source, target, graph=self.graphs[graph_name])

    def query(self, question: str, graph_name: str = "scripts", budget: int = 2000) -> dict[str, Any]:
        """Natural-language BFS query (noisier in code-only mode)."""
        return self._run("query", question, "--budget", str(budget), graph=self.graphs[graph_name])

    def available(self) -> dict[str, bool]:
        return {name: path.exists() for name, path in self.graphs.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Graphify code-structure router for Veritas.")
    parser.add_argument("subcommand", choices=["affected", "explain", "path", "query", "available"])
    parser.add_argument("args", nargs="*", help="node names or question")
    parser.add_argument("--graph", choices=["scripts", "skills", "skills-md"], default="scripts", help="Which graph to query")
    parser.add_argument("--budget", type=int, default=2000, help="Token budget for query subcommand")
    args = parser.parse_args()

    router = GraphifyRouter()

    if args.subcommand == "available":
        print(json.dumps(router.available(), indent=2))
        return 0

    if not args.args:
        print(json.dumps({"status": "error", "error": f"{args.subcommand} requires at least one argument"}, indent=2))
        return 1

    try:
        if args.subcommand == "affected":
            result = router.affected(args.args[0], graph_name=args.graph)
        elif args.subcommand == "explain":
            result = router.explain(args.args[0], graph_name=args.graph)
        elif args.subcommand == "path":
            if len(args.args) < 2:
                print(json.dumps({"status": "error", "error": "path requires source and target"}, indent=2))
                return 1
            result = router.path(args.args[0], args.args[1], graph_name=args.graph)
        elif args.subcommand == "query":
            result = router.query(" ".join(args.args), graph_name=args.graph, budget=args.budget)
        else:
            result = {"status": "error", "error": "unknown subcommand"}
    except GraphifyError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1

    print(json.dumps({"status": "ok", "graph": args.graph, "result": result}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
