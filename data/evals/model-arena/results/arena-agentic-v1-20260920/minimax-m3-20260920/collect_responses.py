"""Collect candidate text from transport-*.json into responses.json."""
from __future__ import annotations

import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
PLAN = json.loads((RUN / "dispatch-plan.json").read_text(encoding="utf-8"))


def extract_text(doc: dict) -> str:
    payloads = ((doc.get("result") or {}).get("payloads") or [])
    if payloads:
        return payloads[0].get("text") or ""
    return ""


def main() -> int:
    mapping = {}
    missing = []
    for case in PLAN["cases"]:
        iid = case["instance_id"]
        path = RUN / f"transport-{iid}.json"
        if not path.exists():
            missing.append(iid)
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        if not raw.strip():
            mapping[iid] = ""
            continue
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError:
            mapping[iid] = ""
            continue
        mapping[iid] = extract_text(doc)
    (RUN / "responses.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"collected": len(mapping), "missing": missing}, sort_keys=True))
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
