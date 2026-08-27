# OTEL Emission Producer Audit - 2026-07-03

## Scope

Review-only audit for Randall's request:

> Run a review-only OTEL emission-producer audit to find where approved metadata fields are supposed to enter the collector stream.

This audit inspects local proof only. It does not mutate collector config, runtime config, Gateway config, cron schedules, services, external exporters, finance/canon/portfolio state, paper/live/account state, or Skill Workshop proposals.

## Bottom Line

The approved metadata fields are supposed to enter the local collector stream from OpenClaw Gateway OTEL instrumentation, over local OTLP HTTP to the collector receiver at `127.0.0.1:4318`.

The fields are already present in the collector file-exported trace and metric streams:

- `tmp/otel-collector/traces.jsonl`
- `tmp/otel-collector/metrics.jsonl`

The current warning in `scripts/otel_runtime_metadata_probe.py` is therefore a measurement-source problem, not proof that the producer is absent. The probe is checking collector debug stderr logs, especially `tmp/otel-collector/local-restart.err.log`, where the collector debug exporter is set to `verbosity: basic`. Basic debug output reports counts such as spans, metrics, and data points, but not span or metric attributes. The detailed approved metadata is in the JSONL file exporters instead.

## Evidence Chain

### 1. Owner Packet

Source: `tmp/otel-field-depth-limited-owner-packet.json`

Observed posture:

- Packet status: `approved_enabled`
- Validation: `ok`
- `authority_boundary.owner_approved_local_depth_expansion`: `true`
- External export: not approved
- Collector/runtime mutation from this audit: not approved
- Required boundary: local-only, metadata-only, no raw prompt, response, tool payload, system prompt, secrets, or headers

The packet approves local metadata depth, not unbounded content capture and not external telemetry export.

### 2. Collector Receiver And Exporters

Source: `tools/otelcol/openclaw-local-otel-runtime-metadata.yaml`

Relevant collector path:

- OTLP receiver endpoint: `127.0.0.1:4318`
- Trace pipeline exporters: `debug`, `file/traces`
- Metric pipeline exporters: `debug`, `file/metrics`
- Log pipeline exporters: `file/logs`
- File exporter targets:
  - traces: `tmp/otel-collector/traces.jsonl`
  - metrics: `tmp/otel-collector/metrics.jsonl`
  - logs: `tmp/otel-collector/logs.jsonl`
- Debug exporter verbosity: `basic`

Interpretation:

- The collector is configured to preserve detailed trace and metric payloads in local JSONL files.
- The collector debug stderr path is expected to be shallow because `verbosity: basic` omits attributes.
- The empty `logs.jsonl` file is not a blocker for this audit because the observed approved metadata is carried by traces and metrics.

### 3. OpenClaw OTEL Producer Documentation

Source: `C:\Users\Veritas\AppData\Roaming\npm\node_modules\openclaw\docs\gateway\opentelemetry.md`

The installed OpenClaw documentation identifies the producer-side OTEL surfaces:

- Environment route includes `OTEL_EXPORTER_OTLP_ENDPOINT`, signal-specific OTLP endpoints, `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_PROTOCOL`, and `OPENCLAW_OTEL_PRELOADED`.
- Privacy posture says raw model/tool content is not exported by default.
- Metrics include approved metadata fields such as:
  - `openclaw.tokens`
  - `openclaw.cost.usd`
  - `openclaw.run.duration_ms`
  - `openclaw.context.tokens`
  - `gen_ai.client.token.usage`
  - `gen_ai.client.operation.duration`
  - `openclaw.model_call.duration_ms`
  - `openclaw.model_call.request_bytes`
  - `openclaw.model_call.response_bytes`
  - `openclaw.model_call.time_to_first_byte_ms`
  - `openclaw.skill.used`
  - `openclaw.tool.execution.duration_ms`
- Spans include approved metadata fields on:
  - `openclaw.model.usage`
  - `openclaw.run`
  - `openclaw.model.call`
  - `openclaw.tool.execution`
  - `openclaw.context.assembled`
  - `openclaw.tool.loop`

This documentation matches the fields observed in the local collector JSONL files.

### 4. Actual Collector Output

Review scan inspected these local files:

- `tmp/otel-collector/local-restart.err.log`
- `tmp/otel-collector/collector.err.log`
- `tmp/otel-collector/traces.jsonl`
- `tmp/otel-collector/metrics.jsonl`
- `tmp/otel-collector/logs.jsonl`

Observed results:

| File | Approved Metadata Observed | Notes |
|---|---:|---|
| `tmp/otel-collector/local-restart.err.log` | 0 fields | Fresh, but debug stderr is basic count output only. |
| `tmp/otel-collector/collector.err.log` | 0 fields | Older debug stderr; no detailed attributes. |
| `tmp/otel-collector/traces.jsonl` | 21 field families | Detailed trace attributes present. |
| `tmp/otel-collector/metrics.jsonl` | 26 field families | Detailed metric attributes present. |
| `tmp/otel-collector/logs.jsonl` | 0 fields | Empty; not the active metadata carrier. |

Representative trace attributes observed:

