// Condition-trigger script for the upstream release re-test watch.
//
// Purpose: fire only when the installed OpenClaw version changes from the last
// observed value, so a release re-test happens without a model polling for it.
//
// Contract: returns { fire, message?, state? }. Read-only — it never mutates the
// workspace, the scheduler, or anything upstream. Actions live in the job payload.
//
// Failure posture: a success-only watcher looks healthy while broken, so repeated
// inability to read the version raises one warning instead of staying silent.

const pkgPath =
  "C:\\Users\\Veritas\\AppData\\Roaming\\npm\\node_modules\\openclaw\\package.json";

const res = await exec({
  command: `(Get-Content '${pkgPath}' -Raw | ConvertFrom-Json).version`,
});

const version = String(res?.aggregated ?? res?.stdout ?? "").trim();
const prev = trigger.state?.version ?? null;
const failStreak = version ? 0 : (trigger.state?.failStreak ?? 0) + 1;
const warnedAt = trigger.state?.warnedAt ?? null;

if (!version) {
  const shouldWarn = failStreak >= 3 && warnedAt === null;
  const state = {
    version: prev,
    failStreak,
    warnedAt: shouldWarn ? Date.now() : warnedAt,
  };
  if (shouldWarn) {
    json({
      fire: true,
      message:
        "Upstream release watch is blind: it failed to read the installed OpenClaw version three checks in a row. " +
        "Verify the package.json path and the trigger script; the issue re-test watch is not working until this is repaired.",
      state,
    });
  } else {
    json({ fire: false, state });
  }
} else if (prev === null) {
  // First observation only records a baseline; it must not fire on install.
  json({ fire: false, state: { version, failStreak: 0, warnedAt: null } });
} else if (prev !== version) {
  json({
    fire: true,
    message:
      `OpenClaw version changed: ${prev} -> ${version}. ` +
      "Re-test upstream issue #155478 (memory_search KNN child spawn on Windows) per " +
      "06. Playbooks/Operating Procedures/Upstream Escalation and Community Contribution Procedure.md step 10. " +
      "Steps: (1) re-run tmp/knn_spawn_probe.mjs for the current spawn-cost table; " +
      "(2) inspect dist/extensions/memory-core/manager-runtime.js for reused/pooled KNN children " +
      "instead of a one-shot spawn per query; " +
      "(3) check whether memory-search-knn.child.js now sets PRAGMA mmap_size or cache_size; " +
      "(4) check the issue state with: gh issue view 155478 --repo openclaw/openclaw --json state,labels. " +
      "Then report a fixed / regressed / unmoved verdict, update " +
      "06. Playbooks/Project Continuity/Upstream Escalation Register.md, and tell Randall. " +
      "Filing or commenting upstream remains an owner-approved action: do not post without approval.",
    state: { version, previousVersion: prev, failStreak: 0, warnedAt: null },
  });
} else {
  json({ fire: false, state: { version, failStreak: 0, warnedAt: null } });
}
