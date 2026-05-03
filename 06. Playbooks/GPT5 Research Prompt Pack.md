# GPT5 Research Prompt Pack

## Purpose

Use GPT5.4 Research as a cheap external research arm with web access.
It does not know current workspace truth, so prompts should ask for external evidence and challenge framing, not internal-state decisions.

## Best-fit task types

- post-earnings external research
- thesis challenge passes
- macro / policy / credit context
- peer comparison
- event-risk framing
- presentation / UX best-practice research when public examples matter

## Output-saving convention

Save raw outputs to:
- `tmp/external-research/YYYY-MM-DD <topic> - GPT5.md`

## Prompt 1 — post-earnings challenge pass

```text
Do a decision-grade external research pass on [COMPANY] after its latest earnings report.

Focus on:
- what actually improved
- what actually weakened
- whether the market reaction reflects thesis impairment, valuation reset, or noise
- the strongest bull and bear arguments from credible public sources
- what matters most next quarter

Output:
1. Core verdict
2. Bull case
3. Bear case
4. What matters most next quarter
5. What would invalidate the constructive read

Use current public web sources. Be direct and evidence-based.
```

## Prompt 2 — external bear-case build

```text
Build the strongest evidence-based bear case against [COMPANY] using current public sources.

Do not produce a balanced overview first.
Start from the bearish view and make it as strong as possible.
Then end with:
1. which bearish points are strongest
2. which are weak or overstated
3. what upcoming evidence would prove the bear case right or wrong

Be direct and avoid filler.
```

## Prompt 3 — peer comparison

```text
Compare [COMPANY] versus [PEER 1], [PEER 2], and [PEER 3] on the one issue that matters most right now: [ISSUE].

Focus on:
- relative strengths
- relative weaknesses
- whether the market is likely pricing the gap correctly
- which company currently has the most favorable risk/reward on this issue alone

Use current public sources and keep the analysis decision-grade.
```

## Prompt 4 — macro / policy context

```text
Do a concise but decision-grade external research pass on [MACRO TOPIC].

Focus on:
- what changed recently
- what credible sources broadly agree on
- what the market may still be underestimating
- what would matter most for equities / rates / oil / credit over the next 1-3 months

Output:
1. Current regime read
2. Key supporting evidence
3. Main uncertainty
4. What would change the view
```

## Prompt 5 — event-risk framing

```text
Do an external research pass on the current risk around [EVENT / GEOPOLITICAL TOPIC].

Focus on:
- what is confirmed
- what is speculative
- which scenarios matter most economically
- what public companies or sectors are most exposed
- what would justify treating this as a real portfolio risk rather than headline noise

Be concrete and source-driven.
```

## Prompt 6 — command-center / UX best-practice research

```text
Research public best practices for [DASHBOARD / HTML / INFO DESIGN TOPIC].

Focus on:
- what actually improves operator scanning speed
- what reduces false confidence
- what makes alert and status systems easier to trust
- concrete design patterns worth reusing
- bad patterns to avoid

Output:
1. Key design principles
2. Reusable patterns
3. Mistakes to avoid
4. What would matter most for a finance operations command center
```

## Usage notes

- ask GPT5 for external evidence, not workspace truth
- prefer one sharp question over broad vague prompts
- save raw outputs before summarizing them elsewhere
- have Veritas review before promoting conclusions into canonical notes
