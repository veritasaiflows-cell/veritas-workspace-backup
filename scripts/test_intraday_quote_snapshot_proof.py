import unittest
from unittest import mock

import requests

import intraday_quote_snapshot_proof as quote_proof


class AlertSymbolSelectionTests(unittest.TestCase):
    def test_explicit_alert_symbols_are_required(self) -> None:
        with self.assertRaisesRegex(quote_proof.BlockedRun, "explicit_active_alert_symbols_required"):
            quote_proof.load_symbols(None)

    def test_explicit_alert_symbols_are_normalized_without_legacy_sources(self) -> None:
        symbols, selection = quote_proof.load_symbols(["nvda", " GOOG ", "NVDA"])

        self.assertEqual(symbols, ["NVDA", "GOOG"])
        self.assertEqual(
            selection,
            {
                "policy": "explicit_active_alert_symbols_only",
                "source_contract": "caller_supplied_active_alert_scope",
                "requested_symbol_count": 2,
            },
        )


class ProviderRetryTests(unittest.TestCase):
    def _retry(self, side_effect, *, attempts=3):
        log: list[dict] = []
        with mock.patch.object(quote_proof, "fetch_snapshots", side_effect=side_effect) as fetch, \
                mock.patch.object(quote_proof.time, "sleep") as sleep:
            try:
                result = quote_proof.fetch_snapshots_with_retry(
                    ["NVDA"], 15, "iex", attempts=attempts, backoff_seconds=2.0, log=log
                )
            except requests.RequestException as exc:
                return None, log, fetch, sleep, exc
            return result, log, fetch, sleep, None

    def test_transient_transport_failure_recovers_on_retry(self) -> None:
        result, log, fetch, _, exc = self._retry(
            [requests.ConnectionError("network down"), (200, {"NVDA": {}})]
        )

        self.assertIsNone(exc)
        self.assertEqual(result, (200, {"NVDA": {}}))
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual([entry["outcome"] for entry in log], ["transport_error", "completed"])
        self.assertEqual(log[0]["error_type"], "ConnectionError")

    def test_exhausted_transport_failures_reraise_and_preserve_log(self) -> None:
        result, log, fetch, _, exc = self._retry(requests.ConnectionError("network down"))

        self.assertIsNone(result)
        self.assertIsInstance(exc, requests.ConnectionError)
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(len(log), 3)
        self.assertTrue(all(entry["outcome"] == "transport_error" for entry in log))

    def test_transient_provider_status_is_retried(self) -> None:
        result, log, fetch, _, _ = self._retry([(503, {}), (200, {"NVDA": {}})])

        self.assertEqual(result, (200, {"NVDA": {}}))
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(log[0]["outcome"], "retryable_provider_status")
        self.assertEqual(log[0]["status_code"], 503)

    def test_non_retryable_status_fails_closed_without_retry(self) -> None:
        result, log, fetch, _, _ = self._retry([(403, {})])

        self.assertEqual(result, (403, {}))
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(log, [{"attempt": 1, "outcome": "completed", "status_code": 403}])

    def test_all_attempts_retryable_returns_last_status_without_stale_exception(self) -> None:
        result, log, fetch, _, exc = self._retry(
            [requests.ConnectionError("down"), (503, {}), (503, {})]
        )

        self.assertIsNone(exc)
        self.assertEqual(result, (503, {}))
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(
            [entry["outcome"] for entry in log],
            ["transport_error", "retryable_provider_status", "retryable_provider_status"],
        )

    def test_single_attempt_makes_no_retry(self) -> None:
        result, _, fetch, sleep, _ = self._retry([(200, {"NVDA": {}})], attempts=0)

        self.assertEqual(result, (200, {"NVDA": {}}))
        self.assertEqual(fetch.call_count, 1)
        sleep.assert_not_called()

    def test_backoff_is_exponential_and_skipped_after_final_attempt(self) -> None:
        _, _, fetch, sleep, _ = self._retry(requests.ConnectionError("down"))

        self.assertEqual(fetch.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2.0, 4.0])


if __name__ == "__main__":
    unittest.main()
