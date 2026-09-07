from pathlib import Path
path=Path('scripts/chain_manifest.py')
text=path.read_text(encoding='utf-8')
step='{"script": "finance_discrepancy_resolver.py", "args": ["--write"], "category": "review_only", "expected_outputs": ["tmp/finance-discrepancy-resolver.json", "tmp/finance-discrepancy-resolver.md"], "depends_on": ["canonical_note_patch_proposal.py", "portfolio_snapshot_patch_proposal.py", "board_canon_guardrail.py", "stale_intelligence_guardrail.py"], "recovery_posture": "fail_chain"}'
repls = [
('            {"script": "current_window_artifact_index.py", "args": ["--window", "morning", "--write"], "category": "summary", "expected_outputs": ["tmp/current-window-artifacts.json", "tmp/current-window-artifacts.md"], "depends_on": ["daily_review_objects.py", "run_summary_refresh.py"], "recovery_posture": "fail_chain"},',
 f'            {step},\n            {{"script": "current_window_artifact_index.py", "args": ["--window", "morning", "--write"], "category": "summary", "expected_outputs": ["tmp/current-window-artifacts.json", "tmp/current-window-artifacts.md"], "depends_on": ["daily_review_objects.py", "run_summary_refresh.py", "finance_discrepancy_resolver.py"], "recovery_posture": "fail_chain"}},'),
('            {"script": "proposal_patch_scope_validator.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/proposal-patch-scope-validation.json"], "depends_on": ["portfolio_snapshot_patch_proposal.py"], "recovery_posture": "fail_chain"},',
 f'            {step},\n            {{"script": "proposal_patch_scope_validator.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/proposal-patch-scope-validation.json"], "depends_on": ["portfolio_snapshot_patch_proposal.py", "finance_discrepancy_resolver.py"], "recovery_posture": "fail_chain"}},'),
('            {"script": "archive_suggester.py", "args": ["--include-tmp-md"], "category": "review_only", "expected_outputs": ["tmp/archive-suggestions.json", "tmp/archive-suggestions.md"], "depends_on": ["portfolio_snapshot_patch_proposal.py"], "recovery_posture": "fail_chain"},',
 f'            {step},\n            {{"script": "archive_suggester.py", "args": ["--include-tmp-md"], "category": "review_only", "expected_outputs": ["tmp/archive-suggestions.json", "tmp/archive-suggestions.md"], "depends_on": ["portfolio_snapshot_patch_proposal.py", "finance_discrepancy_resolver.py"], "recovery_posture": "fail_chain"}},')]
for old,new in repls:
    if old not in text:
        raise SystemExit(f'missing target: {old[:80]}')
    text=text.replace(old,new,1)
path.write_text(text,encoding='utf-8')
