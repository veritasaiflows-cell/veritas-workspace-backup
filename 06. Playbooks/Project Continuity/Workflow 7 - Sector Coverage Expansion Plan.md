# Workflow 7 - Sector Coverage Expansion Plan

## Objective
- Define a controlled sector-expansion method for the tracked universe without reopening random ticker sprawl.
- Keep this pass at the operating-framework level: sector admission logic, lane defaults, and a small conditional draft wave only.

## Current State
- Workflow 7 opened immediately after Workflow 6 closed with follow-up on 2026-05-02.
- Workflow 7 is now **closed with follow-up** after the bounded Option C implementation pass (single Healthcare watch-lane pilot add).
- The machine-tracked universe is now **22 names** split across **10 execution / 8 watch / 2 macro / 2 speculative** after the bounded Healthcare pilot add.
- Trust is still warning-grade / `usable_with_caution`, so any further sector expansion must stay human-gated and capacity-aware.
- Current tracked-sector posture is concentrated in the existing conviction sleeves rather than broad market coverage.

## Last Meaningful Progress
- Completed the first sector inventory from `tmp/portfolio-config.json`, `04. Research/Coverage Universe.md`, and the Workflow 6 continuity note.
- Completed pass 2 recommendation design on 2026-05-02: selected the preferred Wave 1 sleeve pair, ranked primary/backup proxies, and made a bounded go/no-go call without changing machine config.
- Confirmed the current tracked universe is concentrated as follows:

| Sector bucket | Current tracked names | Lane split snapshot | Draft read |
|---|---|---|---|
| Tech / AI / platform | `GOOG`, `MSFT`, `NVDA`, `AMZN`, `AMD`, `PLTR`, `SMCI` | 3 execution / 3 watch / 1 speculative | Heaviest existing sleeve; no need to widen first |
| Energy | `XOM`, `CVX`, `LNG` | 1 execution / 2 watch | Adequate first-layer coverage |
| Defense | `LMT`, `RTX`, `KTOS` | 1 execution / 1 watch / 1 speculative | Adequate first-layer coverage |
| Financials | `JPM`, `BRK.B`, `GS` | 3 execution | Strongly covered already |
| Industrials / power infrastructure | `ETN`, `VRT`, `CAT` | 2 execution / 1 watch | Adequate first-layer coverage |
| Macro sleeves | `SLV`, `TLT` | 2 macro | Intentional non-equity hedge coverage |

- Confirmed the largest true gaps are **Healthcare**, **Utilities / regulated power**, **Consumer Staples / defensive quality**, and **Materials / commodity supply-chain exposure**.
- Confirmed there is no reason to add a broad batch now while the warning stack and maintenance load remain active.

## Framework - sector expansion admission rules

### Sector eligibility criteria
- Add a new sector only when it improves real sleeve balance, macro resilience, or decision quality versus the current universe.
- The sector must fill a genuine coverage gap, not just offer another interesting chart.
- The sector must have at least one clear liquid leader or proxy that can represent it without immediate multi-name branching.
- The sector must be maintainable inside the current warning-grade operating stack without degrading existing execution upkeep.
- If the sector does not plausibly compete for capital, hedge a real regime risk, or improve read-through quality, do not admit it yet.

### Leader / proxy selection rules
- Start with **one primary sector proxy** only.
- Allow **one backup candidate** at most if the first proxy has a known structural flaw or if a second name is needed later for replacement, not simultaneous sprawl.
- Prefer liquid, institutionally followed names with clean sector identity, durable ownership logic, and readable technical structure.
- Prefer the simplest honest representation: leader first, narrower satellite only after the leader proves useful.
- Avoid near-duplicate adds where an existing tracked name already gives enough read-through.

### Default lane for new adds
- **Default = watch lane** for any new sector-equity add.
- **Macro lane** only if the instrument is explicitly a hedge or regime-expression tool.
- **Speculative lane** only with an explicit asymmetric-sleeve reason; never use sector expansion as a pretext for speculative accumulation.
- **Execution lane** is not the default admission lane; a new name earns execution only after a later promotion review proves recurring capital relevance.

### Capacity gate
- **Max 2 net-new names per expansion wave** under the current warning-grade posture.
- Prefer **1 new sector proxy per wave** unless a paired defensive + cyclical gap fill is clearly justified.
- Do not open a new wave until the prior wave has lived through at least one real catalyst/review cycle and the maintenance burden still feels honest.
- Prefer replacement or consolidation before adding a third name to any newly opened sector sleeve.

### Promotion / demotion / replacement rules
- **Watch -> execution:** requires thesis ownership, explicit entry/stop policy, evidence the name now competes for live capital, and a human decision that weekday upkeep is worth the cost.
- **Execution -> watch:** use when the name becomes secondary, underdefined, duplicate, or no longer changes 30-90 day capital decisions.
- **Replacement within a sector:** allowed when the original proxy no longer represents the sleeve cleanly, carries avoidable single-name distortion, or proves too redundant versus existing holdings.
- **Removal:** use if a new sector proxy never earns practical value after a full review cycle or if the sector gap can be covered more honestly by an existing tracked name.
- Expansion should usually be **replace-before-add**, not accumulate-forever.

## First candidate expansion wave - draft only

**Status:** draft only; no automatic additions.

### Wave 1 candidate set
1. **Healthcare defensive-growth proxy** - add **1 watch-lane leader** only
   - Why this sector: current universe has no direct healthcare coverage despite its importance as a large defensive-growth sleeve and regime balancer.
   - Draft selection rule: prefer the cleanest large-cap healthcare leader with durable earnings quality and high liquidity.
   - Draft lane: **watch**.

