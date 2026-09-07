# Redacted Tool-Result Telemetry

Generated: `2026-05-25T05:39:48Z`

## Boundary

- report_only: `True`
- mutations_performed: `False`
- authority: No config/auth/runtime mutation, no canon mutation, no approval or execution authority.
- redaction: No raw tool-result bodies are exported. Target/source/locator fields are bounded and secret-like strings are redacted before writing.

## Summary

- Transcripts scanned: `1`
- Tool-result events: `1645`
- Medium/high output events: `334`
- Truncated or hard-warn events: `116`

## By tool

| Tool | Count | Total output chars | Max output chars |
|---|---:|---:|---:|
| `read` | 652 | 4322394 | 16000 |
| `exec` | 560 | 1657934 | 16000 |
| `memory_search` | 45 | 251349 | 8961 |
| `web_fetch` | 23 | 131677 | 16000 |
| `cron` | 18 | 88134 | 15993 |
| `sessions_spawn` | 84 | 51975 | 672 |
| `process` | 25 | 38677 | 15997 |
| `sessions_history` | 6 | 30821 | 14473 |
| `memory_get` | 13 | 30040 | 6097 |
| `sessions_yield` | 58 | 19791 | 1204 |
| `subagents` | 5 | 11069 | 2485 |
| `web_search` | 3 | 10894 | 6748 |
| `edit` | 82 | 6050 | 197 |
| `write` | 43 | 3007 | 116 |
| `apply_patch` | 22 | 1783 | 299 |
| `session_status` | 3 | 1443 | 524 |
| `update_plan` | 3 | 324 | 108 |

## By path category

| Category | Count | Total output chars | Max output chars |
|---|---:|---:|---:|
| `unknown` | 1443 | 5556432 | 16000 |
| `workspace_file` | 79 | 446816 | 15982 |
| `workspace_memory` | 41 | 228588 | 8961 |
| `workspace_tmp` | 35 | 209539 | 15997 |
| `external_url` | 28 | 160102 | 16000 |
| `command_or_query` | 16 | 49949 | 15983 |
| `workspace_script` | 1 | 4183 | 4183 |
| `query_or_text` | 2 | 1753 | 1298 |

## Largest events (content-free)

| Tool | Status | Duration ms | Output chars | Category | Target | Truncated | Recommendation |
|---|---|---:|---:|---|---|---:|---|
| `exec` | `success` |  | 16000 | `unknown` | `unknown` | True | Constrain command output, redirect large artifacts to files, then read only targeted excerpts. |
| `exec` | `success` |  | 16000 | `unknown` | `unknown` | True | Constrain command output, redirect large artifacts to files, then read only targeted excerpts. |
| `exec` | `success` |  | 16000 | `unknown` | `unknown` | True | Constrain command output, redirect large artifacts to files, then read only targeted excerpts. |
| `exec` | `success` |  | 16000 | `unknown` | `unknown` | True | Constrain command output, redirect large artifacts to files, then read only targeted excerpts. |
| `read` | `success` |  | 16000 | `unknown` | `unknown` | True | Use a smaller read offset/limit or a targeted search/excerpt; avoid re-reading the full file after the useful locator is known. |
| `web_fetch` | `success` |  | 16000 | `external_url` | `https://developers.openai.com/api/docs/guides/migrate-to-responses` | True | Fetch fewer results or lower extraction limits; preserve URLs/provenance and summarize only decision-relevant excerpts. |
| `web_fetch` | `success` |  | 16000 | `external_url` | `https://github.com/openai/openai-node` | True | Fetch fewer results or lower extraction limits; preserve URLs/provenance and summarize only decision-relevant excerpts. |
| `read` | `success` |  | 15999 | `unknown` | `unknown` | True | Use a smaller read offset/limit or a targeted search/excerpt; avoid re-reading the full file after the useful locator is known. |
| `exec` | `success` |  | 15999 | `unknown` | `unknown` | True | Constrain command output, redirect large artifacts to files, then read only targeted excerpts. |
| `read` | `success` |  | 15999 | `unknown` | `unknown` | True | Use a smaller read offset/limit or a targeted search/excerpt; avoid re-reading the full file after the useful locator is known. |
| `read` | `success` |  | 15999 | `unknown` | `unknown` | True | Use a smaller read offset/limit or a targeted search/excerpt; avoid re-reading the full file after the useful locator is known. |
| `read` | `success` |  | 15999 | `unknown` | `unknown` | True | Use a smaller read offset/limit or a targeted search/excerpt; avoid re-reading the full file after the useful locator is known. |
| `process` | `success` |  | 15997 | `workspace_tmp` | `tmp/canon-volatile-execution-board-sync.md` | True | Use a smaller read offset/limit or a targeted search/excerpt; avoid re-reading the full file after the useful locator is known. |
| `cron` | `success` |  | 15993 | `unknown` | `unknown` | True | Keep the raw artifact on disk and bring only bounded, task-relevant excerpts back into chat. |
| `cron` | `success` |  | 15986 | `unknown` | `unknown` | True | Keep the raw artifact on disk and bring only bounded, task-relevant excerpts back into chat. |
| `exec` | `success` |  | 15986 | `unknown` | `unknown` | True | Constrain command output, redirect large artifacts to files, then read only targeted excerpts. |
| `exec` | `success` |  | 15983 | `unknown` | `unknown` | True | Constrain command output, redirect large artifacts to files, then read only targeted excerpts. |
| `exec` | `success` |  | 15983 | `command_or_query` | `python scripts\\policy_expectations_refresh.py` | True | Constrain command output, redirect large artifacts to files, then read only targeted excerpts. |
| `read` | `success` |  | 15982 | `workspace_file` | `rel(CACHE_DB),` | True | Use a smaller read offset/limit or a targeted search/excerpt; avoid re-reading the full file after the useful locator is known. |
| `exec` | `success` |  | 15980 | `unknown` | `unknown` | True | Constrain command output, redirect large artifacts to files, then read only targeted excerpts. |
| `exec` | `success` |  | 15978 | `unknown` | `unknown` | True | Constrain command output, redirect large artifacts to files, then read only targeted excerpts. |
| `read` | `success` |  | 15978 | `unknown` | `unknown` | True | Use a smaller read offset/limit or a targeted search/excerpt; avoid re-reading the full file after the useful locator is known. |
| `read` | `success` |  | 15977 | `unknown` | `unknown` | True | Use a smaller read offset/limit or a targeted search/excerpt; avoid re-reading the full file after the useful locator is known. |
| `exec` | `success` |  | 15974 | `unknown` | `unknown` | True | Constrain command output, redirect large artifacts to files, then read only targeted excerpts. |
| `read` | `success` |  | 15973 | `unknown` | `unknown` | True | Use a smaller read offset/limit or a targeted search/excerpt; avoid re-reading the full file after the useful locator is known. |
