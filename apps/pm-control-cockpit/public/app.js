const $ = (selector) => document.querySelector(selector);
const emptyTemplate = $("#empty-state");
let currentState = null;
let talkRecorder = null;
let talkStream = null;
let talkChunks = [];
const talkState = {
  status: "idle",
  transcript: "",
  response: "",
  audioUrl: "",
  audioPath: "",
  turnId: "",
  sessionKey: "agent:main:talk-lite",
  autoSpeak: true,
  confirmBeforeSend: true,
  busy: false,
  recording: false,
  error: "",
  turns: [],
};

function text(value, fallback = "unknown") {
  return value === undefined || value === null || value === "" ? fallback : String(value);
}

function statusKind(value) {
  const lower = text(value, "").toLowerCase();
  if (["ok", "ready", "active", "installed_or_present", "ready_for_main_session", "complete_for_now"].includes(lower)) return "good";
  if (lower.includes("blocked") || lower.includes("error") || lower.includes("failed") || lower.includes("missing")) return "bad";
  if (lower.includes("warning") || lower.includes("needs") || lower.includes("review") || lower.includes("stale")) return "warn";
  return "neutral";
}

function badge(value) {
  return `<span class="badge ${statusKind(value)}">${escapeHtml(text(value))}</span>`;
}

function escapeHtml(value) {
  return text(value, "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  }[char]));
}

function formatTime(value) {
  if (!value) return "unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return text(value);
  return date.toLocaleString([], { dateStyle: "short", timeStyle: "medium" });
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let amount = bytes;
  let unit = 0;
  while (amount >= 1024 && unit < units.length - 1) {
    amount /= 1024;
    unit += 1;
  }
  return `${amount.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}

function list(items, renderer) {
  if (!Array.isArray(items) || items.length === 0) return emptyTemplate.innerHTML;
  return `<div class="list">${items.map(renderer).join("")}</div>`;
}

function table(headers, rows) {
  if (!rows || rows.length === 0) return emptyTemplate.innerHTML;
  return `<div class="scroll"><table><thead><tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
}

function metric(label, value, kind = "neutral") {
  return `<div class="metric"><div class="label">${escapeHtml(label)}</div><div class="value ${kind}">${escapeHtml(text(value))}</div></div>`;
}

function progress(score) {
  const width = Math.max(0, Math.min(100, Number(score) || 0));
  return `<div class="progress" title="${width}%"><span style="width:${width}%"></span></div>`;
}

function source(key) {
  return currentState?.sources?.find((item) => item.key === key) || {};
}

function renderStatusStrip(state) {
  const readiness = state.pm.readiness || {};
  const healthKind = state.health.status === "ok" ? "good" : "bad";
  $("#status-strip").innerHTML = [
    metric("Network", "127.0.0.1 only", "good"),
    metric("Authority", "review-only", "warn"),
    metric("Paper / Live", "blocked", "good"),
    metric("Proof State", Number(state.health.stale_required_count || 0) ? "stale present" : "fresh enough", Number(state.health.stale_required_count || 0) ? "warn" : "good"),
    metric("Randall View", state.randall?.status || state.health.status, statusKind(state.randall?.status || state.health.status)),
    metric("Finance Proof Queue", `${text(state.summaries.finance_os_owner_action_queue, 0)} owner rows`, Number(state.summaries.finance_os_owner_action_queue || 0) ? "warn" : "good"),
    metric("Deliverables", `${text(state.summaries.deliverables_published_count, 0)} published`, Number(state.summaries.deliverables_error_count || 0) ? "bad" : "good"),
    metric("PM Readiness", `${text(readiness.average_score)} ${text(readiness.readiness_band, "")}`.trim(), statusKind(readiness.readiness_band)),
    metric("Lanes", `${text(readiness.ready_or_complete_lanes, 0)} / ${text(readiness.lane_count, 0)} ready`, "neutral"),
    metric("Blockers", text(readiness.blocked_lanes, 0), Number(readiness.blocked_lanes || 0) ? "bad" : "good"),
    metric("Needs Validation", text(readiness.needs_validation_lanes, 0), Number(readiness.needs_validation_lanes || 0) ? "warn" : "good"),
    metric("Academy", state.summaries.academy_ready ? "ready" : "review", state.summaries.academy_ready ? "good" : "warn"),
    metric("Workflow Routes", `${text(state.summaries.workflow_routes, 0)} routes`, Number(state.summaries.workflow_stale_or_aging || 0) ? "warn" : "good"),
    metric("SQL Adapter", state.summaries.sql_adapter_status || (state.summaries.sql_cache_present ? "present" : "missing"), statusKind(state.summaries.sql_adapter_status || "warning")),
    metric("Closeout", state.closeout.status === "ok" && Number(state.closeout.failure_count || 0) === 0 ? "ok" : text(state.closeout.status), statusKind(state.closeout.status)),
    metric("Health", state.health.status, healthKind),
  ].join("");
}

function renderOverview(state) {
  const selected = state.handoff.selected_action || {};
  const changed = state.pm.changed_since_last_run || {};
  $("#overview").innerHTML = `
    <div class="grid">
      <section class="section">
        <h2>Current PM State</h2>
        <div class="grid-3">
          ${metric("Generated", formatTime(state.pm.generated_at_utc), "neutral")}
          ${metric("Selected Action", selected.action_id || "none", statusKind(selected.lane_status))}
          ${metric("Dispatcher", state.summaries.dispatcher_present ? "installed" : "missing", state.summaries.dispatcher_present ? "good" : "bad")}
        </div>
      </section>
      <section class="section">
        <h2>Changed Since Last Run</h2>
        <dl class="kv">
          <dt>Previous run</dt><dd>${escapeHtml(formatTime(changed.previous_generated_at_utc))}</dd>
          <dt>Next action changed</dt><dd>${badge(Boolean(changed.next_action_changed))}</dd>
          <dt>Lane status changes</dt><dd>${escapeHtml(text(changed.lane_status_changes?.length, 0))}</dd>
          <dt>New blockers</dt><dd>${escapeHtml(text(changed.new_blockers?.length, 0))}</dd>
          <dt>Resolved blockers</dt><dd>${escapeHtml(text(changed.resolved_blockers?.length, 0))}</dd>
        </dl>
      </section>
    </div>
    <section class="section">
      <h2>Ranked Next Actions</h2>
      ${renderActionList(state.pm.next_actions)}
    </section>
  `;
}

function renderRandall(state) {
  const randall = state.randall || {};
  const finance = randall.finance || {};
  const deliverables = randall.deliverables_summary || {};
  const noteRows = (randall.human_notes || []).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.title))}</strong></td>
      <td>${escapeHtml(text(item.role))}</td>
      <td class="source-path mono">${escapeHtml(text(item.path))}</td>
    </tr>
  `);
  const priorityRows = (finance.priority_queue || []).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.ticker))}</strong><br><span class="muted">${escapeHtml(text(item.name))}</span></td>
      <td>${badge(item.auto_tier)}</td>
      <td>${badge(item.auto_state || item.primary_state)}</td>
      <td>${escapeHtml(text(item.review_priority_score))}</td>
      <td>${badge(item.actionability)}</td>
      <td>${escapeHtml(text(item.priority_boundary))}</td>
    </tr>
  `);
  const ownerRows = (finance.owner_action_queue || []).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.ticker))}</strong><br><span class="muted">${escapeHtml(text(item.name))}</span></td>
      <td>${badge(item.auto_tier)}</td>
      <td>${badge(item.band_status)}</td>
      <td>${escapeHtml(text(item.latest_known_price))}</td>
      <td>${badge(item.actionability)}</td>
    </tr>
  `);
  const sourceRows = (randall.source_health || []).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.title))}</strong><br><span class="muted mono">${escapeHtml(text(item.key))}</span></td>
      <td>${badge(item.exists ? "exists" : "missing")}</td>
      <td>${badge(item.stale ? "stale" : "fresh")}</td>
      <td>${badge(item.status || item.validation_status || "n/a")}</td>
      <td class="source-path mono">${escapeHtml(text(item.path))}</td>
    </tr>
  `);
  $("#randall").innerHTML = `
    <div class="grid-3">
      ${metric("Randall View", randall.status || "unknown", statusKind(randall.status))}
      ${metric("Finance OS", finance.status || "unknown", statusKind(finance.status))}
      ${metric("Deliverables", `${text(deliverables.published_count, 0)} / ${text(deliverables.item_count, 0)}`, Number(deliverables.error_count || 0) ? "bad" : "good")}
      ${metric("SQL Canon Answers", text(state.summaries.finance_sql_canon_production_answer_count, 0), "neutral")}
      ${metric("Workflow Routes", text(state.summaries.workflow_routes, 0), Number(state.summaries.workflow_stale_or_aging || 0) ? "warn" : "good")}
      ${metric("Health", state.health.status, statusKind(state.health.status))}
    </div>
    <section class="section">
      <h2>Human Read Stack</h2>
      ${table(["Surface", "Role", "Path"], noteRows)}
    </section>
    <section class="section">
      <h2>Finance Priority Queue</h2>
      ${table(["Ticker", "Tier", "State", "Score", "Actionability", "Boundary"], priorityRows)}
    </section>
    <section class="section">
      <h2>Owner Action Queue</h2>
      ${table(["Ticker", "Tier", "Band", "Price", "Actionability"], ownerRows)}
    </section>
    <div class="grid">
      <section class="section">
        <h2>Authority Stops</h2>
        <div class="chips">${(randall.stop_lines || []).map((item) => badge(item)).join("")}</div>
      </section>
      <section class="section">
        <h2>Randall Source Health</h2>
        ${table(["Source", "Exists", "Freshness", "Status", "Path"], sourceRows)}
      </section>
    </div>
  `;
}

