# OS Optimization RSI + Routing Enforcement Prework

Generated: 2026-05-24 14:46 MST  
Lane: RSI/department enforcement prework for WF74/WF71/WF73  
Status: review-only proposal; no implementation, no config/auth/channel/service mutation, no authority expansion

## Executive verdict

WF74 is ready to stop being a standalone artifact generator and become a production-feedback intake loop. The highest-value inputs are not more generic reflection; they are live validator failures, repeated main-session corrections, stale-note/drift events, cron/runtime failures, and helper-lane load-budget violations.

WF71/WF73 already have the right lightweight enforcement surface: `06. Playbooks/Operating Procedures/Subagent Load Budget and Staff Handoff Standard.md`. The next improvement should be a thin spawn-packet checklist plus optional lint/report artifact, not a new staff registry, second memory plane, or autonomous routing system.

## Sources inspected

- `06. Playbooks/Active Workflows.md`
- `tmp/wf72-post-audit-os-optimization-phase-plan.md`
- `06. Playbooks/Project Continuity/Workflow 74 - Veritas Recursive Self-Improvement Loop.md`
- `06. Playbooks/Project Continuity/Workflow 71 - Veritas OS Department Staff and Skill Ownership Model.md`
- `06. Playbooks/Project Continuity/Workflow 73 - Queue Index and Boot Surface Optimization.md`
- `06. Playbooks/Operating Procedures/Subagent Load Budget and Staff Handoff Standard.md`
- `06. Playbooks/Cron Run Ledger.md`
- Recent proof artifacts including `tmp/wf74-rsi-validation.json`, `tmp/wf74-rsi-evaluation-harness.json`, `tmp/wf74-rsi-trend-report.json`, `tmp/wf72-sql-to-note-drift-report.json`, `tmp/run-summary-sunday.json`, `tmp/run-summary-post-close.json`, `tmp/dashboard-validation.json`, `tmp/probability-readiness-validation.json`, `tmp/stale-intelligence-guardrail.json`, `tmp/cron-automation-authority-validation.json`, and `tmp/wf72-entry-stop-sql-activation-validation.json`.

## Current state facts that matter

- WF74 V1 validation is clean: `tmp/wf74-rsi-validation.json` reports `status=ok`, `checks=24`, `failed=0`.
- WF74 evaluation harness already has fixtures for stale current-state claims, approval inference from green/validator states, chat-only corrections, and untested skill/validator patches.
- WF74 trend report says repeated friction is concentrated in validator gaps, authority boundaries, workflow friction, implementation discipline, memory continuity, and RSI routing.
- WF72 SQL cache state has advanced: full 252-key entry/stop reference metadata activation is complete and validation-clean; total exact metadata rows are 265. Do not let older 2-row/6-row SQL validation artifacts create stale-current-state claims.
- Current drift surface is real but review-only: `tmp/wf72-sql-to-note-drift-report.json` shows 18 candidates, 12 review-needed, with authority flags false.
- Current cron/runtime friction remains a production input: Cron Run Ledger records the `sourceReplyDeliveryMode` / stale hashed Gateway import incidents and the WF76 phase plan calls out the morning job bug as the highest-leverage operational unblocker.
- Current validators are mostly warning-grade, not blocked: Sunday/post-close run summaries are warning with `stop_line=false`; dashboard has one warning for the suspended legacy weight gap; probability readiness remains warning because probability/win-rate claims stay blocked.

## Proposed WF74 production-feedback input contract

WF74 should ingest only high-signal events that meet one of these triggers:

| Trigger | Input source | Minimum fields | Action |
|---|---|---|---|
| Validator failure or blocked validator | `tmp/*validation*.json`, `tmp/run-summary-*.json`, `scripts/*` validator output | artifact path, status, failed checks, owning workflow, whether current or stale historical | classify as fix-now / monitor / stale-validator-maintenance / queue item |
| Repeated main-session correction | daily memory, durable memory, user correction, post-QA repair note | correction text, repeated pattern, owning file/skill/procedure, proof destination | route to skill/playbook/validator/fixture or daily-only memory |
| Stale-note / drift event | `tmp/wf72-sql-to-note-drift-report.json`, patch proposals, stale guardrails | target note, source artifact, drift status, review-needed flag, authority flags | create review packet or bounded main-session sync candidate; no cron-direct apply |
| Cron/runtime failure | Cron Run Ledger, run history, run summaries, cron authority validation | job id/name, failure mode, expected artifacts, overlap/rerun rule, required approval | create fix plan or diagnosis packet; config/channel/service changes gated |
| Helper load-budget violation | spawn packet, helper closeout, read-first list, output contract | primary department, read-first count, allowed writes, stop lines, proof, merge mode | require prompt repair or add optional lint finding |
| Authority-boundary near miss | QA report, boundary lint, finance validator, user correction | exact phrase/claim, forbidden implication, owner surface, corrected wording | add/update boundary fixture or forbidden-language check |

### False-positive controls

- Treat old blocked artifacts as RSI inputs only if they are still current, referenced by Active Workflows, or failed after the latest state transition.
- Separate `warning` from `blocked`; warning-grade artifacts should not become busywork unless repeated or misleading.
- Require an owning workflow or owner surface before adding a durable lesson.
- Do not promote one-off chat corrections to global memory unless they change future behavior.
- Never infer approval from a validator turning green.

## Production-feedback candidates found now

