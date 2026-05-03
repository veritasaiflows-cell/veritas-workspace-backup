# Auth Readiness Audit

## Bottom line

Core binaries are now installed, but several high-value skills are still not truly usable because auth, API keys, or config are missing.

## Ready at binary level

- `clawhub` binary: installed
- `obsidian` binary: installed
- `gh`: installed
- `rg`: installed
- `jq`: installed
- `ffmpeg`: installed

## Auth and config results

### GitHub
- `gh` binary exists
- Auth status: **not logged in**
- Required next step: `gh auth login`

### ClawHub
- `clawhub` binary exists
- Auth status: **not logged in**
- Required next step: `clawhub login`

### Obsidian CLI
- `obsidian` binary exists
- Current status: **not usable yet** because it requires `OBSIDIAN_API_KEY`
- Important finding: Obsidian's desktop config currently points the open vault to:
  - `C:\Users\Veritas2.0\.openclaw\workspace\.obsidian`
- That is wrong for our intended setup. The intended vault root is:
  - `C:\Users\Veritas2.0\.openclaw\workspace`
- This likely means Obsidian was opened against the `.obsidian` subfolder instead of the workspace root at least once.

### Environment-variable gated skills
These are currently blocked because their required env vars are missing:

- `ELEVENLABS_API_KEY`
- `NOTION_API_KEY`
- `TRELLO_API_KEY`
- `TRELLO_TOKEN`
- `GOOGLE_PLACES_API_KEY`
- `SHERPA_ONNX_RUNTIME_DIR`
- `SHERPA_ONNX_MODEL_DIR`

### OpenAI note
- Randall explicitly does **not** want to use `OPENAI_API_KEY` here.
- Use OpenAI Codex / OAuth-backed tooling instead of enabling direct OpenAI API-key workflows.

## Readiness classification

### Actually ready now
- `rg`
- `jq`
- `ffmpeg`

### Installed but not yet ready
- `gh`
- `clawhub`
- `obsidian`

### Blocked by missing credentials or runtime config
- `notion`
- `trello`
- `goplaces`
- `sag`
- `openai-whisper-api`
- `sherpa-onnx-tts`

## Recommendation

Best next actions:
1. Fix the Obsidian vault target so the active vault is the workspace root, not `.obsidian/`
2. Log into GitHub CLI
3. Log into ClawHub
4. Add API keys only for services Randall actually wants enabled

Installed is not the same as operational. This audit reflects operational truth.
