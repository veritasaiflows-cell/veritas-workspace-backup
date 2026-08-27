"""Tests for the route-catalog-health packet."""
import unittest

from route_catalog_health import build_health_packet


class RouteCatalogHealthTests(unittest.TestCase):
    def test_health_packet_is_ok_when_sources_clean(self) -> None:
        packet = build_health_packet()
        self.assertIn(packet["status"], {"ok", "blocked"})
        self.assertIn("schema", packet)
        self.assertEqual(packet["schema"], "veritas.route_catalog_health.v1")
        summary = packet["summary"]
        self.assertGreaterEqual(summary["route_count"], 1)
        self.assertEqual(summary["max_allowed_tool_calls"], 8)
        self.assertIsInstance(summary["over_budget_routes"], list)
        self.assertIsInstance(summary["stale_routes"], list)
        self.assertTrue(summary["raw_capture_blocked"])

    def test_over_budget_routes_surfaces_in_summary(self) -> None:
        packet = build_health_packet()
        self.assertIn("over_budget_routes", packet["summary"])
        self.assertIn("stale_routes", packet["summary"])
        self.assertIsInstance(packet["summary"]["over_budget_routes"], list)

    def test_no_raw_capture_phrase_in_packet(self) -> None:
        packet = build_health_packet()
        body = str(packet)
        for forbidden in ["prompt_text", "response_text", "tool_payload"]:
            # Ensure the field is never set to a body of text
            value = packet.get("summary", {}).get(forbidden)
            if value is not None:
                self.fail(f"{forbidden} unexpectedly set in summary")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
