---
name: "veritas-prompt-book-operator"
description: "Prompt-book work; reusable prompt families. Validate metadata contracts, route eval gaps, and apply explicitly approved skill changes."
---

# Prompt Book Operations

## Procedure

1. Identify the repeated internal challenge, prompt family, workflow/self-prompt pattern, helper contract, or prompt-book PM request. Check `06. Playbooks/Veritas Prompt Book.md` and existing registry coverage; finish with the family and missing coverage identified rather than a duplicate entry.

2. Refresh proof in this order. For harness-readiness evidence only, use the first four commands and their corresponding outputs; PM-job and morning-P0 refreshes belong to full prompt-book operations, not the readiness subset.

```powershell
python scripts\prompt_book_registry.py --write --write-md --validate
python scripts\prompt_book_eval_fixtures.py --write --write-md --validate
python scripts\prompt_book_linter.py --write --validate
python scripts\prompt_book_eval_gap_packet.py --write --write-md --validate
python scripts\prompt_book_pm_job_packet.py --write --write-md --validate
python scripts\prompt_book_morning_p0_contract.py --write --write-md --validate
```

Read the corresponding `tmp/prompt-book-registry.json`, `tmp/prompt-book-eval-fixtures.json`, `tmp/prompt-book-lint.json`, `tmp/prompt-book-eval-gap-packet.json`, `tmp/prompt-book-pm-job-packet.json`, and `tmp/prompt-book-morning-p0-contract.json`. Verify statuses before using an entry as proof.

3. Update missing metadata-only registry coverage through the owner scripts. Require objective, source artifacts, allowed/forbidden tools, output schema, proof, stop lines, eval status, and authority boundary. Fixtures probe required output fields, review-only authority, stop lines, and absence of raw capture; store no prompt/response bodies, tool payloads, system prompts, secrets, credentials, or user request bodies. Rerun lint and fixtures until the entry is valid or the failure is explicitly blocked.

4. Route missing regression coverage through the eval-gap packet and implementation through the PM-job packet. Treat clean fixtures as metadata-contract regression proof, not model-quality, AGI/ASI, training, or self-modification proof. Finish with each gap either covered or assigned a concrete follow-up.

5. When repeated use evidences a durable skill change, use Skill Workshop under its available publication policy. Inspect affected bodies and the proposal's complete artifact inventory before revision; merge rather than replace unrelated procedure. When supplying `support_files` to a revision, include the complete retained bundle: an empty array removes supporting files, it does not mean leave them unchanged. Inspect the revised inventory and read back changed artifacts before evaluation or apply; verify reference targets and body-size limits as well as the main text. Consolidate duplicate proposed changes without rejecting or quarantining proposals absent explicit authorization. Report a clean scan, evaluator results and independent procedure review separately; zero configured evaluator results is not an automated pass, and a timed-out reviewer supplies no verdict. Apply only explicitly approved scope through Skill Workshop; finish with actual applied status and intact artifacts, not inferred approval or validation.

6. After an approved skill apply, run:

```powershell
python scripts\skill_workshop_body_guard.py --write --validate
openclaw skills check
git diff --check -- skills
```

Refresh the prompt-book proof chain and verify the resulting live skill and metadata contracts. Report registry status, fixture count, eval-gap count, PM-job count, actual proposal dispositions, validation evidence, and remaining blockers.

## Stop Lines

Keep raw prompts, responses, tool payloads, system prompts, secrets, and authorization headers out of stored proof. Prompt-book work grants no finance/canon/portfolio/cash/sizing/risk changes, paper/live/account actions, cron schedule edits, runtime config, channels, credentials, external delivery, or inferred owner approval. Stop at any requested expansion beyond the authorized metadata or skill scope.