| Candidate | Evidence | Proposed routing | Notes |
|---|---|---|---|
| Cron runtime/import failure pattern | Cron Run Ledger `sourceReplyDeliveryMode` and stale hashed import notes; WF72 plan Phase 1 WF76 bug fix | WF76 diagnosis/fix packet; WF74 tracks as runtime-friction lesson after proof | No config/service patch without exact approval. |
| Stale SQL validation artifacts after WF72 expansion | Recent scan found old phase validations marked blocked/failed while current WF72 entry/stop activation validator is clean | WF74 stale-current-state fixture + WF72 validator maintenance note if repeated | Avoid claiming WF72 blocked from historical artifacts after 265-row activation. |
| SQL-to-note drift review backlog | `tmp/wf72-sql-to-note-drift-report.json`: 18 candidates / 12 review-needed / no apply authority | WF72 note-drift weekly cadence design; WF74 input when repeated drift patterns recur | Report/proposal only; main-session sync remains gated. |
| Probability readiness warning persists | `tmp/probability-readiness-validation.json`: warning 3 | WF55/WF68 advisor unlock lane; WF74 only if repeated probability-language slips occur | Blocks probability/win-rate claims. |
| Dashboard warning is known accounting gap | `tmp/dashboard-validation.json`: portfolio suspended weight gap warning | Monitor; not a WF74 fix unless it causes repeated false blockers | Warning-grade, not stop-line. |
| Helper load-budget enforcement currently procedural, not linted | WF71/WF73 + Subagent Load Budget procedure | Add lightweight spawn-template checklist now; optional lint later only if violations repeat | Avoid new durable control plane. |

## Lightweight spawn-template enforcement proposal

Embed this checklist into future helper-lane prompts and main-session spawn review. Keep it as a prompt/template discipline first; only add a validator if repeated violations appear.

### Required fields

1. Staff lane / primary department: exactly one.
2. Objective: one bounded outcome.
3. Read-first files: 3-8 exact files for normal lanes; 10-15 max only with explicit broad-audit exception.
4. Allowed actions: read-only, artifact write, patch proposal, or implementation; name write surfaces.
5. Forbidden actions / stop lines: include config/auth/channel/service, destructive cleanup, finance/trade/account/paper/live, canon/apply boundaries as applicable.
6. Output contract: exact artifact path(s), summary format, JSON parse requirement when applicable.
7. Acceptance proof: validator/test/direct-inspection gate.
8. Timeout / partial output: what to return if incomplete.
9. Merge expectation: review-only, needs audit, safe-to-merge proposal, or implementation complete.
10. Authority boundary: explicit false flags for owner approval, external execution, portfolio/canon mutation unless exact approved gate is in scope.
11. Positive trigger: why helper lane is needed instead of main-session one-step work.
12. Negative trigger check: why no forbidden/final-authority/config/destructive/live-account decision is being delegated.

### Main-session pre-spawn gate

- If task is one-step lookup/edit, final queue judgment, owner-facing synthesis, or authority-sensitive decision: keep in main.
- If task is multi-artifact, proof-heavy, implementation-heavy, broad-inspection, or independent-QA useful: delegate with one primary department.
- If read-first list exceeds budget without broad-audit label: shrink or split.
- If allowed writes collide with another helper or canonical owner surface: stop and re-scope.
- If proof gate is missing: do not spawn until proof is named.

### Optional lint/report later

If violations repeat, add a local review-only checker that reads a spawn handoff markdown/json and reports:

- missing primary department
- read-first count over budget
- no stop lines
- no proof gate
- no output artifact
- write-surface collision risk
- authority flags omitted or widened
- broad-audit exception missing

This checker should write only to `tmp/` and must not create a new staff registry, alter prompts/base model/system instructions, or mutate config/auth/channel/service surfaces.

## Validation gates for any implementation pass

Minimum gates before promotion:

1. `python scripts\wf74_rsi.py --validate-only` returns clean.
2. Any new JSON artifact parses.
3. If a spawn-template lint is added, run it against at least one valid and one intentionally-invalid fixture.
4. Re-run or inspect `tmp/wf74-boundary-lint-report.json` / Go boundary lint if authority-language surfaces change.
5. Confirm Active Workflows still states main session is final integrator and helper lanes do not move queue state.
6. Independent QA for any procedure/validator change that affects helper spawning or RSI routing.

## Hardening pass

Before closing any implementation based on this prework:

- Check for authority widening: no base-model/system prompt modification, no self-preservation/replication/resource-acquisition framing, no owner-approval inference, no portfolio/trade/account/paper/live authority, no config/auth/channel/service mutation.
- Check for control-plane bloat: no second memory tree, no new staff registry unless explicitly approved, no duplicate Active Workflows replacement.
- Check for stale-state traps: current WF72 state must reference 265 exact metadata rows, not older 13-row or 2-row claims.
- Check for cron boundary: cron may report/propose; no cron-direct canon apply or external delivery/channel expansion without approval.
- Check for load budget: helper lanes stay file-grounded and thin; broad audits are explicitly labeled read-only.

## Recommended next implementation slice

1. Patch WF74 input taxonomy/documentation or `scripts/wf74_rsi.py` to accept production-feedback classes above, but keep it review-only.
2. Add a spawn-template checklist section to the existing Subagent Load Budget procedure only if main session wants a durable text patch; otherwise use it directly in future handoffs.
3. Defer validator/lint implementation until one or two real helper-lane violations occur, unless Randall wants enforcement immediately.

## Stop lines preserved

No config/auth/channel/service mutation. No autonomous authority expansion. No second memory/control plane. No base-model/system prompt changes. No portfolio/canon/trade/account/paper/live authority. No archive/move/delete. No cron-direct canon apply. No generated artifact, validator, SQL row, or helper output becomes owner approval.
