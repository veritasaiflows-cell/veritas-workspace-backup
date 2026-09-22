# Applied Proof and Usage

## Bounded Handoff

When delegating, provide an explicit workspace-relative base path, no more than 6 files / 120,000 bytes / 30,000 estimated context tokens, sorted inventory, byte sizes, SHA-256 hashes, contract hash, frozen snapshot ID, deterministic preflight, exact deliverable, validators, stop lines, next recipient, and timeout.

A persistent attachment lane must preflight the actual receiver/payload shape, not merely a nonce. For a shell-free receiver use a small manifest plus one raw UTF-8 source attachment at a time; verify readback names, bytes, hashes, and line limits before dispatch. Do not use compression or aggregate envelopes without a fresh proof for that exact decoder and reader.

State whether the lane is a `patch_draft` or verified `scoped_worktree_implementation`. A draft is not a shared-workspace change. Re-use an unchanged frozen snapshot for repair/QA. Send a changed-only delta when possible. Do not fork or replay the full conversation unless the worker genuinely needs it.

## Frozen Input and Applied Diff

For v3 handoffs, acceptance must bind the manifest schema to the handoff contract version; a v2 wrapper around a v3 handoff, or the reverse, blocks rather than downgrading proof requirements. Treat frozen input integrity and post-apply verification as separate phases: re-hash frozen sources before dispatch; after Main applies a patch, preserve immutable frozen metadata and verify the actual workspace state using each changed file's frozen before-hash plus its post-apply hash and size. A no-op or changed path outside the frozen scope blocks.

The applied diff must be a bounded, hash-matched workspace artifact with normalized workspace-relative paths. QA must use a hash-matched result artifact tied to that exact applied-diff hash, frozen snapshot, changed-path list, and post-apply file hashes. Each QA command needs a recorded zero exit result, hash-matched output artifact, and the exact changed paths/post-apply hashes it validated. A self-attested command list, arbitrary hash, or unrelated test command is not completion proof.

## Usage and Efficiency Closeout

For every material job record, when exposed:

- parent job, phase, attempt, retry, task shape, write scope;
- expected and actual backend/model/thinking;
- files, bytes, estimated context tokens, duration;
- input, cached input, uncached input, output, reasoning metadata, and total with explicit semantics;
- QA verdict, Main acceptance, incident state, rework, and proof;
- `provider_usage_unavailable` when the provider exposes no trustworthy counters.

Never invent token counts, use ingestion time as usage time, call API-equivalent cost an invoice, or store raw prompts/responses/tool payloads/headers/secrets/credentials/account identifiers.

Measure uncached and gross tokens per Main-accepted job, first-pass acceptance, time to accepted proof, retry tax, and escaped defects when the evidence is available. Prefer like-for-like comparisons. Incidents and invalid telemetry receive no success credit.

Automatic route ranking and promotion remain disabled. Randall may request descriptive efficiency review on demand; no fixed cohort pilot or minimum job count is required. Main must explicitly change policy.
