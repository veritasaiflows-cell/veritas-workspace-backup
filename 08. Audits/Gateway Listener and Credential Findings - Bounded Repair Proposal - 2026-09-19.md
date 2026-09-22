# Gateway Listener and Credential Findings — Bounded Repair Proposal

- Date: 2026-09-19 (America/Phoenix)
- Trigger: two adjacent findings from the read-only Grok reliability investigation (2026-09-19)
- Status: investigation complete, read-only. **No credential, config, service, startup, or runtime change made.**
- Authority: this document is a proposal. It grants no approval and performs no action.
- Provenance boundary: the Grok incident proved socket resets. It did **not** establish these findings as their cause, and nothing here claims it did.

## 1. Scope and method

Fresh read-only probes were run before any conclusion. No secret value was read, printed, or written by this
investigation. Secret-bearing fields were assessed by type, length, character class, Shannon entropy,
cross-location hash comparison, and bounded dictionary identity tests only.

Commands used (all read-only, no mutating flags):

- `openclaw --version`, `openclaw gateway status --deep`, `openclaw doctor --lint`
- `openclaw config validate`, `openclaw secrets audit --check`
- `schtasks /Query /TN "OpenClaw Gateway" /V|/XML`
- `Get-NetTCPConnection`, `Get-CimInstance Win32_Process`, `Get-Acl`
- bounded `Select-String` over the day's gateway logs

Explicitly **not** run, per instruction: `openclaw doctor --fix`, `openclaw gateway install --force`, any
start/stop/restart of this Gateway, any permission broadening.

## 2. Finding A — "stopped task, reachable listener"

**Verdict: the contradiction is real but it is a reporting artifact plus a genuine orphaned process. It is not
evidence of two competing gateways, and it is not resolved as harmless.**

Facts established:

| Fact | Value |
|---|---|
| Listener on 127.0.0.1:18789 | pid 4912, `node.exe` |
| pid 4912 command line | `node ...\openclaw\openclaw.mjs gateway run` |
| pid 4912 start time | 2026-09-18 23:26:35 local |
| pid 4912 parent chain | `powershell.exe` pid 15020 (created 23:26:27, still alive) → `explorer.exe` pid 1584 |
| pid 4912 Windows session | 3 |
| Scheduled task `\OpenClaw Gateway` last run | 2026-09-18 23:25:49 local (06:25:49Z) |
| Scheduled task last result | **78** |
| Scheduled task state | Enabled, Ready, `InteractiveToken`, runs as `RQs_Business\Veritas` |
| Task action | `C:\Users\Veritas\.openclaw\gateway.vbs` → `gateway.cmd` → `node gateway` |
| Triggers | LogonTrigger + repetition `PT1M` |
| `MultipleInstancesPolicy` / `ExecutionTimeLimit` | `IgnoreNew` / `PT0S` |
| Only listener on 18789 | pid 4912 (no second gateway process exists) |
| Gateway bind | loopback only (`127.0.0.1`), port 18789 — preserved, correctly narrow |

Interpretation:

1. `gateway status --deep` reports `Runtime: stopped (state Ready, last run 78)` because it reads **scheduled-task
   state**, while `Connectivity probe: ok` reflects **whatever is actually listening**. Those are two different
   questions. That is the whole of the apparent contradiction — not a phantom second gateway.
2. The live gateway was **not** started by the scheduled task. Its parent is an interactively-opened
   `powershell.exe` under `explorer.exe`. A task-launched process would have shown `wscript.exe`/`cmd.exe` as
   parent. So the task's own start at 23:25:49 exited 78, and a separate interactive launch ~46s later took over
   the port.
3. **Material risk:** the process serving this Gateway is an interactive child of a user shell in session 3. It is
   not managed by the service, so it will not survive that shell exiting or a logoff, and the scheduled task has
   not demonstrated a working recovery (its only recent recorded result is 78).
4. **Not established:** the meaning of exit code 78. A bounded search of the installed `dist` and docs for
   `EX_CONFIG`, `CONFIG_ERROR`, `configuration error`, and `78` produced **no** matching definition, and the
   day's gateway logs contain no `EADDRINUSE` / "address in use" / "exited with code 78" entry in the relevant
   window. `Microsoft-Windows-TaskScheduler/Operational` is **disabled** (`IsEnabled=False`), so task exit history
   is unavailable. **Root cause is unresolved and is stated as unresolved.** A port-conflict hypothesis is
   plausible but unproven, and it is not the same thing as evidence.

## 3. Finding B — managed credential embedded in service environment

**Verdict: confirmed, real credential, currently duplicated in two plaintext locations.**

Facts established (value-free):

