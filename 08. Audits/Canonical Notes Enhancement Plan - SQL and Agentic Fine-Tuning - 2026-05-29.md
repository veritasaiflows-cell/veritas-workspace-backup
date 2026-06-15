# Canonical Notes Enhancement Plan - SQL and Agentic Fine-Tuning - 2026-05-29

**Auditor:** Veritas main session (Claude Opus 4.8)
**Run window:** 2026-05-29 22:20-23:10 MST
**Scope:** Design plan to enhance the human-approved canonical Markdown notes — primarily `03. Portfolio/Execution Board.md` and `04. Research/Coverage and Watchlist.md` — so they are fine-tuned to interoperate cleanly with the SQL layer (WF72) and the agentic answer router (WF77/WF78), without surrendering their status as the top of the truth hierarchy.
**Posture:** Review-only design plan. No mutations performed. No portfolio, canon, sizing, cash, risk-rule, trade/account, paper/live, config/auth/channel/runtime, or owner-approval state changed. This is a proposal for Randall's approval, not an applied change.
**Companion artifact:** `08. Audits/Finance Workflow Efficiency Audit - WF72 WF77 WF78 - 2026-05-29.md` (this plan operationalizes the "make SQL real, but only the part that pays now" tension that audit surfaced).

---

## 1. Executive Summary

- **The problem in one line:** Our canonical finance truth lives in human prose, but our SQL layer and our router need machine-addressable structure. Today the two are bridged by *fragile prose-scraping*, which is exactly why WF72's SQL cache is **0 effective rows** and why every WF77 answer self-downgrades.
- **The fix in one line:** Add a small, fenced, machine-readable **canon anchor block** to the top of each per-ticker section in the canonical notes. Humans keep reading the prose below it; machines read the block above it. **One file, one source of truth, two readers.**
- **Why this is the right move now:** Unlike "make SQL fully canonical" (premature — no consumer pulls for it yet), enhancing the notes themselves pays off *immediately* through the router that already has real demand. The same change *also* lowers the future cost of SQL-first canon if/when retail SaaS unblocks. It is the one move that serves both lanes without betting on either.
- **What this is NOT:** It is not a second source of truth, not a sidecar, not a schema migration, not an authority change. The anchor block lives *inside* the canonical note, so it *is* canon. SQL and agents extract *from* it; they never override it.
- **Cost honesty:** This is real, bounded effort — ~42 ticker blocks across two notes, plus an extractor and a drift validator. It is not free, and if done carelessly it adds a maintenance tax. Section 7 explains how to make the *existing* automated band-maintenance path write the block so we do not double-maintain.

---

## 2. Why The Current Notes Fight The Machines

Evidence from the live canonical notes (read 2026-05-29):

**`03. Portfolio/Execution Board.md` — the data SQL needs, in a form SQL cannot trust.**
The per-ticker sections carry the exact levels the SQL cache wants — band low/high, stop, close — but they are embedded in free prose with bold markers and human caveats. Representative ETN block:
```
- Preferred entry band: **382.90 to 401.36** *(current artifact layer 2026-05-29)
- Reference band: **382.90 to 401.36** / reference stop **362.67** (current artifact layer 2026-05-29; volatile canon sync)
- Explicit stop / invalidation: **362.67**; below this level the setup is fail-closed pending fresh review.
- Close: **400.60** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
```
Problems for a parser:
- The same number (band, stop) appears 2-3 times in slightly different phrasings ("Preferred entry band", "Reference band", "Explicit stop / invalidation", "Reference stop"). A scraper must guess which is authoritative.
- Formatting noise: stray trailing `******`, `?` characters where em-dashes belong, inconsistent `to` vs `–` separators.
- **No machine-addressable identity.** There is no stable `canon_id` a SQL row or router answer can point back to. WF78 backlog items #7/#10 already flagged this exact gap.
- **No structured provenance.** WF72 is blocked precisely because rows lack `owner_source_path`, `source_sha256`, `source_timestamp`. That provenance exists conceptually ("current artifact layer 2026-05-29") but is not captured as fields anything can verify.

**`04. Research/Coverage and Watchlist.md` — universe truth without machine keys.**
Owns membership, tier, durable thesis/risk/act-when via Obsidian `[[wikilinks]]`. Excellent for humans; the wikilinks are not stable machine IDs, tiers are prose labels, and there is no per-ticker `last_reviewed`/`status` field the router can filter on.

**Net effect:** every consumer (SQL extractor, answer router, validator) must re-derive structure from prose on every pass. That is brittle, it silently rots when phrasing drifts, and it is the direct cause of the "0 effective rows" / "fresh quote required" failure modes.

---

## 3. Design Principle: One Note, Two Readers