- `openclaw.provider=openai`
- `openclaw.model=gpt-5.5`
- `gen_ai.system=openai`
- `gen_ai.request.model=gpt-5.5`
- `gen_ai.operation.name=chat`
- `openclaw.api=openai-chatgpt-responses`
- `openclaw.transport=stdio`
- `openclaw.channel=webchat`
- `openclaw.trigger=user`
- `openclaw.outcome=completed`
- `openclaw.tokens.input`
- `openclaw.tokens.output`
- `openclaw.tokens.cache_read`
- `openclaw.tokens.cache_write`
- `openclaw.tokens.total`
- `gen_ai.usage.input_tokens`
- `gen_ai.usage.output_tokens`
- `gen_ai.usage.cache_read.input_tokens`
- `openclaw.toolName`
- `openclaw.tool.source`
- `gen_ai.tool.name`

Representative metric names observed:

- `openclaw.model_call.duration_ms`
- `openclaw.model_call.request_bytes`
- `openclaw.model_call.response_bytes`
- `openclaw.model_call.time_to_first_byte_ms`
- `gen_ai.client.operation.duration`
- `gen_ai.client.token.usage`
- `openclaw.tokens`
- `openclaw.cost.usd`
- `openclaw.tool.execution.duration_ms`
- `openclaw.run.duration_ms`
- `openclaw.context.tokens`

The producer path is therefore active for trace and metric streams.

## Findings

### Finding 1: Producer Source Is OpenClaw Gateway

The emission producer is OpenClaw Gateway runtime instrumentation. The local trace resource identifies an OpenClaw process and `openclaw` instrumentation scope, with spans such as `openclaw.model.call`, `openclaw.run`, `openclaw.model.usage`, and `openclaw.tool.execution`.

### Finding 2: Approved Metadata Enters Through OTLP HTTP And File Exporters

The local collector route is:

1. OpenClaw Gateway emits OTEL spans and metrics.
2. Collector receives via OTLP HTTP at `127.0.0.1:4318`.
3. Collector writes detailed attributes to:
   - `tmp/otel-collector/traces.jsonl`
   - `tmp/otel-collector/metrics.jsonl`

This is the evidence path future probes should inspect first.

### Finding 3: Current Probe Watches The Wrong Evidence Surface

`scripts/otel_runtime_metadata_probe.py` currently reports:

- owner packet approved/enabled: true
- runtime metadata observed: false
- allowed field count: 0
- diagnosis: `collector_debug_log_current_allowed_fields_absent`

That diagnosis is accurate only for the debug stderr stream. It is misleading for the whole collector path because approved fields are present in the file-exported JSONL streams.

### Finding 4: Debug Basic Verbosity Explains The False Negative

The collector debug exporter is configured with `verbosity: basic`. Basic debug output reports counts like resource spans, spans, metrics, and data points, not field-level attributes. The absence of approved fields in `local-restart.err.log` is expected under this setting.

Changing debug verbosity could make stderr easier to probe, but that would be collector config mutation. This audit does not recommend that as the first repair because a no-config repair exists: read the existing JSONL exporters.

### Finding 5: Count-Only System Prompt Marker Is Not Raw Prompt Capture

A simple text scan can flag the string `system_prompt` in `traces.jsonl`, but the observed field is count-only metadata such as `openclaw.context.system_prompt_chars`, not raw system prompt content.

This aligns with the existing probe's safer filtering logic: count-only prompt/system-prompt size metadata is allowed; raw prompt/system prompt content remains blocked.

## Recommendations

### P0: Patch The Runtime Metadata Probe To Read JSONL Exporters

Update `scripts/otel_runtime_metadata_probe.py` so its evidence sources include:

- `tmp/otel-collector/traces.jsonl`
- `tmp/otel-collector/metrics.jsonl`
- current `tmp/otel-collector/*.err.log` files as secondary debug-health evidence

Expected result:

- `runtime_metadata_observed` should become true when approved fields appear in the local file exporters.
- The probe should retain raw-content and secret/header marker checks.
- The probe should continue filtering count-only prompt/system-prompt character fields as allowed metadata, not raw content.

No collector config mutation is required for this fix.

### P1: Add Regression Coverage For Basic-Debug False Negatives

Add or update tests so this state is handled correctly:

- debug stderr contains only basic count lines
- `traces.jsonl` and/or `metrics.jsonl` contains approved metadata fields
- probe returns observed metadata true, with a diagnosis that distinguishes file-export success from debug-stderr absence

### P1: Split The Diagnosis Labels

The current diagnosis label should be split into more precise cases:

- `debug_basic_attributes_hidden_file_export_observed`
- `debug_log_absent_or_stale`
- `file_export_absent`
- `collector_ingestion_observed_no_approved_fields`
- `producer_absent_or_not_instrumented`

This prevents WF74/WF88 from treating a measurement-source limitation as a runtime producer failure.

### P2: Keep Collector Debug Verbosity Changes Owner-Gated

Only consider debug verbosity changes if JSONL probing is insufficient. That would be collector config mutation and should stay owner-gated with preview, rollback, and validator proof.

## Boundary Preserved

This audit performed local review and proof interpretation only. It did not:

- mutate OTEL collector config
- mutate OpenClaw runtime or Gateway config
- restart collector or services
- enable external export
- expand raw prompt/response/tool capture
- mutate cron schedules
- mutate finance/canon/portfolio/cash/sizing/risk state
- perform paper/live/account/brokerage action
- apply/reject/quarantine Skill Workshop proposals
- delete, archive, or move files

## Next Action

Proceed with a narrow P0 probe patch:

> Teach `scripts/otel_runtime_metadata_probe.py` to read the existing trace and metric JSONL file exporters before declaring approved/enabled runtime metadata absent.

That should close the current approved/enabled-vs-observed OTEL false negative without touching collector configuration.
