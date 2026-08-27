# Disciplined Entry Band Engine Spec

**Status:** PROPOSAL — review-only, owner decision required. Not applied. No capital/trade/canon authority.
**Owner:** Veritas main session
**Requested by:** Randall — 2026-08-17
**Lane:** `DISCIPLINED-BAND-ENGINE-SPEC-20260817` (concurrent lane register)
**Authority class:** `review_only_no_deployment_authority`

---

## 1. Problem this fixes

The written entry band is the **disciplined buy zone** — where Randall is willing to commit capital. Today it is maintained two ways, both broken:

1. **Manually** — AMD's written band (295.33–342.53) was last set **2026-05-06** and never revisited. It went **103 days stale** while price ran +50%. Manual maintenance does not scale and silently rots.
2. **Auto via `band_refresh.py`** — proposals anchor to **current MA structure** (Keltner + 20/50-day MA). By construction this **rises with price**. It is a trend-follower, not a discipline engine. As AMD rallied, its proposed/reclaim band ratcheted to 471–503, ~0.5% from price. The name then reads `NEAR_BAND`/`IN_BAND` and churns in the recommendation review every cycle even though it is +50% above its disciplined zone.

**Compounding data bug:** the SQL canon `reference_levels` row for AMD now holds the **reclaim band** (471.05–503.55, sourced from `band-proposals.json` via `reference_levels_band_proposals_source_migration.py`), not the written band. So the "canonical" reference layer is showing the chasing band as if it were the disciplined one.

**Randall's directive (2026-08-17):**
- Don't maintain written bands manually.
- Keltner+MA "proves it's not working" as a written-band engine.
- Prefer the system be an **alert system for human review** over serving stale information.
- Canon should be **SQL-refreshed daily but stay disciplined** (must not chase price).

## 2. Core principle — daily-fresh FACTS, event-driven LEVELS

The tension ("auto-refreshed daily" vs "disciplined / doesn't chase") resolves by separating what refreshes daily from what is allowed to move:

- **Refresh STATUS daily** — price, distance-to-band, band_status, staleness age, extension flag. Cheap, automated, never stale.
- **Change LEVELS only on a confirmed structural event** — a new higher-timeframe swing pivot, a break-and-hold, an earnings/thesis reset, or explicit owner approval. Never on daily MA drift.

Canon is SQL-refreshed every day (facts), but the disciplined band levels only move when something structurally real happens. This is the mechanism that keeps it fresh **and** disciplined.

## 3. Two-band model (both auto-maintained, honestly labeled)

Stop conflating the two bands the system already produces:

| Band | Engine | Refresh cadence | Purpose | Authority |
|---|---|---|---|---|
| **Tracking band** | Keltner+MA (existing `band_refresh.py`) | levels daily | proximity/alerting only — "how far from the current trend" | reference/alert only |
| **Disciplined band** | new structure-anchored engine (§4) | levels event-driven; status daily | the actual buy zone the no-chase gate uses | canonical written band |

The no-chase gate and capital-review overlay must bind to the **disciplined band**. The tracking band may inform "getting close" alerts but must never be treated as the buy zone. `reference_levels` must store both, clearly separated by `authority_class`.

## 4. Recommended disciplined-band engine

A **structure-anchored band with a slow ratchet cap.** Anchor priority:

1. **Structural support** — most recent higher-timeframe (weekly) swing low / prior consolidation shelf → band low.
2. **Fibonacci retracement** of the current up-leg (38.2–61.8%) → disciplined pullback zone. Re-anchors only when a *new* confirmed swing high/low forms, not daily.
3. **200-day SMA** → slow floor / sanity anchor.
4. **Optional valuation overlay** where fundamentals exist (forward P/E or EV/EBITDA implied price) → most disciplined anchor; needs a clean estimate feed, carries model risk. Layer later, not in v1.

**Band construction (v1):** band = the retracement zone bounded by structural support and the 200-day SMA. **Stop** = below the swing low / 200-day, ATR-buffered (reuse `band_refresh.py` ATR-14 logic).

**Why this stays disciplined:** the anchors are slow (weekly pivots, 200-day) and event-gated (Fib re-anchors on new pivots). A fast rally moves the *tracking* band but not the disciplined one, until a genuine structural change confirms.

## 5. Discipline guardrails (the part that stops chasing)

- **Event-gated levels** — disciplined band mutates only on a confirmed structural event or explicit owner approval. Never on daily drift.
- **Ratchet cap** — disciplined band may not rise faster than the 200-day SMA rose over the same window. Directly kills the "band chased a 50% rally" failure.
- **Extension auto-drop** — if price is > 1.5 ATR (or > 8%) above the disciplined band, the name is flagged `EXTENDED — no disciplined entry` and **drops off the deployable/recommendation slate automatically**, staying on a watch list. This is the direct AMD-churn fix.
- **Staleness alert** — any disciplined band older than ~30 days, or where price has run > X ATR from it, auto-fires a "review this band" alert to Randall. Nothing can silently go 103 days stale again. This is the "alert system for human review" Randall asked for, built in. (`band_refresh.py` already has a `needs_review` flag at >7 trading days / >5% from midpoint — extend/reuse it for the disciplined lane.)
- **Append-only audit** — every level change logs its triggering event and prior value; owner can veto.

