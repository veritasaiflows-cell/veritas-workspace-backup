# Retrieval Metadata and Notes Field Standard

## Purpose
Give audits, research notes, workflow notes, and major reports a consistent retrieval handle without creating a second truth system.

## Verdict
A small standardized retrieval block helps. The workspace already has strong retrieval anchors through folder paths, headings, daily memory, workflow continuity notes, Obsidian search, and the SQLite artifact index. The missing layer is a compact, repeated human-readable metadata block that makes status, owner, next action, and archive posture searchable without opening every note.

Do not use this block to replace the body of the note or to declare financial truth. It is an index aid.

## Where to use it
Use on:
- major workflow continuity notes under `06. Playbooks/Project Continuity/`
- dated audits under `08. Audits/`
- research notes where status, ticker, catalyst, or next action matters
- operating procedures whose owner or status may be ambiguous

Do not retrofit every legacy note immediately. Add it when a note is created, materially revised, or repeatedly hard to find.

## Standard block
Place this near the top, after the title and before long narrative sections:

```md
## Retrieval Notes
- Type: audit | workflow | research | procedure | report
- Status: active | monitoring | closed | blocked | archived | superseded
- Owner surface: <canonical owning note/script/workflow>
- Authority: canonical | review-only | generated | historical | procedure
- Workflow: WF## / none
- Key entities: <tickers, systems, scripts, assets, or themes>
- Source freshness: fresh | partial | stale | manual-dependency | unknown
- Next action: <one concrete action or none>
- Archive posture: keep-active | archive-candidate-after-YYYY-MM-DD | superseded-by <path> | permanent-reference
- Tags: #veritas/<domain> #wf/<id> #status/<status>
```

Use only the fields that help retrieval. If a field is unknown, say `unknown`; do not invent precision.

## Authority rules
- `Authority` describes the note's role, not permission to mutate state.
- `review-only`, `generated`, and `historical` must never imply portfolio mutation, deployment-state mutation, trade execution, or owner approval.
- For finance notes, final action authority remains with the owning canonical note layer and explicit owner approval.

## Archive posture rules
- `keep-active`: currently used in live workflows or navigation.
- `archive-candidate-after-YYYY-MM-DD`: can be proposed for archive after that date if no active references remain.
- `superseded-by <path>`: retrieval should route to the newer note.
- `permanent-reference`: keep for doctrine, proofs, or historically important decisions.

## SQLite / Obsidian use
- Obsidian can search these fields directly.
- Future SQLite note indexes may parse `## Retrieval Notes` blocks as derived metadata.
- SQL hits must still link back to source Markdown before judgment.

## Stop lines
- Do not add tags or fields that imply approval, execution, or canonical truth beyond the note's real authority.
- Do not auto-archive a note solely because the block says archive-candidate; verify live references first.
- Do not use metadata cleanup as a substitute for fixing stale body content.
