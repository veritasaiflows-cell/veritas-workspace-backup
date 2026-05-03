# Auth Readiness Audit

## Bottom line

Revalidated on 2026-04-18.
Current truth: local CLI readiness is much better than this note previously claimed. `clawhub`, `gh`, `rg`, `jq`, `ffmpeg`, and `obsidian` are all callable from the current shell. GitHub and ClawHub auth are verified. The main remaining config gate is API-key-based tooling that Randall has not enabled.

## Ready at binary level

- `clawhub`: callable
- `obsidian`: callable
- `gh`: callable
- `rg`: callable
- `jq`: callable
- `ffmpeg`: callable

## Auth and config results

### GitHub
- `gh` is callable from the current shell
- Auth status: verified via `gh auth status`
- Logged in account: `veritasaiflows-cell`

### ClawHub
- `clawhub` is callable from the current shell
- Auth status: verified via `clawhub whoami`
- Logged in account: `veritasaiflows-cell`

### Obsidian CLI and vault config
- `obsidian` is callable from the current shell
- Obsidian desktop vault config correctly points to:
  - `C:\Users\Veritas2.0\.openclaw\workspace`
- `OBSIDIAN_API_KEY` is not present, so API-driven Obsidian flows remain intentionally gated
- Direct file-based Obsidian work in the workspace is ready now and does not depend on that API key

### Environment-variable gated skills
These remain blocked because their required env vars are missing:

- `ELEVENLABS_API_KEY`
- `NOTION_API_KEY`
- `TRELLO_API_KEY`
- `TRELLO_TOKEN`
- `GOOGLE_PLACES_API_KEY`
- `SHERPA_ONNX_RUNTIME_DIR`
- `SHERPA_ONNX_MODEL_DIR`

### OpenAI note
- `OPENAI_API_KEY` is not present
- That matches Randall's preference to use OpenAI Codex / OAuth-backed routing instead of direct OpenAI API-key workflows

## Readiness classification

### Actually ready now
- `clawhub`
- `gh`
- `rg`
- `jq`
- `ffmpeg`
- Obsidian desktop vault targeting
- Direct file-based Obsidian workflows

### Ready but still partially gated
- `obsidian` API usage, because `OBSIDIAN_API_KEY` is absent

### Blocked by missing credentials or runtime config
- `notion`
- `trello`
- `goplaces`
- `sag`
- `openai-whisper-api`
- `sherpa-onnx-tts`

## Recommendation

Do not treat old readiness audits as durable truth. Revalidate binary visibility, auth, and config together before relying on them.
