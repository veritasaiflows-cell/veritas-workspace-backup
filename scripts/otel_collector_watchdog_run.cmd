@echo off
rem Bounded OTEL collector watchdog entry point for scheduled use (cron + logon task).
rem Local-only: detects collector death and restarts it detached; also flags
rem "listening but receiving nothing". No config/service/network mutation.
setlocal
set "WORKSPACE=C:\Users\Veritas\.openclaw\workspace"
set "PY=C:\Users\Veritas\AppData\Local\Programs\Python\Python313\python.exe"
if not exist "%PY%" set "PY=python"
cd /d "%WORKSPACE%"
"%PY%" scripts\otel_collector_watchdog.py --restart --write --validate --starvation-hours 2
exit /b %ERRORLEVEL%
