from pathlib import Path
p=Path('scripts/test_run_summary_tail_order.py')
text=p.read_text(encoding='utf-8')
text=text.replace('''            "daily_review_objects.py",\n            "board_canon_guardrail.py",''','''            "daily_review_objects.py",\n            "portfolio_mutation_proposal_generator.py",\n            "board_canon_guardrail.py",''')
text=text.replace('''            "portfolio_snapshot_patch_proposal.py",\n            "current_window_artifact_index.py",''','''            "portfolio_snapshot_patch_proposal.py",\n            "finance_discrepancy_resolver.py",\n            "current_window_artifact_index.py",''',1)
text=text.replace('''            "portfolio_snapshot_patch_proposal.py",\n            "proposal_patch_scope_validator.py",''','''            "portfolio_snapshot_patch_proposal.py",\n            "finance_discrepancy_resolver.py",\n            "proposal_patch_scope_validator.py",''')
text=text.replace('''            "portfolio_snapshot_patch_proposal.py",\n            "archive_suggester.py",''','''            "portfolio_snapshot_patch_proposal.py",\n            "finance_discrepancy_resolver.py",\n            "archive_suggester.py",''')
p.write_text(text, encoding='utf-8')
