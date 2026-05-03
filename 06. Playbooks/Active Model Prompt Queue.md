# Active Model Prompt Queue

Use this file to decide what to run next.

## Status key
- `ready` = run now if using that model
- `hold` = valid, but not current priority
- `done` = completed for the current cycle
- `stale` = revise before reuse

## Current queue

### 1) Gemini Flash — machine-state workflow-state verification
- Status: `ready`
- Why now: bounded, cheap, and directly relevant to current machine/note lag
- Save output to: `tmp/external-research/2026-05-01 Workflow-State Verification - Gemini Flash.md`
- Prompt source: `06. Playbooks/Gemini Flash Prompt Pack.md`
- Exact prompt:

```text
You are doing a bounded machine-state verification pass for Veritas OS.

Focus only on these files:
- tmp/portfolio-config.json
- scripts/trigger_sheet_refresh.py
- scripts/deployment_check.py
- tmp/deployment-check.json
- tmp/trigger-sheet.json
- tmp/dashboard-validation.json

Context:
Recent judgment now supports:
- MSFT = Almost Deployable
- XOM = Watch
Recent diagnosis suggests stale workflow_state values in portfolio-config.json are overriding fresher machine logic.

Your job:
Verify whether stale workflow_state values in portfolio-config.json are the exact reason trigger-sheet outputs still lag reality for MSFT, GOOG, and AMZN.

Questions:
1. What are the current workflow_state values in portfolio-config.json for:
   - MSFT
   - GOOG
   - AMZN
   - GS
2. Where exactly does trigger_sheet_refresh.py enforce those workflow_state values over deployment-check results?
3. For each of MSFT, GOOG, and AMZN, is the current blocked/contradictory state caused by:
   - stale workflow_state in config
   - earnings-window logic
   - summary-generation logic
   - some other path
4. If workflow_state is the blocker, what is the smallest safe reconciliation action?
5. Do not change anything. Diagnosis only.

Output format:
## Config state
- MSFT:
- GOOG:
- AMZN:
- GS:

## Enforcement path
- function(s):
- rule order:
- artifact effect:

## Per-name root cause
- MSFT:
- GOOG:
- AMZN:

## Smallest safe next action
- one bounded recommendation only

Rules:
- no broad strategy
- no note-layer advice
- no code patch yet
- cite keys, function names, and field names when possible
```

### 2) GPT5.4 Research — XOM geopolitical / earnings risk pass
- Status: `ready`
- Why now: useful external context, cheap, and separate from workspace debugging
- Save output to: `tmp/external-research/2026-05-01 XOM Post-Earnings Risk Pass - GPT5.md`
- Prompt source: `06. Playbooks/GPT5 Research Prompt Pack.md`
- Exact prompt:

```text
Do a decision-grade external research pass on Exxon after its May 1 2026 earnings report.

Focus on:
- quality of the quarter
- oil macro sensitivity
- Hormuz / Middle East production risk
- whether the stock deserves requalification toward a constructive setup or should remain watch-only
- strongest bull and bear arguments from credible public sources

Output:
1. Core verdict
2. Bull case
3. Bear case
4. What is new after earnings
5. What would justify a more constructive stance

Use current public web sources. Be direct and evidence-based.
```

### 3) Claude Sonnet — cross-project synthesis after machine verification
- Status: `hold`
- Why hold: wait until the next Flash verification pass clarifies the machine-side blocker
- Save output: optional; Claude remains an interactive lane
- Prompt source: custom bounded judgment pass

### 4) Gemini Pro — bounded implementation fix after diagnosis
- Status: `hold`
- Why hold: wait until the stale workflow_state diagnosis is confirmed cleanly
- Save output: optional; Gemini Pro remains an interactive lane

## Queue maintenance rule

After a prompt is run and reviewed:
- change `ready` -> `done` if complete
- change `ready` -> `stale` if the prompt framing proved wrong
- promote a `hold` item to `ready` only when the dependency above it is resolved