The whole plan rests on a single principle that protects the truth hierarchy:

> **The machine-readable block and the human prose live in the same canonical file. The block is canon, not a copy of canon. SQL/agents read the block; they never become an alternate source.**

This keeps the truth hierarchy intact (human-approved canonical Markdown stays #1) while removing the prose-scraping fragility. There is no sidecar JSON to drift, because the structured fields *are* the note. The SQL cache simply becomes a fast index *of* the note, with verifiable provenance pointing back at the note — which is exactly what turns "0 effective rows" into "effective rows."

---

## 4. The Canon Anchor Block (proposed format)

Add one fenced block at the top of each per-ticker section. Proposal uses a fenced ```` ```canon ```` block with simple `key: value` lines (parses trivially, renders as a clean code box in Obsidian, survives copy/paste, and is visually distinct from prose so humans know it is the machine layer).

**Execution Board per-ticker anchor (example, ETN):**
```canon
canon_id: exec:ETN
owner: Randall (human-approved)
last_reviewed: 2026-05-29
status: deployable_now
authority: reference_only
band_low: 382.90
band_high: 401.36
stop: 362.67
close: 400.60
close_date: 2026-05-29
band_position: inside_band
source_path: tmp/technical-refresh.json
source_sha256: <hash of the owner-source artifact at review time>
source_timestamp: 2026-05-29T00:00:00Z
```
The existing human prose stays exactly where it is, immediately below the block. Nothing human-facing is lost; the caveats, narrative, invalidation logic, and authority language remain.

**Coverage and Watchlist per-ticker anchor (example):**
```canon
canon_id: cov:ETN
owner: Randall (human-approved)
last_reviewed: 2026-05-29
tier: core_candidate
status: active
thesis_pointer: [[04. Research/Coverage and Watchlist#ETN]]
exec_pointer: exec:ETN
```

### Controlled vocabularies (so machines validate without NLP)

| Field | Allowed values |
|---|---|
| `status` (exec) | `deployable_now`, `almost_deployable`, `wait_no_chase`, `watch_only`, `repair_do_not_touch`, `blocked` |
| `authority` | `reference_only` (only legal value — encodes the boundary structurally) |
| `band_position` | `inside_band`, `above_band`, `below_band`, `below_stop` |
| `tier` (coverage) | `core_candidate`, `tactical`, `speculative`, `portfolio_review`, `sector_monitor`, `etf_monitor` |
| `status` (coverage) | `active`, `watch_pool`, `expansion_queue`, `retired` |

These mirror the vocabularies already used in prose today (Section in Execution Board: "Deployable now / Almost deployable / Wait-no chase / Watch-only / Repair / Blocked"). We are encoding what already exists, not inventing new states.

---

## 5. What Each Field Buys Us

| Field | SQL layer (WF72) | Agentic router (WF77/78) | Human |
|---|---|---|---|
| `canon_id` | Stable primary key; rows point back to canon | Answers cite a stable target instead of a line number | Unambiguous reference in cross-notes |
| `last_reviewed` | Freshness gate input | Router can flag "review is N days old" deterministically | Sees staleness at a glance |
| `status` / `band_position` | Indexable enum, no NLP | Answer contract resolves state without parsing prose | Same words they already use |
| `band_low/high`, `stop`, `close` | Effective numeric rows | Band math is exact, not regex-guessed | Identical to current prose values |
| `source_path` + `source_sha256` + `source_timestamp` | **The three missing fields that unblock "0 effective rows"** | Provenance-backed answers, honest downgrade when hash stale | Audit trail of where the level came from |
| `authority: reference_only` | Boundary travels with the row | Router cannot accidentally imply execution entitlement | Boundary is structural, not just prose |

The provenance trio is the load-bearing part: it is the exact reason WF72's retail-grade readiness reports `blocked / 0 effective rows`. Capturing it *in the note* is what makes the SQL row trustworthy — and it does so without moving canon out of the note.

---

## 6. Phased Rollout (bounded, reversible, demand-ordered)

Ordered so each phase delivers value even if the next never ships.

- **Phase 0 — Spec + 1-ticker pilot (cheap, do first).** Write the anchor-block spec into `06. Playbooks/Notes Layer Governance Protocol.md`. Hand-author the ETN block in Execution Board as the reference example. Confirm it renders cleanly in Obsidian and parses. Approval checkpoint before touching the other 41.
- **Phase 1 — Execution Board anchors (the high-value 42).** Populate anchor blocks for all 42 names. Levels copy 1:1 from existing prose (no new analysis, no re-derivation). This is the phase that makes the router's band math reliable — the single highest-leverage outcome from the companion audit.
- **Phase 2 — Coverage and Watchlist anchors.** Add `canon_id`, `tier`, `status`, `last_reviewed`, and `exec_pointer` to each universe entry. Cross-link `cov:<T>` ↔ `exec:<T>` so the router can traverse universe ↔ execution without prose matching.
- **Phase 3 — Extractor + drift validator (the wiring).** One read-only script parses the ```` ```canon ```` blocks and (a) populates/refreshes the SQL cache rows with real provenance, and (b) runs a **drift check**: does the structured block agree with the prose values in the same section? Mismatch = loud failure, never a silent cache preference. This is what converts "0 effective rows" into effective rows *and* enforces canon-beats-cache mechanically.
- **Phase 4 — Router consumption + schema freeze.** Point WF77's answer contract at `canon_id` + structured fields instead of prose scraping. Then freeze: no new card fields unless both populatable-with-real-data and decision-relevant (per the companion audit's WF77 recommendation).

Each phase is independently committable and independently reversible (the blocks are additive Markdown; deleting them restores the prior note exactly).

---

## 7. Avoiding The Maintenance Tax (the honest risk)

The companion audit's strongest objection to "make SQL real" was that **provenance captured now goes stale before the consumer exists**, and re-hashing on every band change is a recurring tax. Bands *do* change often — Execution Board shows automated band-maintenance edits on 2026-05-21, -22, -26, -27. This plan must not create a second thing to hand-maintain. Mitigations:

1. **The automated band-maintenance path writes the block, not a human.** The same `eligible proposal applied` mechanism that already rewrites the prose levels should write the structured fields in the same pass. Maintenance stays single-touch.
2. **Hash the owner-source artifact, not the recomputed level.** `source_sha256` covers the upstream artifact (e.g. `tmp/technical-refresh.json`) at review time, so a band recompute from the same source does not force a manual re-hash dance.
3. **Drift validator is the safety net, not a chore.** It runs in the existing finance-chain validation step; it only speaks up on real block-vs-prose disagreement.
4. **Stop at 42.** Do not extend anchors to the WF78 100/500 candidate names — those are non-decision-grade monitors (companion audit). Anchors are for the decision universe only.

If these four hold, the marginal maintenance cost is near zero because it rides the path that already edits these levels.

---

## 8. How This Reconciles With The Prior Audit (lane A vs lane B)

The companion audit recommended **demoting WF72 SQL to routing/index-only (lane B)** and *not* pursuing full SQL-first canon (lane A) yet. This plan is consistent with that, not a reversal:

- It does **not** make SQL the source of truth. Canon stays in the note. SQL stays an index — but now an index with real provenance, so it stops reporting "0 effective rows" for a reason that was never about code.
- The justification is **router reliability today**, not SQL-first ambition. The provenance fields are a *byproduct* that happens to unblock lane A later, cheaply, if demand ever pulls for it.
- It directly enables the audit's #1 highest-leverage move ("a working price/band freshness path for WF77") by giving the freshness pipeline a structured, addressable target to write into.

In short: **this is lane B's discipline plus the one structural improvement that makes a future lane A nearly free — without committing to lane A now.**

---

## 9. Decision Asks for Randall

1. **Format:** Approve the ```` ```canon ```` fenced block with `key: value` lines as the canonical anchor format? (Recommended — renders clean in Obsidian, parses trivially, visually separates machine layer from prose.)
2. **Phase 0/1 scope:** Approve hand-authoring the ETN pilot block, then (on your sign-off) populating all 42 Execution Board anchors by copying existing prose values 1:1 (no re-analysis)?
3. **Maintenance wiring:** Approve having the existing automated band-maintenance path own the structured fields (Section 7) so we never double-maintain?
4. **Sequencing:** Confirm the demand order — Execution Board anchors first (highest leverage), Coverage second, extractor/validator third, router consumption + schema freeze last?

No phase touches portfolio/sizing/cash/risk/execution state, and every phase is additive and reversible. Nothing here is applied until you approve the format and Phase 0.

---

## 10. Boundaries Preserved

- No portfolio, canon, sizing, cash, or risk-rule mutation — this is a design proposal only.
- The anchor block keeps canon **inside** the human note; it creates no second source of truth and no sidecar that could drift.
- Truth hierarchy unchanged: human-approved canonical Markdown remains #1; SQL/agents read from it and must downgrade on drift, never silently prefer a cache.
- No trade/account/brokerage/money-movement action; no paper/live execution; no owner-approval inference.
- No config/auth/channel/service/runtime change; no SQL writes performed (Phase 3 extractor is proposed, not run).
- `authority: reference_only` is the only legal value of that field by design — the review-only boundary is encoded structurally.
- This document is a review/proof artifact only; it is not canon, approval, apply authority, or execution authority.
