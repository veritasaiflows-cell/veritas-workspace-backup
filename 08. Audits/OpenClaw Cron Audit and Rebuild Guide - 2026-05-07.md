# OpenClaw Cron Audit and Rebuild Guide - 2026-05-07

## Bottom line
The scheduler is live and enabled, with **6 current cron jobs** persisted at `C:\Users\Veritas\.openclaw\cron\jobs.json`.

The cron layer is **not uniformly green** right now:
- the control-plane preflight job is working fail-closed
- the finance-window layer is mixed
- two jobs still have **zero run history** on their current live definitions
- one job recently stopped for **exec approval**, which means a reinstall can easily break scheduled execution if durable approvals are lost

This is usable, but it is not a “set it and forget it” surface.

---

## Live scheduler state
- **Cron enabled:** yes
- **Job store:** `C:\Users\Veritas\.openclaw\cron\jobs.json`
- **Live job count:** 6
- **Delivery posture:** internal-only / `delivery.mode = none`
- **Default session target for all 6 current jobs:** `isolated`

Implication:
- these jobs do **not** depend on Telegram, Discord, or other chat-channel delivery plugins
- proof comes from **cron run history + workspace artifacts**, not routed messages

---

## Current live cron inventory

### 1. Finance Refresh - Pre-Market
- **Job ID:** `10ed843b-9c2d-4fd1-a162-ca6e4c21c0a6`
- **Schedule:** `0 6 * * 1-5` (`America/Phoenix`)
- **Owner command:** `python scripts\run_finance_refresh_chain.py morning`
- **Tools allowed:** `exec`, `read`
- **Current reality:** latest scheduled run on 2026-05-07 finished fail-closed in the summary because the owner proof surface was contradictory before the later manual repair.
- **Audit verdict:** job definition is valid, but the latest **scheduled** proof is still not a clean green proof for the current live definition.

### 2. Finance Refresh - Post-Close
- **Job ID:** `f2fd65c3-29b9-49d8-ab32-8e7ea347297e`
- **Schedule:** `20 13 * * 1-5` (`America/Phoenix`)
- **Owner command:** `python scripts\run_finance_refresh_chain.py post-close`
- **Tools allowed:** `exec`, `read`
- **Current reality:** latest scheduled run on 2026-05-07 reported fail-closed / not complete because `tmp/run-summary-post-close.json` stayed blocked/stale while later artifacts existed.
- **Audit verdict:** live job exists and fires, but the truth surface for this window is currently degraded and should not be treated as fully clean.

### 3. Finance Refresh - Sunday Weekly
- **Job ID:** `0718a128-3abf-4322-920b-e693041a7de4`
- **Schedule:** `0 9 * * 0` (`America/Phoenix`)
- **Owner command:** `python scripts\run_finance_refresh_chain.py sunday`
- **Tools allowed:** `exec`, `read`
- **Current reality:** current live definition has **zero run-history entries**.
- **Audit verdict:** configured, but not currently re-proved on the present job definition.

### 4. Finance Refresh - Post-Earnings Catch-up
- **Job ID:** `73b6fb43-2b71-45e6-948f-b1a23dc51a7d`
- **Schedule:** `30 15 * * 1-5` (`America/Phoenix`)
- **Owner command:** `python scripts\run_finance_refresh_chain.py post-earnings`
- **Tools allowed:** `exec`, `read`
- **Current reality:** latest run on 2026-05-07 stopped at an **approval request** (`/approve 9a2b71c8 allow-once`). Prior clean autonomy is therefore not safe to assume.
- **Audit verdict:** job exists, but scheduled autonomy is brittle until exec approvals are verified after reinstall.

### 5. Workflow Queue - Sequential Advancement Preflight
- **Job ID:** `39ae017c-3c2e-4567-846e-22a2a2a24dc9`
- **Schedule:** `0 2,14 * * *` (`America/Phoenix`)
- **Owner action:** control-plane fail-closed workflow preflight
- **Tools allowed:** `read`, `edit`, `write`, `exec`
- **Current reality:** latest run stayed honest and left WF38 **in-progress**.
- **Important drift:** the payload still contains a stale hardcoded intended order (`WF31 -> WF26 -> WF22`), but the live run correctly overrode that by checking current files first.
- **Audit verdict:** functionally healthy and fail-closed, but the embedded prompt should be refreshed so the packet matches live workflow order again.

