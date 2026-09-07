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
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TMP = ROOT / "tmp"

GRAPH_CANDIDATES = {
    "scripts": [
        ROOT / "scripts" / "graphify-out" / "graph.json",
        TMP / "graphify-scripts-pilot" / "graphify-out" / "graph.json",
    ],
    "skills": [TMP / "graphify-skills-pilot" / "graphify-out" / "graph.json"],
    "skills-md": [TMP / "graphify-test3-hostagent" / "graphify-out" / "graph.json"],
}

# Compatibility export for callers that imported the old constant directly.
GRAPHS = {name: paths[0] for name, paths in GRAPH_CANDIDATES.items()}

GRAPHIFY_BIN = "graphify"


class GraphifyError(Exception):
    pass


class GraphifyRouter:
    """Read-only query interface to local Graphify graphs."""

    def __init__(self, graphs: dict[str, Path] | None = None) -> None:
        candidates = (
            {name: [Path(path)] for name, path in graphs.items()}
            if graphs is not None
            else {name: [Path(path) for path in paths] for name, paths in GRAPH_CANDIDATES.items()}
        )
        self.candidates = candidates
        self.graphs = {
            name: selected
            for name, paths in candidates.items()
            if (selected := self._select_path(name, paths)) is not None
        }
        self._check_bin()

    @staticmethod
    def _manifest_entry_count(graph: Path) -> int:
        manifest = graph.parent / "manifest.json"
        if not manifest.is_file():
            return 0
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        return len(payload) if isinstance(payload, dict) else 0

    @classmethod
    def _select_path(cls, name: str, paths: list[Path]) -> Path | None:
        existing = [path.resolve() for path in paths if path.is_file()]
        if not existing:
            return None
        if name != "scripts":
            return existing[0]
        # A populated Graphify manifest is stronger evidence than graph mtime.
        # Graph size then favors the more complete candidate without loading it.
        return max(
            existing,
            key=lambda path: (
                1 if cls._manifest_entry_count(path) > 0 else 0,
                path.stat().st_size,
                path.stat().st_mtime,
            ),
        )

    @staticmethod
    def _utc_text(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _graph_counts(path: Path) -> tuple[int, int, bool]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        nodes = payload.get("nodes")
        links = payload.get("links", payload.get("edges"))
        if not isinstance(nodes, list) or not isinstance(links, list):
            raise GraphifyError("graph JSON must contain node and edge arrays")
        return len(nodes), len(links), bool(payload.get("directed"))

    @staticmethod
    def _scripts_manifest_health(graph: Path) -> dict[str, Any]:
        out_dir = graph.parent
        manifest = out_dir / "manifest.json"
        source_root = out_dir.parent
        if not manifest.is_file():
            return {
                "method": "manifest_mtime",
                "manifest_path": manifest,
                "source_root": source_root,
                "manifest_entries": 0,
                "changed_count": None,
                "new_count": None,
                "deleted_count": None,
                "coverage_status": "unknown",
            }
        try:
            rows = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            rows = None
        if not isinstance(rows, dict) or not rows:
            return {
                "method": "manifest_mtime",
                "manifest_path": manifest,
                "source_root": source_root,
                "manifest_entries": 0,
                "changed_count": None,
                "new_count": None,
                "deleted_count": None,
                "coverage_status": "invalid_manifest",
            }

        tracked = {str(key).replace("\\", "/"): value for key, value in rows.items() if isinstance(value, dict)}
        suffixes = {Path(key).suffix.casefold() for key in tracked if Path(key).suffix}
        current: dict[str, Path] = {}
        for path in source_root.rglob("*"):
            if not path.is_file() or "graphify-out" in path.parts or "__pycache__" in path.parts:
                continue
            if path.suffix.casefold() not in suffixes:
                continue
            current[path.relative_to(source_root).as_posix()] = path

        changed = 0
        for key in sorted(set(tracked) & set(current)):
            recorded = tracked[key].get("mtime")
            if not isinstance(recorded, (int, float)) or abs(current[key].stat().st_mtime - float(recorded)) > 0.001:
                changed += 1
        new = sorted(set(current) - set(tracked))
        deleted = sorted(set(tracked) - set(current))
        return {
            "method": "manifest_mtime",
            "manifest_path": manifest,
            "source_root": source_root,
            "manifest_entries": len(tracked),
            "current_files": len(current),
            "changed_count": changed,
            "new_count": len(new),
            "deleted_count": len(deleted),
            "new_sample": new[:10],
            "deleted_sample": deleted[:10],
            "coverage_status": "fresh" if changed == 0 and not new and not deleted else "stale",
        }

    @classmethod
    def _semantic_hash_health(cls, graph: Path) -> dict[str, Any]:
        try:
            payload = json.loads(graph.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"method": "source_sha256", "coverage_status": "invalid_graph"}
        sources: dict[str, set[str]] = {}
        for node in payload.get("nodes", []):
            if not isinstance(node, dict):
                continue
            source = str(node.get("source_file") or "").replace("\\", "/").strip()
            digest = str(node.get("source_sha256") or "").strip().casefold()
            if source and digest:
                sources.setdefault(source, set()).add(digest)
        missing: list[str] = []
        mismatched: list[str] = []
        ambiguous: list[str] = []
        for source, hashes in sorted(sources.items()):
            path = ROOT / source
            if len(hashes) != 1:
                ambiguous.append(source)
            elif not path.is_file():
                missing.append(source)
            elif cls._sha256(path).casefold() not in hashes:
                mismatched.append(source)
        status = "fresh" if sources and not missing and not mismatched and not ambiguous else "stale"
        return {
            "method": "source_sha256",
            "source_count": len(sources),
            "missing_count": len(missing),
            "mismatched_count": len(mismatched),
            "ambiguous_hash_count": len(ambiguous),
            "missing_sample": missing[:10],
            "mismatched_sample": mismatched[:10],
            "coverage_status": status,
        }

    @classmethod
    def _profile(cls, name: str, path: Path) -> dict[str, Any]:
        resolved = path.resolve()
        base: dict[str, Any] = {
            "name": name,
            "path": resolved,
            "exists": resolved.is_file(),
            "status": "blocked",
            "coverage_status": "missing",
        }
        if not resolved.is_file():
            return base
        try:
            nodes, edges, directed = cls._graph_counts(resolved)
            stat = resolved.stat()
            freshness = (
                cls._scripts_manifest_health(resolved)
                if name == "scripts"
                else cls._semantic_hash_health(resolved)
                if name == "skills-md"
                else {"method": "graph_mtime_only", "coverage_status": "unknown"}
            )
            coverage = str(freshness.get("coverage_status") or "unknown")
            base.update(
                {
                    "status": "healthy" if nodes > 0 and edges > 0 else "blocked",
                    "coverage_status": coverage,
                    "nodes": nodes,
                    "edges": edges,
                    "directed": directed,
                    "bytes": stat.st_size,
                    "modified_at_utc": cls._utc_text(stat.st_mtime),
                    "modified_timestamp": stat.st_mtime,
                    "freshness": freshness,
                }
            )
        except (OSError, json.JSONDecodeError, GraphifyError) as exc:
            base["error"] = str(exc)
        return base

    @staticmethod
    def _select_profile(profiles: list[dict[str, Any]]) -> dict[str, Any]:
        usable = [row for row in profiles if row.get("status") == "healthy"]
        if not usable:
            return profiles[0] if profiles else {"path": None, "status": "blocked"}
        freshness_rank = {"fresh": 3, "stale": 2, "unknown": 1, "invalid_manifest": 0, "missing": 0}
        return max(
            usable,
            key=lambda row: (
                freshness_rank.get(str(row.get("coverage_status")), 0),
                int(row.get("nodes") or 0),
                float(row.get("modified_timestamp") or 0),
            ),
        )

    @staticmethod
    def _public_profile(profile: dict[str, Any], *, selected: bool) -> dict[str, Any]:
        result = dict(profile)
        result["path"] = str(profile.get("path")) if profile.get("path") is not None else None
        result["selected"] = selected
        result.pop("modified_timestamp", None)
        freshness = dict(result.get("freshness") or {})
        for key in ("manifest_path", "source_root"):
            if key in freshness:
                freshness[key] = str(freshness[key])
        result["freshness"] = freshness
        return result

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

    def health(self, graph_name: str | None = None) -> dict[str, Any]:
        profiles_by_name = {
            name: [self._profile(name, path) for path in paths]
            for name, paths in self.candidates.items()
        }
        names = [graph_name] if graph_name else sorted(profiles_by_name)
        graphs: dict[str, Any] = {}
        for name in names:
            if name not in profiles_by_name:
                raise GraphifyError(f"unknown graph: {name}")
            selected = self.graphs.get(name)
            profiles = [
                self._public_profile(row, selected=selected is not None and row.get("path") == selected)
                for row in profiles_by_name[name]
            ]
            chosen = next((row for row in profiles if row["selected"]), None)
            graphs[name] = {
                "status": "ok" if chosen and chosen.get("status") == "healthy" else "blocked",
                "freshness": chosen.get("coverage_status") if chosen else "missing",
                "selected_path": chosen.get("path") if chosen else None,
                "candidates": profiles,
            }
        overall = "blocked" if any(row["status"] == "blocked" for row in graphs.values()) else (
            "warning" if any(row["freshness"] != "fresh" for row in graphs.values()) else "ok"
        )
        return {"schema": "veritas.graphify_router_health.v1", "status": overall, "graphs": graphs}


def main() -> int:
    parser = argparse.ArgumentParser(description="Graphify code-structure router for Veritas.")
    parser.add_argument("subcommand", choices=["affected", "explain", "path", "query", "available", "health"])
    parser.add_argument("args", nargs="*", help="node names or question")
    parser.add_argument(
        "--graph",
        choices=["scripts", "skills", "skills-md"],
        default=None,
        help="Which graph to query (default: scripts; health checks all graphs when omitted)",
    )
    parser.add_argument("--budget", type=int, default=2000, help="Token budget for query subcommand")
    args = parser.parse_args()

    router = GraphifyRouter()

    if args.subcommand == "available":
        print(json.dumps(router.available(), indent=2))
        return 0
    if args.subcommand == "health":
        print(json.dumps(router.health(args.graph), indent=2))
        return 0

    if not args.args:
        print(json.dumps({"status": "error", "error": f"{args.subcommand} requires at least one argument"}, indent=2))
        return 1

    graph_name = args.graph or "scripts"
    try:
        if args.subcommand == "affected":
            result = router.affected(args.args[0], graph_name=graph_name)
        elif args.subcommand == "explain":
            result = router.explain(args.args[0], graph_name=graph_name)
        elif args.subcommand == "path":
            if len(args.args) < 2:
                print(json.dumps({"status": "error", "error": "path requires source and target"}, indent=2))
                return 1
            result = router.path(args.args[0], args.args[1], graph_name=graph_name)
        elif args.subcommand == "query":
            result = router.query(" ".join(args.args), graph_name=graph_name, budget=args.budget)
        else:
            result = {"status": "error", "error": "unknown subcommand"}
    except GraphifyError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 1

    print(json.dumps({"status": "ok", "graph": graph_name, "result": result}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
