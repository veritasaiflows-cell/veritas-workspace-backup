#!/usr/bin/env bash
# Shared helpers for the intelligence review scripts.
# Sourced by every check script. Designed for Git Bash on Windows.

set -u

# Color codes; respect NO_COLOR.
if [[ -z "${NO_COLOR:-}" && -t 1 ]]; then
  C_OK=$'\033[32m'
  C_WARN=$'\033[33m'
  C_FAIL=$'\033[31m'
  C_DIM=$'\033[2m'
  C_RESET=$'\033[0m'
else
  C_OK=""; C_WARN=""; C_FAIL=""; C_DIM=""; C_RESET=""
fi

# Status counters tracked across a single script run.
IR_OK=0
IR_WARN=0
IR_FAIL=0

ir_ok()   { printf "  %sok%s     %s\n"   "$C_OK"   "$C_RESET" "$*"; IR_OK=$((IR_OK+1)); }
ir_warn() { printf "  %swarn%s   %s\n"   "$C_WARN" "$C_RESET" "$*"; IR_WARN=$((IR_WARN+1)); }
ir_fail() { printf "  %sfail%s   %s\n"   "$C_FAIL" "$C_RESET" "$*"; IR_FAIL=$((IR_FAIL+1)); }
ir_info() { printf "  %sinfo   %s%s\n"   "$C_DIM"  "$*"   "$C_RESET"; }

ir_section() {
  printf "\n== %s ==\n" "$1"
}

ir_have() {
  command -v "$1" >/dev/null 2>&1
}

# Print final tally; return non-zero if any failures.
ir_summary() {
  printf "\n%sok%s=%d %swarn%s=%d %sfail%s=%d\n" \
    "$C_OK" "$C_RESET" "$IR_OK" \
    "$C_WARN" "$C_RESET" "$IR_WARN" \
    "$C_FAIL" "$C_RESET" "$IR_FAIL"
  [[ "$IR_FAIL" -eq 0 ]]
}

# Resolve workspace root from this script's location: scripts/lib.sh -> ..
ir_workspace_root() {
  local here
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  (cd "$here/.." && pwd)
}
