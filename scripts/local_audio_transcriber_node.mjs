#!/usr/bin/env node
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const SCRIPT_PATH = fileURLToPath(import.meta.url);
const ROOT = path.resolve(path.dirname(SCRIPT_PATH), "..");
const DEFAULT_TOOLS_DIR = path.join(ROOT, "tmp", "audio-tools");

function parseArgs(argv) {
  const args = {
    input: "",
    model: "Xenova/whisper-base.en",
    cacheDir: path.join(DEFAULT_TOOLS_DIR, ".cache"),
    toolsDir: DEFAULT_TOOLS_DIR,
    keepWav: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--input") args.input = argv[++i] || "";
    else if (arg === "--model") args.model = argv[++i] || args.model;
    else if (arg === "--cache-dir") args.cacheDir = argv[++i] || args.cacheDir;
    else if (arg === "--tools-dir") args.toolsDir = argv[++i] || args.toolsDir;
    else if (arg === "--keep-wav") args.keepWav = true;
    else if (arg === "--help" || arg === "-h") {
      console.log("Usage: node scripts/local_audio_transcriber_node.mjs --input <audio> [--model Xenova/whisper-base.en]");
      process.exit(0);
    }
  }
  return args;
}

function fail(message, details = {}) {
  console.error(JSON.stringify({ status: "error", error: message, ...details }));
  process.exit(2);
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!args.input) fail("missing_input");

  const input = path.resolve(args.input);
  if (!fs.existsSync(input)) fail("input_not_found", { input });

  const toolsDir = path.resolve(args.toolsDir);
  const nodeModules = path.join(toolsDir, "node_modules");
  const requireFromTools = createRequire(path.join(nodeModules, "package.json"));
  const ffmpegPath = requireFromTools("ffmpeg-static");
  const { WaveFile } = requireFromTools("wavefile");
  const transformersPath = path.join(nodeModules, "@xenova", "transformers", "src", "transformers.js");
  const { pipeline, env } = await import(pathToFileURL(transformersPath).href);

  fs.mkdirSync(args.cacheDir, { recursive: true });
  fs.mkdirSync(path.join(toolsDir, "scratch"), { recursive: true });
  env.cacheDir = args.cacheDir;

  const wavPath = path.join(
    toolsDir,
    "scratch",
    `${path.basename(input).replace(/[^a-zA-Z0-9_.-]/g, "_")}.${process.pid}.wav`,
  );

  const convert = spawnSync(
    ffmpegPath,
    ["-hide_banner", "-loglevel", "error", "-y", "-i", input, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wavPath],
    { encoding: "utf8" },
  );
  if (convert.status !== 0) {
    fail("ffmpeg_convert_failed", {
      input,
      stderr: (convert.stderr || "").slice(-2000),
    });
  }

  const started = Date.now();
  let output;
  try {
    const wav = new WaveFile(fs.readFileSync(wavPath));
    wav.toBitDepth("32f");
    wav.toSampleRate(16000);
    let audio = wav.getSamples();
    if (Array.isArray(audio)) audio = audio[0];
    audio = Float32Array.from(audio);

    const transcriber = await pipeline("automatic-speech-recognition", args.model);
    output = await transcriber(audio, { return_timestamps: true });
  } finally {
    if (!args.keepWav) {
      try {
        fs.unlinkSync(wavPath);
      } catch {
        // Best-effort scratch cleanup only.
      }
    }
  }

  const text = String(output?.text || "").trim();
  const chunks = Array.isArray(output?.chunks) ? output.chunks : [];
  const result = {
    status: text ? "ok" : "empty_transcript",
    generated_at_utc: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    input,
    model: args.model,
    local_only: true,
    text,
    chunks,
    elapsed_ms: Date.now() - started,
    host: os.hostname(),
  };
  console.log(JSON.stringify(result));
}

main().catch((error) => {
  fail("transcription_failed", { message: String(error?.message || error) });
});
