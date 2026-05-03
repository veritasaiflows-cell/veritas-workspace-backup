# Dashboard Command Center Audit

**Date:** 2026-04-22  
**Scope:** `veritas-command-center.html`, `scripts/generate_dashboard.py`, `scripts/dashboard-template.html`, related `tmp/` dashboard/source artifacts, and dashboard-relevant portions of `scripts/README.md`  
**Out of scope:** `Claude.md`

## 1. Executive overview

This dashboard is usable, visually strong, and materially better than a toy status page. It has a coherent pipeline, a clean separation between source files and rendered output, and enough provenance/delta machinery to be operationally helpful.

But it is not yet decision-grade in the strict sense it implies.

The core problem is trust calibration. The system presents itself as current, centralized, and disciplined, while several parts are still manually maintained, partially missing, hardcoded, or silently defaulted. That creates a real risk of false confidence. The UI often looks more certain than the underlying data deserves.

The biggest issues are not styling. They are truthfulness, data semantics, and governance drift:
- freshness can read as "current" even when market data is old or partial
- some business logic still lives in the template despite the claimed architecture boundary
- hardcoded assumptions remain in the UI layer
- missing data is sometimes rendered as numeric zero or suppressed instead of treated as unavailable
- there is little validation for internal contradictions across source fields

Bottom line: this is a solid operating dashboard prototype with real utility, but it is still too permissive and too optimistic for high-trust portfolio decision support.

## 2. Overall score

**6.7 / 10**

Strong structure and practicality, weakened by data-trust leakage, logic drift, and misleading certainty.

## 3. Category scores

| Category | Score | Notes |
|---|---:|---|
| Architecture / separation | 7.5 | Better than average, but business logic still leaks into UI |
| Data provenance / freshness | 6.0 | Provenance exists, but freshness semantics are too generous |
| Decision-support reliability | 5.8 | Helpful, but can overstate readiness and currentness |
| UX / readability | 8.2 | Clear, fast to scan, strong visual hierarchy |
| Maintainability | 6.2 | Centralization improved, but hardcoded logic remains |
| Operational robustness | 6.4 | Handles missing files, but often degrades too quietly |
| Drift resistance | 5.5 | Manual inputs and duplicated assumptions invite divergence |

## 4. Strengths

- Clean single-file generator flow. `generate_dashboard.py` is understandable and operationally simple.
- Good provenance concept. The `provenance` and `freshness` blocks are the right idea.
- Useful normalization layer. The generator turns uneven source artifacts into a consistent dashboard payload.
- Delta tracking is genuinely valuable. `dashboard-delta.json` adds operational context instead of just repainting the same screen.
- Strong UX. The dashboard is readable, structured, and optimized for fast scanning.
- Appropriate use of offline cached JSON. That reduces runtime fragility and keeps the dashboard reproducible.
- Portfolio truth is mostly externalized to `tmp/portfolio-config.json`, which is the right direction.

## 5. Vulnerabilities

1. **Misleading freshness classification**  
   The dashboard can show **"Data Current"** and **"Execution context: FRESH"** even when market data is 38.1 hours old and `market-state.json` is explicitly `status: "partial"` with missing 2Y, missing 2s10s, null FedWatch, empty sector snapshots, and empty actionable-name snapshots.

2. **Silent zero/default rendering for missing data**  
   Multiple UI renderers use patterns like `(value || 0).toFixed(...)`. Missing data can therefore render as `0.00`, not as unavailable. That is unacceptable in a decision-support dashboard.

3. **Hardcoded business assumptions still in the UI**  
   The risk/compliance view hardcodes tech concentration tickers in the template instead of using config payload. This directly contradicts the stated architecture direction.

4. **Unsanitized `innerHTML` rendering**  
   The template injects many values directly into `innerHTML`. In this local/offline context this is not the top risk, but it is still a fragility and data-integrity problem if malformed strings enter source JSON.

5. **No contradiction checks across source fields**  
   Example: `LMT` is labeled `"Above 200d, below 20d/50d"` while `above200` is `false` and close is below the listed 200d. The dashboard does not detect or flag the inconsistency.

## 6. Operational risks

