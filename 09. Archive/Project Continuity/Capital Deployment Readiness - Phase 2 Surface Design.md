# Capital Deployment Readiness — Phase 2 Morning Surface Design

**Project:** Capital Deployment Readiness
**Phase:** 2 — Morning decision surface design
**Author:** Claude (IC)
**Date:** 2026-05-01
**Status:** Complete — awaiting operator review

---

## 1. What this document is

The architecture specification for the minimum effective morning deployment decision surface. It defines:

- The seven surface states and their precise meanings
- The adjudication rules that convert raw machine fields into surface states
- The required fields for each name in the morning view
- How machine `action_state` is overridden when `workflow_state` or trust-state disagrees
- The current morning surface applied against today's stack (concrete example)
- Downgrade behavior under degraded trust
- What Phase 3 must implement to make this surface reliable

This is an architecture document. No scripts, notes, or surfaces have been changed.

---

## 2. Surface state taxonomy

Seven states. One system-level halt. These are what the morning surface displays — not raw machine fields.

| Surface state | Meaning | Operator action |
|---|---|---|
| **DEPLOYABLE NOW** | All five gates pass, system trust clean, workflow decision-grade, human reviewed | Confirm and act |
| **ALMOST DEPLOYABLE** | Constructive setup, one condition unmet (typically price not yet in band) | Wait for condition; monitor |
| **ALMOST / NEAR-EARNINGS CAUTION** | ALMOST state but earnings within 7 days — sizing capped at half tier | Explicit decision required to accept pre-print exposure |
| **POST-EARNINGS REVIEW** | Earnings print passed; prior setup is obsolete; new review required before re-evaluation | Run post-earnings review workflow before any re-classification |
| **BLOCKED** | Valid active earnings or event block (print has not yet occurred, ≤14 days out) | Do not act; re-evaluate after event |
| **DO NOT TOUCH** | Hard block: below stop, repair mode, or structure too broken for justified deployment | Off the board entirely |
| **WATCH / RESEARCH NEEDED** | Not decision-grade: no human-validated setup, missing levels, or thesis incomplete | Do not deploy; complete research first |
| **SYSTEM HOLD** | stop_line = true — full workflow halt | No deployment decisions of any kind until stop_line clears |

**One additional qualifier, not a standalone state:**  
**TRUST CEILING APPLIED** — machine said DEPLOYABLE NOW, but fallback_state.used=true or band_stale=true downgraded it to ALMOST DEPLOYABLE. Operator sees the raw machine call and the override reason. When trust clears, this name returns to DEPLOYABLE NOW automatically.

---

## 3. Adjudication rules

The adjudication rules are the contract between raw machine fields and surface state. They are applied in order. **First match wins; stop evaluating further rules once a state is assigned.**

These rules are to be applied per name, after the system trust header has been read.

