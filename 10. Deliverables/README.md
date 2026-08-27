# Deliverables

This folder is the human-facing shelf for PDFs, Excel workbooks, HTML views, and CSV exports that Randall should be able to find without digging through `tmp/`.

## Rule

- `10. Deliverables/` is for presentation and retrieval.
- `tmp/` remains the machine proof, staging, and validation surface.
- `state/deliverables/` owns the machine-readable manifest and SQLite index.
- A copied deliverable is not portfolio canon, trade approval, paper/live execution approval, cash authority, or proof deletion authority.

## Current Categories

- `Finance Intelligence/` - finance workbooks, finance PDFs, HTML dashboards, and related CSV exports.
- `Command Center/` - human-facing command-center HTML exports and view-model presentations.
- `WF75/` - retail-readiness PDFs, HTML briefs, workbooks, and renderer-regression exports.

Use `INDEX.md` after running `python scripts\deliverables_publisher.py --write --validate`.
