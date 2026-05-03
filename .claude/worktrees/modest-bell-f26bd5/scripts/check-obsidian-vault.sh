#!/usr/bin/env bash
# Verify Obsidian's registered vaults point at the workspace root, not the
# nested .obsidian/ folder. Reproduces the manual finding from yesterday's audit.
#
# On Windows, Obsidian stores its vault registry at:
#   %APPDATA%/obsidian/obsidian.json
# That file is JSON of the form: { "vaults": { "<id>": { "path": "...", "open": true } } }

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

ir_section "Obsidian vault registry"

WORKSPACE="$(ir_workspace_root)"
ir_info "expected vault root: $WORKSPACE"

# Resolve obsidian.json regardless of POSIX vs native path style.
APPDATA_RAW="${APPDATA:-}"
if [[ -z "$APPDATA_RAW" && -n "${USERPROFILE:-}" ]]; then
  APPDATA_RAW="$USERPROFILE/AppData/Roaming"
fi

if [[ -z "$APPDATA_RAW" ]]; then
  ir_fail "APPDATA not set; cannot locate obsidian.json"
  ir_summary
  exit $?
fi

# Convert backslashes for Git Bash.
APPDATA_POSIX="${APPDATA_RAW//\\//}"
CONFIG="$APPDATA_POSIX/obsidian/obsidian.json"

if [[ ! -f "$CONFIG" ]]; then
  ir_fail "obsidian.json not found at $CONFIG"
  ir_summary
  exit $?
fi
ir_ok "found $CONFIG"

if ! ir_have jq; then
  ir_warn "jq missing; falling back to grep-based check"
  if grep -qi "/.obsidian\"" "$CONFIG" || grep -qi '\\\\.obsidian"' "$CONFIG"; then
    ir_fail "vault path appears to point at a .obsidian/ subfolder"
  else
    ir_ok "no .obsidian/ vault path detected (best-effort)"
  fi
  ir_summary
  exit $?
fi

# Normalize both sides to forward slashes + lowercase for comparison.
norm() { tr '\\' '/' | tr '[:upper:]' '[:lower:]'; }

WS_NORM="$(printf '%s' "$WORKSPACE" | norm)"

# Pull each registered vault and classify it.
mapfile -t VAULTS < <(jq -r '.vaults | to_entries[] | "\(.value.open // false)\t\(.value.path)"' "$CONFIG" 2>/dev/null)

if [[ "${#VAULTS[@]}" -eq 0 ]]; then
  ir_warn "no vaults registered in obsidian.json"
  ir_summary
  exit $?
fi

found_workspace=0
bad_vault=0
for line in "${VAULTS[@]}"; do
  open="${line%%	*}"
  path="${line#*	}"
  path_norm="$(printf '%s' "$path" | norm)"

  flag=""
  [[ "$open" == "true" ]] && flag="(open) "

  if [[ "$path_norm" == "$WS_NORM" ]]; then
    ir_ok "${flag}workspace root vault registered: $path"
    found_workspace=1
  elif [[ "$path_norm" == *"/.obsidian"* ]]; then
    ir_fail "${flag}vault points inside .obsidian/: $path"
    bad_vault=1
  else
    ir_info "${flag}other vault: $path"
  fi
done

if [[ "$found_workspace" -eq 0 ]]; then
  ir_fail "workspace root not registered as a vault"
fi

ir_summary
