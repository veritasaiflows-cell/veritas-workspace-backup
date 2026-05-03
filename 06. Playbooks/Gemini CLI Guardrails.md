# Gemini CLI Guardrails

## Purpose

Define the safe operating posture for Gemini CLI inside the Veritas OS.

This playbook exists because Gemini CLI now has:
- local workspace access
- local OAuth-backed credentials
- trusted-folder state
- multiple approval modes, including high-risk modes

The goal is to capture the useful leverage without casually widening risk.

## Current approved model posture

Approved Gemini CLI models:
- policy name: `gemini-3.1-pro`
  - verified CLI ID: `gemini-3.1-pro-preview`
  - alternate verified CLI ID: `gemini-3-pro-preview`
- policy name: `gemini-3-flash`
  - verified CLI ID: `gemini-3-flash-preview`

Explicitly not approved for normal Veritas OS use:
- `gemini-3.1-flash-lite-preview`
- `gemini-3.1-flash`
- any other Gemini variant unless explicitly added later

Important:
- the shorter policy names are useful for human routing
- the actual callable Gemini CLI model IDs on this machine are currently the verified preview IDs above

Reason:
- keep routing simple
- avoid quality drift from cheaper/lighter variants
- preserve a clear split between primary implementation lane and cheap bounded fallback lane

## Current trust-surface findings

Observed on 2026-05-01:
- Gemini CLI is installed and callable
- headless prompt execution works
- verified working model IDs:
  - `gemini-3.1-pro-preview`
  - `gemini-3-pro-preview`
  - `gemini-3-flash-preview`
- verified non-working attempted IDs:
  - `gemini-3-flash`
  - `gemini-3.1-flash`
- local Gemini config lives under `~/.gemini/`
- local OAuth credential storage exists in `~/.gemini/oauth_creds.json`
- current trusted folders include:
  - `C:/Users/Veritas.RQs_Business/.openclaw/workspace`
  - `C:/Users/Veritas.RQs_Business/Desktop/workspace`

### Immediate cleanup target

The active OpenClaw workspace should remain trusted.
The older desktop workspace trust should be removed if it is no longer intentionally used.

Why:
- stale trusted folders widen the accidental execution surface
- they create ambiguity about which workspace Gemini may safely operate in

## Default execution posture

Default Gemini CLI posture:
- Veritas owns Gemini routing and model selection
- headless, bounded prompts first
- explicit model selection
- current workspace only
- no broad autonomous edits by default

Preferred pattern:
- Veritas chooses whether Gemini Pro or Flash should be used
- use Gemini for a specific prompt
- constrain file scope when possible
- review results before promoting conclusions or applying changes

## Approval-mode rules

Allowed default posture:
- `--approval-mode plan`
- default approval mode when interactive review is desired

Exceptional posture:
- `--approval-mode yolo`
- `--yolo`

Use YOLO only when all of the following are true:
- model is `gemini-3.1-pro-preview` (or an explicitly approved Pro-equivalent)
- the task is bounded implementation work, not broad research or strategy
- Veritas intentionally routes the task into YOLO mode
- the target files and expected change surface are already clear
- the rollback path is straightforward

Do not use by default:
- `--approval-mode auto_edit`
- `--approval-mode yolo` for Flash
- `--yolo` for Flash

Reason:
- these remove too much friction for a workspace that contains meaningful state, automation logic, and credential-adjacent files
- YOLO may be justified for Pro on well-bounded implementation passes, but it is an explicit exception, not the baseline

## Workspace-trust rules

### Allowed
- `C:/Users/Veritas.RQs_Business/.openclaw/workspace`

### Review / remove unless intentionally needed
- `C:/Users/Veritas.RQs_Business/Desktop/workspace`

### Rule
Do not keep legacy or ambiguous trusted folders around "just in case."
Trust should match actively used workspaces only.

## Credential handling rules

Treat these as sensitive:
- `~/.gemini/oauth_creds.json`
- `~/.gemini/google_accounts.json`
- any future token or account files under `~/.gemini/`

Rules:
- do not paste contents into chat
- do not log contents in notes or memory
- do not broaden filesystem access to these files without a specific reason
- prefer least-privilege handling and avoid copying these files around

## Safe-use rules by model

### Gemini 3.1 Pro
CLI invocation note:
- prefer `gemini-3.1-pro-preview`
- `gemini-3-pro-preview` is also working here

Operator note:
- Veritas owns routing into Gemini Pro tasks
- YOLO may be used selectively on bounded implementation passes when Veritas explicitly chooses that posture

Use for:
- multi-file implementation
- bounded script changes
- validator and plumbing work
- larger-context repo understanding

### Gemini 3 Flash
CLI invocation note:
- use `gemini-3-flash-preview`

Operator note:
- Veritas owns routing into Gemini Flash tasks
- Flash remains a bounded audit/diagnosis lane and should not use YOLO posture

Use for:
- bounded audit passes
- contradiction checks
- stale-state verification
- narrow diagnosis after the contract is already defined

Do not use Flash for:
- broad OS-state synthesis
- first-pass architecture design
- canonical-state adjudication
- ambiguous trust or policy disputes

## Output-promotion rules

Gemini output is not canonical truth by itself.

Promotion boundary:
- diagnosis may justify a human-reviewed implementation task
- useful findings may justify a Claude or Veritas judgment pass
- raw Gemini output should not directly rewrite canonical notes or stateful config without review

## Current recommended cleanup plan

### Read-only conclusion
Recommended next trust cleanup:
1. remove `C:/Users/Veritas.RQs_Business/Desktop/workspace` from Gemini trusted folders if no longer intentionally used
2. keep only the active OpenClaw workspace trusted
3. continue using only `gemini-3.1-pro` and `gemini-3-flash`
4. keep Gemini in bounded/headless mode by default

### Requires explicit approval before changing
- editing Gemini trusted-folder state
- altering Gemini settings files
- changing local credential handling or filesystem permissions

## Durable rule

Gemini CLI is an implementation tool and bounded audit tool inside Veritas OS.
It is not a free-roaming autonomous agent.
Veritas routes Gemini work; Randall handles Claude prompting and reporting directly.
