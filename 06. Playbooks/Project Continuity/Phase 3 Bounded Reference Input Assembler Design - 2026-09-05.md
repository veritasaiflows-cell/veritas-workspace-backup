# Phase 3 bounded reference-input assembler design

Date: 2026-09-05, America/Phoenix. Owner: Main. Status: Main-accepted DESIGN after independent GLM challenge and the bounded clarifications recorded below; NO assembler implementation or activation approved by this document.

## Decision and scope

Build a pure, bounded reference-evidence serializer behind a guarded coherent-read dependency. Do not glue together the existing per-method readers and label the result a snapshot. Preserve the existing Phase3F evidence format and its verification; require an additional, hash-bound provenance package at the future orchestration boundary. If that binding cannot be enforced, block integration rather than accept a free-form sidecar or invent a database hash.

This follows Main acceptance of the coverage system/path patch, recorded in `tmp/coverage-acceptance-assembler-20260905/acceptance.json`. Coverage acceptance is not input-assembler, recurring-pipeline, Phase3H, or Phase4 acceptance. Current request authorizes DESIGN only.

## Verified source constraints

| Owner | Current behavior and consequence |
| --- | --- |
| `finance_sql_canon_access.py:412-424,832-850,1443-1587,1748-1762` | Guard, membership, reference, and freshness calls open separate read connections. There is no current public session that binds all reads to one transaction. A before/after file checksum is not a replacement. |
| `finance_sql_canon_access.py:1498-1587` | Resolver owns all active identity/witness validation, A+B selection, aliases, triples fingerprint and eligibility debt. Use it once; never fork the predicate or filter false-eligibility members. |
| `alert_level_freshness_controller.py:263-308` | Lineage reader opens the default DB independently, then hashes source files. Injecting a reference client alone does not redirect lineage. Files are outside the SQL transaction and need their own byte/hash observation. |
| `alert_level_freshness_controller.py:621-781` | Consumer requires exact top-level and row key sets, canonical path, a 64-hex database hash, full ordered tickers, scope fingerprint, and canonical scope-payload hash. It checks the database hash's shape, not its correspondence to the read snapshot. |
| `phase3f_external_canary_approval.py` | Existing `canonical_json_bytes` and strict evidence parser own byte encoding. Scope bytes and approved input bytes already have separate hash bindings; retain them. |
| `phase3g_dynamic_execution.py:65-137` | Dynamic path consumes explicit files and resolves scope once. It does not produce references/quotes, retention or digest. It must not acquire a second membership read during future integration. |

## Proposed interfaces (not existing APIs)

1. **Guarded read session, owned by the finance accessor:** one canonical read-only connection, query-only protection, bounded transaction deadline, and same-transaction guard checks. Resolve membership exactly once inside this session using the existing resolver's semantics. Return a session-bound frozen scope plus reference/freshness/lineage row material. SQL counts used by validation are not a second membership selection; tests must distinguish them.
2. **Bound reference-read bundle:** already-selected ordered A+B tickers; immutable canonical scope bytes and their SHA256; the original triples fingerprint; guard/read-session identity; canonical database origin; captured reference/freshness/lineage projections; source-file observations; missing-class diagnostics. Production constructors remain inside the guarded owner. Require a private construction sentinel and identity validation, following the existing verified-approval pattern, so ordinary callers cannot substitute a dictionary or a read-session identifier string. This is an in-process construction boundary, NOT cryptographic authentication or protection against arbitrary malicious Python code. Arbitrary caller dictionaries or `verified=true` flags are not proof. Synthetic injection is test-only and cannot enable the production entry point.
3. **Pure assembler:** consume that bound bundle, not a database path plus an arbitrary scope. Return canonical existing-v1 reference-evidence bytes and a provenance/debt manifest. No providers, SQL queries/writes, file output, policy loading, reservations, receipts, or authorization calls from serialization. All scoped validation occurs before any publishable bytes are returned.

The old two-new-file proposal is insufficient for end-to-end provenance. A separately scoped accessor/lineage dependency must precede it; this design does not authorize editing those owners.

## Coherent acquisition contract

