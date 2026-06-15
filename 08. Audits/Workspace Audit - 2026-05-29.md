# Workspace Audit - 2026-05-29

**Auditor:** Veritas main session (Claude Opus 4.7)
**Run window:** 2026-05-29 13:59-14:05 MST
**Scope:** Validator stack, finance chains, cron health, SQL/canon guards, workspace hygiene, security, doctrine bloat
**Posture:** Review-only. No mutations performed except `boot_surface_size_guard.py --write`-style report files written by validators. No portfolio, canon, trade/account, paper/live, config/auth/channel/runtime, or owner-approval state changed.

---

## 1. Executive Summary

- **Overall trust:** Workspace is in a clean structural state after today's WF73 boot-bloat reduction, WF72 SQL-canon retail-grade fail-closed posture, WF72 archive microbatches 2A-3/2A-4, and the WF72 typed entry/stop helper no-drift pilot. All boot/control surfaces are inside size budget; doctrine hierarchy and finance-authority boundaries are intact.
- **Open errors:** Three concrete repair items concentrated in the finance/cron lane:
  1. WF58 dashboard acceptance test failure blocks the post-close window (GOOG vs JPM/MSFT/GS assertion drift).
  2. WF68 advisor validator throws `in_band_alert_labeled_wait_for_band` while the current advisor packet has zero in-band alerts - likely validator false positive.
  3. WF63/WF67 paper-position cron fails on the PowerShell wrapper heredoc, same pattern fixed for morning cron on 2026-05-28.
- **Hygiene items:** 18 `tmp/*.py` executable helpers remain (next microbatch candidate); `tmp/` totals 112 MB with several stale > 100h JSON artifacts ripe for a review-only stale-tmp packet; memory semantic search is configured for the OpenAI provider with no API key.
- **Security:** 0 critical, 2 warning, 1 info. Loopback-only gateway plus two unpinned npm plugin specs; nothing requires immediate action.
- **What stays preserved:** SQL fail-closed retail posture (265 rows, 0 SQL-effective retail rows), paper-only WF67 boundary, no SQL-canon expansion, no portfolio/canon mutation, no live/paper execution, no config/auth/channel/runtime change.

---

## 2. Validator Stack Results

| Validator | Result | Notes |
|---|---|---|
| `scripts/boot_surface_size_guard.py --validate` | `status=ok`, `hard_failures=0`, `warnings=0`, `total_boot_control_bytes=97266` | Boot/control surfaces inside budget after WF73 trims. |
| `scripts/workflow_hygiene_check.py --validate` | `status=ok`, `blocking=0`, `warnings=0`, `active_lanes=13/13` | P0/P1 active register and stop lines intact. |
| `scripts/artifact_index.py validate` | `28/0` | All freshness/lineage checks pass. Last incremental at 2026-05-29T20:57:19Z. |
| `scripts/workspace_boundary_check.py` | Warnings only | 18 `tmp/*.py` executable helpers flagged as boundary residue. |
| `scripts/dashboard_truth_lint.py` | `status=ok`, 1 info finding | Pre-existing Execution Board "deployable-state language" note. |
| `scripts/sql_canon_retail_grade_readiness.py` | `status=blocked_for_sql_first_retail_grade`, `validation=ok`, `cache_rows=265`, `guard_status=blocked`, `sql_effective_allowed_rows=0` | By design, fail-closed. |
| `scripts/wf72_entry_stop_sql_activate.py --batch all --validate-only` | `status=ok`, `expected_key_count=252` | All 252 WF72 entry/stop reference rows validate. |
| `scripts/wf72_entry_stop_reference_helper.py --ticker ETN` | `status=ok`, `row_count=6` | Typed read-only helper functional. |
| `scripts/finance_intelligence_router_qa.py --pretty` | `status=pass`, schema_version 1, review-only, owner approval not inferred | 479 checks, 0 errors, 0 warnings on most recent run. |
| `openclaw config validate` | ok | Config schema clean. |
| `openclaw skills check` | `Eligible: 48`, `Missing requirements: 0`, `Blocked by allowlist: 0` | Skills layer healthy. |
| `openclaw doctor` | No bootstrap truncation | Only flags memory-search provider issue. |
| `openclaw security audit` | `0 critical, 2 warn, 1 info` | See Section 6. |

