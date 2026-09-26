import unittest

from fetch_retry import fetch_with_retry


def flaky(errors, result="ok"):
    calls = []

    def fetch():
        calls.append(1)
        if errors:
            raise errors.pop(0)
        return result
    return fetch, calls


class Hidden(unittest.TestCase):
    def test_recovers(self):
        fetch, calls = flaky([ConnectionError(), TimeoutError()])
        slept = []
        self.assertEqual(fetch_with_retry(fetch, attempts=3, sleep=slept.append), "ok")
        self.assertEqual((len(calls), slept), (3, [1, 2]))

    def test_exhausts_and_reraises_last(self):
        last = OSError("third")
        fetch, calls = flaky([OSError("1"), OSError("2"), last])
        slept = []
        with self.assertRaises(OSError) as ctx:
            fetch_with_retry(fetch, attempts=3, sleep=slept.append)
        self.assertIs(ctx.exception, last)
        self.assertEqual((len(calls), slept), (3, [1, 2]))

    def test_non_os_error_not_retried(self):
        fetch, calls = flaky([ValueError("bad")])
        slept = []
        with self.assertRaises(ValueError):
            fetch_with_retry(fetch, attempts=5, sleep=slept.append)
        self.assertEqual((len(calls), slept), (1, []))

    def test_delay_cap(self):
        fetch, calls = flaky([OSError()] * 6)
        slept = []
        self.assertEqual(fetch_with_retry(fetch, attempts=7, sleep=slept.append), "ok")
        self.assertEqual(slept, [1, 2, 4, 8, 8, 8])

    def test_single_attempt(self):
        fetch, calls = flaky([OSError()])
        slept = []
        with self.assertRaises(OSError):
            fetch_with_retry(fetch, attempts=1, sleep=slept.append)
        self.assertEqual(slept, [])

    def test_bad_attempts(self):
        fetch, calls = flaky([])
        with self.assertRaises(ValueError):
            fetch_with_retry(fetch, attempts=0, sleep=lambda s: None)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