- Establish a single read transaction before guard validation and the one resolver selection. All required SQL guard checks and reference/freshness/lineage SELECTs use that same connection and snapshot. Factor/reuse current owner logic; no alternate SQL tier owner or weakened guard. Roll back/close on success or failure; no SQL write, checkpoint, journal-mode change, schema change, or copied production database.
- With a deferred transaction, `BEGIN` alone does not establish the read snapshot; its first database read does. Guard validation must run in that transaction before membership selection, and all subsequent row reads must remain on it. Read-only WAL/shared-memory/open/read failures are systemic failures: emit no evidence package, call no providers, and never retry by opening read-write, repairing journals, or changing configuration. Test those failures without claiming that every missing shared-memory file makes read-only WAL universally impossible.
- A read transaction is a consistent observation at its start, not a promise that canon cannot change later. Release it before provider work. A bounded session-age check and the exact scope/payload binding govern subsequent use; do not hold a read lock across network work.
- Capture scope bytes immediately, deep-copy/freeze nested mappings, and verify them before/after assembly. `dataclass(frozen=True)` alone does not freeze dictionaries. Reject mutation, structural breaches, altered witnesses, unknown/duplicate tickers, or missing identity provenance. Full membership and false eligibility survive; over-envelope scope remains complete and separately blocks provider admission.
- Query reference/freshness and lineage rows only for the original ordered ticker tuple. Missing rows remain absent; never synthesize numeric bands, fill freshness defaults, promote eligibility, or recompute membership. Distinguish semantic missing/invalid evidence from guard/SQL/OS failures.
- Capture lineage source observations with safe workspace-contained, non-reparse paths and bounded reads. De-duplicate a source path/hash pair per bundle. Hash the exact bytes actually read; compare to the expected hash in the transaction's lineage rows. Missing file/hash mismatch is named non-ready evidence debt; SQL/OS/permission/resource failure aborts with a sanitized systemic error. Invalid/escaped source path aborts before content access. A non-atomic path check is not TOCTOU immunity; future acquisition must either provide a verified safe-open mechanism or explicitly block unsafe conditions.
- Do not claim a simultaneous SQL/filesystem snapshot. SQL rows belong to one transaction; file observations belong to exact captured bytes and observation times. Later file replacement cannot make those bytes newer. Reuse the captured observations in assembly; no second hash read silently replaces the observed version.

## Database identity and provenance (WAL-safe meaning)

`database_path` in existing v1 remains exactly `state/finance/finance-canon.sqlite`. `database_sha256` must be the real observed hash of that canonical main file, never a made-up value, readset digest, backup hash, or hash of concatenated main/WAL/SHM bytes. It is labeled **physical main-file observation only** in the manifest. Equal main-file hashes do not prove coherent SQL state, especially with WAL; this field is not the snapshot identity.

Capture that physical observation inside the acquisition window. Ordinary file hashing is not atomic against concurrent checkpoints; reject detected replacement/instability and retain the observation's time and limitations. Never assert that these observed bytes are the transaction's database snapshot or use their hash for coherence, source freshness, or authorization. SQL read-session binding remains the required coherence proof.

The required manifest separately binds: protocol version; acquisition start/end; canonical database origin and path-validation result; guard/version identity; read-session identifier; exact scope bytes hash/fingerprint; canonical readset digest over allowlisted membership/witness/reference/freshness/lineage projections; source-observation hashes; missing-class map; reference-evidence byte hash; and `snapshot_semantics=single_sql_read_transaction_plus_captured_source_observations`. Do not persist accounts, credentials, raw prompts, or unrelated DB rows.

A hash only binds content; it does not prove origin. Future orchestration must receive this bundle directly from the guarded session owner, verify its binding before any reservation/provider call, and bind the manifest digest and evidence digest into its immutable retained run inputs. Standalone imported evidence files with a self-authored sidecar remain insufficient. A separately reviewed consumer/transport change is required if the existing sealing path cannot carry this mandatory binding. No permissive fallback to v1-only acceptance.

## Exact serialization and debt behavior

- Reuse `canonical_json_bytes`; UTF-8, sorted keys, compact separators, no BOM/newline, no NaN/Infinity, then round-trip through the existing strict parser. Output remains under its existing 10 MiB limit. Reject overflow; do not truncate rows.
- Exact top keys: `schema`, `status`, `database_path`, `database_sha256`, `scope_fingerprint`, `scope_payload_sha256`, `tickers`, `reference_levels`, `evidence_freshness`, `lineage`, `errors`. Schema stays `veritas.phase3f.alert_reference_evidence.v1`; `status=ok` and `errors=[]` mean structurally assembled, never complete evidence. Use the consumer-owned exact dataclass/lineage field sets, with no extra fields inside v1. Bind extra diagnostics only in the separate manifest.
- `tickers` is the full ordered scope. Per-class maps contain only genuinely observed rows, keyed by original canonical ticker; no foreign keys or null-row placeholders. Preserve observed row values and their explicit non-ready states. Missing rows are omitted and named by ticker/class in the manifest.
- **Important current consumer limit:** with dynamic `allow_missing=True`, if any of reference/freshness/lineage is absent, `_phase3f_reference_evidence` discards that ticker's otherwise available reference/freshness values and supplies empty lineage. It does not remove the ticker. Preserve and test this conservative behavior; do not claim class-level preservation through the existing consumer. The manifest retains the precise debt, and quote observation remains independently tested. Changing this all-or-none behavior is a separate consumer-policy slice, not assembler scope.
- Distinguish `assembled_with_evidence_debt` in the manifest from systemic acquisition failure. A systemic failure returns no publishable evidence package and causes zero provider calls. No ordinary missing rows may mask a failed guard or database read.

## Bounds and failure behavior