function renderDeliverables(state) {
  const deliverables = state.deliverables || {};
  const summary = deliverables.summary || {};
  const itemRows = (deliverables.items || []).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.title))}</strong><br><span class="muted">${escapeHtml(text(item.category))}</span></td>
      <td>${badge(item.kind)}</td>
      <td>${badge(item.destination_exists ? "published" : "missing")}</td>
      <td>${escapeHtml(formatBytes(item.size_bytes))}</td>
      <td class="source-path mono">${escapeHtml(text(item.deliverable_path))}</td>
      <td class="source-path mono">${escapeHtml(text(item.source_path))}</td>
    </tr>
  `);
  const sourceRows = [
    ...(deliverables.source_health || []),
    ...(deliverables.human_notes_source_health || []),
  ].map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.title))}</strong><br><span class="muted mono">${escapeHtml(text(item.key))}</span></td>
      <td>${badge(item.exists ? "exists" : "missing")}</td>
      <td>${badge(item.stale ? "stale" : "fresh")}</td>
      <td>${badge(item.status || item.validation_status || "n/a")}</td>
      <td class="source-path mono">${escapeHtml(text(item.path))}</td>
    </tr>
  `);
  $("#deliverables").innerHTML = `
    <div class="grid-3">
      ${metric("Published", text(summary.published_count, 0), Number(summary.error_count || 0) ? "bad" : "good")}
      ${metric("Catalog Items", text(summary.item_count, 0), "neutral")}
      ${metric("Copied This Run", text(summary.copied_count, 0), "neutral")}
      ${metric("Errors", text(summary.error_count, 0), Number(summary.error_count || 0) ? "bad" : "good")}
      ${metric("Categories", (summary.categories || []).length, "neutral")}
      ${metric("Source Size", formatBytes(summary.total_source_bytes), "neutral")}
    </div>
    <section class="section">
      <h2>Published Deliverables</h2>
      ${table(["Deliverable", "Kind", "Status", "Size", "Shelf Path", "Source Path"], itemRows)}
    </section>
    <section class="section">
      <h2>Deliverable Source Health</h2>
      ${table(["Source", "Exists", "Freshness", "Status", "Path"], sourceRows)}
    </section>
  `;
}

function renderActionList(actions) {
  return list(actions, (action) => `
    <article class="row-card">
      <div class="row-title">
        <strong>${escapeHtml(text(action.rank))}. ${escapeHtml(text(action.description))}</strong>
        ${badge(action.lane_status || action.authority)}
      </div>
      <dl class="kv">
        <dt>Action</dt><dd class="mono">${escapeHtml(text(action.action_id))}</dd>
        <dt>Lane</dt><dd>${escapeHtml(text(action.lane_id))}</dd>
        <dt>Authority</dt><dd>${badge(action.authority)}</dd>
        <dt>Heartbeat executes</dt><dd>${badge(action.heartbeat_may_execute)}</dd>
        <dt>Main helper allowed</dt><dd>${badge(action.helper_lane_allowed_from_main_session)}</dd>
        <dt>Stop lines</dt><dd><div class="chips">${(action.stop_lines || []).map((item) => badge(item)).join("")}</div></dd>
      </dl>
    </article>
  `);
}

function renderLanes(state) {
  const rows = (state.pm.lanes || []).map((lane) => `
    <tr>
      <td><strong>${escapeHtml(text(lane.title || lane.lane_id))}</strong><br><span class="muted mono">${escapeHtml(text(lane.lane_id))}</span></td>
      <td>${badge(lane.status)}</td>
      <td>${escapeHtml(text(lane.readiness_score))}<br>${progress(lane.readiness_score)}</td>
      <td>${escapeHtml(text(lane.readiness_contribution))}</td>
      <td>${escapeHtml(text(lane.blocker_count || lane.blockers?.length || 0))}</td>
      <td>${escapeHtml(text(lane.next_action?.description || lane.next_action))}</td>
    </tr>
  `);
  const blockerRows = (state.pm.blockers || []).map((blocker) => `
    <tr>
      <td>${escapeHtml(text(blocker.lane_id))}</td>
      <td>${badge(blocker.severity || blocker.status)}</td>
      <td>${escapeHtml(text(blocker.description || blocker.blocker))}</td>
      <td>${escapeHtml(text(blocker.next_action))}</td>
    </tr>
  `);
  $("#lanes").innerHTML = `
    <section class="section">
      <h2>Lane Scoreboard</h2>
      ${table(["Lane", "Status", "Score", "Contribution", "Blockers", "Next"], rows)}
    </section>
    <section class="section">
      <h2>Blocker Register</h2>
      ${table(["Lane", "Severity", "Blocker", "Next"], blockerRows)}
    </section>
  `;
}

function renderHandoff(state) {
  const contract = state.handoff.main_session_contract || {};
  const selected = state.handoff.selected_action || {};
  $("#handoff").innerHTML = `
    <div class="grid">
      <section class="section">
        <h2>Main-Session Handoff</h2>
        <dl class="kv">
          <dt>Status</dt><dd>${badge(state.handoff.status)}</dd>
          <dt>Generated</dt><dd>${escapeHtml(formatTime(state.handoff.generated_at_utc))}</dd>
          <dt>Selected action</dt><dd class="mono">${escapeHtml(text(selected.action_id))}</dd>
          <dt>Lane</dt><dd>${escapeHtml(text(selected.lane_id))}</dd>
          <dt>Validation</dt><dd>${badge(state.handoff.validation?.status)}</dd>
          <dt>Dispatch</dt><dd>${escapeHtml(text(contract.dispatch_text))}</dd>
        </dl>
      </section>
      <section class="section">
        <h2>Autonomy</h2>
        <dl class="kv">
          <dt>Heartbeat</dt><dd>${badge(state.autonomy.heartbeat_status)}</dd>
          <dt>Heartbeat handoff</dt><dd>${badge(state.autonomy.heartbeat_handoff?.status)}</dd>
          <dt>Cron plan</dt><dd>${badge(state.autonomy.cron_status)}</dd>
          <dt>Dispatcher</dt><dd>${badge(state.autonomy.live_cron_state?.dispatcher_present ? "present" : "missing")}</dd>
          <dt>Dispatcher job</dt><dd class="mono">${escapeHtml(text(state.autonomy.live_cron_state?.dispatcher_job_id))}</dd>
        </dl>
      </section>
    </div>
    <section class="section">
      <h2>Execution Contract</h2>
      ${list(contract.execute_in_order || [], (item) => `<article class="row-card">${escapeHtml(item)}</article>`)}
    </section>
    <section class="section">
      <h2>After Execution</h2>
      ${list(contract.after_execution || [], (item) => `<article class="row-card mono">${escapeHtml(item)}</article>`)}
    </section>
  `;
}

