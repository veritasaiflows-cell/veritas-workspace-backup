#!/usr/bin/env python3
from __future__ import annotations

import unittest

import graphify_selective_provenance_repair as repair


class SelectiveGraphifyRepairTests(unittest.TestCase):
    def test_plan_replaces_only_the_audited_sources_with_traceable_edges(self) -> None:
        original = repair.read_json(repair.DEFAULT_INPUT)
        plan = repair.read_json(repair.DEFAULT_PLAN)
        extraction, metadata, repaired_batch = repair.build_repaired_extraction(original, plan)
        graph, analysis, _report = repair.rebuild_graph(repair.DEFAULT_OUT, extraction, write_graph=False)
        communities = {int(key): value for key, value in analysis["communities"].items()}
        metrics = repair.extraction_metrics(extraction, communities)

        self.assertEqual(len(repaired_batch), 7)
        self.assertEqual(len(plan["selective_sources"]), 13)
        self.assertEqual(metrics["document_coverage"], 51)
        self.assertEqual(metrics["unknown_source_nodes"], 0)
        self.assertEqual(metrics["unknown_source_edges"], 0)
        self.assertEqual(metrics["missing_edge_endpoints"], 0)
        self.assertEqual(metrics["predicate_status_conflicts"], 0)
        self.assertEqual(metrics["unclustered_nodes"], 0)
        self.assertEqual(len(metadata["enrichment_added"]), 5)
        self.assertEqual(metadata["quarantined_edges"], [])
        self.assertEqual(len(graph["nodes"]), metrics["nodes"])
        self.assertEqual(len(graph["links"]), metrics["edges"])

        for edge in extraction["edges"]:
            self.assertTrue(str(edge["source_file"]).startswith("skills/"))
            self.assertIn("source_location", edge)
            self.assertEqual(edge["relation"], edge["predicate"])
            self.assertEqual(edge["confidence"], edge["extraction_status"])

    def test_fusion_semantic_gaps_do_not_become_graph_claims(self) -> None:
        self.assertEqual(
            repair.FUSION_SEMANTIC_GAPS[
                "Trace an agent improvement from proposal through QA and promotion."
            ],
            "no_explicit_improvement_to_workspace_qa_to_promotion_to_memory_path",
        )
        self.assertEqual(
            repair.FUSION_SEMANTIC_GAPS["How does retrieval refresh affect routing?"],
            "no_explicit_retrieval_refresh_to_routing_relation",
        )


if __name__ == "__main__":
    unittest.main()