```
INPUT FIELDS REQUIRED PER NAME:
  below_stop              boolean — from deployment-check.json
  workflow_state          string  — from trigger-sheet.json
  earnings_blocked        boolean — from trigger-sheet.json
  days_to_earnings_calendar  integer — from earnings-calendar.json (NOT vault date)
  post_earnings_review_confirmed  boolean — new field; see Section 6 for definition
  action_state            string  — from trigger-sheet.json
  fallback_state_used     boolean — from run-summary-post-close.json (system-level)
  band_stale              boolean — derived: name appears in dashboard-validation band_staleness scope

RULE 0 — System halt (check once per session, not per name)
  IF stop_line = true (from run-summary)
  THEN all names → SYSTEM HOLD
  STOP all further evaluation

RULE 1 — Hard structural block
  IF below_stop = true
  THEN surface_state = DO NOT TOUCH [BELOW STOP]
  RETURN

RULE 2 — Stale earnings block (post-print, block not cleared)
  IF earnings_blocked = true
  AND days_to_earnings_calendar > 14
  THEN surface_state = POST-EARNINGS REVIEW [stale block — vault date predates print]
  RETURN

RULE 3 — Post-earnings requalification required (T+0 or T+1 without confirmed review)
  IF days_to_earnings_calendar ≤ 0
  AND post_earnings_review_confirmed = false
  THEN surface_state = POST-EARNINGS REVIEW [print occurred; setup review required]
  RETURN

RULE 4 — Semantic gate: not decision-grade
  IF workflow_state = WATCH
  THEN surface_state = WATCH / RESEARCH NEEDED
  RETURN

RULE 5 — Repair mode (not below stop, but structure broken)
  IF workflow_state = REPAIR
  AND below_stop = false
  THEN surface_state = DO NOT TOUCH [REPAIR]
  RETURN

RULE 6 — Trust ceiling on DEPLOYABLE NOW
  IF action_state = DEPLOYABLE (machine)
  AND (fallback_state_used = true OR band_stale = true)
  THEN surface_state = ALMOST DEPLOYABLE [trust ceiling]
  ADD note: "machine rated DEPLOYABLE NOW — ceiling applies until trust clears"
  RETURN

RULE 7 — Valid active earnings block
  IF earnings_blocked = true
  AND days_to_earnings_calendar > 0
  AND days_to_earnings_calendar ≤ 14
  THEN surface_state = BLOCKED [earnings — N days]
  RETURN

RULE 8 — Near-earnings caution qualifier (applied after state, not instead of state)
  IF surface_state is ALMOST DEPLOYABLE (reached via any path)
  AND 1 ≤ days_to_earnings_calendar ≤ 7
  THEN ADD qualifier: NEAR-EARNINGS CAUTION
  (qualifier modifies the display label; does not change primary state)

RULE 9 — Standard pass-through (no override fired)
  action_state DEPLOYABLE  → DEPLOYABLE NOW
  action_state ALMOST      → ALMOST DEPLOYABLE
  action_state BLOCKED     → BLOCKED
  action_state BENCH       → DO NOT TOUCH [BENCH]
  action_state WATCH       → WATCH / RESEARCH NEEDED
  action_state BELOW STOP  → DO NOT TOUCH [BELOW STOP]
  action_state (blank)     → WATCH / RESEARCH NEEDED
```

### Rule precedence rationale

The order is deliberate and must not be changed without operator review:

- Rule 1 before Rule 2: below_stop is a hard structural fact that overrides any calendar question.
- Rule 2 before Rule 3: stale earnings block is detected before T+0 check; avoids double-firing on a name that is both past its print and has `days_to_earnings = 0`.
- Rule 3 before Rule 4: a name that just reported is POST-EARNINGS REVIEW even if it is also WATCH — the review state is more specific and actionable.
- Rule 4 before Rule 5: WATCH is more specific than REPAIR; a WATCH name should not get a DO NOT TOUCH [REPAIR] label when the correct message is "not decision-grade."
- Rule 5 before Rule 6: repair mode produces a harder message than a trust ceiling; a repaired name should not appear as ALMOST DEPLOYABLE.
- Rule 6 before Rule 7: trust ceilings apply to DEPLOYABLE NOW promotions; earnings blocks are independent.
- Rule 8 applied after state is set: it is a qualifier on an existing ALMOST state, not a state itself.

---

## 4. Required fields for the morning surface

### System trust header (required, shown before all names)

The header is produced from run-summary-post-close.json and dashboard-validation.json. It must appear at the top of every morning deployment surface. It cannot be omitted or hidden.

**Required header fields:**

```
SYSTEM TRUST STATUS
─────────────────────────────────────────────────────────────────
System halt (stop_line):         [ YES / NO ]
DEPLOYABLE NOW suspended:        [ YES / NO ]  (fallback_state.used)
Canonical note mutation:         [ ALLOWED / BLOCKED ]
Presentation authorized:         [ YES / NO ]

Active warnings:                 N total (X critical, Y warning)
Warning codes:                   [ list warning codes ]
Earnings blocks (stale):         [ list of tickers with stale blocks ]
Macro gate trust:                [ CLEAN / DEGRADED ]
Policy source:                   [ AUTO / MANUAL FALLBACK ]

Run-summary generated:           [ timestamp ]
Artifacts as of:                 [ latest artifact timestamp ]
Trust header generated from:     run-summary + dashboard-validation
─────────────────────────────────────────────────────────────────
```

If run-summary and latest artifacts have a timestamp gap > 2 hours, flag:  
`⚠ run-summary predates latest artifacts by Xh — trust state may not reflect most recent run`

### Per-name surface fields (minimum required)

Each name in the morning surface must show these fields in this order:

