# Derived Evidence Freshness Convention

## Purpose
Keep every expensive derived artifact fresh without paying refresh cost on a schedule. One convention — gate plus proof plus max-age plus conditional refresh — applied per surface instead of re-derived each time. Proven on graphs (memory_graph_maintenance gate/refresh), binaries (go_binary_freshness_guard), and finance digests (alert-freshness controller with reader age limit).

## Trigger
Use this convention when adding or repairing any derived artifact: graph, index, price evidence, quote snapshot, consensus refresh, packet, or scorecard. Apply it when a guard fails on stale/missing evidence or when a routine pays full rebuild cost every run.

## Read first
- The owning script's `--help` and its current proof packet in `tmp/`
- `cron-automation-manager` for scheduler boundaries
- `task-intake-contract` for material work framing

## The convention
1. **Gate (cheap, scheduled).** A read-only freshness check — mtime/hash/row-count compare — runs on cron. Cost target is seconds. It writes a proof packet and reports `ok`, `warning` (refresh due), or `error` (source broken). It never rebuilds.
2. **Proof packet (always).** Every gate and refresh writes timestamped JSON under `tmp/` with schema, `generated_at_utc`, `status`, and the exact staleness signal (changed counts, uncovered counts, ages). No proof, no trust.
3. **Max-age (consumer side).** Every reader enforces a max age on its input and fails closed — stale input is a warning or error, never silently served as current. The digest 6-hour limit is the reference implementation.
4. **Conditional refresh (on drift only).** The expensive rebuild runs only when the gate says `warning`, bounded by `--max-seconds`, and records before/after state. Steady-state cost is O(drift), not O(schedule).
5. **Warning versus error.** Missing upstream evidence with a healthy source is `warning` (valid empty state, e.g. preview ledger with zero rows). A broken or unresolvable source is `error`. Empty-pass results that report `ok` with zero records are defects — fix the gate, not the grade.

## Per-surface application
| Surface | Gate | Proof | Max-age reader | Refresh |
|---|---|---|---|---|
| Scripts code graph | `memory_graph_maintenance.py --mode gate` (daily 23:10) | `tmp/operational-graph-maintenance.json` | router health check before query | `--mode refresh` weekly Sun 04:00 + on demand |
| Go binaries | `go_binary_freshness_guard.py --validate` | `tmp/go-binary-freshness-guard.json` | build scripts check freshness before use | rebuild when source newer |
| Finance digests | alert-freshness controller | `tmp/alert-level-freshness-controller.json` | digest 6-hour age limit, fail closed | morning chain quote stage |
| WF77 supplemental prices | uncovered-count warning in proof | supplemental evidence JSON + snapshot | bridge valid-row counts, handoff missing-rows error | fetch only tickers lacking valid technical close and fresh supplemental evidence |
| WF75 fixture regression | validator exit code | `tmp/wf75-renderer-export-regression.json` with card provenance | closeout fails the guard on regression error | fixture fallback keeps proof honest when live cards absent |
| Ticker cards | card freshness runner | card `generated_at_utc` + missing-evidence entries | `load_card` fails closed on missing/invalid | owner runner refresh |

## Dynamic routing alignment
Gates check freshness only. They never select tickers, never infer approval, never mutate canon, and never execute. The dynamic entitlement scope decides *what* is covered; this convention decides *when evidence is fresh enough to trust*. Keep those two jobs separate: a stale gate blocks use of evidence, it never changes routing.

## Proof
- Gate command exits 0 with a fresh proof packet (`generated_at_utc` within the scheduled window).
- Refresh runs only on `warning` and records before/after.
- Each listed reader rejects input older than its max age in a live test (stale fixture → warning/error, not silent use).
- No scheduled job pays full rebuild cost when the gate reports `ok`.

## Stop lines
- Do not downgrade an `error` to `warning` to make a guard pass; fix the source or prove the empty state is valid (ledger self-reports ok, append pipeline ran with zero candidates).
- Do not synthesize live finance evidence to satisfy a gate. Fixture scaffolding is allowed only in fixture-only harnesses with explicit synthetic provenance, never in canon, cards, quotes, or ledgers.
- Do not recreate retired surfaces (portfolio, paper, deployment, sizing, orders, accounts) to satisfy a proof check; mark the check retired instead.
- Do not add a new gate without its proof packet, reader max-age, and rollback (previous proof retained).
- Config, auth, credential, network, channel, runtime, and schedule changes still need their exact gates; this convention grants none of them.

## Next action after use
- New surface covered: add its row to the table above with gate/proof/reader/refresh commands.
- Recurring gate warning: fix the producer (refresh source artifacts before downstream scorecards) rather than widening the max age.
- Repeated `error`: treat as incident (missing source, broken producer, retired contract) and route to the owning lane.
