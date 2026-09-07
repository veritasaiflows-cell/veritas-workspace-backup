from pathlib import Path

# Patch activation script for approved 7-key source-freshness extension.
p = Path('scripts/sql_canon_low_risk_phase3_activate.py')
text = p.read_text(encoding='utf-8')
text = text.replace('LOW_RISK_BOUNDARY = "phase3_sql_canon_low_risk_metadata_exact_six_keys_no_execution_authority"', 'LOW_RISK_BOUNDARY = "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority"')
old = '''APPROVED_KEYS = (
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
)
NEWLY_APPROVED_KEYS = (
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
)'''
new = '''APPROVED_KEYS = (
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
    "breadth:source_freshness_classification",
    "credit:source_freshness_classification",
    "fundamental_ir:source_freshness_classification",
    "fundamentals:source_freshness_classification",
    "market:source_freshness_classification",
    "policy:source_freshness_classification",
    "technical:source_freshness_classification",
)
NEWLY_APPROVED_KEYS = (
    "breadth:source_freshness_classification",
    "credit:source_freshness_classification",
    "fundamental_ir:source_freshness_classification",
    "fundamentals:source_freshness_classification",
    "market:source_freshness_classification",
    "policy:source_freshness_classification",
    "technical:source_freshness_classification",
)'''
if old not in text:
    raise SystemExit('approved keys block not found')
text = text.replace(old, new)
text = text.replace('''APPROVAL_TEXT = (
    "Randall approved WF72 Phase 3 activation for only four low-risk SQL-canon metadata keys: "
    "NVDA:last_earnings_date, NVDA:post_earnings_review_date, deployment:source_freshness_classification, "
    "and earnings:source_freshness_classification. Approval is limited to SQL-canon/cache activation plus "
    "rollback/export and no-drift validation, and excludes Markdown/canon/portfolio mutation, owner-approval "
    "inference, cron-direct apply, entry bands, technical state, sector/sleeve/sizing, trade/account/paper/live "
    "authority, and money movement. Proceed only after resolving or explicitly adjudicating stale "
    "tmp/deployment-readiness-surface.json artifact-index validation blocker."
)''', '''APPROVAL_TEXT = (
    "Randall explicitly approved WF72 key-level full migration and activation for the seven shadow-ready "
    "source-freshness SQL-canon metadata keys: breadth, credit, fundamental_ir, fundamentals, market, "
    "policy, and technical source_freshness_classification. Approval is limited to SQL-canon/cache "
    "activation plus rollback/export and no-drift validation for those exact keys, preserving the existing "
    "six active keys. It excludes Markdown/canon/portfolio mutation, owner-approval inference, cron-direct "
    "apply, deployment/status wording, entry bands, stops, sizing, sleeve, cash, risk-rule, trade/account/"
    "paper/live authority, credentials/config, and money movement."
)''')
text = text.replace('PLAN_JSON = TMP / "sql-canon-low-risk-shadow-activation-plan.json"', 'PLAN_JSON = TMP / "wf72-phase7-source-freshness-shadow-proof.json"')
text = text.replace('if plan.get("status") != "shadow_activation_plan_ready_review_only":\n        issues.append("shadow_activation_plan_not_ready")', 'if plan.get("status") != "shadow_ready":\n        issues.append("phase7_shadow_proof_not_ready")')
text = text.replace('if tuple(plan.get("eligible_keys") or ()) != NEWLY_APPROVED_KEYS:\n        issues.append("eligible_key_set_mismatch")', 'if tuple(plan.get("shadow_ready_keys") or ()) != NEWLY_APPROVED_KEYS:\n        issues.append("approved_shadow_key_set_mismatch")')
text = text.replace('"schema_version": "sql_canon_low_risk_phase3_approval_context.v1"', '"schema_version": "sql_canon_phase7_source_freshness_activation_approval_context.v1"')
text = text.replace('"approved_new_keys": list(NEWLY_APPROVED_KEYS),\n        "active_keys_to_preserve": ["NVDA:earnings_lifecycle_status", "NVDA:post_earnings_review_confirmed"],', '"approved_new_keys": list(NEWLY_APPROVED_KEYS),\n        "active_keys_to_preserve": [key for key in APPROVED_KEYS if key not in NEWLY_APPROVED_KEYS],')
text = text.replace('"schema_version": "sql_canon_low_risk_phase3_preactivation_export.v1"', '"schema_version": "sql_canon_phase7_source_freshness_preactivation_export.v1"')
text = text.replace('"schema_version": "sql_canon_low_risk_phase3_activation.v1"', '"schema_version": "sql_canon_phase7_source_freshness_activation.v1"')
text = text.replace('"schema_version": "sql_canon_low_risk_phase3_validation.v1"', '"schema_version": "sql_canon_phase7_source_freshness_validation.v1"')
text = text.replace('add("exact_six_keys_only", set(keys) == set(APPROVED_KEYS) and len(keys) == len(APPROVED_KEYS), str(keys))', 'add("exact_thirteen_keys_only", set(keys) == set(APPROVED_KEYS) and len(keys) == len(APPROVED_KEYS), str(keys))')
text = text.replace('add("new_four_keys_present", set(NEWLY_APPROVED_KEYS).issubset(keys), str(keys))', 'add("new_seven_keys_present", set(NEWLY_APPROVED_KEYS).issubset(keys), str(keys))')
text = text.replace('# SQL Canon Low-Risk Phase 3 Activation', '# SQL Canon Phase 7 Source-Freshness Activation')
text = text.replace('- Scope: exactly six low-risk metadata keys; four newly approved plus two preserved Phase 4A lifecycle keys.', '- Scope: exactly thirteen low-risk metadata keys; seven newly approved source-freshness keys plus six preserved metadata keys.')
text = text.replace('"schema_version": "sql_canon_low_risk_phase3_post_activation_no_drift.v1"', '"schema_version": "sql_canon_phase7_source_freshness_post_activation_no_drift.v1"')
text = text.replace('# SQL Canon Low-Risk Phase 3 Post-Activation No-Drift Proof', '# SQL Canon Phase 7 Source-Freshness Post-Activation No-Drift Proof')
text = text.replace('- Protected dashboard/Today/run-summary fingerprints are inherited from Phase 2 consumer proof; Phase 3 did not change consumer behavior.', '- Protected dashboard/Today/run-summary fingerprints are inherited from consumer proof; Phase 7 only expanded approved proof metadata keys and did not change dashboard behavior authority.')
p.write_text(text, encoding='utf-8')