function renderTalkLite(state) {
  const talk = state.talk_lite || {};
  if (!talkState.sessionKey && talk.session_key) talkState.sessionKey = talk.session_key;
  const boundary = talk.authority_boundary || {};
  const turnRows = talkState.turns.slice(0, 8).map((turn) => `
    <tr>
      <td>${badge(turn.status || "ok")}</td>
      <td>${escapeHtml(formatTime(turn.generated_at_utc))}</td>
      <td class="source-path">${escapeHtml(text(turn.transcript))}</td>
      <td class="source-path">${escapeHtml(text(turn.reply_text))}</td>
    </tr>
  `);
  $("#talk-lite").innerHTML = `
    <div class="grid-3">
      ${metric("Surface", boundary.local_only === false ? "exposed" : "local-only", boundary.local_only === false ? "bad" : "good")}
      ${metric("Mode", "push-to-talk", "neutral")}
      ${metric("Voice Output", boundary.microsoft_tts_allowed === false ? "blocked" : "Microsoft TTS", boundary.microsoft_tts_allowed === false ? "bad" : "good")}
      ${metric("Realtime API", boundary.realtime_openai_voice_api_used ? "used" : "not used", boundary.realtime_openai_voice_api_used ? "bad" : "good")}
      ${metric("Authority", boundary.review_only === false ? "unsafe" : "review-only", boundary.review_only === false ? "bad" : "warn")}
      ${metric("Paper / Live", boundary.paper_or_live_execution_allowed ? "allowed" : "blocked", boundary.paper_or_live_execution_allowed ? "bad" : "good")}
    </div>
    <div class="grid">
      <section class="section">
        <h2>Talk Lite</h2>
        <div class="talk-controls">
          <button id="talk-record" type="button" class="${talkState.recording ? "recording" : ""}" data-action="${talkState.recording ? "talk-stop" : "talk-start"}" ${talkState.busy ? "disabled" : ""}>${talkState.recording ? "Stop" : "Record"}</button>
          <label class="button-link file-button" for="talk-file">Upload</label>
          <input id="talk-file" class="hidden-file" type="file" accept="audio/*" ${talkState.busy || talkState.recording ? "disabled" : ""} />
          <button type="button" data-action="talk-send" ${talkState.busy || !talkState.transcript.trim() ? "disabled" : ""}>Send to Veritas</button>
          <button type="button" data-action="talk-speak" ${talkState.busy || !talkState.response.trim() ? "disabled" : ""}>Speak Reply</button>
          <button type="button" data-action="talk-clear" ${talkState.busy ? "disabled" : ""}>Clear</button>
        </div>
        <div class="talk-options">
          <label><input id="talk-confirm" type="checkbox" ${talkState.confirmBeforeSend ? "checked" : ""} /> Confirm before send</label>
          <label><input id="talk-autospeak" type="checkbox" ${talkState.autoSpeak ? "checked" : ""} /> Speak response</label>
        </div>
        <label class="field-label" for="talk-session-key">Session</label>
        <input id="talk-session-key" class="text-input mono" type="text" value="${escapeHtml(talkState.sessionKey || talk.session_key || "agent:main:talk-lite")}" />
        <label class="field-label" for="talk-transcript">Transcript</label>
        <textarea id="talk-transcript" class="talk-textarea" rows="8">${escapeHtml(talkState.transcript)}</textarea>
        <div class="talk-status">
          ${badge(talkState.status)}
          ${talkState.error ? badge(talkState.error) : ""}
          ${talkState.turnId ? `<span class="muted mono">${escapeHtml(talkState.turnId)}</span>` : ""}
        </div>
      </section>
      <section class="section">
        <h2>Response</h2>
        <div id="talk-response" class="talk-response">${escapeHtml(talkState.response || "No response yet.")}</div>
        ${talkState.audioUrl ? `<audio class="talk-audio" controls src="${escapeHtml(talkState.audioUrl)}"></audio>` : ""}
        <dl class="kv">
          <dt>Audio path</dt><dd class="mono">${escapeHtml(text(talkState.audioPath, "none"))}</dd>
          <dt>Transcript preview</dt><dd>${badge(talkState.confirmBeforeSend ? "required" : "quick")}</dd>
          <dt>Config/Auth</dt><dd>${badge(boundary.config_auth_runtime_mutation_allowed ? "allowed" : "blocked")}</dd>
          <dt>Canon/Portfolio</dt><dd>${badge(boundary.canon_or_portfolio_mutation_allowed ? "allowed" : "blocked")}</dd>
        </dl>
      </section>
    </div>
    <section class="section">
      <h2>Local Turn Log</h2>
      ${table(["Status", "Time", "Transcript", "Reply"], turnRows)}
    </section>
  `;
}

function renderCloseout(state) {
  const commandRows = (state.closeout.results || []).map((result) => `
    <tr>
      <td>${badge(result.status)}</td>
      <td class="mono">${escapeHtml(text(result.command))}</td>
      <td>${escapeHtml(text(result.returncode))}</td>
      <td>${escapeHtml(formatTime(result.finished_at_utc))}</td>
    </tr>
  `);
  $("#closeout").innerHTML = `
    <div class="grid-3">
      ${metric("Closeout Status", state.closeout.status, statusKind(state.closeout.status))}
      ${metric("Commands", `${text(state.closeout.command_count, 0)} total`, "neutral")}
      ${metric("Failures", text(state.closeout.failure_count, 0), Number(state.closeout.failure_count || 0) ? "bad" : "good")}
    </div>
    <section class="section">
      <h2>WF75 Closeout Commands</h2>
      ${table(["Status", "Command", "Code", "Finished"], commandRows)}
    </section>
    <section class="section">
      <h2>Refreshed Outputs</h2>
      ${list(state.closeout.outputs || [], (item) => `<article class="row-card mono">${escapeHtml(item)}</article>`)}
    </section>
  `;
}

