# Derived-Manifest Deleted-Sources Packet

Read when a derived code-graph owner refuses with deleted-sources-need-review
while the deletions sit uncommitted in the worktree. This file owns only the
evidence packet that unblocks an owner decision. The manifest prune and any
graph publish stay on the operator-owned owner path — graph updates are
outside this collection — and nothing here authorizes them. Evidence base:
the 2026-09-20 eight-script graph block.

1. Confirm the refusal shape. Read the owner's preflight/packet: reason
   `deleted_sources_need_review` with a `deleted_refused` list, plus backlog
   accounting (changed/selected/deferred counts, target caps). A refusal
   without that list is a different failure — do not use this packet.
2. Prove the deletions safe with three checks, all recorded before writing:
   live imports (search the code tree excluding generated snapshots, which
   regenerate each run — hits there are history, not dependencies; require
   zero live hits); scheduler/contract refs (search cron contracts and
   enabled payloads for the module names; require zero with the contract
   validator at zero drift); manifest rows and identity (confirm each deleted
   path is a manifest entry; record HEAD sha256 plus byte size per file by
   hashing the `git show HEAD:<path>` bytes — the worktree file is absent).
   Classify doc/skill mentions: an explicit prohibition against running the
   module supports removal; only a live dependency blocks it.
3. Stage the packet as applied:false. One JSON plus one human-readable twin
   under `tmp/`: per-file path, HEAD hash, size, removal reason, and
   rollback (`git checkout HEAD -- <paths>`); the proof trio from step 2;
   the proposed owner-path action (manifest prune via the incremental-owner
   publish with its guarded rollback preimages, then bounded refresh batches
   inside the owner's target/batch caps); the named approver and no inferred
   approval. Validate the JSON parses.
4. Never hand-edit the derived manifest, never restore or publish
   unilaterally, and never force the consuming job green while the block
   stands. The block is the design working; the packet is review-only until
   the owner approves.
