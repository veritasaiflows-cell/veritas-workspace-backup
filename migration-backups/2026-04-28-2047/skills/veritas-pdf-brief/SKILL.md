---
name: veritas-pdf-brief
description: Build a Veritas finance-first PDF deliverable from an equity report, visual report, or deck. Use when the output should be printable, shareable, and cleanly formatted as a fixed-layout document without turning into bloated slideware or a raw note dump.
---

# Veritas PDF Brief

Use this skill when the user wants a polished PDF output.

This is not just "export whatever exists".
The PDF should be:
- readable
- printable
- finance-first
- decision-oriented
- visually clean without bloat

## Core mission

Convert existing research or generated report assets into a fixed-layout PDF brief that preserves the key decision logic and visuals.

## Before starting

Read the relevant source assets first:
- generated Word report if it exists
- generated deck if it exists
- staged JSON payloads in `tmp/`
- generated PNG panels if they exist
- canonical workspace notes if needed to verify the conclusion

## Default PDF structure

1. Title and date
2. Executive summary
3. Company snapshot
4. Key quarter / guidance
5. Visual panels
6. Technical / risk / action verdict
7. Source note or methodology appendix if needed

## Rules

- keep the PDF tighter than the Word report unless the user explicitly wants a full report PDF
- prefer strong callout boxes over long paragraphs
- preserve readable contrast and spacing
- do not add filler to make the PDF longer
- fixed-layout means every page should feel intentional

## Output rule

If a PDF is generated from an existing Word or deck workflow, note which source artifact it came from.

## Relationship to scripts

The script should handle rendering.
This skill defines what belongs in the PDF and what should be omitted.
