# Skills and Earnings Workflow Audit - 2026-04-29

## Purpose

Capture the next-session skill/workflow direction without bloating core files.

This audit focuses on how the current skill stack and script stack should absorb recurring earnings work, especially the note layer under `05. Intelligence/Earnings/`.

---

## Current state

### Active OpenClaw finance skills

These are the live workspace skills today:
- `veritas-fundamental-pass`
- `veritas-macro-pass`
- `veritas-technical-pass`
- `veritas-positioning-pass`
- plus presentation/reflection/governor support skills

These already cover most of the **analysis logic**:
- company quality and valuation
- macro regime judgment
- technical readiness and entry discipline
- portfolio action and ranking

### Packaged Cowork skill drafts

Packaged but not active in the OpenClaw workspace skill system:
- `veritas-weekly-brief`
- `veritas-portfolio-update`
- `veritas-deep-dive`

These are most useful as **workflow/orchestration references**, not as drop-in live skills.

### Current earnings note layer

Current scorecards present in `05. Intelligence/Earnings/`:
- `VRT Q1 2026 Post-Earnings Scorecard.md`
- `LMT Q1 2026 Post-Earnings Scorecard.md`

This is enough to prove the note pattern exists, but not enough to call the earnings workflow mature.

---

## Main finding

The real gap is **not raw analysis skill coverage**.

The real gap is **recurring workflow ownership** for post-earnings closure:
- when to run the post-earnings chain
- how to turn `tmp/post-earnings-prep.json` into note-layer updates
- how to mark closure state honestly
- how to sync earnings conclusions into the broader operating board
- how to avoid leaving earnings interpretation half-finished across multiple notes

In blunt terms:
- the system can already analyze
- the system does **not yet fully own earnings closure as an end-to-end operating workflow**

---

## Where earnings work currently lives

### Canonical interpretation home
- `05. Intelligence/Earnings/<Ticker> <Quarter> Post-Earnings Scorecard.md`

### Supporting machine artifacts
- `tmp/post-earnings-prep.json`
- `tmp/post-earnings-note-targets.json`

### Related downstream notes that often need sync
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `02. Markets/Watchlist.md`
- `05. Intelligence/Weekly Intelligence Brief.md`
- `05. Intelligence/Event Calendar.md`

This means earnings handling is inherently cross-note and should be treated as a workflow skill, not just a writing task.

---

## What should be built next

## 1. Promote a real `veritas-weekly-brief` workspace skill

Priority: highest.

Why:
- recurring high-value output
- already has a packaged draft
- should own script order, evidence inputs, staleness rules, and judgment-slot writing

What it should own:
- `run_finance_refresh_chain.py sunday`
- required note stack reads
- how to use `tmp/weekly-intelligence-brief.json`
- how to reconcile machine summary with live note truth
- how to handle stale/manual/partial inputs explicitly

## 2. Build or convert a real `veritas-portfolio-update` workspace skill

Priority: high.

Why:
- current positioning skill decides; it does not fully synchronize the board
- the portfolio layer spans multiple notes with real drift risk

What it should own:
- refresh inputs
- stale-band checks
- earnings-block / post-earnings state checks
- sync order across watchlist / trigger sheet / technical sheet / portfolio snapshot
- explicit no-silent-drift rule

## 3. Add a dedicated earnings workflow skill

Priority: high, but after weekly-brief and portfolio-update structure is clear.

Recommended name:
- `veritas-post-earnings-sync`

Why this should exist:
- post-earnings work is not just “analyze the quarter”
- it requires structured closure from script artifact -> scorecard -> board sync -> closure state

What it should own:
1. run `python scripts/run_finance_refresh_chain.py post-earnings`
2. inspect `tmp/post-earnings-prep.json`
3. inspect `tmp/post-earnings-note-targets.json`
4. create or update the canonical earnings scorecard note
5. classify closure state:
   - Reported
   - Interpreted
   - Synced
   - Closed with follow-up
6. push required updates into the board notes
7. explicitly record unresolved gaps such as:
   - missing IR confirmation
   - no entry band yet defined
   - thesis intact but not deployment-grade
   - sector read-through pending

This should be a **thin orchestration skill**, not a replacement for:
- `veritas-fundamental-pass`
- `veritas-technical-pass`
- `veritas-positioning-pass`

Those three should supply the judgment logic inside the earnings workflow.

---

## How earnings updates should fit the automation model

### Good automation boundary

Automate:
- script refresh chain execution
- artifact preparation
- candidate note targeting
- scorecard scaffolding
- closure-state scaffolding
- stale/missing-source warnings

Keep human/agent judgment in the note layer for:
- thesis implications
- sector read-through
- whether a beat actually matters
- whether a setup is deployable or still blocked
- whether the quarter confirms, weakens, or invalidates the thesis

This preserves the finance operating rule:
- scripts prepare evidence
- notes own the final judgment

### Bad automation boundary

Do **not** automate straight from raw artifact to canonical conclusion without judgment.

That would create exactly the kind of false confidence this workspace is supposed to avoid.

---

## Concrete next-session build order

1. Convert/promote `veritas-weekly-brief` into an active workspace skill
2. Convert/promote `veritas-portfolio-update` into an active workspace skill
3. Create `veritas-post-earnings-sync` as a thin workflow skill
4. Reuse existing analysis skills inside that earnings workflow instead of duplicating research logic
5. Only after that, decide whether `veritas-deep-dive` should become:
   - a thin orchestrator, or
   - just source material for improving the active analysis skills

---

## Skill-design rules from this audit

- Do not add another overlapping generic “research” skill unless the current analysis spine proves insufficient.
- Prefer thin workflow/orchestration skills over duplicate analysis skills.
- Put repeatable procedure in skills, not in core doctrine files.
- Keep earnings automation honest: scaffold and sync automatically, interpret manually.
- Treat `05. Intelligence/Earnings/` as the canonical post-earnings interpretation layer, not as a dumping ground for raw script output.

---

## Bottom line

The next useful skill work is not “make Veritas smarter at stocks.”
It is:
- make recurring outputs owned
- make cross-note sync reliable
- make post-earnings closure systematic
- keep the judgment layer human/agent-authored and evidence-first

That is the cleanest path to more automation without turning the vault into brittle noise.