function renderSmb(state) {
  const smb = state.smb || {};
  const contract = smb.contract || {};
  const library = smb.scenario_library || {};
  const preview = smb.customer_preview || {};
  const validation = smb.customer_preview_validation || {};
  const pilot = smb.pilot_decision_packet || {};
  const automation = smb.automation_blueprints || {};
  const automationValidation = smb.automation_blueprints_validation || {};
  const offerIcp = smb.offer_icp_packet || {};
  const demos = smb.demo_packets || {};
  const demoValidation = smb.demo_packets_validation || {};
  const marketingOps = smb.marketing_ops_blueprints || {};
  const marketingOpsValidation = smb.marketing_ops_blueprints_validation || {};
  const cockpitPanel = smb.cockpit_panel || {};
  const salesPractice = smb.sales_practice_packet || {};
  const phaseCloseout = smb.phase_closeout || {};
  const phaseRows = (cockpitPanel.phase_statuses || phaseCloseout.phases || []).map((phase) => `
    <tr>
      <td><strong>${escapeHtml(text(phase.title || phase.name))}</strong><br><span class="muted mono">${escapeHtml(text(phase.phase_id || phase.phase))}</span></td>
      <td>${badge(phase.status)}</td>
      <td class="source-path mono">${escapeHtml(text(phase.artifact))}</td>
    </tr>
  `);
  const demoRows = (demos.demos || []).map((demo) => `
    <tr>
      <td><strong>${escapeHtml(text(demo.title))}</strong><br><span class="muted mono">${escapeHtml(text(demo.demo_id))}</span></td>
      <td>${escapeHtml(text(demo.manual_packet_summary?.failure_mode))}</td>
      <td>${escapeHtml(text(demo.manual_packet_summary?.next_best_manual_step))}</td>
      <td>${badge(demo.automation_blueprint?.activation_state)}</td>
    </tr>
  `);
  const marketingRows = (marketingOps.blueprints || []).map((blueprint) => `
    <tr>
      <td><strong>${escapeHtml(text(blueprint.title))}</strong><br><span class="muted mono">${escapeHtml(text(blueprint.blueprint_id))}</span></td>
      <td>${escapeHtml(text(blueprint.purpose))}</td>
      <td>${escapeHtml(text(blueprint.input_contract?.dedup_key))}</td>
      <td>${badge(blueprint.activation_state)}</td>
    </tr>
  `);
  const sectionRows = (preview.preview_sections || []).map((section) => `
    <tr>
      <td><strong>${escapeHtml(text(section.title))}</strong></td>
      <td>${escapeHtml(text(section.customer_visible_summary))}</td>
      <td>${(section.source_scenarios || []).map((item) => badge(item)).join(" ")}</td>
    </tr>
  `);
  const blueprintRows = (automation.blueprints || []).map((blueprint) => `
    <tr>
      <td><strong>${escapeHtml(text(blueprint.blueprint_id))}</strong><br><span class="muted">${(blueprint.scenario_ids || []).map((item) => badge(item)).join(" ")}</span></td>
      <td>${escapeHtml(text(blueprint.trigger?.type))}<br><span class="muted">${escapeHtml(text(blueprint.trigger?.source))}</span></td>
      <td>${escapeHtml(text(blueprint.input_contract?.dedup_key))}</td>
      <td>${badge(blueprint.activation_state)}</td>
      <td>${escapeHtml(text(blueprint.tool_candidate))}</td>
    </tr>
  `);
  const sourceRows = (smb.source_health || []).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.title))}</strong><br><span class="muted mono">${escapeHtml(text(item.key))}</span></td>
      <td>${badge(item.exists ? "exists" : "missing")}</td>
      <td>${badge(item.stale ? "stale" : "fresh")}</td>
      <td>${badge(item.status || item.validation_status || "n/a")}</td>
      <td class="source-path mono">${escapeHtml(text(item.path))}</td>
    </tr>
  `);
  $("#smb").innerHTML = `
    <div class="grid-3">
      ${metric("Contract", contract.status || "missing", statusKind(contract.status))}
      ${metric("Scenarios", library.scenario_count || 0, "neutral")}
      ${metric("Preview Validation", validation.status || validation.validation?.status || "missing", statusKind(validation.status || validation.validation?.status))}
      ${metric("Blueprints", automation.blueprint_count || 0, "neutral")}
      ${metric("Blueprint Validation", automationValidation.status || automationValidation.validation?.status || "missing", statusKind(automationValidation.status || automationValidation.validation?.status))}
      ${metric("Demo Validation", demoValidation.status || demoValidation.validation?.status || "missing", statusKind(demoValidation.status || demoValidation.validation?.status))}
      ${metric("Marketing Ops", marketingOps.blueprint_count || 0, "neutral")}
      ${metric("Phase Closeout", phaseCloseout.status || "missing", statusKind(phaseCloseout.status))}
    </div>
    <section class="section">
      <h2>Phase Panel</h2>
      <dl class="kv">
        <dt>Positioning</dt><dd>${escapeHtml(text(offerIcp.positioning?.plain_language_offer))}</dd>
        <dt>Next safe action</dt><dd>${escapeHtml(text(cockpitPanel.next_safe_action || phaseCloseout.remaining_gate))}</dd>
        <dt>Sales practice</dt><dd>${badge(salesPractice.practice_mode || salesPractice.status)}</dd>
      </dl>
      ${table(["Phase", "Status", "Artifact"], phaseRows)}
    </section>
    <section class="section">
      <h2>Lead Rescue Preview</h2>
      <dl class="kv">
        <dt>Offer</dt><dd>${escapeHtml(text(preview.offer_name))}</dd>
        <dt>Preview kind</dt><dd>${badge(preview.preview_kind)}</dd>
        <dt>Pilot posture</dt><dd>${badge(pilot.pilot_posture)}</dd>
        <dt>Decision needed</dt><dd>${escapeHtml(text(pilot.decision_needed))}</dd>
      </dl>
    </section>
    <section class="section">
      <h2>Customer Preview Sections</h2>
      ${table(["Section", "Summary", "Sources"], sectionRows)}
    </section>
    <section class="section">
      <h2>Dry-Run Automation Blueprints</h2>
      ${table(["Blueprint", "Trigger", "Dedup Key", "Activation", "Tool Candidate"], blueprintRows)}
    </section>
    <section class="section">
      <h2>Sanitized Demo Packets</h2>
      ${table(["Demo", "Failure Mode", "Next Manual Step", "Activation"], demoRows)}
    </section>
    <section class="section">
      <h2>Marketing Ops Blueprints</h2>
      ${table(["Blueprint", "Purpose", "Dedup Key", "Activation"], marketingRows)}
    </section>
    <div class="grid">
      <section class="section">
        <h2>Sample Outputs</h2>
        ${list(preview.sample_outputs || [], (item) => `<article class="row-card">${escapeHtml(item)}</article>`)}
      </section>
      <section class="section">
        <h2>Explicit Exclusions</h2>
        ${list(pilot.explicit_exclusions || preview.positioning?.not_in_scope || [], (item) => `<article class="row-card">${escapeHtml(item)}</article>`)}
      </section>
    </div>
    <section class="section">
      <h2>SMB Source Health</h2>
      ${table(["Source", "Exists", "Freshness", "Status", "Path"], sourceRows)}
    </section>
  `;
}

function renderAcademy(state) {
  const academy = state.academy || {};
  const current = academy.current || {};
  const manifest = academy.manifest || {};
  const lesson = academy.current_lesson || {};
  const posture = academy.training_posture || {};
  const assetRows = Object.entries(academy.asset_outputs || {}).map(([key, value]) => `
    <tr>
      <td class="mono">${escapeHtml(key)}</td>
      <td class="source-path mono">${escapeHtml(text(value))}</td>
    </tr>
  `);
  const planRows = (academy.daily_plan || []).map((item) => `
    <tr>
      <td>${escapeHtml(text(item.day))}</td>
      <td><strong>${escapeHtml(text(item.title))}</strong><br><span class="muted">${escapeHtml(text(item.duration_minutes))} minutes</span></td>
      <td>${escapeHtml(text(item.practice))}</td>
      <td>${escapeHtml(text(item.acceptance))}</td>
    </tr>
  `);
  const healthRows = (academy.source_health || []).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.title))}</strong><br><span class="muted mono">${escapeHtml(text(item.key))}</span></td>
      <td>${badge(item.exists ? "exists" : "missing")}</td>
      <td>${badge(item.stale ? "stale" : "fresh")}</td>
      <td>${badge(item.status || item.validation_status || "n/a")}</td>
      <td class="source-path mono">${escapeHtml(text(item.path))}</td>
    </tr>
  `);
  $("#academy").innerHTML = `
    <div class="grid-3">
      ${metric("Academy", current.current_training_posture?.academy_live ? "live" : "review", current.current_training_posture?.academy_live ? "good" : "warn")}
      ${metric("Manifest", manifest.status || "missing", statusKind(manifest.status))}
      ${metric("Mode", current.current_training_posture?.mode || "unknown", "neutral")}
    </div>
    <section class="section">
      <h2>Current Lesson</h2>
      <dl class="kv">
        <dt>Department</dt><dd>${escapeHtml(text(current.department_name))}</dd>
        <dt>Daily cadence</dt><dd>${escapeHtml(text(current.current_training_posture?.recommended_daily_time))}</dd>
        <dt>Weekly review</dt><dd>${escapeHtml(text(current.current_training_posture?.weekly_review_time))}</dd>
        <dt>Lesson</dt><dd><strong>${escapeHtml(text(lesson.title))}</strong></dd>
        <dt>Objective</dt><dd>${escapeHtml(text(lesson.teaching_objective))}</dd>
        <dt>Training posture</dt><dd>${Object.entries(posture).map(([key, value]) => `${escapeHtml(key)} ${badge(value)}`).join(" ")}</dd>
      </dl>
    </section>
    <div class="grid">
      <section class="section">
        <h2>Training Assets</h2>
        ${table(["Asset", "Path"], assetRows)}
      </section>
      <section class="section">
        <h2>Stop Lines</h2>
        ${list(current.stop_lines || [], (item) => `<article class="row-card">${badge(item)}</article>`)}
      </section>
    </div>
    <section class="section">
      <h2>Daily Micro-Learning Plan</h2>
      ${table(["Day", "Lesson", "Practice", "Acceptance"], planRows)}
    </section>
    <section class="section">
      <h2>Academy Source Health</h2>
      ${table(["Source", "Exists", "Freshness", "Status", "Path"], healthRows)}
    </section>
  `;
}