```
[SURFACE STATE]  TICKER
  workflow_state:        WATCH | ALMOST | BLOCKED | REPAIR
  close:                 NNN.NN
  vs. band:              X.X% above / below / IN BAND / no band
  days_to_earnings:      N days / TODAY / YESTERDAY / N days ago
  near-earnings caution: YES (if ≤7 days) / —
  band stale:            YES / NO
  earnings date confirmed: YES / UNCONFIRMED (vault ≠ calendar)
  macro gate:            CLEAN / DEGRADED
  override applied:      [ rule number + reason ] or NONE
  why:                   [human text from trigger-sheet why field, 1 line]
  trigger:               [technical_trigger text, 1 line]
```

**Not required on the surface (Phase 1 finding: these add noise):**
- Priority score numbers (misleading for WATCH-state names)
- Regime fit / technical posture / catalyst risk individual scores (summary is sufficient)
- Workbook CSV data

### Name ordering on the surface

Names must be grouped by surface state, not by priority rank. This directly addresses the FP-7 gap where GS ranked above JPM.

**Required group order:**
1. DEPLOYABLE NOW
2. ALMOST DEPLOYABLE (no qualifier)
3. ALMOST DEPLOYABLE / NEAR-EARNINGS CAUTION
4. POST-EARNINGS REVIEW (ordered by: most consequential first — defined below)
5. BLOCKED (valid active block)
6. DO NOT TOUCH
7. WATCH / RESEARCH NEEDED
8. SYSTEM HOLD (if active, replaces all other groups)

**Within POST-EARNINGS REVIEW, ordering rule:**  
Names where `in_entry_band = true` appear first (most consequential). Then names extended above band (least near-term priority).

---

## 5. Machine action_state override logic

This section defines precisely when and how the surface overrides what the machine reported.

### Override taxonomy

Three types of override, each with a visible indicator:

**Override Type A — Semantic downgrade**  
Machine said: DEPLOYABLE NOW or ALMOST DEPLOYABLE  
Surface says: WATCH / RESEARCH NEEDED  
Trigger: Rule 4 (workflow_state = WATCH)  
Display: `[WATCH — overrides machine: ALMOST DEPLOYABLE]`  
Meaning: The setup does not exist yet. Price hitting a band is not sufficient.

**Override Type B — Post-earnings downgrade**  
Machine said: BLOCKED (stale) or ALMOST DEPLOYABLE (T+1)  
Surface says: POST-EARNINGS REVIEW  
Trigger: Rule 2 or Rule 3  
Display: `[POST-EARNINGS REVIEW — overrides machine: BLOCKED (stale)]`  
Meaning: The pre-print framing is obsolete. A new review is required.

**Override Type C — Trust ceiling**  
Machine said: DEPLOYABLE NOW  
Surface says: ALMOST DEPLOYABLE [trust ceiling]  
Trigger: Rule 6 (fallback_state.used = true or band_stale = true)  
Display: `[ALMOST DEPLOYABLE — trust ceiling; machine: DEPLOYABLE NOW]`  
Meaning: Setup looks actionable but system trust is degraded; operator must manually confirm before acting.

### When no override fires

If none of Rules 1–7 fire, the surface state is Rule 9 pass-through. No override indicator is shown. The surface state matches the machine state.

### Override cascade prohibition

Only one override may apply to a name. Overrides are not stacked. The first rule to fire is the only rule that applies. If Rule 1 fires (below_stop), the name does not also get a POST-EARNINGS REVIEW label.

---

## 6. The `post_earnings_review_confirmed` field

This field does not exist in the current machine stack. It is a required addition for Phase 3. It is defined here so Phase 3 has a precise target.

**Definition:** `post_earnings_review_confirmed` is `true` for a given name on a given day if and only if:
- The name has had earnings within the prior 10 trading days (days_to_earnings_calendar between -10 and 0), AND
- The Deployment Trigger Sheet.md note layer has been updated after the earnings date with an explicit post-earnings action_state and supporting logic

**How it is set:** Not by a script. Set by the operator or by Claude on standing authority when the trigger-sheet note is updated post-earnings. The field is stored in portfolio-config.json per name as `post_earnings_review_date` (the date of the last post-earnings review). If `post_earnings_review_date > last_earnings_date`, the review is confirmed.

**Default:** false (no review confirmed) for any name where the field is absent or where `post_earnings_review_date ≤ last_earnings_date`.

**Current state for all names as of 2026-05-01:**