- **False green status risk:** the operator may trust "fresh" status when the market layer is only partially live.
- **Manual update dependency risk:** Fed target data is explicitly hardcoded and earnings/watchlist drift is already visible.
- **Weak failure surfacing:** missing or incomplete sections often degrade into empty blocks or benign-looking defaults instead of loud operator warnings.
- **Snapshot lag risk:** generated HTML embeds a static snapshot, but the UI presentation can feel live unless the user notices the timestamps.
- **Governance mismatch:** README claims a cleaner architecture boundary than the actual template enforces.

## 7. Data-trust / drift risks

- `portfolio-config.json` is marked manual, but the dashboard does not sharply distinguish manual truth from machine-refreshed truth in the primary UI.
- Freshness logic is age-threshold based, not market-session aware. A source can be technically under 48 hours old and still be operationally stale for morning execution use.
- `tech_tickers_for_concentration` exists in config but is not carried through the payload or used by the template. That is textbook drift setup.
- Partial macro inputs are surfaced as warnings, but the top-level UI still reports a healthy execution state.
- Entry-band and stop math assume source correctness, with no validation against `inBand`, `belowStop`, posture, or deployment state.

## 8. UX or decision-support weaknesses

- The header regime badge is static text, not clearly data-bound.
- The dashboard emphasizes certainty visually more than uncertainty structurally.
- Missing macro sub-blocks like sectors/actionable names are not surfaced prominently.
- The "Today’s Action Card" logic can overstate trigger conditions because `triggerToday` is based on `bandGapDollar <= 0`, which includes names below the entry band, not only names inside the band.
- The earnings badge logic in the template marks `days <= 1` as `TODAY`, which can mislabel tomorrow.
- There is no dedicated trust banner explaining that some inputs are manual, partial, or best-effort.

## 9. Maintainability concerns

- The template still contains nontrivial business logic, not just presentation.
- Several fallback/default behaviors are duplicated in JS rather than normalized once in Python.
- Architecture comments overstate purity, which will mislead future maintainers.
- The generated HTML is large and data-heavy, which makes review and diffing noisy.
- Hardcoded style/status mappings are acceptable, but hardcoded portfolio semantics are not.
- No explicit schema validation layer exists for source JSONs or normalized payload.

## 10. Prioritized recommendations

### Priority 1, fix immediately

1. **Make freshness truth stricter and more honest.**  
   `exec_freshness` should degrade for `partial` quality, critical nulls, or empty expected sub-blocks, not only missing files or age breaches.

2. **Stop rendering missing numeric data as zero.**  
   Replace all numeric zero fallbacks for absent values with explicit unavailable states.

3. **Remove remaining hardcoded portfolio logic from the template.**  
   Pass concentration tickers and any other decision semantics through the payload.

4. **Add validation and contradiction checks in Python.**  
   Catch posture/flag/math mismatches and surface them as warnings or integrity failures.

### Priority 2, next pass

5. **Move business logic out of the template.**  
   The template should mostly render precomputed display-ready sections or validated primitives.

6. **Differentiate data quality visibly in the UI.**  
   Show machine-refreshed, manual, partial, and missing states distinctly and prominently.

7. **Make regime badge and other headline elements fully data-bound.**

8. **Add market-session-aware freshness.**  
   A 38-hour-old market snapshot should not present the same as a same-session refresh.

### Priority 3, cleanup and hardening

9. **Escape rendered strings or reduce `innerHTML` usage where practical.**
10. **Add a small schema contract for each source artifact and the final payload.**
11. **Add a dedicated integrity/trust panel summarizing manual fields, partial inputs, and stale-but-under-threshold cases.**

## 11. Concise remediation roadmap

### Phase 1, trust repair
- tighten `exec_freshness` semantics
- treat partial critical data as degraded, not fresh
- eliminate zero-for-missing rendering
- add integrity warnings for contradictory records

### Phase 2, architecture repair
- move compliance and trigger-calculation logic into Python
- pass all config-driven semantics through payload
- make the template a thinner renderer

### Phase 3, operator confidence repair
- add an explicit trust/status panel
- distinguish manual vs machine vs partial inputs visually
- make headline badges fully derived from payload

## Blunt conclusion

The dashboard looks more finished than it really is.

It is already useful for orientation. It is not yet trustworthy enough to serve as a clean final decision surface without a skeptical human reading the warnings and knowing where the bodies are buried.

If you fix the truth-calibration problems first, this becomes a strong operating console. If you keep polishing visuals before tightening semantics, it will drift into a dangerous confidence machine.
