# Advanced Capability Pilots

Status: synthesis only
Owner workflow: WF88
Generated page type: evaluation_contract
Authority boundary: review-only map; no canon, approval, execution, cron mutation, portfolio mutation, model training, or owner approval inference.
Promotion path: wiki insight -> WF88 recommendation -> WF74/PM/Skill Workshop/validator route -> proof -> explicit approval or validated implementation where allowed.

## Source artifacts

- `tmp/advanced-capability-pilot-packet.json`
- `data/evals/advanced-capability-pilot-fixtures.json`
- `tmp/frontier-capability-eval-spine.json`
## Current pilot state

- Fixture-ready pilots: `6`.
- Executed pilots: `0`.
- Promotion-ready pilots: `0`.
- Validation: `ok`.

The current contracts cover strict Structured Outputs, programmatic tool recovery, Responses multi-agent beta, explicit prompt caching, persisted reasoning, and max/pro reasoning. The explicit-cache contract now requires a stable cache key, a supported explicit breakpoint, at least 1,024 prefix tokens, a variable suffix, two matched requests, and cached/write token usage fields. These contracts define isolated request and measurement shapes only; they made no external API calls and captured no raw prompts, responses, reasoning, or tool payloads.

A later runner needs matched baselines, privacy-safe attribution, cost limits, failure injection, and authority-stop proof. No model route, runtime, configuration, or promotion follows from this page.
