# Gemini Flash Prompt Pack

## Purpose

Use Gemini Flash as a cheap bounded workspace worker.
It is useful when the contract is already clear and the task is narrow.
It is not the default model for broad strategic synthesis in a continuity-heavy workspace.

## Best-fit task types

- artifact contradiction audit
- record-vs-summary coherence check
- file-level blame mapping
- bounded validator review
- narrow implementation diagnosis
- mechanical follow-up after Gemini Pro or Veritas has already defined the contract

## Output-saving convention

Save raw outputs to:
- `tmp/external-research/YYYY-MM-DD <topic> - Gemini Flash.md`

## Prompt 1 — artifact contradiction audit

```text
You are doing a bounded machine-state audit inside Veritas OS.

Read only these files:
- [ARTIFACT 1]
- [ARTIFACT 2]
- [ARTIFACT 3]
- [ARTIFACT 4]

Instructions:
- do not summarize the whole workspace
- do not infer project phase from older notes
- do not propose broad architecture changes
- focus only on contradictions visible in the listed artifacts

Output:
## Findings
- bullet list of concrete contradictions only

## Highest-priority contradiction
- one item only

## Smallest next fix
- one bounded recommendation only
```

## Prompt 2 — stale-state verification

```text
You are doing a bounded state-verification pass.

Focus only on:
- [CONFIG FILE]
- [SCRIPT FILE 1]
- [SCRIPT FILE 2]
- [ARTIFACT FILE 1]
- [ARTIFACT FILE 2]

Goal:
Verify whether a stale config/state field is overriding fresher machine logic.

Questions:
1. What are the current values of the relevant state fields?
2. Where exactly are those fields enforced in code?
3. What artifact effect do they produce?
4. What is the smallest safe next action?

Rules:
- diagnosis only
- no code patch
- no broad strategy
- cite keys, function names, and field names when possible
```

## Prompt 3 — file-level blame mapping

```text
You are doing a bounded diagnosis pass.

Focus only on these files:
- [SCRIPT FILE 1]
- [SCRIPT FILE 2]
- [SCRIPT FILE 3]
- [CURRENT ARTIFACT]

Goal:
Identify where a contradiction originates.

Output:
## Root causes
- one bullet per contradiction

## File-level blame
- file 1:
- file 2:
- file 3:

## Smallest bounded next fix
- one recommendation only

Rules:
- do not rewrite the architecture
- do not discuss project history unless directly needed
```

## Prompt 4 — validator-only review

```text
Review only the validator/gate logic in these files:
- [VALIDATOR 1]
- [VALIDATOR 2]
- [RELATED ARTIFACT]

Goal:
Determine whether the validator is truthfully reflecting current machine state or creating false warning noise.

Output:
1. truthful warnings
2. possibly stale / misleading warnings
3. one smallest next improvement

Rules:
- validator scope only
- no full workspace summary
```

## Prompt 5 — narrow implementation handoff prep

```text
You are preparing a bounded implementation handoff.

Read only:
- [FILES]

Goal:
Convert the current contradiction into a precise implementation task for a stronger coding model.

Output:
## Problem statement
## Exact files involved
## Relevant functions / keys
## Smallest implementation target
## Risks if changed incorrectly

Rules:
- no patch
- no broad synthesis
- keep it concrete
```

## Prompt 6 — what not to do

```text
Do NOT:
- summarize the whole OS state
- infer the current project phase from old continuity files
- restate already-fixed broad architecture problems as if they are current next steps
- propose major strategy changes when the prompt is only about artifacts or code
```

## Usage notes

- give Flash tightly scoped file lists
- prefer artifact-first prompts
- keep asks bounded to one contradiction family at a time
- use Flash outputs as reviewable inputs, not direct authority
- escalate to Gemini Pro when multi-file implementation is actually needed
