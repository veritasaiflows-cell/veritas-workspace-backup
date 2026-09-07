# WF72 Phase 4 - SQLite Lineage Expansion Proposal

Generated: 2026-05-22T07:24:11Z  
Status: proposal ready / review-only

## Bottom line

Expand the existing `scripts/artifact_index.py` SQLite spine, not a new database family. The next minimal step is to index official IR capture artifacts, source-field lineage, and exact canon-proposal staging as **derived SQL support surfaces only**. SQL may help stage and audit proposals; it must not become canon, apply changes, infer approval, or touch paper/live execution.

## Inputs reviewed

- `scripts/artifact_index.py`
- `scripts/official_ir_capture_validator.py`
- `data/fundamentals/official-ir-capture-contract.json`
- `tmp/wf72-phase4-sql-truth-spine-prototype.json`
- `tmp/official-ir-captures/amd-q1-2026.json` sample capture shape
- `06. Playbooks/Project Continuity/Workflow 72 - Financial OS Efficiency Restructure and Priority Compression.md`

## Proposed minimal schema additions

### 1. `official_ir_capture_runs`

One row per review-only official IR/SEC capture artifact.

Key columns:

- `artifact_run_id` FK -> `artifact_runs(id)`
- `source_file` unique
- `ticker`, `company_name`, `period_end`, `capture_generated_at_utc`
- `review_only` default `1`
- `resolved_for_apply` default `0`
- `source_type`, `source_url`, `filing_url`, `accession_number`, `retrieved_at_utc`
- `source_text_sha256`, `source_html_sha256`, `source_title`
- `summary_json`, `raw_json`

Indexes:

- `(ticker, period_end, capture_generated_at_utc)`
- `(source_text_sha256, source_url)`

### 2. `official_ir_capture_fields`

One row per captured field from `captures.*`.

Key columns:

- `capture_run_id` FK -> `official_ir_capture_runs(id)`
- `artifact_run_id` FK -> `artifact_runs(id)`
- `ticker`, `period`, `field_name`, `status`
- `value_json`
- `source_url`, `source_section`, `excerpt`, `excerpt_sha256`
- `inferred` default `0`
- `capture_date_utc`, `note`
- `manual_required`, `not_disclosed`
- `raw_json`

Indexes:

- unique `(capture_run_id, field_name)`
- `(ticker, field_name, period)`
- `(status, manual_required, not_disclosed)`
- `(excerpt_sha256)`

### 3. `source_field_lineage`

Explicit downstream-to-upstream field lineage only. No ticker/date inference.

Key columns:

- downstream artifact/file/table/row/field
- `lineage_kind`
- upstream artifact/file/table/row/field
- upstream `source_url`, `source_section`, `excerpt_sha256`
- `confidence` default `direct_or_declared`
- `raw_json`

Use this to connect Today-card/capital/canon-staging fields back to official capture rows only when the upstream evidence is declared or mechanically traceable.

### 4. `canon_proposal_staging`

Exact review-only staging for proposed canon-note text changes.

Key columns:

- `artifact_run_id`, `source_file`
- `proposal_id`, `target_file`, `target_section`, `proposal_kind`
- `authority_classification`, `requires_owner_approval`
- `proposal_apply_allowed` default `0`
- `applied` default `0`
- `old_text_sha256`, `new_text_sha256`, `diff_sha256`
- `evidence_status`, `validator_status`, `source_lineage_status`
- `status`, `raw_json`

This should become the single SQL staging/audit view for exact proposal diffs. It still must not apply them.

### 5. `canon_proposal_evidence_links`

Many-to-many links from staged proposals to official capture fields, validator runs, source artifacts, or other indexed evidence.

Key columns:

- `canon_proposal_staging_id`
- `evidence_kind`, `evidence_table`, `evidence_row_id`
- `evidence_source_file`, `evidence_field`, `evidence_sha256`, `evidence_url`
- `required`, `status`, `raw_json`

## Migration / backfill plan

1. Bump `SCHEMA_VERSION` from `2` to `3`.
2. Add the new tables/indexes inside current `init_schema()` using `STRICT` tables.
3. Extend artifact discovery to include `tmp/official-ir-captures/*.json`, excluding `*-validation.json` and `all-validation.json` from capture-run ingestion.
4. Add `official_ir_capture` and optionally `official_ir_capture_validation` artifact types.
5. Route capture validation artifacts through existing `validator_runs` rather than creating duplicate validator tables.
6. Insert one `official_ir_capture_runs` row per capture artifact and one `official_ir_capture_fields` row per required/available field.
7. Compute `excerpt_sha256` from the exact excerpt text; compute `manual_required` and `not_disclosed` from status.
8. Backfill `source_field_lineage` conservatively only where links are explicit/declarative. Leave ambiguous links absent.
9. Rebuild `tmp/veritas-artifact-index.sqlite` in one transaction with WAL, `foreign_keys=ON`, and `busy_timeout=5000`.
10. Emit a read-only report with counts, status distribution, hash coverage, and zero forbidden authority flags.

