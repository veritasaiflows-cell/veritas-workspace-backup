# Workspace Organization and Auto-Archive Audit

Generated: 2026-05-10T04:04:31Z  
Scope: read-only organization, retrieval, and safe auto-archive audit for `C:\Users\Veritas\.openclaw\workspace`.

## 1. Executive verdict

The workspace is mostly coherent and much cleaner than a normal automation-heavy Obsidian vault: the numbered finance domains are intact, generated finance artifacts are mostly contained under `tmp/`, durable scripts live under `scripts/`, and retrieval already has a real SQLite layer. The main risk is not catastrophic clutter; it is **active-path residue from fast workflow acceleration**: undocumented root exceptions, executable scratch helpers still in `tmp/`, opaque package names in `scripts/skills/`, stale proof reports accumulating in `tmp/`, and policy/validator drift around the newly approved `data/` state-history path.

Verdict: **do not run broad auto-archive yet.** Build a conservative archive suggester first, then allow automatic moves only for exact low-risk classes with manifest, dry-run, and post-move validator proof. Canonical finance notes, governance notes, active workflow notes, config/runtime files, and generated finance truth must remain human-approved.

High-confidence findings from validators:
- `python scripts/workspace_boundary_check.py` returned `status: warning` with 12 findings: `backups/`, `data/`, six Python helpers in `tmp/`, two `__pycache__/` info items, and expected generated retrieval/dashboard artifacts.
- `python scripts/dashboard_truth_lint.py` returned `status: ok` with 0 findings.
- `python scripts/workspace_governance_truth_check.py` returned `status: warning` only for Telegram setup-pending / owner allow config visibility, not workspace structure.

## 2. What already exists for retrieval and organization

### Folder structure and policy

Existing strong structure:
- Canonical numbered domains are present and ordered: `01. Dashboards/` through `09. Archive/`.
- System/implementation surfaces are separate: `memory/`, `scripts/`, `skills/`, `tmp/`, `migration-backups/`.
- `skills/workspace-governor/references/workspace-standards.md` defines root policy, archive policy, generated artifact handling, naming conventions, folder-fit guidance, and cleanup checklist.
- `scripts/README.md` clearly separates durable tooling in `scripts/` from generated/staged artifacts in `tmp/`.
- `09. Archive/` already holds retired consulting-era domains, historical audits, old report assets, and prior tmp/script cleanup material.

### Retrieval layer already in place

Existing retrieval supports are meaningful:
- `scripts/workspace_index.py` builds `tmp/workspace-index.sqlite` and `tmp/workspace-index-report.json`.
- Last report observed: `status: ok`, schema version 3, FTS enabled, 476 documents, 6,949 headings, 172 links, 254 aliases, 11 owners, 90 artifacts, 228 artifact metadata rows.
- The index explicitly excludes `.clawhub`, `.git`, `.obsidian`, `.openclaw`, `__pycache__`, `migration-backups`, and broad `tmp/` content while still summarizing selected artifact globs.
- `scripts/artifact_index.py` builds `tmp/veritas-artifact-index.sqlite` from market-intelligence and daily-review JSON outputs; live query returned current post-close escalations from `tmp/daily-review-objects-post-close.json` and `tmp/market-intelligence-events-post-close.json`.
- `06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md` correctly states SQL is retrieval/cache only and source Markdown/JSON must be opened before judgment.

### Existing provenance and truth boundaries

Strong boundaries already exist:
- `scripts/README.md` labels generated artifacts as evidence/staging surfaces that do not outrank canonical notes.
- `tmp/portfolio-config.json` is explicitly a machine-readable config spine, not a root note.
- `data/state-history/README.md` describes the approved durable append-only history path and forbids model-driven deployment, portfolio mutation, trade execution, or owner-approval inference.
- `08. Audits/` contains high-signal workflow and QA history; this is useful retrieval evidence, not random clutter by default.

## 3. Gaps / drift found, with file/path evidence

### A. Root policy drift: `data/` is real but not yet documented in workspace standards

