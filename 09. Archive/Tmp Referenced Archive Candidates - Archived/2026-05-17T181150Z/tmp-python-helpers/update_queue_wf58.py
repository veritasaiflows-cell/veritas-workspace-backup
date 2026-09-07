from pathlib import Path
p=Path('06. Playbooks/OpenClaw Parallel Pilot Queue.md')
text=p.read_text(encoding='utf-8')
start=text.index('### Active workflow')
mid=text.index('### Recently completed / handed-off proof spine')
new_active='''### Active workflow
**Workflow 58 - Dashboard freshness, entry-band automation, capital recommendations, and discrepancy resolver**

Status:
- active priority after Randall explicitly approved orchestration mode for presentation/canonical-sync-review/capital-recommendation readiness
- Phase 1 bones are implemented: readiness gates, review-only discrepancy resolver, review-only capital-deployment proposal generator, current-window artifact indexing, and morning/post-close/Sunday manifest wiring
- GS eligible entry-band update was applied and synchronized into the Technical Entry and Invalidation Sheet; MSFT and AMD remain manual-review/wait-state blockers because their proposals are non-applyable
- next work is residual hardening: capital-rec Markdown/validator, current-window role test, cron posture decision, and manual-review queue visibility for remaining band blockers
- must not build trade/account paths, owner-approval inference, scheduled mutation apply, sizing/sleeve/cash/risk-rule mutation, or execution entitlement

'''
text=text[:start]+new_active+text[mid:]
start=text.index('### Next approved queue item')
mid=text.index('### Recently completed sidecar')
new_next='''### Next approved queue item
**WF58 residual hardening / capital-rec review surface**

Status:
- next move is a bounded implementation pass that adds a human-readable Markdown renderer and bundle-level validator for `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`
- acceptance: generated JSON and Markdown agree on tickers/recommendation posture; bundle validator proves all authority fields remain false except owner-decision-required; current-window artifact index test requires the capital-rec and discrepancy roles
- blocked scope: no patch helper, no write-capable apply helper, no scheduled mutation, no owner-approval mutation, no portfolio/risk/canonical-note mutation, no sizing/sleeve/cash mutation, and no trade/account action
- after this pass, decide whether separate cron jobs are needed; current recommendation is to keep the bones in finance-chain manifests unless a non-chain cadence becomes necessary

'''
text=text[:start]+new_next+text[mid:]
p.write_text(text,encoding='utf-8')
