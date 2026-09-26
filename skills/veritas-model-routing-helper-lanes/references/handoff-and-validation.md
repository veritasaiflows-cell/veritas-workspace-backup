# Handoff Contract And Validation Budget

Moved verbatim from the parent `SKILL.md` on 2026-09-25 to keep its body under 10,000 characters.

## Required Handoff Contract

Before dispatch, record:

- parent job, lane, phase, attempt number, and retry count;
- expected backend, exact model, and thinking;
- task shape, authority class, write scope, and exact leased writes;
- explicit workspace-relative base path;
- at most 6 files, 120,000 total bytes, and 30,000 estimated context tokens;
- sorted file inventory, sizes, SHA-256 hashes, manifest hash, and frozen snapshot ID;
- deterministic preflight status and proof;
- deliverable, acceptance criteria, stop lines, rollback note, next recipient, and timeout;
- fresh persistent transport proof when that backend is selected.

Re-use the same frozen snapshot for repair or QA when inputs did not change. If files changed, generate a new snapshot. Do not resend full transcript history when a bounded delta and exact owner files suffice.

## Validation Budget

- `micro`: deterministic proof plus Main verification.
- `narrow`: focused tests plus Main verification.
- `shared` or `major`: deterministic preflight followed by one fresh independent QA pass.

Independent QA is risk-based, not automatic for every patch. Use it for shared contracts, broad surfaces, finance/runtime/authority sensitivity, or judgment-heavy behavior. Cap ordinary rework at one bounded repair plus one fresh QA pass; after a second substantive rejection, stop and rescope rather than replaying the same large context.
