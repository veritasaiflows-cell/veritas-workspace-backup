#!/usr/bin/env bash
# Verify presence of Tier 1 binaries the workspace depends on.
# Mirrors the binary section of "Auth Readiness Audit.md".

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

ir_section "Tier 1 binaries"

# Required: workspace operates blind without these.
REQUIRED=(rg jq gh ffmpeg clawhub obsidian)
for bin in "${REQUIRED[@]}"; do
  if ir_have "$bin"; then
    ir_ok "$bin"
  else
    ir_fail "$bin missing on PATH"
  fi
done

# Optional but commonly useful; warn rather than fail.
OPTIONAL=(node npm git curl)
ir_section "Optional helpers"
for bin in "${OPTIONAL[@]}"; do
  if ir_have "$bin"; then
    ir_ok "$bin"
  else
    ir_warn "$bin missing on PATH"
  fi
done

ir_summary