**Verdict:** Validator stack is green except for the three operational errors in Section 3.

---

## 3. Active Errors (Repair Recommended)

### 3.1 WF58 Dashboard Acceptance Failure (post-close chain blocked)

- **Source:** `tmp/dashboard-acceptance-report.json`
- **Summary:** `summary.passed=28`, `summary.failed=1`, `summary.total=29`, `summary.all_passed=false`
- **Failing assertion:** `workflow8_command_center_alignment`
  - `GOOG technical state should be ALMOST DEPLOYABLE`
  - `GOOG deployment state should be ALMOST`
  - `deployment_summary.almost should include GOOG, got ['JPM', 'MSFT', 'GS']`
- **Downstream impact:** `tmp/run-summary-post-close.json` reports:
  - `status=blocked`
  - `operator_action_required`: repair/rerun `test_dashboard_acceptance.py`, refresh stale required outputs (command_center, dashboard_validation, workbook_exports, post_earnings_prep, post_earnings_note_targets, postmarket_snapshot, daily_executive_brief, postclose_brief_input), inspect `tmp/dashboard-acceptance-report.json`.
  - `canonical_note_mutation_allowed=false` downstream.
- **Likely cause:** Hardcoded assertion drift - GOOG state changed (most likely correctly demoted out of ALMOST) but the test assertion was not updated; alternatively the dashboard producer regressed and dropped GOOG.
- **Recommended fix:** Read `test_dashboard_acceptance.py` `workflow8_command_center_alignment` against current `tmp/dashboard-data.json` and current GOOG state in `03. Portfolio/Execution Board.md`. If GOOG was correctly demoted, update the assertion (or move it to a flexible-set check). If the producer dropped GOOG in error, fix the producer. Effort: ~30 min main-session.
- **Boundary:** Fix is bounded to test or `scripts/generate_dashboard.py` (or its inputs). No portfolio mutation, no canon change, no execution/order action.

### 3.2 WF68 Advisor Validator False-Positive (cron error)

- **Cron:** `Finance - WF68 Intraday Alert Producer` (`a9f14c77-9223-4760-9e8e-e83417708b38`), schedule `cron 5,35 6-12 * * 1-5 @ America/Phoenix`, status `error`.
- **Validator output:** `tmp/intraday-alerts/advisor-alert-packet-validation.json` reports `status=error`, two errors:
  - `in_band_alert_labeled_wait_for_band:0`
  - `in_band_alert_labeled_wait_for_band:1`
- **Packet state:** `tmp/intraday-alerts/advisor-alert-packet.json` is `ADVISOR_READY`, generated 2026-05-29T19:39:26Z, `alert_count=9`, **in-band alert count=0** based on `band_status` filtering.
- **Inference:** The validator is asserting against alerts at indices 0 and 1 in some interpretation where they are "in-band labeled wait_for_band," but the packet has no in-band alerts under standard band-status filtering. Either the validator's notion of "in-band" differs from the producer's `band_status` field, or it is reading a stale snapshot.
- **Recommended fix:** Open the WF68 advisor validator (`scripts/wf68_intraday_alert_producer.py` and any sibling validator). Reconcile validator's "in-band" definition against the producer's `band_status` semantics. Effort: ~30 min main-session.
- **Boundary:** No external delivery, no Telegram/Discord/Signal/email restore, no live/paper order, no canon/portfolio mutation, no config/auth/channel mutation. Authority flags remain false.

### 3.3 WF63/WF67 Paper-Position Cron Wrapper Failure

- **Cron:** `Finance - WF63/WF67 Paper Position Read-Only Refresh` (`5e33df77-ebc5-4b09-84a6-feaa5832142c`), weekdays 13:50 America/Phoenix, status `error`.
- **Diagnostic:** Wrapper PowerShell heredoc fails. The actual `scripts/alpaca_paper_position_sql_refresh.py` runs fine when invoked directly (confirmed 2026-05-28 17:32 MST: paper-position packet ok at `2026-05-29T00:31:21Z`).
- **Recommended fix:** Apply the same wrapper hardening already applied to the morning finance cron on 2026-05-28: replace the inline PowerShell JSON-parse one-liners with simple `python -c "import json; json.load(...)"` reads. Effort: ~10 min main-session through the cron update path.
- **Boundary:** Cron job payload edit only; no schedule change, no config/auth/channel mutation, no finance authority expansion, no live endpoint/credentials, no money/account movement.

