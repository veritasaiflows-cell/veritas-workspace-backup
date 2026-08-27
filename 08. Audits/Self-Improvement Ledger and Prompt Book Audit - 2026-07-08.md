# Self-Improvement, Ledger, and Prompt Book Audit - 2026-07-08

Owner: Veritas main session
Scope: WF74 self-improvement loop, question-route usage ledger, prompt book / route catalog, and their PM candidates.
Authority: review/proof only. No skill apply, no cron/config mutation, no finance/canon/portfolio action, no owner-approval inference.

## Conclusion

The self-improvement and prompt-book layers are structurally healthy (validators clean, zero eval gaps, zero over-budget routes, zero auto-apply risk), but two loops are running on scaffolding instead of real data: the usage ledger has never recorded an actual tool-call count, and the top WF74 opportunity (regressed cron signals, priority 92) has a generated patch plan that nobody has opened a lane for. The system is good at generating recommendations and weak at consuming them.

## Evidence (refreshed 2026-07-08 ~08:45 MST)

| Surface | Result | Proof |
|---|---|---|
| WF74 opportunity queue | ok, 4 opportunities | `tmp/wf74-improvement-opportunity-queue.json` |
| WF74 auto-patch proposer | ok, 4 plans (3 patch plans), auto_apply=0 | `tmp/wf74-auto-patch-proposer.json` |
| Prompt book registry/lint | ok, 15 entries, 0 eval gaps | `tmp/prompt-book-lint.json` |
| Eval gap packet | ok, 0 gaps | `tmp/prompt-book-eval-gap-packet.json` |
| Prompt book PM jobs | ok, 4 jobs | `tmp/prompt-book-pm-job-packet.json` |
| Route catalog health | ok, 8 routes, 0 over budget, 0 stale | `tmp/route-catalog-health.json` |
| Usage ledger | ok, 8 rows, metadata-only, raw capture blocked | `tmp/question-route-usage-ledger.json` |

## Findings

### F1 - Usage ledger has zero real usage data (material)
All 8 ledger rows show `actual_tool_calls: null` and `usage_event_recorded: false`. Budget compliance (`over_budget=false` everywhere) is derived entirely from static estimates, so the ledger cannot yet detect a route that actually blows its budget. The recording CLI exists (`question_route_usage_ledger.py --record --route-id <id> --actual-tool-calls <n>`) but is never invoked after answering a routed question.

### F2 - Top WF74 opportunity is stalled at "plan generated" (material)
"Repair regressed cron signals after completed migration plan" (priority 92) has patch plan `wf74-auto-patch-9982cbad32c6` ready, but no implementation lane has been opened. This is the same top blocker flagged in the morning status. The loop-trace closure rule says a chat mention does not close an item — by our own standard this item is open routing debt.

### F3 - Route catalog health packet does not ingest lint status (minor)
`tmp/route-catalog-health.json` shows `lint_status: null` even though the linter reports `status=ok`. The morning control plane's single health packet is missing one of its inputs. Low risk today (lint is clean), but it means a future lint failure would be invisible in the aggregated view.

### F4 - Prompt book coverage is complete but static (observation)
15 registry entries, 0 eval gaps, 0 fixture gaps. Healthy — but zero gaps for multiple refreshes can also mean the registry is not absorbing new friction. WF74 produced 0 `skill_workshop_requests` and 0 `prompt_book_candidate` classifications this cycle, consistent with either genuinely low friction or under-detection. No action forced; watch whether new friction events ever classify as prompt-book candidates.

### F5 - Owner-gated plans are correctly parked (healthy)
4 owner-gated plans, `execution_guardrail_review` correctly isolated for the execution-posture item, `auto_apply_count=0`. Authority boundaries are behaving as designed. No drift found.

## Recommendations (priority order)

1. **Open a bounded implementation lane for the cron-signal repair patch plan** (`wf74-auto-patch-9982cbad32c6`). Highest-priority WF74 item, plan already generated, low-risk. This converts the audit's biggest finding into work. Needs your go-ahead to open the lane.
2. **Wire actual-usage recording into routed answers.** Lightest viable version: after answering via a catalog route, record `--actual-tool-calls` once. Candidate: fold into the prompt-book-operator skill's response contract so it is procedural, not memory-dependent. Route as a small patch/skill revision (pending proposal, not auto-applied).
3. **Fix `lint_status` ingestion in `route_catalog_health.py`.** Small deterministic patch; fits the existing `patch_plan` class.
4. **Accept the 4 prompt-book PM jobs as the standing backlog** (eval-fixture upkeep, cron/helper prompt-contract lint, isolated-agent template feed, token-heavy prompt compression). The two medium-priority jobs (cron-contract lint, template feed) are the next real capability gains after items 1-3.
5. **No action on F4/F5** — monitor-only.

## Boundaries preserved

No patches applied, no skills applied, no cron/schedule/config changes, no finance/portfolio/canon mutation, no paper/live/account action. All recommendations require either a scoped lane (1-3) or stay review-only (4-5).
