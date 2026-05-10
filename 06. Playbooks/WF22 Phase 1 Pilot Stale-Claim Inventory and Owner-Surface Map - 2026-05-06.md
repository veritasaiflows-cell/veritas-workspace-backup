# WF22 Phase 1 Pilot Stale-Claim Inventory and Owner-Surface Map - 2026-05-06

## Purpose
Bound the WF22 Phase 1 pilot to the named high-signal set and classify only mechanical/alignment freshness candidates or explicit rejections before any patch dry run.

## Scope used
Pilot targets required by Workflow 22:
- NVDA timing path
- JPM
- ETN
- GOOG / MSFT post-earnings freshness
- oil / Hormuz sleeve

Evidence and contract basis:
- `06. Playbooks/Research Automation Canonical Freshness Patch Contract.md`
- `06. Playbooks/Research Automation Freshness Candidate Input Contract.md`
- `06. Playbooks/Research Automation Intake Packet Contract.md`
- `06. Playbooks/Research Automation Routing and Promotion Contract.md`
- `06. Playbooks/WF26 External Intelligence Manual Verification Pilot and Cadence Verdict - 2026-05-06.md`
- `tmp/research-automation/intake-packets-20260506-021940.json`
- `tmp/research-automation/intake-packets-20260506-152048.json`

## Phase 1 pilot note list / owner surfaces
### Normal v1 owner surfaces
- `01. Dashboards/Executive Brief.md`
- `01. Dashboards/Next Actions.md`
- `01. Dashboards/This Week.md`
- `05. Intelligence/Event Calendar.md`
- `05. Intelligence/Weekly Intelligence Brief.md`

### Manual-only / caution surfaces that may be referenced but not mutated
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- `02. Markets/Macro Regime Dashboard.md`

## Candidate inventory

### 1) NVDA timing path
- **Phase 1 disposition:** explicit rejection for Phase 2 dry run now
- **Why:** both intake packets keep the item unresolved because provider-level timing exists but clean NVDA IR confirmation is still not captured. That fails the safe-use expectation for a mechanical patch and risks turning a timing placeholder into false canonical certainty.
- **Freshness class if revisited later:** `mechanical_date_elapsed_event`
- **Judgment impact now:** `possible`
- **Evidence quality now:** mixed (`tier_1_primary` placeholder plus `tier_2_trusted` timing signal), still unresolved
- **Owner-surface map:**
  - likely owner surfaces once primary confirmation exists:
    - `05. Intelligence/Event Calendar.md`
    - `01. Dashboards/This Week.md`
    - `01. Dashboards/Executive Brief.md`
  - downstream caution / reference surfaces only:
    - `03. Portfolio/Deployment Trigger Sheet.md`
    - `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- **Required downstream sync if ever approved later:** event-calendar date/status check first, then dashboard wording alignment; no trigger-sheet state change from this lane
- **Rejection reason:** unresolved primary timing capture keeps the candidate outside safe mechanical freshness help

### 2) JPM
- **Phase 1 disposition:** no freshness candidate; explicit rejection
- **Why:** the packet evidence describes stable macro support and a dashboard-watch context object, not a stale canonical claim. Any attempt to convert this into canon would arbitrate between supportive macro context and still-cautious deployment surfaces.
- **Freshness class if forced:** would behave like `cross_surface_contradiction`, not safe normal v1 freshness
- **Judgment impact now:** `possible`
- **Evidence quality now:** confirmed macro context, but not a stale-note fix target
- **Owner-surface map:**
  - review-owner surfaces only:
    - `01. Dashboards/Executive Brief.md`
    - `01. Dashboards/Next Actions.md`
    - `01. Dashboards/This Week.md`
    - `05. Intelligence/Weekly Intelligence Brief.md`
  - manual-only truth / caution surfaces referenced by the contradiction:
    - `02. Markets/Macro Regime Dashboard.md`
    - `03. Portfolio/Deployment Trigger Sheet.md`
    - `03. Portfolio/Portfolio Snapshot.md`
- **Required downstream sync if human review later identifies a real stale sentence:** reconcile dashboard wording against macro dashboard and trigger-sheet posture before any patch draft
- **Rejection reason:** not a mechanical/alignment stale-claim packet; owner-boundary ambiguity is too high

### 3) ETN post-earnings freshness
- **Phase 1 disposition:** conditional higher-review Phase 2 candidate only; do not treat as a normal fast-path patch target
- **Why:** the 2026-05-06 02:19 packet explicitly routes ETN to `canonical_freshness_patch_candidate`, but the same packet also says primary-source capture remained incomplete and flags potential thesis drift. That means ETN can justify a dry run only as a tightly bounded contradiction/alignment example, not as routine post-earnings freshness help.
- **Freshness class:** `cross_surface_contradiction` for the pilot dry run, not normal `post_catalyst_status`
- **Judgment impact now:** `possible`
- **Evidence quality now:** partial; `tier_1_primary` placeholder plus `tier_2_trusted` secondary cluster
- **Candidate stale-claim shape allowed in Phase 2:** future-tense or pre-print wording on a normal v1 owner surface after ETN has already reported, with replacement text limited to reported/interpreted status plus explicit primary-capture incompleteness
- **Owner-surface map:**
  - likely owner surfaces:
    - `01. Dashboards/Executive Brief.md`
    - `01. Dashboards/This Week.md`
    - `05. Intelligence/Weekly Intelligence Brief.md`
    - `05. Intelligence/Event Calendar.md`
  - downstream caution / reference surfaces only:
    - `03. Portfolio/Deployment Trigger Sheet.md`
    - `03. Portfolio/Portfolio Snapshot.md`
    - `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- **Required downstream sync for Phase 2 dry run:**
  - confirm the exact stale owner-surface sentence still exists
  - draft only event-status / wording cleanup
  - record that manual portfolio surfaces may need inspection but must not be auto-mutated