---

## 4. Hygiene Items (Review-Only)

### 4.1 Workspace Boundary Residue - 18 `tmp/*.py` Executable Helpers

Current residue (per `workspace_boundary_check.py`):

```
tmp/morning_finance_inspect_20260526.py
tmp/session_recap_extract.py
tmp/inspect_canon_cache_etn.py
tmp/inspect_etn_canon_rows.py
tmp/cron_watchdog_check.py
tmp/sql_canon_hardening_audit_20260526.py
tmp/inspect_recent_subagent_jsonl.py
tmp/archive_orphan_transcripts_20260526.py
tmp/inspect_canon_cache_counts.py
tmp/patch_etn_acceptance_contract.py
tmp/extract_cat.py
tmp/inspect_cron_outputs.py
tmp/inspect_cron_flags.py
tmp/check_band_eligible.py
tmp/inspect_warnings.py
tmp/final_compact_proof.py
tmp/cron_status_snapshot.py
tmp/extract_ticker.py
```

- **Suggested microbatch 2A-5 candidates (cron/operator probes + extraction probes):**
  - `cron_status_snapshot.py`, `cron_watchdog_check.py`, `inspect_cron_flags.py`, `inspect_cron_outputs.py`
  - `extract_cat.py`, `extract_ticker.py`, `session_recap_extract.py`
- **Process:** Build an exact `tmp/wf72-archive-microbatch-2a5-approval-packet-2026-05-29.json` with per-file hash, reference scan, destination under `09. Archive/tmp-python-helpers - Archived/`, rollback, validators, and `delete_count=0`. **No move without explicit Randall approval.**
- **Protected (do not include in next packet):** SQL/ETN-sensitive helpers, retail SaaS artifacts, WF72 archive-control sidecars, recent acceptance/patch probes still referenced by active proof.

### 4.2 Stale `tmp/` Artifacts (> 100h old, > 500 KB)

| Path | Size | Age | Disposition |
|---|---|---|---|
| `tmp/openclaw-config-schema-current.json` | 4.5 MB | 111h | Likely obsolete after OpenClaw 2026.5.27 update; regenerable. |
| `tmp/sql-canon-phase4-dashboard-before.json` | 1.0 MB | 145h | Historical-only. |
| `tmp/wf72-script-ownership-inventory.json` | 641 KB | 183h | Historical-only. |
| `tmp/sql-canon-phase4a-activation.json` | 605 KB | 97h | Historical-only. |

- **Volume snapshot:** `tmp/` = 643 JSON + 159 MD + 18 PY + ancillary = ~112 MB total.
- **Recommendation:** Build a review-only stale-tmp report identifying candidates >7 days old that are not referenced by current validators, with reference scan and proposed disposition (regenerate, archive, or retain). **No move without owner approval.**

### 4.3 Memory Semantic Search Disabled

- **Doctor output:** Memory search provider = `openai`, no API key found. Semantic recall will not work.
- **Two clean options:**
  - Set `OPENAI_API_KEY` in the environment, or
  - `openclaw config set agents.defaults.memorySearch.enabled false`
- **Impact today:** Noise in `openclaw doctor` output. Memory file recall via `memory_get` / `memory_search` still works against `MEMORY.md` and `memory/*.md`; only the semantic provider is offline.

### 4.4 Backups Folder Snapshot

- `backups/` total ~3.1 MB across multiple dated subfolders. Notable recent entries:
  - `20260529-1222-wf73-active-workflows-bloat-reduction/`
  - `20260529-1222-wf73-root-bootstrap-bloat-reduction/`
  - `20260529-1232-wf73-soul-agents-bloat-reduction/`
  - `20260529-1248-wf72-continuity-rollup/`
  - `wf78-live-pilot-import/wf78-live-pilot-import-20260529T045139Z/`
- **Recommendation:** Backups folder is healthy and small. No action needed; leave as durable rollback path.

---

## 5. SQL/Canon Posture

