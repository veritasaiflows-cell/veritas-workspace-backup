# Telemetry Audit Mode Plan — disabled-by-default prototype

Created: 2026-05-24 22:34 MST  
Status: **plan/prototype only** — no config/runtime mutation performed.

## Workflow under review
Short-lived local-only telemetry/audit mode for operator review.

## Current phase
Manual review artifact only.

## Recommended next phase
Only after Randall explicitly approves: create or apply an exact **disabled-by-default** local config patch template using the proper config/schema path. Enabling any capture is a separate approval.

## Safe automation boundary
Allowed now:
- Keep `tmp/telemetry-audit-mode-plan.json` and this note as local review artifacts.
- Validate JSON and confirm all default capture/export flags are false.

Requires explicit approval:
- Any config/runtime patch.
- Any enabling of audit mode.
- Any log, prompt, model-output, tool-call, system-message, config, or environment capture.
- Any external/network export.
- Any retention beyond the approved TTL.

Blocked by default:
- Credential/secret capture.
- Silent background collection.
- Live brokerage/account telemetry capture.
- External transmission of raw prompts, conversations, tool payloads, credentials, or logs.

## Default flags
All false by default:
- `enabled=false`
- `logs=false`
- `capture_prompts=false`
- `capture_model_outputs=false`
- `capture_tool_calls=false`
- `capture_system_messages=false`
- `capture_config=false`
- `capture_environment=false`
- `external_export=false`
- `network_export=false`
- `persistent_background_collection=false`

## Approval language
Template-only approval:
> I approve creating a local disabled-by-default audit-mode config patch template only. Do not enable audit mode, do not capture logs/prompts/model/tool/system content, and do not export externally.

Short-lived local test approval:
> I approve enabling local-only telemetry audit mode for this exact session/window: `<scope>`. TTL: `<minutes, max 60>`. Capture flags allowed: `<explicit list>`. External export remains false. Redact secrets and credentials. Auto-disable and delete staged raw captures at TTL expiry.

External export:
> External export is not approved unless I give a separate exact destination, data fields, redaction policy, TTL, and reason. No inferred approval.

## TTL, rollback, retention, redaction
- Default TTL: `0` minutes / disabled.
- Recommended max test TTL: `60` minutes.
- Auto-disable required at TTL expiry.
- Rollback required after any test: restore prior config or remove audit block, verify all flags false, delete raw captures unless explicitly approved otherwise.
- Default retention: none.
- Local test retention: delete raw local captures at TTL expiry; retain only a redacted local summary if approved.
- Always redact/drop: tokens, API keys, OAuth material, passwords, cookies, session IDs, brokerage identifiers, live endpoints, unnecessary personal data, hidden/system instructions unless exact owner-approved local redacted handling requires it.

## Optional local config patch template — do not apply without approval
```json
{
  "telemetryAuditMode": {
    "enabled": false,
    "ttlMinutes": 0,
    "localOnly": true,
    "capture": {
      "logs": false,
      "prompts": false,
      "modelOutputs": false,
      "toolCalls": false,
      "systemMessages": false,
      "config": false,
      "environment": false
    },
    "export": {
      "external": false,
      "network": false,
      "destination": null
    },
    "retention": {
      "raw": "delete_at_ttl_or_disabled",
      "summary": "disabled_unless_approved",
      "maxMinutes": 60
    },
    "redaction": {
      "enabled": true,
      "dropSecrets": true,
      "dropCredentials": true,
      "dropHiddenInstructionsByDefault": true
    },
    "rollback": {
      "autoDisableOnExpiry": true,
      "requireBackupBeforeApply": true,
      "postRollbackValidationRequired": true
    }
  }
}
```

## Stop lines
Stop and ask Randall before:
- Touching OpenClaw config/runtime.
- Enabling capture or export.
- Extending TTL/retention.
- Capturing prompts, model outputs, tool payloads, system/developer messages, or sensitive runtime state.
- Adding network destinations or sync.

## Trust gates still missing
- Owner approval for any config/runtime mutation.
- Official config schema/path inspection.
- Backup/rollback artifact.
- Runtime validation after any future approved patch.

## Validation/evidence
Planned validation:
1. Parse JSON.
2. Assert every default capture/export flag is false.
3. Assert optional template has `enabled=false`, `ttlMinutes=0`, `localOnly=true`, and external/network export false.

