from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from generate_dashboard import TMP, build_payload, load_sources, write_json

OUT_PATH = TMP / "dashboard-validation.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dashboard trust and integrity state without rendering HTML.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on warnings as well as critical issues.")
    parser.add_argument("--write", action="store_true", help="Write tmp/dashboard-validation.json with the current validation block.")
    args = parser.parse_args()

    sources = load_sources()
    payload = build_payload(sources)
    validation = payload["validation"]
    trust = payload["trust"]

    print(f"overall_exec_status: {payload['exec_freshness']}")
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
        write_json(OUT_PATH, validation)
        print(f"wrote {OUT_PATH}")

    if validation["summary"]["critical"]:
        return 2
    if args.strict and validation["summary"]["warning"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
