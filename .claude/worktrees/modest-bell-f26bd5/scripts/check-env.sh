#!/usr/bin/env bash
# Verify presence of API keys / runtime env vars for the gated skills.
# Sourced from "Auth Readiness Audit.md". OPENAI_API_KEY is intentionally
# excluded — Randall prefers Codex / OAuth tooling.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

ir_section "Skill env vars"

# Each entry: VAR_NAME|skill label
ENV_VARS=(
  "OBSIDIAN_API_KEY|obsidian (CLI)"
  "ELEVENLABS_API_KEY|sag (ElevenLabs TTS)"
  "NOTION_API_KEY|notion"
  "TRELLO_API_KEY|trello"
  "TRELLO_TOKEN|trello"
  "GOOGLE_PLACES_API_KEY|goplaces"
  "SHERPA_ONNX_RUNTIME_DIR|sherpa-onnx-tts"
  "SHERPA_ONNX_MODEL_DIR|sherpa-onnx-tts"
)

for entry in "${ENV_VARS[@]}"; do
  name="${entry%%|*}"
  label="${entry##*|}"
  val="${!name:-}"
  if [[ -n "$val" ]]; then
    ir_ok "$name set ($label)"
  else
    ir_fail "$name missing ($label)"
  fi
done

ir_section "Excluded by policy"
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  ir_warn "OPENAI_API_KEY is set; Randall prefers Codex/OAuth tooling instead"
else
  ir_ok "OPENAI_API_KEY not set (matches stated preference)"
fi

ir_summary
