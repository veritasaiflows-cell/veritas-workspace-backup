# Veritas Encounter Contract

## Purpose

Make routine Randall/Veritas encounters faster, clearer, and safer by standardizing prompt shortcuts, approval wording, update cadence, and stop lines.

This procedure routes behavior. It does not grant approval, replace finance canon, mutate schedules, or outrank `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`, skills, workflow notes, or exact owner artifacts.

## Trigger

Use this procedure when Randall asks for:

- status or "what changed today"
- approvals or approval-card prep
- finance ticker reviews, deployment reviews, or paper-order prep
- long work updates
- skill/doctrine/procedure patches
- efficient prompting or repeated encounter patterns

## Read First

- `SOUL.md`, `USER.md`, `TOOLS.md`
- `skills/veritas-response-contract/SKILL.md`
- `06. Playbooks/Startup Truth Index.md`
- For finance requests: SQL/JSON finance front doors, ticker card, and full-answer artifacts before any external source
- For cron or scheduled work: `skills/cron-automation-manager/SKILL.md` and cron contracts/control packets

## Prompt Shortcuts

| Randall says | Veritas should do |
|---|---|
| `Status?` | Use `tmp/veritas-status-card.json` or read-only status renderer; do not regenerate heavy control packets. |
| `What changed today?` | Summarize today's memory/work completions, practical value, remaining blockers, and next action. |
| `Review only` | Inspect and critique; do not edit or apply. |
| `Proceed if safe` | Execute reversible/local work inside existing authority; stop at owner-gated boundaries. |
| `Approval check` | Present exact approve/deny item, scope, proof, risk, expiration if relevant, and blocked actions. |
| `Decision card: <ticker>` | Workspace-first finance decision card with recommendation vs approval split. |
| `Ticker review: <ticker>` | Workspace-first full review when requested; use market-hours rule and recent-news/source-open check. |
| `Patch doctrine` | Use Skill Workshop or the owning procedure path; preserve existing body/details before apply. |
| `Cron cadence audit` | Review contracts/schedules/artifacts only; no schedule mutation without a later exact diff approval. |

## Approval Format

When Randall approves work, prefer exact scope:

```text
Approved: <specific action/proposal/job/file set>.
Allowed: <safe operations>.
Blocked: <surfaces/actions not approved>.
Proof required: <validator/artifact/check>.
Expires/limit: <time, run count, or scope limit when relevant>.
```

For finance:

```text
Approved: prepare review or paper-order approval card for <ticker>.
Not approved: capital deployment, execution, live trading, account changes, cash/sizing/risk-rule mutation, or owner-approval inference.
```

Approval language authorizes only the named scope. Silence does not expand authority.

## Update Cadence

For short work, answer directly after proof.

For longer work, send brief updates when one of these changes:

- a blocker/root cause is found
- a file/procedure/skill edit is about to happen
- validation passes or fails
- authority boundary is reached
- a helper/audit lane is spawned or returns material findings

Updates should be one or two sentences. Do not narrate every command.

## Finance Web-Search Rule

Default: workspace-first, no broad web discovery.

Use local finance cadence first:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\finance_intelligence_state.py ticker <TICKER> --pretty
python scripts\artifact_index.py ticker-card <TICKER>
python scripts\artifact_index.py answer-packet <TICKER>
```

Use web/source-open checks only for:

- full ticker reviews
- deployment requests
- approval-card or paper-order preparation
- explicit user requests for external verification
- local workspace freshness failure where the answer would otherwise make a material current claim

For ordinary quick reads, status, ranking, and workspace-backed answers, use current local artifacts. If local data is stale, missing, or contradictory, report a workspace freshness blocker and run/repair the local refresh path when safe instead of substituting broad web search.

Recent-news checks should be narrow: official company/SEC/IR source first when fundamentals are material, plus one credible recent-news check when the review/deployment request needs current news risk.

Market-hours rule:

- If market is open, use local live/intraday quote readiness before current-price or entry-action claims.
- If market is closed, prefer the post-close chain and local quote overlay. Do not do redundant live quote searches by default.
- Post-close quote evidence is review evidence, not execution freshness.

## Cron Cadence Rule

Cron should match the natural update cadence of the data:

- intraday / market-window: prices, trigger state, deployment gates, paper-readiness guard proof
- daily / post-close: ticker cards, full-answer freshness, WF78/WF84/WF85 routing, earnings/catalyst deltas, market regime inputs
- weekly: macro/sector posture, research opportunity resets, OS improvement radar, broad portfolio/readiness review
- monthly: slow-changing reference material, structural audits, non-urgent governance hygiene, stale index/sprawl reviews

Do not promote slow-moving data to daily cron just because it is useful. Do not demote market-sensitive data below daily/post-close if it supports ticker freshness, deployment, or risk decisions.

Any schedule change requires a separate cron diff packet, owner approval when material, backup/rollback where applicable, and post-apply validation.

## Stop Lines

Stop and ask for exact approval before:

- cron schedule mutation
- config/auth/channel/network/service/runtime mutation
- destructive cleanup, archive, move, delete, or rename
- finance canon, portfolio, cash, sizing, or risk-rule mutation outside exact approved gates
- paper/live/brokerage/account action
- capital deployment or trade/order execution
- external/customer/public delivery
- treating generated artifacts, ticker cards, quote proof, or recommendations as owner approval

## Proof

For procedure/doctrine edits:

- update the owning index when relevant
- run `openclaw skills check` when skills changed
- run targeted diff/whitespace checks on touched files
- record material operating changes in today's `memory/YYYY-MM-DD.md`

For cron cadence audits:

- run or inspect `cron_contract_validator.py`, `cron_freshness_spine.py`, and `cron_control_packet.py`
- classify findings as schedule mismatch, stale domain input, technical failure, monitor-only stale, or owner-gated action
- produce recommendations first; do not mutate schedules in the audit

## Next Action

Use the prompt shortcut if clear. If not clear, infer the narrowest safe mode from Randall's wording and proceed until complete, blocked, or exact approval is required.
