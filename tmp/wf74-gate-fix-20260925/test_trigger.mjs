// Harness for the WF74 gate trigger: runs the script body with a mocked exec()
// shaped like the documented code-mode result ({ aggregated }), plus trigger.state.
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import assert from "node:assert/strict";

const body = readFileSync(new URL("./trigger.js", import.meta.url), "utf8");
const AsyncFn = Object.getPrototypeOf(async function () {}).constructor;
const run = (exec, state) => new AsyncFn("exec", "trigger", body)(exec, { state });

const live = execFileSync("C:/Users/Veritas/AppData/Local/Programs/Python/Python313/python.exe",
  ["C:/Users/Veritas/.openclaw/workspace/scripts/wf74_scoreboard_rollup_trigger.py"], { encoding: "utf8" });
const liveD = JSON.parse(live.trim().split(/\r?\n/).pop());
const ok = (payload) => async () => ({ status: "completed", exitCode: 0, aggregated: payload });

// 1. Real prefilter output, no prior state: fires with the item list, not "unreadable".
let r = await run(ok(live), undefined);
assert.equal(r.fire, liveD.actionable_count > 0);
assert.ok(!r.message || !r.message.includes("unreadable"), "real output must not read as unreadable");
assert.equal(r.state.sig, liveD.signature);

// 2. Same signature as last time: dedupe holds, no fire.
r = await run(ok(live), { sig: liveD.signature });
assert.equal(r.fire, false);

// 3. Stuck legacy state "unreadable" (the live job today): real output fires once and repairs state.
r = await run(ok(live), { sig: "unreadable" });
assert.equal(r.state.sig, liveD.signature);

// 4. Genuinely malformed output still fires "unreadable".
r = await run(ok("not json"), undefined);
assert.equal(r.fire, true);
assert.ok(r.message.includes("unreadable"));

// 5. ok:false still fires "unreadable".
r = await run(ok(JSON.stringify({ ok: false })), undefined);
assert.ok(r.fire && r.message.includes("unreadable"));

// 6. Stale scoreboards fire STALE and keep the previous signature.
r = await run(ok(JSON.stringify({ ok: true, stale: true, age_hours: 30 })), { sig: "abc" });
assert.ok(r.fire && r.message.includes("STALE"));
assert.equal(r.state.sig, "abc");

// 7. exec throwing fires exec_error.
r = await run(async () => { throw new Error("boom"); }, undefined);
assert.equal(r.state.sig, "exec_error");

// 8. Regression proof: the OLD field order (stdout/output/text) on this result shape reads as unreadable.
const oldRaw = ((x) => x.stdout || x.output || x.text || JSON.stringify(x))({ aggregated: live });
const oldD = JSON.parse(oldRaw.trim().split(/\r?\n/).pop());
assert.notEqual(oldD.ok, true, "old parser should reproduce the false alarm");

console.log(JSON.stringify({ ok: true, cases: 8, live_actionable: liveD.actionable_count }));
