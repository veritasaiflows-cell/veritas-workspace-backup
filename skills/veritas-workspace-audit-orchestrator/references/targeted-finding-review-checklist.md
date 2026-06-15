# Targeted Finding Review Checklist

Use this when Randall asks where a finding stands or whether to proceed with a recommendation.

1. Restate the finding.
2. Verify current status from live artifacts, not prior chat.
3. Inspect the exact owner surface plus one upstream producer and one downstream consumer when applicable.
4. Classify the finding: live, stale, resolved, partially resolved, or superseded.
5. Name the risk if left alone.
6. Name the smallest repair.
7. Name acceptance proof.
8. Name stop lines.
9. Route recurring patterns to one of: existing skill update, new skill, operating procedure, validator/script, workflow continuity, or daily memory.

Use P1/P2/P3 severity:
- P1 blocks trust, correctness, finance authority, config/runtime safety, or reliable startup/control state.
- P2 is material operational debt with a workaround.
- P3 is cleanup, ergonomics, or future hardening.