### 6. Workspace Audit - Governor
- **Job ID:** `dc1fa262-a841-446d-a7ab-d3753f2f6d6d`
- **Schedule:** `30 11 * * 2,5` (`America/Phoenix`)
- **Owner action:** bounded workspace-governor audit
- **Tools allowed:** `read`, `write`, `edit`, `exec`
- **Current reality:** current live definition has **zero run-history entries**.
- **Audit verdict:** configured, but still needs first current-definition proof.

---

## What must exist for these jobs to work

### Core runtime
1. **OpenClaw Gateway with cron enabled**
2. **Cron job store present** at `C:\Users\Veritas\.openclaw\cron\jobs.json`
3. **Workspace root unchanged** at `C:\Users\Veritas\.openclaw\workspace`
4. **Python available on PATH** as `python`
5. **Cron runs allowed to use `exec`**
6. **Durable exec approvals preserved** when a scheduled chain needs them

### Python packages required by the current script surface
Minimum supported dependencies from `scripts/README.md`:
```bash
pip install yfinance tzdata
```

Optional but useful for richer report/output flows:
```bash
pip install python-docx pillow
```

Why these matter:
- missing `yfinance` previously broke the morning chain hard
- missing `tzdata` previously broke timezone-dependent consumers (`America/New_York` resolution) and left cron runs in blocked / contradictory states

### Skills / operator surfaces to verify
`openclaw skills check` currently reports the skill layer healthy.
Most relevant visible skills for cron recovery are:
- `cron-automation-manager`
- `openclaw-operator`
- `openclaw-troubleshooter`
- `workspace-governor`
- `memory-continuity-manager`

Important note:
- this host currently reports **33 visible/eligible skills** and **0 missing requirements**
- if a reinstall breaks plugin-skill linking on Windows, check symlink privilege / Developer Mode before assuming the skill is missing

### Plugins / routing to check
Current cron jobs do **not** depend on Telegram or Discord delivery.
That is intentional.

Check these instead:
- **Codex / model runtime route** is still usable for isolated agentTurn jobs
- **plugin-skills linking** still works after reinstall
- **channel plugins remain intentionally disabled** unless you are deliberately widening scope again

Do **not** waste time reinstalling Telegram/Discord just to fix cron. These jobs are internal-only.

---

## Rebuild / recovery order after reinstall

### Phase 1 - prove the runtime first
1. Run `openclaw skills check`
2. Run `cron status`
3. Run `cron list`
4. Confirm the scheduler is enabled and the job count is still **6**
5. Confirm `C:\Users\Veritas\.openclaw\cron\jobs.json` still contains the six expected job IDs

If `openclaw status` hangs or is noisy during reinstall:
- do **not** assume the runtime is healthy just because the process exists
- fall back to `cron status`, `cron list`, skills check, and artifact proof
- during this audit, `openclaw status` did not return cleanly, so it should not be treated as the sole health gate

### Phase 2 - prove Python and script dependencies
Run:
```bash
python --version
python -c "import yfinance, tzdata; print('deps ok')"
```

If that fails, fix Python/deps before touching cron definitions.

### Phase 3 - prove exec approval posture
Check whether scheduled chain commands still have the approvals they need.
The important durable file is:
- `C:\Users\Veritas\.openclaw\exec-approvals.json`

Reason:
- at least one current cron job (`Finance Refresh - Post-Earnings Catch-up`) recently stopped for approval instead of completing
- reinstall/update can wipe or invalidate the narrow approvals that keep scheduled runs autonomous

### Phase 4 - prove the job definitions are still real
For each job, verify:
- name
- schedule
- timezone
- session target = `isolated`
- delivery mode = `none`
- payload still contains the expected run packet

