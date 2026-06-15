import json
import sqlite3
import time
import argparse
from pathlib import Path
import datetime
import sys

ROOT = Path(__file__).parent.parent
TMP_DIR = ROOT / 'tmp'
JSON_INDEX = TMP_DIR / 'workflow-routing-index.json'
SQLITE_DB = TMP_DIR / 'workflow-routing-index.sqlite'
OUTPUT_JSON = TMP_DIR / 'wf73-efficiency-scorecard.json'

def measure_time(func):
    start = time.perf_counter()
    res = func()
    end = time.perf_counter()
    return res, (end - start) * 1000

def run_scorecard(write=False, validate=False):
    status = "baseline_captured"
    metrics = {}
    coverage = {}

    if not JSON_INDEX.exists() or not SQLITE_DB.exists():
        status = "blocked_missing_dependencies"
        payload = {
            "schema": "wf73.efficiency_scorecard.v1",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": status,
            "error": f"Missing one or both routing indexes. Expected: {JSON_INDEX.name} and {SQLITE_DB.name}"
        }
    else:
        # 1. JSON Metrics
        def load_json():
            with open(JSON_INDEX, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        json_data, json_load_ms = measure_time(load_json)
        
        # Estimate route count
        json_routes = len(json_data.get('routes', json_data)) if isinstance(json_data, dict) else len(json_data)
        
        def search_json():
            # Dummy search to simulate finding a route
            if isinstance(json_data, dict) and 'routes' in json_data:
                return [r for r in json_data['routes'] if 'WF' in str(r)]
            elif isinstance(json_data, list):
                return [r for r in json_data if 'WF' in str(r)]
            elif isinstance(json_data, dict):
                return [k for k, v in json_data.items() if 'WF' in str(k)]
            return []
            
        _, json_search_ms = measure_time(search_json)

        # 2. SQLite Metrics
        def query_sqlite():
            conn = sqlite3.connect(SQLITE_DB)
            cursor = conn.cursor()
            
            main_table = "workflow_routes"
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {main_table}")
                count = cursor.fetchone()[0]
            except Exception:
                count = 0
            
            # Dummy query to simulate route lookup
            try:
                cursor.execute(f"SELECT * FROM {main_table} LIMIT 1")
                cursor.fetchall()
            except:
                pass
                
            conn.close()
            return count

        sqlite_routes, sqlite_query_ms = measure_time(query_sqlite)

        metrics = {
            "json_load_ms": round(json_load_ms, 3),
            "json_search_ms": round(json_search_ms, 3),
            "sqlite_full_cycle_ms": round(sqlite_query_ms, 3),
            "speedup_multiplier": round((json_load_ms + json_search_ms) / sqlite_query_ms, 2) if sqlite_query_ms > 0 else 0
        }
        
        coverage = {
            "json_total_routes": json_routes,
            "sqlite_total_routes": sqlite_routes,
            "coverage_match": bool(json_routes > 0 and json_routes == sqlite_routes)
        }

        payload = {
            "schema": "wf73.efficiency_scorecard.v1",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "status": status,
            "metrics": metrics,
            "coverage": coverage
        }

    if write:
        TMP_DIR.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        print(f"Wrote scorecard to tmp/{OUTPUT_JSON.name}")

    if validate:
        if status == "blocked_missing_dependencies":
            print("Validation failed: Missing dependencies.")
            print(json.dumps(payload, indent=2))
            return False
            
        print("Validation passed: Scorecard generated.")
        print(json.dumps(payload, indent=2))
        
    return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()
    
    success = run_scorecard(write=args.write, validate=args.validate)
    if not success:
        sys.exit(1)
