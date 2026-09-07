# Tool Bloat Reduction Guard

Generated UTC: `2026-05-25T06:43:55Z`

Status: **warning**

## Counts

- tool_result_events: `1645`
- medium_events: `334`
- high_events: `0`
- truncated_events: `116`

## Top output tools

| Tool | Count | Total chars | Max chars | Next action |
|---|---:|---:|---:|---|
| `read` | 652 | 4322394 | 16000 | Use artifact_index/sql cockpit, then bounded read(offset/limit) only for the exact section needed. |
| `exec` | 560 | 1657934 | 16000 | Redirect verbose command output to tmp artifacts and print status, counts, and artifact path only. |
| `memory_search` | 45 | 251349 | 8961 | Use lower maxResults for narrow recall and follow with targeted memory_get lines only. |
| `web_fetch` | 23 | 131677 | 16000 | Lower maxChars and preserve source URL/provenance instead of full extracted page text. |
| `cron` | 18 | 88134 | 15993 | Return compact job/run summaries and artifact paths; avoid embedding full payload bodies in closeouts. |
| `sessions_spawn` | 84 | 51975 | 672 | Summarize output and store verbose details in a tmp artifact when practical. |
| `process` | 25 | 38677 | 15997 | Use process log limits and write long logs to tmp artifacts before summarizing. |
| `sessions_history` | 6 | 30821 | 14473 | Use small limits and includeTools=false unless tool history is required for diagnosis. |

## Policy

- Prefer SQL cockpit/artifact index before reading large generated artifacts.
- Use read offset/limit or targeted search after the first locator is known.
- For exec commands that can emit large output, write full output to a tmp artifact and print only status plus artifact path.
- For web_fetch, lower maxChars and keep URLs/provenance instead of dumping full pages.
- For cron/subagent results, return compact closeout plus artifact paths, not full artifact bodies.
- Use redacted telemetry and scorecard artifacts as the review surface; do not export raw tool bodies by default.

## Acceptance

- hard_fail: `False`
- next_target: reduce medium/truncated events by using bounded reads, capped fetches, and artifact-path closeouts
