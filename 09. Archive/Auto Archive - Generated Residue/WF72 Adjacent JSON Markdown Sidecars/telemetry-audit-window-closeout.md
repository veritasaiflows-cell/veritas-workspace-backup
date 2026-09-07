# Telemetry Audit Window Closeout

Generated UTC: `2026-05-25T06:43:46.434736Z`

Status: **audit_window_closed_baseline_restored**

## Required rollback checks

- Config validation: `valid=true`
- logs: `False`
- captureContent.enabled: `False`
- inputMessages: `False`
- outputMessages: `False`
- toolInputs: `False`
- toolOutputs: `False`
- systemPrompt: `False`
- external export: `False` (endpoint `http://127.0.0.1:4318`)

## Boundary

Local-only metrics/traces remain enabled. Logs and all message/tool/system content capture are disabled after the temporary audit window.

## Proof

- Disable proof: `tmp/telemetry-audit-window-disable-audit.json`
- Closeout JSON: `tmp/telemetry-audit-window-closeout.json`

## Runtime note

`openclaw config patch` reported: `Restart the gateway to apply.` No gateway restart was performed because this rollback packet specified the control/validation/get/closeout commands and said not to change anything else.