Proposed first implementation limits (to validate in hermetic tests and read-load measurements): 30-second end-to-end acquisition/assembly deadline; no retry loop; at most 1,024 captured A+B members (complete scope is retained in a rejection diagnostic if exceeded), 1,024 unique source observations, 10 MiB per source, 64 MiB aggregate captured source bytes, and the existing 10 MiB serialized evidence cap. These are resource denial limits, NOT policy admission caps, tier caps, or permission to truncate. Use a monotonic deadline with a real SQLite progress/interrupt path and bounded file reads; a timeout constant or `busy_timeout` alone is not enforcement. Reject before providers on overflow or deadline. Provider policy remains separately authoritative for its smaller scope/component/attempt/duration/day limits.

Deadline proof must include guard validation (including `PRAGMA integrity_check`), source-file observation, physical hash capture, and serialization, not only row SELECTs. Byte caps alone do not bound stalled file I/O. Slice A must specify and fault-test a cancellation/containment mechanism for both blocked SQL and blocked file observation before claiming the 30-second bound; an uncancelled timeout race fails acceptance.

No artifact is current merely because it was assembled today. Retain source timestamps, missing/invalid freshness, and downstream market-calendar checks. Retry policy, if later needed, starts a whole new scoped acquisition; no mixing old membership and new references.

## Implementation sequence and tests

| Slice | Proposed scope | Required acceptance proof |
| --- | --- | --- |
| A: coherent read dependency | Exact bounded accessor and lineage-session changes plus hermetic tests; keep existing callers compatible | Synthetic WAL two-connection test: writer commits between membership and reference reads; bundle still uses one original snapshot. Guard failure aborts. One membership selection. No production DB access. Cancellation/deadline and closed-session rejection. |
| B: pure assembler | New `scripts/phase3g_recurring_reference_inputs.py` and `scripts/test_phase3g_recurring_reference_inputs.py` only, after A accepted | Deterministic exact canonical bytes; actual sealed consumer compatibility; full A+B including false flags; each missing class individually and in combinations; no foreign keys; no invented values; mutation/provenance/hash tampering rejected; NaN/duplicate/NFC/size bounds; zero queries/providers/writes from serializer. |
| C: orchestration binding | Separate reviewed session-to-assembler-to-sealed-input integration | Cannot bypass manifest/origin verification; one scope from acquisition through execution; proof input hashes retained; systemic failure zero providers; quote/provider and analyst-cadence boundaries preserved. |
| D: recurring parity/activation | Separately approved provider-specific quote intake, digest/retention parity, exact scheduler ownership/cutover | Capacity, rollback and mixed-mode quarantine proof; live readback. Not authorized here. |

Add adversarial tests for wrong canonical DB origin, fake physical hash, WAL commits invisible to main-file hash, source replacement and symlink escape, expired/mutated bundles, missing/malformed lineage, over-envelope-but-complete scope, injected SQL/OS failure, duplicate aliases and witness conflicts. Verify actual downstream debt and membership outputs rather than asserting only serializer success. Source-free test fixtures must not manufacture an authorization route.

## Acceptance and rollout boundaries

Main accepts the reviewed design, not readiness or apply authority. Muse authors any later authorized code, GLM performs independent actual-diff QA, and Main accepts exact hashes. Rollback for future local code is a hash-bound inverse preserving unrelated changes; package rejection must never overwrite shared production outputs. No cron install, provider call, policy change, SQL/canon/tier write, runtime/config change, cleanup, external delivery, capital, account, paper/live action, Phase3H start or Phase4 work follows from this design.

Next recommendation: approve/route Slice A as a new bounded local code contract, then B; do not dispatch the obsolete two-file-only assembler contract as if coherent-read provenance already exists.

## Review and Main adjudication

Independent review: `tmp/coverage-acceptance-assembler-20260905/glm-design-review/result.json`. GLM reported PASS with no blocking findings on the frozen design. Main verified its frozen-input/source hashes and reviewed its five advisory suggestions. Main integrated construction-sentinel precision, non-atomic physical-hash limits, read-only failure handling, full-path deadline coverage, and deferred-transaction ordering. Main rejected the overstatements that a Python private sentinel is non-forgeable against arbitrary in-process code or that read-only WAL is universally impossible when shared-memory state is absent.

The reviewer reported exceeding its 25-call budget (approximately 36 calls), with no machine-captured elapsed/usage accounting. Record this as a review-process incident, not an efficient or budget-conformant success; no token/cost, first-pass efficiency or operational-lane completion credit is claimed. Its source-backed findings remain advisory input to Main's independent design adjudication. The final clarified document is Main-owned; the original reviewed draft remains frozen rather than being retroactively relabeled as this version.

This design is complete as a reviewed architecture/dependency contract. Slice A mechanism and hermetic proof, Slice B implementation, Slice C binding, and all activation gates remain unimplemented/unaccepted. Detailed proof and final hashes live in `tmp/coverage-acceptance-assembler-20260905/design-closeout.json`.
