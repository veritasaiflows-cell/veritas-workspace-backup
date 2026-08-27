import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { basename, dirname, extname, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
type JsonObject = { [key: string]: JsonValue };

type RegistrySource = {
  key: string;
  title: string;
  path: string;
  kind: "json" | "sqlite" | "file";
  required: boolean;
  max_age_hours?: number | null;
  group: string;
  role: string;
};

type SourceState = RegistrySource & {
  exists: boolean;
  absolute_path: string;
  mtime_utc?: string;
  age_hours?: number;
  stale: boolean;
  parseable_json: boolean;
  status?: unknown;
  schema?: unknown;
  validation_status?: unknown;
  error?: string;
  payload?: JsonObject;
};

type Registry = {
  schema: string;
  status: string;
  purpose: string;
  workspace_root: string;
  default_refresh_seconds?: number;
  authority_boundary?: Record<string, boolean>;
  sources: RegistrySource[];
  ui?: {
    title?: string;
    subtitle?: string;
    primary_owner?: string;
    default_tab?: string;
  };
};

const __dirname = dirname(fileURLToPath(import.meta.url));
const appRoot = resolve(__dirname, "..");
const workspaceRoot = resolve(appRoot, "..", "..");
const defaultRegistryPath = resolve(workspaceRoot, "state", "pm-cockpit-source-registry.json");
const registryPath = resolveWorkspacePath(process.env.PM_COCKPIT_SOURCE_REGISTRY || defaultRegistryPath);
const port = Number(process.env.PORT || "8765");
const execFileAsync = promisify(execFile);
const sqliteBinary = process.env.SQLITE3_BIN || "sqlite3";
const nodeBinary = process.env.NODE_BIN || process.execPath;
const roamingAppData = process.env.APPDATA || resolve(process.env.USERPROFILE || "", "AppData", "Roaming");
const openclawCliPath = process.env.OPENCLAW_CLI_PATH || resolve(roamingAppData, "npm", "node_modules", "openclaw", "openclaw.mjs");
const pythonBinary = process.env.PYTHON_BIN || "python";
const financeCanonDbPath = "state/finance/finance-canon.sqlite";
const commandCenterRoot = resolve(workspaceRoot, "10. Deliverables", "Command Center");
const talkLiteRoot = resolve(workspaceRoot, "tmp", "talk-lite");
const talkLiteAudioRoot = resolve(talkLiteRoot, "audio");
const talkLiteTranscriptRoot = resolve(talkLiteRoot, "transcripts");
const talkLiteTtsRoot = resolve(talkLiteRoot, "tts");
const talkLiteTurnRoot = resolve(talkLiteRoot, "turns");
const talkLiteSessionKey = process.env.TALK_LITE_SESSION_KEY || "agent:main:talk-lite";
const talkLiteMaxAudioBytes = Number(process.env.TALK_LITE_MAX_AUDIO_BYTES || 25_000_000);
const talkLiteAgentTimeoutSeconds = Number(process.env.TALK_LITE_AGENT_TIMEOUT_SECONDS || 600);
const talkLiteBoundary = {
  local_only: true,
  browser_surface: "pm_control_cockpit",
  voice_mode: "talk_lite_push_to_talk",
  realtime_voice_provider_required: false,
  realtime_openai_voice_api_used: false,
  local_transcription_allowed: true,
  microsoft_tts_allowed: true,
  veritas_gpt_text_turn_allowed: true,
  review_only: true,
  transcript_confirmation_default: true,
  capital_deployment_allowed: false,
  canon_or_portfolio_mutation_allowed: false,
  config_auth_runtime_mutation_allowed: false,
  paper_or_live_execution_allowed: false,
  brokerage_or_account_action_allowed: false,
  owner_approval_inferred: false,
};

function asObject(value: unknown): JsonObject {
  return value && typeof value === "object" && !Array.isArray(value) ? value as JsonObject : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function resolveWorkspacePath(pathValue: string): string {
  const candidate = isAbsolute(pathValue) ? resolve(pathValue) : resolve(workspaceRoot, pathValue);
  const relative = candidate.toLowerCase().startsWith(workspaceRoot.toLowerCase());
  if (!relative) {
    throw new Error(`Refusing to read outside workspace: ${pathValue}`);
  }
  return candidate;
}

function relativeWorkspacePath(pathValue: string): string {
  return pathValue.replace(workspaceRoot, "").replace(/^\\+/, "").replaceAll("\\", "/");
}

function utcStamp(): string {
  return new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function safeLabel(value: string, fallback = "audio"): string {
  const cleaned = basename(value || fallback).replace(/[^a-zA-Z0-9_.-]/g, "-").replace(/-+/g, "-");
  return cleaned.slice(0, 80) || fallback;
}

function extensionFromMime(mimeType: string, fileName = ""): string {
  const ext = extname(fileName).toLowerCase();
  if ([".webm", ".ogg", ".oga", ".opus", ".mp3", ".wav", ".m4a"].includes(ext)) return ext;
  const lower = mimeType.toLowerCase();
  if (lower.includes("webm")) return ".webm";
  if (lower.includes("ogg") || lower.includes("opus")) return ".ogg";
  if (lower.includes("mpeg") || lower.includes("mp3")) return ".mp3";
  if (lower.includes("wav")) return ".wav";
  if (lower.includes("m4a") || lower.includes("mp4")) return ".m4a";
  return ".webm";
}

async function ensureTalkLiteDirs() {
  await Promise.all([
    mkdir(talkLiteAudioRoot, { recursive: true }),
    mkdir(talkLiteTranscriptRoot, { recursive: true }),
    mkdir(talkLiteTtsRoot, { recursive: true }),
    mkdir(talkLiteTurnRoot, { recursive: true }),
  ]);
}

async function readRequestJson(request: IncomingMessage, maxBytes = talkLiteMaxAudioBytes + 200_000): Promise<JsonObject> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    size += buffer.length;
    if (size > maxBytes) throw new Error("request_body_too_large");
    chunks.push(buffer);
  }
  const textBody = Buffer.concat(chunks).toString("utf8").trim();
  if (!textBody) return {};
  return asObject(JSON.parse(textBody));
}

function extractBase64(value: unknown): string {
  const raw = String(value || "");
  const comma = raw.indexOf(",");
  const body = comma >= 0 ? raw.slice(comma + 1) : raw;
  return body.replace(/\s+/g, "");
}

function safeTalkLitePath(pathValue: string): string {
  const absolute = resolveWorkspacePath(pathValue);
  if (!absolute.toLowerCase().startsWith(talkLiteRoot.toLowerCase())) {
    throw new Error(`Refusing Talk Lite path outside tmp/talk-lite: ${pathValue}`);
  }
  return absolute;
}

function firstPayloadText(payload: JsonObject): string {
  const result = asObject(payload.result);
  const meta = asObject(result.meta);
  const payloads = asArray(result.payloads).map(asObject);
  return String(
    meta.finalAssistantVisibleText ||
    meta.finalAssistantRawText ||
    payloads.find((item) => item.text)?.text ||
    "",
  ).trim();
}

function spokenText(value: string): string {
  const cleaned = value.replace(/\s+/g, " ").trim();
  if (cleaned.length <= 1400) return cleaned;
  return `${cleaned.slice(0, 1390).trim()}...`;
}

async function runJsonCommand(command: string, args: string[], timeoutMs: number): Promise<JsonObject> {
  const { stdout, stderr } = await execFileAsync(command, args, {
    cwd: workspaceRoot,
    windowsHide: true,
    timeout: timeoutMs,
    maxBuffer: 20_000_000,
  });
  const trimmed = stdout.trim();
  if (!trimmed) {
    throw new Error(`empty_command_output:${command}:${stderr.slice(-1000)}`);
  }
  return asObject(JSON.parse(trimmed));
}

async function runOpenclawJson(args: string[], timeoutMs: number): Promise<JsonObject> {
  return runJsonCommand(nodeBinary, [openclawCliPath, ...args], timeoutMs);
}

async function synthesizeTalkLite(textValue: string, turnId: string): Promise<JsonObject> {
  await ensureTalkLiteDirs();
  const outputPath = resolve(talkLiteTtsRoot, `${turnId}.mp3`);
  const payload = await runOpenclawJson([
    "infer",
    "tts",
    "convert",
    "--json",
    "--output",
    outputPath,
    "--text",
    spokenText(textValue),
  ], 120_000);
  const outputs = asArray(payload.outputs).map(asObject);
  const firstOutput = outputs[0] || {};
  const pathValue = String(firstOutput.path || outputPath);
  return {
    ...payload,
    audio_path: relativeWorkspacePath(pathValue),
    audio_url: `/api/talk-lite/audio?path=${encodeURIComponent(relativeWorkspacePath(pathValue))}`,
  };
}

async function transcribeTalkLiteAudio(request: IncomingMessage): Promise<JsonObject> {
  await ensureTalkLiteDirs();
  const body = await readRequestJson(request);
  const audioBase64 = extractBase64(body.audio_base64 || body.data_base64 || body.audio);
  if (!audioBase64) throw new Error("missing_audio_base64");
  const audioBuffer = Buffer.from(audioBase64, "base64");
  if (!audioBuffer.length) throw new Error("empty_audio_payload");
  if (audioBuffer.length > talkLiteMaxAudioBytes) throw new Error(`audio_payload_too_large:${audioBuffer.length}`);

  const sourceName = safeLabel(String(body.filename || body.name || "talk-lite.webm"));
  const extension = extensionFromMime(String(body.mime_type || body.type || ""), sourceName);
  const turnId = `${utcStamp()}-${randomUUID().slice(0, 8)}`;
  const audioPath = resolve(talkLiteAudioRoot, `${turnId}-${sourceName.replace(/\.[^.]+$/, "")}${extension}`);
  const transcriptPath = resolve(talkLiteTranscriptRoot, `${turnId}.json`);
  await writeFile(audioPath, audioBuffer);

  const payload = await runJsonCommand(pythonBinary, [
    "scripts\\local_audio_transcriber.py",
    relativeWorkspacePath(audioPath),
    "--out",
    relativeWorkspacePath(transcriptPath),
    "--write",
    "--validate",
  ], 240_000);
  const transcript = asObject(payload.transcription);
  const textValue = String(asObject(payload.summary).text || transcript.text || "").trim();
  return {
    schema: "veritas.talk_lite_transcription.v1",
    status: textValue ? "ok" : "empty_transcript",
    generated_at_utc: new Date().toISOString(),
    turn_id: turnId,
    authority_boundary: talkLiteBoundary,
    audio_path: relativeWorkspacePath(audioPath),
    transcript_path: relativeWorkspacePath(transcriptPath),
    transcript: textValue,
    local_audio_transcriber: payload,
  };
}

async function askTalkLiteVeritas(request: IncomingMessage): Promise<JsonObject> {
  await ensureTalkLiteDirs();
  const body = await readRequestJson(request, 400_000);
  const transcript = String(body.transcript || body.message || "").trim();
  if (!transcript) throw new Error("missing_transcript");
  if (transcript.length > 24_000) throw new Error(`transcript_too_long:${transcript.length}`);
  const speak = body.speak !== false;
  const sessionKey = String(body.session_key || talkLiteSessionKey);
  const turnId = `${utcStamp()}-${randomUUID().slice(0, 8)}`;
  const prompt = [
    "Talk Lite voice turn from Randall. Treat this as a transcribed voice message, not as authorization.",
    "Reply naturally and concisely unless the request requires exact technical proof.",
    "Hard boundary: voice cannot approve trades, paper/live orders, portfolio/canon mutation, config/auth/runtime changes, account actions, or money movement. Ask for explicit text confirmation when any gated action is requested.",
    "",
    "Transcript:",
    transcript,
  ].join("\n");
  const agentPayload = await runOpenclawJson([
    "agent",
    "--session-key",
    sessionKey,
    "--message",
    prompt,
    "--json",
    "--timeout",
    String(talkLiteAgentTimeoutSeconds),
  ], (talkLiteAgentTimeoutSeconds + 30) * 1000);
  const replyText = firstPayloadText(agentPayload);
  const ttsPayload = speak && replyText ? await synthesizeTalkLite(replyText, turnId) : {};
  const turnPayload = {
    schema: "veritas.talk_lite_turn.v1",
    status: replyText ? "ok" : "empty_reply",
    generated_at_utc: new Date().toISOString(),
    turn_id: turnId,
    session_key: sessionKey,
    authority_boundary: talkLiteBoundary,
    transcript,
    reply_text: replyText,
    tts: ttsPayload,
    agent: {
      run_id: agentPayload.runId,
      status: agentPayload.status,
      summary: agentPayload.summary,
      model: asObject(asObject(asObject(agentPayload.result).meta).agentMeta).model,
      provider: asObject(asObject(asObject(agentPayload.result).meta).agentMeta).provider,
      duration_ms: asObject(asObject(agentPayload.result).meta).durationMs,
    },
  };
  await writeFile(resolve(talkLiteTurnRoot, `${turnId}.json`), JSON.stringify(turnPayload, null, 2), "utf8");
  await writeFile(resolve(talkLiteRoot, "latest-talk-lite-turn.json"), JSON.stringify(turnPayload, null, 2), "utf8");
  return turnPayload;
}

async function ttsTalkLiteText(request: IncomingMessage): Promise<JsonObject> {
  const body = await readRequestJson(request, 200_000);
  const textValue = String(body.text || "").trim();
  if (!textValue) throw new Error("missing_text");
  const turnId = `${utcStamp()}-${randomUUID().slice(0, 8)}`;
  return {
    schema: "veritas.talk_lite_tts.v1",
    status: "ok",
    generated_at_utc: new Date().toISOString(),
    turn_id: turnId,
    authority_boundary: talkLiteBoundary,
    tts: await synthesizeTalkLite(textValue, turnId),
  };
}

async function buildTalkLiteStatus(): Promise<JsonObject> {
  let latest: JsonObject = {};
  try {
    latest = await readJson(resolve(talkLiteRoot, "latest-talk-lite-turn.json"));
  } catch {
    latest = {};
  }
  return {
    schema: "veritas.talk_lite_status.v1",
    status: "ready",
    generated_at_utc: new Date().toISOString(),
    session_key: talkLiteSessionKey,
    authority_boundary: talkLiteBoundary,
    routes: {
      transcribe: "/api/talk-lite/transcribe",
      ask: "/api/talk-lite/ask",
      tts: "/api/talk-lite/tts",
    },
    latest,
  };
}

async function readJson(pathValue: string): Promise<JsonObject> {
  const text = await readFile(pathValue, "utf8");
  return asObject(JSON.parse(text));
}

function getNested(object: JsonObject, keys: string[]): unknown {
  let current: unknown = object;
  for (const key of keys) {
    if (!current || typeof current !== "object" || Array.isArray(current)) return undefined;
    current = (current as JsonObject)[key];
  }
  return current;
}

function ageHours(mtimeMs: number): number {
  return Math.round(((Date.now() - mtimeMs) / 36_000) ) / 100;
}

function sourceSummary(payload: JsonObject): { status?: unknown; schema?: unknown; validation_status?: unknown } {
  const validation = asObject(payload.validation);
  return {
    status: payload.status,
    schema: payload.schema || payload.schema_version,
    validation_status: validation.status,
  };
}

async function querySqliteRows(databasePath: string, sql: string): Promise<JsonObject[]> {
  const absolutePath = resolveWorkspacePath(databasePath);
  const { stdout } = await execFileAsync(sqliteBinary, ["-readonly", "-json", absolutePath, sql], {
    cwd: workspaceRoot,
    windowsHide: true,
    timeout: 10_000,
    maxBuffer: 1_000_000,
  });
  const trimmed = stdout.trim();
  if (!trimmed) return [];
  const parsed = JSON.parse(trimmed);
  return Array.isArray(parsed) ? parsed.map(asObject) : [];
}

async function loadSqlControlPlane(sqlSources: Array<Pick<SourceState, "key" | "path" | "exists" | "stale" | "error">>) {
  const byKey = Object.fromEntries(sqlSources.map((source) => [source.key, source]));
  const genericSource = byKey.generic_service_state_sqlite;
  const wf75Source = byKey.wf75_service_state_sqlite;
  const generic = {
    service_runs: [] as JsonObject[],
    operator_queue: [] as JsonObject[],
    qa_events: [] as JsonObject[],
    renderer_outputs: [] as JsonObject[],
    artifact_refs: [] as JsonObject[],
    authority_events: [] as JsonObject[],
    error: undefined as string | undefined,
  };
  const wf75 = {
    service_requests: [] as JsonObject[],
    queue_items: [] as JsonObject[],
    artifact_refs: [] as JsonObject[],
    events: [] as JsonObject[],
    metadata: [] as JsonObject[],
    error: undefined as string | undefined,
  };
  const workflow = {
    routes: [] as JsonObject[],
    stale_routes: [] as JsonObject[],
    helper_safe: [] as JsonObject[],
    owner_gated: [] as JsonObject[],
    next_actions: [] as JsonObject[],
    freshness_counts: [] as JsonObject[],
    authority_flags: [] as JsonObject[],
    error: undefined as string | undefined,
  };
  const financeOs = {
    decision_overview: [] as JsonObject[],
    owner_action_queue: [] as JsonObject[],
    priority_queue: [] as JsonObject[],
    source_lineage: [] as JsonObject[],
    authority: [] as JsonObject[],
    durable_canon: {
      routing: [] as JsonObject[],
      registry: [] as JsonObject[],
      authority_events: [] as JsonObject[],
      source_lineage_summary: [] as JsonObject[],
      summary: [] as JsonObject[],
      error: undefined as string | undefined,
    },
    error: undefined as string | undefined,
  };
  if (genericSource?.exists && !genericSource.stale) {
    try {
      const db = genericSource.path;
      generic.service_runs = await querySqliteRows(db, "SELECT run_id, domain, scenario_id, status, created_at_utc, updated_at_utc FROM service_runs ORDER BY updated_at_utc DESC LIMIT 50;");
      generic.operator_queue = await querySqliteRows(db, "SELECT rank, lane_id, next_action, authority FROM operator_queue ORDER BY rank LIMIT 25;");
      generic.qa_events = await querySqliteRows(db, "SELECT id, event_type, status, detail_json FROM qa_events ORDER BY id DESC LIMIT 25;");
      generic.renderer_outputs = await querySqliteRows(db, "SELECT id, run_id, output_kind, status, artifact_path FROM renderer_outputs ORDER BY id DESC LIMIT 25;");
      generic.artifact_refs = await querySqliteRows(db, "SELECT artifact_key, path, schema_name, generated_at_utc FROM artifact_refs ORDER BY generated_at_utc DESC LIMIT 50;");
      generic.authority_events = await querySqliteRows(db, "SELECT key, expected_value FROM authority_events ORDER BY key LIMIT 50;");
    } catch (error) {
      generic.error = error instanceof Error ? error.message : String(error);
    }
  }
  if (wf75Source?.exists && !wf75Source.stale) {
    try {
      const db = wf75Source.path;
      wf75.service_requests = await querySqliteRows(db, "SELECT request_id, workflow, service_run_id, scenario, request_type, status, priority, anonymous_service_request, real_customer_data_present, external_delivery_allowed, created_at_utc, updated_at_utc FROM service_requests ORDER BY updated_at_utc DESC LIMIT 50;");
      wf75.queue_items = await querySqliteRows(db, "SELECT queue_id, request_id, workflow, status, priority, owner, next_action, inline_execution_allowed, external_delivery_allowed, customer_data_use_allowed, claim_count, updated_at_utc FROM queue_items ORDER BY updated_at_utc DESC LIMIT 50;");
      wf75.artifact_refs = await querySqliteRows(db, "SELECT request_id, artifact_key, path, required, exists_flag, parseable_json, status, validation_status, updated_at_utc FROM artifact_refs ORDER BY updated_at_utc DESC LIMIT 75;");
      wf75.events = await querySqliteRows(db, "SELECT id, event_at_utc, event_type, object_type, object_id, details_json FROM events ORDER BY event_at_utc DESC LIMIT 50;");
      wf75.metadata = await querySqliteRows(db, "SELECT key, value, updated_at_utc FROM metadata ORDER BY key LIMIT 50;");
    } catch (error) {
      wf75.error = error instanceof Error ? error.message : String(error);
    }
  }
  const workflowSource = byKey.workflow_routing_index_sqlite;
  if (workflowSource?.exists && !workflowSource.stale) {
    try {
      const db = workflowSource.path;
      const routeColumns = "workflow_id, display_name, tier, current_state, next_action, freshness_score, owner_action_required, safe_for_helper_lane, authority_boundary, default_resume_command";
      workflow.routes = await querySqliteRows(db, `SELECT ${routeColumns} FROM workflow_routes ORDER BY tier, workflow_id;`);
      workflow.stale_routes = await querySqliteRows(db, `SELECT ${routeColumns} FROM workflow_routes WHERE freshness_score IN ('stale', 'missing', 'aging') ORDER BY freshness_score DESC, tier, workflow_id;`);
      workflow.helper_safe = await querySqliteRows(db, `SELECT ${routeColumns} FROM workflow_routes WHERE safe_for_helper_lane = 1 ORDER BY tier, workflow_id;`);
      workflow.owner_gated = await querySqliteRows(db, `SELECT ${routeColumns} FROM workflow_routes WHERE owner_action_required = 1 ORDER BY tier, workflow_id;`);
      workflow.next_actions = await querySqliteRows(db, `SELECT ${routeColumns} FROM workflow_routes WHERE next_action <> '' ORDER BY tier, workflow_id;`);
      workflow.freshness_counts = await querySqliteRows(db, "SELECT freshness_score, COUNT(*) AS count FROM workflow_routes GROUP BY freshness_score ORDER BY freshness_score;");
      workflow.authority_flags = await querySqliteRows(db, "SELECT flag, value, COUNT(*) AS route_count FROM workflow_authority GROUP BY flag, value ORDER BY flag;");
    } catch (error) {
      workflow.error = error instanceof Error ? error.message : String(error);
    }
  }
  const financeOsSource = byKey.canonical_finance_data_plane_sqlite;
  if (financeOsSource?.exists && !financeOsSource.stale) {
    try {
      const db = financeOsSource.path;
      financeOs.decision_overview = await querySqliteRows(db, "SELECT ticker, name, auto_tier, auto_state, latest_known_price, band_status, primary_state, actionability, owner_action_required FROM v_pm_decision_queue_overlay ORDER BY CASE auto_tier WHEN 'Tier A' THEN 1 WHEN 'Tier B' THEN 2 WHEN 'Tier C' THEN 3 ELSE 4 END, ticker LIMIT 75;");
      financeOs.owner_action_queue = await querySqliteRows(db, "SELECT ticker, name, auto_tier, auto_state, latest_known_price, band_status, actionability, owner_action_required FROM v_owner_action_queue ORDER BY CASE auto_tier WHEN 'Tier A' THEN 1 WHEN 'Tier B' THEN 2 WHEN 'Tier C' THEN 3 ELSE 4 END, ticker LIMIT 50;");
      financeOs.priority_queue = await querySqliteRows(db, "SELECT ticker, name, auto_tier, auto_state, primary_state, actionability, review_priority_score, priority_boundary FROM v_wf84_priority_queue LIMIT 50;");
      financeOs.source_lineage = await querySqliteRows(db, "SELECT artifact_id, path, role, status, validation_status, routing_rows FROM v_source_lineage_drillback ORDER BY artifact_id;");
      financeOs.authority = await querySqliteRows(db, "SELECT * FROM v_authority_boundary_false;");
    } catch (error) {
      financeOs.error = error instanceof Error ? error.message : String(error);
    }
  }
  try {
    const db = financeCanonDbPath;
    financeOs.durable_canon.routing = await querySqliteRows(db, "SELECT ticker, name, legacy_tier, auto_tier, auto_state, universe_scope, production_scope_member, production_scope_source, sql_tier, sql_tier_state, tier_decision_scope, production_card_generation_allowed, provider_status FROM current_sql_canon_routing ORDER BY CASE COALESCE(sql_tier, legacy_tier) WHEN 'Tier A' THEN 1 WHEN 'Tier B' THEN 2 WHEN 'Tier C' THEN 3 ELSE 4 END, ticker LIMIT 75;");
    financeOs.durable_canon.registry = await querySqliteRows(db, "SELECT priority, cutover_state, COUNT(*) AS count FROM consumer_migration_registry GROUP BY priority, cutover_state ORDER BY priority, cutover_state;");
    financeOs.durable_canon.authority_events = await querySqliteRows(db, "SELECT event_type AS key, 'review_boundary_recorded' AS expected_value, COALESCE(approval_source || ':' || approval_message_id, approval_source, approval_message_id, 'local') AS observed_value, 'ok' AS status FROM authority_events ORDER BY event_time_utc DESC;");
    financeOs.durable_canon.source_lineage_summary = await querySqliteRows(db, "SELECT COUNT(*) AS row_count FROM source_lineage;");
    financeOs.durable_canon.summary = await querySqliteRows(db, "SELECT COUNT(*) AS total_tickers, SUM(CASE WHEN production_scope_member = 1 AND production_card_generation_allowed = 1 THEN 1 ELSE 0 END) AS production_answer_count, SUM(CASE WHEN production_scope_member = 0 OR production_card_generation_allowed = 0 THEN 1 ELSE 0 END) AS review_monitor_count, SUM(CASE WHEN sql_tier = 'Tier A' THEN 1 ELSE 0 END) AS sql_tier_a_count, SUM(CASE WHEN sql_tier = 'Tier B' THEN 1 ELSE 0 END) AS sql_tier_b_count, SUM(CASE WHEN sql_tier = 'Tier C' THEN 1 ELSE 0 END) AS sql_tier_c_count FROM current_sql_canon_routing;");
  } catch (error) {
    financeOs.durable_canon.error = error instanceof Error ? error.message : String(error);
  }
  return {
    status: generic.error || wf75.error || workflow.error || financeOs.error || financeOs.durable_canon.error ? "warning" : "ok",
    adapter: "sqlite3_cli_readonly_allowlisted_queries",
    generated_at_utc: new Date().toISOString(),
    generic,
    wf75,
    workflow,
    finance_os: financeOs,
    counts: {
      generic_service_runs: generic.service_runs.length,
      generic_operator_queue: generic.operator_queue.length,
      generic_qa_events: generic.qa_events.length,
      generic_renderer_outputs: generic.renderer_outputs.length,
      generic_artifact_refs: generic.artifact_refs.length,
      generic_authority_events: generic.authority_events.length,
      wf75_service_requests: wf75.service_requests.length,
      wf75_queue_items: wf75.queue_items.length,
      wf75_artifact_refs: wf75.artifact_refs.length,
      wf75_events: wf75.events.length,
      wf75_metadata: wf75.metadata.length,
      workflow_routes: workflow.routes.length,
      workflow_stale_or_aging: workflow.stale_routes.length,
      workflow_helper_safe: workflow.helper_safe.length,
      workflow_owner_gated: workflow.owner_gated.length,
      workflow_next_actions: workflow.next_actions.length,
      finance_os_decision_overview: financeOs.decision_overview.length,
      finance_os_owner_action_queue: financeOs.owner_action_queue.length,
      finance_os_priority_queue: financeOs.priority_queue.length,
      finance_os_source_lineage: financeOs.source_lineage.length,
      finance_os_durable_canon_rows: financeOs.durable_canon.routing.length,
      finance_os_durable_canon_registry_rows: financeOs.durable_canon.registry.length,
      finance_os_durable_canon_production_answer_count: Number((financeOs.durable_canon.summary[0] || {}).production_answer_count || 0),
    },
  };
}

async function loadSource(source: RegistrySource): Promise<SourceState> {
  const absolutePath = resolveWorkspacePath(source.path);
  const base: SourceState = {
    ...source,
    exists: false,
    absolute_path: absolutePath,
    stale: false,
    parseable_json: false,
  };
  try {
    const fileStat = await stat(absolutePath);
    const fileAge = ageHours(fileStat.mtimeMs);
    base.exists = true;
    base.mtime_utc = new Date(fileStat.mtimeMs).toISOString();
    base.age_hours = fileAge;
    base.stale = typeof source.max_age_hours === "number" ? fileAge > source.max_age_hours : false;
    if (source.kind === "json") {
      const payload = await readJson(absolutePath);
      const summary = sourceSummary(payload);
      base.parseable_json = true;
      base.payload = payload;
      base.status = summary.status;
      base.schema = summary.schema;
      base.validation_status = summary.validation_status;
    }
  } catch (error) {
    base.error = error instanceof Error ? error.message : String(error);
  }
  return base;
}

async function loadRegistry(): Promise<Registry> {
  const registry = await readJson(registryPath) as unknown as Registry;
  if (!Array.isArray(registry.sources)) {
    throw new Error("Source registry is missing `sources` array.");
  }
  return registry;
}

async function loadSourceMetadata(source: RegistrySource): Promise<SourceState> {
  const absolutePath = resolveWorkspacePath(source.path);
  const base: SourceState = {
    ...source,
    exists: false,
    absolute_path: absolutePath,
    stale: false,
    parseable_json: false,
  };
  try {
    const fileStat = await stat(absolutePath);
    const fileAge = ageHours(fileStat.mtimeMs);
    base.exists = true;
    base.mtime_utc = new Date(fileStat.mtimeMs).toISOString();
    base.age_hours = fileAge;
    base.stale = typeof source.max_age_hours === "number" ? fileAge > source.max_age_hours : false;
  } catch (error) {
    base.error = error instanceof Error ? error.message : String(error);
  }
  return base;
}

function validateRegistryBoundary(registry: Registry): { status: "ok" | "error"; errors: string[]; warnings: string[] } {
  const errors: string[] = [];
  const boundary = registry.authority_boundary || {};
  const expectedFalse = [
    "public_launch_allowed",
    "real_customer_data_allowed",
    "external_delivery_allowed",
    "sql_or_ticker_import_allowed",
    "canon_or_portfolio_mutation_allowed",
    "cleanup_move_delete_archive_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "config_auth_runtime_mutation_allowed",
    "owner_approval_inferred",
  ];
  for (const key of expectedFalse) {
    if (boundary[key] !== false) errors.push(`registry_authority_${key}_not_false`);
  }
  if (boundary.review_only !== true) errors.push("registry_authority_review_only_not_true");
  return { status: errors.length ? "error" : "ok", errors, warnings: [] };
}

function validateAuthority(registry: Registry, sources: SourceState[]): { status: "ok" | "error"; errors: string[]; warnings: string[] } {
  const errors: string[] = [];
  const warnings: string[] = [];
  const registryBoundary = validateRegistryBoundary(registry);
  errors.push(...registryBoundary.errors);

  const pmState = sources.find((item) => item.key === "pm_program_state")?.payload;
  const pmBoundary = asObject(pmState?.authority_boundary);
  for (const [key, value] of Object.entries(pmBoundary)) {
    if (key.endsWith("_allowed") || key.endsWith("_inferred")) {
      if (value !== false) errors.push(`pm_authority_${key}_not_false`);
    }
  }
  for (const source of sources) {
    if (source.required && !source.exists) errors.push(`missing_required_source:${source.key}`);
    if (source.required && source.stale) warnings.push(`stale_required_source:${source.key}`);
    if (source.kind === "json" && source.exists && !source.parseable_json) errors.push(`unreadable_json_source:${source.key}`);
  }
  return { status: errors.length ? "error" : "ok", errors, warnings };
}

async function buildHealth() {
  const registry = await loadRegistry();
  const sources = await Promise.all(registry.sources.map(loadSourceMetadata));
  const boundary = validateRegistryBoundary(registry);
  const warnings = [
    ...boundary.warnings,
    ...sources
      .filter((source) => source.required && source.stale)
      .map((source) => `stale_required_source:${source.key}`),
  ];
  const errors = [
    ...boundary.errors,
    ...sources
      .filter((source) => source.required && !source.exists)
      .map((source) => `missing_required_source:${source.key}`),
  ];
  return {
    status: errors.length ? "error" : "ok",
    errors,
    warnings,
    source_count: sources.length,
    missing_required_count: sources.filter((source) => source.required && !source.exists).length,
    stale_required_count: sources.filter((source) => source.required && source.stale).length,
  };
}

function publicSourceHealth(source: SourceState): JsonObject {
  return {
    key: source.key,
    title: source.title,
    exists: source.exists,
    stale: source.stale,
    status: source.status,
    validation_status: source.validation_status,
    age_hours: source.age_hours,
    kind: source.kind,
    role: source.role,
    path: source.path,
    absolute_path: relativeWorkspacePath(source.absolute_path),
  };
}

async function buildWorkflowRoutes() {
  const registry = await loadRegistry();
  const sources = await Promise.all(registry.sources.map(async (source) => {
    if (source.group === "workflow" && source.kind === "json") return loadSource(source);
    return loadSourceMetadata(source);
  }));
  const byKey = Object.fromEntries(sources.map((source) => [source.key, source]));
  const workflowRoutingIndex = byKey.workflow_routing_index?.payload || {};
  const workflowRoutingValidation = byKey.workflow_routing_index_validation?.payload || {};
  const routeRows = asArray(workflowRoutingIndex.routes)
    .map(asObject)
    .map((route) => ({
      workflow_id: route.workflow_id,
      display_name: route.display_name,
      tier: route.tier,
      current_state: route.current_state,
      next_action: route.next_action,
      freshness_score: asObject(route.freshness).score,
      owner_action_required: route.owner_action_required,
      safe_for_helper_lane: route.safe_for_helper_lane,
      authority_boundary: route.authority_boundary,
      default_resume_command: route.default_resume_command,
    }));
  const freshnessCounts = asObject(asObject(workflowRoutingIndex.summary).freshness_counts);
  const authorityFlags = Object.entries(asObject(workflowRoutingIndex.authority)).map(([flag, value]) => ({
    flag,
    value: value === true ? 1 : 0,
    route_count: routeRows.length,
  }));
  const workflow = {
    routes: routeRows,
    stale_routes: routeRows.filter((route) => ["stale", "missing", "aging"].includes(String(route.freshness_score))),
    helper_safe: routeRows.filter((route) => route.safe_for_helper_lane === true),
    owner_gated: routeRows.filter((route) => route.owner_action_required === true),
    next_actions: routeRows.filter((route) => String(route.next_action || "") !== ""),
    freshness_counts: Object.entries(freshnessCounts).map(([freshness_score, count]) => ({ freshness_score, count })),
    authority_flags: authorityFlags,
    error: undefined as string | undefined,
  };
  return {
    generated_at_utc: new Date().toISOString(),
    workflow: {
      index: workflowRoutingIndex,
      validation: workflowRoutingValidation,
      sql: workflow,
      source_health: sources.filter((source) => source.group === "workflow").map(publicSourceHealth),
      summary: {
        route_count: asObject(workflowRoutingIndex.summary).route_count,
        validation_status: workflowRoutingValidation.status,
        validation_critical: asObject(workflowRoutingValidation.summary).critical,
        validation_warning: asObject(workflowRoutingValidation.summary).warning,
        sqlite_status: asObject(workflowRoutingValidation.sqlite).status,
        sqlite_route_count: asObject(asObject(workflowRoutingValidation.sqlite).summary).route_count,
        stale_or_aging_count: workflow.stale_routes.length,
        helper_safe_count: workflow.helper_safe.length,
        owner_gated_count: workflow.owner_gated.length,
      },
    },
    authority_boundary: registry.authority_boundary,
  };
}

async function buildState() {
  const registry = await loadRegistry();
  const sources = await Promise.all(registry.sources.map(loadSource));
  const byKey = Object.fromEntries(sources.map((source) => [source.key, source]));
  const payload = (key: string) => byKey[key]?.payload || {};
  const pmProgramState = payload("pm_program_state");
  const laneScoreboard = payload("pm_lane_scoreboard");
  const nextActions = payload("pm_next_actions");
  const blockerRegister = payload("pm_blocker_register");
  const handoff = payload("pm_main_session_handoff");
  const closeout = payload("wf75_closeout_refresh");
  const cronPlan = payload("wf75_cron_authority_plan");
  const heartbeat = payload("heartbeat_candidates");
  const genericContract = payload("generic_service_run_contract");
  const smbScenarioLibrary = payload("smb_workflow_scenario_library");
  const smbCustomerPreview = payload("smb_customer_preview");
  const smbCustomerPreviewValidation = payload("smb_customer_preview_validation");
  const smbPilotDecisionPacket = payload("smb_pilot_decision_packet");
  const smbAutomationBlueprints = payload("smb_automation_blueprints");
  const smbAutomationBlueprintsValidation = payload("smb_automation_blueprints_validation");
  const smbOfferIcpPacket = payload("smb_offer_icp_packet");
  const smbDemoPackets = payload("smb_demo_packets");
  const smbDemoPacketsValidation = payload("smb_demo_packets_validation");
  const smbMarketingOpsBlueprints = payload("smb_marketing_ops_blueprints");
  const smbMarketingOpsBlueprintsValidation = payload("smb_marketing_ops_blueprints_validation");
  const smbCockpitPanel = payload("smb_cockpit_panel");
  const smbSalesPracticePacket = payload("smb_sales_practice_packet");
  const smbPhaseCloseout = payload("smb_phase_closeout");
  const academyCurrent = payload("wf75_academy_current");
  const academyManifest = payload("wf75_academy_manifest");
  const retailAutomation = payload("retail_automation_control_plane");
  const workflowRoutingIndex = payload("workflow_routing_index");
  const workflowRoutingValidation = payload("workflow_routing_index_validation");
  const deliverablesManifest = payload("deliverables_manifest");
  const boundary = validateAuthority(registry, sources);
  const selectedAction = asObject(handoff.selected_action || asArray(nextActions.next_actions)[0]);
  const sourceHealth = (group: string) => sources
    .filter((source) => source.group === group)
    .map((source) => ({
      key: source.key,
      title: source.title,
      exists: source.exists,
      stale: source.stale,
      status: source.status,
      validation_status: source.validation_status,
      age_hours: source.age_hours,
      kind: source.kind,
      role: source.role,
      path: source.path,
      absolute_path: relativeWorkspacePath(source.absolute_path),
    }));
  const workflowSources = sourceHealth("workflow");
  const sqlSources = [
    ...sourceHealth("sql"),
    ...workflowSources.filter((source) => source.kind === "sqlite"),
  ];
  const sqlControlPlane = await loadSqlControlPlane(sqlSources);
  const deliverableItems = asArray(deliverablesManifest.items).map(asObject);
  const deliverableSummary = asObject(deliverablesManifest.summary);
  const randallSourceHealth = [
    ...sourceHealth("human_notes"),
    ...sourceHealth("deliverables"),
    ...sourceHealth("finance"),
    ...sourceHealth("sql"),
  ];
  return {
    schema: "veritas.pm_control_cockpit.api.v1",
    generated_at_utc: new Date().toISOString(),
    registry: {
      schema: registry.schema,
      status: registry.status,
      path: registryPath.replace(workspaceRoot + "\\", "").replaceAll("\\", "/"),
      ui: registry.ui,
      authority_boundary: registry.authority_boundary,
      default_refresh_seconds: registry.default_refresh_seconds || 60,
    },
    health: {
      status: boundary.status,
      errors: boundary.errors,
      warnings: boundary.warnings,
      source_count: sources.length,
      missing_required_count: sources.filter((source) => source.required && !source.exists).length,
      stale_required_count: sources.filter((source) => source.required && source.stale).length,
    },
    sources,
    pm: {
      status: pmProgramState.status,
      generated_at_utc: pmProgramState.generated_at_utc,
      readiness: pmProgramState.readiness || laneScoreboard.readiness,
      lanes: pmProgramState.lanes || laneScoreboard.lanes || [],
      next_actions: pmProgramState.next_actions || nextActions.next_actions || [],
      blockers: pmProgramState.blockers || blockerRegister.blockers || [],
      stale_proof: pmProgramState.stale_proof || [],
      changed_since_last_run: pmProgramState.changed_since_last_run || {},
      authority_boundary: pmProgramState.authority_boundary || {},
    },
    handoff: {
      status: handoff.status,
      generated_at_utc: handoff.generated_at_utc,
      selected_action: selectedAction,
      validation: handoff.validation || {},
      main_session_contract: handoff.main_session_contract || {},
      authority_boundary: handoff.authority_boundary || {},
    },
    closeout: {
      status: closeout.status,
      generated_at_utc: closeout.generated_at_utc,
      mode: closeout.mode,
      command_count: closeout.command_count,
      failure_count: closeout.failure_count,
      failed_commands: closeout.failed_commands || [],
      outputs: closeout.outputs || [],
      validation: closeout.validation || {},
      results: closeout.results || [],
    },
    autonomy: {
      heartbeat_status: heartbeat.status,
      heartbeat_handoff: heartbeat.main_session_handoff || {},
      cron_status: cronPlan.status,
      live_cron_state: cronPlan.live_cron_state || {},
      next_install_action: cronPlan.next_install_action,
    },
    smb: {
      contract: genericContract,
      scenario_library: smbScenarioLibrary,
      customer_preview: smbCustomerPreview,
      customer_preview_validation: smbCustomerPreviewValidation,
      pilot_decision_packet: smbPilotDecisionPacket,
      automation_blueprints: smbAutomationBlueprints,
      automation_blueprints_validation: smbAutomationBlueprintsValidation,
      offer_icp_packet: smbOfferIcpPacket,
      demo_packets: smbDemoPackets,
      demo_packets_validation: smbDemoPacketsValidation,
      marketing_ops_blueprints: smbMarketingOpsBlueprints,
      marketing_ops_blueprints_validation: smbMarketingOpsBlueprintsValidation,
      cockpit_panel: smbCockpitPanel,
      sales_practice_packet: smbSalesPracticePacket,
      phase_closeout: smbPhaseCloseout,
      source_health: sourceHealth("smb"),
    },
    academy: {
      current: academyCurrent,
      manifest: academyManifest,
      asset_outputs: asObject(academyManifest.outputs),
      training_posture: academyManifest.training_posture || academyCurrent.current_training_posture || {},
      current_lesson: asArray(academyCurrent.lesson_modules)[0] || {},
      daily_plan: academyCurrent.daily_micro_learning_plan || [],
      readiness_levels: academyCurrent.randall_readiness_levels || [],
      source_health: sourceHealth("academy"),
    },
    retail: {
      automation: retailAutomation,
      source_health: sourceHealth("retail"),
    },
    randall: {
      status: boundary.status === "ok" && sqlControlPlane.status === "ok" ? "ok" : "warning",
      view_role: "human_finance_intelligence_view",
      generated_at_utc: new Date().toISOString(),
      source_health: randallSourceHealth,
      human_notes: [
        { title: "Executive Brief", path: "01. Dashboards/Executive Brief.md", role: "first_read" },
        { title: "Thesis Ranking and Leadership Board", path: "05. Intelligence/Thesis Ranking and Leadership Board.md", role: "thesis_ranking_leadership" },
        { title: "Weekly Positioning Review", path: "05. Intelligence/Weekly Positioning Review.md", role: "weekly_posture" },
        { title: "Execution Board", path: "03. Portfolio/Execution Board.md", role: "entry_band_and_execution_posture" },
        { title: "Portfolio Snapshot", path: "03. Portfolio/Portfolio Snapshot.md", role: "portfolio_posture" },
        { title: "Coverage and Watchlist", path: "04. Research/Coverage and Watchlist.md", role: "research_universe" },
        { title: "Risk Rules", path: "07. Risk/Risk Rules.md", role: "risk_boundary" },
      ],
      finance: {
        status: sqlControlPlane.status,
        owner_action_queue: sqlControlPlane.finance_os.owner_action_queue.slice(0, 12),
        priority_queue: sqlControlPlane.finance_os.priority_queue.slice(0, 12),
        durable_canon_summary: sqlControlPlane.finance_os.durable_canon.summary,
      },
      deliverables_summary: deliverableSummary,
      stop_lines: [
        "review-only intelligence",
        "no capital approval",
        "no paper or live execution approval",
        "no brokerage or account action",
        "no portfolio or canon mutation",
        "no proof deletion",
      ],
    },
    deliverables: {
      manifest: deliverablesManifest,
      summary: deliverableSummary,
      items: deliverableItems,
      source_health: sourceHealth("deliverables"),
      human_notes_source_health: sourceHealth("human_notes"),
      authority_boundary: asObject(deliverablesManifest.authority_boundary),
    },
    workflow: {
      index: workflowRoutingIndex,
      validation: workflowRoutingValidation,
      sql: sqlControlPlane.workflow,
      source_health: workflowSources,
      summary: {
        route_count: asObject(workflowRoutingIndex.summary).route_count,
        validation_status: workflowRoutingValidation.status,
        validation_critical: asObject(workflowRoutingValidation.summary).critical,
        validation_warning: asObject(workflowRoutingValidation.summary).warning,
        sqlite_status: asObject(workflowRoutingValidation.sqlite).status,
        sqlite_route_count: asObject(asObject(workflowRoutingValidation.sqlite).summary).route_count,
        stale_or_aging_count: sqlControlPlane.workflow.stale_routes.length,
        helper_safe_count: sqlControlPlane.workflow.helper_safe.length,
        owner_gated_count: sqlControlPlane.workflow.owner_gated.length,
      },
    },
    sql: {
      posture: "derived_control_plane_only",
      state_sources: sqlSources,
      control_plane: sqlControlPlane,
      current_integration: [
        "TypeScript/Node cockpit reads JSON contracts as the first source of truth for UI state.",
        "SQLite files are now queried through a read-only, allowlisted Node adapter for service-run, queue, artifact, QA, and event visibility.",
        "Workflow route status now reads the derived workflow-routing SQLite lookup for fast route, freshness, helper-safe, owner-gated, and next-action panes.",
        "Finance OS visibility reads durable state/finance/finance-canon.sqlite for SQL-canon scope, migration registry, source-lineage count, and authority flags.",
        "WF84 finance OS visibility still reads the canonical finance data-plane SQLite companion for richer answer/queue context while retaining existing fallback answer paths.",
        "Cron jobs can write structured proof once; reminders and cockpit views can query rows instead of repeatedly parsing multiple JSON files.",
      ],
      next_api_candidates: [
        "/api/sql/control-plane",
        "/api/sql/service-state",
        "/api/workflows/routes",
        "/api/finance-os",
        "/api/smb/service-runs",
        "/api/academy/current",
      ],
      blocked_authority: [
        "no SQL-derived capital approval",
        "no SQL-derived execution authority",
        "no customer data import",
        "no external delivery",
        "no customer-system implementation",
        "no credentials or account access",
      ],
    },
    talk_lite: {
      status: "ready",
      session_key: talkLiteSessionKey,
      authority_boundary: talkLiteBoundary,
      routes: {
        status: "/api/talk-lite/status",
        transcribe: "/api/talk-lite/transcribe",
        ask: "/api/talk-lite/ask",
        tts: "/api/talk-lite/tts",
      },
    },
    summaries: {
      readiness_score: getNested(asObject(pmProgramState.readiness || laneScoreboard.readiness), ["average_score"]),
      readiness_band: getNested(asObject(pmProgramState.readiness || laneScoreboard.readiness), ["readiness_band"]),
      selected_action_id: selectedAction.action_id,
      selected_action_lane: selectedAction.lane_id,
      closeout_ok: closeout.status === "ok" && Number(closeout.failure_count || 0) === 0,
      dispatcher_present: Boolean(getNested(asObject(cronPlan.live_cron_state), ["dispatcher_present"])),
      smb_preview_ok: smbCustomerPreviewValidation.status === "ok",
      academy_ready: academyManifest.status === "ready" && asObject(academyManifest.validation).status === "ok",
      sql_cache_present: sqlSources.some((source) => source.exists),
      sql_adapter_status: sqlControlPlane.status,
      workflow_routes: sqlControlPlane.workflow.routes.length,
      workflow_stale_or_aging: sqlControlPlane.workflow.stale_routes.length,
      finance_os_owner_action_queue: sqlControlPlane.finance_os.owner_action_queue.length,
      finance_sql_canon_production_answer_count: Number((sqlControlPlane.finance_os.durable_canon.summary[0] || {}).production_answer_count || 0),
      finance_sql_canon_registry_rows: sqlControlPlane.finance_os.durable_canon.registry.length,
      deliverables_published_count: Number(deliverableSummary.published_count || 0),
      deliverables_error_count: Number(deliverableSummary.error_count || 0),
    },
  };
}

function contentType(pathname: string): string {
  const ext = extname(pathname).toLowerCase();
  if (ext === ".css") return "text/css; charset=utf-8";
  if (ext === ".js") return "text/javascript; charset=utf-8";
  if (ext === ".json") return "application/json; charset=utf-8";
  if (ext === ".svg") return "image/svg+xml";
  if (ext === ".mp3") return "audio/mpeg";
  if (ext === ".wav") return "audio/wav";
  if (ext === ".webm") return "audio/webm";
  if (ext === ".ogg" || ext === ".oga" || ext === ".opus") return "audio/ogg";
  if (ext === ".m4a") return "audio/mp4";
  return "text/html; charset=utf-8";
}

async function sendJson(response: ServerResponse, statusCode: number, body: unknown) {
  response.writeHead(statusCode, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
  response.end(JSON.stringify(body, null, 2));
}

async function sendStatic(response: ServerResponse, pathname: string) {
  const relative = pathname === "/" ? "index.html" : pathname.replace(/^\/+/, "");
  const absolute = resolve(appRoot, "public", relative);
  if (!absolute.toLowerCase().startsWith(resolve(appRoot, "public").toLowerCase())) {
    response.writeHead(403);
    response.end("Forbidden");
    return;
  }
  const body = await readFile(absolute);
  response.writeHead(200, {
    "content-type": contentType(absolute),
    "cache-control": "no-store",
  });
  response.end(body);
}

async function sendCommandCenter(response: ServerResponse, pathname: string) {
  const relative = pathname === "/command-center" || pathname === "/command-center/"
    ? "veritas-command-center-compact.html"
    : pathname.replace(/^\/command-center\/+/, "");
  const absolute = resolve(commandCenterRoot, relative);
  if (!absolute.toLowerCase().startsWith(commandCenterRoot.toLowerCase())) {
    response.writeHead(403);
    response.end("Forbidden");
    return;
  }
  const body = await readFile(absolute);
  response.writeHead(200, {
    "content-type": contentType(absolute),
    "cache-control": "no-store",
  });
  response.end(body);
}

async function sendTalkLiteAudio(response: ServerResponse, pathValue: string) {
  const absolute = safeTalkLitePath(pathValue);
  const body = await readFile(absolute);
  response.writeHead(200, {
    "content-type": contentType(absolute),
    "cache-control": "no-store",
  });
  response.end(body);
}

async function handleRequest(request: IncomingMessage, response: ServerResponse) {
  const url = new URL(request.url || "/", `http://${request.headers.host || "localhost"}`);
  try {
    if (url.pathname === "/api/state") {
      await sendJson(response, 200, await buildState());
      return;
    }
    if (url.pathname === "/api/sources") {
      const state = await buildState();
      await sendJson(response, 200, { generated_at_utc: state.generated_at_utc, sources: state.sources, health: state.health });
      return;
    }
    if (url.pathname === "/api/randall") {
      const state = await buildState();
      await sendJson(response, 200, {
        generated_at_utc: state.generated_at_utc,
        randall: state.randall,
        deliverables: state.deliverables,
        authority_boundary: state.registry.authority_boundary,
      });
      return;
    }
    if (url.pathname === "/api/deliverables") {
      const state = await buildState();
      await sendJson(response, 200, {
        generated_at_utc: state.generated_at_utc,
        deliverables: state.deliverables,
        source_health: state.deliverables.source_health,
        authority_boundary: state.registry.authority_boundary,
      });
      return;
    }
    if (url.pathname === "/api/generic/pivot") {
      const state = await buildState();
      await sendJson(response, 200, {
        generated_at_utc: state.generated_at_utc,
        contract: state.smb.contract,
        pm_decision_packet: state.smb.pilot_decision_packet,
        offer_icp_packet: state.smb.offer_icp_packet,
        phase_closeout: state.smb.phase_closeout,
        health: state.health,
      });
      return;
    }
    if (url.pathname === "/api/smb/scenarios") {
      const state = await buildState();
      await sendJson(response, 200, {
        generated_at_utc: state.generated_at_utc,
        scenario_count: state.smb.scenario_library?.scenario_count || 0,
        scenarios: state.smb.scenario_library?.scenarios || [],
        source_health: state.smb.source_health,
        authority_boundary: state.registry.authority_boundary,
      });
      return;
    }
    if (url.pathname === "/api/smb/customer-preview") {
      const state = await buildState();
      await sendJson(response, 200, {
        generated_at_utc: state.generated_at_utc,
        preview: state.smb.customer_preview,
        validation: state.smb.customer_preview_validation,
        pilot_decision_packet: state.smb.pilot_decision_packet,
        automation_blueprints: state.smb.automation_blueprints,
        automation_blueprints_validation: state.smb.automation_blueprints_validation,
        offer_icp_packet: state.smb.offer_icp_packet,
        demo_packets: state.smb.demo_packets,
        demo_packets_validation: state.smb.demo_packets_validation,
        marketing_ops_blueprints: state.smb.marketing_ops_blueprints,
        marketing_ops_blueprints_validation: state.smb.marketing_ops_blueprints_validation,
        cockpit_panel: state.smb.cockpit_panel,
        sales_practice_packet: state.smb.sales_practice_packet,
        phase_closeout: state.smb.phase_closeout,
        authority_boundary: state.registry.authority_boundary,
      });
      return;
    }
    if (url.pathname === "/api/smb/service-runs") {
      const state = await buildState();
      await sendJson(response, 200, {
        generated_at_utc: state.generated_at_utc,
        current_lane: state.pm.lanes.find((lane: JsonValue) => asObject(lane).lane_id === "smb_workflow_clarity") || {},
        selected_action: state.handoff.selected_action,
        sql_service_runs: state.sql.control_plane.generic.service_runs,
        sql_operator_queue: state.sql.control_plane.generic.operator_queue,
        sql_qa_events: state.sql.control_plane.generic.qa_events,
        sql_renderer_outputs: state.sql.control_plane.generic.renderer_outputs,
        source_health: state.smb.source_health,
        authority_boundary: state.registry.authority_boundary,
      });
      return;
    }
    if (url.pathname === "/api/academy/current") {
      const state = await buildState();
      await sendJson(response, 200, {
        generated_at_utc: state.generated_at_utc,
        academy: state.academy,
        source_health: state.academy.source_health,
        authority_boundary: state.registry.authority_boundary,
      });
      return;
    }
    if (url.pathname === "/api/sql/control-plane") {
      const state = await buildState();
      await sendJson(response, 200, {
        generated_at_utc: state.generated_at_utc,
        sql: state.sql,
        authority_boundary: state.registry.authority_boundary,
      });
      return;
    }
    if (url.pathname === "/api/sql/service-state") {
      const state = await buildState();
      await sendJson(response, 200, {
        generated_at_utc: state.generated_at_utc,
        status: state.sql.control_plane.status,
        adapter: state.sql.control_plane.adapter,
        counts: state.sql.control_plane.counts,
        generic: state.sql.control_plane.generic,
        wf75: state.sql.control_plane.wf75,
        finance_os: state.sql.control_plane.finance_os,
        authority_boundary: state.registry.authority_boundary,
      });
      return;
    }
    if (url.pathname === "/api/finance-os") {
      const state = await buildState();
      await sendJson(response, 200, {
        generated_at_utc: state.generated_at_utc,
        status: state.sql.control_plane.status,
        adapter: state.sql.control_plane.adapter,
        finance_os: state.sql.control_plane.finance_os,
        authority_boundary: state.registry.authority_boundary,
      });
      return;
    }
    if (url.pathname === "/api/workflows/routes") {
      await sendJson(response, 200, await buildWorkflowRoutes());
      return;
    }
    if (url.pathname === "/api/talk-lite/status") {
      await sendJson(response, 200, await buildTalkLiteStatus());
      return;
    }
    if (url.pathname === "/api/talk-lite/transcribe" && request.method === "POST") {
      await sendJson(response, 200, await transcribeTalkLiteAudio(request));
      return;
    }
    if (url.pathname === "/api/talk-lite/ask" && request.method === "POST") {
      await sendJson(response, 200, await askTalkLiteVeritas(request));
      return;
    }
    if (url.pathname === "/api/talk-lite/tts" && request.method === "POST") {
      await sendJson(response, 200, await ttsTalkLiteText(request));
      return;
    }
    if (url.pathname === "/api/talk-lite/audio") {
      await sendTalkLiteAudio(response, url.searchParams.get("path") || "");
      return;
    }
    if (url.pathname === "/health") {
      const health = await buildHealth();
      await sendJson(response, health.status === "ok" ? 200 : 500, health);
      return;
    }
    if (url.pathname === "/command-center" || url.pathname.startsWith("/command-center/")) {
      await sendCommandCenter(response, url.pathname);
      return;
    }
    if ([
      "/randall",
      "/deliverables",
      "/veritas",
      "/pm",
      "/generic",
      "/smb",
      "/smb/scenarios",
      "/smb/service-runs",
      "/smb/customer-preview",
      "/academy",
      "/academy/current",
      "/workflows",
      "/workflows/routes",
      "/sql",
      "/sql/control-plane",
      "/sql/service-state",
      "/finance-os",
      "/talk-lite",
    ].includes(url.pathname)) {
      await sendStatic(response, "/");
      return;
    }
    await sendStatic(response, url.pathname);
  } catch (error) {
    await sendJson(response, 500, {
      status: "error",
      error: error instanceof Error ? error.message : String(error),
    });
  }
}

async function validateOnly(): Promise<number> {
  const state = await buildState();
  const fatal = state.health.status !== "ok";
  console.log(JSON.stringify({
    status: fatal ? "error" : "ok",
    registry: state.registry.path,
    source_count: state.health.source_count,
    missing_required_count: state.health.missing_required_count,
    stale_required_count: state.health.stale_required_count,
    readiness_score: state.summaries.readiness_score,
    selected_action_id: state.summaries.selected_action_id,
    closeout_ok: state.summaries.closeout_ok,
    dispatcher_present: state.summaries.dispatcher_present,
    academy_ready: state.summaries.academy_ready,
    sql_cache_present: state.summaries.sql_cache_present,
    sql_adapter_status: state.summaries.sql_adapter_status,
    errors: state.health.errors,
    warnings: state.health.warnings,
  }, null, 2));
  return fatal ? 1 : 0;
}

if (process.argv.includes("--validate")) {
  process.exitCode = await validateOnly();
} else {
  const server = createServer((request, response) => {
    void handleRequest(request, response);
  });
  server.listen(port, "127.0.0.1", () => {
    console.log(`PM control cockpit listening at http://127.0.0.1:${port}`);
    console.log(`Source registry: ${registryPath}`);
  });
}