- **`tmp/veritas-canon-cache.sqlite`:** Exactly 265 approved metadata rows (13 low-risk proof/freshness/lifecycle + 252 WF72 entry/stop reference metadata across 42 tickers). Integrity ok, foreign-key rows 0, forbidden-authority rows 0.
- **`tmp/veritas-artifact-index.sqlite`:** Derived proof/index/staging only. No canon/apply/approval/execution authority. Last incremental 2026-05-29T20:57:19Z.
- **`tmp/finance-intelligence-state.sqlite`:** Review-only SQL current-state for 42 production tickers plus isolated 25-name live-pilot rows. Production overlap with pilot = 0.
- **Retail SQL-first status:** `blocked_for_sql_first_retail_grade`. Cache_rows = 265, sql_effective_allowed_rows = 0, blocker_rows = 265. Fail-closed by design.
- **No SQL writes, no SQL-canon expansion beyond the 265-row boundary, no SQL-first consumer migration while guard blocked.**

---

## 6. Security Posture

- **Audit summary:** 0 critical, 2 warn, 1 info.

### 6.1 Warning - `gateway.trusted_proxies_missing`

- `gateway.bind` is loopback and `gateway.trustedProxies` is empty.
- Fix only if Control UI is exposed via reverse proxy. **Current posture is local-only; no action required now.**

### 6.2 Warning - `plugins.installs_unpinned_npm_specs`

- Unpinned plugin index install records:
  - `codex` (`@openclaw/codex`)
  - `diagnostics-otel` (`@openclaw/diagnostics-otel`)
- **Recommendation:** Pin to exact versions next time these plugins are touched (e.g., `@scope/pkg@1.2.3`). Low priority; not exploited.

### 6.3 Info - Attack Surface Summary

- groups: open=0, allowlist=0
- tools.elevated: enabled
- hooks.webhooks: disabled
- hooks.internal: enabled
- browser control: enabled
- trust model: personal assistant (one trusted operator boundary), not hostile multi-tenant on shared gateway.

**No critical security findings. Current posture aligns with `TOOLS.md` config and security guidance.**

---

## 7. Cron Health Snapshot

| Job | Status | Notes |
|---|---|---|
| `Finance - Weekday Morning Refresh` | ok | Last run 8h ago. |
| `Finance - WF68 Intraday Alert Producer` | **error** | See Section 3.2. |
| `Finance - Weekday Post-Close Refresh` | ok | Last run 41m ago (chain produced output but downstream `tmp/run-summary-post-close.json` is `blocked` per Section 3.1). |
| `Finance - WF63/WF67 Paper Position Read-Only Refresh` | **error** | See Section 3.3. |
| `Finance - Research Freshness/Opportunity Review` | ok | Last run 22h ago. |
| `Finance - Daily Canon Drift Gate` | ok | Last run 22h ago. |
| `Workspace Index - Daily` | ok | Last run 23h ago. |
| `Security Audit - Daily` | ok | Last run 21h ago. |
| `Security Audit - Main Session` | ok | Last run 21h ago. |
| `Cron - Main Session Finance Reminder` | ok | Last run <1m ago. |
| `Finance - Sunday Weekly Refresh` chain | ok | Last run 5d ago. |
| `WF76 - Weekly Cron Audit` | ok | Last run 5d ago. |
| `WF77 Weekly Analyst Coverage` | idle | Schedules Monday. |

- **Sessions/agents:** Cron survived OpenClaw 2026.5.27 update. No unauthorized scheduler mutation. No live/paper/account action.

---

## 8. Doctrine & Continuity Health

- **Doctrine hierarchy preserved:** `SOUL.md` (7.8 KB) -> `AGENTS.md` (7.7 KB) -> `IDENTITY.md` (small) -> `USER.md` -> `TOOLS.md` (9.4 KB) -> procedures/skills -> `MEMORY.md` (8.6 KB) -> `HEARTBEAT.md`.
- **Boot/control surfaces:** Total 97,266 bytes - well inside the WF73 reduced budget. No truncation in `openclaw doctor`.
- **Active Workflows:** 20.8 KB after WF73 trim. P0/P1 register has all 13 required active lanes.
- **WF72 continuity:** Rolled up from 130.9 KB / 704 lines to 11.0 KB / 166 lines earlier today (2026-05-29 12:51 MST). Backup at `backups/20260529-1248-wf72-continuity-rollup/`.
- **Helper-lane discipline:** Subagent Spawn Handoff Template, Spawn and Closeout Governance Matrix, Automation Orchestration Protocol, Startup Truth Index, `veritas-self-improvement` skill, `disciplined-implementation` skill, and Major Workflow Contract Standard all flattened today around the narrow-packet default after morning helper-lane timeouts.
- **Daily memory:** `memory/2026-05-29.md` carries today's full log including pre-compaction flushes. `MEMORY.md` is curated and lean.