| Name | Last earnings | post_earnings_review_date | Review confirmed? |
|---|---|---|---|
| MSFT | 2026-04-29 | none | **NO** |
| GOOG | 2026-04-29 | none | **NO** |
| AMZN | 2026-04-29 | none | **NO** |
| CAT | 2026-04-30 | none | **NO** |
| XOM | 2026-05-01 | none | **NO** (earnings today) |
| LMT | 2026-04-23 | none | **NO** |
| ETN | 2026-05-05 | n/a (upcoming) | n/a |
| All others | >10 trading days ago | n/a | n/a |

---

## 7. Current morning surface (Phase 2 applied to 2026-05-01 data)

This is the concrete output of applying the adjudication rules to the current stack. This is what the morning surface would show if Phase 3 were implemented.

```
═══════════════════════════════════════════════════════════════════
VERITAS MORNING DEPLOYMENT SURFACE — 2026-05-01
Data as of: 2026-04-30 close | Run: 2026-05-01 06:47 UTC
═══════════════════════════════════════════════════════════════════

SYSTEM TRUST STATUS
──────────────────────────────────────────────────────────────────
System halt:              NO
DEPLOYABLE NOW suspended: YES  (fallback_state.used = true)
Canonical note mutation:  BLOCKED
Presentation authorized:  NO

Active warnings: 8 (0 critical, 8 warning)
  band_staleness            10 names: ETN GOOG AMZN VRT RTX CAT CVX PLTR KTOS SLV
  timing_sensitive_dates    BRK.B (May 2, unconfirmed) | NVDA (May 20, unconfirmed)
  earnings_block_stale      AMZN GOOG MSFT (vault dates pre-Apr-29; prints passed)
  macro_manual_dependency   Policy pillar: ZQ futures fallback (CME 404)
  policy_fallback_source    CME primary failed; fallback active

Macro gate: DEGRADED (policy manual) — regime direction likely correct; precision degraded
⚠ run-summary (03:58 UTC) predates latest artifacts (06:47 UTC) by 2h49m

──────────────────────────────────────────────────────────────────
DEPLOYABLE NOW                                               (0 names)
──────────────────────────────────────────────────────────────────
  None. DEPLOYABLE NOW is suspended system-wide (fallback_state.used = true).
  Under clean trust, GS would reach this surface state — but GS is blocked
  by Rule 4 (workflow_state = WATCH) independent of trust state.
  No name reaches DEPLOYABLE NOW today.

──────────────────────────────────────────────────────────────────
ALMOST DEPLOYABLE                                            (2 names)
──────────────────────────────────────────────────────────────────

  JPM  [ALMOST DEPLOYABLE]
    workflow_state:  ALMOST
    close:           313.23  |  vs. band: 2.4% above band top (band 300–306)
    days_to_earnings: 74 days  |  near-earnings caution: —
    band stale:      NO (within tolerance)
    earnings date:   2026-07-14 (confirmed yfinance; 74d)
    macro gate:      DEGRADED (qualifier; regime conclusion robust)
    override:        NONE
    why:             close 313.23 — posture constructive but not yet in band
    trigger:         Pullback into 300–306 while holding 200-day and higher-low structure
    ──
    OPERATOR NOTE: Cleanest active candidate. Sole name that survives full
    contract review without an override. 2.4% from band top. Only enter on
    genuine pullback; do not force.

  NVDA  [ALMOST DEPLOYABLE]
    workflow_state:  ALMOST
    close:           199.57  |  vs. band: 0.15% above band top (band 188.03–199.28)
    days_to_earnings: 19 days  |  near-earnings caution: —
    band stale:      NO (within tolerance)
    earnings date:   2026-05-20 UNCONFIRMED (vault: May 27; yfinance: May 20)
    macro gate:      DEGRADED (qualifier)
    override:        NONE
    why:             close 199.57 — posture constructive; 0.15% above band top
    trigger:         Pullback into 186–191 only; never chase above current levels
    ──
    OPERATOR NOTE: At the band edge; any small pullback puts it in band.
    Cannot promote to DEPLOYABLE NOW until earnings date confirmed from IR
    (vault vs. yfinance mismatch). 19 days is outside near-earnings caution
    window but the date uncertainty is a real qualifier.

──────────────────────────────────────────────────────────────────
ALMOST DEPLOYABLE / NEAR-EARNINGS CAUTION                    (1 name)
──────────────────────────────────────────────────────────────────

  ETN  [ALMOST DEPLOYABLE + NEAR-EARNINGS CAUTION]
    workflow_state:  ALMOST
    close:           433.01  |  vs. band: 3.0% above band top (band 395.59–420.31)
    days_to_earnings: 4 days  |  near-earnings caution: YES (earnings May 5)
    band stale:      YES (in band_staleness warning scope)
    earnings date:   2026-05-05 (yfinance; derived — not IR-confirmed)
    macro gate:      DEGRADED (qualifier)
    override:        RULE 8 (near-earnings caution qualifier added)
    why:             Best chart in the sheet; current price extended vs. preferred zone
    trigger:         Pullback into 388–396 with support holding
    ──
    OPERATOR NOTE: Earnings in 4 days. Any deployment now is pre-print exposure.
    Band is also stale — the 395.59–420.31 band may shift after band refresh.
    Do not deploy at current price (3.0% above stale band top). If the operator
    wants pre-print exposure, it requires explicit decision and half-tier sizing.
    Post-print review is the preferred path.

──────────────────────────────────────────────────────────────────
POST-EARNINGS REVIEW                                         (5 names)
──────────────────────────────────────────────────────────────────
  Ordered by consequence: in-band names first.

  MSFT  [POST-EARNINGS REVIEW — stale block; IN BAND]           ← PRIORITY
    workflow_state:  BLOCKED
    close:           407.78  |  vs. band: IN BAND (band 389.64–412.56)
    days_to_earnings: 89 days (next: 2026-07-29)
    band stale:      NO (within tolerance)
    earnings date:   2026-07-29 (yfinance) | vault had 2026-04-29 — STALE
    macro gate:      DEGRADED
    override:        RULE 2 (earnings_blocked=true but calendar shows 89d; stale block)
    ma posture:      above 20d (403.52) and 50d (395.79); below 200d (467.08)
    why:             In entry band at 407.78 but earnings block active (block is stale)
    ──
    OPERATOR NOTE: MSFT printed Apr 29. Block is stale (vault date not updated).
    MSFT is currently IN its entry band at 407.78. MA posture is partial (below 200d
    at 467.08 is a real concern). Post-earnings review is REQUIRED before any
    re-classification. After review: if the Apr 29 results support the thesis and
    the 200d posture is acceptable, MSFT could be ALMOST DEPLOYABLE. This is the
    highest-priority post-earnings review in the current stack.

  AMZN  [POST-EARNINGS REVIEW — stale block]
    workflow_state:  BLOCKED
    close:           265.06  |  vs. band: 3.9% above band top (band 240.89–255.09)
    days_to_earnings: 90 days (next: 2026-07-30)
    band stale:      YES (in band_staleness warning scope)
    earnings date:   2026-07-30 (yfinance) | vault had 2026-04-29 — STALE
    macro gate:      DEGRADED
    override:        RULE 2 (stale block)
    why:             Name not yet decision-grade; explicit entry and stop missing
    ──
    OPERATOR NOTE: Apr 29 print happened. Block is stale. Post-earnings review needed.
    Even after review and block clearance, AMZN is 3.9% above a stale band — likely
    ALMOST DEPLOYABLE at best, not deployable now. Secondary to MSFT.

  GOOG  [POST-EARNINGS REVIEW — stale block]
    workflow_state:  BLOCKED
    close:           381.94  |  vs. band: 10.8% above band top (band 325.66–344.66)
    days_to_earnings: 83 days (next: 2026-07-23)
    band stale:      YES (in band_staleness warning scope)
    earnings date:   2026-07-23 (yfinance) | vault had 2026-04-29 — STALE
    macro gate:      DEGRADED
    override:        RULE 2 (stale block)
    why:             Earnings block active — wait for print (block is stale)
    ──
    OPERATOR NOTE: Apr 29 print happened. Block is stale. Post-earnings review needed.
    GOOG is 10.8% above a stale band — extended regardless of block status.
    After review: likely stays ALMOST DEPLOYABLE for a pullback setup at best.
    Third priority after MSFT and AMZN.

  CAT  [POST-EARNINGS REVIEW — T+1, no review note]
    workflow_state:  WATCH
    close:           890.11  |  vs. band: 7.2% above band top (band 779.15–830.59)
    days_to_earnings: -1 (reported 2026-04-30 — yesterday)
    band stale:      YES
    earnings date:   2026-04-30 (reported) | next not yet on calendar
    macro gate:      DEGRADED
    override:        RULE 3 (days_to_earnings ≤ 0; no post-earnings review)
    why:             Reported yesterday; pre-print setup is obsolete
    ──
    OPERATOR NOTE: CAT just reported. Pre-print ALMOST DEPLOYABLE classification
    is obsolete. Post-earnings review required before any re-evaluation.
    Also workflow_state=WATCH (no human-validated entry) and 7.2% above a stale band.
    Lowest priority of the post-earnings group for immediate action.

  XOM  [POST-EARNINGS REVIEW — reporting today]
    workflow_state:  REPAIR
    close:           154.33  |  vs. band: no band defined
    days_to_earnings: 0 (reporting today — 2026-05-01)
    band stale:      n/a (no band)
    earnings date:   2026-05-01
    macro gate:      DEGRADED
    override:        RULE 3 (days_to_earnings = 0; reporting today)
    why:             Repair mode; requalification gate is May 1 earnings plus EIA follow-through
    ──
    OPERATOR NOTE: XOM reports today. Requalification event is live. Post-earnings
    interpretation is the next step — run post_earnings_prep.py after the print and
    update Deployment Trigger Sheet and Portfolio Snapshot. If oil structure and Q1
    results support the thesis, XOM moves to ALMOST DEPLOYABLE or WATCH depending
    on whether a band can be defined. Do not pre-position.

──────────────────────────────────────────────────────────────────
BLOCKED (valid active block)                                 (0 names)
──────────────────────────────────────────────────────────────────
  None. The three names that appeared BLOCKED in machine output (AMZN, GOOG, MSFT)
  have been reclassified to POST-EARNINGS REVIEW because their blocks are stale
  (vault dates predate actual prints). No name currently has a valid active
  pre-print block (where earnings are ≤14 days away and have not yet occurred).

  UPCOMING VALID BLOCKS (will transition to BLOCKED as dates approach):
    BRK.B  — earnings 2026-05-02 (tomorrow); currently DO NOT TOUCH [REPAIR]
    ETN    — earnings 2026-05-05 (4 days); currently ALMOST + NEAR-EARNINGS CAUTION
    NVDA   — earnings 2026-05-20 (19 days; unconfirmed); currently ALMOST

──────────────────────────────────────────────────────────────────
DO NOT TOUCH                                                 (4 names)
──────────────────────────────────────────────────────────────────

  LMT  [DO NOT TOUCH — BELOW STOP]
    workflow_state:  REPAIR  |  close: 517.97  |  stop: 581.50
    below_stop: YES  |  ma posture: below all MAs
    override: RULE 1
    why:   Post-earnings repair; old setup invalidated before Apr 23 print

  RTX  [DO NOT TOUCH — BELOW STOP]
    workflow_state:  WATCH  |  close: 176.07  |  stop: 182.60
    below_stop: YES  |  ma posture: below all MAs
    override: RULE 1
    why:   Below all MAs; not decision-grade; setup does not exist

  BRK.B  [DO NOT TOUCH — REPAIR + NEAR-EARNINGS CAUTION]
    workflow_state:  REPAIR  |  close: 473.60  |  band: 465–472 (actionable only on repair through 481+)
    below_stop: NO  |  ma posture: below all MAs
    days_to_earnings: 1 day  |  near-earnings caution: YES
    earnings date: 2026-05-02 UNCONFIRMED (vault: May 4; yfinance: May 2)
    override: RULE 5 (repair mode); RULE 8 (near-earnings caution qualifier)
    why:   Below all MAs; structure weak; earnings tomorrow (date unconfirmed)

  GS  [WATCH / RESEARCH NEEDED — overrides machine: DEPLOYABLE NOW]
    Note: GS is displayed in the WATCH group below, but included here as a
    cross-reference because the machine ranks it #1. See WATCH section.

──────────────────────────────────────────────────────────────────
WATCH / RESEARCH NEEDED                                      (3 names)
──────────────────────────────────────────────────────────────────

  GS  [WATCH / RESEARCH NEEDED]
    workflow_state:  WATCH
    close:           923.77  |  vs. band: IN BAND (band 878.71–926.76)
    days_to_earnings: 74 days  |  band stale: NO (within tolerance)
    earnings date:   2026-07-14 (yfinance; newly added — confirm against vault)
    macro gate:      DEGRADED
    override:        RULE 4 (workflow_state = WATCH; machine said DEPLOYABLE NOW)
    why:   Not yet decision-grade; explicit entry and stop still missing in note layer
    ──
    OPERATOR NOTE: GS price genuinely hit its machine-generated band. This is a
    real technical signal, not a phantom. What is missing is the human validation
    layer — a decision-grade trigger note with explicit entry logic, sizing rationale,
    and stop in the Deployment Trigger Sheet. Until that exists, GS is WATCH.
    The threshold for promotion is: (1) thesis review completed, (2) human-validated
    entry and stop written into the trigger sheet, (3) workflow_state changed from
    WATCH to ALMOST by operator.

  VRT  [WATCH / RESEARCH NEEDED]
    workflow_state:  WATCH
    close:           328.49  |  vs. band: 1.7% above band top (band 292.22–323.07)
    days_to_earnings: 89 days  |  band stale: YES
    earnings date:   2026-07-29  |  macro gate: DEGRADED
    override:        RULE 4 (workflow_state = WATCH; machine said ALMOST DEPLOYABLE)
    why:   Not yet decision-grade; explicit entry and stop still missing
    ──
    OPERATOR NOTE: Good thematic fit. Beat-and-raise Apr 22. But no human-validated
    setup exists. Also 1.7% above a stale band — even technically not quite in band.
    Promote only after a thesis review and human trigger note is written.

  AMD  [WATCH / RESEARCH NEEDED]
    workflow_state:  WATCH  |  close: 354.49  |  no band defined
    days_to_earnings: 5 days (earnings 2026-05-05)  |  near-earnings caution: YES
    override: RULE 4 (WATCH)
    why:   Entry band not defined; research needed

═══════════════════════════════════════════════════════════════════
MORNING SUMMARY — 2026-05-01
═══════════════════════════════════════════════════════════════════
Deployable now:          0  (DEPLOYABLE NOW suspended system-wide)
Almost deployable:       2  (JPM, NVDA)
Near-earnings caution:   1  (ETN)
Post-earnings review:    5  (MSFT★, AMZN, GOOG, CAT, XOM)
Blocked (valid):         0
Do not touch:            4  (LMT, RTX, BRK.B, + GS cross-reference)
Watch / research:        3  (GS, VRT, AMD)

★ MSFT is the priority post-earnings review — in band, stale block, needs human read
  on Apr 29 results before any re-classification.

Highest-confidence action: Monitor JPM only for pullback to 300–306.
```

