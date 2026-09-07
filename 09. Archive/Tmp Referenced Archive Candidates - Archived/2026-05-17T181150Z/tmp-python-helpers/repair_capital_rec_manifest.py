from pathlib import Path
path=Path('scripts/chain_manifest.py')
lines=path.read_text(encoding='utf-8').splitlines()
# Remove prior malformed capital-rec insertions.
lines=[line for line in lines if '"script": "portfolio_mutation_proposal_generator.py"' not in line]
out=[]
current=None
inserted=set()
for line in lines:
    stripped=line.strip()
    if stripped == '"morning": {':
        current='morning'
    elif stripped == '"post-close": {':
        current='post-close'
    elif stripped == '"post-earnings": {':
        current='post-earnings'
    elif stripped == '"sunday": {':
        current='sunday'
    if current in {'morning','post-close','sunday'} and '"script": "board_canon_guardrail.py"' in line and current not in inserted:
        out.append(f'            {{"script": "portfolio_mutation_proposal_generator.py", "args": ["--window", "{current}", "--write"], "category": "review_only", "expected_outputs": ["tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json"], "depends_on": ["daily_review_objects.py", "band_refresh.py", "deployment_check.py", "validate_portfolio_config.py"], "recovery_posture": "fail_chain"}},')
        inserted.add(current)
    out.append(line)
path.write_text('\n'.join(out)+'\n', encoding='utf-8')
print('inserted', sorted(inserted))