| Location | Form | Identity |
|---|---|---|
| `~/.openclaw/gateway.cmd` line 4 | inline `set "TELEGRAM_BOT_TOKEN=..."` | 46 chars, matches Telegram bot-token shape (`<bot_id>:<secret>`), sha256[0:12] `72a27ce5144d` |
| `gateway.cmd` line 3 | `OPENCLAW_SERVICE_MANAGED_ENV_KEYS=TELEGRAM_BOT_TOKEN` | declares the key as service-managed |
| User-scope environment (`HKCU`) | persistent user env var | **byte-identical** to the `gateway.cmd` literal (sha256[0:12] `72a27ce5144d`) |
| `openclaw.json` → `channels.telegram.botToken` | **already a SecretRef object** `{source:"env", provider:"default", id:"TELEGRAM_BOT_TOKEN"}` | resolves via `secrets audit`: `unresolved=0` |
| Machine-scope environment | absent | — |
| `gateway.cmd` / `gateway.vbs` ACL | `NT AUTHORITY\SYSTEM` and `RQs_Business\Veritas`, FullControl | any process running as Veritas can read the literal |

Interpretation:

- The credential is **real**, not a placeholder, and it is **live**: `channels.telegram.botToken` already resolves
  to it through an `env` SecretRef, and Telegram polling is active in the logs.
- The doctor warning is accurate. `gateway.cmd` is a plaintext secret store on disk, readable by every process
  running under the Veritas account — including any agent with filesystem tools. This is precisely the
  "agents or workspace tools may see these keys" exposure the lint calls out.
- The inline literal is **redundant**: the same value already exists in User-scope env, which the task inherits
  (`LogonType=InteractiveToken`, `Run As User=RQs_Business\Veritas`). That redundancy is what makes a low-risk
  removal possible without touching the task definition.
- `openclaw secrets store list` shows the protected store is **empty**, so a `{source:"store"}` migration requires
  populating it first.

## 4. Finding C — `doctor --lint` plaintext config fields

`openclaw config validate` → valid, exit 0. `openclaw secrets audit --check` → findings: plaintext=11,
unresolved=0, shadowed=0, storeResidue=0, legacy=5.

Of the two lint-flagged fields, **one is a real credential and one is a non-secret placeholder**:

| Field | Assessment | Evidence |
|---|---|---|
| `gateway.auth.token` | **REAL credential, plaintext** | 48 chars, pure hex, 29/48 digits, entropy 3.81 bits, char classes `lower+digit`, generated-looking; no dictionary match; `gateway.auth.mode=token` so this is the live auth secret |
| `models.providers.ollama.apiKey` | **PLACEHOLDER, not a secret** | 12 chars, lowercase+hyphen only, entropy 2.36 bits, single char = 33% of the value, zero digits; **exact case-sensitive match** to the non-secret literal `ollama-local` across a 324-candidate generated dictionary. Endpoint is `http://127.0.0.1:11434` (loopback), Ollama errors in the log: 0 auth failures in 39 related lines |

So the lint count of 2 flagged fields overstates real exposure by one. `ollama.apiKey` should be reclassified,
not treated as an incident.

