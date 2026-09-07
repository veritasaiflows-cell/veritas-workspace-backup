# Audit Remediation Portfolio Decision Packets

- Generated: 2026-05-17 20:48 MST subagent lane
- Status: owner-decision packets / review-only
- Canonical apply: none
- Trade/account action: none
- Source basis: `03. Portfolio/Portfolio Snapshot.md`, `03. Portfolio/Execution Board.md`, `07. Risk/Risk Rules.md`, `tmp/portfolio-mutation-proposals/portfolio-model-40-60-proposal.md`, `tmp/portfolio-mutation-proposals/portfolio-model-40-60-proposal.json`, `tmp/capital-deployment-recommendation-validation.json`, and inspected current capital-deployment recommendation bundle.

## Authority boundary

These packets are decision support only. They do not authorize canonical note/model mutation, cash movement, live/paper orders, brokerage/account action, or inferred owner approval. Any portfolio-model apply still requires an exact WF64/WF56-style gated apply path: scoped proposal, exact preview/diff, approval artifact, validators, backups/rollback, post-apply proof, and audit trail.

## Shared constraints that matter

- Risk Rules cap a single sector at **25%** and normal single-name size at **15%**.
- Current draft direct Technology weight is already **25%**: MSFT 10% + GOOG 10% + NVDA 5%.
- Broader AI-power/capex correlation is higher once ETN is included, so a formal sector-cap exception would understate the real crowding risk.
- The 40% ETF / 60% stock proposal is review-only, but it helps by converting the draft model into **36% ETFs / 54% stocks / 10% cash** if the existing 10% cash target is preserved.
- Current capital-deployment recommendation validation is structurally clean (`critical=0`, `warning=0`), but the underlying packets are still review-only with `apply_allowed=false`, `owner_approval_granted=false`, and `trade_or_account_action_allowed=false`.

---

# Decision Packet 1 — MSFT Technology-cap sequencing

## Decision needed

Randall needs to choose how MSFT should be sequenced before any real sizing action, because MSFT is owner-promoted as a staged manual candidate but direct Technology is already at the written 25% draft-model cap.

## Current evidence

- Portfolio Snapshot: MSFT is listed at **10% draft weight** as Core Technology quality and owner-promoted deployable-now / staged manual candidate.
- Execution Board: MSFT working band is **389.64–412.56**, stop **378.18**, owner-approved on **2026-05-12**, but still **below the 200-day** in the 2026-05-14 board context.
- Execution Board caveat: MSFT is a **starter-tranche / staged manual** setup, not a full-confidence trend-reclaim setup.
- Snapshot concentration rule: direct Tech is already **at cap**, so MSFT deployment requires one of: reduce another Tech weight first, keep any tranche within verified headroom, or approve a written Tech-cap exception.
- Current recommendation bundle conflict/freshness caveat: the 2026-05-17 generated MSFT packet reports `recommendation_posture=wait_for_band`, `source_freshness=stale/review_required`, and close **421.92** outside the 389.64–412.56 band context, while the canonical board still shows 409.43 / 2026-05-14 in-band. Treat this as a **freshness/price-state conflict requiring main-session confirmation before action**.

## Options

| Option | What it means | Pros | Risks / blockers |
|---|---|---|---|
| A — Reduce Tech first, then allow only a starter MSFT lane | Lower direct Tech model weight before any MSFT sizing; keep MSFT staged/manual and do not full-size while below 200D / freshness conflict is unresolved. | Honors 25% cap; keeps owner-approved MSFT thesis alive; avoids cap exception. | Requires choosing which Tech weight absorbs the reduction, likely NVDA or GOOG; still needs fresh price/band confirmation. |
| B — Defer MSFT until fresh band/reclaim confirmation | No MSFT deployment decision until the board and generated packet agree on price/band state, and either pullback into band or 200D reclaim improves setup quality. | Cleanest evidence discipline; avoids chasing after possible move above band. | May miss an early staged entry; leaves owner-approved MSFT promotion unused for now. |
| C — Written Tech-cap exception | Permit direct Tech above 25% because MSFT is high-quality. | Fastest path if Randall wants to prioritize mega-cap quality. | Not recommended: violates written cap and ignores AI/large-cap platform crowding. Quality is not a risk-rule exception by itself. |
| D — Use 40/60 model to reset the sizing answer | Adopt the 40/60 proposal as the next model-design direction: MSFT becomes **8% of risk assets / 7.2% account-level** if 10% cash is retained, not the old 10% account-level draft. | Solves cap pressure structurally; lowers direct-stock dependency; keeps MSFT meaningful but less crowded. | Still review-only; requires ETF look-through and gated apply before canonical mutation. |

## Recommendation

Recommend **Option D as the model-design answer plus Option B as the immediate action discipline**:

1. Treat MSFT’s old 10% draft weight as superseded for planning by the proposed 40/60 framework, where MSFT is **8% of risk assets / 7.2% account-level** if 10% cash is preserved.
2. Do **not** approve a Tech-cap exception.
3. Do **not** treat MSFT as actionable until main session resolves the board-vs-packet freshness conflict and confirms whether price is back inside the written band or has a better reclaim setup.
4. If Randall wants an eventual starter tranche, fund it only after direct Tech pro-forma exposure stays at or below 25% after look-through checks, or after a separately written exception.

