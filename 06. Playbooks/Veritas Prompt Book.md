# Veritas Prompt Book

## Purpose

The Veritas Prompt Book is the governed registry for reusable prompt families, self-prompt patterns, helper-lane packets, and internal challenge-solving loops.

It is not a raw prompt vault. It stores metadata, hashes, source paths, contracts, eval coverage, stop lines, and PM routing. It does not store raw prompts, raw responses, tool payloads, system prompts, secrets, or approval authority.

## First-Hop Commands

```powershell
python scripts\prompt_book_registry.py --write --write-md --validate
python scripts\prompt_book_eval_fixtures.py --write --write-md --validate
python scripts\prompt_book_linter.py --write --validate
python scripts\prompt_book_eval_gap_packet.py --write --write-md --validate
python scripts\prompt_book_pm_job_packet.py --write --write-md --validate
python scripts\prompt_book_morning_p0_contract.py --write --write-md --validate
python scripts\question_route_catalog.py --write --write-md --validate
python scripts\question_route_usage_ledger.py --write --write-md --validate
```

Primary artifacts:

- `tmp/prompt-book-registry.json`
- `tmp/prompt-book-eval-fixtures.json`
- `tmp/prompt-book-lint.json`
- `tmp/prompt-book-eval-gap-packet.json`
- `tmp/prompt-book-pm-job-packet.json`
- `tmp/prompt-book-morning-p0-contract.json`
- `tmp/question-route-catalog.json`
- `tmp/question-route-usage-ledger.json`

## Morning P0 Pickup

Use the morning P0 contract when Prompt Book state needs implementation pickup or post-apply proof refresh:

```powershell
python scripts\prompt_book_morning_p0_contract.py --write --write-md --validate
```

The 2026-07-07 approved sequence is complete:

1. Reviewed the pending Skill Workshop proposals through Skill Workshop.
2. Revised and applied `veritas-prompt-book-operator` first after Randall's exact approval.
3. Revised and applied `veritas-self-improvement`, `veritas-pm-department`, `cron-automation-manager`, and the merged `agi-harness-readiness-operator` update.
4. Rejected the duplicate `agi-harness-readiness-operator` proposal as superseded.
5. Keep deterministic eval fixtures green and route future gaps through PM.

Current fixture targets are covered by `tmp/prompt-book-eval-fixtures.json`: `task-intake-contract-v1`, `agi-harness-mode-v1`, `finance-response-contract-v1`, `current-opportunity-approval-brief-v1`, `question-route-catalog-v1`, `question-route-usage-ledger-v1`, `helper-lane-contract-v1`, `wf88-wiki-synthesis-contract-v1`, `pm-control-intake-v1`, `retail-truth-routing-stop-lines-v1`, and `smb-service-packet-v1`.

Stop lines stay unchanged: no raw prompt/response/tool payload capture, no future Skill Workshop apply/reject/quarantine without exact approval, no cron schedule/runtime/config/channel mutation, no finance/canon/portfolio/cash/sizing/risk mutation, no paper/live/account action, no external delivery, no AGI/ASI capability claim, no autonomy promotion, and no owner approval inference.

## Operating Model

Use the prompt book when a prompt, self-prompt, reusable task contract, helper packet, PM intake, cron prompt contract, or Skill Workshop proposal pattern needs to become repeatable.

Each prompt-book entry should identify:

- prompt family ID
- owner workflow
- department
- source artifacts
- objective
- allowed tools
- forbidden tools
- output schema
- proof requirement
- stop lines
- eval status
- authority boundary

## RSI Loop

Repeated internal challenge flow:

1. WF74 detects repeated friction, stale procedure, prompt drift, eval failure, helper-boundary issue, or internal challenge recurrence.
2. The prompt-book registry identifies whether an existing prompt family already owns the pattern.
3. The eval-gap packet classifies missing fixtures or weak proof.
4. The PM job packet creates review-only implementation candidates.
5. Skill Workshop receives a pending proposal only when the pattern needs reusable skill doctrine.
6. No skill, doctrine, cron schedule, runtime config, finance state, or external output changes without its separate gate.

## Current Opportunity / Approval Brief

Use this deterministic first-hop route for questions like "What are my current opportunities and overdue items? What needs my approval?":

