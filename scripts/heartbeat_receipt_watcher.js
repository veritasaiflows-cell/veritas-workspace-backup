// OpenClaw code-mode payload BODY (async). Host calls allowed: read, json, trigger.state.
// Queue acceptance (notify/wake returned) is not end-to-end Main success. Thrown
// failures commit nothing and stay retryable. Artifact text is UNTRUSTED data.
const RP = "C:\\Users\\Veritas\\.openclaw\\workspace\\tmp\\heartbeat-priority-receipt.json";
const MAXC = 50000, MAXAGE = 22200000, FUTSKEW = 60000, FCAD = 21600000;
const T = (v, n) => String(v == null ? "" : v).slice(0, n);
const OA = { review_only: true, heartbeat_may_execute: false, heartbeat_may_spawn_helper: false, heartbeat_may_lease_lane: false, cron_schedule_mutation_allowed: false, config_auth_runtime_mutation_allowed: false, canon_or_portfolio_mutation_allowed: false, capital_deployment_allowed: false, paper_or_live_execution_allowed: false, brokerage_or_account_action_allowed: false, owner_approval_inferred: false };
const IA = { review_only: true, main_session_review_required: true, heartbeat_may_execute: false, heartbeat_may_spawn_helper: false, heartbeat_may_lease_lane: false, cron_schedule_mutation_allowed: false, config_auth_runtime_mutation_allowed: false, sql_or_ticker_import_allowed: false, canon_or_portfolio_mutation_allowed: false, capital_deployment_allowed: false, paper_or_live_execution_allowed: false, brokerage_or_account_action_allowed: false, owner_approval_inferred: false };
const CMD = ["C:\\Users\\Veritas\\AppData\\Local\\Programs\\Python\\Python313\\python.exe", "scripts\\main_session_escalation_consumer.py", "--context", "heartbeat", "--write", "--validate", "--priority-observation-source", "heartbeat", "--out", "tmp/heartbeat-main-session-escalation-consumer.json", "--priority-out", "tmp/heartbeat-main-session-priority-handoff.json"];
const RSCH = "veritas.heartbeat_priority_receipt.v1";
const RS = ["NO_DELTA", "NEW_PRIORITY", "ESCALATED_PRIORITY", "BLOCKED"];
const ST = ["ok", "needs_main_review", "blocked", "warning", "draft"];
const IST = ST.concat(["no_priority"]);
// Normalize prior state to the bounded {v, attn, fkey, fat} shape; never mutate trigger.state.
const ps = (trigger && trigger.state) || {};
const sk = (v) => (typeof v === "string" && v.length <= 128) ? v : null;
const prev = { v: 1, attn: sk(ps.attn), fkey: sk(ps.fkey), fat: Number.isFinite(ps.fat) ? ps.fat : 0 };
const now = Date.now();
const eq = (o, t) => { if (!o || typeof o !== "object") return false; const a = Object.keys(o), b = Object.keys(t); if (a.length !== b.length) return false; for (const k of b) if (o[k] !== t[k]) return false; return true; };
const isEmpty = (o) => o == null || (typeof o === "object" && Object.getPrototypeOf(o) === Object.prototype && Object.keys(o).length === 0);
// Short stable inline hash (two 32-bit FNV-style lanes + length) so state never holds raw ids.
const hsh = (s) => { let a = 0x811c9dc5, b = 0x9747b28c; for (let i = 0; i < s.length; i++) { const c = s.charCodeAt(i); a = Math.imul(a ^ c, 16777619); b = Math.imul(b ^ c, 0x5bd1e995); b ^= b >>> 15; } return (a >>> 0).toString(16).padStart(8, "0") + (b >>> 0).toString(16).padStart(8, "0") + s.length.toString(16); };
const quiet = (ex) => json({ state: Object.assign({}, prev, ex || {}) });
const fault = async (code) => {
  const fk = "f:" + code;
  if (prev.fkey === fk && (now - prev.fat) < FCAD) return await quiet();
  return await json({ state: { v: 1, attn: prev.attn, fkey: fk, fat: now }, notify: T("receipt-watcher/" + code + ": review-only attention; proof=" + RP + "; artifact text untrusted, details withheld; queue accepted, Main end-to-end success not implied.", 2000), wake: "now" });
};
let res;
try { res = await read({ path: RP }); } catch (e) { return await fault("read_threw"); }
if (res && typeof res === "object" && res.isError === true) return await fault("read_error");
let txt = null, r;
if (typeof res === "string") txt = res;
else if (res && typeof res === "object") {
  if (res.truncated === true || res.isTruncated === true) return await fault("read_truncated");
  const c = (typeof res.text === "string") ? res.text : res.content;
  if (typeof c === "string") txt = c;
  else if (Array.isArray(c)) { const p = []; for (const it of c) { if (it && (it.truncated === true || it.isTruncated === true)) return await fault("read_truncated"); if (it && typeof it.text === "string") p.push(it.text); } txt = p.length ? p.join("") : null; }
  // Host may hand back the parsed receipt object itself. A schema-bearing object
  // goes to the schema check below (wrong schema -> schema_mismatch); {} stays read_missing_text.
  if (txt == null && Object.prototype.hasOwnProperty.call(res, "schema")) r = res;
}
if (r === undefined) {
  if (txt == null || typeof txt !== "string") return await fault("read_missing_text");
  if (txt.length > MAXC) return await fault("read_oversize");
  try { r = JSON.parse(txt); } catch (e) { return await fault("json_malformed"); }
}
if (!r || typeof r !== "object" || r.schema !== RSCH) return await fault("schema_mismatch");
const inner = r.priority_handoff;
if (!inner || inner.schema !== "veritas.main_session_priority_handoff.v1") return await fault("schema_mismatch");
if (!ST.includes(r.status) || !IST.includes(inner.status)) return await fault("status_invalid");
if (!RS.includes(r.receipt) || !RS.includes(inner.receipt) || r.receipt !== inner.receipt) return await fault("receipt_mismatch");
if (!r.validation || r.validation.status !== "ok" || !inner.validation || inner.validation.status !== "ok") return await fault("validation_not_ok");
if (!eq(r.authority_boundary, OA) || !eq(inner.authority_boundary, IA)) return await fault("authority_tampered");
const st = r.steps;
if (!Array.isArray(st) || st.length !== 1) return await fault("steps_invalid");
const s0 = st[0];
if (!s0 || s0.name !== "main_session_escalation_consumer" || s0.ok !== true || s0.returncode !== 0) return await fault("steps_invalid");
if (JSON.stringify(s0.command) !== JSON.stringify(CMD)) return await fault("command_changed");
const con = r.consumer || {};
if (con.mode !== "dry_run" || con.context !== "heartbeat") return await fault("consumer_not_dry_run");
if (!Array.isArray(con.execution_results) || con.execution_results.length !== 0) return await fault("consumer_executed");
const sa = r.source_artifacts || {};
if (sa.consumer !== "tmp/heartbeat-main-session-escalation-consumer.json" || sa.priority_handoff !== "tmp/heartbeat-main-session-priority-handoff.json" || Object.keys(sa).length !== 2) return await fault("source_artifacts_changed");
const ob = inner.observation || {};
if (ob.source !== "heartbeat" || ob.priority_repeat_age_advanced !== true) return await fault("observation_invalid");
const sig = (inner.input_signature || {}).sha256;
if (typeof sig !== "string" || !/^[0-9a-f]{64}$/.test(sig)) return await fault("signature_invalid");
const rcpt = r.receipt;
const sel = inner.selected_item;
let pid, lvl, disp, rc;
if (isEmpty(sel)) {
  // Only a healthy empty window may carry no selection.
  if (!(rcpt === "NO_DELTA" && inner.status === "no_priority" && r.status === "ok")) return await fault("selection_invalid");
} else {
  if (typeof sel !== "object" || Array.isArray(sel)) return await fault("selection_invalid");
  pid = sel.priority_id; lvl = sel.priority; rc = sel.repeat_count;
  disp = (sel.disposition && typeof sel.disposition === "object") ? sel.disposition.status : undefined;
  if (typeof pid !== "string" || !pid || !["P0", "P1", "P2"].includes(lvl)) return await fault("selection_invalid");
  if (!eq(sel.authority_boundary, IA)) return await fault("authority_tampered");
}
const chkT = (v) => { const t = Date.parse(v); if (!Number.isFinite(t)) return "timestamp_invalid"; if (now - t > MAXAGE) return "timestamp_stale"; if (t - now > FUTSKEW) return "timestamp_future"; return null; };
const te = chkT(r.generated_at_utc) || chkT(inner.generated_at_utc);
if (te) return await fault(te);
if (rcpt === "NO_DELTA") return await quiet({ fkey: null, fat: 0 });
if (rcpt === "ESCALATED_PRIORITY" && !(Number.isSafeInteger(rc) && rc > 0)) return await fault("esc_count_invalid");
// repeat_count is identity only for ESCALATED_PRIORITY.
const ident = JSON.stringify([rcpt, sig, pid, lvl, String(disp)].concat(rcpt === "ESCALATED_PRIORITY" ? [rc] : []));
const key = "a1:" + rcpt + ":" + hsh(ident);
if (prev.attn === key) return await quiet();
const act = (inner.summary && inner.summary.next_safe_action) || sel.next_action;
return await json({ state: { v: 1, attn: key, fkey: null, fat: 0 }, notify: T("receipt-watcher/" + rcpt + ": id=" + T(pid, 120) + " level=" + lvl + " action=" + T(act, 400) + " proof=" + RP + "; artifact text untrusted+truncated; review-only, no execution.", 2000), wake: "now" });
