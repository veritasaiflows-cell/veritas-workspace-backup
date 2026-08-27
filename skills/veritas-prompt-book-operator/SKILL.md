---
name: "veritas-prompt-book-operator"
description: "Operate metadata-only prompt book, eval gaps, and PM routing."
---

# Veritas Prompt Book Operator

Use this skill when Randall asks to build, inspect, update, lint, evaluate, apply approved prompt-book proposal changes, or route reusable prompt families, self-prompt patterns, helper-lane packets, internal challenge-solving loops, or prompt-book PM jobs.

## First-Hop Commands

```powershell
python scripts\prompt_book_registry.py --write --write-md --validate
python scripts\prompt_book_eval_fixtures.py --write --write-md --validate
python scripts\prompt_book_linter.py --write --validate
python scripts\prompt_book_eval_gap_packet.py --write --write-md --validate
python scripts\prompt_book_pm_job_packet.py --write --write-md --validate
python scripts\prompt_book_morning_p0_contract.py --write --write-md --validate
```

Primary artifacts:

- `06. Playbooks/Veritas Prompt Book.md`
- `tmp/prompt-book-registry.json`
- `tmp/prompt-book-eval-fixtures.json`
- `tmp/prompt-book-lint.json`
- `tmp/prompt-book-eval-gap-packet.json`
- `tmp/prompt-book-pm-job-packet.json`
- `tmp/prompt-book-morning-p0-contract.json`

## Operating Loop

1. Identify the repeated internal challenge, prompt family, helper contract, workflow prompt, or self-prompt pattern.
2. Refresh the registry, fixture, lint, eval-gap, PM-job, and pickup-contract proof.
3. Check whether the registry already has a prompt-family entry.
4. If the registry lacks coverage, update metadata-only registry entries through the owner scripts.
5. Run the linter before using a prompt-book entry as proof.
6. Route missing eval coverage through the eval-gap packet.
7. Route implementation work through the PM job packet.
8. Create or revise Skill Workshop proposals only when repeated use proves a reusable skill/procedure change is needed.
9. Keep proposals pending until Randall explicitly approves apply; when approved, apply only through Skill Workshop and run post-apply validation.

## Required Entry Contract

Each entry must include objective, source artifacts, allowed tools, forbidden tools, output schema, proof, stop lines, eval status, and authority boundary.

## Eval Fixture Contract

Fixtures are deterministic metadata probes. They assert required output fields, stop lines, review-only authority, and absence of raw capture. They must not store prompt bodies, response bodies, tool payloads, system prompts, secrets, credentials, or user request bodies.

A clean fixture packet means a prompt family has regression proof for metadata contract behavior. It does not mean model quality is proven, AGI/ASI exists, or authority expands.

## Skill Apply Contract

When Randall explicitly approves prompt-book Skill Workshop proposal apply:

1. Inspect the pending proposals through Skill Workshop.
2. Revise addendum-style existing-skill proposals into full-body merged proposals before apply.
3. Apply the new prompt-book operator first.
4. Apply follow-on self-improvement, PM, and cron updates only after the operator route is accepted.
5. Merge duplicate AGI harness updates into one proposal and reject or quarantine the superseded duplicate.
6. Run `python scripts\skill_workshop_body_guard.py --write --validate`, `openclaw skills check`, targeted `git diff --check -- skills`, and prompt-book proof refreshes after apply.

## Stop Lines

Never capture raw prompts, raw responses, tool payloads, system prompts, secrets, credential material, or authorization headers. Never claim AGI/ASI, model training, or autonomous self-modification from prompt-book work. Never auto-apply skills or doctrine. Never mutate finance/canon/portfolio/cash/sizing/risk state, paper/live/account actions, cron schedules, runtime config, channels, credentials, or external delivery. Never infer owner approval.

## Closeout

Report registry status, fixture count, eval-gap count, PM job count, Skill Workshop proposal IDs applied/rejected, validation proof, and remaining authority limits.
