from __future__ import annotations

import unittest

from current_window_artifact_index import COMMON_ARTIFACTS, build_index, normalize_window


class CurrentWindowArtifactIndexTests(unittest.TestCase):
    def test_legacy_aliases_resolve_to_active_windows(self) -> None:
        self.assertEqual(normalize_window("full"), "post-close")
        self.assertEqual(normalize_window("sunday"), "weekly")

    def test_active_roles_are_alerts_os_only(self) -> None:
        text = " ".join([*COMMON_ARTIFACTS, *COMMON_ARTIFACTS.values()]).lower()
        for token in (
            "portfolio",
            "deployment",
            "position-sizing",
            "paper",
            "trade-grade",
            "wf67",
            "wf78",
            "wf86",
            "wf87",
        ):
            self.assertNotIn(token, text)

    def test_post_close_index_uses_active_chain_and_digest(self) -> None:
        payload = build_index("post-close")
        roles = {row["role"]: row["path"] for row in payload["artifacts"]}
        self.assertEqual(roles["alerts_recommendations_chain"], "tmp/alerts-recommendations-chain-post-close.json")
        self.assertEqual(roles["recommendation_digest"], "tmp/finance-alert-os-post-close-digest.json")
        self.assertEqual(payload["rendered_outputs"]["json"], "tmp/current-window-artifacts.json")
        self.assertFalse(payload["authority"]["maintains_finance_state"])
        self.assertFalse(payload["authority"]["capital_or_execution_authority"])


if __name__ == "__main__":
    unittest.main()