Adjacent plaintext findings surfaced by the same audit, **outside the two flagged fields** and worth a follow-up
(not in this proposal's scope):

- `~/.openclaw/agents/main/agent/models.json` → `providers.kimi-code.apiKey` (plaintext).
- SQLite auth profiles holding plaintext API keys: `openai`, `ollama-cloud`, `google`, `kimi`, `openrouter`,
  `meta`, `kimi-code`, `opencode`, `opencode-go`, `zai`.
- 5 legacy residues: OAuth credentials for `openai`/`xai`/`google` in `state/openclaw.sqlite`, plus two
  `auth-profiles.json.sqlite-import.*.bak` / `auth-state.json.sqlite-import.*.bak` archives. The audit itself
  marks OAuth as out of scope for static SecretRef migration.

Also observed, benign: the OTEL Collector Watchdog scheduled task is detected by status as an "other
gateway-like service". It is a workspace watchdog, not a second gateway.

## 5. Bounded repair proposal

Three independent workstreams, ordered by risk benefit. **Each requires explicit owner approval. Nothing here has
been executed.**

### WS1 — Remove the duplicated plaintext Telegram token from the service launcher

Preferred end state: `channels.telegram.botToken` resolves from the protected store; the inline literal and the
User-scope env copy are both removed.

- 5.1 Back up `~/.openclaw/openclaw.json` and `~/.openclaw/gateway.cmd` to a timestamped path; record sha256 of
  both.
- 5.2 `openclaw secrets store set TELEGRAM_BOT_TOKEN --kind secret` with the value supplied by **masked prompt or
  stdin/file**, never `--value` and never through chat.
- 5.3 Repoint the config field to `{source:"store", provider:"default", id:"TELEGRAM_BOT_TOKEN"}` (the
  store-backed SecretRef form).
- 5.4 Remove line 4 from `gateway.cmd`. Either drop `TELEGRAM_BOT_TOKEN` from
  `OPENCLAW_SERVICE_MANAGED_ENV_KEYS` on line 3, or regenerate the launcher properly — the latter is a service
  change and is **explicitly out of scope here**.
- 5.5 Delete the User-scope `TELEGRAM_BOT_TOKEN` environment variable so only the protected store holds it.
- 5.6 `openclaw secrets reload` (runtime re-resolve, no config write, no restart), then verify.

Fallback, if the store path fails verification: keep the `env` SecretRef and only delete the inline `gateway.cmd`
literal (5.4), relying on the User-scope env var. Smaller change, still removes the on-disk plaintext copy.

### WS2 — Move `gateway.auth.token` to a SecretRef

Highest-value single fix, and the one with the sharpest failure mode: this is the live gateway auth secret.

- 5.7 Same backup step as 5.1.
- 5.8 Migrate via the sanctioned one-way path: `openclaw secrets configure --plan-out <path>` (interactive, requires
  a TTY) → review plan → `openclaw secrets apply --from <path> --dry-run` → apply. The tooling moves the value into
  the store and scrubs the plaintext residue **without the value entering model context**.
- 5.9 Verify the gateway still accepts a loopback client before declaring success.
- **Risk:** if the ref fails to resolve while `gateway.auth.mode=token`, the Gateway can fail closed and lock out
  loopback clients. Mitigation: do not restart the Gateway in the same step; stage the change, run
  `openclaw secrets reload`, verify, and only then consider a managed restart separately.

### WS3 — Reclassify the Ollama placeholder (no migration)

- 5.10 No SecretRef migration for `models.providers.ollama.apiKey`. It is the literal `ollama-local` against a
  loopback endpoint with no auth failures. Migrating a placeholder adds store ceremony and hides a non-secret.
- 5.11 Optional tidy (cosmetic, low value): replace it with an explicit documented non-secret marker so
  `doctor --lint` stops reporting it, or accept the persistent lint warning as a known false positive.

### Not proposed / out of scope

- Regenerating the service launcher (`openclaw gateway install --force`).
- Any start, stop, or restart of this Gateway.
- Changing `gateway.bind` (loopback-only binding is correct and must be preserved).
- Broadening any tool or filesystem permission.
- `doctor --fix` (it would also attempt unrelated migrations: TOOLS.md merges, HEARTBEAT.md→cron scratch).

## 6. Rollback

| Step | Rollback |
|---|---|
| 5.1 / 5.7 backups | Restoration source of truth; keep until verification passes |
| 5.2 store set | `openclaw secrets store rm TELEGRAM_BOT_TOKEN` |
| 5.3 config repoint | restore `openclaw.json` from the 5.1 backup (or `openclaw config set` back to the `env` ref) |
| 5.4 gateway.cmd edit | restore `gateway.cmd` from the 5.1 backup |
| 5.5 env var delete | re-create the User-scope variable (value from the 5.1 backup of `gateway.cmd`) |
| 5.8 auth token migration | restore `openclaw.json` from the 5.7 backup; `secrets store rm` the new entry |
| runtime effect | `openclaw secrets reload` to re-publish a resolved snapshot |

Every rollback is a file restore or a store `rm`. No irreversible step is proposed.

## 7. Verification

- `openclaw config validate` → exit 0.
- `openclaw secrets audit --check` → the specific findings for `gateway.auth.token` and
  `channels.telegram.botToken` absent; expect exit 1 to persist only for the remaining out-of-scope findings
  listed in §4.
- `openclaw secrets reload --json` → snapshot published with no unresolved refs.
- Telegram: confirm polling continues and no auth error appears in the gateway log.
- Gateway auth: confirm a loopback client still authenticates under `mode=token`.
- Launcher hygiene: confirm `gateway.cmd` no longer contains a token-shaped literal
  (pattern count `\d{6,}:[A-Za-z0-9_-]{30,}` → 0, currently 1).
- Regression: confirm no new `EADDRINUSE` / bind failure appears after any later managed restart.

## 8. Open items requiring an owner decision

1. **Approve WS1, WS2, WS3 individually.** They are separable; WS2 carries the real failure mode.
2. **The orphaned interactive Gateway.** Decide whether to move the running Gateway under proper service
   ownership. This is a service/runtime change and needs separate approval; leaving it as-is means the Gateway
   does not survive that shell or a logoff, and its auto-recovery is unproven.
3. **Exit code 78.** Root cause unresolved. The cheap evidence path is enabling
   `Microsoft-Windows-TaskScheduler/Operational` (currently disabled) and capturing the launcher's output on the
   next task start — both are service-level changes needing approval.
4. **Adjacent plaintext exposures** in §4 (agent `models.json`, SQLite auth profiles, legacy backups) are not
   covered by this proposal and merit their own bounded pass.