## Query examples

```sql
-- Latest official capture status by ticker
SELECT r.ticker, r.period_end, COUNT(f.id) AS fields,
       SUM(f.manual_required) AS manual_required,
       SUM(f.not_disclosed) AS not_disclosed,
       r.source_type, r.source_url
FROM official_ir_capture_runs r
JOIN official_ir_capture_fields f ON f.capture_run_id = r.id
GROUP BY r.id
ORDER BY r.capture_generated_at_utc DESC;
```

```sql
-- Fields that should degrade downstream confidence
SELECT ticker, period, field_name, status, note, source_file
FROM official_ir_capture_fields
WHERE status IN ('manual_required', 'partial', 'not_disclosed_in_release')
ORDER BY ticker, field_name;
```

```sql
-- Staged canon proposals that are not lineage-clean or violate apply stop lines
SELECT proposal_id, target_file, proposal_kind, evidence_status,
       source_lineage_status, requires_owner_approval
FROM canon_proposal_staging
WHERE source_lineage_status != 'verified'
   OR proposal_apply_allowed != 0
   OR applied != 0
ORDER BY target_file, proposal_id;
```

```sql
-- Official evidence attached to one staged proposal
SELECT c.proposal_id, c.target_file, e.evidence_kind,
       f.ticker, f.field_name, f.status, f.source_section, f.excerpt_sha256
FROM canon_proposal_staging c
JOIN canon_proposal_evidence_links e ON e.canon_proposal_staging_id = c.id
LEFT JOIN official_ir_capture_fields f
  ON e.evidence_table = 'official_ir_capture_fields'
 AND e.evidence_row_id = f.id
WHERE c.proposal_id = ?;
```

```sql
-- Authority violation guard
SELECT source_file, surface, flag_name, flag_value
FROM authority_flags
WHERE flag_value = 1
  AND flag_name IN (
    'canonical_note_mutation_allowed',
    'portfolio_mutation_allowed',
    'proposal_apply_allowed',
    'trade_execution_allowed',
    'trade_or_account_action_allowed',
    'owner_approval_inferred',
    'owner_approval_granted'
  );
```

## Authority stop lines

- SQL remains derived/index/staging only.
- Markdown owner notes and approved apply artifacts remain canonical.
- SQL may stage exact proposal rows, but may not apply them.
- Clean validation, complete source fields, or verified lineage must not imply owner approval.
- Never set these true from SQL: `proposal_apply_allowed`, `applied`, `canonical_note_mutation_allowed_by_sql`, `portfolio_mutation_allowed_by_sql`, `trade_or_account_action_allowed`, `paper_order_allowed_by_sql`, `owner_approval_inferred`.
- No edits to canon notes, `Active Workflows.md`, config, credentials, authority surfaces, paper/live orders, account state, cash/sleeve/risk rules, or channel/service posture in this phase.
- Ambiguous lineage stays `unverified`; do not fabricate joins from ticker/date proximity.

## Validation gates

- `python -m py_compile scripts\artifact_index.py scripts\test_artifact_index.py`
- `python scripts\artifact_index.py rebuild`
- New read-only query smoke if implemented:
  - `python scripts\artifact_index.py official-ir --limit 10`
  - `python scripts\artifact_index.py canon-stage --limit 20`
- `python scripts\official_ir_capture_validator.py --all --write --output tmp\official-ir-captures\all-validation.json` returns zero critical findings.
- `python scripts\test_artifact_index.py` covers:
  - official capture run/field counts
  - source hash and excerpt hash determinism
  - validation artifact ingestion
  - staging apply flags hard false
  - forbidden authority guard returns zero rows
- JSON proposal/report parses cleanly.
- Existing Phase 4 counts should not regress except where input artifacts are intentionally absent.

## Recommended tiny CLI additions

- `official-ir`: ticker, period, source, field counts, manual/partial/not-disclosed counts.
- `lineage`: explicit downstream field -> upstream source/capture field links.
- `canon-stage`: proposal id, target file, authority/apply flags, evidence/lineage status.

## Non-goals

- No canon note mutation.
- No `Active Workflows.md` mutation.
- No owner approval inference.
- No paper/live execution path.
- No replacement of markdown owner truth with SQLite.
