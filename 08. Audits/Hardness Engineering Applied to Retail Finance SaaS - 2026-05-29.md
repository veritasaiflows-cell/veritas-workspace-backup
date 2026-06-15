# Hardness Engineering Applied to Retail Finance SaaS - 2026-05-29

**Author:** Veritas main session
**Date:** 2026-05-29 15:08 MST
**Context:** Written after workspace audit and retail SaaS readiness assessment. Defines the concept, maps it to the current Veritas workspace, and identifies where to apply it in the retail investor finance intelligence product build.

---

## 1. What Hardness Engineering Is

The term comes from materials science. **Hardness** is a material's resistance to permanent deformation under localized stress — measured by how much force it takes to dent, scratch, or reshape a surface. Engineering for hardness means designing the *structure itself* to resist deformation, not relying on a protective coating or an external guard layered on top.

The key distinction:

- **Soft system:** protected by guards added on top. Remove the guard and the system deforms — produces incorrect output, corrupts state, or violates a claim boundary.
- **Hard system:** the structure itself resists deformation. Resistance is intrinsic. There is no path through the system that produces bad output because the system's shape does not permit it.

"Hardness engineering" as a formal software discipline does not exist under that name. The closest adjacent concepts are high-assurance systems design, security hardening, and fault-tolerant architecture. But the materials-science framing is more precise for the design question at hand: **not "how do we check for errors afterward" but "how do we build a system structurally incapable of certain failure modes."**

### The Practical Design Question

Instead of: *What validators do we layer on top of this system?*

Ask: *What is this system structurally incapable of producing?*

A hard financial intelligence product cannot emit a regulated-advice claim not because a validator blocked it, but because the output schema has no field to hold one. A hard freshness layer cannot present stale data as current because the rendering function does not have a code path that produces a timestamp-free output. The defect is impossible, not just caught.

---

## 2. Where the Veritas Workspace Already Has Structural Hardness

The workspace has accumulated a significant amount of intrinsic hardness through the WF58, WF68, WF72, WF73, and WF75/retail-SaaS work. Most of it was built in response to real defects — which is exactly how hardness accumulates in engineered materials (stress reveals weak points; the material is redesigned to eliminate them).

| Mechanism | What it structurally resists | How it's hard (not just checked) |
|---|---|---|
| `retail_saas_customer_output_validator.py` with adversarial probes baked in | Stale-data overconfidence, buy/sell directives, price-target/upside language, internal path/SQL/proof leaks | Adversarial probes are part of the validator's own test suite — failing them is a build failure, not a separate audit |
| SQL fail-closed posture (`guard_status=blocked`, `sql_effective_allowed_rows=0`) | SQL rows being treated as retail-grade truth before freshness gates clear | The guard is a required gate before any SQL-first consumer; there is no path to SQL-first use without clearing the guard |
| `wf72_entry_stop_reference_helper.py` — URI `mode=ro`, no write path | Inadvertent SQL mutations through the reference metadata layer | The read-only URI mode is structural; a write cannot happen through this path regardless of what the caller asks |
| `deployment_readiness_surface.py` machine/prose conflict guard | Green deployment state emitted while prose/research evidence says blocked/no-chase | The conflict guard is in the generation function; the output schema's `AUTHORITY CONFLICT` state is produced before rendering, not flagged after |
| `authority_vocabulary_consistency_check.py` | Authority-widening language drifting into generated artifacts | Runs as part of the finance chain manifest; artifacts with forbidden vocabulary cannot pass validation |
| `boot_surface_size_guard.py` with hard byte limits | Doctrine bloat silently re-accumulating after WF73 reduction | Hard failure on size threshold means bloat cannot go undetected through a routine chain run |
| Customer export schema — no `recommendation`, `action`, or `target_price` fields | Regulated-advice claim language in customer-facing output | Schema-level omission: you cannot serialize a `recommendation` field because the field does not exist in the output contract |
| WF67 paper-only guardrail — paper endpoint required, kill switch required, audit log required | Live brokerage action through the paper trading path | Each required element is a structural prerequisite; missing any one of them blocks execution before the order reaches an endpoint |