- **Phase 2 guardrail:** reject immediately if the proposed text drifts into beat / guidance interpretation, posture, ranking, or deployability
- **Why not normal-safe:** unresolved primary capture plus thesis-risk language means the best honest outcome may still be `needs_review` rather than a normal proposed candidate

### 4) GOOG / MSFT post-earnings freshness
- **Phase 1 disposition:** conditional candidate set; justify Phase 2 dry run only if a real stale owner-surface sentence is still present
- **Why:** Workflow 22 names GOOG / MSFT post-earnings freshness directly as pilot targets, and the canonical patch contract cites them as bounded post-earnings review examples. The current intake packets do not provide a dedicated GOOG or MSFT packet, so Phase 1 can only mark them as owner-surface scan candidates rather than verified patch packets.
- **Freshness class:** `post_catalyst_status`
- **Judgment impact now:** `none` if limited to post-print status wording; otherwise reject
- **Evidence quality now:** workflow-authorized target, but packet support is indirect in this pass
- **Owner-surface map:**
  - likely owner surfaces:
    - `01. Dashboards/Executive Brief.md`
    - `01. Dashboards/This Week.md`
    - `05. Intelligence/Weekly Intelligence Brief.md`
    - `05. Intelligence/Event Calendar.md`
  - downstream caution / reference surfaces only:
    - `03. Portfolio/Deployment Trigger Sheet.md`
    - `03. Portfolio/Portfolio Snapshot.md`
    - `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- **Required downstream sync for any later dry run:** verify exact stale wording in the owner note, confirm post-earnings fact pattern from approved evidence already in the workspace, then keep sync notes limited to dashboard/event-calendar alignment
- **Phase 1 caveat:** without a linked packet or exact stale sentence, these remain scan targets, not ready patch packets

### 5) Oil / Hormuz sleeve
- **Phase 1 disposition:** explicit rejection
- **Why:** both WF26 and the latest intake packet keep this as stop-line verification only with rumor / blocked-source evidence and no attributable chain. The candidate contract explicitly says geopolitical rumor cannot justify freshness patching.
- **Freshness class if forced:** would drift into `thesis_or_posture_change`
- **Judgment impact now:** `material`
- **Evidence quality now:** `rumor_unverified`
- **Owner-surface map:**
  - possible review surfaces only if verified later:
    - `05. Intelligence/Weekly Intelligence Brief.md`
    - `01. Dashboards/Executive Brief.md`
  - manual-only truth / caution surfaces most exposed:
    - `02. Markets/Macro Regime Dashboard.md`
    - `03. Portfolio/Portfolio Snapshot.md`
    - `03. Portfolio/Deployment Trigger Sheet.md`
- **Required downstream sync if evidence quality later improves:** human macro review before any dashboard or weekly wording consideration
- **Rejection reason:** rumor-tier freshness theater and posture risk are explicitly out of bounds

## Phase 1 summary verdict
### Candidates justified for Phase 2 dry run now
1. **ETN post-earnings freshness** - maybe, but only as a higher-review contradiction/alignment dry run after confirming the exact stale owner-surface sentence still exists.
2. **GOOG / MSFT post-earnings freshness** - maybe, but only after an owner-surface scan finds exact stale post-earnings wording and approved evidence already exists in workspace notes.

### Not justified for Phase 2 dry run now
- **NVDA timing path** - unresolved primary timing capture
- **JPM** - macro/dashboard context is not a clean freshness patch target
- **Oil / Hormuz sleeve** - rumor-tier / posture-risk stop line

## Recommendation
**Phase 2 dry run is justified now only as a very narrow higher-review pass on ETN stale pre-print wording, plus GOOG / MSFT only if exact stale owner-surface wording is confirmed before drafting.**
Do **not** carry NVDA, JPM, or oil / Hormuz into the dry run until their stop-line conditions clear or a clearly mechanical stale sentence is identified on an approved owner surface.
