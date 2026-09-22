// Measures Windows process-creation cost for the memory_search KNN child, using the
// exact same spawn mechanism the Gateway uses (child_process.spawnSync mirrors spawn
// creation cost; the gateway uses async spawn of process.execPath).
import { spawnSync } from "node:child_process";
import { performance } from "node:perf_hooks";

const execPath = process.execPath;
const child =
  "C:\\Users\\Veritas\\AppData\\Roaming\\npm\\node_modules\\openclaw\\dist\\extensions\\memory-core\\memory-search-knn.child.js";

function timeIt(label, fn, runs = 6) {
  const samples = [];
  for (let i = 0; i < runs; i++) {
    const t0 = performance.now();
    fn(i);
    samples.push(Math.round(performance.now() - t0));
  }
  const sorted = [...samples].sort((a, b) => a - b);
  return {
    label,
    samples,
    min: sorted[0],
    median: sorted[Math.floor(sorted.length / 2)],
    max: sorted[sorted.length - 1],
  };
}

const rows = [];

// 1. bare Node: version only (no script evaluation)
rows.push(
  timeIt("node --version", () =>
    spawnSync(execPath, ["--version"], { stdio: "ignore" }),
  ),
);

// 2. bare Node with a trivial script
rows.push(
  timeIt("node -e 0", () => spawnSync(execPath, ["-e", "0"], { stdio: "ignore" })),
);

// 3. the real KNN child, empty stdin -> it runs, reports invalid input, exits
rows.push(
  timeIt("knn child (empty stdin)", () =>
    spawnSync(execPath, [child], { input: "", stdio: ["pipe", "ignore", "pipe"] }),
  ),
);

// 4. the real KNN child with a valid JSON body (still no DB work: bad path)
rows.push(
  timeIt("knn child (invalid request JSON)", () =>
    spawnSync(execPath, [child], {
      input: JSON.stringify({ status: "noop" }),
      stdio: ["pipe", "ignore", "pipe"],
    }),
  ),
);

// 5. second-child-in-a-row: is there any OS-level warming?
rows.push(
  timeIt("knn child, immediate repeat (warm?)", () =>
    spawnSync(execPath, [child], { input: "", stdio: ["pipe", "ignore", "pipe"] }),
  ),
);

console.log(JSON.stringify({ execPath, nodeVersion: process.version, rows }, null, 2));
