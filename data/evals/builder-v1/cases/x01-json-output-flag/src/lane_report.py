import argparse
import sys


def summarize(rows):
    """rows: list of {"agent": str, "tokens": int}. Returns {agent: total_tokens}."""
    out = {}
    for row in rows:
        out[row["agent"]] = out.get(row["agent"], 0) + row["tokens"]
    return out


def render_text(summary):
    return "\n".join(f"{agent}: {tokens}" for agent, tokens in sorted(summary.items()))


def main(argv=None, rows=None, out=sys.stdout):
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-tokens", type=int, default=0)
    args = ap.parse_args(argv)
    summary = {a: t for a, t in summarize(rows or []).items() if t >= args.min_tokens}
    out.write(render_text(summary) + "\n")
    return 0
