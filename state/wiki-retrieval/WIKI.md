# Memory Wiki

This vault is maintained by the OpenClaw memory-wiki plugin.

- Vault mode: `isolated`
- Render mode: `native`
- Search corpus default: `wiki`

## Architecture
- Raw sources remain the evidence layer.
- To keep unmanaged raw Markdown in `sources/`, add `<!-- openclaw:wiki:raw-source -->` near the top of the page.
- Wiki pages are the human-readable synthesis layer.
- `.openclaw-wiki/cache/agent-digest.json` is the agent-facing compiled digest.

## Notes
<!-- openclaw:human:start -->
<!-- openclaw:human:end -->
