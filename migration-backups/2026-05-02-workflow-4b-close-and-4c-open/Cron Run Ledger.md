# Cron Run Ledger

## Purpose
Compact operator surface for live cron-proof status, recent evidence, and rerun/follow-up decisions.

This is the human-readable layer for Workflow 4B.
Use it with:
- cron run history
- `06. Playbooks/Automation Run Summary Contract.md`
- the active continuity note for the current workflow

## Current delivery posture
- accepted for now: **internal-only / no-delivery**
- reason: the live jobs do not currently have a reliable routed delivery target in this surface
- trust must come from cron run history plus workspace artifacts/notes, not imagined chat delivery

## Proof standard
A job is proved for Workflow 4B only when all are true:
1. a controlled cron run exists in cron run history
2. the expected artifact or note surface exists and is inspectable
3. trust-boundary fields stayed explicit where relevant
4. blocked/error follow-up behavior is recorded
5. rerun and overlap rules are explicit

## Overlap and rerun rules
- Do not force overlapping finance-window runs that write the same artifact family.
- Do not run `veritas:day-job-orchestrator` and `veritas:continuity-hygiene-pass` as concurrent control-plane writers.
- Rerun a finance window when a required artifact is missing, the run is blocked/error, a trust-boundary field is missing, or a clearly recoverable source glitch justifies another pass.
- Do not rerun just to erase honest warning-grade outputs.
- When a run ends blocked/error, record the next-step action here or in the active continuity note before rerunning.

## Proof ledger

### veritas:day-job-orchestrator
- **Schedule:** daily 19:45 America/Phoenix
- **Owner:** Veritas control-plane lane
- **Expected evidence:** queue / registry / continuity-note sync plus cron run history
- **Trust boundary:** must not fake completion or silently jump the queue
- **Proof status:** proved before Workflow 4B opening
- **Current evidence:** two controlled runs already exist in cron history; first corrected real drift, second confirmed honest closure of Workflow 4
- **Blocked/error follow-up:** if queue / registry / continuity disagree, correct the outlier first and stop if completion remains ambiguous

### finance:morning-internal-refresh
- **Schedule:** weekdays 06:05 America/Phoenix
- **Owner:** `scripts/run_finance_refresh_chain.py morning`
- **Expected artifacts:** `tmp/run-summary-morning.json`, `tmp/dashboard-validation.json`, `tmp/veritas-command-center.html`, `tmp/workbook-export-manifest.json`
- **Trust boundary:** `presentation_allowed=false` and `canonical_note_mutation_allowed=false` must remain explicit while warning-grade trust persists
- **Proof status:** pending controlled cron-run proof
- **Current artifact evidence:** run-summary exists and remains warning-grade internal staging
- **Blocked/error follow-up:** if required outputs or trust fields are missing, record the failure and rerun only after the cause is named

### finance:post-close-internal-refresh
- **Schedule:** weekdays 13:20 America/Phoenix
- **Owner:** `scripts/run_finance_refresh_chain.py post-close`
- **Expected artifacts:** `tmp/run-summary-post-close.json`, `tmp/dashboard-validation.json`, `tmp/post-earnings-prep.json`, `tmp/post-earnings-note-targets.json`, command-center/workbook artifacts
- **Trust boundary:** `presentation_allowed=false` and `canonical_note_mutation_allowed=false` must remain explicit while warning-grade trust persists
- **Proof status:** pending controlled cron-run proof
- **Current artifact evidence:** run-summary exists and remains warning-grade internal staging
- **Blocked/error follow-up:** if required outputs are partial or missing beyond the allowed warning contract, log the next step before rerunning

### finance:sunday-internal-refresh
- **Schedule:** Sunday 08:00 America/Phoenix
- **Owner:** `scripts/run_finance_refresh_chain.py sunday`
- **Expected artifacts:** `tmp/run-summary-sunday.json`, `tmp/weekly-macro-snapshot.json`, `tmp/weekly-intelligence-brief.json`, command-center/workbook artifacts
- **Trust boundary:** `presentation_allowed=false` and `canonical_note_mutation_allowed=false` must remain explicit while warning-grade trust persists
- **Proof status:** pending controlled cron-run proof
- **Current artifact evidence:** run-summary exists and remains warning-grade internal staging
- **Blocked/error follow-up:** if a weekly artifact is missing or trust fields disappear, stop and record the specific broken surface before rerunning

### veritas:continuity-hygiene-pass
- **Schedule:** Sunday 18:45 America/Phoenix
- **Owner:** Veritas control-plane hygiene lane
- **Expected evidence:** bounded cleanup/archive-safe note changes plus cron run history
- **Trust boundary:** must not touch canonical finance notes, active master notes, or active chain logs
- **Proof status:** proved on 2026-05-02
- **Current artifact evidence:** this controlled hygiene pass found no archive-safe continuity notes, performed bounded truth-sync cleanup on Workflow 4B wording, and appended the factual result to `memory/2026-05-02.md`
- **Blocked/error follow-up:** if archive safety is ambiguous, stop and record the ambiguity instead of cleaning aggressively

## Workflow 4B close checklist
- [x] `veritas:day-job-orchestrator` proof logged
- [ ] `finance:morning-internal-refresh` proof logged
- [ ] `finance:post-close-internal-refresh` proof logged
- [ ] `finance:sunday-internal-refresh` proof logged
- [x] `veritas:continuity-hygiene-pass` proof logged
- [x] rerun / overlap rules encoded in the protocol and ledger
- [ ] final QC completed
