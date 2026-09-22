# Gateway Boot Guard - idempotent start-if-not-running launcher.
# Runs at machine boot (registered by install_gateway_boot_guard.ps1) BEFORE any
# user logs on. If the gateway is already up (logon task won the race), exits 0.
# Otherwise launches the same known-good hidden launcher the existing
# "OpenClaw Gateway" task uses. A second gateway instance can't bind port 18789
# and exits harmlessly anyway (observed 2026-09-15: LastTaskResult=1, no damage),
# so this is double-start safe by construction.
# No new credential storage: the launcher file is the installer-written one.

$ErrorActionPreference = 'Stop'
$port = 18789
$launcher = 'C:\Users\Veritas\.openclaw\gateway.vbs'

$listening = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    exit 0
}

# Synchronous, hidden - mirrors the existing task's invocation exactly.
& wscript.exe $launcher
exit $LASTEXITCODE