function renderRetail(state) {
  const retail = state.retail?.automation || {};
  const visibility = retail.operator_visibility || {};
  const sql = retail.sql_support_health || {};
  const customer = retail.customer_safety_gate || {};
  const decision = retail.customer_output_decision || {};
  const regression = retail.seeded_bad_regression || {};
  const quiet = retail.quiet_cron_summary || {};
  const routeRows = (visibility.routes || []).map((route) => `
    <tr>
      <td><strong>${escapeHtml(text(route.route_id))}</strong><br><span class="muted">${escapeHtml(text(route.sql_role))}</span></td>
      <td>${badge(route.status)}</td>
      <td>${badge(route.source_open_gate)}</td>
      <td>${badge(route.fallback_decay_gate)}</td>
      <td>${badge(route.final_answer_posture)}</td>
    </tr>
  `);
  const demoRows = (retail.internal_demo_cards || []).map((card) => `
    <tr>
      <td>${escapeHtml(text(card.question))}</td>
      <td>${escapeHtml(text(card.route))}</td>
      <td>${badge(card.case)}</td>
      <td>${badge(card.category || "n/a")}</td>
      <td>${badge(card.answer_posture)}</td>
      <td>${escapeHtml(text(card.residue_count, 0))}</td>
    </tr>
  `);
  const sourceRows = (retail.source_artifacts || []).map((item) => `
    <tr>
      <td class="source-path mono">${escapeHtml(text(item.path))}</td>
      <td>${badge(item.exists ? "exists" : "missing")}</td>
      <td>${badge(item.status || item.validation_status || "n/a")}</td>
      <td>${escapeHtml(formatTime(item.mtime_utc))}</td>
    </tr>
  `);
  const categoryRows = Object.entries(regression.categories || {}).map(([key, value]) => `
    <tr><td class="mono">${escapeHtml(key)}</td><td>${badge(value ? "covered" : "missing")}</td></tr>
  `);
  $("#retail").innerHTML = `
    <div class="grid-3">
      ${metric("Retail Automation", retail.status || "missing", statusKind(retail.status))}
      ${metric("Route Gates", `${text(visibility.route_count, 0)} routes`, "neutral")}
      ${metric("Harness", `${text(visibility.harness_score?.checks_total, 0)} checks`, statusKind(visibility.harness_score?.status))}
      ${metric("SQL Support", `${text(sql.a2_guard_status)} / ${text(sql.wf78_status)}`, statusKind(sql.a2_guard_status))}
      ${metric("Customer Gate", `${text(customer.customer_export_validator_status)} / seeded ${text(customer.seeded_bad_validation_status)}`, statusKind(customer.customer_export_validator_status))}
      ${metric("Output Decision", decision.decision || "customer_output_blocked", statusKind(decision.status))}
      ${metric("Unsafe Coverage", `${text(regression.blocked_as_expected, 0)} / ${text(regression.seeded_bad_cases, 0)} blocked`, statusKind(regression.blocked_as_expected === regression.seeded_bad_cases ? "ok" : "warning"))}
      ${metric("Quiet Summary", quiet.mode || "unknown", statusKind(quiet.mode))}
    </div>
    <section class="section">
      <h2>Customer Output Decision</h2>
      <dl class="kv">
        <dt>Status</dt><dd>${badge(decision.status || "blocked")}</dd>
        <dt>Decision</dt><dd>${badge(decision.decision || "customer_output_blocked")}</dd>
        <dt>Internal answer-safety</dt><dd>${badge(decision.internal_answer_safety_ready ? "ready" : "not_ready")}</dd>
        <dt>Customer output</dt><dd>${badge(decision.customer_output_allowed ? "allowed" : "blocked")}</dd>
        <dt>Blockers</dt><dd>${(decision.blockers || []).map((item) => badge(item)).join(" ") || badge("none_listed")}</dd>
      </dl>
    </section>
    <section class="section">
      <h2>Truth Routing Gates</h2>
      ${table(["Route", "Status", "Source-Open", "Fallback-Decay", "Answer"], routeRows)}
    </section>
    <div class="grid">
      <section class="section">
        <h2>SQL Support Health</h2>
        <dl class="kv">
          <dt>Posture</dt><dd>${badge(sql.posture)}</dd>
          <dt>A2 read allowed</dt><dd>${badge(sql.a2_sql_read_allowed)}</dd>
          <dt>WF78 phase</dt><dd>${badge(sql.wf78_phase)}</dd>
          <dt>Universe</dt><dd>${escapeHtml(text(sql.universe?.total_tickers, 0))} total; ${escapeHtml(text(sql.universe?.production_answer_path_count, 0))} production; ${escapeHtml(text(sql.universe?.review_monitor_count, 0))} review-monitor</dd>
          <dt>Pilot candidates</dt><dd>${(sql.universe?.recommended_pilot_tickers || []).map((item) => badge(item)).join(" ")}</dd>
        </dl>
      </section>
      <section class="section">
        <h2>Safety Gate</h2>
        <dl class="kv">
          <dt>Posture</dt><dd>${badge(customer.posture)}</dd>
          <dt>Clean validator</dt><dd>${badge(customer.customer_export_validator_status)}</dd>
          <dt>Seeded-bad validator</dt><dd>${badge(customer.seeded_bad_validation_status)}</dd>
          <dt>Bad cases</dt><dd>${escapeHtml(text(regression.blocked_as_expected, 0))} / ${escapeHtml(text(regression.seeded_bad_cases, 0))} blocked</dd>
        </dl>
      </section>
    </div>
    <section class="section">
      <h2>Seeded-Bad Coverage</h2>
      ${table(["Category", "Coverage"], categoryRows)}
    </section>
    <section class="section">
      <h2>Internal Demo Cards</h2>
      ${table(["Question", "Route", "Case", "Category", "Answer", "Residue"], demoRows)}
    </section>
    <section class="section">
      <h2>Refresh Prompts</h2>
      ${list(retail.staleness_refresh_prompts || [], (item) => `<article class="row-card">${badge(item.severity)} ${escapeHtml(text(item.prompt))}</article>`)}
    </section>
    <section class="section">
      <h2>Retail Source Health</h2>
      ${table(["Path", "Exists", "Status", "Modified"], sourceRows)}
    </section>
  `;
}