# Patch consumer guard constants.
p = Path('scripts/sql_consumer_authority_guard.py')
text = p.read_text(encoding='utf-8')
text = text.replace('LOW_RISK_SQL_CANON_BOUNDARY = "phase3_sql_canon_low_risk_metadata_exact_six_keys_no_execution_authority"', 'LOW_RISK_SQL_CANON_BOUNDARY = "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority"')
old = '''LOW_RISK_APPROVED_KEYS = (
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
)'''
new = '''LOW_RISK_APPROVED_KEYS = (
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
    "breadth:source_freshness_classification",
    "credit:source_freshness_classification",
    "fundamental_ir:source_freshness_classification",
    "fundamentals:source_freshness_classification",
    "market:source_freshness_classification",
    "policy:source_freshness_classification",
    "technical:source_freshness_classification",
)'''
if old not in text: raise SystemExit('guard keys block not found')
text = text.replace(old, new)
p.write_text(text, encoding='utf-8')

# Patch dashboard payload constants and fallback values.
p = Path('scripts/dashboard_payload.py')
text = p.read_text(encoding='utf-8')
text = text.replace('PHASE4A_SQL_CANON_BOUNDARY = "phase3_sql_canon_low_risk_metadata_exact_six_keys_no_execution_authority"', 'PHASE4A_SQL_CANON_BOUNDARY = "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority"')
old = '''PHASE4A_APPROVED_KEYS = (
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
)'''
new = '''PHASE4A_APPROVED_KEYS = (
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
    "breadth:source_freshness_classification",
    "credit:source_freshness_classification",
    "fundamental_ir:source_freshness_classification",
    "fundamentals:source_freshness_classification",
    "market:source_freshness_classification",
    "policy:source_freshness_classification",
    "technical:source_freshness_classification",
)'''
if old not in text: raise SystemExit('dashboard keys block not found')
text = text.replace(old, new)
old = '''        "deployment:source_freshness_classification": get_path(source_status, "deployment.source_state.classification"),
        "earnings:source_freshness_classification": get_path(source_status, "earnings.source_state.classification"),
    })'''