---

## 8. Downgrade behavior under degraded trust

This table defines exactly what changes on the morning surface when specific trust conditions are active. Each condition maps to a precise surface behavior change.

| Trust condition | Source | Surface behavior |
|---|---|---|
| `stop_line = true` | run-summary | All names → SYSTEM HOLD. No other content shown. |
| `fallback_state.used = true` | run-summary | DEPLOYABLE NOW suspended globally. Any name that would reach DEPLOYABLE NOW via Rule 9 is downgraded to ALMOST DEPLOYABLE [trust ceiling]. Header shows "DEPLOYABLE NOW SUSPENDED." |
| `canonical_note_mutation_allowed = false` | run-summary | Warning shown: "note updates via automated flow are blocked — human writes only." No effect on name states. |
| `presentation_allowed = false` | run-summary | Warning shown: "surface is not authorized for publication — treat as evidence only." No effect on name states. |
| `dashboard_validation overall = "warning"` | dashboard-validation | Header shows active warning list with ticker scope. All warnings are named before name rows. |
| `timing_sensitive_earnings_dates` warning active | dashboard-validation | Affected names show `earnings date: UNCONFIRMED` in their surface row. Cannot be promoted to DEPLOYABLE NOW until date confirmed. |
| `earnings_block_window_unexpected` for a name | dashboard-validation | Rule 2 fires for that name → POST-EARNINGS REVIEW override. |
| `band_staleness` for a name | dashboard-validation | Name shows `band stale: YES`. Rule 6 prevents DEPLOYABLE NOW. If Rule 9 would emit ALMOST, the ALMOST stands but with stale band qualifier. |
| `macro_manual_dependency` active | dashboard-validation | All names show `macro gate: DEGRADED`. No state changes — qualifier only. |
| `policy_expectations_fallback_source` active | dashboard-validation | Included in macro gate DEGRADED qualifier. No additional state change beyond macro note. |