function renderSql(state) {
  const sql = state.sql || {};
  const control = sql.control_plane || {};
  const counts = control.counts || {};
  const generic = control.generic || {};
  const wf75 = control.wf75 || {};
  const financeOs = control.finance_os || {};
  const durableCanon = financeOs.durable_canon || {};
  const durableSummary = (durableCanon.summary || [])[0] || {};
  const sourceLineageSummary = (durableCanon.source_lineage_summary || [])[0] || {};
  const sourceRows = (sql.state_sources || []).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.title))}</strong><br><span class="muted mono">${escapeHtml(text(item.key))}</span></td>
      <td>${badge(item.exists ? "exists" : "missing")}</td>
      <td>${badge(item.stale ? "stale" : "fresh")}</td>
      <td>${escapeHtml(text(item.age_hours, "n/a"))}</td>
      <td>${escapeHtml(text(item.role))}</td>
      <td class="source-path mono">${escapeHtml(text(item.path))}</td>
    </tr>
  `);
  const serviceRunRows = (generic.service_runs || []).map((item) => `
    <tr>
      <td class="mono">${escapeHtml(text(item.run_id))}</td>
      <td>${escapeHtml(text(item.domain))}</td>
      <td>${escapeHtml(text(item.scenario_id))}</td>
      <td>${badge(item.status)}</td>
      <td>${escapeHtml(formatTime(item.updated_at_utc))}</td>
    </tr>
  `);
  const requestRows = (wf75.service_requests || []).map((item) => `
    <tr>
      <td class="mono">${escapeHtml(text(item.request_id))}</td>
      <td>${escapeHtml(text(item.workflow))}</td>
      <td>${escapeHtml(text(item.request_type))}</td>
      <td>${badge(item.status)}</td>
      <td>${badge(item.real_customer_data_present ? "customer-data-present" : "anonymous")}</td>
      <td>${badge(item.external_delivery_allowed ? "external-allowed" : "internal-only")}</td>
      <td>${escapeHtml(formatTime(item.updated_at_utc))}</td>
    </tr>
  `);
  const queueRows = (wf75.queue_items || []).map((item) => `
    <tr>
      <td class="mono">${escapeHtml(text(item.queue_id))}</td>
      <td>${badge(item.status)}</td>
      <td>${escapeHtml(text(item.priority))}</td>
      <td>${escapeHtml(text(item.owner))}</td>
      <td>${escapeHtml(text(item.next_action))}</td>
      <td>${badge(item.inline_execution_allowed ? "inline-allowed" : "no-inline")}</td>
      <td>${badge(item.customer_data_use_allowed ? "customer-data-allowed" : "no-customer-data")}</td>
    </tr>
  `);
  const qaRows = (generic.qa_events || []).map((item) => `
    <tr>
      <td>${escapeHtml(text(item.event_type))}</td>
      <td>${badge(item.status)}</td>
      <td class="source-path mono">${escapeHtml(text(item.detail_json))}</td>
    </tr>
  `);
  const financePriorityRows = (financeOs.priority_queue || []).slice(0, 20).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.ticker))}</strong><br><span class="muted">${escapeHtml(text(item.name))}</span></td>
      <td>${badge(item.auto_tier)}</td>
      <td>${badge(item.auto_state)}</td>
      <td>${escapeHtml(text(item.review_priority_score))}</td>
      <td>${escapeHtml(text(item.actionability))}</td>
      <td>${badge(item.priority_boundary)}</td>
    </tr>
  `);
  const financeOwnerRows = (financeOs.owner_action_queue || []).slice(0, 20).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.ticker))}</strong><br><span class="muted">${escapeHtml(text(item.name))}</span></td>
      <td>${badge(item.auto_tier)}</td>
      <td>${badge(item.band_status)}</td>
      <td>${escapeHtml(text(item.latest_known_price))}</td>
      <td>${escapeHtml(text(item.actionability))}</td>
    </tr>
  `);
  const financeSourceRows = (financeOs.source_lineage || []).map((item) => `
    <tr>
      <td class="mono">${escapeHtml(text(item.artifact_id))}</td>
      <td class="source-path mono">${escapeHtml(text(item.path))}</td>
      <td>${escapeHtml(text(item.role))}</td>
      <td>${badge(item.status || item.validation_status || "unknown")}</td>
      <td>${escapeHtml(text(item.routing_rows, 0))}</td>
    </tr>
  `);
  const financeCanonRows = (durableCanon.routing || []).slice(0, 25).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.ticker))}</strong><br><span class="muted">${escapeHtml(text(item.name))}</span></td>
      <td>${badge(item.sql_tier || item.legacy_tier || item.auto_tier)}</td>
      <td>${badge(item.sql_tier_state || item.auto_state)}</td>
      <td>${badge(Number(item.production_scope_member) ? "production-scope" : (item.tier_decision_scope || item.universe_scope || "review-monitor"))}</td>
      <td>${badge(Number(item.production_card_generation_allowed) ? "card-allowed" : "card-blocked")}</td>
      <td>${badge(item.provider_status || "unknown")}</td>
    </tr>
  `);
  const registryRows = (durableCanon.registry || []).map((item) => `
    <tr>
      <td>${badge(item.priority)}</td>
      <td>${badge(item.cutover_state)}</td>
      <td>${escapeHtml(text(item.count, 0))}</td>
    </tr>
  `);
  const authorityRows = (durableCanon.authority_events || []).map((item) => `
    <tr>
      <td class="mono">${escapeHtml(text(item.key))}</td>
      <td>${escapeHtml(text(item.expected_value))}</td>
      <td>${escapeHtml(text(item.observed_value))}</td>
      <td>${badge(item.status)}</td>
    </tr>
  `);
  $("#sql").innerHTML = `
    <div class="grid-3">
      ${metric("SQL Posture", sql.posture || "unknown", "warn")}
      ${metric("Adapter", control.status || "missing", statusKind(control.status))}
      ${metric("Service Rows", `${text(counts.generic_service_runs, 0)} generic / ${text(counts.wf75_service_requests, 0)} WF75`, "neutral")}
      ${metric("Finance OS Queue", text(counts.finance_os_owner_action_queue, 0), Number(counts.finance_os_owner_action_queue || 0) ? "warn" : "good")}
      ${metric("SQL Answer Path", text(durableSummary.production_answer_count, counts.finance_os_durable_canon_production_answer_count || 0), Number(durableSummary.production_answer_count || 0) ? "warn" : "good")}
      ${metric("Canon Lineage Rows", text(sourceLineageSummary.row_count, 0), Number(sourceLineageSummary.row_count || 0) ? "good" : "warn")}
    </div>
    <section class="section">
      <h2>Integration Shape</h2>
      ${list(sql.current_integration || [], (item) => `<article class="row-card">${escapeHtml(item)}</article>`)}
    </section>
    <section class="section">
      <h2>Generic Service Runs From SQL</h2>
      ${table(["Run", "Domain", "Scenario", "Status", "Updated"], serviceRunRows)}
    </section>
    <section class="section">
      <h2>WF75 Service Requests From SQL</h2>
      ${table(["Request", "Workflow", "Type", "Status", "Data Boundary", "Delivery", "Updated"], requestRows)}
    </section>
    <section class="section">
      <h2>Operator Queue From SQL</h2>
      ${table(["Queue", "Status", "Priority", "Owner", "Next Action", "Inline", "Customer Data"], queueRows)}
    </section>
    <section class="section">
      <h2>Finance OS Priority Queue</h2>
      ${table(["Ticker", "Tier", "State", "Score", "Actionability", "Boundary"], financePriorityRows)}
    </section>
    <section class="section">
      <h2>Finance OS Owner Action Queue</h2>
      ${table(["Ticker", "Tier", "Band", "Price", "Actionability"], financeOwnerRows)}
    </section>
    <section class="section">
      <h2>Finance OS Source Lineage</h2>
      ${table(["Artifact", "Path", "Role", "Status", "Routing Rows"], financeSourceRows)}
    </section>
    <section class="section">
      <h2>Durable Finance Canon Scope</h2>
      ${table(["Ticker", "Tier", "State", "Scope", "Card", "Provider"], financeCanonRows)}
    </section>
    <section class="section">
      <h2>SQL Canon Consumer Migration Registry</h2>
      ${table(["Priority", "Cutover State", "Count"], registryRows)}
    </section>
    <section class="section">
      <h2>SQL Canon Authority Flags</h2>
      ${table(["Flag", "Expected", "Observed", "Status"], authorityRows)}
    </section>
    <div class="grid">
      <section class="section">
        <h2>Next API Candidates</h2>
        ${list(sql.next_api_candidates || [], (item) => `<article class="row-card mono">${escapeHtml(item)}</article>`)}
      </section>
      <section class="section">
        <h2>Blocked Authority</h2>
        ${list(sql.blocked_authority || [], (item) => `<article class="row-card">${badge(item)}</article>`)}
      </section>
    </div>
    <section class="section">
      <h2>Generic QA Events From SQL</h2>
      ${table(["Event", "Status", "Detail"], qaRows)}
    </section>
    <section class="section">
      <h2>Derived SQL Source Health</h2>
      ${table(["Source", "Exists", "Freshness", "Age hours", "Role", "Path"], sourceRows)}
    </section>
  `;
}