### Where Hardness is Currently Soft (Checklist-Dependent)

These mechanisms exist but rely on a separate check that can drift:

| Mechanism | Why it's soft | Evidence |
|---|---|---|
| `test_dashboard_acceptance.py` | Hardcoded assertions that drift from system state | Today's failure: GOOG vs JPM/MSFT/GS. The test decoupled from reality; the system kept running |
| WF68 advisor validator | Validator and producer have diverged semantically | Validator throws `in_band_alert_labeled_wait_for_band` while the current packet has zero in-band alerts — they no longer agree on what "in-band" means |
| `openclaw doctor` memory-search warning | External key dependency; no graceful degradation path | System reports an error but continues; there is no structural fallback that says "memory search is unavailable, here is what you get instead" |
| Finance chain acceptance test | Blocked chain stops canonical note mutation but the chain still runs and produces stale artifacts | `tmp/run-summary-post-close.json` is `blocked` but artifacts continue to be generated and referenced |

---

## 3. Hardness Engineering Applied to the Retail Finance SaaS

The retail investor finance intelligence product has three output-layer properties that must be structurally guaranteed, not just checked:

1. The system cannot emit an unvalidated claim to a customer.
2. The system cannot present stale data as current.
3. The system cannot produce regulated-advice language in any customer-visible field.

Below is how to engineer each of these as structural properties rather than validator layers.

---

### 3.1 Output-Layer Hardness — No Path to Unvalidated Customer Output

**Current state:** `retail_saas_fixture_demo.py` calls `retail_saas_customer_output_validator.py` as a separate step. The two are adjacent, not fused. A caller can generate the fixture output and skip the validator.

**Hard version:**

```python
def generate_customer_brief(ticker_data, investor_profile) -> CustomerBrief:
    raw = _build_raw_brief(ticker_data, investor_profile)
    result = validate_customer_output(raw)
    if result.status != "pass":
        raise ClaimBoundaryViolation(result.errors)
    return raw  # only reachable if validation passes
```

There is no `generate_customer_brief` that returns an unvalidated brief. The function signature enforces it. To get output you must pass the validator. This is structural — not a reminder to run the validator, not a downstream check.

**What this prevents:** a future code path, cron job, or helper lane generating a customer brief without validation. The prevention is in the function interface, not in developer discipline.

---

### 3.2 Freshness Hardness — Stale Data Cannot Appear as Current

**Current state:** Freshness is tracked (`evidence_freshness: "partial"` in the customer export) but it is a label on data, not a rendering gate. Stale data can still render as a normal brief entry with a label attached.

**Hard version — two-tier rendering:**

Every customer-visible item has an explicit freshness state that maps to a rendering class, not a string label:

| Freshness state | Customer rendering | Cannot produce |
|---|---|---|
| `fresh` (< 24h) | Full item with evidence | — |
| `degraded` (24h–72h) | Reduced item with visible staleness banner | Confident thesis language |
| `stale` (> 72h) | Item withheld or shown as "requires refresh" only | Any ticker-level claim |
| `missing` | Placeholder with explicit gap | Any populated field |

The rendering function accepts `freshness_state` as a required parameter. It has no branch for "render full item regardless of freshness." Stale data cannot produce a full-confidence output because the code path does not exist.

**What this prevents:** a customer receiving a watchlist brief that looks current but is built on 5-day-old data, because the cron that was supposed to refresh failed silently.

---

### 3.3 Claim-Boundary Hardness — Regulated-Advice Language Structurally Absent

**Current state:** The validator blocks strings like "buy now," "strong buy," "target price," and "expected return." This is the soft version — the fields could hold this language but the validator catches it.

**Hard version — schema-level exclusion:**

The customer output schema has no fields that can hold regulated-advice content:

```json
{
  "ticker": "ETN",
  "research_posture": "watch | review | no_chase | blocked",
  "evidence_freshness": "fresh | degraded | stale | missing",
  "plain_language_summary": "...",
  "key_risk_flags": [...],
  "evidence_gaps": [...],
  "disclosures": [...]
}
```

No `recommendation` field. No `action` field. No `target_price` field. No `expected_return` field. No `confidence_score` field. These fields do not exist in the schema; they cannot be serialized into a customer brief because there is nowhere to put them.

The validator then handles the rendered string layer as a second hardness tier — catching advisory language that slips into `plain_language_summary` or `key_risk_flags` as prose.

Two layers, both structural:
1. Schema cannot hold regulated-advice data types.
2. String validator cannot pass regulated-advice prose.

Together, these make the claim boundary hard rather than dependent on a single catch layer.

---

## 4. The One-Function Pattern

The practical implementation of all three hardness targets converges on the same architecture:

```
generate_validated_customer_output(input) -> output | raises
```

- Single entry point.
- Validation is not a separate step; it is part of the return type contract.
- The function either returns valid output or raises a typed exception — no third state.
- The caller cannot get output and then decide whether to validate.

This is the materials-science analog: the resistance is in the structure, not in a guard bolted on after manufacture.

Applied to the current `retail_saas_fixture_demo.py` / `retail_saas_customer_output_validator.py` split, the next implementation step is fusing the generation and validation into a single callable that enforces the contract at the type boundary.

---

## 5. Where Hardness Engineering Does Not Apply

Not every system property benefits from this approach. Over-hardening creates brittleness — a material that is maximally hard is also maximally brittle. Relevant examples in this workspace:

- **The WF73 boot-size guard uses a warning threshold, not a hard limit for all files.** Continuity notes are watch items, not hard failures, because they legitimately grow during active work. Hard limits on continuity notes would block useful work.
- **SQL fail-closed posture is correct for retail-grade SQL-first use but must not block the fallback path.** The system should be hard against SQL-first retail use while remaining soft (fallback-allowed) for the existing 265 approved metadata rows. Two different hardness levels for two different access paths.
- **Finance chain acceptance tests should be hard against false-green but soft against format changes.** A test that hardcodes specific ticker names in the "almost deployable" bucket will drift as the portfolio changes. The hard property is "no undetected false-green state," not "GOOG is always in the almost bucket."

The design principle: **harden against the failure mode you cannot afford, not against all change.** Hardness and adaptability are in tension. Pick the axis that matters.

---

## 6. Recommended Next Steps

| Step | What it hardens | Effort |
|---|---|---|
| Fuse `retail_saas_fixture_demo.py` and `retail_saas_customer_output_validator.py` into a single `generate_validated_customer_brief()` function | Structural guarantee: no customer output without passing validation | Small — refactor, not new code |
| Implement two-tier freshness rendering in customer output schema | Structural guarantee: stale data cannot render as current | Medium — schema change + renderer update |
| Remove `recommendation`/`action`/`target_price` fields from customer output schema at the JSON contract level | Structural guarantee: regulated-advice fields cannot be serialized | Small — schema edit |
| Rewrite `test_dashboard_acceptance.py::workflow8_command_center_alignment` to assert a property (no false-green undetected), not specific ticker names | Converts a soft drifting assertion into a hard invariant | Small — test rewrite |
| Wire `retail_saas_customer_output_validator.py` as a required gate in any cron/chain that generates customer-facing output | Structural guarantee: cron cannot skip validation | Medium — chain manifest update |

---

## 7. Authority Boundary

This document is analysis and design guidance only. It grants no app launch authority, no customer-data authority, no external delivery, no portfolio/canon mutation, no trade/account/brokerage/paper/live authority, and no owner approval inference. All retail SaaS build steps remain gated on the decisions identified in the 2026-05-29 workspace audit: legal/compliance counsel, source licensing, delivery channel, and service-vs-app architecture decision.

---

*End of report.*
