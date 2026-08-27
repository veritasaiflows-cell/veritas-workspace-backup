import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
import axe from "axe-core";

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
      return { browser, launch: attempt.channel ? `channel:${attempt.channel}` : attempt.executablePath ? `executable:${attempt.executablePath}` : "bundled" };
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

async function inspectViewport(browser, file, viewport, screenshotDir) {
  const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height } });
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  const url = pathToFileURL(path.resolve(file.path)).href;
  await page.goto(url, { waitUntil: "load" });
  await page.waitForTimeout(250);
  await page.addScriptTag({ content: axe.source });
  const axeResult = await page.evaluate(async () => {
    return await window.axe.run(document);
  });
  await page.evaluate(() => {
    document.dispatchEvent(new KeyboardEvent("keydown", { altKey: true, key: "ArrowRight", bubbles: true }));
  });
  await page.waitForTimeout(150);
  const keyboardPracticeCount = await page.locator(".interaction").count();
  const facts = await page.evaluate(() => {
    const bodyText = document.body.innerText || "";
    const controls = Array.from(document.querySelectorAll("button, input, textarea"));
    const overflowing = Array.from(document.querySelectorAll("button, .nav-button, .metric")).filter((el) => {
      return el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2;
    }).slice(0, 10).map((el) => ({
      tag: el.tagName.toLowerCase(),
      text: (el.textContent || "").trim().slice(0, 80),
      width: el.clientWidth,
      scrollWidth: el.scrollWidth,
      height: el.clientHeight,
      scrollHeight: el.scrollHeight
    }));
    return {
      title: document.title,
      body_text_length: bodyText.length,
      controls: controls.length,
      headings: document.querySelectorAll("h1,h2,h3").length,
      nav_buttons: document.querySelectorAll(".nav-button").length,
      interactions: document.querySelectorAll(".interaction").length,
      overflowing
    };
  });
  const screenshotPath = path.join(screenshotDir, `${safeName(file.name)}-${viewport.name}.png`);
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await page.close();
  const severeViolations = axeResult.violations.filter((violation) => ["serious", "critical"].includes(violation.impact));
  const errors = [];
  if (facts.body_text_length < 500) errors.push("body_text_too_short");
  if (facts.controls < 3) errors.push("too_few_controls");
  if (facts.nav_buttons < 4) errors.push("missing_navigation_buttons");
  if (keyboardPracticeCount < 1) errors.push("keyboard_navigation_did_not_reach_practice");
  if (consoleErrors.length) errors.push("console_errors_present");
  if (severeViolations.length) errors.push("serious_or_critical_axe_violations");
  if (facts.overflowing.length) errors.push("visible_control_overflow_detected");
  return {
    viewport: viewport.name,
    width: viewport.width,
    height: viewport.height,
    screenshot: screenshotPath.replaceAll("\\", "/"),
    facts,
    keyboard_practice_count: keyboardPracticeCount,
    console_errors: consoleErrors,
    axe_violations: axeResult.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      description: violation.description,
      nodes: violation.nodes.length
    })),
    severe_axe_violation_count: severeViolations.length,
    errors
  };
}

async function main() {
  const configPath = process.argv[2];
  if (!configPath) throw new Error("Missing config path");
  const config = readJson(configPath);
  fs.mkdirSync(config.screenshot_dir, { recursive: true });
  const generatedAt = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const output = {
    schema: "veritas.interactive_training_qa_runner.v1",
    generated_at_utc: generatedAt,
    status: "ok",
    browser: null,
    files: [],
    validation: { errors: [], warnings: [] },
    authority_boundary: {
      local_files_only: true,
      external_delivery_approved: false,
      learner_data_external_transport: false
    }
  };
  let browserHandle = null;
  try {
    const launched = await launchBrowser(config);
    browserHandle = launched.browser;
    output.browser = launched.launch;
    for (const file of config.files) {
      const viewports = [];
      for (const viewport of config.viewports) {
        viewports.push(await inspectViewport(browserHandle, file, viewport, config.screenshot_dir));
      }
      const fileErrors = viewports.flatMap((view) => view.errors.map((error) => `${file.name}:${view.viewport}:${error}`));
      output.files.push({
        name: file.name,
        path: file.path.replaceAll("\\", "/"),
        status: fileErrors.length ? "blocked" : "ok",
        viewports,
        errors: fileErrors
      });
      output.validation.errors.push(...fileErrors);
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
  const fallback = configPath ? readJson(configPath) : { output_path: "tmp/interactive-training-qa-validation.json" };
  writeJson(fallback.output_path, {
    schema: "veritas.interactive_training_qa_runner.v1",
    generated_at_utc: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    status: "blocked",
    files: [],
    validation: { errors: [`runner_exception:${error.message}`], warnings: [] },
    authority_boundary: {
      local_files_only: true,
      external_delivery_approved: false,
      learner_data_external_transport: false
    }
  });
  process.exit(1);
});
