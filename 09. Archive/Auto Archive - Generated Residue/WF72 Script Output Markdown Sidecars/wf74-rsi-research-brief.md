# WF74 RSI research brief

- Generated: 2026-05-24T05:52:54Z
- Status: review_ready

## Bottom line

Research supports bounded critique-revise-evaluate-retain loops, not open-ended autonomous self-modification.

## Proven / useful patterns

- bounded self-feedback can improve individual outputs when evaluation is explicit
- reflection memory helps when tied to concrete failures and curated retention
- separate evaluator/auditor roles reduce overreliance on single-agent self-assessment
- tests, rollback, and QA are mandatory before code/skill/procedure changes are treated as improvements

## Speculative or risky patterns

- open-ended recursive self-improvement without external gates
- agents editing their own authority, prompts, config, tools, or memory without independent review
- benchmark-only improvement claims transferred into finance/workspace reliability
- reflection as substitute for validation/provenance/source freshness

## Sources and implications

### Self-Refine: Iterative Refinement with Self-Feedback
- URL: https://arxiv.org/abs/2303.17651
- Finding: Bounded self-feedback and revision can improve outputs across tasks without model training; this supports critique/revise/evaluate loops, not autonomous self-modification.
- WF74 implication: Use structured self-critique only when paired with explicit evaluation and retention rules.

### Reflexion: Language Agents with Verbal Reinforcement Learning
- URL: https://proceedings.neurips.cc/paper_files/paper/2023/file/1b44b878bb782e6954cd888628510e90-Paper-Conference.pdf
- Finding: Agents can improve across repeated attempts by storing natural-language reflections from concrete failures when feedback is available.
- WF74 implication: Store only evidence-backed lessons with destination, proof, and review status; avoid memory dumping.

### RISE / Recursive Introspection
- URL: https://arxiv.org/html/2407.18219v2
- Finding: Multi-turn introspection with reward/evaluation signals can improve reasoning in trained/evaluated settings; it is not a prompt-only guarantee.
- WF74 implication: Evaluator quality matters more than reflection volume; build an evaluation harness before calling RSI durable.

### Self-Improving Coding Agent
- URL: https://arxiv.org/html/2504.15228v2
- Finding: Code-modifying agents can improve benchmark scores, but benchmark gains do not prove safety, generality, or suitability for finance/workspace authority.
- WF74 implication: Code/skill changes require tests, rollback, independent QA, and no authority widening.

### LLM Agent Memory Survey
- URL: https://arxiv.org/html/2404.13501
- Finding: Memory is central to agent improvement but creates risks: stale/false memory, retrieval errors, contamination, and evaluation difficulty.
- WF74 implication: Keep Veritas memory curated through existing memory/continuity surfaces; do not create a second memory tree.

### LLM Agent Evaluation Survey
- URL: https://arxiv.org/abs/2503.16416
- Finding: Reliable agents need task-specific evaluation, regression checks, and behavior metrics; generic self-assessment is insufficient.
- WF74 implication: Build fixtures from real Veritas failures: stale claims, boundary errors, missing proof, bad memory routing, and overbroad helper use.

### OWASP GenAI / LLM Top 10
- URL: https://owasp.org/www-project-top-10-for-large-language-model-applications/
- Finding: Relevant risks include prompt injection, excessive agency, sensitive disclosure, insecure tools, and overreliance.
- WF74 implication: RSI must not expand permissions, tools, channels, config, or finance authority automatically.

## WF74 design implications

- make evaluator skills the first ClawHub inspection batch
- build a reflection-to-proposal pipeline before any apply loop
- create a lesson/correction trend report that remains review-only
- add an evaluation harness for truth, evidence, boundaries, continuity, actionability, regression proof, and signal/noise
- require independent QA before applying improvements beyond review artifacts
- keep every change file-backed, test-backed when possible, and reversible
