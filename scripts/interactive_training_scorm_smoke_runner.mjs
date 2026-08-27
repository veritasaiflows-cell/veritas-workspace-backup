import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function writeJson(filePath, data) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2) + "\n", "utf8");
}

function safeName(value) {
  return value.replace(/[^a-z0-9_-]+/gi, "-").replace(/^-|-$/g, "").toLowerCase();
}

async function launchBrowser(config) {
  const attempts = [];
  if (config.browser_channel) attempts.push({ channel: config.browser_channel });
  if (config.browser_executable) attempts.push({ executablePath: config.browser_executable });
  attempts.push({});
  let lastError = null;
  for (const attempt of attempts) {
    try {
      const browser = await chromium.launch({ headless: true, ...attempt });
      return {
        browser,
        launch: attempt.channel ? `channel:${attempt.channel}` : attempt.executablePath ? `executable:${attempt.executablePath}` : "bundled"
      };
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

function expectedScormKeys() {
  return [
    "cmi.core.lesson_status",
    "cmi.core.score.raw",
    "cmi.core.lesson_location",
    "cmi.suspend_data"
  ];
}

async function smokeModule(browser, module, screenshotDir) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 840 } });
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.addInitScript(() => {
    const api = {
      calls: [],
      values: {},
      initialized: false,
      finished: false,
      LMSInitialize(arg) {
        this.calls.push({ method: "LMSInitialize", arg: String(arg) });
        this.initialized = true;
        return "true";
      },
      LMSSetValue(key, value) {
        this.calls.push({ method: "LMSSetValue", key: String(key), value: String(value) });
        this.values[String(key)] = String(value);
        return "true";
      },
      LMSCommit(arg) {
        this.calls.push({ method: "LMSCommit", arg: String(arg) });
        return "true";
      },
      LMSFinish(arg) {
        this.calls.push({ method: "LMSFinish", arg: String(arg) });
        this.finished = true;
        return "true";
      },
      LMSGetLastError() {
        return "0";
      },
      LMSGetErrorString(code) {
        return String(code);
      },
      LMSGetDiagnostic(code) {
        return String(code);
      }
    };
    window.API = api;
    window.__scormSmokeApi = api;
  });
  const url = pathToFileURL(path.resolve(module.scorm_index)).href;
  await page.goto(url, { waitUntil: "load" });
  await page.waitForTimeout(250);
  const execution = await page.evaluate(() => {
    const facts = {
      has_set_view: typeof setView === "function",
      has_complete_module: typeof completeModule === "function",
      body_text_length: (document.body.innerText || "").length,
      title: document.title
    };
    if (facts.has_set_view) setView("review");
    if (facts.has_complete_module) completeModule();
    return facts;
  });
  await page.waitForTimeout(250);
  const snapshot = await page.evaluate(() => {
    const api = window.__scormSmokeApi;
    return {
      calls: api ? api.calls : [],
      values: api ? api.values : {},
      initialized: api ? api.initialized : false,
      finished: api ? api.finished : false,
      progress_text: (document.getElementById("completed")?.textContent || "").trim(),
      score_text: (document.getElementById("score")?.textContent || "").trim()
    };
  });
  fs.mkdirSync(screenshotDir, { recursive: true });
  const screenshotPath = path.join(screenshotDir, `${safeName(module.name)}-scorm-smoke.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await page.close();

  const methods = snapshot.calls.map((call) => call.method);
  const setKeys = snapshot.calls.filter((call) => call.method === "LMSSetValue").map((call) => call.key);
  const finishIndex = snapshot.calls.findIndex((call) => call.method === "LMSFinish");
  const callsAfterFinish = finishIndex >= 0 ? snapshot.calls.slice(finishIndex + 1) : [];
  const lessonStatusAfterFinish = finishIndex >= 0
    ? callsAfterFinish.filter((call) => call.key === "cmi.core.lesson_status").map((call) => call.value)
    : [];
  const writeCallsAfterFinish = callsAfterFinish.filter((call) => ["LMSSetValue", "LMSCommit"].includes(call.method));
  const missingKeys = expectedScormKeys().filter((key) => !setKeys.includes(key));
  const errors = [];
  if (!snapshot.initialized) errors.push("scorm_initialize_not_called");
  if (!methods.includes("LMSCommit")) errors.push("scorm_commit_not_called");
  if (!methods.includes("LMSFinish")) errors.push("scorm_finish_not_called");
  if (snapshot.values["cmi.core.lesson_status"] === "incomplete") errors.push("final_lesson_status_downgraded_to_incomplete");
  if (lessonStatusAfterFinish.includes("incomplete")) errors.push("lesson_status_incomplete_written_after_finish");
  if (writeCallsAfterFinish.length) errors.push("scorm_write_after_finish");
  if (missingKeys.length) errors.push(`missing_scorm_keys:${missingKeys.join(",")}`);
  if (!execution.has_complete_module) errors.push("complete_module_function_missing");
  if (execution.body_text_length < 500) errors.push("body_text_too_short");
  if (consoleErrors.length) errors.push("console_errors_present");

  return {
    name: module.name,
    module_id: module.module_id,
    path: module.scorm_index.replaceAll("\\", "/"),
    status: errors.length ? "blocked" : "ok",
    screenshot: screenshotPath.replaceAll("\\", "/"),
    execution,
    calls: snapshot.calls,
    values: snapshot.values,
    initialized: snapshot.initialized,
    finished: snapshot.finished,
    progress_text: snapshot.progress_text,
    score_text: snapshot.score_text,
    console_errors: consoleErrors,
    errors
  };
}

async function main() {
  const configPath = process.argv[2];
  if (!configPath) throw new Error("Missing config path");
  const config = readJson(configPath);
  const output = {
    schema: "veritas.interactive_training_scorm_smoke_runner.v1",
    generated_at_utc: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    status: "ok",
    browser: null,
    modules: [],
    validation: { errors: [], warnings: [] },
    authority_boundary: {
      local_files_only: true,
      external_lms_upload: false,
      learner_data_external_transport: false
    }
  };
  let browserHandle = null;
  try {
    const launched = await launchBrowser(config);
    browserHandle = launched.browser;
    output.browser = launched.launch;
    for (const module of config.modules) {
      const result = await smokeModule(browserHandle, module, config.screenshot_dir);
      output.modules.push(result);
      output.validation.errors.push(...result.errors.map((error) => `${module.name}:${error}`));
    }
  } finally {
    if (browserHandle) await browserHandle.close();
  }
  output.status = output.validation.errors.length ? "blocked" : "ok";
  writeJson(config.output_path, output);
  if (output.validation.errors.length) process.exitCode = 1;
}

main().catch((error) => {
  const configPath = process.argv[2];
  const fallback = configPath ? readJson(configPath) : { output_path: "tmp/interactive-training-scorm-smoke-validation.json" };
  writeJson(fallback.output_path, {
    schema: "veritas.interactive_training_scorm_smoke_runner.v1",
    generated_at_utc: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    status: "blocked",
    modules: [],
    validation: { errors: [`runner_exception:${error.message}`], warnings: [] },
    authority_boundary: {
      local_files_only: true,
      external_lms_upload: false,
      learner_data_external_transport: false
    }
  });
  process.exit(1);
});
