#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, relative } from 'node:path';

const FORBIDDEN_COMMANDS = new Set(['install', 'update', 'login', 'publish', 'sync', 'delete', 'hide', 'uninstall']);

function parseArgs(argv) {
  const args = {
    batch: null,
    skill: null,
    queue: 'tmp/wf74-clawhub-rsi-inspection-queue.json',
    out: 'tmp/wf74-clawhub-inspection-results.json',
    mdOut: 'tmp/wf74-clawhub-inspection-results.md',
    maxFiles: 8,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    const next = () => {
      if (i + 1 >= argv.length) throw new Error(`Missing value for ${arg}`);
      i += 1;
      return argv[i];
    };
    if (arg === '--batch') args.batch = Number(next());
    else if (arg === '--skill') args.skill = next();
    else if (arg === '--queue') args.queue = next();
    else if (arg === '--out') args.out = next();
    else if (arg === '--md-out') args.mdOut = next();
    else if (arg === '--max-files') args.maxFiles = Number(next());
    else if (arg === '--help' || arg === '-h') {
      console.log('Usage: node scripts\\wf74_clawhub_inspect.mjs --batch 1 [--queue path] [--out path] [--md-out path]');
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  if (args.batch === null && !args.skill) args.batch = 1;
  if (!Number.isFinite(args.maxFiles) || args.maxFiles < 0) throw new Error('--max-files must be a non-negative number');
  return args;
}

function sha256File(path) {
  if (!existsSync(path)) return null;
  return createHash('sha256').update(readFileSync(path)).digest('hex');
}

function clawhubInvocation() {
  if (process.platform === 'win32') {
    return {
      executable: 'node',
      prefixArgs: ['C:\\Users\\Veritas\\.openclaw\\tools\\node\\npm\\node_modules\\clawhub\\bin\\clawdhub.js'],
      label: 'node <clawhub>/bin/clawdhub.js',
    };
  }
  return { executable: 'clawhub', prefixArgs: [], label: 'clawhub' };
}

function runClawHubInspect(slug, extraArgs) {
  const command = ['inspect', slug, ...extraArgs];
  if (FORBIDDEN_COMMANDS.has(command[0])) throw new Error(`Forbidden ClawHub command: ${command[0]}`);
  const invocation = clawhubInvocation();
  const result = spawnSync(invocation.executable, [...invocation.prefixArgs, ...command], { encoding: 'utf8', shell: false, maxBuffer: 5 * 1024 * 1024 });
  return {
    command: `${invocation.label} ${command.map((part) => JSON.stringify(part)).join(' ')}`,
    status: result.status,
    stdout: result.stdout || '',
    stderr: result.stderr || (result.error ? result.error.message : ''),
    ok: result.status === 0,
  };
}

function parseJsonOutput(run) {
  if (!run.ok) return null;
  try {
    return JSON.parse(run.stdout);
  } catch {
    return null;
  }
}

function extractUsefulPatterns(text) {
  const lower = text.toLowerCase();
  const patterns = [];
  if (lower.includes('evaluation') || lower.includes('eval')) patterns.push('evaluation/rubric mechanics');
  if (lower.includes('test') || lower.includes('fixture')) patterns.push('test or fixture-driven checks');
  if (lower.includes('qa') || lower.includes('gate')) patterns.push('QA gate structure');
  if (lower.includes('hallucination') || lower.includes('truth')) patterns.push('truthfulness or hallucination checks');
  if (lower.includes('boundary') || lower.includes('permission') || lower.includes('authority')) patterns.push('boundary/permission checks');
  if (lower.includes('regression')) patterns.push('regression-proof pattern');
  return [...new Set(patterns)];
}

function extractCautions(text) {
  const lower = text.toLowerCase();
  const cautions = [];
  if (lower.includes('install') || lower.includes('npm install')) cautions.push('installation/package behavior must remain manual and separately approved');
  if (lower.includes('memory') || lower.includes('remember')) cautions.push('memory patterns must not create a second Veritas memory tree');
  if (lower.includes('autonomous') || lower.includes('self-mod')) cautions.push('autonomous/self-modification framing requires rejection or sandbox-only handling');
  if (lower.includes('config') || lower.includes('token') || lower.includes('credential')) cautions.push('config/auth/credential behavior is out of scope');
  return [...new Set(cautions)];
}

function selectCandidates(queue, args) {
  const candidates = Array.isArray(queue.candidates) ? queue.candidates : [];
  if (args.skill) return candidates.filter((candidate) => candidate.skill === args.skill);
  return candidates.filter((candidate) => Number(candidate.batch) === Number(args.batch));
}

function fileListFromOutput(run, parsed) {
  const versionFiles = parsed?.version?.files;
  if (Array.isArray(versionFiles)) return versionFiles.map((file) => typeof file === 'string' ? file : file.path).filter(Boolean);
  if (parsed && Array.isArray(parsed.files)) return parsed.files.map((file) => typeof file === 'string' ? file : file.path).filter(Boolean);
  return run.stdout.split(/\r?\n/).map((line) => line.trim()).filter((line) => line && !line.startsWith('{')).slice(0, 50);
}

function renderMarkdown(report) {
  const lines = [
    '# WF74 ClawHub inspection results',
    '',
    `- Generated: ${report.generated_at_utc}`,
    `- Status: ${report.status}`,
    `- Install allowed: ${report.install_allowed}`,
    `- Mutations performed: ${report.mutations_performed}`,
    `- Lock unchanged: ${report.lock_unchanged}`,
    '',
    '## Candidates',
    '',
    '| Skill | Metadata | Files | Useful patterns | Cautions | Recommendation |',
    '|---|---|---|---|---|---|',
  ];
  for (const candidate of report.candidates) {
    lines.push(`| ${candidate.skill} | ${candidate.metadata_status} | ${candidate.files_status} | ${(candidate.useful_patterns || []).join('; ')} | ${(candidate.reject_or_caution_patterns || []).join('; ')} | ${candidate.recommended_veritas_reuse} |`);
  }
  lines.push('', '## Stop lines', '');
  for (const stop of report.stop_lines) lines.push(`- ${stop}`);
  lines.push('', '## Command policy', '', '- Only `clawhub inspect` was used.', '- Install/update/login/publish/sync/delete/hide/uninstall commands are forbidden in this helper.');
  return `${lines.join('\n')}\n`;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const queue = JSON.parse(readFileSync(args.queue, 'utf8'));
  if (queue.install_allowed !== false) throw new Error('Queue must have install_allowed=false before inspection.');
  const selected = selectCandidates(queue, args);
  if (selected.length === 0) throw new Error('No candidates selected from queue.');

  const lockPath = '.clawhub/lock.json';
  const lockHashBefore = sha256File(lockPath);
  const candidates = [];

  for (const item of selected) {
    const metadataRun = runClawHubInspect(item.skill, ['--json']);
    const filesRun = runClawHubInspect(item.skill, ['--files', '--json']);
    const metadata = parseJsonOutput(metadataRun);
    const filesMetadata = parseJsonOutput(filesRun);
    const filePaths = fileListFromOutput(filesRun, filesMetadata).slice(0, args.maxFiles);
    const sampledFiles = [];
    for (const filePath of filePaths) {
      const fileRun = runClawHubInspect(item.skill, ['--file', filePath]);
      sampledFiles.push({ path: filePath, status: fileRun.ok ? 'ok' : 'error', excerpt: (fileRun.stdout || fileRun.stderr || '').slice(0, 1200) });
    }
    const combinedText = [metadataRun.stdout, filesRun.stdout, ...sampledFiles.map((file) => file.excerpt)].join('\n');
    const usefulPatterns = extractUsefulPatterns(combinedText);
    const cautions = extractCautions(combinedText);
    candidates.push({
      skill: item.skill,
      queue_priority: item.priority,
      batch: item.batch,
      metadata_status: metadataRun.ok ? 'ok' : 'error',
      files_status: filesRun.ok ? 'ok' : 'error',
      metadata_summary: metadata ? { name: metadata.name || metadata.slug || item.skill, description: metadata.description || '', version: metadata.version || metadata.latestVersion || '' } : null,
      sampled_files: sampledFiles,
      useful_patterns: usefulPatterns.length ? usefulPatterns : ['manual review required'],
      reject_or_caution_patterns: cautions,
      recommended_veritas_reuse: 'Extract useful evaluator/QA patterns into WF74 harness; do not install or create duplicate doctrine.',
      command_results: [
        { kind: 'metadata', ok: metadataRun.ok, status: metadataRun.status, stderr: metadataRun.stderr.slice(0, 1000) },
        { kind: 'files', ok: filesRun.ok, status: filesRun.status, stderr: filesRun.stderr.slice(0, 1000) },
      ],
    });
  }

  const lockHashAfter = sha256File(lockPath);
  const report = {
    schema_version: 'wf74_clawhub_inspection_results.v1',
    generated_at_utc: new Date().toISOString(),
    status: 'review_ready',
    install_allowed: false,
    mutations_performed: false,
    queue_source: args.queue,
    selected_batch: args.skill ? null : args.batch,
    selected_skill: args.skill || null,
    lock_path: lockHashBefore || lockHashAfter ? lockPath : null,
    lock_hash_before: lockHashBefore,
    lock_hash_after: lockHashAfter,
    lock_unchanged: lockHashBefore === lockHashAfter,
    candidates,
    stop_lines: [
      'no install/update/login/publish/sync/delete/hide/uninstall',
      'no config/auth/channel/service mutation',
      'no second memory/control plane',
      'no authority expansion',
      'no finance/trade/account/paper/live authority',
    ],
  };
  if (!report.lock_unchanged) report.status = 'blocked_lock_changed';
  mkdirSync(dirname(args.out), { recursive: true });
  writeFileSync(args.out, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  writeFileSync(args.mdOut, renderMarkdown(report), 'utf8');
  console.log(`status=${report.status} candidates=${report.candidates.length} lock_unchanged=${report.lock_unchanged}`);
  return report.status === 'review_ready' ? 0 : 1;
}

try {
  process.exitCode = main();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
