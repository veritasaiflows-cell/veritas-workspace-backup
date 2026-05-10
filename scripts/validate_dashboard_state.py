from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from generate_dashboard import TMP, build_payload, load_sources, write_json

OUT_PATH = TMP / "dashboard-validation.json"
SCHEMA_VERSION = 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dashboard trust and integrity state without rendering HTML.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on warnings as well as critical issues.")
    parser.add_argument("--write", action="store_true", help="Write tmp/dashboard-validation.json with the current validation block.")
    args = parser.parse_args()

    sources = load_sources()
    payload = build_payload(sources)
    validation = payload["validation"]
    trust = payload["trust"]

    source_freshness = payload.get("source_freshness") or trust.get("source_freshness") or {}
    print(f"overall_exec_status: {payload['exec_freshness']}")
    print(f"source_freshness: {source_freshness.get('overall_classification', 'unknown')} / {source_freshness.get('trust_level', 'unknown')}")
    print(f"integrity: {validation['summary']['critical']} critical, {validation['summary']['warning']} warning")
    print("source_statuses:")
    for source in trust["sources"]:
        tags = f" tags={','.join(source['tags'])}" if source["tags"] else ""
        print(f"  - {source['label']}: {source['status']}{tags}")
    if trust["manual_dependencies"]:
        print("manual_dependencies:")
        for dep in trust["manual_dependencies"]:
            print(f"  - [{dep['status']}] {dep['label']}: {dep['detail']}")
    if validation["warnings"]:
        print("warnings:")
        for warning in validation["warnings"]:
            ticker = f" ({warning['ticker']})" if warning.get("ticker") else ""
            print(f"  - [{warning['severity']}] {warning['code']}{ticker}: {warning['message']}")
    else:
        print("warnings:\n  - none")

    if args.write:
        validation_output = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "stale_after_hours": 8,
            "source_freshness": source_freshness,
            **validation,
        }
        write_json(OUT_PATH, validation_output)
        print(f"wrote {OUT_PATH}")

    if validation["summary"]["critical"]:
        return 2
    if args.strict and validation["summary"]["warning"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
