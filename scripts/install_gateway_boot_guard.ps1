# Installs "OpenClaw Gateway Boot Guard" - an AtStartup scheduled task with an
# S4U (run-whether-logged-in, no stored password) principal so the gateway
# auto-starts after an unattended Windows Update reboot.
#
# Owner-directed 2026-09-18 (Randall). Implements D2 option 3 from the 09-16
# root-cause register. MUST run elevated (right-click PowerShell -> Run as
# administrator). Idempotent: -Force overwrites any prior version.
#
# Known residual risk (register D2): session-0 execution may lose access to
# user-session / DPAPI-protected state. Mandatory controlled reboot test before
# this is trusted: Saturday 2026-09-19 (no declared session; market closed).

#Requires -RunAsAdministrator

$taskName = 'OpenClaw Gateway Boot Guard'
$guard = 'C:\Users\Veritas\.openclaw\workspace\scripts\gateway_boot_guard.ps1'

$action    = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$guard`""
$trigger   = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = 'PT60S'   # let network/TCP settle before the port check
$principal = New-ScheduledTaskPrincipal -UserId 'RQs_Business\Veritas' -LogonType S4U -RunLevel Limited
$settings  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
              -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

$t = Get-ScheduledTask -TaskName $taskName
"Registered: $($t.TaskName) | State: $($t.State)"
"Principal : $($t.Principal.UserId) | LogonType: $($t.Principal.LogonType) | RunLevel: $($t.Principal.RunLevel)"
"Trigger   : $($t.Triggers[0].CimClass.CimClassName) (delay $($t.Triggers[0].Delay))"
"Guard     : $guard"
"Verify    : Get-ScheduledTask -TaskName '$taskName' | fl"