## 6. How canon/SQL stays daily-fresh AND disciplined

Extend `reference_levels` (or add a companion table) to store both bands, with a hard separation of what refreshes when:

| Column group | Refresh | Notes |
|---|---|---|
| `tracking_band_low/high/stop` | daily | Keltner/MA; proximity/alert authority only |
| `disciplined_band_low/high/stop` | **levels: event-driven; never daily** | the written buy zone |
| `band_status`, `distance_to_band_pct`, `staleness_age_days`, `extended_flag` | daily | facts |
| `levels_set_at`, `level_change_trigger`, `prior_levels` | on event | audit trail |
| `authority_class` per band | static | tracking = alert-only; disciplined = canonical |

Daily refresh writes only the fact columns and the tracking band. It must be **structurally incapable** of moving the disciplined levels without a logged trigger event. This is enforced in the daily hygiene controller, not left to convention.

## 7. Reuse vs build (don't duplicate existing infra)

**Reuse:**
- `band_hygiene_freshness_controller.py` — already the daily read-only refresh spine with the correct authority boundary (all capital/trade/account flags false). Extend it to refresh the disciplined-band fact columns.
- `band_refresh.py` — ATR-14, drift, and `needs_review` staleness logic. Keep it as the **tracking-band** proposer; stop treating its output as the written band.
- `auto_apply_entry_band_maintenance.py` — the existing bounded `entry_band` apply gate. Disciplined-band level changes route through this gate (posture-preserving only), never a new ungated path.
- `reference_levels_band_proposals_source_migration.py` — audit/fix the migration that put the reclaim band into canon.

**Build (new):**
- Structure/Fib/200-day disciplined-band engine (§4).
- Ratchet cap + extension auto-drop rules (§5).
- Two-band `reference_levels` schema extension (§6).
- Extension filter in `portfolio_mutation_proposal_generator.py` / `daily_review_objects.py` so `EXTENDED` names leave the deployable slate.

## 8. Rollout phases (proposed, owner-gated)

1. **P1 — schema + labeling fix (lowest risk, biggest clarity win):** add disciplined vs tracking columns to `reference_levels`; correct the AMD-style mislabel so canon stops showing the reclaim band as the buy zone. Back-fill disciplined bands from the last owner-set values.
2. **P2 — extension auto-drop + staleness alert:** stop extended names churning the slate; wire the daily "band needs review" alert to Telegram (review-only, mirrors the capital-slate notifier pattern already live).
3. **P3 — disciplined engine v1:** structure + Fib + 200-day anchor with ratchet cap, proposing (not applying) disciplined bands through the existing `entry_band` gate.
4. **P4 (optional, later):** valuation overlay where fundamentals data supports it.

Each phase is a separate proposal with validator proof, backup/rollback, and owner approval before apply. No phase mutates canon or portfolio state without the gated-apply path.

## 9. Authority boundary (unchanged)

- Review-only. No capital deployment, no trade/paper/account/brokerage action, no money movement, no approval inference.
- Disciplined-band level changes are **portfolio/canon maintenance** → require the exact gated-apply path (scoped proposal, diff hash, standing-approval artifact, validator proof, backup/rollback, post-apply validation, audit trail). They do not run from cron or heartbeat.
- Cron/hygiene controller may refresh **facts and the tracking band** daily and **alert**; it may not move disciplined levels or infer approval.

## 10. Open owner decisions (need Randall)

1. **Extension threshold** for auto-drop: 1.5 ATR, or a fixed 8%? (Affects how aggressively names leave the slate.)
2. **Staleness alert age**: 30 days, or tie it to ATR-distance only?
3. **Ratchet policy**: hard-cap disciplined band rise to 200-day rise, or allow a manual owner override to raise a band when thesis justifies (e.g., a real regime change)?
4. **Build order**: confirm P1 (schema/labeling fix) first, or fold P1+P2 together?
5. **Valuation overlay (P4)**: in scope eventually, or keep the engine purely technical/structural?

---

### Hand-off / continuity

- **Deliverable:** this spec (review-only). No code written, no canon mutated.
- **Next action on approval:** stand up P1 as a scoped implementation proposal (schema extension + labeling fix) routed through `project_implementation_router.py`, with the `entry_band` gate for any level change.
- **Blocked on:** Randall's answers to §10 (thresholds + build order) before any implementation lane opens.
- **Lane:** `DISCIPLINED-BAND-ENGINE-SPEC-20260817`, closed with this file as proof.