## Owner decision prompt

Choose one:

- **Approve planning direction only:** use 40/60 model planning weight for MSFT at 8% risk assets / 7.2% account-level; no action until fresh band confirmation.
- **Defer entirely:** leave MSFT unchanged and revisit after fresh technical refresh.
- **Approve written exception:** intentionally allow direct Tech above 25% after naming the cap breach and risk acceptance.

Default Veritas recommendation: **approve planning direction only; no exception; no action until fresh confirmation.**

---

# Decision Packet 2 — LMT / Defense exposure gap

## Decision needed

Randall needs to decide how to handle the Defense sleeve while LMT is below-stop repair and its 10% draft weight is suspended.

## Current evidence

- Portfolio Snapshot: LMT has a **10% draft weight** but the status says repair mode; stance suspended; cannot be treated as deployable until owner resolves the defense gap.
- Execution Board: LMT close **520.41 / 2026-05-14**, preferred band **548.51–582.27**, explicit stop **531.63**, below all MAs, below stop, and **do not touch / below-stop repair**.
- Execution Board: LMT’s setup failed; no re-entry case until stop reclaim, support rebuild, and fresh review.
- Snapshot sector allocation: Defense shows **LMT 10% + KTOS 2% = 12%**, but the actual deployable defense answer is not 12% because LMT is suspended and KTOS is speculative/watch context.
- 40/60 proposal: sets LMT to **0%**, keeps KTOS only as **1% risk-asset / 0.9% account-level optional placeholder**, and proposes a **Defense/aerospace ETF role at 7% risk assets / 6.3% account-level** pending validation.
- ETF candidate noted: ITA or equivalent defense/aerospace ETF, but holdings concentration, LMT/RTX overlap, and technical promotion review are still blockers.

## Options

| Option | What it means | Pros | Risks / blockers |
|---|---|---|---|
| A — Keep LMT 10% placeholder suspended | Leave the draft model as-is but mark the weight non-deployable until LMT heals. | Minimal change; preserves original defense intent. | Misleading model optics: a 10% suspended placeholder can be mistaken for active exposure; does not solve capital allocation. |
| B — Accept KTOS-only Defense exposure | Treat KTOS as the only Defense sleeve for now, likely 1–2% speculative/watch exposure. | Simple and conservative on capital at risk. | Defense exposure becomes tiny and speculative; KTOS is not a core defense substitute and is below reclaim structure. |
| C — Replace suspended LMT with validated Defense ETF sleeve | Set active LMT model weight to 0% pending repair, keep a small KTOS placeholder at most, and earmark Defense exposure through ITA/equivalent after ETF validation. | Best match to the 40/60 model; diversifies idiosyncratic LMT setup risk; solves the gap without forcing a broken chart. | Requires ETF holdings/overlap and technical validation; may still have LMT/RTX exposure via ETF look-through. |
| D — Promote RTX or another single-name Defense substitute now | Find another defense stock to fill LMT’s weight. | Could preserve single-name upside if a clean candidate exists. | Not supported by current board: RTX is watch repair; no validated replacement packet is present. |

## Recommendation

Recommend **Option C**:

1. Treat LMT’s active deployment/model role as **0% until repair clears**; keep any old 10% line explicitly suspended, not deployable.
2. Use the 40/60 proposal to earmark Defense through an ETF role: **7% of risk assets / 6.3% account-level** if the 10% cash target is retained.
3. Keep KTOS as only a speculative monitor, no more than the 40/60 proposal’s **1% risk-asset / 0.9% account-level** placeholder unless a separate speculative-sleeve exception is reviewed.
4. Block any LMT re-entry until it at least reclaims the **531.63 stop**, rebuilds support, and receives fresh review against the written band / MAs.

## Owner decision prompt

Choose one:

- **Approve planning direction only:** LMT active weight to 0% in the proposed 40/60 model, Defense ETF role earmarked for validation, KTOS max 1% risk-asset placeholder; no canonical apply yet.
- **Hold suspended placeholder:** keep LMT 10% as non-deployable draft placeholder until it heals.
- **Accept no core Defense exposure for now:** KTOS/speculative monitor only, no ETF earmark.

Default Veritas recommendation: **approve planning direction only: LMT 0%, Defense ETF validation queue, KTOS max 1% risk-asset placeholder.**

---

## How the 40/60 model resolves both issues

- It reduces the pressure to force single names into the model when their chart or evidence state is broken.
- It lowers MSFT from the old 10% account-level draft to **8% risk assets / 7.2% account-level**, making the Tech-cap problem easier to solve without a written exception.
- It replaces the suspended LMT problem with a review-only ETF sleeve candidate, so Defense exposure can be diversified instead of dependent on one broken setup.
- It preserves the existing **10% cash target** unless Randall separately approves a cash-policy change.
- It still cannot be applied until ETF look-through, sector/correlation, execution-state, source-freshness, patch-preview, approval, backup/rollback, and post-apply validators pass.

## Final stop line

No trade, account action, paper order, live order, cash movement, or canonical portfolio mutation is authorized by these packets. The only safe next step is main-session review and owner selection of the planning direction.