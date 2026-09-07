# Automation Health Dashboard Prototype

Generated UTC: `2026-05-25T06:43:55Z`

## Boundary

- report_only: `True`
- mutations_performed: `False`
- authority: report-only local automation health prototype; no config/auth/runtime/network/cron mutation, no canon/portfolio mutation, no owner approval inference, no finance/trading/account/paper/live authority

## Overall

- Status: **blocked**
- Summary: Local automation surfaces are useful for review, but not cleanly ready for runtime expansion or model-driven capital action.

### Blockers / trust limits

- Native Codex/Gateway endpoint migration is blocked by plugin/core readiness and endpoint security gates.
- Probability readiness remains review-only: no owner decisions and insufficient retained outcome history.
- Trust layer may allow presentation/recommendation review, but capital action remains owner-gated and false.

## Readiness matrix

| Lane | Status | Key proof |
|---|---:|---|
| Cache/tool telemetry | `warning` | bootstrap pressure=0.857; oversized tool results=334 |
| OTEL telemetry | `enabled_receiving_metrics` | Do not enable logs/content capture, external export, or Gateway /v1 endpoints without a separate explicit approval packet. |
| Native Codex/Gateway | `blocked` | probable @openclaw/codex plugin/core version skew against pinned OpenClaw core |
| Cron | `ok` | enabled jobs seen=18; authority validation=ok |
| Validators | `ok` | dashboard acceptance all passed=True; capital=ok; governance=ok |
| Trust | `warning` | trust=review_required; presentation=True; capital_action=False |
| Probability | `not_ready` | outcome_ready=False; realized=5; owner_decisions=0 |
| Governance | `ok` | critical=0; warnings=0; info=1 |

## Local history / trends

- History path: `data/state-history/automation-health-dashboard-history.jsonl`
- Records before current: `9`
- Trend JSON: `tmp/automation-health-dashboard-trends.json`
- Trend MD: `tmp/automation-health-dashboard-trends.md`
- Privacy note: No transcript paths, locators, prompt text, tool inputs/outputs, command text, URLs, raw OTLP payloads, or artifact contents are stored.

## Redacted tool-result telemetry

- Transcripts scanned count: `1`
- Oversized tool results: `334`
- High severity tool results: `0`
- By tool: `{"cron": 2, "exec": 11, "process": 1, "read": 9, "web_fetch": 2}`
- By severity: `{"medium": 25}`
- Privacy note: Transcript paths, raw locators, previews, command text, URLs, and tool-output content intentionally omitted.

## Source artifacts

| Artifact | Exists | Status | Generated | SHA-256 |
|---|---:|---:|---:|---|
| `cache_efficiency_scorecard` | `True` | `None` | `2026-05-25T05:39:48Z` | `8852a4289519a48b` |
| `otel_prototype_readiness` | `True` | `None` | `2026-05-25T04:55:01Z` | `28490777554da66e` |
| `otel_enabled_proof` | `True` | `enabled_receiving_metrics` | `2026-05-25T05:24:19.148871Z` | `4a7b520961155775` |
| `native_codex_gateway_decision_packet` | `True` | `None` | `2026-05-25T05:02:53Z` | `5d69ee5eaeac0c3b` |
| `capital_deployment_recommendation_validation` | `True` | `ok` | `2026-05-25T01:29:38Z` | `68c5c2d0d6740dc7` |
| `probability_readiness_report` | `True` | `None` | `2026-05-25T01:08:39Z` | `366b1f0589a3397e` |
| `workspace_governance_truth_check` | `True` | `ok` | `2026-05-25T04:39:56Z` | `9f930c208fa834b7` |
| `cron_authority_validation` | `True` | `ok` | `2026-05-25T01:06:56Z` | `62aac767c83044bc` |
| `cron_status_snapshot` | `True` | `None` | `2026-05-21T21:42:43Z` | `5a0f8a78f63ac29e` |
| `dashboard_validation` | `True` | `None` | `2026-05-25T01:29:05.173835+00:00` | `291e6a07c6daf2a6` |
| `dashboard_acceptance_report` | `True` | `None` | `2026-05-24T21:22:08Z` | `68042f52e86b48da` |
| `run_summary_post_close` | `True` | `warning` | `2026-05-23T20:43:02Z` | `f4b6cdcfc17301e5` |

## Next actions

- Keep this dashboard report-only until it is reviewed against live operator needs.
- Keep OTEL local-only with logs/content capture/external export off unless a separate explicit approval packet changes that boundary.
- Use the redacted tool-result telemetry to reduce repeated large reads and cap command/web outputs before the next long run.
- Do not migrate native Codex or enable Gateway /v1 endpoints until the plugin/core skew and endpoint security packet are resolved.
- Continue outcome-retention capture before using probability outputs for ranking, sizing, or deployment decisions.
