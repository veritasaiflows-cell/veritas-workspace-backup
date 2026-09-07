"""Full guard-positive SYNTHETIC test fixture. Never read/copy production SQL.

No CLI, provider or activation entry point. Callers supply an empty temporary
directory; no authority derives from these invented records.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from finance_sql_canon_access import UniverseMembershipRecord, REFERENCE_LEVEL_LINEAGE_FIELDS
from alerts_os_sql_retirement_policy import AUDITED_INITIAL_RECORD_COUNT


def _json(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def build_fixture(root: Path) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("synthetic_fixture_requires_empty_directory")
    db = root / "state/finance/finance-canon.sqlite"
    db.parent.mkdir(parents=True)
    numeric = [dict(ticker=f"S{i:03d}", reference_price_low=100.0,
                    reference_price_high=110.0, reference_invalidation_level=90.0,
                    reference_confidence=70) for i in range(200)]
    projection_hash = hashlib.sha256(_json(numeric).encode()).hexdigest()
    authority = dict(numeric_values_changed=False, original_provenance_invented=False,
                     portfolio_or_account_state_maintained=False, capital_or_order_authority=False,
                     execution_allowed=False)
    baseline = dict(rows=numeric, numeric_projection_sha256=projection_hash, authority=authority)
    records = [dict(consumer_path=f"scripts/wf67_synthetic_{i:03d}.py", retired_by_this_migration=True)
               for i in range(AUDITED_INITIAL_RECORD_COUNT)]
    manifest = dict(schema="veritas.alerts_os_consumer_retirement_manifest.v1",
                    record_count=len(records), retired_by_this_migration_count=len(records),
                    records=records, record_set_sha256=hashlib.sha256(_json(records).encode()).hexdigest(),
                    authority=dict(active_dispatch_allowed=False, capital_or_order_authority=False, execution_allowed=False))
    def artifact(label, value):
        raw = _json(value).encode()
        digest = hashlib.sha256(raw).hexdigest()
        name = f"sources/{label}-{digest}.json"
        (root / name).parent.mkdir(exist_ok=True)
        (root / name).write_bytes(raw)
        return name, digest
    bp, bh = artifact("baseline", baseline)
    mp, mh = artifact("retirement", manifest)
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        created = set()
        def insert(name, row):
            if name not in created:
                conn.execute(f"CREATE TABLE {name} ({','.join(row)})")
                created.add(name)
            values = [_json(v) if isinstance(v, (list, dict)) else v for v in row.values()]
            conn.execute(f"INSERT INTO {name} ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", values)
        identity = {"ticker", "name", "instrument_type", "sector", "industry", "yfinance_symbol", "sec_cik", "company_ir", "active"}
        for i, n in enumerate(numeric):
            ticker = n["ticker"]
            tier = "A" if i == 0 else "B" if i == 1 else "C"
            member = UniverseMembershipRecord(ticker=ticker, name="Synthetic", instrument_type="test",
                sector=None, industry=None, yfinance_symbol=ticker, sec_cik=None, company_ir=None,
                active=True, universe_scope="synthetic", tier=tier, coverage_obligation_tier=tier,
                monitoring_role="monitor", production_scope_member=False, production_scope_source=None,
                sql_tier=f"Tier {tier}", sql_tier_state="current", tier_decision_scope="test",
                review_100_monitor=False, decision_grade_eligible=i != 1, source_open_required=False,
                promotion_required_before_action=False, raw_json={})
            all_fields = asdict(member)
            insert("securities", {k:v for k,v in all_fields.items() if k in identity})
            insert("universe_membership", {k:v for k,v in all_fields.items() if k not in identity or k=="ticker"})
            insert("answer_path_scope", dict(ticker=ticker, answer_scope="alert_recommendation_review", production_card_generation_allowed=0))
            insert("evidence_status", dict(ticker=ticker, customer_output_allowed=0, paper_or_live_execution_allowed=0,
                  recommendation_fields_allowed=0, has_production_card=0, card_path=None))
            common = dict(source_artifact_path=bp, source_artifact_sha256=bh, source_generated_at_utc="2026-09-05T00:00:00Z",
                          authority_class="review_only", fallback_rule="none")
            insert("reference_levels", dict(**n, reference_band_status="synthetic", **common, raw_json={}))
            insert("evidence_freshness", dict(ticker=ticker, resolution_state="missing", required_depth="synthetic",
                card_generated_at_utc=None, card_missing_or_stale_count=1, stale_families_json="[]", source_confidence_class="low",
                **common, raw_json={}))
            for family, fields in (("reference_levels", sorted(REFERENCE_LEVEL_LINEAGE_FIELDS)),
                    ("evidence_freshness", ["card_generated_at_utc", "required_depth", "resolution_state", "stale_families"])):
                for field in fields:
                    insert("source_lineage", dict(scope="ticker", scope_key=ticker, field_family=family,
                        field_name=field, **common, source_status="ok", validator_status="ok", inserted_at_utc="2026-09-05T00:00:00Z"))
        for i in range(400):
            retired = i < len(records)
            path = records[i]["consumer_path"] if retired else f"scripts/synthetic_consumer_{i}.py"
            insert("consumer_migration_registry", dict(consumer_path=path, priority="P3" if retired else "P0",
                migration_lane="retired_historical_no_dispatch" if retired else "answer_path_parity_lane",
                cutover_state="retired_alerts_os_pivot" if retired else "sql_primary_guarded",
                fallback_required=0, parity_required=0, raw_sql_needs_review=0,
                source_artifact_path=mp, source_artifact_sha256=mh))
        conn.execute("CREATE TABLE tier_routing_state (ticker,auto_tier,auto_state,capital_deployment_approved,trade_or_execution_approved)")
        conn.execute("CREATE TABLE authority_events (event)")
        conn.execute("CREATE TABLE migration_validation_runs (run)")
        conn.execute("CREATE VIEW current_sql_canon_routing AS SELECT * FROM universe_membership")
        for key, val in (
            ("alerts_os_reference_baseline_v1", dict(path=bp, sha256=bh, numeric_projection_sha256=projection_hash,
                row_count=200, lifecycle="immutable_active_alert_reference_baseline")),
            ("alerts_os_consumer_retirement_manifest_v1", dict(path=mp, sha256=mh, record_count=len(records),
                retired_by_this_migration_count=len(records), lifecycle="immutable_historical_lifecycle_proof_no_dispatch_authority")),
            ("canon_owner_field_families_v1", {"field_families":[]})):
            insert("finance_state_meta", dict(key=key, value=_json(val)))
        conn.commit()
    finally:
        conn.close()
    return db
