---
name: code-review-auditor
description: High-signal code review for OpenClaw workspace scripts and AI-generated patches. Use when reviewing diffs, validating correctness or maintainability, checking contract propagation after shared vocab or JSON changes, or preparing an independent QA pass before workflow closure.
---

# Code Review Auditor

Review the code that exists, not the story told about it.

## Read First

Read only what matters:
- the changed file or diff
- the owning workflow note if one exists
- the nearest upstream producer and downstream consumer
- the validator, test, or acceptance harness most likely to catch drift
- the latest audit note if this is residue review

## Review Lenses

Check these in order:
1. correctness
2. contract propagation
3. fail-closed behavior
4. freshness or timestamp honesty
5. maintainability and duplication
6. proof quality

## What to Look For

### Correctness
- wrong branch or bucket mapping
- stale constant or dead variable path
- hidden fallback that undoes the intended fix
- platform-specific runtime debt

### Contract propagation
- shared labels changed in one file but not peers
- manifest fields added without consumer updates
- summary surfaces still speaking legacy vocabulary
- validators still proving the wrong contract

### Fail-closed behavior
- degraded or missing inputs still treated as clean
- manual dependencies hidden from summaries
- presentation layer implying readiness not supported by artifacts

### Proof quality
- test expectations still match stale behavior
- harness mutation leaks between cases
- compile-only proof used where runtime artifact proof is available

## Review Procedure

1. Restate the claimed change in one line.
2. Inspect the owner file.
3. Inspect at least one adjacent consumer.
4. Inspect the proof surface.
5. Classify findings as:
   - blocking
   - should-fix-now
   - acceptable residue
6. Recommend the smallest next repair.

## Boundaries

- Review only unless Randall explicitly asks for implementation.
- Do not mutate files, config, auth, runtime, finance authority surfaces, or portfolio/canon artifacts as part of the review pass.
- Do not broaden scope into redesign unless the inspected change creates a blocking correctness or contract risk.
- Ground every finding in a concrete file, line, artifact, validator, or observed behavior.
- If proof is missing, stale, or only compile-level where runtime proof is needed, say that plainly instead of inferring success.

## Output Format

Return in this order:
- review scope
- files inspected
- blocking findings
- non-blocking findings
- proof assessment
- recommended next repair
