import re

_PART = re.compile(r"(\d+)([hms])")


def parse_duration(text):
    """Parse "1h30m", "45s", "2h5s" and similar into seconds.

    Units are h, m and s; each appears at most once and in that order (h before m
    before s). No whitespace is allowed anywhere. Raises ValueError for empty,
    malformed or out-of-order input.
    """
    if not re.fullmatch(r"(\d+h)?(\d+m)?(\d+s)?", text):
        raise ValueError(f"bad duration: {text!r}")
    return sum(int(n) * {"h": 3600, "m": 60, "s": 1}[u] for n, u in _PART.findall(text))
