import time


def fetch_with_retry(fetch, attempts=3, sleep=None):
    """Call fetch() up to ``attempts`` times, retrying on OSError.

    Returns the first successful result. Only OSError (including
    subclasses such as ConnectionError and TimeoutError) triggers a
    retry, with exponential-backoff delays of 1, 2, 4, ... seconds
    capped at 8 via ``sleep`` (defaults to time.sleep). No sleep
    occurs after the final failed attempt; the last OSError is
    re-raised. Any non-OSError exception propagates immediately.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    if sleep is None:
        sleep = time.sleep
    delay = 1
    for attempt in range(attempts):
        try:
            return fetch()
        except OSError:
            if attempt == attempts - 1:
                raise
            sleep(delay)
            delay = min(delay * 2, 8)
