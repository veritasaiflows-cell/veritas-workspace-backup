@echo off
setlocal
set "WORKSPACE=C:\Users\Veritas\.openclaw\workspace"
set "PYTHON=C:\Users\Veritas\AppData\Local\Programs\Python\Python313\python.exe"
cd /d "%WORKSPACE%"
"%PYTHON%" "%WORKSPACE%\scripts\local_otel_collector.py" --host 127.0.0.1 --port 4318 --out "%WORKSPACE%\tmp\otel-collector"
