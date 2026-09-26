def fetch_with_retry(fetch, attempts=3, sleep=None):
    """Call fetch() and return its result."""
    return fetch()