The rebuild source of truth is:
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Cron Run Ledger.md`
- `C:\Users\Veritas\.openclaw\cron\jobs.json`
- this audit note

### Phase 5 - controlled proof runs
Best order:
1. `Workflow Queue - Sequential Advancement Preflight` - safest fail-closed control-plane check
2. `Workspace Audit - Governor` - bounded audit-only check
3. `Finance Refresh - Sunday Weekly` - controlled weekend proof for the weekly finance lane
4. `Finance Refresh - Pre-Market`
5. `Finance Refresh - Post-Close`
6. `Finance Refresh - Post-Earnings Catch-up`

Do not call the layer healthy just because the jobs exist.
Proof means:
- a real cron run exists in history
- required artifacts are fresh
- the run summary tells the truth
- no material contradiction remains between summary and downstream artifacts

---

## If a cron job disappears after reinstall
Use this order:
1. check `cron status`
2. check `cron list`
3. inspect `C:\Users\Veritas\.openclaw\cron\jobs.json`
4. if the file is empty/missing/stale, rebuild the jobs from this audit + the live protocol docs
5. after recreate, do **not** stop at creation; run proof and inspect artifacts

The six current jobs to recreate are exactly:
- `Finance Refresh - Pre-Market`
- `Finance Refresh - Post-Close`
- `Finance Refresh - Sunday Weekly`
- `Finance Refresh - Post-Earnings Catch-up`
- `Workflow Queue - Sequential Advancement Preflight`
- `Workspace Audit - Governor`

---

## If a cron job runs but produces bad truth
Use these failure classes.

### A. Missing dependency failure
Symptoms:
- `ModuleNotFoundError`
- timezone resolution errors
- early-chain hard fail

Fix:
- reinstall `yfinance` and `tzdata`
- rerun a controlled proof only after the imports work

### B. Approval failure
Symptoms:
- cron run summary is just an `/approve ... allow-once` request
- scheduled job did not actually do the work

Fix:
- repair the exact durable approval posture
- do not broaden approvals more than needed
- re-prove the job after approval is restored

### C. Stale-summary / fresh-artifact contradiction
Symptoms:
- downstream files are fresh
- run summary is stale, blocked, or contradictory
- chain looks done but proof surface is not trustworthy

Fix:
- trust the contradiction and fail closed
- inspect the chain/finalizer ordering and the exact artifact writer that drifted
- do not mark the window green just because some outputs refreshed

### D. Prompt drift inside the job payload
Symptoms:
- job still runs, but embedded assumptions are stale
- current example: the queue-preflight job still names an old workflow order in its prompt packet

Fix:
- update the payload contract to match live control-plane truth
- keep file-first validation as the safety backstop

### E. Zero-run current-definition jobs
Symptoms:
- job exists, but `cron runs` returns no entries for the current job ID

Fix:
- treat the definition as unproved
- do one controlled run when safe
- inspect artifacts before calling it healthy

---

## What I learned and want kept durable
1. **Cron creation is not proof.** The job is only real after run history and artifacts agree.
2. **Internal-only delivery is fine if it is explicit.** These jobs do not need chat plugins to be healthy.
3. **`yfinance` and `tzdata` are not optional here.** Missing either can make the finance layer lie by accident.
4. **Exec approvals are part of runtime readiness.** A reinstall can quietly break scheduled autonomy without touching the job definitions.
5. **Run-summary truth matters as much as script success.** We already had a real morning-window bug where the chain finished but the summary surface lied about terminal state.
6. **Fail-closed is working and should stay working.** Several recent runs correctly refused to claim success from contradictory state.
7. **Prompt packets drift.** Even when the fail-closed logic saves you, stale embedded workflow assumptions should still be cleaned up.
8. **Two current jobs are configured but not currently re-proved** on the live definitions: Sunday Weekly and Workspace Audit - Governor.
9. **A reinstall/update is exactly when historical assumptions go bad.** Recheck the live scheduler, skills, approvals, and Python deps instead of trusting notes alone.

---

## Immediate recommended next actions after the reinstall settles
1. verify `cron status` and `cron list`
2. verify `openclaw skills check`
3. verify Python + `yfinance` + `tzdata`
4. verify `exec-approvals.json`
5. run a controlled proof for:
   - `Finance Refresh - Sunday Weekly`
   - `Workspace Audit - Governor`
6. then re-prove the degraded finance siblings, especially:
   - `Finance Refresh - Pre-Market`
   - `Finance Refresh - Post-Close`
   - `Finance Refresh - Post-Earnings Catch-up`
7. refresh the queue-preflight payload so its embedded workflow order matches current live control-plane truth again

## Honest current verdict
The cron layer is **present and partially healthy**, but **not fully re-proved** for the current live definitions.

What is solid:
- scheduler enabled
- six jobs present
- skill layer currently healthy
- internal-only delivery posture is intentional
- fail-closed behavior is still catching bad states instead of inventing success

What is not yet solid:
- Sunday Weekly proof on the current job ID
- Workspace Governor proof on the current job ID
- post-close truth-surface cleanliness
- post-earnings approval continuity
- payload freshness on the workflow-preflight cron
