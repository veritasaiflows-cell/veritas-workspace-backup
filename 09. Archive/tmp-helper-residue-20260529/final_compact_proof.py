import json, pathlib
# print final compact proof
paths=['tmp/run-chain-post-close.json','tmp/run-summary-post-close.json','tmp/auto-band-apply.json','tmp/dashboard-validation.json','tmp/capital-deployment-recommendation-validation.json','tmp/post-apply-validation-chain.json','tmp/current-window-artifacts.json']
for f in paths:
 d=json.loads(pathlib.Path(f).read_text(encoding='utf-8'))
 print(f, 'status=', d.get('status'), 'summary=', d.get('summary'), 'authority=', d.get('authority'))
print('current-window-md-head:', pathlib.Path('tmp/current-window-artifacts.md').read_text(encoding='utf-8').splitlines()[:4])
