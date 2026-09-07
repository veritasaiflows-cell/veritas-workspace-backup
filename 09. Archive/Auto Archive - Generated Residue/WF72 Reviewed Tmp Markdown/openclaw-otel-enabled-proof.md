# OpenClaw OTEL Enabled Proof

Generated UTC: `2026-05-25T05:24:19.148871Z`

Status: **enabled_receiving_metrics**

## Collector

- Endpoint: `http://127.0.0.1:4318`
- Health: `ok`
- Receipts: `5`
- Signals seen: `metrics, traces`

## Privacy boundary

- Local only: `True`
- Logs enabled: `False`
- Content capture: `{"enabled": false, "inputMessages": false, "outputMessages": false, "systemPrompt": false, "toolInputs": false, "toolOutputs": false}`
- External export: `False`
- Raw prompt/tool/system capture: `False`

## Validation

- `openclaw gateway status` running loopback-only
- `openclaw plugins doctor` no plugin issues detected
- `openclaw config get diagnostics.otel` shows metrics/traces enabled, logs/content capture off
- local collector received OTLP `/v1/metrics` receipts
