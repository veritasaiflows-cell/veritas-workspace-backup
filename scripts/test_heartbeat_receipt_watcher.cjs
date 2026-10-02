"use strict";
const fs = require("fs"), assert = require("assert");
const BODY = fs.readFileSync(__dirname + "/heartbeat_receipt_watcher.js", "utf8");
const AsyncFn = Object.getPrototypeOf(async function () {}).constructor;
const NOW = 1759365249000, SIG = "9065afcbb33c7f735bbbd53f1c1e234f5a775d89cb78cb3bfdb03667e72d3c1d", SIG2 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const OA = { review_only: true, heartbeat_may_execute: false, heartbeat_may_spawn_helper: false, heartbeat_may_lease_lane: false, cron_schedule_mutation_allowed: false, config_auth_runtime_mutation_allowed: false, canon_or_portfolio_mutation_allowed: false, capital_deployment_allowed: false, paper_or_live_execution_allowed: false, brokerage_or_account_action_allowed: false, owner_approval_inferred: false };
const IA = { review_only: true, main_session_review_required: true, heartbeat_may_execute: false, heartbeat_may_spawn_helper: false, heartbeat_may_lease_lane: false, cron_schedule_mutation_allowed: false, config_auth_runtime_mutation_allowed: false, sql_or_ticker_import_allowed: false, canon_or_portfolio_mutation_allowed: false, capital_deployment_allowed: false, paper_or_live_execution_allowed: false, brokerage_or_account_action_allowed: false, owner_approval_inferred: false };
const CMD = ["C:\\Users\\Veritas\\AppData\\Local\\Programs\\Python\\Python313\\python.exe", "scripts\\main_session_escalation_consumer.py", "--context", "heartbeat", "--write", "--validate", "--priority-observation-source", "heartbeat", "--out", "tmp/heartbeat-main-session-escalation-consumer.json", "--priority-out", "tmp/heartbeat-main-session-priority-handoff.json"];
const iso = (t) => new Date(t).toISOString();
function sel(o) { o = o || {}; return { priority_id: "escalation:db985ca098546e79", priority: "P1", repeat_count: o.rc == null ? 3 : o.rc, next_action: "No deterministic safe handler is registered.", authority_boundary: Object.assign({}, IA), disposition: { status: o.disp || "accepted" } }; }
function base(o) {
  o = o || {}; const g = iso(o.genAge != null ? NOW - o.genAge : NOW - 60000);
  return { schema: "veritas.heartbeat_priority_receipt.v1", generated_at_utc: g, status: "needs_main_review", authority_boundary: Object.assign({}, OA), steps: [{ name: "main_session_escalation_consumer", command: CMD.slice(), ok: true, returncode: 0 }], source_artifacts: { consumer: "tmp/heartbeat-main-session-escalation-consumer.json", priority_handoff: "tmp/heartbeat-main-session-priority-handoff.json" }, consumer: { status: "warning", mode: "dry_run", context: "heartbeat", execution_results: [] }, priority_handoff: { schema: "veritas.main_session_priority_handoff.v1", generated_at_utc: g, status: "needs_main_review", receipt: o.receipt || "NO_DELTA", input_signature: { sha256: o.sig || SIG }, observation: { source: "heartbeat", priority_repeat_age_advanced: true }, authority_boundary: Object.assign({}, IA), summary: { next_safe_action: "No deterministic safe handler is registered." }, selected_item: sel(o), validation: { status: "ok", errors: [], warnings: [] } }, receipt: o.receipt || "NO_DELTA", validation: { status: "ok", errors: [], warnings: [] } };
}
async function run(raw, prev, now, opts) {
  opts = opts || {}; const fn = new AsyncFn("read", "json", "trigger", BODY);
  let out; const j = opts.jsonThrow ? async () => { throw new Error("commit-fail"); } : (o) => { out = o; return o; };
  const snap = JSON.parse(JSON.stringify(prev || {}));
  const frozen = Object.freeze(JSON.parse(JSON.stringify(prev || {})));
  const trig = { state: frozen };
  const rd = opts.throws ? async () => { throw new Error("boom"); } : async (a) => { assert.strictEqual(a.path, "C:\\Users\\Veritas\\.openclaw\\workspace\\tmp\\heartbeat-priority-receipt.json"); return typeof raw === "string" ? raw : JSON.parse(JSON.stringify(raw)); };
  const real = Date.now; Date.now = () => now;
  try { await fn(rd, j, trig); } finally { Date.now = real; }
  return { out, trig, frozen, snap };
}
let n = 0; const ok = (c, m) => { n++; assert.ok(c, m); };
(async () => {
  // quiet NO_DELTA twice (unresolved P1), state not committed
  let r1 = await run(base(), {}, NOW);
  ok(!r1.out.wake && !r1.out.notify, "nodelta quiet");
  ok(JSON.stringify(r1.out.state.fkey) === "null", "nodelta clears fault");
  let r2 = await run(base(), r1.out.state, NOW + 60000);
  ok(!r2.out.wake, "nodelta repeat quiet");
  ok(JSON.stringify(r1.trig.state) === JSON.stringify(r1.snap) && Object.isFrozen(r1.frozen), "frozen intact");
  // NEW once, re-timestamp suppressed, new signature wakes
  let w1 = await run(base({ receipt: "NEW_PRIORITY" }), {}, NOW);
  ok(w1.out.wake === "now" && /NEW_PRIORITY/.test(w1.out.notify), "new wakes");
  let w2 = await run(base({ receipt: "NEW_PRIORITY", genAge: 10000 }), w1.out.state, NOW + 120000);
  ok(!w2.out.wake, "new retimestamp suppressed");
  ok(JSON.stringify(w2.out.state) === JSON.stringify(w1.out.state), "quiet commits nothing");
  let w3 = await run(base({ receipt: "NEW_PRIORITY", sig: SIG2 }), w1.out.state, NOW + 180000);
  ok(w3.out.wake === "now", "new signature wakes");
  // ESC count key
  let e1 = await run(base({ receipt: "ESCALATED_PRIORITY" }), {}, NOW);
  ok(e1.out.wake === "now", "esc wakes");
  let e2 = await run(base({ receipt: "ESCALATED_PRIORITY" }), e1.out.state, NOW + 60000);
  ok(!e2.out.wake, "esc same count quiet");
  let e3 = await run(base({ receipt: "ESCALATED_PRIORITY", rc: 4 }), e1.out.state, NOW + 120000);
  ok(e3.out.wake === "now", "esc bumped count wakes");
  let e4 = base({ receipt: "ESCALATED_PRIORITY", rc: 0 });
  let e4r = await run(e4, {}, NOW);
  ok(e4r.out.wake === "now" && /esc_count_invalid/.test(e4r.out.notify), "esc bad count faults");
  // BLOCKED wakes once
  let b1 = await run(base({ receipt: "BLOCKED" }), {}, NOW);
  ok(b1.out.wake === "now" && /BLOCKED/.test(b1.out.notify), "blocked wakes");
  let b2 = await run(base({ receipt: "BLOCKED" }), b1.out.state, NOW + 60000);
  ok(!b2.out.wake, "blocked deduped");
  // content[] text form
  let c1 = await run({ content: [{ type: "text", text: JSON.stringify(base({ receipt: "NEW_PRIORITY" })) }] }, {}, NOW);
  ok(c1.out.wake === "now", "content array accepted");
  // negative contract fixtures (parameterized)
  const mut = (f) => { const b = base({ receipt: "NEW_PRIORITY" }); f(b); return b; };
  const NEG = [
    ["read_threw", null, { throws: true }], ["read_error", { isError: true }, {}],
    ["read_missing_text", {}, {}], ["read_truncated", { content: [{ text: "x", truncated: true }] }, {}],
    ["read_oversize", "x".repeat(50001), {}], ["json_malformed", "{nope", {}],
    ["schema_mismatch", mut((b) => { b.schema = "x"; }), {}],
    ["status_invalid", mut((b) => { b.status = "zzz"; }), {}],
    ["receipt_mismatch", mut((b) => { b.receipt = "BLOCKED"; }), {}],
    ["validation_not_ok", mut((b) => { b.validation.status = "blocked"; }), {}],
    ["authority_tampered", mut((b) => { b.authority_boundary.capital_deployment_allowed = true; }), {}],
    ["steps_invalid", mut((b) => { b.steps[0].ok = false; }), {}],
    ["command_changed", mut((b) => { b.steps[0].command.push("--execute-safe"); }), {}],
    ["consumer_not_dry_run", mut((b) => { b.consumer.mode = "live"; }), {}],
    ["consumer_executed", mut((b) => { b.consumer.execution_results = [{ x: 1 }]; }), {}],
    ["source_artifacts_changed", mut((b) => { b.source_artifacts.consumer = "tmp/evil.json"; }), {}],
    ["observation_invalid", mut((b) => { b.priority_handoff.observation.source = "cron"; }), {}],
    ["signature_invalid", base({ receipt: "NEW_PRIORITY", sig: "zz" }), {}],
    ["timestamp_stale", base({ receipt: "NEW_PRIORITY", genAge: 22300000 }), {}],
    ["timestamp_future", mut((b) => { b.generated_at_utc = iso(NOW + 120000); b.priority_handoff.generated_at_utc = iso(NOW + 120000); }), {}]
  ];
  for (const [code, raw, o] of NEG) { const rr = await run(raw, {}, NOW, o); ok(rr.out && rr.out.wake === "now" && rr.out.notify.indexOf(code) !== -1, "fault " + code); }
  // fault dedupe / 6h cadence / change / reset
  const bad = "{nope";
  let f1 = await run(bad, {}, NOW);
  ok(f1.out.wake === "now", "fault first wakes");
  let f2 = await run(bad, f1.out.state, NOW + 1000);
  ok(!f2.out.wake, "fault repeat suppressed");
  let f3 = await run(bad, f1.out.state, NOW + 21600001);
  ok(f3.out.wake === "now", "fault 6h repeat wakes");
  let f4 = await run("x".repeat(50001), f1.out.state, NOW + 2000);
  ok(f4.out.wake === "now" && /read_oversize/.test(f4.out.notify), "changed fault wakes");
  let rec = await run(base(), f1.out.state, NOW + 3000);
  ok(!rec.out.wake && rec.out.state.fkey === null, "recovery quiet resets fault");
  let f5 = await run(bad, rec.out.state, NOW + 4000);
  ok(f5.out.wake === "now", "fault after recovery wakes");
  ok(rec.out.state.attn === f1.out.state.attn, "recovery keeps priority credit");
  // thrown commit failure stays retryable, frozen untouched
  const fr = await run(base({ receipt: "NEW_PRIORITY" }), { v: 1, attn: null, fkey: null, fat: 0 }, NOW, { jsonThrow: true }).catch(() => null);
  ok(fr === null, "json throw propagates");
  // bounds
  const big = base({ receipt: "NEW_PRIORITY" }); big.priority_handoff.summary.next_safe_action = "A".repeat(5000);
  const bb = await run(big, {}, NOW);
  ok(bb.out.notify.length <= 2000 && /untrusted/.test(bb.out.notify), "notify bounded+marked");
  ok(JSON.stringify(bb.out.state).length <= 1000 && JSON.stringify(w1.out.state).length <= 1000, "state bounded");
  console.log("heartbeat-watcher tests passed: " + n + " assertions");
})().catch((e) => { console.error("FAIL: " + (e && e.message)); process.exit(1); });
