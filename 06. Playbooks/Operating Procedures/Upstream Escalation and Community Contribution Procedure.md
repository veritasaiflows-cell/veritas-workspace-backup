# Upstream Escalation and Community Contribution Procedure

## Retrieval Notes
- Type: procedure
- Status: active
- Owner surface: `skills/openclaw-troubleshooter/SKILL.md` (diagnosis), this procedure (escalation)
- Authority: procedure
- Workflow: none
- Key entities: OpenClaw upstream, GitHub issues, Windows portability, local findings, `gh`
- Source freshness: 2026-09-21 first filed escalation (#155478)
- Next action: use when a verified local finding is a genuine upstream defect; record in the register
- Archive posture: permanent-reference
- Tags: #veritas/runtime #status/active #retrieval/escalation

## Purpose
Turn a verified local OpenClaw finding into a useful upstream contribution without filing noise,
duplicating closed work, or overstating severity. Keep the loop durable so Windows/runtime challenges
found here benefit the community and eventually come back as upstream fixes.

## Relationship to the diagnosis lane
`openclaw-troubleshooter` owns finding the real failure point. This procedure owns what happens when the
failure point turns out to be in OpenClaw itself rather than in local config, environment, or the user's
setup. Do not escalate before the diagnosis lane has separated those buckets.

## Trigger
Escalate when all of these hold:
- the finding is reproduced and attributed with measurement, not inference
- the mechanism is visible in installed OpenClaw code (or docs), not guessed
- it is not caused by local config, PATH, credentials, a deliberate user choice, or a stale note
- it would plausibly affect other users on a similar platform or setup

Do not escalate when the finding is local-only, already explained by an owner note, or still speculative.

## Procedure

1. **Verify locally before writing anything.**
   Reproduce the symptom, measure it, and read the actual code path in the installed build
   (`dist/**`) rather than trusting an index, an old audit, or a memory note. Separate symptom from
   mechanism: state the cost term, not just the visible slowness. Record the environment
   (OpenClaw version, OS build, Node version, index/store size).
   *Completion: a measurement table and a named code path exist.*

2. **Rule out local amplifiers.**
   Before blaming OpenClaw, explicitly test the usual suspects and say which you eliminated
   (antivirus/Defender state, PATH/wrapper shims, disk pressure, model/provider warmth, config drift).
   An unexamined amplifier makes the report weak.
   *Completion: each plausible local cause is either eliminated with evidence or named as unproven.*

3. **Run the duplicate check BEFORE drafting.** This step is the one most often skipped.
   ```powershell
   gh search issues --repo openclaw/openclaw "<symptom keywords>" --limit 10 --json number,title,state
   gh search prs    --repo openclaw/openclaw "<keywords>"         --limit 10 --json number,title,state
   ```
   If you find a closed issue, do not stop at the title. Read the fix:
   ```powershell
   gh api repos/openclaw/openclaw/issues/<n> --jq ".state,.state_reason,.closed_at"
   gh api repos/openclaw/openclaw/issues/<n>/timeline   # find the fixing PR
   gh api repos/openclaw/openclaw/pulls/<pr>/files --jq ".[].filename"
   ```
   Then answer two questions in writing:
   - is the fix present in my installed build?
   - if present, does it address my specific term, or a different term?
   *Completion: the finding is classified as NEW, PARTIALLY-FIXED, or ALREADY-FIXED, with the
   predecessor issue/PR numbers recorded.*

4. **Choose the frame from that classification.**
   - NEW → open a new issue
   - PARTIALLY-FIXED → open a new issue and cite the predecessor PR as prior work
   - ALREADY-FIXED → do not file; record it in the register as closed-by-upstream and re-test on the
     next release
   Never post into a closed thread expecting triage. Closed issues rarely re-enter the queue; a
   closed-but-unfixed residual needs its own issue referencing the predecessor.

5. **Write the body to a file, then pass the file.** PowerShell mangles inline JSON and long quoted
   bodies. Draft to a file and use `--body-file`.
   ```powershell
   gh issue create --repo openclaw/openclaw --title "<title>" --body-file "<path to body.md>"
   ```
   Include, in this order: environment table; repro steps a stranger can run; expected vs actual;
   the measurement/attribution table; the predecessor-work section; then asks in priority order.
   *Completion: the body stands alone for a reader with none of your context.*

6. **State severity honestly, including platform dependence.**
   If the cost is Windows process creation, Windows path behavior, or a WSL/PowerShell interaction,
   say so plainly and note the likely smaller impact on Linux/macOS. Let upstream judge severity with
   correct information rather than an inflated one. Name what you did *not* prove.

7. **Ask for owner approval before any public action.** Filing, commenting, and reacting are external
   actions under `AGENTS.md`. Prepare everything, then wait for an explicit yes. Do not treat a
   pre-existing owner-allowlisted channel as authority to post publicly.

8. **File, then verify the result.**
   ```powershell
   gh issue view <n> --repo openclaw/openclaw --json number,title,state,url,labels
   ```
   Confirm the issue is OPEN and attributed correctly. A returned URL is not proof the body rendered.

9. **Record it in the register** (see below) with number, state, next action, and a follow-up date.
   *Completion: the escalation is trackable without reading this conversation.*

10. **Close the loop.** Re-test on new releases; report a fixed/regressed/unmoved verdict back to
    Randall. A filed issue with no follow-up is not a finished contribution.

## The register
Every escalation gets one row in `06. Playbooks/Project Continuity/Upstream Escalation Register.md`:
issue number, title, state, severity frame, predecessor work, next action, follow-up date. Update the
row when upstream responds or a release changes the answer.

## Do not
- **Do not patch `node_modules` locally.** Any `openclaw update` destroys it, and an unversioned local
  edit misrepresents the finding. Route it upstream or leave it documented.
- Do not file before the duplicate check, even when the symptom feels novel.
- Do not claim a universal impact for a platform-specific cost.
- Do not include secrets, tokens, account data, private paths beyond what the report needs, or session
  content in an issue body.
- Do not restate an old audit as a new finding; re-measure or say it is unverified.

## Proof standard
An escalation is complete when: the issue URL exists and is OPEN; the register row is updated; the
body contains repro steps and a measurement table; and the severity frame names its platform
dependence. Filing alone is not completion — the follow-up verdict is.

## Stop lines
- Duplicate check not done → stop, do not file.
- Owner approval absent → stop before any public action.
- Finding still speculative or locally explained → return to the diagnosis lane.
- A local patch would be needed to reproduce → say so; do not ship a patched reproduction as clean.