---

## 9. Recommended Sequence (Owner-Decision)

| # | Item | Owner | Effort | Boundary |
|---|---|---|---|---|
| 1 | Fix WF58 dashboard acceptance regression (Section 3.1) - unblocks post-close finance chain | main | ~30 min | Test/producer change only; no portfolio mutation. |
| 2 | Repair WF68 advisor in-band-labeling validator false positive (Section 3.2) | main | ~30 min | Validator/producer change only; no external delivery. |
| 3 | Harden WF63/WF67 paper-position cron wrapper - same heredoc fix as morning cron (Section 3.3) | main | ~10 min | Cron payload edit only. |
| 4 | Propose archive microbatch 2A-5 packet for cron/operator + extraction probes (Section 4.1) | main | Propose + await approval | No move without owner approval; `delete_count=0`. |
| 5 | Decide memory-search provider posture (set OPENAI_API_KEY or disable; Section 4.3) | Randall | 1 min | Local config only. |
| 6 | (Optional) Propose stale-tmp review packet for > 7d artifacts (Section 4.2) | main | Propose + await approval | Review-only; no move without owner approval. |
| 7 | (Tracked) Pin `@openclaw/codex` and `@openclaw/diagnostics-otel` next time plugins are touched (Section 6.2) | main | Defer | Plugin config only. |

---

## 10. Boundary Reaffirmations

The following remain untouched and must remain untouched without explicit owner authority:

- No SQL-canon expansion beyond the exact 265 approved metadata rows.
- No SQL writes; no SQL-first consumer migration while guard blocked.
- No portfolio, canon, sleeve, sizing, cash, or risk-rule mutation.
- No trade/account/brokerage/money movement.
- No paper submit/cancel/sell outside WF67 with exact scoped request, fresh kill switch, guard validation, redacted audit, main-session notification, and Randall's exact approval.
- No live endpoints/credentials, close/liquidation endpoints, or paper-to-live promotion.
- No config/auth/channel/service/runtime mutation without explicit approval and first-class tooling.
- No archive move/delete without exact owner-approved microbatch packet with hash/reference/rollback/validator proof.
- No customer/public retail SaaS use until privacy, retention, export/delete/access-control, source licensing, delivery channel, customer-safe renderer, and qualified counsel/compliance gates are resolved.
- No new durable control surface or doctrine rewrite from this audit.

---

## 11. Proof Artifacts Referenced

- `tmp/dashboard-acceptance-report.json`
- `tmp/run-summary-post-close.json`
- `tmp/intraday-alerts/advisor-alert-packet.json`
- `tmp/intraday-alerts/advisor-alert-packet-validation.json`
- `tmp/sql-canon-retail-grade-readiness.json`
- `tmp/finance-intelligence-router-qa-*.json`
- `tmp/wf78-live-25-pilot-import-gate.json`
- `tmp/finance-intelligence-state.sqlite`
- `tmp/veritas-canon-cache.sqlite`
- `tmp/veritas-artifact-index.sqlite`
- `tmp/boot-surface-size-guard.json`
- `tmp/workflow-hygiene-check.json`
- `tmp/wf73-boot-core-bloat-baseline-2026-05-29.json`
- `tmp/wf73-soul-agents-bloat-reduction-apply-2026-05-29.json`
- `tmp/wf72-archive-microbatch-2a3-apply-report-2026-05-29.json`
- `tmp/wf72-archive-microbatch-2a4-sql-probes-apply-report-2026-05-29.json`
- `tmp/wf72-entry-stop-helper-no-drift-pilot.json`
- `06. Playbooks/Active Workflows.md`
- `06. Playbooks/Startup Truth Index.md`
- `06. Playbooks/Project Continuity/Workflow 72 - Financial OS Efficiency Restructure and Priority Compression.md`
- `06. Playbooks/Project Continuity/Workflow 73 - Queue Index and Boot Surface Optimization.md`
- `memory/2026-05-29.md`

---

*Audit complete. No mutations performed beyond validator report writes. Awaiting owner direction on the recommended sequence in Section 9.*
