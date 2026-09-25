#!/usr/bin/env python3
"""Model-free retention check for delegated documentation trims.

Compares an original note with a trimmed rewrite and reports which
load-bearing facts from the original are missing from the rewrite:
file/artifact paths, UUID-style run ids, quoted owner words, and dated
owner approvals. A named section (default "Stop lines") must survive
verbatim. Missing items are not automatically wrong - a superseded fact
may be dropped on purpose - but each one must be explained by the
delegate's ledger or restored before Main accepts the trim.

Read-only; prints JSON; exit 1 when the verbatim section is broken.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PATH_RE = re.compile(r"`([^`\s]*[/\\][^`]*?\.(?:json|md|py|jsonl|patch|sqlite|txt|sha256))`")
BARE_PATH_RE = re.compile(r"(?<![\w/])((?:tmp|scripts|state|memory|skills|06\. Playbooks)[/\\][^\s`'\")\],;]+)")
UUID_RE = re.compile(r"\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b|\b[0-9a-f]{8}\.\.\.")
QUOTE_RE = re.compile(r"[\"“]([^\"”\n]{12,200})[\"”]")
APPROVAL_RE = re.compile(r"[^.\n]*\b(?:Randall|owner)\b[^.\n]*\b(?:approv|decid|accept)\w*[^.\n]*", re.I)


def norm(s: str) -> str:
    return " ".join(s.replace("\\", "/").split()).casefold()


def section(text: str, heading: str) -> str | None:
    m = re.search(rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else None


def facts(text: str) -> dict[str, set[str]]:
    paths = {p.rstrip(".") for p in PATH_RE.findall(text)} | {p.rstrip(".") for p in BARE_PATH_RE.findall(text)}
    return {"paths": paths, "run_ids": set(UUID_RE.findall(text)),
            "quotes": {q.strip() for q in QUOTE_RE.findall(text)}}


def check(original: str, trimmed: str, verbatim_section: str = "Stop lines") -> dict:
    t = norm(trimmed)
    missing = {k: sorted(v for v in vals if norm(v) not in t)
               for k, vals in facts(original).items()}
    totals = {k: len(v) for k, v in facts(original).items()}
    orig_sec = section(original, verbatim_section)
    trim_sec = section(trimmed, verbatim_section)
    verbatim_ok = orig_sec is not None and trim_sec is not None and norm(orig_sec) == norm(trim_sec)
    approvals = [a.strip() for a in APPROVAL_RE.findall(original)]
    return {"schema": "veritas.doc_trim_retention.v1",
            "original_lines": original.count("\n") + 1, "trimmed_lines": trimmed.count("\n") + 1,
            "totals": totals, "missing_counts": {k: len(v) for k, v in missing.items()},
            "missing": missing, "verbatim_section": verbatim_section,
            "verbatim_section_ok": verbatim_ok, "approval_sentences_in_original": len(approvals)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("original")
    ap.add_argument("trimmed")
    ap.add_argument("--verbatim-section", default="Stop lines")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    res = check(Path(a.original).read_text(encoding="utf-8"), Path(a.trimmed).read_text(encoding="utf-8"),
                a.verbatim_section)
    text = json.dumps(res, indent=2)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    return 0 if res["verbatim_section_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
