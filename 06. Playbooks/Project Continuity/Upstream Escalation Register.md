# Upstream Escalation Register

## Retrieval Notes
- Type: report
- Status: active
- Owner surface: `06. Playbooks/Operating Procedures/Upstream Escalation and Community Contribution Procedure.md`
- Authority: review-only
- Workflow: none
- Key entities: OpenClaw upstream issues, Windows portability, local verified findings
- Source freshness: 2026-09-21
- Next action: re-test #155478 when a new OpenClaw release lands; report the verdict back to Randall
- Archive posture: keep-active
- Tags: #veritas/runtime #status/active #retrieval/escalation

## Purpose
Track every upstream escalation from this workspace in one place: what was filed, what it was really
about, whether it is still live, and what happens next. This is a tracking surface, not canon and not
authority to post anything.

## Open escalations

| Issue | Filed | State | Severity frame | Predecessor work | Next action |
|---|---|---|---|---|---|
| [#155478](https://github.com/openclaw/openclaw/issues/155478) — `memory_search` KNN child cost is now Windows process creation (~1.5–1.8 s bare spawn), not module load | 2026-09-21 | OPEN | Windows/portability — likely minor on Linux/macOS | #140681 (closed, same symptom), fixed by #140730 (slim imports); that fix IS in 2026.9.4 and does not address process creation | Re-test on the next release; if unfixed, confirm the issue is still open; report verdict |

## Detail: #155478

- **What was measured.** Per-query `memory_search` cost on Windows 10.0.26200 / Node v26.7.0 /
  OpenClaw 2026.9.4. Bare `node --version` (median 1,696 ms) is statistically indistinguishable from
  booting the real KNN child (median 1,778 ms), so the residual after the upstream import-slimming fix
  is process creation, not module load.
- **Mechanism.** `runVectorKnnInSubprocess` spawns a fresh one-shot child per query
  (`manager-runtime.js:5189`, wired unconditionally at `:5567`; `MAX_CONCURRENT_VECTOR_KNN_CHILDREN = 2`
  bounds concurrency, not reuse).
- **Asks filed.** (1) amortize the KNN child — one long-lived worker per manager, or in-process below a
  working-set threshold; (2) set `PRAGMA mmap_size` / `cache_size` on the child connection (~100 ms).
- **Confirmed in the report.** The same spawn path applies to local (non-file-backed) indexes — there is
  no backing-store branch in `extensions/memory-core/`.
- **Local canon.** `06. Playbooks/Project Continuity/Workspace Speed Audit - 2026-09-20.md` §5.
- **Draft/rationale artifact.** `06. Playbooks/Project Continuity/Upstream Issue Draft - memory_search KNN child spawn - 2026-09-21.md`

## Closed-by-upstream (do not refile without re-measurement)

| Issue | State | Why it is closed | Re-test trigger |
|---|---|---|---|
| [#140681](https://github.com/openclaw/openclaw/issues/140681) — per-query KNN child boot ~2.3 s | closed / completed | Fixed by [#140730](https://github.com/openclaw/openclaw/pull/140730); child boot 443 ms → 60 ms median on Linux | Already re-tested 2026-09-21; fix present in 2026.9.4 and working as measured, so the residual was refiled as #155478 rather than reopened |

## Use rule
- This register tracks escalations; it is review-only and grants no authority to post publicly.
- Filing and commenting remain owner-approved external actions under `AGENTS.md`.
- Update a row whenever upstream responds or a release changes the answer; a row with no next action is
  a stale row.
