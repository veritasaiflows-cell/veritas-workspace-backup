<!-- openclaw:wiki:raw-source -->
# Advanced Capability Pilots

Canonical page: `wiki/scorecards-and-evals/Advanced Capability Pilots.md`
Canonical rendered SHA-256: `fe44632a15867af67c27a840e694d08d901d6824b893339417b3eac248511c62`.
Source snapshot SHA-256: `3601a6df6c84a49ca4416da23af657e1aaff9026ecf9c52e5f23dcc898744160`.
Authority: review-only retrieval mirror; canonical wiki and named owner artifacts remain authoritative.

## Query aliases

- advanced capability pilots
- isolated pilot gate
- pilot execution evidence

## Canonical content

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
