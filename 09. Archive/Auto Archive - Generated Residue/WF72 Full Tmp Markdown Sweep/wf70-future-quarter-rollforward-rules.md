# WF70 Future-Quarter Rollforward Rules

Generated: 2026-05-22T19:51:27Z

Status: design-ready, not implemented. Review-only evidence/control artifact.

## Purpose

Define how official IR captures roll from the current Q1 2026 capture set to future quarters without stale prior-quarter evidence being treated as current.

## Current inventory
- Capture count: 31
- Period-end counts: 2026-03-28: 1, 2026-03-29: 2, 2026-03-31: 27, 2026-04-26: 1
- Tickers: AMD, AMZN, BKNG, BRK.B, CAT, CME, CVX, ECL, ETN, GE, GOOG, GS, JPM, KTOS, LIN, LLY, LMT, LNG, META, MSFT, NFLX, NVDA, PH, PLTR, RTX, SMCI, TMUS, VMC, VRT, WMB, XOM

## Rollforward states
- **latest_current:** Validator-clean official capture is the newest known official period for the ticker, and no newer official release/filing has been detected.
- **latest_partial:** Newest official period has a capture artifact, but one or more required fields are partial/not_disclosed/not_applicable/manual_required according to official evidence; downstream can use it only with explicit caveat.
- **new_source_detected_not_captured:** An official newer-period source is known, but the next-period capture artifact has not been produced or validated; previous capture must be treated as stale for current decision use.
- **parser_failed_or_manual_required:** New official source was found but extraction did not satisfy the field contract; emit manual_required/source_found_parser_failed rather than carrying forward old values.
- **stale_prior_period:** Older validator-clean capture retained for history/comparison only after newer official period is detected or current period expectation passes.
- **missing_official_source:** No official source found for expected period; do not fabricate fields and do not mark previous period as current if release should already exist.
- **not_yet_due:** Next reporting period is not yet expected for the ticker; prior validator-clean capture remains latest official evidence, not stale.

## Rules
### Artifact Naming
- Keep immutable period files: tmp/official-ir-captures/{ticker}-{period_slug}.json and .md.
- Use q2-2026 etc. for next period; do not overwrite q1 artifacts.
- Validation file mirrors period slug: {ticker}-{period_slug}-validation.json.
### Source Priority
- SEC 8-K/6-K exhibit 99.1 or equivalent official filing exhibit
- Company IR earnings release
- Company earnings presentation / shareholder letter
- Official prepared remarks/interview transcript
- Third-party material only as a discovery cue, never as official field evidence
### Selection
- Downstream consumers must select latest validator-clean official capture per ticker by period_end/reporting_period, not by filename sort alone.
- If a newer official source is detected but not captured/validated, downstream state is new_source_detected_not_captured and previous period is stale_prior_period.
- Historical captures remain queryable for comparison but cannot silently satisfy current-period freshness.
### Failure Behavior
- Never reuse prior-quarter numeric values as current-quarter values.
- If extraction fails, create/degrade to parser_failed_or_manual_required with source URL and missing fields.
- If company does not disclose a field, use not_disclosed_in_release/not_applicable with evidence, not manual_required or fabricated data.
### Authority
- Review-only evidence/proof surface.
- No canon mutation by cron.
- No portfolio, deployment, trade/account, paper-order, sizing/sleeve/cash/risk-rule mutation.
- No owner approval inference from clean capture or validator state.

## Q1 hard-coding consumer scan
| Surface | Q1 dependency | Role | Smallest change |
|---|---:|---|---|
| `scripts/official_ir_capture_common.py` | high | shared writer currently hard-codes q1-2026 filenames and Q1 2026 markdown title | add optional period_slug/period_label to run_capture_batch() and render_markdown(), defaulting to q1-2026/Q1 2026 for backward compatibility |
| `scripts/chain_manifest.py` | high | scheduled windows list q1-2026 expected outputs for all capture scripts and validations | derive expected outputs from a current official-capture period registry instead of duplicating literal q1 filenames across windows |
| `scripts/current_window_artifact_index.py` | high | current-window proof lookup hard-codes q1 capture and validation artifact paths | replace static official capture entries with latest-valid selector output or generated registry rows; retain historical q1 links as prior-period proof |
| `scripts/run_summary_refresh.py` | high | window required outputs hard-code q1 paths, so future q2 coexistence would require manual duplication | load official capture required outputs from the same period registry/latest selector used by current-window index |
| `scripts/fundamental_ir_reconciliation_packets.py` | medium | loads all validated official capture JSON by ticker; if q1 and q2 coexist, later sorted filename may overwrite earlier without explicit freshness logic | select latest validator-clean capture per ticker by period_end/reporting_period, emit previous_period_artifact, and degrade stale/missing states explicitly |
| `scripts/official_earnings_bridge.py` | medium | reads official capture directory and needs same latest-per-ticker semantics as reconciliation packets | reuse a shared latest capture selector; never treat old q1 as current after newer official source is detected |
| `scripts/official_ir_capture_validator.py` | low | validates arbitrary capture files already; default example points to goog-q1-2026 | make defaults examples only; optionally validate registry/latest set and report period coverage |
| `scripts/artifact_index.py` | low | SQL schema already stores period_end and indexes ticker+period; not materially q1-bound | add current_period_state/latest flag only after selector exists; keep SQL proof/index/staging only |
| `capture entrypoints: goog/tech/priority/etn_vrt/batch2/batch2b/longtail` | high | source metadata and extractor text are Q1-specific production captures | do not overwrite; create Q2 metadata/extractor entries or period-aware source registry when official Q2 releases arrive; keep Q1 as immutable historical capture |

## Smallest code changes needed
- Introduce a small official_capture_period_registry artifact or module listing ticker, expected/current period_slug, period_end, source status, capture script, and expected output paths.
- Add a shared latest-validator-clean capture selector used by fundamental_ir_reconciliation_packets.py and official_earnings_bridge.py before Q2 files coexist with Q1 files.
- Parameterize official_ir_capture_common.py filename/title rendering with period_slug/period_label while preserving current Q1 defaults.
- Generate chain_manifest/current_window_artifact_index/run_summary_refresh official-capture path entries from the registry/selector to remove duplicated q1 literals.
- Only after the registry/selector exists, add Q2 source metadata/extractor entries ticker-by-ticker as official releases arrive; keep old Q1 files immutable.

## Recommended implementation order
- Build registry/selector with read-only report mode first.
- Run side-by-side current Q1 outputs to prove no drift.
- Replace consumer duplicated q1 path lists with generated registry/selector outputs.
- Only then add next-period capture sources as releases appear.

## Authority boundary

Review-only. No canon/portfolio/deployment/trade/account/paper-order/sizing/sleeve/cash/risk-rule mutation and no owner approval inferred.
