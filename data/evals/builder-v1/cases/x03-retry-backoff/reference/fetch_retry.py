import time


def fetch_with_retry(fetch, attempts=3, sleep=None):
    """Call fetch() with retries on OSError and return its result."""
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    sleep = sleep or time.sleep
    delay = 1
    for attempt in range(1, attempts + 1):
        try:
            return fetch()
        except OSError:
            if attempt == attempts:
                raise
            sleep(delay)
            delay = min(delay * 2, 8)
