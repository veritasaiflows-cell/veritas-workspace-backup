# Notes Layer Audit Checklist

## Purpose
Run a compact recurring QA pass on the human note layer and its supporting control surfaces.

## When to use
- after a structural cleanup pass
- after a major workflow closes
- during weekly hygiene reviews
- when the vault starts feeling noisy, duplicative, or misleading

## Checklist

### 1. Root sanity
- root contains only core files, numbered domains, essential implementation folders, archive surfaces, or documented exceptions
- no new stray top-level folders were added without policy justification
- empty scaffolding is removed
- documented exceptions are still actually justified

### 2. Entry-point sanity
- `Home.md` still reflects the real review order
- `Home.md` links still point to the current operator surfaces
- no second root navigation system has been created

### 3. Control-plane continuity sanity
- active queue, registry, and active continuity note agree
- daily continuity still lives in `memory/YYYY-MM-DD.md`
- active project continuity still lives in `06. Playbooks/Project Continuity/`
- no shadow continuity system has appeared

### 4. Canonical-note sanity
- core operator notes do not present stale state as current fact
- generated artifacts are not silently outranking canonical notes
- duplicate operator surfaces are either reconciled, demoted, or explicitly staged

### 5. Playbooks sanity
- protocols, workflows, specs, policies, contracts, and checklists use clear suffixes
- `06. Playbooks/` is not accumulating ambiguous one-off notes
- active project notes live in `Project Continuity/`, not mixed into generic playbooks
- workbook assets stay under `06. Playbooks/Workbooks/`

### 6. Generated-surface sanity
- durable scripts stay in `scripts/`, not `tmp/`
- machine outputs stay in `tmp/` unless a documented exception exists
- any root-level generated surface is explicitly documented and still necessary

### 7. Archive sanity
- retired material is filed under `09. Archive/`
- active project notes, chain logs, and canonical finance notes are not archived casually
- archive moves preserve reference value without polluting the active review path

### 8. Skill/document boundary sanity
- durable procedures belong in skills or governed playbooks, not random notes
- environment facts belong in `TOOLS.md`, not scattered in audits
- repeated workspace rules are promoted into protocol files instead of living only in chat

### 9. QA output
For each pass, record:
- what drift was found
- what was changed
- what was left alone and why
- any documented exception still in force
- the next smallest cleanup or trust-hardening move

## Default rule
Prefer the smallest structural correction that restores clarity.
Do not reorganize for aesthetics alone.
