# Cron Job Retrofit Checklist

## Purpose
Use this checklist to compare live sibling cron jobs against `06. Playbooks/Cron Job Protocol.md` before claiming they are honestly hardened.

## Retrofit checklist
For each live job, verify all of these:
1. **Name** follows the sibling naming pattern
2. **Window family** is explicit
3. **Schedule / timezone** is explicit and correct
4. **Session target** is explicit and justified
5. **Owner** is explicit
6. **Trigger goal** is explicit
7. **Read first** names exact files in priority order
8. **Execute in order** names exact commands/scripts in order
9. **Inspect after execution** names exact artifacts/proofs
10. **Response contract** is explicit and uses the required fields
11. **Spawn recommendation** is explicit
12. **Inputs read** are bounded
13. **Writable surfaces** are bounded
14. **Delivery mode** is explicit and matches reality
15. **Trust grade** is explicit
16. **Validation proof** is explicit
17. **Stop line** is explicit
18. **Escalation path** is explicit
19. **Overlap owner** is explicit
20. **Sibling symmetry** is intact unless a real exception is documented

## Current live finance sibling review (2026-05-04)

### 1. Finance Refresh - Pre-Market
- **Schedule / timezone**: pass (`0 6 * * 1-5`, `America/Phoenix`)
- **Session target**: pass (`isolated`)
- **Delivery mode**: pass (`none`, internal-only proof)
- **Payload contract before retrofit**: fail - prompt was outcome-oriented but did not name exact read-first files, exact execution order, inspect-after artifacts, spawn recommendation, out-of-bounds surfaces, or stop lines
- **Retrofit priority**: high
- **Required window proofs**:
  - `tmp/run-summary-morning.json`
  - `tmp/dashboard-validation.json`
  - `tmp/dashboard-acceptance-report.json`
  - `tmp/deployment-check.json`
  - `tmp/veritas-command-center.html`
  - `tmp/workbook-export-manifest.json`

### 2. Finance Refresh - Post-Close
- **Schedule / timezone**: pass (`20 13 * * 1-5`, `America/Phoenix`)
- **Session target**: pass (`isolated`)
- **Delivery mode**: pass (`none`, internal-only proof)
- **Payload contract before retrofit**: fail - same contract gaps as pre-market
- **Retrofit priority**: high
- **Required window proofs**:
  - `tmp/run-summary-post-close.json`
  - `tmp/dashboard-validation.json`
  - `tmp/dashboard-acceptance-report.json`
  - `tmp/post-earnings-prep.json`
  - `tmp/post-earnings-note-targets.json`
  - `tmp/veritas-command-center.html`
  - `tmp/workbook-export-manifest.json`

### 3. Finance Refresh - Sunday Weekly
- **Schedule / timezone**: pass (`0 9 * * 0`, `America/Phoenix`)
- **Session target**: pass (`isolated`)
- **Delivery mode**: pass (`none`, internal-only proof)
- **Payload contract before retrofit**: fail - same contract gaps as sibling jobs
- **Retrofit priority**: high
- **Required window proofs**:
  - `tmp/run-summary-sunday.json`
  - `tmp/weekly-macro-snapshot.json`
  - `tmp/weekly-intelligence-brief.json`
  - `tmp/veritas-command-center.html`
  - `tmp/workbook-export-manifest.json`

## Cross-sibling findings
- Schedules, timezones, isolated-session posture, and internal-only delivery are already symmetrical.
- The real gap is the **run packet / response contract layer**, not the schedule layer.
- All three jobs need explicit read-first, execute-in-order, inspect-after, response-contract, spawn, out-of-bounds, and stop-line wording in the payload itself.
- No sibling currently needs a schedule or delivery-mode change to satisfy WF24.

## Retrofit order
1. patch all three payload prompts to the explicit run-packet format
2. verify live cron definitions still show the intended schedule/session posture
3. confirm the next run history and workspace artifacts match the new proof contract
4. only then treat WF24 Phase 3 as honestly advanced

## Notes
- Delivery preview may still show fail-closed routing details because these jobs use `delivery.mode = none`; that is acceptable under the current internal-only proof posture and is not a blocker by itself.
- This checklist hardens the build contract and sibling symmetry. It does not authorize autonomy widening.