### What trust degradation does NOT do

- It does not downgrade names from ALMOST DEPLOYABLE to BLOCKED or DO NOT TOUCH
- It does not change the priority ordering within a state group
- It does not trigger additional blocks beyond what the adjudication rules already specify
- The current trust degradation (fallback_state.used=true, macro manual) does not block JPM's ALMOST DEPLOYABLE status — JPM's state is correct under both clean and degraded trust

---

## 9. What Phase 3 must implement

Phase 2 has defined the target surface. Phase 3 must make the machine stack reliable enough to generate it automatically. The ten gaps from Phase 1 map to specific Phase 3 work items.

**Required for the surface to be trustworthy without manual adjudication:**

| Gap | Phase 3 work |
|---|---|
| G-1 (workflow_state not gated) | Add `workflow_state ≠ WATCH` as required condition before emitting DEPLOYABLE or ALMOST in deployment-check.py and trigger-sheet generation |
| G-2 (stale earnings blocks) | Reconcile earnings_blocked against earnings-calendar.json dates in technical-refresh.py; when calendar date > 14d and earnings_blocked=true, emit `earnings_block_stale: true` and clear the block |
| G-3 (trust gates not propagated) | Add trust_state header block to trigger-sheet.json and positioning-ranking.json mirroring run-summary downstream permission flags |
| G-4 (no post-earnings state transition) | Add `post_earnings_review_confirmed` field to portfolio-config.json per name; add state logic: days_to_earnings_calendar ≤ 0 AND !confirmed → POST_EARNINGS_REVIEW state |
| G-5 (near-earnings qualifier missing) | Add NEAR-EARNINGS CAUTION qualifier to action_state string when days_to_earnings ≤ 7 AND catalyst_risk_score ≤ 3 |
| G-6 (score bonuses override semantic state) | Cap priority_bucket at Secondary for names with workflow_state=WATCH or thesis_status containing "under active review" |
| G-7 (run-summary predates artifact refresh) | Move run-summary generation to last step in run_finance_refresh_chain.py, after all downstream artifacts are written |
| G-8 (macro trust not per-name) | Add `macro_gate_trust: "clean" \| "degraded"` per record to trigger-sheet.json when macro_manual_dependency warning is active |
| G-9 (band stale not per-name) | Add `band_stale: true \| false` per record to trigger-sheet.json based on dashboard-validation band_staleness scope |
| G-10 (acceptance report misleading) | Rename `all_passed` to `validator_functioning`; add separate `data_quality_grade` field |

