# Workflow 10 Subagent Session Lifecycle Reliability QA Audit - 2026-05-03

## Verdict
**Pass with named runtime residue.** Workflow 10 can close honestly once the continuity/control surfaces are updated to reflect the implemented trust rules and residue routing.

## What this workflow actually fixed
- `scripts/run_summary_refresh.py` no longer leaves consumer-facing `execution.chain_status` stuck at `running` after successful finance-window runs; raw runtime state is preserved separately for audit.
- Scheduled-window run summaries now also match the written v1 fail-closed policy again: `presentation_allowed=false` and `canonical_note_mutation_allowed=false` after regeneration.
- `06. Playbooks/Automation Run Summary Contract.md` now explicitly documents the execution block and the normalization rule for the finalizer self-observation race.
- `06. Playbooks/Automation Orchestration Protocol.md` now states that runtime/session state is advisory until artifact-level proof and owner surfaces agree.
- `06. Playbooks/Cron Run Ledger.md` no longer treats stale `execution.chain_status="running"` as an open bug; it now points to the normalized/raw split honestly.
- Stale root `.git/worktrees/` metadata was rechecked live, proven inactive against `git worktree list`, and the four read-only orphan directories were cleared so prune stopped flagging them.

## Verification evidence
- `openclaw status` -> gateway/session runtime reachable; active sessions visible
- `openclaw memory status --deep --json` -> embedding probe still fails credentials; memory index still not trustworthy enough to treat as primary continuity proof
- `python scripts/run_summary_refresh.py --window morning/post-close/post-earnings/sunday` -> all regenerated successfully
- regenerated run summaries now show terminal `execution.chain_status` with raw state preserved separately when needed
- regenerated run summaries now keep scheduled-window trust fields fail-closed again instead of silently promoting downstream rights on clean runs
- `git worktree prune --dry-run -v` initially surfaced four stale read-only metadata directories; after bounded manual clearing, the dry run returned clean

## No-go assumptions that now need to stay explicit
- async exec completion events are not completion proof by themselves
- interactive auth prompt fragments are unresolved until the underlying task is reconciled explicitly
- memory search/runtime state remains helpful but non-authoritative while credentials/index health are broken
- filesystem cleanup success must be verified against active-worktree truth, not inferred from tool noise alone

## Residue that stays named after closure
- memory embedding credentials / indexing health remain broken and deserve separate follow-up if the workflow chain later prioritizes it
- runtime/session state is better bounded, but still not "boring" enough to outrank artifact-level proof
- this workflow does not solve thesis-parity or macro-manual-dependency debt; those stay with Workflows 11 and 12

## Close condition
Close Workflow 10 when:
1. workflow continuity note reflects the implemented fixes
2. queue/registry say Workflow 10 closed and Workflow 11 active
3. the closure checkpoint is committed after those surfaces are synchronized
