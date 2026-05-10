# Closed Workflow Retrospective Guidance - 2026-05-06

## Scope
- Retrospective guidance pass on the most recent closed workflow batch visible on live control surfaces.
- Live surfaces now show the recent closure set as: WF21, WF31, WF26, WF22, WF36 bounded follow-up, WF27, WF32, WF33, WF34, and WF35.
- This slightly differs from the initially suggested order because the live queue/registry now place WF32-WF35 as earlier closed hardening lanes and WF23 as the active downstream workflow.

## Sources reviewed
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- `memory/2026-05-06.md`
- `MEMORY.md`
- `06. Playbooks/Project Continuity/Workflow 21 - Recurring Source Bundle and Review Window Pilot.md`
- `06. Playbooks/Project Continuity/Workflow 31 - Runtime Continuity, Memory Indexing, and Scheduled-Proof Hardening.md`
- `08. Audits/WF21 Schema Island and Closeout Audit - 2026-05-06.md`
- `08. Audits/WF31 Runtime Continuity and Scheduled-Proof Closeout Audit - 2026-05-06.md`
- `08. Audits/WF26 External Intelligence Pilot Closeout Audit - 2026-05-06.md`
- `08. Audits/WF36 Slice A Retrieval Metadata Follow-up Audit - 2026-05-06.md`
- `08. Audits/WF27 Predictive Readiness Methodology Audit - 2026-05-06.md`
- `08. Audits/WF32-WF33 QA Audit - 2026-05-05.md`
- `08. Audits/WF34 Folder Boundary Audit and Completion - 2026-05-05.md`
- `08. Audits/WF35 Dashboard Truth-Surface Audit and Completion - 2026-05-05.md`

## 1) Repeated strengths worth standardizing
- **Fail-closed closure discipline held.** The strongest pattern across WF21, WF26, WF27, WF31, and WF36 was refusing to widen from partial usefulness into fake readiness. HOLD / bounded-follow-up / review-only outcomes were used correctly instead of forcing “ready” language.
- **Residue was usually named, not buried.** The better closures explicitly separated “closed at intended scope” from later widening work: WF21 kept cron activation deferred, WF31 kept semantic-memory and scheduled-proof promotion deferred, WF26 kept no standalone cron, WF27 kept data-retention prerequisites explicit, and WF36 kept SQL subordinate.
- **Control surfaces were eventually reconciled back to live truth.** After the WF32/WF33/WF21 ordering drift was caught, queue, registry, continuity, and daily memory were brought back into alignment instead of letting stale status language persist.
- **Authority boundaries stayed explicit.** WF35’s owner map, WF21/WF26’s review-only posture, WF22’s manual-apply rule, and WF36’s retrieval-only framing all reinforced a healthy pattern: dashboards summarize, SQL retrieves, packets review, humans decide.
- **Proof posture improved when artifacts were regenerated, not just code patched.** WF32/WF33 only became honestly closable after acceptance proof and chain proof were refreshed; this is exactly the right habit to keep.

## 2) Recurring drift / failure patterns to watch
- **Control-plane drift appears faster than workflow memory catches up.** The largest repeated failure mode was status disagreement across queue, registry, continuity, and recent audits. WF32/WF33/WF21 ordering drift is the clearest example, but the same pattern appears whenever an older summary block survives a reprioritization.
- **Code-landed vs proof-landed keeps separating.** WF32/WF33 showed the classic risk: the fix exists in code, but the artifacts and acceptance outputs still describe the old world. Until the sidecars and tests are refreshed, closure language drifts fake-green.
- **Old diagnoses linger after reality changes.** WF31 showed this sharply: memory looked broken in older notes, then later live checks showed bounded health. Without explicit stale-diagnosis cleanup, the workspace can carry ghost blockers forward.
- **Adjacent-consumer drift remains a standing risk after schema/vocabulary changes.** WF32/WF33 needed cross-surface contradiction checks because shared state vocabulary and JSON fields ripple into validators, summaries, and chains.
- **Useful pilot lanes naturally try to overgrow.** WF21, WF26, WF22, and WF36 all had latent pressure to widen from bounded helper surfaces into recurring automation or second-truth layers. The closures resisted that, but the pressure is recurring and should be assumed in future lanes.

## 3) Guidance for avoiding residue in upcoming workflows
- **Treat queue/registry/continuity sync as part of closeout, not post-close cleanup.** A workflow should not count as closed until the top queue block, recent-closures section, registry row, continuity note, and daily memory all tell the same story.
- **When a diagnosis changes, explicitly mark the old claim stale in the owning note or audit.** This would have reduced WF31 residue faster and prevents future workflows from reopening solved blockers by inheritance.
- **Keep “bounded usefulness” as a first-class success state.** Upcoming workflows should be allowed to end in HOLD / review-only / discovery-only without social pressure to justify themselves by widening.
- **Require adjacent proof refresh whenever outputs are contract-bearing.** If a workflow changes JSON shape, validation vocabulary, scheduling order, or truth-owner semantics, closure should include regenerated artifacts and the smallest downstream acceptance gate that consumes them.
- **Prefer one canonical phase artifact per concept.** WF26 benefited from collapsing duplicate Phase 1 maps; future workflows should avoid parallel draft truths once a canonical artifact exists.

## 4) Concrete recommendations for orchestration discipline
1. **Add a mandatory closeout sync checklist to every workflow pass:** queue top summary, recently closed section, registry row, continuity note, audit/verdict note, and daily memory entry must all be updated or explicitly deferred together.
2. **Use a stale-diagnosis rule in audits:** if live checks overturn an earlier blocker, the closing artifact should name the earlier claim as stale and point to the new truth source.
3. **Preserve the “code change -> regenerate artifacts -> rerun smallest acceptance gate” sequence as mandatory for shared-contract work.** WF32/WF33 proved why this cannot be optional.
4. **Open widening workflows only when a consumer is real, not because a bounded pilot was merely useful.** WF21, WF26, WF22, and WF36 all closed well because they resisted speculative next-step inflation.
5. **Keep subordinate surfaces labeled by function in every new workflow:** review packets, dashboard summaries, SQL caches, and machine companions should each state what they cannot authorize.
6. **Use independent audits to challenge closure claims before queue movement whenever a workflow touches control surfaces, shared contracts, or automation authority.** The recent batch was strongest where the audit acted as a real brake rather than a ceremonial final note.

## Bottom line
- This closure batch was stronger than average because it repeatedly chose honest boundedness over performative completion.
- The main thing to harden next is not ambition; it is synchronization discipline, stale-claim cleanup, and proof refresh sequencing so the control plane stops carrying residue longer than the implementation does.