Evidence:
- Live root contains `data/`.
- `data/state-history/README.md` says `state-history-v1.jsonl` is the approved durable path for WF43 append-only review history.
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md` records Randall approved `data/state-history/state-history-v1.jsonl` as the durable path on 2026-05-09.
- `workspace_boundary_check.py` still flags `data/` as: `root directory has no documented active entitlement`.
- `workspace-standards.md` current allowed non-numbered active root folders do not include `data/`.

Judgment: this is policy/validator lag, not evidence that `data/` should be archived. `data/` should become a documented root exception/domain for durable append-only derived state, with strict subfolder rules.

### B. Root policy drift: `backups/` is not documented and likely belongs under archive or migration-backups

Evidence:
- Live root contains `backups/startup-hardening-20260506-230017/` with `AGENTS.md.bak`, `MEMORY.md.bak`, and `USER.md.bak`.
- `workspace_boundary_check.py` flags `backups/` as `root directory has no documented active entitlement`.
- `workspace-standards.md` allows `migration-backups/`, but not `backups/`.

Judgment: likely archive candidate, but not automatic without checking whether startup-hardening recovery still needs the exact path. If not path-sensitive, move under `09. Archive/backups - Archived/2026-05-06-startup-hardening/` or fold into `migration-backups/` only if that folder is the approved reversible-checkpoint surface.

### C. Executable scratch helpers still live in `tmp/`

Evidence from `workspace_boundary_check.py`:
- `tmp/dump_bands.py`
- `tmp/find_band_refs.py`
- `tmp/find_disallowed_model_refs.py`
- `tmp/find_disallowed_openclaw_refs.py`
- `tmp/find_model_refs.py`
- `tmp/market_close_quick.py`

Judgment: this violates the existing generated-artifact rule. These should be classified one by one:
- durable diagnostic -> promote to `scripts/` or `scripts/operators/` with README entry and tests if reused;
- one-off proof helper -> archive under `09. Archive/tmp-helper-scripts - Archived/<date>/`;
- obsolete scratch -> archive-first, then delete only after owner-approved retention window.

### D. `tmp/` is carrying many human-readable workflow reports and drafts

Evidence: Markdown reports in `tmp/` include:
- `tmp/wf-program-architect-audit.md`
- `tmp/wf-implementation-readiness-scan.md`
- `tmp/wf41-router-contract-report.md`
- `tmp/wf42-capital-recommendation-report.md`
- `tmp/wf43-state-history-report.md`
- `tmp/wf44-implementation-report.md`
- `tmp/wf45-implementation-report.md`
- `tmp/wf46-implementation-report.md`
- `tmp/wf47-implementation-report.md`
- `tmp/retrospective-governance-gap-proposal-2026-05-06.md`
- `tmp/retrospective-hardening-qa-2026-05-06.md`
- `tmp/wf23-phase3-dashboard-overlap-edit-proposal-2026-05-06.md`
- `tmp/wf37-first-postclose-brief-draft.md`, `tmp/wf37-first-premarket-brief-draft.md`, `tmp/wf37-safe-draft.md`, `tmp/wf37-unsafe-draft.md`

Judgment: `tmp/` is appropriate for active staged reports, but completed workflow reports should not live there forever. The archive system needs a retention rule: leave active/current workflow reports in `tmp/`; after queue closeout or N days, suggest promotion to `08. Audits/` if decision-grade, or archive to `09. Archive/tmp-reports - Archived/YYYY-MM/` if only proof residue.

### E. `tmp/research-automation/` retains historical packet runs from closed workflows

Evidence:
- `tmp/research-automation/intake-packets-20260504-051443.json`
- `tmp/research-automation/intake-packets-20260504-055803.json`
- `tmp/research-automation/intake-packets-20260506-021940.json`
- `tmp/research-automation/intake-packets-20260506-152048.json`
- `tmp/research-automation/freshness-patch-candidates-20260504-055803.json`
- `tmp/research-automation/freshness-patch-candidates-20260506-204259.json`
- queue references the 2026-05-06 packets as proof for WF21 closeout.

Judgment: do not blindly archive these; some are cited proof. A suggester should detect references from `06. Playbooks/OpenClaw Parallel Pilot Queue.md` and `08. Audits/` before moving. If referenced, keep or archive with link-safe path updates. If unreferenced historical packet residue, archive by workflow/date.

### F. Active `scripts/skills/` has opaque package names

Evidence:
- Expected packages: `scripts/skills/veritas-deep-dive.skill`, `scripts/skills/veritas-portfolio-update.skill`, `scripts/skills/veritas-weekly-brief.skill`.
- Opaque files also present: `scripts/skills/zi4THA1Z`, `scripts/skills/ziMeFDto`, `scripts/skills/zixwHtyk`.

Judgment: these names are retrieval-hostile. They may be Cowork/internal package artifacts, so do not auto-move. Verify whether they are active package IDs. If not active, rename/archive; if active, document why opaque names remain and add a small manifest mapping ID -> skill.

### G. `scripts/__pycache__/` and `scripts/operators/__pycache__/` are active debris, but ignored

Evidence:
- `workspace_boundary_check.py` reports both as info only.
- `.gitignore` already includes `__pycache__/`.

Judgment: low-risk cleanup candidate, but not urgent. Can be auto-removed only if the cleanup script is explicitly allowed to delete runtime caches. Archive is not needed for bytecode caches.

### H. `memory/.dreams/` contains runtime recall/cache temp files

Evidence:
- `memory/.dreams/events.jsonl`
- `memory/.dreams/short-term-recall.json`
- temp files such as `memory/.dreams/short-term-recall.json.<pid>.<timestamp>.<uuid>.tmp`
- `.gitignore` ignores `memory/.dreams/`.

Judgment: not an Obsidian/user note organization issue, but stale `.tmp` files could accumulate. Do not mutate until runtime ownership is understood. Future cleanup should be runtime-aware and avoid deleting live memory files.

### I. Procedure / README command mismatch for `workspace_index.py`

Evidence:
- `06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md` lists `python scripts\workspace_index.py search "Workflow 36"`.
- `scripts/README.md` also lists `python scripts/workspace_index.py search "Workflow 36"`.
- Actual script usage observed: `workspace_index.py [-h] [--root ROOT] [--db DB] [--report REPORT] [--search SEARCH] [--limit LIMIT]`.
- `python scripts/workspace_index.py search "workspace governor"` failed; `python scripts/workspace_index.py --search "workspace governor" --limit 5` succeeded.

Judgment: retrieval infrastructure works, but operator docs are stale. This is a quick doc fix, not an architecture problem.

## 4. Recommendation on standardized notes/retrieval fields

Recommendation: **add a lightweight standardized metadata block for workflow/audit/research/control notes, not for every note and not for generated JSON.** The current retrieval stack is already good enough for path/headings/full-text lookup; the missing piece is consistent classification for lifecycle, archive eligibility, authority, and source provenance.

Use either YAML frontmatter or a visible `## Retrieval / Notes` block. Prefer YAML for machine parsing, but keep it minimal and optional for legacy notes.

