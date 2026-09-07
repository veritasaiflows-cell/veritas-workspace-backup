from pathlib import Path
path=Path('scripts/chain_manifest.py')
text=path.read_text(encoding='utf-8')
def step(window):
    return '{"script": "portfolio_mutation_proposal_generator.py", "args": ["--window", "'+window+'", "--write"], "category": "review_only", "expected_outputs": ["tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json"], "depends_on": ["daily_review_objects.py", "band_refresh.py", "deployment_check.py", "validate_portfolio_config.py"], "recovery_posture": "fail_chain"}'
repls=[
('morning','            {"script": "board_canon_guardrail.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/board-canon-guardrail.json", "tmp/board-canon-guardrail.md"], "depends_on": ["daily_review_objects.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},'),
('post-close','            {"script": "board_canon_guardrail.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/board-canon-guardrail.json", "tmp/board-canon-guardrail.md"], "depends_on": ["daily_review_objects.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},'),
('sunday','            {"script": "board_canon_guardrail.py", "args": ["--write"], "category": "validation", "expected_outputs": ["tmp/board-canon-guardrail.json", "tmp/board-canon-guardrail.md"], "depends_on": ["daily_review_objects.py", "regime_scoring_refresh.py", "trigger_sheet_refresh.py", "deployment_check.py"], "recovery_posture": "fail_chain"},'),
]
for window, target in repls:
    idx=text.find(target)
    if idx == -1:
        raise SystemExit(f'missing target for {window}')
    text=text[:idx] + f'            {step(window)},\n' + text[idx:]
path.write_text(text,encoding='utf-8')