```powershell
python scripts\current_opportunity_approval_brief.py --refresh --write --write-md --validate
```

Add `--include-long-work` only when Randall asks about resumable/overdue long-running jobs:

```powershell
python scripts\current_opportunity_approval_brief.py --refresh --include-long-work --write --write-md --validate
```

This route refreshes only PM control, cron control, trade-grade decision cards, WF85 paper-deployment visibility, and owner-gated action queue packets. It targets a 6-7 call budget including memory recall, instead of broad exploratory scans. It does not use broad search, status-card fallback, or paper-position checks unless the packet is missing, stale, blocked, or Randall asks for those surfaces.

Authority remains review-only: no cron schedule/runtime/config mutation, no finance canon/portfolio/cash/sizing/risk mutation, no capital deployment, no paper/live execution, no external delivery, and no owner approval inference.

## Question Route Catalog

Use this catalog before answering recurring operational questions where the correct source path is known:

```powershell
python scripts\question_route_catalog.py --write --write-md --validate
```

For deterministic selection proof:

```powershell
python scripts\question_route_catalog.py --question "What are my capital deployment recommendations?" --write --write-md --validate
```

V1 route cards:

| Route ID | Use | Budget |
|---|---|---:|
| `current_opportunities_and_approvals` | current opportunities, overdue items, owner approvals | 6 |
| `skill_proposals_and_patches` | Skill Workshop proposals and skill patch state | 6 |
| `skills_modified_or_created` | live skills changed or newly created | 5 |
| `capital_deployment_recommendations` | capital deployment recommendations with finance stop lines | 8 |
| `daily_improvements_and_opportunities` | today's workflow/OS improvement queue | 7 |
| `implementation_agent_orchestration` | bounded implementation agents, model effort, QA posture, and validator proof | 8 |
| `prompt_book_asi_harness_readiness` | ASI-style harness discipline and Prompt Book readiness | 8 |

This is ASI-style harness discipline, not an ASI claim. The pattern is: classify the question, load the smallest trusted route, cap tool calls, return proof and limits, then escalate only when stale, blocked, ambiguous, or over budget.

If a route repeatedly needs more than 8 calls, create a PM improvement candidate rather than expanding free-form prompting. Do not create a new workflow for route failures.

Track route usage with metadata only:

```powershell
python scripts\question_route_usage_ledger.py --write --write-md --validate
```

When recording a concrete route pass, include only route ID, actual tool-call count, and stale/blocker flag:

```powershell
python scripts\question_route_usage_ledger.py --route-id current_opportunities_and_approvals --actual-tool-calls 6 --write --write-md --validate
```

The usage ledger must not store raw question text, response text, tool payloads, prompts, secrets, or delivery content. Over-budget rows create PM follow-up need; they do not expand route budgets or create new workflows.

## Promotion Rules

- `draft`: useful pattern identified, no repeat proof.
- `registry_v0_review_only`: metadata entry exists, no authority.
- `eval_covered`: deterministic fixture or validator exists.
- `approved_live_skill`: live skill owns the behavior.
- `deprecated`: retained for audit, not live routing.

Promotion requires validation proof. Clean prompt-book proof does not imply skill apply, authority expansion, finance deployment, paper/live action, or external delivery.

## Stop Lines

Never use this layer to:

- capture raw prompts, responses, tool payloads, system prompts, or secrets
- claim AGI/ASI or model training from prompt management
- auto-apply skills or doctrine
- mutate finance/canon/portfolio/cash/sizing/risk state
- create paper/live/brokerage/account action
- mutate cron schedules, runtime config, credentials, channels, startup, or services
- infer owner approval
- expose prompt-library content externally without a separate gate

## Current V0 Seed Entries

Registry v0 starts with task-intake, AGI harness mode, WF74 self-prompt review, finance response contract, current opportunity approval brief, question route catalog, question route usage ledger, WF74/WF88 loop trace, PM control intake, retail truth routing, SMB service packets, helper-lane contracts, WF88 wiki synthesis, and supervised finance source-scout/redteam templates.

The live count and eval gap state are in `tmp/prompt-book-registry.json` and `tmp/prompt-book-eval-gap-packet.json`; use those artifacts instead of stale hard-coded counts.
