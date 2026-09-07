# WF74 ClawHub RSI inspection queue

- Generated: 2026-05-24T05:52:54Z
- Status: review queue only / no installs
- First batch goal: design WF74's evaluation harness.

## Candidates

| skill | batch | priority | status | reason | decision_bias |
|---|---|---|---|---|---|
| agent-evaluation | 1 | P0 | inspect_first | Most directly aligned with WF74 evaluation harness and regression metrics. | extract_patterns_not_install |
| agent-qa-gates | 1 | P0 | inspect_first | Potentially useful for pre-final gates: hallucinated data, leaked context, wrong format, duplicate sends, post-compaction drift, boundary errors. | extract_patterns_not_install |
| openclaw-self-improvement | 2 | P1 | inspect_after_evaluators | Likely relevant to OpenClaw-native workflow improvement, but overlap with veritas-self-improvement must be controlled. | inspect_extract_or_reject |
| actual-self-improvement | 2 | P1 | inspect_after_evaluators | May contain durable lesson capture patterns for debugging/corrections/friction. | inspect_extract_or_reject |
| agent-scorecard | 3 | P2 | optional_inspect | Could inform a weekly Veritas quality scorecard if evaluator skills are insufficient. | optional_extract |
| recursive-self-improvement | 99 | reject_by_default | reject_or_sandbox_only | Name and described scope suggest broad autonomous repair/optimization patterns that are unsafe for Veritas without sandbox review. | reject |

## Inspection gates

- read metadata/docs only before any install decision
- reject or extract patterns if skill creates duplicate memory/doctrine/control surface
- reject if it implies autonomous config/auth/runtime mutation or authority expansion
- prefer patching existing Veritas-native skills/procedures over installing overlapping skills
