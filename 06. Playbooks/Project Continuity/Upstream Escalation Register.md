# Upstream Escalation Register

## Retrieval Notes
- Type: report
- Status: active
- Owner surface: `06. Playbooks/Operating Procedures/Upstream Escalation and Community Contribution Procedure.md`
- Authority: review-only
- Workflow: none
- Key entities: OpenClaw upstream issues, Windows portability, local verified findings
- Source freshness: 2026-09-22
- Next action: upgrade to the first release containing PR #153832, then re-measure spawn cost; Ask 2 (SQLite pragmas) remains unaddressed
- Archive posture: keep-active
- Tags: #veritas/runtime #status/active #retrieval/escalation

## Purpose
Track every upstream escalation from this workspace in one place: what was filed, what it was really
about, whether it is still live, and what happens next. This is a tracking surface, not canon and not
authority to post anything.

## Open escalations

None currently open. See the closed table below.

### #155478 status change: CLOSED by upstream (2026-09-22T06:56:53Z), `stateReason: COMPLETED`

Closed by `clawsweeper[bot]` as already implemented on `main`, citing
[#153832](https://github.com/openclaw/openclaw/pull/153832) *perf(memory-core): reuse native KNN query
processes* (merged 2026-09-20T18:36:31Z). It was triaged before closing — labels `P2` and
`impact:other`.

**That closure is substantively correct, and it landed on the exact ask we filed.** PR #153832 reuses
the existing OS-killable KNN child with serial requests per database and request IDs over
newline-delimited JSON, keeps the two-live-child limit, and retires idle children after 30 minutes.
Its own synthetic proof: 100 queries → spawns reduced 100 → 1, p50 latency 329.29 ms → 4.20 ms. That
is Ask 1 as written.

**Important nuance — fixed on `main` is not fixed on this machine.** Verified 2026-09-22:

- Installed build is **2026.9.4**, released 2026-09-11T03:46:22Z — **nine days before** the fix merged.
- Latest published release is **2026.9.5**, 2026-09-19T01:55:23Z — still **before** the fix merged
  (2026-09-20T18:36:31Z). So **no released build contains #153832 yet.**
- The installed child is still strictly one-shot: `process.stdin.once("end", ...)` reads one JSON
  blob, writes one result, exits — there is no request-ID or newline-delimited protocol, which is
  what #153832 introduces.
- `manager-runtime.js:5189` still spawns per query; no reuse/pool code is present in 2026.9.4.

So the user-visible Windows cost persists on this host until an upgrade past 2026.9.5. The next
release to watch for is the first one published after 2026-09-20.

**Ask 2 remains unaddressed.** The closure routed the SQLite cache-tuning half elsewhere: *"evaluate
any remaining SQLite cache-tuning benefit separately against that implementation."* The child still
sets only `PRAGMA query_only` + `busy_timeout`, and there is still no config surface for `mmap_size`.
Worth ~100 ms — small, and now subordinate to the process-reuse change. Do not refile it as-is;
re-measure after upgrading, since process reuse changes the cost profile it was measured against.

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
- **Outcome.** Closed as superseded, one day after filing. The report was accurate for its build
  (2026.9.4) and its primary ask was granted, but it was filed against a release that predated the
  fix. Lesson for the procedure: before filing, also check whether the fix is already merged on `main`
  but not yet released — `gh api repos/<repo>/pulls/<n>` merge dates versus the installed version's
  release date. That check would have changed the framing from a fresh report to a
  release-tracking note.

## Closed-by-upstream (do not refile without re-measurement)

| Issue | State | Why it is closed | Re-test trigger |
|---|---|---|---|
| [#140681](https://github.com/openclaw/openclaw/issues/140681) — per-query KNN child boot ~2.3 s | closed / completed | Fixed by [#140730](https://github.com/openclaw/openclaw/pull/140730); child boot 443 ms → 60 ms median on Linux | Already re-tested 2026-09-21; fix present in 2026.9.4 and working as measured, so the residual was refiled as #155478 rather than reopened |
| [#155478](https://github.com/openclaw/openclaw/issues/155478) — Windows per-query KNN spawn cost | closed / completed (2026-09-22) | Superseded by [#153832](https://github.com/openclaw/openclaw/pull/153832) (process reuse), which implements Ask 1; closed by `clawsweeper[bot]` as already implemented on `main` | **Upgrade to the first release published after 2026-09-20**, then re-measure `memory_search` spawn cost on Windows. Expect the spawn term to collapse if reuse works as its 100-query proof claims |

## Use rule
- This register tracks escalations; it is review-only and grants no authority to post publicly.
- Filing and commenting remain owner-approved external actions under `AGENTS.md`.
- Update a row whenever upstream responds or a release changes the answer; a row with no next action is
  a stale row.
