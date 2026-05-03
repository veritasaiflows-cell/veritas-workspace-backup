#!/usr/bin/env bash
# Verify auth state for tools that need login (separate from binary presence).
# A binary exists != it can act on the user's behalf. This is the operational layer.

set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib.sh
source "$HERE/lib.sh"

ir_section "Auth state"

# GitHub CLI: `gh auth status` exits 0 when at least one host is authenticated.
if ir_have gh; then
  if gh auth status >/dev/null 2>&1; then
    user="$(gh api user -q .login 2>/dev/null || echo unknown)"
    ir_ok "gh: logged in as $user"
  else
    ir_fail "gh: not logged in (run: gh auth login)"
  fi
else
  ir_fail "gh: binary missing"
fi

# ClawHub: no documented status command; probe a couple of likely shapes
# and fall back to a generic "unknown" warn so the audit doesn't lie.
if ir_have clawhub; then
  out=""
  if out="$(clawhub whoami 2>&1)" && [[ -n "$out" ]] && ! echo "$out" \
       | grep -qiE 'not logged in|unauthorized|unknown command|error'; then
    ir_ok "clawhub: $(echo "$out" | head -n1)"
  elif out="$(clawhub auth status 2>&1)" && echo "$out" \
       | grep -qiE 'logged in|authenticated'; then
    ir_ok "clawhub: $(echo "$out" | head -n1)"
  elif echo "$out" | grep -qiE 'not logged in|unauthorized'; then
    ir_fail "clawhub: not logged in (run: clawhub login)"
  else
    ir_warn "clawhub: auth state could not be determined"
  fi
else
  ir_fail "clawhub: binary missing"
fi

ir_summary
