# Alert Bands and Invalidation Register

## Purpose

Own the human thesis, static alert thresholds, and alert-interpretation register for tracked names. Guarded SQL is the exact machine mirror used by the fast path.

## Current-Level Contract

- Human canonical source: this register.
- Machine-readable mirror: `state/finance/finance-canon.sqlite` field family `reference_levels`.
- Typed access guard: `python scripts\finance_sql_canon_access.py --write --validate`.
- Current alert-level proof: `python scripts\alert_level_freshness_controller.py --write --validate`.
- Exact level claims must include source timestamp, quote timestamp, freshness state, validation state, and confidence.
- If any required field is stale, missing, or conflicted, emit a freshness or invalidation review alert and do not represent the recommendation as current.

The table below is the source for the mirrored numeric thresholds. A mirror is current only when its source path, artifact hash, values, and source timestamp reconcile to this file. Moving a threshold into this register does not refresh its underlying market judgment; `level_as_of` remains the last substantive review date.

## Static Alert Thresholds

These values were migrated without numeric change during the 2026-08-29 portfolio-management retirement. `State` is an observation label, not an order or holding state. Blank state means no current classification was preserved.

| Ticker | Alert low | Alert high | Invalidation threshold | State | Level as of |
|---|---:|---:|---:|---|---|
| AMD | 411.81 | 495.52 | 373.76 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| AMZN | 243.52 | 262.94 | 232.73 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| BKNG | 188.28 | 205.72 | 178.75 | NEAR_BAND | 2026-08-21T20:31:52.979543+00:00 |
| BRK.B | 488.39 | 506.98 | 478.07 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| CAT | 758.52 | 860.43 | 712.19 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| CME | 252.31 | 265.88 | 244.77 | NEAR_BAND | 2026-08-21T20:31:52.979543+00:00 |
| CVX | 186.90 | 196.84 | 181.26 | NEAR_BAND | 2026-08-21T20:31:52.979543+00:00 |
| ECL | 272.36 | 281.00 | 264.78 | NEAR_BAND | 2026-08-21T20:31:52.979543+00:00 |
| ETN | 385.98 | 434.40 | 363.96 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| GE | 341.38 | 363.52 | 329.08 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| GOOG | 326.46 | 348.13 | 314.42 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| GS | 1019.26 | 1045.58 | 981.53 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| ITA | 212.15 | 223.44 | 205.88 |  | 2026-06-16 |
| JPM | 342.95 | 356.74 | 335.29 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| KTOS | 73.52 | 78.09 | 69.86 | BELOW_STOP | 2026-08-17T19:48:23.483024+00:00 |
| LIN | 468.30 | 492.08 | 455.09 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| LLY | 1146.80 | 1217.12 | 1093.23 | NEAR_BAND | 2026-08-21T20:31:52.979543+00:00 |
| LMT | 550.09 | 583.84 | 531.34 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| LNG | 255.11 | 268.80 | 245.31 | NEAR_BAND | 2026-08-21T20:31:52.979543+00:00 |
| META | 623.36 | 648.95 | 602.89 | BELOW_STOP | 2026-08-21T20:31:52.979543+00:00 |
| MSFT | 439.68 | 472.96 | 417.51 | NEAR_BAND | 2026-08-21T20:31:52.979543+00:00 |
| NFLX | 88.42 | 91.27 | 86.14 | BELOW_STOP | 2026-08-21T20:31:52.979543+00:00 |
| NVDA | 202.15 | 217.11 | 193.84 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| PAVE | 53.94 | 56.28 | 52.64 |  | 2026-06-16 |
| PH | 965.41 | 1026.18 | 931.65 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| PLTR | 139.89 | 163.76 | 129.04 | ABOVE_BAND_WAIT | 2026-08-21T20:31:52.979543+00:00 |
| RTX | 206.23 | 216.92 | 200.29 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| SLV | 64.22 | 66.41 | 62.47 | BELOW_STOP | 2026-08-17T19:48:23.483024+00:00 |
| SMCI | 25.84 | 33.30 | 22.46 | ABOVE_BAND_WAIT | 2026-08-17T19:48:23.483024+00:00 |
| TLT | 85.20 | 85.96 | 84.59 | BELOW_STOP | 2026-08-17T19:48:23.483024+00:00 |
| TMUS | 194.73 | 201.38 | 189.41 | BELOW_STOP | 2026-08-21T20:31:52.979543+00:00 |
| VAW | 225.44 | 233.70 | 220.85 |  | 2026-06-16 |
| VMC | 288.18 | 297.98 | 280.34 | BELOW_STOP | 2026-08-21T20:31:52.979543+00:00 |
| VRT | 230.66 | 280.95 | 207.79 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| VXUS | 80.88 | 83.36 | 78.15 |  | 2026-06-16 |
| WMB | 68.51 | 73.17 | 65.92 | IN_BAND | 2026-08-21T20:31:52.979543+00:00 |
| XLB | 49.84 | 51.68 | 48.81 |  | 2026-06-16 |
| XLC | 114.31 | 116.55 | 112.71 |  | 2026-06-16 |
| XLE | 56.35 | 58.04 | 54.83 |  | 2026-06-16 |
| XLF | 52.26 | 53.07 | 51.61 |  | 2026-06-16 |
| XLI | 166.78 | 173.40 | 163.10 |  | 2026-06-16 |
| XOM | 150.65 | 159.09 | 145.78 | NEAR_BAND | 2026-08-21T20:31:52.979543+00:00 |