Suggested fields for new decision-grade notes:

```yaml
---
type: audit | workflow-report | research-note | playbook | canonical-finance-note | generated-report
status: active | closed | superseded | archived | review-only
workflow: WF40
owner_surface: "06. Playbooks/OpenClaw Parallel Pilot Queue.md"
authority: canonical | machine-companion | review-only | historical | generated-cache
source_paths:
  - tmp/run-summary-post-close.json
  - scripts/run_summary_refresh.py
archive_after: 2026-06-10
archive_policy: suggest-only | auto-archive-ok | never-auto-archive
---
```

Why this helps:
- Auto-archive can distinguish closed proof residue from active control-plane notes.
- SQLite can query `status`, `workflow`, `authority`, and `archive_policy` directly instead of inferring from filename and folder.
- Obsidian search becomes more precise: `status:active workflow:WF43 authority:historical`.
- It prevents `tmp/` proof reports from becoming invisible clutter while preserving source paths.

Do not overdo it:
- Do not retrofit all 476 indexed documents immediately.
- Do not add metadata to canonical finance notes if it creates maintenance burden or a second authority layer.
- Do not let metadata outrank path, headings, queue state, source files, or actual artifact freshness.

Minimal v1 target:
- New `08. Audits/` reports.
- New `06. Playbooks/Project Continuity/Workflow ...` notes.
- New human-readable `tmp/wf*-*.md` implementation reports.
- New research/thesis notes only where lifecycle and provenance matter.