**Implementation sequence for Phase 3 (recommended):**  
G-2 first (fixes the AMZN/GOOG/MSFT false negatives — most visible wrong signal). Then G-1 (fixes GS false positive — highest severity wrong call). Then G-7 (fixes timestamp gap — process integrity). Then G-3, G-4, G-5, G-6 in a single pass (surface completeness). Then G-8, G-9, G-10 (refinement).

**One required operator action before Phase 3 can fully close G-2 and G-4:**  
The vault watchlist dates for MSFT, GOOG, AMZN, LMT must be updated post-print before the script reconciliation in G-2 will work correctly. The script fix and the vault update are co-dependent. If the script is fixed but the vault dates remain at April 29, the reconciliation will still see vault=calendar and not detect the staleness.

---

## 10. Fields required in portfolio-config.json that do not exist today

Phase 3 must add these fields to `portfolio-config.json` per name entry:

```json
{
  "ticker": "MSFT",
  ...existing fields...,
  "post_earnings_review_date": null,
  "last_earnings_date": "2026-04-29",
  "earnings_date_ir_confirmed": false,
  "earnings_date_ir_confirmed_date": null
}
```

- `post_earnings_review_date`: date the last post-earnings review was completed in the trigger sheet. `null` if never done or if last_earnings_date is more recent.
- `last_earnings_date`: the date of the most recent actual earnings print (not next earnings date). Used by G-2 and G-4.
- `earnings_date_ir_confirmed`: whether the next earnings date has been confirmed from the company's IR. Drives the UNCONFIRMED qualifier on the surface.
- `earnings_date_ir_confirmed_date`: when the confirmation was recorded.

---

*Phase 2 complete.*  
*All findings are design-only. No files changed except this design document.*  
*Proceed to Phase 3 upon operator confirmation.*
