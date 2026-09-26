def dedupe_by_key(rows, key):
    """Remove rows whose value for `key` was already seen.

    Keeps the first occurrence of each value and the original order. Rows that do not
    have `key` at all are always kept. The input list is not modified.
    """
    seen, out = set(), []
    for row in rows:
        if key not in row:
            continue
        if row[key] in seen:
            continue
        seen.add(row[key])
        out.append(row)
    return out