## 5. Safe auto-archive design: automatic / suggestion-only / blocked

### Automatic in a future script, after explicit implementation approval

Only safe if the script writes a manifest, runs dry-run by default, preserves paths in an archive folder, and runs validators after:

1. Python bytecode/cache cleanup
   - `scripts/**/__pycache__/`
   - no archive needed; delete-only is acceptable only if Randall approves cache cleanup.

2. Generated SQLite sidecars and stale validator JSON only when exact ignored patterns match
   - `tmp/workspace-index.sqlite*`
   - `tmp/veritas-artifact-index.sqlite*`
   - `tmp/workspace-boundary-check.json`
   - `tmp/dashboard-truth-lint.json`
   - Better default: rebuild/overwrite rather than archive.

3. Exact `tmp/` report patterns with metadata `archive_policy: auto-archive-ok`
   - Example target: `09. Archive/tmp-reports - Archived/YYYY-MM/`
   - Must create `archive-manifest.json` with original path, hash, size, timestamp, reason, and validator results.

4. Exact temporary test outputs generated by known tests after retention expires
   - Example: `tmp/state-history-test.jsonl`
   - Only if test docs or metadata mark them disposable.

### Suggestion-only / human-approved moves

These should appear in an archive recommendation report, not move silently:

- `backups/startup-hardening-20260506-230017/`
- executable helpers in `tmp/*.py`
- `tmp/research-automation/*` historical packets referenced by audits/queue
- `tmp/wf*-*.md` implementation reports without metadata
- `scripts/skills/zi4THA1Z`, `scripts/skills/ziMeFDto`, `scripts/skills/zixwHtyk`
- old daily adjunct notes in `memory/YYYY-MM-DD-topic.md`
- old audits in `08. Audits/` that are historically useful but no longer active
- archived-folder restructuring inside `09. Archive/`

### Blocked from auto-archive

Never auto-move without explicit owner approval:

- Canonical finance notes in `01. Dashboards/`, `02. Markets/`, `03. Portfolio/`, `04. Research/`, `05. Intelligence/`, and `07. Risk/`.
- Core operating files: `SOUL.md`, `USER.md`, `AGENTS.md`, `TOOLS.md`, `MEMORY.md`, `IDENTITY.md`, `Home.md`, `HEARTBEAT.md`, `Continuity Protocol.md`, `CLAUDE.md`, `GEMINI.md`.
- OpenClaw/runtime/config/plugin/channel surfaces under `.openclaw/`, `.obsidian/`, `.clawhub/`, or outside workspace.
- `data/state-history/` durable rows once append proof exists.
- Any file referenced by the live queue, active workflow continuity, or recent audit proof until reference-safe move logic exists.
- Anything containing credentials, tokens, secrets, or auth material; those require security handling, not archive convenience.

## 6. Minimal implementation plan, phased

### Phase 0 — policy alignment, no moves

1. Update `workspace-standards.md` to document `data/` as an allowed root folder only for durable append-only state/history datasets with README, no credentials, and no canonical portfolio authority.
2. Update `scripts/workspace_boundary_check.py` so `data/` is no longer flagged when it contains only approved structures such as `data/state-history/README.md` and the approved JSONL path.
3. Fix `workspace_index.py` command examples in `scripts/README.md` and `06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md` from subcommand style to `--search` style.

### Phase 1 — archive suggester, read-only

Build `scripts/archive_suggester.py` as read-only:
- inventory candidate files;
- classify by rule: cache, generated artifact, tmp report, scratch helper, stale proof, root exception, opaque skill package, active/canonical/blocked;
- check inbound references using ripgrep or workspace index;
- emit `tmp/archive-suggestions.json` and `tmp/archive-suggestions.md`;
- no moves, no deletes.

### Phase 2 — owner-approved archive move mode

