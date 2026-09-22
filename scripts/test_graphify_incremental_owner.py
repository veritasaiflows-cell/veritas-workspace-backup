#!/usr/bin/env python3
"""Adversarial regression tests for the bounded incremental owner."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parent
LIB = SCRIPTS / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
import graphify_incremental_owner as owner  # noqa: E402


VALIDATION_ROOT = Path(
    os.environ.get("GRAPH_INCREMENTAL_TEST_ROOT", tempfile.gettempdir())
).resolve()


def _tempdir() -> tempfile.TemporaryDirectory[str]:
    VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=VALIDATION_ROOT)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()


def _row(path: Path, *, semantic: str = "") -> dict:
    return {
        "mtime": path.stat().st_mtime,
        "seen": 7.0,
        "ast_hash": _md5(path),
        "semantic_hash": semantic,
    }


def _ast_node(node_id: str, source: str) -> dict:
    return {
        "id": node_id,
        "label": node_id,
        "file_type": "code",
        "source_file": source,
        "_origin": "ast",
    }


def _ast_edge(source: str, target: str, source_file: str) -> dict:
    return {
        "source": source,
        "target": target,
        "source_file": source_file,
        "relation": "calls",
        "_origin": "ast",
    }


def _stub_node(node_id: str) -> dict:
    """Shared resolution stub exactly as graphify.extract emits it: AST
    origin, blank source_file, no file ownership (Any/Path/json/argparse)."""
    return {
        "id": node_id,
        "label": node_id,
        "file_type": "code",
        "source_file": "",
        "source_location": "",
        "_origin": "ast",
    }


def _base_graph() -> dict:
    return {
        "directed": False,
        "multigraph": False,
        "graph": {"name": "fixture", "custom": {"preserve": True}},
        "nodes": [
            _ast_node("a::old", "a.py"),
            _ast_node("stable::f", "stable.py"),
            {
                "id": "semantic::a",
                "label": "semantic",
                "file_type": "code",
                "source_file": "a.py",
                "_origin": "semantic",
                "data": {"preserve": True},
            },
        ],
        "links": [
            _ast_edge("a::old", "stable::f", "a.py"),
            _ast_edge("stable::f", "stable::f", "stable.py"),
            {
                "source": "semantic::a",
                "target": "stable::f",
                "source_file": "a.py",
                "relation": "supports",
                "_origin": "semantic",
                "data": {"preserve": True},
            },
        ],
        "hyperedges": [{"id": "h1", "nodes": ["semantic::a", "stable::f"]}],
    }


class Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.source = root / "source"
        self.output = root / "output"
        self.graph = self.output / "graph.json"
        self.manifest = self.output / "manifest.json"
        self.source.mkdir()
        self.output.mkdir()
        self.a = self.source / "a.py"
        self.stable = self.source / "stable.py"
        _write(self.a, "def old():\n    return 0\n")
        _write(self.stable, "def stable():\n    return 1\n")
        self.graph.write_text(json.dumps(_base_graph()), encoding="utf-8")
        self.rows = {
            "a.py": _row(self.a, semantic="must-blank"),
            "stable.py": _row(self.stable, semantic="keep-stable"),
        }
        self.manifest.write_text(json.dumps(self.rows), encoding="utf-8")

    def modify_a(self) -> None:
        _write(self.a, "def fresh():\n    return 2\n")

    def stage(self, name: str) -> Path:
        return self.root / name

    @staticmethod
    def fresh() -> dict:
        return {
            "nodes": [_ast_node("a::fresh", "a.py")],
            "edges": [_ast_edge("a::fresh", "stable::f", "a.py")],
            "failed_sources": [],
        }


def _fake(result: dict, mutate=None):
    calls: dict = {}

    def extract(
        paths,
        *,
        root,
        cache_root,
        resolution_context_nodes,
        resolution_context_edges,
    ):
        calls["paths"] = [Path(path).relative_to(root).as_posix() for path in paths]
        calls["root"] = Path(root)
        calls["cache_root"] = Path(cache_root)
        calls["context_nodes"] = json.loads(json.dumps(resolution_context_nodes))
        calls["context_edges"] = json.loads(json.dumps(resolution_context_edges))
        if mutate:
            mutate()
        return json.loads(json.dumps(result))

    extract.calls = calls
    return extract


class SelectionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = _tempdir()
        self.root = Path(self.temp.name) / "source"
        self.root.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_caps_apply_only_to_changed_subset_and_same_mtime_hash_wins(self) -> None:
        unchanged = self.root / "large.py"
        changed = self.root / "changed.py"
        _write(unchanged, "x = 1\n" * 200)
        _write(changed, "a = 1\n")
        manifest = {"large.py": _row(unchanged), "changed.py": _row(changed)}
        old_mtime = changed.stat().st_mtime
        _write(changed, "a = 2\n")
        os.utime(changed, (old_mtime, old_mtime))
        selection = owner.select_targets(
            self.root,
            manifest,
            max_file_bytes=20,
            max_total_bytes=20,
        )
        self.assertIsNone(selection["policy_block"])
        self.assertEqual([item["path"] for item in selection["targets"]], ["changed.py"])
        self.assertGreater(unchanged.stat().st_size, 20)
        self.assertEqual(selection["total_target_bytes"], changed.stat().st_size)

    def test_bounded_batch_is_resumable_when_total_drift_exceeds_count_cap(self) -> None:
        manifest = {}
        for index in range(30):
            path = self.root / f"f{index:02d}.py"
            _write(path, f"x = {index}\n")
        selection = owner.select_targets(
            self.root,
            manifest,
            max_targets=25,
            max_total_bytes=4_000_000,
        )
        self.assertIsNone(selection["policy_block"])
        self.assertEqual(len(selection["targets"]), 25)
        self.assertEqual(len(selection["deferred_changed"]), 5)
        self.assertEqual([item["path"] for item in selection["targets"]][:2], ["f00.py", "f01.py"])

    def test_escaped_changed_path_is_refused(self) -> None:
        _write(self.root / "safe.py", "x = 1\n")
        selection = owner.select_targets(self.root, {}, changed_paths=["../escape.py"])
        self.assertIn("unsafe_changed_path", selection["policy_block"])
        self.assertEqual(selection["targets"], [])

    def test_missing_and_unreadable_are_not_fresh(self) -> None:
        live = self.root / "live.py"
        _write(live, "x = 1\n")
        rows = {"live.py": _row(live), "gone.py": {"ast_hash": "x", "mtime": 1}}
        report = owner.freshness_report(self.root, rows)
        self.assertEqual(report["status"], "stale")
        self.assertEqual(report["deleted_count"], 1)
        with mock.patch.object(
            owner,
            "hash_file",
            return_value={"ok": False, "reason": "unreadable:PermissionError", "size": 0},
        ):
            blocked = owner.freshness_report(self.root, {"live.py": _row(live)})
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["coverage_status"], "unknown")

    def test_sensitive_generated_hidden_ignore_and_links_are_never_hashed(self) -> None:
        _write(self.root / ".gitignore", "*.py\n!keep.py\n")
        _write(self.root / "keep.py", "x = 1\n")
        _write(self.root / "drop.py", "x = 2\n")
        _write(self.root / "credentials" / "inside.py", "x = 3\n")
        _write(self.root / "generated" / "inside.py", "x = 4\n")
        _write(self.root / "tmp" / "inside.py", "x = 5\n")
        _write(self.root / "pkg" / ".gitignore", "/nested.py\n")
        _write(self.root / "pkg" / "nested.py", "x = 6\n")
        linked = self.root / "linked.py"
        try:
            linked.symlink_to(self.root / "keep.py")
        except OSError:
            linked = None
        with mock.patch.object(owner, "hash_file", wraps=owner.hash_file) as hashed:
            selection = owner.select_targets(self.root, {})
        read_names = {Path(call.args[0]).name for call in hashed.call_args_list}
        self.assertEqual(read_names, {"keep.py"})
        self.assertEqual([item["path"] for item in selection["targets"]], ["keep.py"])
        skipped = {item["path"]: item["reason"] for item in selection["skipped"]}
        self.assertEqual(skipped["credentials"], "sensitive_directory")
        self.assertEqual(skipped["generated"], "excluded_dir")
        self.assertEqual(skipped["tmp"], "excluded_dir")
        if linked is not None:
            self.assertEqual(skipped["linked.py"], "reparse_or_symlink_not_followed")

    def test_linked_ignore_and_reparse_flag_fail_closed(self) -> None:
        ignore = self.root / ".gitignore"
        _write(ignore, "*.py\n")
        original_lstat = Path.lstat

        def marked_lstat(path):
            actual = original_lstat(path)
            if Path(path) == ignore:
                return mock.Mock(
                    st_mode=actual.st_mode,
                    st_file_attributes=0x400,
                )
            return actual

        with mock.patch.object(Path, "lstat", autospec=True, side_effect=marked_lstat):
            selection = owner.select_targets(self.root, {})
        self.assertIn(
            "linked_or_nonregular_ignore_refused",
            selection["policy_block"],
        )
        fake_stat = mock.Mock(st_mode=stat.S_IFREG, st_file_attributes=0x400)
        self.assertTrue(owner._stat_is_reparse(fake_stat))

    def test_containing_repository_parent_ignore_is_loaded_before_source_reads(self) -> None:
        repository = self.root.parent
        (repository / ".git").mkdir()
        _write(repository / ".gitignore", "/source/drop.py\n")
        _write(self.root / "drop.py", "do_not_read = 1\n")
        _write(self.root / "keep.py", "x = 1\n")
        with mock.patch.object(owner, "hash_file", wraps=owner.hash_file) as hashed:
            selection = owner.select_targets(self.root, {})
        read_paths = {Path(call.args[0]).name for call in hashed.call_args_list}
        self.assertEqual(read_paths, {"keep.py"})
        self.assertEqual([item["path"] for item in selection["targets"]], ["keep.py"])
        self.assertEqual(selection["ignore_files"][0]["path"], "@repository/.gitignore")
        skipped = {item["path"]: item["reason"] for item in selection["skipped"]}
        self.assertEqual(skipped["drop.py"], "ignored_by_rule")

    def test_health_rejects_source_root_reparse_before_resolution(self) -> None:
        _write(self.root / "live.py", "x = 1\n")
        original_lstat = Path.lstat

        def marked_lstat(path):
            actual = original_lstat(path)
            if Path(path) == self.root:
                return mock.Mock(
                    st_mode=actual.st_mode,
                    st_file_attributes=0x400,
                )
            return actual

        with mock.patch.object(Path, "lstat", autospec=True, side_effect=marked_lstat):
            report = owner.freshness_report(self.root, {})
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["coverage_status"], "unknown")
        self.assertIn("source_root_reparse_component", report["policy_block"])


class StageAndMergeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = _tempdir()
        self.fixture = Fixture(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run(self, stage_name: str, fake=None, **kwargs):
        return owner.run_stage(
            source_root=self.fixture.source,
            graph_path=self.fixture.graph,
            manifest_path=self.fixture.manifest,
            stage_dir=self.fixture.stage(stage_name),
            extract_fn=fake or _fake(Fixture.fresh()),
            backend_name="fake-unit-extractor",
            **kwargs,
        )

    def test_stage_preserves_semantic_metadata_context_and_binds_receipt(self) -> None:
        self.fixture.modify_a()
        fake = _fake(Fixture.fresh())
        base_graph_bytes = self.fixture.graph.read_bytes()
        base_manifest_bytes = self.fixture.manifest.read_bytes()
        result = self._run("stage-success", fake=fake)
        self.assertEqual(result["outcome"], "staged")
        self.assertEqual(fake.calls["paths"], ["a.py"])
        self.assertEqual(
            {node["id"] for node in fake.calls["context_nodes"]},
            {"stable::f"},
        )
        staged_graph_path = self.fixture.stage("stage-success") / "staged_graph.json"
        staged_manifest_path = self.fixture.stage("stage-success") / "staged_manifest.json"
        staged_graph = json.loads(staged_graph_path.read_text(encoding="utf-8"))
        staged_manifest = json.loads(staged_manifest_path.read_text(encoding="utf-8"))
        by_id = {node["id"]: node for node in staged_graph["nodes"]}
        self.assertTrue(by_id["semantic::a"]["data"]["preserve"])
        semantic_edge = next(
            edge for edge in staged_graph["links"] if edge.get("_origin") == "semantic"
        )
        self.assertTrue(semantic_edge["data"]["preserve"])
        self.assertEqual(staged_graph["graph"], _base_graph()["graph"])
        self.assertEqual(staged_graph["hyperedges"], _base_graph()["hyperedges"])
        self.assertEqual(staged_manifest["a.py"]["semantic_hash"], "")
        self.assertEqual(staged_manifest["stable.py"], self.fixture.rows["stable.py"])
        receipt = result["receipt"]
        self.assertEqual(receipt["exact_subset_stamps"], ["a.py"])
        self.assertEqual(
            receipt["baseline_graph_sha256"],
            hashlib.sha256(base_graph_bytes).hexdigest(),
        )
        self.assertEqual(
            receipt["baseline_manifest_sha256"],
            hashlib.sha256(base_manifest_bytes).hexdigest(),
        )
        self.assertEqual(
            receipt["staged_graph_sha256"],
            hashlib.sha256(staged_graph_path.read_bytes()).hexdigest(),
        )
        self.assertFalse(receipt["full_graph_freshness_claimed"])
        self.assertFalse(receipt["current_head_claimed"])
        self.assertEqual(self.fixture.graph.read_bytes(), base_graph_bytes)
        self.assertEqual(self.fixture.manifest.read_bytes(), base_manifest_bytes)

    def test_subset_stamps_exactly_selected_and_excludes_deferred_context(self) -> None:
        b = self.fixture.source / "b.py"
        _write(b, "def b():\n    return 1\n")
        rows = json.loads(self.fixture.manifest.read_text(encoding="utf-8"))
        rows["b.py"] = _row(b, semantic="keep-b")
        graph = json.loads(self.fixture.graph.read_text(encoding="utf-8"))
        graph["nodes"].append(_ast_node("b::old", "b.py"))
        graph["links"].append(_ast_edge("b::old", "stable::f", "b.py"))
        self.fixture.graph.write_text(json.dumps(graph), encoding="utf-8")
        self.fixture.manifest.write_text(json.dumps(rows), encoding="utf-8")
        self.fixture.modify_a()
        _write(b, "def b():\n    return 2\n")
        fake = _fake(Fixture.fresh())
        result = self._run(
            "stage-subset", fake=fake, changed_paths=["a.py"], max_targets=1
        )
        self.assertEqual(result["outcome"], "staged")
        self.assertEqual(result["stamped"], ["a.py"])
        self.assertEqual(result["selection"]["deferred_changed"], ["b.py"])
        self.assertNotIn("b::old", {node["id"] for node in fake.calls["context_nodes"]})
        staged = json.loads(
            (self.fixture.stage("stage-subset") / "staged_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(staged["b.py"], rows["b.py"])

    def test_source_ignore_and_output_drift_during_extraction_block(self) -> None:
        mutators = {
            "source": lambda: _write(self.fixture.a, "def drift():\n    pass\n"),
            "ignore": lambda: _write(self.fixture.source / ".gitignore", "*.tmp\n"),
            "graph": lambda: self.fixture.graph.write_bytes(
                self.fixture.graph.read_bytes() + b" "
            ),
            "manifest": lambda: self.fixture.manifest.write_bytes(
                self.fixture.manifest.read_bytes() + b" "
            ),
        }
        for name, mutator in mutators.items():
            with self.subTest(name=name):
                case = Fixture(Path(self.temp.name) / name)
                case.modify_a()
                result = owner.run_stage(
                    source_root=case.source,
                    graph_path=case.graph,
                    manifest_path=case.manifest,
                    stage_dir=case.stage("stage"),
                    extract_fn=_fake(Fixture.fresh(), mutate=(
                        lambda case=case, name=name: (
                            _write(case.a, "def drift():\n    pass\n")
                            if name == "source"
                            else _write(case.source / ".gitignore", "*.tmp\n")
                            if name == "ignore"
                            else case.graph.write_bytes(case.graph.read_bytes() + b" ")
                            if name == "graph"
                            else case.manifest.write_bytes(case.manifest.read_bytes() + b" ")
                        )
                    )),
                    backend_name="fake-drift-extractor",
                )
                self.assertEqual(result["outcome"], "blocked")
                self.assertIn("drift", result["reason"])

    def test_failures_empty_foreign_and_non_ast_never_stamp(self) -> None:
        variants = [
            (
                {"nodes": [], "edges": [], "failed_sources": []},
                "omitted_or_empty",
            ),
            (
                {
                    "nodes": [_ast_node("a::fresh", "a.py")],
                    "edges": [],
                    "failed_sources": [str(self.fixture.a)],
                },
                "failures",
            ),
            (
                {
                    "nodes": [_ast_node("foreign", "foreign.py")],
                    "edges": [],
                    "failed_sources": [],
                },
                "outside_selected",
            ),
            (
                {
                    "nodes": [{
                        **_ast_node("a::fresh", "a.py"),
                        "_origin": "semantic",
                    }],
                    "edges": [],
                    "failed_sources": [],
                },
                "non_ast",
            ),
            (
                {
                    "nodes": [_ast_node("a::fresh", "a.py")],
                    "edges": ["malformed"],
                    "failed_sources": [],
                },
                "not_object",
            ),
            (
                # "a::old" exists in the base graph owned by the replaced
                # target a.py: a genuine stale reference that must still
                # refuse. (A truly unknown id is the external-symbol case,
                # covered by the drop tests below.)
                {
                    "nodes": [_ast_node("a::fresh", "a.py")],
                    "edges": [_ast_edge("a::fresh", "a::old", "a.py")],
                    "failed_sources": [],
                },
                "dangling",
            ),
        ]
        for index, (fresh, reason) in enumerate(variants):
            with self.subTest(reason=reason):
                case = Fixture(Path(self.temp.name) / f"bad-{index}")
                case.modify_a()
                result = owner.run_stage(
                    source_root=case.source,
                    graph_path=case.graph,
                    manifest_path=case.manifest,
                    stage_dir=case.stage("stage"),
                    extract_fn=_fake(fresh),
                    backend_name="fake-invalid-extractor",
                )
                self.assertEqual(result["outcome"], "blocked")
                self.assertIn(reason, result["reason"])
                self.assertFalse((case.stage("stage") / "proof.json").exists())

    def test_duplicate_dangling_incoming_hyperedge_and_foreign_block(self) -> None:
        base = _base_graph()
        duplicate = json.loads(json.dumps(base))
        duplicate["nodes"].append(dict(duplicate["nodes"][0]))
        self.assertIn(
            "duplicate",
            owner.merge_candidate(
                duplicate,
                Fixture.fresh(),
                {"a.py"},
                source_root=self.fixture.source,
            )["error"],
        )
        incoming = json.loads(json.dumps(base))
        incoming["links"].append(
            _ast_edge("stable::f", "a::old", "stable.py")
        )
        self.assertIn(
            "dangling",
            owner.merge_candidate(
                incoming,
                Fixture.fresh(),
                {"a.py"},
                source_root=self.fixture.source,
            )["error"],
        )
        hyper = json.loads(json.dumps(base))
        hyper["hyperedges"].append({"id": "h2", "nodes": ["a::old"]})
        self.assertIn(
            "hyperedge_dangling",
            owner.merge_candidate(
                hyper,
                Fixture.fresh(),
                {"a.py"},
                source_root=self.fixture.source,
            )["error"],
        )

    def test_shared_stub_base_wins_and_new_stub_is_kept(self) -> None:
        base = _base_graph()
        base["nodes"].append(_stub_node("stable::stub"))
        fresh = {
            "nodes": [
                _ast_node("a::fresh", "a.py"),
                _stub_node("stable::stub"),
                _stub_node("json"),
            ],
            "edges": [
                _ast_edge("a::fresh", "stable::f", "a.py"),
                _ast_edge("a::fresh", "stable::stub", "a.py"),
                _ast_edge("a::fresh", "json", "a.py"),
            ],
            "failed_sources": [],
        }
        result = owner.merge_candidate(
            base, fresh, {"a.py"}, source_root=self.fixture.source
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["shared_stub_base_wins"], 1)
        self.assertEqual(result["shared_stub_new"], 1)
        candidate_ids = {node["id"] for node in result["candidate"]["nodes"]}
        self.assertIn("stable::stub", candidate_ids)
        self.assertIn("json", candidate_ids)

    def test_duplicate_nodes_and_edges_from_extract_are_collapsed(self) -> None:
        fresh = {
            "nodes": [
                _ast_node("a::fresh", "a.py"),
                _ast_node("a::fresh", "a.py"),
            ],
            "edges": [
                _ast_edge("a::fresh", "stable::f", "a.py"),
                _ast_edge("a::fresh", "stable::f", "a.py"),
            ],
            "failed_sources": [],
        }
        result = owner.merge_candidate(
            _base_graph(), fresh, {"a.py"}, source_root=self.fixture.source
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["duplicate_nodes_dropped"], 1)
        self.assertEqual(result["duplicate_edges_dropped"], 1)
        self.assertEqual(result["fresh_nodes"], 1)
        self.assertEqual(result["fresh_edges"], 1)

    def test_unresolvable_external_endpoint_edge_is_dropped_not_fatal(self) -> None:
        fresh = {
            "nodes": [_ast_node("a::fresh", "a.py")],
            "edges": [
                _ast_edge("a::fresh", "stable::f", "a.py"),
                _ast_edge("a::fresh", "json", "a.py"),
                _ast_edge("a::fresh", "argparse", "a.py"),
            ],
            "failed_sources": [],
        }
        result = owner.merge_candidate(
            _base_graph(), fresh, {"a.py"}, source_root=self.fixture.source
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["dropped_unresolvable_edges"], 2)
        self.assertEqual(result["unresolvable_symbols"], ["argparse", "json"])
        self.assertEqual(result["fresh_edges"], 1)

    def test_blank_source_edge_is_dropped_and_counted(self) -> None:
        fresh = {
            "nodes": [_ast_node("a::fresh", "a.py")],
            "edges": [
                _ast_edge("a::fresh", "stable::f", "a.py"),
                {
                    **_ast_edge("a::fresh", "stable::f", ""),
                    "relation": "imports",
                },
            ],
            "failed_sources": [],
        }
        result = owner.merge_candidate(
            _base_graph(), fresh, {"a.py"}, source_root=self.fixture.source
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["dropped_unresolvable_edges"], 1)
        self.assertEqual(result["fresh_edges"], 1)

    def test_node_and_edge_shrink_are_independently_refused(self) -> None:
        base = _base_graph()
        node_shrink = owner.merge_candidate(
            base,
            {
                "nodes": [],
                "edges": [],
                "failed_sources": [],
            },
            {"a.py"},
            source_root=self.fixture.source,
        )
        self.assertIn("omitted", node_shrink["error"])
        two_old = json.loads(json.dumps(base))
        two_old["nodes"].append(_ast_node("a::old2", "a.py"))
        two_old["links"].append(_ast_edge("a::old2", "stable::f", "a.py"))
        node_result = owner.merge_candidate(
            two_old,
            Fixture.fresh(),
            {"a.py"},
            source_root=self.fixture.source,
        )
        self.assertEqual(node_result["error"], "candidate_node_shrink_refused")
        edge_heavy = json.loads(json.dumps(base))
        edge_heavy["links"].append(
            {
                **_ast_edge("a::old", "semantic::a", "a.py"),
                "relation": "uses",
            }
        )
        edge_result = owner.merge_candidate(
            edge_heavy,
            Fixture.fresh(),
            {"a.py"},
            source_root=self.fixture.source,
        )
        self.assertEqual(edge_result["error"], "candidate_edge_shrink_refused")

    def test_stage_paths_are_strict_and_success_cannot_be_reused(self) -> None:
        self.fixture.modify_a()
        inside = owner.run_stage(
            source_root=self.fixture.source,
            graph_path=self.fixture.graph,
            manifest_path=self.fixture.manifest,
            stage_dir=self.fixture.source / "stage",
            extract_fn=_fake(Fixture.fresh()),
            backend_name="fake-path-extractor",
        )
        self.assertEqual(inside["reason"], "stage_path_overlap_refused")
        output_child = owner.run_stage(
            source_root=self.fixture.source,
            graph_path=self.fixture.graph,
            manifest_path=self.fixture.manifest,
            stage_dir=self.fixture.output / "stage",
            extract_fn=_fake(Fixture.fresh()),
            backend_name="fake-path-extractor",
        )
        self.assertEqual(output_child["reason"], "stage_path_overlap_refused")
        first = self._run("single-use")
        self.assertEqual(first["outcome"], "staged")
        second = self._run("single-use")
        self.assertEqual(second["reason"], "stage_dir_must_not_exist")

    def test_backend_identity_enforced_and_fake_is_labeled(self) -> None:
        self.fixture.modify_a()
        unlabeled = owner.run_stage(
            source_root=self.fixture.source,
            graph_path=self.fixture.graph,
            manifest_path=self.fixture.manifest,
            stage_dir=self.fixture.stage("unlabeled"),
            extract_fn=_fake(Fixture.fresh()),
        )
        self.assertEqual(unlabeled["reason"], "fake_backend_must_be_plainly_labeled")
        with mock.patch.object(
            owner.importlib.metadata, "version", return_value="0.9.44"
        ):
            wrong = owner.run_stage(
                source_root=self.fixture.source,
                graph_path=self.fixture.graph,
                manifest_path=self.fixture.manifest,
                stage_dir=self.fixture.stage("wrong-version"),
            )
        self.assertIn("version_mismatch", wrong["reason"])


class PublicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = _tempdir()
        self.fixture = Fixture(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _stage(self, name: str = "publish-stage") -> tuple[dict, bytes, bytes]:
        self.fixture.modify_a()
        graph_bytes = self.fixture.graph.read_bytes()
        manifest_bytes = self.fixture.manifest.read_bytes()
        staged = owner.run_stage(
            source_root=self.fixture.source,
            graph_path=self.fixture.graph,
            manifest_path=self.fixture.manifest,
            stage_dir=self.fixture.stage(name),
            extract_fn=_fake(Fixture.fresh()),
            backend_name="fake-publish-extractor",
        )
        self.assertEqual(staged["outcome"], "staged")
        return staged, graph_bytes, manifest_bytes

    def _publish(self, name: str = "publish-stage") -> dict:
        return owner.run_publish(
            source_root=self.fixture.source,
            graph_path=self.fixture.graph,
            manifest_path=self.fixture.manifest,
            stage_dir=self.fixture.stage(name),
        )

    def test_publish_applies_verified_batch_with_rollback_preimages(self) -> None:
        _, graph_bytes, manifest_bytes = self._stage()
        result = self._publish()
        self.assertEqual(result["outcome"], "published")
        self.assertTrue(result["full_graph_freshness_claimed"])
        stage = self.fixture.stage("publish-stage")
        self.assertEqual((stage / "rollback_graph.preimage").read_bytes(), graph_bytes)
        self.assertEqual((stage / "rollback_manifest.preimage").read_bytes(), manifest_bytes)
        self.assertNotEqual(self.fixture.graph.read_bytes(), graph_bytes)
        self.assertNotEqual(self.fixture.manifest.read_bytes(), manifest_bytes)

    def test_publish_refuses_failed_baseline_and_stale_source(self) -> None:
        _, graph_bytes, manifest_bytes = self._stage("baseline")
        self.fixture.graph.write_bytes(graph_bytes + b" ")
        baseline = self._publish("baseline")
        self.assertEqual(baseline["reason"], "publication_baseline_drift")
        self.assertEqual(self.fixture.manifest.read_bytes(), manifest_bytes)
        self.fixture.graph.write_bytes(graph_bytes)
        _, _, _ = self._stage("stale-source")
        _write(self.fixture.a, "def changed_again():\n    return 3\n")
        stale = self._publish("stale-source")
        self.assertEqual(stale["reason"], "publication_source_drift")

    def test_publish_refuses_corrupt_stage_and_escaped_path(self) -> None:
        self._stage("corrupt")
        proof_path = self.fixture.stage("corrupt") / "proof.json"
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        proof["receipt"]["staged_graph_sha256"] = "0" * 64
        proof_path.write_text(json.dumps(proof), encoding="utf-8")
        corrupt = self._publish("corrupt")
        self.assertEqual(corrupt["reason"], "stage_hash_mismatch")
        escaped = owner.run_publish(
            source_root=self.fixture.source,
            graph_path=self.fixture.graph,
            manifest_path=self.fixture.manifest,
            stage_dir=self.fixture.source / "escape",
        )
        self.assertEqual(escaped["reason"], "stage_path_invalid")

    def test_cli_publish_missing_paths_fails_closed(self) -> None:
        argv = [
            "--mode", "publish",
            "--source-root", "missing",
            "--graph", "missing-graph",
            "--manifest", "missing-manifest",
            "--stage-dir", "missing-stage",
        ]
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = owner.main(argv)
        payload = json.loads(stream.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["reason"], "source_root_missing_or_not_directory")

    def test_cli_publish_success_outcomes_exit_zero(self) -> None:
        argv = [
            "--mode", "publish",
            "--source-root", "source",
            "--graph", "graph.json",
            "--manifest", "manifest.json",
            "--stage-dir", "stage",
        ]
        for outcome in ("published", "published_with_backlog"):
            stream = io.StringIO()
            with (
                mock.patch.object(owner, "run_publish", return_value={"outcome": outcome}),
                contextlib.redirect_stdout(stream),
            ):
                code = owner.main(argv)
            self.assertEqual(code, 0, outcome)
            self.assertEqual(json.loads(stream.getvalue())["outcome"], outcome)


if __name__ == "__main__":
    unittest.main()
