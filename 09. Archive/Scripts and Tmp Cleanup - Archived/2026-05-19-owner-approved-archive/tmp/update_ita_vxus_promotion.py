import json
from pathlib import Path
p=Path('tmp/review-packets/ita-vxus-execution-readiness-packets.json')
d=json.loads(p.read_text(encoding='utf-8'))
d['ita_candidate_promotion_2026_05_18']={
    'source_packet':'tmp/review-packets/ita-candidate-promotion-2026-05-18.json',
    'state':'promoted_to_review_only_candidate',
    'paper_execution_ready':False,
    'remaining_blockers':['look-through concentration acceptance','fresh in-band quote','WF67 dry run/guard validation','exact owner order terms'],
    'authority':'review-only; no sizing/sleeve/cash/order/account/trade authority'
}
p.write_text(json.dumps(d,indent=2),encoding='utf-8')
md=Path('tmp/review-packets/ita-vxus-execution-readiness-packets.md')
t=md.read_text(encoding='utf-8')
marker='## 2026-05-18 ITA candidate promotion update'
if marker not in t:
    t += """

## 2026-05-18 ITA candidate promotion update

Randall promoted **ITA** to a review-only candidate on 2026-05-18 08:35 MST. This closes the “main-session promotion” blocker only. It does **not** authorize paper/live execution, sizing, sleeve, cash, brokerage/account action, or owner approval inference. Remaining blockers: concentration/look-through acceptance, fresh in-band quote, WF67 dry run/guard validation, and exact owner order terms. Proof: `tmp/review-packets/ita-candidate-promotion-2026-05-18.md/.json`.
"""
md.write_text(t,encoding='utf-8')
print('updated ITA/VXUS packet promotion section')
