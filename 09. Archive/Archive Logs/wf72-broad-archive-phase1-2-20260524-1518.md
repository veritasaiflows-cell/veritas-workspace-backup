# WF72 Broad Archive Phase 1/2 Apply Manifest

- Generated UTC: 2026-05-24T22:29:50Z
- Archive root: `09. Archive/Broad Workspace Archive - Owner Approved/2026-05-24-wf72-phase1-2-owner-approved`
- Move count: 3
- Delete count: 0
- Error count: 0

| Source | Destination | Hash match | Reason |
|---|---|---:|---|
| `tmpdashboard-acceptance-baseline.json` | `09. Archive/Broad Workspace Archive - Owner Approved/2026-05-24-wf72-phase1-2-owner-approved/root-generated-residue/tmpdashboard-acceptance-baseline.json` | True | Phase 1 root warning archive-ready stale diagnostic/root clutter |
| `tmp/implement_cron_broadening.py` | `09. Archive/Broad Workspace Archive - Owner Approved/2026-05-24-wf72-phase1-2-owner-approved/tmp-python-helpers/implement_cron_broadening.py` | True | Phase 2 one-off cron broadening helper; durable results live in scripts/WF76 artifacts |
| `tmp/wf72_make_phases_8_11_plan.py` | `09. Archive/Broad Workspace Archive - Owner Approved/2026-05-24-wf72-phase1-2-owner-approved/tmp-python-helpers/wf72_make_phases_8_11_plan.py` | True | Phase 2 one-off WF72 plan generator; generated proof artifacts retained in tmp |

Rollback: Move each destination back to its source path and verify sha256_before matches restored file. README/script documentation changes can be reverted from git or by removing the added README and restoring the approved data-surface allowlist.