Add `--apply-approved <manifest>` only after reviewing suggestions:
- copy/move to `09. Archive/<bucket>/...`;
- preserve original basename unless clarity improves;
- write archive manifest with hashes;
- update links only if explicitly allowed;
- run validators after.

### Phase 3 — narrow automatic cleanup

Only after Phase 1 and 2 prove low false-positive rate:
- auto-clean `__pycache__/` if approved;
- auto-refresh/rebuild derived SQLite indexes rather than archiving them;
- auto-archive tmp reports only when they carry `archive_policy: auto-archive-ok`, are older than retention, and have no active references.

## 7. Validators/proof gates

Before any archive apply:
- `python scripts/workspace_boundary_check.py`
- `python scripts/dashboard_truth_lint.py`
- `python scripts/workspace_governance_truth_check.py`
- `python scripts/workspace_index.py --search "<moved filename or workflow>" --limit 10` before and after, or rebuild the index if path truth matters.
- `rg "<candidate path or basename>" .` excluding `.git`, `.obsidian`, `.openclaw`, `.clawhub`, and archive target.

After any archive apply:
- Re-run `python scripts/workspace_boundary_check.py`; expected result should reduce or explain warnings.
- Re-run `python scripts/dashboard_truth_lint.py`; must remain `ok`.
- If `scripts/` changed: `python -m py_compile` for touched scripts and relevant tests.
- If retrieval docs/index changed: `python scripts/workspace_index.py --search "workspace governor" --limit 5` and rebuild report if intended.
- If `data/` policy changed: run state-history proof commands before relying on durable rows:
  - `python -m py_compile scripts\state_history_capture.py scripts\test_state_history_capture.py`
  - `python scripts\test_state_history_capture.py`
  - `python scripts\state_history_capture.py validate`

Proof artifact requirement:
- Every archive move should write an audit trail containing original path, new path, hash, reason, owner approval, date, and validator results.

## 8. Risks and owner decisions needed

Owner decisions needed:
1. Should `data/` become an approved permanent root folder for durable append-only derived state/history? Evidence says yes, but policy should say it explicitly.
2. Should `backups/` be archived under `09. Archive/` or folded into `migration-backups/`? Recommendation: archive unless a tool depends on the path.
3. Should executable scratch helpers in `tmp/` be archived or promoted? Recommendation: archive all six unless a current workflow still uses them.
4. Should old `tmp/` Markdown workflow reports be moved into `08. Audits/` or `09. Archive/tmp-reports - Archived/`? Recommendation: active decision-grade reports to `08. Audits/`; proof-only residue to archive.
5. Should cache deletion be allowed automatically? Recommendation: yes for `__pycache__/`, no for `memory/.dreams/` until runtime ownership is verified.
6. Should new workflow/audit notes require lightweight metadata? Recommendation: yes for new notes only.

Main risks:
- Link breakage if referenced proof artifacts are moved without inbound-reference checks.
- Canonical truth confusion if archive automation touches finance notes or generated state-history rows.
- False cleanup if `tmp/` reports are still live handoff artifacts.
- Runtime damage if memory/cache files are cleaned without knowing active process ownership.
- Over-building metadata bureaucracy that slows actual finance work.

## 9. Quick wins vs defer

### Quick wins

1. Document `data/` in `workspace-standards.md` and update `workspace_boundary_check.py` to recognize approved `data/state-history/`.
2. Fix `workspace_index.py` command examples to use `--search`.
3. Produce a read-only archive-suggestion report; do not move anything yet.
4. Add metadata template for new audit/workflow reports only.
5. Classify the six `tmp/*.py` helpers and archive/promote after owner approval.
6. Decide the fate of root `backups/`.

### Defer

1. Broad archival of `08. Audits/`; current audit density is useful and recent.
2. Broad cleanup of `memory/`; daily memory is continuity, not ordinary clutter.
3. Any auto-archive of canonical finance notes or workflow queue surfaces.
4. Cleanup of `memory/.dreams/` until runtime ownership and stale-temp rules are explicit.
5. Full legacy metadata retrofit across all indexed documents.
6. Chain-integrated archive automation; keep it manual/operator-gated until false positives are proven low.