new = '''        "deployment:source_freshness_classification": get_path(source_status, "deployment.source_state.classification"),
        "earnings:source_freshness_classification": get_path(source_status, "earnings.source_state.classification"),
        "breadth:source_freshness_classification": get_path(source_status, "breadth.source_state.classification"),
        "credit:source_freshness_classification": get_path(source_status, "credit.source_state.classification"),
        "fundamental_ir:source_freshness_classification": get_path(source_status, "fundamental_ir.source_state.classification"),
        "fundamentals:source_freshness_classification": get_path(source_status, "fundamentals.source_state.classification"),
        "market:source_freshness_classification": get_path(source_status, "market.source_state.classification"),
        "policy:source_freshness_classification": get_path(source_status, "policy.source_state.classification"),
        "technical:source_freshness_classification": get_path(source_status, "technical.source_state.classification"),
    })'''
if old not in text: raise SystemExit('dashboard fallback block not found')
text = text.replace(old, new)
p.write_text(text, encoding='utf-8')

# Patch tests constants and fallback values.
p = Path('scripts/test_artifact_index.py')
text = p.read_text(encoding='utf-8')
old = '''LOW_RISK_PHASE3_KEYS = [
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
]
LOW_RISK_PHASE3_BOUNDARY = "phase3_sql_canon_low_risk_metadata_exact_six_keys_no_execution_authority"'''
new = '''LOW_RISK_PHASE3_KEYS = [
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
    "breadth:source_freshness_classification",
    "credit:source_freshness_classification",
    "fundamental_ir:source_freshness_classification",
    "fundamentals:source_freshness_classification",
    "market:source_freshness_classification",
    "policy:source_freshness_classification",
    "technical:source_freshness_classification",
]
LOW_RISK_PHASE3_BOUNDARY = "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority"'''
if old not in text: raise SystemExit('test keys block not found')
text = text.replace(old, new)
text = text.replace('approved six-key final set', 'approved thirteen-key final set')
old = '''                    "deployment:source_freshness_classification": "fresh",
                    "earnings:source_freshness_classification": "fresh",
                },'''
new = '''                    "deployment:source_freshness_classification": "fresh",
                    "earnings:source_freshness_classification": "fresh",
                    "breadth:source_freshness_classification": "fresh",
                    "credit:source_freshness_classification": "fresh",
                    "fundamental_ir:source_freshness_classification": "fresh",
                    "fundamentals:source_freshness_classification": "fresh",
                    "market:source_freshness_classification": "current",
                    "policy:source_freshness_classification": "current",
                    "technical:source_freshness_classification": "fresh",
                },'''
if old not in text: raise SystemExit('test fallback block not found')
text = text.replace(old, new)
p.write_text(text, encoding='utf-8')

# Patch preflight current approved/shadow state.
p = Path('scripts/sql_canon_field_family_preflight.py')
text = p.read_text(encoding='utf-8')
old = '''CURRENT_LOW_RISK_APPROVED_KEYS = {
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
}
PHASE4A_APPROVED_KEYS = CURRENT_LOW_RISK_APPROVED_KEYS
LOW_RISK_SHADOW_ELIGIBLE_KEYS = (
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
)'''
new = '''CURRENT_LOW_RISK_APPROVED_KEYS = {
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
    "breadth:source_freshness_classification",
    "credit:source_freshness_classification",
    "fundamental_ir:source_freshness_classification",
    "fundamentals:source_freshness_classification",
    "market:source_freshness_classification",
    "policy:source_freshness_classification",
    "technical:source_freshness_classification",
}
PHASE4A_APPROVED_KEYS = CURRENT_LOW_RISK_APPROVED_KEYS
LOW_RISK_SHADOW_ELIGIBLE_KEYS = (
)'''
if old not in text: raise SystemExit('preflight keys block not found')
text = text.replace(old, new)
p.write_text(text, encoding='utf-8')

print('patched')
