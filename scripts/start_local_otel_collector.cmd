@echo off
setlocal
set "WORKSPACE=C:\Users\Veritas\.openclaw\workspace"
set "OTELCOL=%WORKSPACE%\tools\otelcol\otelcol.exe"
set "OTEL_CONFIG=%WORKSPACE%\tools\otelcol\openclaw-local-otel-runtime-metadata.yaml"
set "LOG_DIR=%WORKSPACE%\tmp\otel-collector"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
cd /d "%WORKSPACE%"
"%OTELCOL%" --config=file:tools\otelcol\openclaw-local-otel-runtime-metadata.yaml 1>>"%LOG_DIR%\collector.out.log" 2>>"%LOG_DIR%\collector.err.log"