2. **Utilities / regulated power proxy** - add **1 watch-lane leader** only
   - Why this sector: current universe has power-demand exposure through `ETN` and `VRT`, but no direct regulated-utility or defensive yield/power-grid sleeve exposure.
   - Draft selection rule: prefer a liquid utility/power-infrastructure proxy that adds a genuinely different macro behavior set from industrial power names.
   - Draft lane: **watch**.

### Why this wave is bounded
- It targets the two clearest missing sleeves without widening into consumer, materials, REITs, or extra tech subthemes all at once.
- Both candidates would begin in **watch**, not execution, which preserves the current 10-name execution discipline.
- It keeps the universe increase to **at most +2 names**, which is the smallest meaningful test of the framework.
- It stays compatible with the current warning-grade trust posture and does not force machine-config expansion until a human explicitly approves it.

## Pass 2 recommendation

### Chosen Wave 1 sleeve pair
1. **Healthcare**
2. **Utilities / regulated power**

### Why this pair wins
- **Healthcare** is the cleanest true gap in the current 21-name universe: no direct exposure today, while the existing book is heavily tilted toward tech, cyclicals, energy, defense, and financials.
- **Utilities / regulated power** adds a more genuinely different behavior set than Staples right now. `ETN` and `VRT` cover power-demand capex, but they do **not** provide the rate-sensitive, defensive, regulated-yield sleeve that a true utility proxy would add.
- **Consumer Staples** remains the next sleeve in line, but it is less urgent than Utilities because the current universe already has some broad quality ballast through `BRK.B`, while regulated utilities would add a cleaner macro diversifier.
- **Materials** stays behind all three because it is more cyclical, less immediately defensive, and not the best first answer to the current concentration profile.

### Ranked proxy shortlist

#### Healthcare
- **Primary:** `LLY` — most liquid, institutionally followed large-cap healthcare leader; strongest sector read-through and clear relevance if healthcare is going to matter for capital decisions.
- **Backup:** `JNJ` — cleaner defensive/diversified healthcare proxy if Randall wants lower single-theme concentration and a steadier first monitor.

#### Utilities / regulated power
- **Primary:** `SO` — clean regulated-utility identity, defensive yield behavior, and better differentiation from existing industrial/power-infrastructure names.
- **Backup:** `NEE` — very liquid utility leader with broader power/renewables relevance, but less pure as a regulated-power proxy than `SO`.

### Add-vs-replace posture
- **Recommended:** **Option C — +1 only now**.
- If Randall approves opening Wave 1 under warning-grade trust, add **Healthcare first** as a **watch-lane** monitor only.
- Keep the Utilities proxy as the preselected second sleeve, but hold it for the first post-add review cycle rather than jumping from 21 to 23 immediately.
- **Do not force one-for-one replacement yet.** Current names still map to real sleeves, and replacing before a new proxy proves useful would create false precision.

### Go / no-go recommendation
- **No-go for opening the full two-name Wave 1 now.**
- **Conditional go** only for a **single Healthcare watch-lane add** after explicit Randall approval.
- Reason: trust is still warning-grade, maintenance capacity is still constrained, and unresolved ownership residue (`CAT`, `CVX`, `SMCI`) argues for a smaller test instead of a full two-name expansion.

### Randall approval still required
- Whether to approve any new name at all in Workflow 7 under the current warning-grade posture.
- If approving one name, whether the preferred Healthcare proxy should be **`LLY`** or the more defensive backup **`JNJ`**. **Resolved 2026-05-02:** choose `LLY` for the first watch-lane pilot; keep `JNJ` as the replacement/tie-break backup, not a simultaneous add.
- Whether Utilities should remain the queued second sleeve for the next review cycle or be swapped later for Staples if macro posture changes.

## Outstanding
- Let `LLY` live through at least one real healthcare catalyst / earnings review cycle before opening the queued Utilities sleeve (`SO` / `NEE`).
- Decide later whether Utilities still beats Staples once the first new proxy has proved useful.
- If `LLY` fails the maintenance-value test or the valuation/catalyst profile becomes too distorted, revisit `JNJ` as the steadier replacement rather than adding both.

## Blockers / Trust Gaps
- Warning-grade trust residue is still active; further sector expansion must remain explicitly human-approved.
- Existing warning stack still consumes operator bandwidth, so expansion capacity is real, not theoretical.
- `CAT`, `CVX`, `LLY`, and `SMCI` thesis-writeup residue remains unresolved at the full-thesis level; sector expansion should not be used to outrun existing ownership debt.
- This workflow is no longer design-only, but the implementation remains intentionally narrow: one Healthcare watch-lane add only, no execution promotion and no automatic Utilities follow-on.

## Next Action
- Monitor whether `LLY` actually improves healthcare sleeve read-through without adding maintenance drag, then revisit the queued Utilities sleeve only after that review cycle.
- Handoff target after this closure: **Workflow 8 - Command Center chain readiness review**.

## Key Files
- `06. Playbooks/Project Continuity/Workflow 6 - Coverage Tier Framework.md` - upstream lane contract and current 21-name split.
- `04. Research/Coverage Universe.md` - thesis ownership boundary and current written coverage posture.
- `tmp/portfolio-config.json` - machine-tracked sector and lane inventory.
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md` - workflow queue state.
- `06. Playbooks/IC Project Registry.md` - control-board state for the active workflow.

## Automation / Refresh Path
- Keep Workflow 7 as a human-gated framework and candidate-screening workflow.
- Do not add sector candidates to machine config, scheduled chains, or canonical deployment surfaces until a later explicit approval pass lands.
- If Wave 1 is approved later, add the names first as watch-lane entries and review maintenance burden before any further sector wave opens.
