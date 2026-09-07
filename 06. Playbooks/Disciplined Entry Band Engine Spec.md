# Retired - Disciplined Entry Band Engine Spec

Retired on 2026-08-29 by the alerts-and-recommendations OS pivot.

The former design proposed automated band derivation, schema changes, gated canonical apply, and portfolio-maintenance behavior. Those routes are revoked. Static levels are read from guarded alert canon and are never re-derived or auto-applied by the active OS.

Current work may surface evidence gaps, freshness decay, band context, or invalidation alerts through `03. Alerts and Recommendations/` and the deterministic alert chain. Any future canonical-level policy change requires a new explicit owner decision, source-backed proposal, exact diff, backup/rollback, and post-change validation.

This compatibility path owns no current state, producer, scheduler, or apply authority.
