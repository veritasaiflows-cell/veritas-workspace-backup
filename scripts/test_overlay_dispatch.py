"""Board 3 overlay dispatch preview tests (stdlib only, hermetic).

Covers the four Board 3 gates:
  1. 12/12 merges byte-stable across two runs
  2. T4 fixture mappings resolve
  3. denylist enforced (hidden bank / keys / traces unreachable in preview)
  4. gate refusal while dispatch_ready is false

Offline: no network, no model call, no dispatch. The BANK is only read; every
write goes to a fresh temporary directory. Bytecode writing is disabled before
any import so this suite cannot add files under scripts/.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True  # never leave a .pyc beside the source tree

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

BANK = REPO / "data" / "evals" / "model-arena" / "arena-agentic-v1-20260920"
AUTH_PATH = BANK / "overlay" / "dispatch-authorization.json"

import arena_overlay_dispatch as D  # noqa: E402


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MergeDeterminismTest(unittest.TestCase):
    """Gate 1: all 12 cases merge, byte-identical across two runs."""

    def test_twelve_merges_byte_stable(self):
        ctx = D.load_context(BANK, Path("unused"))
        families = D.check_overlay_binding(ctx)
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            manifest_a = D.merge(ctx, families, Path(a))
            manifest_b = D.merge(ctx, families, Path(b))
            self.assertEqual(manifest_a["counts"]["merged_written"], 12)
            self.assertEqual(len(manifest_a["cases"]), 12)
            # every bank case produced a file
            self.assertEqual(
                sorted(r["instance_id"] for r in manifest_a["cases"]),
                sorted(c["instance_id"] for c in ctx["hidden"]["cases"]),
            )
            for row in manifest_a["cases"]:
                fa = Path(a) / row["txt_path"]
                fb = Path(b) / row["txt_path"]
                self.assertTrue(fa.exists(), row["txt_path"])
                self.assertTrue(fb.exists(), row["txt_path"])
                self.assertEqual(_sha(fa), _sha(fb), "byte drift: " + row["txt_path"])
                self.assertEqual(_sha(fa), row["merged_sha256"], row["txt_path"])
            # manifests themselves are identical
            self.assertEqual(
                json.dumps(manifest_a, sort_keys=True),
                json.dumps(manifest_b, sort_keys=True),
            )

    def test_merge_carries_family_contract_and_not_key(self):
        ctx = D.load_context(BANK, Path("unused"))
        families = D.check_overlay_binding(ctx)
        hmap = {c["instance_id"]: c for c in ctx["hidden"]["cases"]}
        with tempfile.TemporaryDirectory() as a:
            manifest = D.merge(ctx, families, Path(a))
            for row in manifest["cases"]:
                text = (Path(a) / row["txt_path"]).read_text(encoding="utf-8")
                self.assertIn("response contract:", text)
                self.assertIn(
                    families[row["family"]]["contract_text"], text, row["instance_id"]
                )
                key_blob = json.dumps(
                    hmap[row["instance_id"]]["key"],
                    sort_keys=True,
                    separators=(",", ":"),
                )
                self.assertNotIn(key_blob, text)
                for token in D.FORBIDDEN_VISIBLE_SUBSTRINGS:
                    self.assertNotIn(token, text)


class FixtureMappingTest(unittest.TestCase):
    """Gate 2: both T4 fixture sets resolve to materialised, byte-verified paths."""

    def test_both_sets_resolve(self):
        ctx = D.load_context(BANK, Path("unused"))
        D.check_overlay_binding(ctx)
        with tempfile.TemporaryDirectory() as out:
            report = D.fixtures(ctx, Path(out))
            self.assertEqual(report["fixture_sets_in_bank"], report["fixture_sets_referenced"])
            self.assertTrue(report["all_referenced_resolved"])
            self.assertEqual(sorted(report["mapping"]), ["fs-194d6799d314b290", "fs-8c44f4aaca482291"])
            for set_id, entry in report["mapping"].items():
                materialised = [f for f in entry["files"] if f["materialised"]]
                self.assertTrue(materialised, set_id)
                for row in materialised:
                    path = Path(out) / D.MOUNT_DIRNAME / D.FIXTURE_DIRNAME / set_id / row["relpath"]
                    self.assertTrue(path.exists(), str(path))
                    self.assertEqual(_sha(path), row["sha256"], str(path))
                    self.assertEqual(len(path.read_bytes()), row["bytes"])
                # start_path presence semantics differ per set by design
                if set_id == "fs-194d6799d314b290":
                    self.assertTrue(entry["start_path_present"])
                    self.assertEqual(entry["missing_paths"], [])
                else:
                    self.assertFalse(entry["start_path_present"])
                    self.assertEqual(entry["missing_paths"], ["recovery/primary.json"])

    def test_control_fields_never_materialise(self):
        ctx = D.load_context(BANK, Path("unused"))
        with tempfile.TemporaryDirectory() as out:
            D.fixtures(ctx, Path(out))
            root = Path(out) / D.MOUNT_DIRNAME / D.FIXTURE_DIRNAME
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                blob = path.read_text(encoding="utf-8")
                for field in D.FIXTURE_CONTROL_FIELDS:
                    self.assertNotIn('"%s"' % field, blob, str(path))
                self.assertNotIn('"expected_trace"', blob)
                self.assertNotIn('"forbidden_reads"', blob)


class IsolationTest(unittest.TestCase):
    """Gate 3: denylist enforced; hidden bank / keys / traces unreachable."""

    def test_full_run_enforces_isolation(self):
        with tempfile.TemporaryDirectory() as out:
            summary = D.run(BANK, Path(out))
            self.assertTrue(summary["isolation"]["enforced"], summary["isolation"]["findings"])
            self.assertFalse(summary["model_callable"])
            mount = Path(out) / D.MOUNT_DIRNAME
            self.assertEqual(
                sorted(p.name for p in mount.iterdir()),
                ["candidate-visible-bank.json", "fixtures"],
            )
            # denylisted artifacts are not present anywhere in the mount
            for name in _load(BANK / "overlay" / "candidate-isolation.json")[
                "candidate_mount_denylist"
            ]:
                self.assertFalse((mount / name).exists(), name)
            # merged prompt text carries no hidden material
            hmap = {c["instance_id"]: c for c in _load(BANK / "hidden-bank.json")["cases"]}
            for txt in sorted(Path(out).glob("*.txt")):
                blob = txt.read_text(encoding="utf-8")
                for iid, case in hmap.items():
                    key_blob = json.dumps(case["key"], sort_keys=True, separators=(",", ":"))
                    self.assertNotIn(key_blob, blob)
                self.assertNotIn('"structure_id"', blob)
                self.assertNotIn('"expected_trace"', blob)
                self.assertNotIn("hidden-bank.json", blob)

    def test_isolation_fails_closed_on_injected_hidden_token(self):
        ctx = D.load_context(BANK, Path("unused"))
        D.check_overlay_binding(ctx)
        with tempfile.TemporaryDirectory() as out:
            bad = Path(out) / "leaky.txt"
            bad.write_text('case x\n"structure_id": "boom"\n', encoding="utf-8")
            with self.assertRaises(D.PreviewError):
                D.isolation(ctx, Path(out))

    def test_isolation_fails_closed_on_whole_key(self):
        ctx = D.load_context(BANK, Path("unused"))
        D.check_overlay_binding(ctx)
        key_blob = json.dumps(
            ctx["hidden"]["cases"][0]["key"], sort_keys=True, separators=(",", ":")
        )
        with tempfile.TemporaryDirectory() as out:
            (Path(out) / "leak.txt").write_text(key_blob, encoding="utf-8")
            with self.assertRaises(D.PreviewError):
                D.isolation(ctx, Path(out))


class GateRefusalTest(unittest.TestCase):
    """Gate 4: refuse to emit model-callable output while dispatch_ready=false."""

    def test_gate_refuses_and_records(self):
        with tempfile.TemporaryDirectory() as out:
            ctx = D.load_context(BANK, Path(out))
            record = D.attempt_dispatch(ctx, Path(out))
            self.assertTrue(record["refused"], record)
            self.assertIn("authorization_not_dispatch_ready", record["reason"])
            self.assertFalse(record["model_callable_output_written"])
            self.assertFalse(record["gate_mutated"])
            written = Path(out) / "gate-refusal.json"
            self.assertTrue(written.exists())
            self.assertTrue(_load(written)["refused"])

    def test_negative_proof_parity_with_frozen_runner(self):
        with tempfile.TemporaryDirectory() as out:
            ctx = D.load_context(BANK, Path(out))
            record = D.attempt_dispatch(ctx, Path(out))
            parity = record["parity"]
            self.assertTrue(parity["available"], parity)
            self.assertTrue(parity["refused"], parity)
            self.assertIn("authorization_not_dispatch_ready", parity["reason"])

    def test_gate_function_raises_directly(self):
        ctx = D.load_context(BANK, Path("unused"))
        with self.assertRaises(D.DispatchRefused):
            D.gate(ctx["authorization"], ctx["overlay"], expected_cases=12)

    def test_gate_mutates_nothing_and_stays_false(self):
        before = _sha(AUTH_PATH)
        auth_before = _load(AUTH_PATH)
        with tempfile.TemporaryDirectory() as out:
            D.run(BANK, Path(out))
        self.assertEqual(_sha(AUTH_PATH), before, "authorization file changed")
        self.assertEqual(_load(AUTH_PATH), auth_before)
        self.assertIs(_load(AUTH_PATH)["dispatch_ready"], False)

    def test_run_writes_only_under_preview_out(self):
        before = sorted(str(p) for p in BANK.rglob("*"))
        with tempfile.TemporaryDirectory() as out:
            D.run(BANK, Path(out))
            produced = sorted(p.name for p in Path(out).iterdir())
        self.assertIn("manifest.json", produced)
        self.assertIn("fixture-mapping.json", produced)
        self.assertIn("isolation-report.json", produced)
        self.assertIn("gate-refusal.json", produced)
        self.assertEqual(before, sorted(str(p) for p in BANK.rglob("*")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
