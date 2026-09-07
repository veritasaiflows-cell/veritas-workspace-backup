const { spawnSync } = require('node:child_process');
const params = {
  key: 'agent:main:dashboard:c40974f9-96a8-4495-a607-aa8a790bbcbf',
  model: 'openai-codex/gpt-5.5'
};
const r = spawnSync('node', ['C:\\Users\\Veritas\\AppData\\Roaming\\npm\\node_modules\\openclaw\\openclaw.mjs', 'gateway', 'call', 'sessions.patch', '--json', '--params', JSON.stringify(params)], { encoding: 'utf8', shell: false });
console.log('status', r.status, 'signal', r.signal);
if (r.stdout) console.log('stdout:', r.stdout);
if (r.stderr) console.error('stderr:', r.stderr);
if (r.error) console.error('error:', r.error);
process.exit(r.status ?? 1);