## Primary Tracked Names

| Ticker | Thesis context | Alert interpretation |
|---|---|---|
| ETN | AI power, electrification, and industrial-capex demand | Watch band entry, evidence deterioration, and structural invalidation. |
| JPM | Selective financial exposure with credit and rate sensitivity | Watch band reclaim, credit deterioration, and invalidation. |
| NVDA | AI leadership with valuation, crowding, and catalyst risk | Enforce no-chase discipline; alert on band entry, earnings reset, or thesis change. |
| GOOG | Search, cloud, AI monetization, and regulatory risk | Watch supported pullbacks, evidence change, and invalidation. |
| MSFT | Cloud and AI platform strength with valuation and capex risk | Watch band entry, trend repair, and thesis change. |
| GS | Capital-markets sensitivity with cyclical risk | Compare signal quality with other financial candidates; alert only on material differentiation. |
| VRT | AI-infrastructure power demand with execution and valuation risk | Watch evidence repair, band entry, and thesis change. |
| BRK.B | Diversified quality and defensive ballast | Alert on material valuation opportunity, thesis change, or structural repair. |
| XOM | Integrated-energy cash generation with commodity and geopolitical sensitivity | Watch energy-regime change, band entry, and invalidation. |
| LMT | Defense demand with program and execution risk | Require structural and evidence repair before a positive recommendation review. |
| RTX | Defense and aerospace demand with program risk | Require structural and evidence repair before a positive recommendation review. |

## Secondary Monitor Names

AMZN, CAT, LLY, CVX, PLTR, AMD, and LNG remain monitor candidates. They become material recommendation candidates only when evidence, freshness, and signal quality clear the trigger policy.

## Record Requirements

Each generated ticker row must contain:

- `ticker`
- `reference_low`
- `reference_high`
- `invalidation_threshold`
- `latest_price`
- `level_as_of_utc`
- `quote_as_of_utc`
- `freshness_status`
- `validation_status`
- `confidence`
- `alert_state`
- `source_path`

## Authority Boundary

Bands and invalidation thresholds are decision-support metadata. They do not authorize capital, orders, account action, money movement, or paper/live execution, and they do not create system-owned sleeves, positions, allocations, weights, sizing, tranches, cash, rebalancing, or simulated account state.
