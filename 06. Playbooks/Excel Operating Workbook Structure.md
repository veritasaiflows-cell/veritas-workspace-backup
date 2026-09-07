# Excel Operating Workbook Structure

## Purpose

The workbook is a read-only operating view for alerts, recommendations, evidence, and freshness. It helps Randall scan exceptions and review decisions; it is not canon and does not grant action authority.

Scripts feed structured exports, the workbook organizes them, owner surfaces retain judgment, and PDFs present selected conclusions.

## Workbook tabs

### 1. Control Panel

One-screen health view containing:

- export and source timestamps
- chain and validation status
- counts by alert state
- freshness-decay and suppressed counts
- evidence gaps and critical warnings
- current macro or regime label with its as-of date

### 2. Alerts

One row per ticker and timeframe:

- ticker and company
- coverage tier or research lane
- alert state
- trigger reason
- band-low, band-high, and invalidation context
- current relationship to the band
- catalyst and thesis state
- evidence date, freshness, and confidence
- next review time and owner pointer

### 3. Recommendations

One row per active review item:

- ticker or theme
- recommendation state and review horizon
- concise thesis
- base, bull, and bear summaries
- key risks and uncertainty
- no-chase or suppression reason when applicable
- Randall's decision point
- evidence and canon pointers

Recommendations are judgment records, not transaction instructions.

### 4. Catalysts and Thesis Changes

One row per catalyst or material thesis event:

- ticker or theme
- event type and expected or observed date
- evidence status
- prior and current thesis state
- alert consequence
- unresolved follow-up
- source and owner note

### 5. Evidence and Freshness

One row per evidence object or required source:

- source identifier and type
- covered ticker or theme
- published, observed, and ingested timestamps
- freshness threshold and current state
- confidence and lineage hash when available
- validation result and failure reason

### 6. Macro and Market Context

One row per current regime or market signal:

- signal name and scope
- observed value or label
- as-of time and source
- confidence and freshness
- alert or recommendation implication
- uncertainty and invalidation condition

### 7. Validation and Lineage

Machine-facing proof view containing:

- chain run identifier and window
- source files and hashes
- row counts
- schema version
- validation checks, warnings, and errors
- export status

## Controlled vocabularies

Use the active alert states:

- Recommendation review
- Band entry
- Near band
- No chase
- Invalidation alert
- Thesis change
- Catalyst alert
- Freshness decay
- Monitor only
- Suppressed

Freshness values are `Fresh`, `Aging`, `Stale`, or `Unknown`. Confidence values are `High`, `Medium`, `Low`, or `Unrated`. Validation values are `Ok`, `Warning`, `Blocked`, or `Suppressed`.

## Operating rules

- Freeze headers, enable filters, and keep identifiers visible.
- Use one table per decision job and stable column names.
- Keep formulas simple, local, and auditable.
- Highlight exceptions and freshness failures instead of decorating normal rows.
- Never overwrite a valid prior export with a partial or unvalidated build.
- Read canonical levels; never derive or write them from the workbook.
- Preserve missing values as missing rather than filling them with guesses.

## Prohibited content

The workbook must not contain or maintain system-owned sleeves, holdings or positions, allocation or weight state, sizing or tranche plans, cash state, order packages, transaction instructions, or paper/live execution routes. It is not a ledger, account view, or execution console.

## Acceptance

The workbook passes when Randall can answer, quickly and truthfully:

1. Which alerts require review now?
2. Which recommendations are supported, suppressed, or stale?
3. What evidence changed the thesis?
4. Which bands or invalidations are relevant?
5. What is uncertain, missing, or overdue?
6. Where did every material field come from?

If it cannot answer those questions without implying execution authority, it is not ready.