function renderWorkflows(state) {
  const workflow = state.workflow || {};
  const summary = workflow.summary || {};
  const sql = workflow.sql || {};
  const routeRows = (sql.routes || []).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.workflow_id))}</strong><br><span class="muted">${escapeHtml(text(item.display_name))}</span></td>
      <td>${badge(item.tier)}</td>
      <td>${badge(item.freshness_score)}</td>
      <td>${badge(Number(item.safe_for_helper_lane) ? "helper-safe" : "main-only")}</td>
      <td>${badge(Number(item.owner_action_required) ? "owner-gated" : "no-owner-action")}</td>
      <td>${escapeHtml(text(item.next_action))}</td>
    </tr>
  `);
  const staleRows = (sql.stale_routes || []).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.workflow_id))}</strong><br><span class="muted">${escapeHtml(text(item.display_name))}</span></td>
      <td>${badge(item.tier)}</td>
      <td>${badge(item.freshness_score)}</td>
      <td>${escapeHtml(text(item.next_action))}</td>
    </tr>
  `);
  const ownerRows = (sql.owner_gated || []).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.workflow_id))}</strong><br><span class="muted">${escapeHtml(text(item.display_name))}</span></td>
      <td>${badge(item.tier)}</td>
      <td>${badge(item.freshness_score)}</td>
      <td>${badge(Number(item.safe_for_helper_lane) ? "helper-safe" : "main-only")}</td>
      <td>${escapeHtml(text(item.authority_boundary))}</td>
    </tr>
  `);
  const freshnessRows = (sql.freshness_counts || []).map((item) => `
    <tr>
      <td>${badge(item.freshness_score)}</td>
      <td>${escapeHtml(text(item.count))}</td>
    </tr>
  `);
  const sourceRows = (workflow.source_health || []).map((item) => `
    <tr>
      <td><strong>${escapeHtml(text(item.title))}</strong><br><span class="muted mono">${escapeHtml(text(item.key))}</span></td>
      <td>${badge(item.exists ? "exists" : "missing")}</td>
      <td>${badge(item.stale ? "stale" : "fresh")}</td>
      <td>${badge(item.status || item.validation_status || "n/a")}</td>
      <td>${escapeHtml(text(item.age_hours, "n/a"))}</td>
      <td class="source-path mono">${escapeHtml(text(item.path))}</td>
    </tr>
  `);
  $("#workflows").innerHTML = `
    <div class="grid-3">
      ${metric("Route Index", `${text(summary.route_count, 0)} JSON / ${text(summary.sqlite_route_count, 0)} SQL`, statusKind(summary.validation_status || "warning"))}
      ${metric("Validation", `${text(summary.validation_critical, 0)} critical / ${text(summary.validation_warning, 0)} warning`, Number(summary.validation_critical || 0) ? "bad" : Number(summary.validation_warning || 0) ? "warn" : "good")}
      ${metric("SQLite", summary.sqlite_status || "unknown", statusKind(summary.sqlite_status || "warning"))}
      ${metric("Stale or Aging", text(summary.stale_or_aging_count, 0), Number(summary.stale_or_aging_count || 0) ? "warn" : "good")}
      ${metric("Helper Safe", text(summary.helper_safe_count, 0), "neutral")}
      ${metric("Owner Gated", text(summary.owner_gated_count, 0), Number(summary.owner_gated_count || 0) ? "warn" : "good")}
    </div>
    <section class="section">
      <h2>Workflow Route Status From SQL</h2>
      ${table(["Workflow", "Tier", "Freshness", "Helper", "Owner", "Next Action"], routeRows)}
    </section>
    <div class="grid">
      <section class="section">
        <h2>Freshness Counts</h2>
        ${table(["Freshness", "Count"], freshnessRows)}
      </section>
      <section class="section">
        <h2>Stale / Aging Routes</h2>
        ${table(["Workflow", "Tier", "Freshness", "Next Action"], staleRows)}
      </section>
    </div>
    <section class="section">
      <h2>Owner-Gated Routes</h2>
      ${table(["Workflow", "Tier", "Freshness", "Helper", "Authority"], ownerRows)}
    </section>
    <section class="section">
      <h2>Workflow Source Health</h2>
      ${table(["Source", "Exists", "Freshness", "Status", "Age hours", "Path"], sourceRows)}
    </section>
  `;
}

function renderSources(state) {
  const rows = (state.sources || []).map((item) => `
    <tr>
      <td><strong>${escapeHtml(item.title)}</strong><br><span class="muted mono">${escapeHtml(item.key)}</span></td>
      <td>${badge(item.exists ? "exists" : "missing")}</td>
      <td>${badge(item.stale ? "stale" : "fresh")}</td>
      <td>${badge(item.status || item.validation_status || "n/a")}</td>
      <td>${escapeHtml(text(item.age_hours, "n/a"))}</td>
      <td class="source-path mono">${escapeHtml(item.path)}</td>
    </tr>
  `);
  $("#sources").innerHTML = `
    <section class="section">
      <h2>Source Registry</h2>
      <dl class="kv">
        <dt>Registry</dt><dd class="mono">${escapeHtml(state.registry.path)}</dd>
        <dt>Sources</dt><dd>${escapeHtml(text(state.health.source_count))}</dd>
        <dt>Missing required</dt><dd>${badge(state.health.missing_required_count)}</dd>
        <dt>Stale required</dt><dd>${badge(state.health.stale_required_count)}</dd>
      </dl>
    </section>
    <section class="section">
      ${table(["Source", "Exists", "Freshness", "Status", "Age hours", "Path"], rows)}
    </section>
  `;
}

function renderAuthority(state) {
  const registryRows = Object.entries(state.registry.authority_boundary || {}).map(([key, value]) => `
    <tr><td class="mono">${escapeHtml(key)}</td><td>${badge(value)}</td></tr>
  `);
  const pmRows = Object.entries(state.pm.authority_boundary || {}).map(([key, value]) => `
    <tr><td class="mono">${escapeHtml(key)}</td><td>${badge(value)}</td></tr>
  `);
  $("#authority").innerHTML = `
    <div class="grid">
      <section class="section">
        <h2>Registry Authority Boundary</h2>
        ${table(["Flag", "Value"], registryRows)}
      </section>
      <section class="section">
        <h2>PM Authority Boundary</h2>
        ${table(["Flag", "Value"], pmRows)}
      </section>
    </div>
    <section class="section">
      <h2>Health</h2>
      <dl class="kv">
        <dt>Status</dt><dd>${badge(state.health.status)}</dd>
        <dt>Errors</dt><dd>${(state.health.errors || []).length ? (state.health.errors || []).map((item) => badge(item)).join(" ") : badge("none")}</dd>
        <dt>Warnings</dt><dd>${(state.health.warnings || []).length ? (state.health.warnings || []).map((item) => badge(item)).join(" ") : badge("none")}</dd>
      </dl>
    </section>
  `;
}

function setTalkState(patch) {
  Object.assign(talkState, patch);
  if (currentState) renderTalkLite(currentState);
}

function talkMimeType() {
  if (!window.MediaRecorder) return "";
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate)) || "";
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || "").split(",").pop() || "");
    reader.onerror = () => reject(reader.error || new Error("file_read_failed"));
    reader.readAsDataURL(blob);
  });
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function syncTalkInputs() {
  const transcript = $("#talk-transcript");
  const session = $("#talk-session-key");
  const confirm = $("#talk-confirm");
  const autospeak = $("#talk-autospeak");
  if (transcript) talkState.transcript = transcript.value;
  if (session) talkState.sessionKey = session.value.trim() || "agent:main:talk-lite";
  if (confirm) talkState.confirmBeforeSend = confirm.checked;
  if (autospeak) talkState.autoSpeak = autospeak.checked;
}

function stopTalkStream() {
  if (talkStream) {
    talkStream.getTracks().forEach((track) => track.stop());
  }
  talkStream = null;
}

async function startTalkRecording() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    setTalkState({ status: "microphone_unavailable", error: "browser_recorder_unavailable" });
    return;
  }
  syncTalkInputs();
  talkChunks = [];
  setTalkState({ status: "requesting_microphone", error: "", audioUrl: "", audioPath: "", response: talkState.response });
  try {
    talkStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = talkMimeType();
    talkRecorder = mimeType ? new MediaRecorder(talkStream, { mimeType }) : new MediaRecorder(talkStream);
    talkRecorder.addEventListener("dataavailable", (event) => {
      if (event.data?.size) talkChunks.push(event.data);
    });
    talkRecorder.addEventListener("stop", () => {
      const blob = new Blob(talkChunks, { type: talkRecorder?.mimeType || "audio/webm" });
      stopTalkStream();
      void transcribeTalkBlob(blob, `talk-lite-${Date.now()}.webm`);
    }, { once: true });
    talkRecorder.start();
    setTalkState({ status: "recording", recording: true, error: "" });
  } catch (error) {
    stopTalkStream();
    setTalkState({ status: "recording_failed", recording: false, error: error.message || String(error) });
  }
}

function stopTalkRecording() {
  if (talkRecorder && talkRecorder.state !== "inactive") {
    setTalkState({ status: "stopping", recording: false });
    talkRecorder.stop();
  }
}

async function transcribeTalkBlob(blob, filename) {
  setTalkState({ status: "transcribing", busy: true, recording: false, error: "" });
  try {
    const payload = await postJson("/api/talk-lite/transcribe", {
      filename,
      mime_type: blob.type || "audio/webm",
      audio_base64: await blobToBase64(blob),
    });
    setTalkState({
      status: payload.status || "transcribed",
      transcript: payload.transcript || "",
      turnId: payload.turn_id || "",
      busy: false,
      error: "",
    });
    if (!talkState.confirmBeforeSend && payload.transcript) {
      await sendTalkTranscript();
    }
  } catch (error) {
    setTalkState({ status: "transcription_failed", busy: false, error: error.message || String(error) });
  }
}

async function sendTalkTranscript() {
  syncTalkInputs();
  if (!talkState.transcript.trim()) {
    setTalkState({ status: "empty_transcript", error: "empty_transcript" });
    return;
  }
  setTalkState({ status: "asking_veritas", busy: true, error: "", audioUrl: "", audioPath: "" });
  try {
    const payload = await postJson("/api/talk-lite/ask", {
      transcript: talkState.transcript,
      session_key: talkState.sessionKey,
      speak: talkState.autoSpeak,
    });
    const tts = payload.tts || {};
    const nextTurn = {
      status: payload.status,
      generated_at_utc: payload.generated_at_utc,
      transcript: payload.transcript,
      reply_text: payload.reply_text,
    };
    setTalkState({
      status: payload.status || "ok",
      response: payload.reply_text || "",
      audioUrl: tts.audio_url || "",
      audioPath: tts.audio_path || "",
      turnId: payload.turn_id || talkState.turnId,
      busy: false,
      error: "",
      turns: [nextTurn, ...talkState.turns].slice(0, 12),
    });
    if (talkState.autoSpeak && tts.audio_url) {
      playTalkAudio(tts.audio_url);
    }
  } catch (error) {
    setTalkState({ status: "veritas_turn_failed", busy: false, error: error.message || String(error) });
  }
}

async function speakTalkResponse() {
  syncTalkInputs();
  if (!talkState.response.trim()) return;
  setTalkState({ status: "speaking", busy: true, error: "" });
  try {
    const payload = await postJson("/api/talk-lite/tts", { text: talkState.response });
    const tts = payload.tts || {};
    setTalkState({
      status: "speech_ready",
      audioUrl: tts.audio_url || "",
      audioPath: tts.audio_path || "",
      busy: false,
      error: "",
    });
    if (tts.audio_url) playTalkAudio(tts.audio_url);
  } catch (error) {
    setTalkState({ status: "speech_failed", busy: false, error: error.message || String(error) });
  }
}

function playTalkAudio(url) {
  setTimeout(() => {
    const audio = document.querySelector(`audio[src="${CSS.escape(url)}"]`);
    if (audio) {
      audio.play().catch(() => {});
    }
  }, 50);
}

function clearTalkLite() {
  if (talkRecorder && talkRecorder.state !== "inactive") talkRecorder.stop();
  stopTalkStream();
  setTalkState({
    status: "idle",
    transcript: "",
    response: "",
    audioUrl: "",
    audioPath: "",
    turnId: "",
    busy: false,
    recording: false,
    error: "",
  });
}

function render(state) {
  currentState = state;
  $("#page-title").textContent = state.registry.ui?.title || "Veritas PM Cockpit";
  $("#subtitle").textContent = state.registry.ui?.subtitle || "Local operator console for workflows, sources, lanes, handoffs, and proof health. Finance actionability lives in the Command Center snapshot.";
  document.title = state.registry.ui?.title || "Veritas PM Cockpit";
  $("#generated").textContent = `API ${formatTime(state.generated_at_utc)}`;
  renderStatusStrip(state);
  renderRandall(state);
  renderDeliverables(state);
  renderOverview(state);
  renderLanes(state);
  renderHandoff(state);
  renderTalkLite(state);
  renderSmb(state);
  renderRetail(state);
  renderWorkflows(state);
  renderAcademy(state);
  renderSql(state);
  renderCloseout(state);
  renderSources(state);
  renderAuthority(state);
}

async function refresh() {
  $("#refresh").disabled = true;
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    $("#status-strip").innerHTML = metric("Cockpit Load", error.message || String(error), "bad");
  } finally {
    $("#refresh").disabled = false;
  }
}

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const action = target.dataset.action;
  if (action === "talk-start") {
    void startTalkRecording();
    return;
  }
  if (action === "talk-stop") {
    stopTalkRecording();
    return;
  }
  if (action === "talk-send") {
    void sendTalkTranscript();
    return;
  }
  if (action === "talk-speak") {
    void speakTalkResponse();
    return;
  }
  if (action === "talk-clear") {
    clearTalkLite();
    return;
  }
  if (target.matches(".tab")) {
    document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((panel) => panel.classList.remove("active"));
    target.classList.add("active");
    $(`#${target.dataset.tab}`).classList.add("active");
  }
});

document.addEventListener("input", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (["talk-transcript", "talk-session-key"].includes(target.id)) syncTalkInputs();
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement)) return;
  if (["talk-confirm", "talk-autospeak"].includes(target.id)) {
    syncTalkInputs();
    if (currentState) renderTalkLite(currentState);
  }
  if (target.id === "talk-file" && target.files?.[0]) {
    const file = target.files[0];
    void transcribeTalkBlob(file, file.name || `talk-lite-${Date.now()}.webm`);
    target.value = "";
  }
});

$("#refresh").addEventListener("click", refresh);
void refresh();
setInterval(refresh, 60_000);
