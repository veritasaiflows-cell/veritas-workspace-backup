# WF9B-12 Orchestration Prompt (Main-Session Controlled)

## Mission
Execute Workflow 9B, then Workflow 10, Workflow 11, and Workflow 12 sequentially to full closure quality.
After each workflow closure, run a bounded hardening pass before advancing.
Do not publish an executive summary until Workflows 9B, 10, 11, and 12 are all honestly complete.

## Authority and ownership
- Veritas main session is final orchestrator, QA owner, and queue-state owner.
- Helper lanes are allowed for read-only research, audits, contradiction checks, and proposal prep.
- Helper lanes must not move queue state, close workflows, or mutate canonical truth surfaces directly.

## Non-negotiable constraints
1. No silent canonical rewrites.
2. No fake-green closure.
3. No queue advancement without explicit verification evidence.
4. One active workflow at a time in the main sequence.
5. After each workflow closes, run a hardening pass and document residue ownership.

## Execution sequence
1. Workflow 9B - Surface alignment and drift-guard hardening
2. Hardening pass H1
3. Workflow 10 - Subagent/session lifecycle reliability review
4. Hardening pass H2
5. Workflow 11 - Coverage admission model
6. Hardening pass H3
7. Workflow 12 - Macro/policy trust repair
8. Hardening pass H4
9. Only then produce executive summary

## Per-workflow completion contract
For each workflow (9B/10/11/12):
- Define objective and exact in-scope deliverables
- Run read-only inventory first
- Prepare decision packet(s)
- Execute approved changes
- Run verification gates
- Record closure note + open residue map
- Run post-closure hardening pass

## Verification gates (minimum)
- Validator / acceptance checks relevant to the workflow
- File-level diff inspection for expected scope
- No unresolved critical contradictions in owner surfaces
- Queue/registry/continuity notes synchronized
- Named blockers either resolved or explicitly handed off

## Helper-lane protocol
- Use helper lanes only for:
  - read-only audits
  - contradiction tables
  - risk/challenge memos
  - implementation proposal drafts
- For every multi-lane pass:
  - define expected lanes up front
  - require completion handshake before synthesis
  - if one lane fails, retry once then fallback lane

## Hardening-pass contract (after each workflow)
Hardening pass must include:
1. Drift scan (queue/registry/continuity/owner surfaces)
2. Ownership-boundary check (no write-surface ambiguity)
3. Validation resilience check (warnings meaningful and non-noisy)
4. Residue classification:
   - fixed now
   - deferred with owner
   - out-of-scope but named

## Consolidation and redundancy cleanup
- Consolidation/shedding is not mixed into early truth-contract execution.
- Run as the last phase inside 9B (or separate bounded pass) per approved scope.
- Target redundancy clusters explicitly (orchestration docs, workbook/docs, legacy continuity duplicates, prompt/model-ops cluster) without doctrine sprawl.

## Done definition for this program
Program done only when:
- Workflow 9B complete + hardening pass H1 complete
- Workflow 10 complete + hardening pass H2 complete
- Workflow 11 complete + hardening pass H3 complete
- Workflow 12 complete + hardening pass H4 complete
- Residue map updated and trustworthy
- Executive summary prepared last
