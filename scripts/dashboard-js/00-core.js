// ── Core constants and utilities ─────────────────────────────────────────────

const tabs = [
  ['overview','Overview'],
  ['deployment','Deployment Board'],
  ['technicals','Technical Analysis'],
  ['portfolio','Portfolio'],
  ['fundamentals','Fundamentals'],
  ['earnings','Earnings'],
  ['macro','Macro'],
  ['risk','Risk & Rules'],
  ['triggers','Execution Board'],
  ['decisionqueue','Decision Queue'],
  ['postearnings','Post-Earnings'],
  ['entrybands','Entry Bands'],
];

const SHORTCUTS = [
  ...tabs.map(([,label], i) => [`${i+1}`, `Go to ${label}`]),
  ['?', 'Show / hide this panel'],
  ['Esc', 'Close overlay or go to Overview'],
];

const toneMap = {fresh:'ok',usable_with_caution:'warn',partial:'warn',stale:'bad',missing:'bad',ok:'ok',warn:'warn',bad:'bad',info:'info',critical:'bad',warning:'warn'};
const statusLabel = {fresh:'Fresh',usable_with_caution:'Caution',partial:'Partial',stale:'Stale',missing:'Missing'};
const $ = id => document.getElementById(id);
const esc = v => (v ?? '—').toString().replace(/[&<>]/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]));
const pill = (text, tone='info') => `<span class="pill ${tone}">${esc(text)}</span>`;
const row = (left, right) => `<div class="row"><div>${left}</div><div>${right}</div></div>`;
const toneClass = tone => `tone-${toneMap[tone] || tone || 'info'}`;

function stateTone(state) {
  if (!state) return 'info';
  const s = state.toUpperCase();
  if (s === 'DEPLOYABLE') return 'ok';
  if (s === 'REVIEW' || s === 'PROMOTION REVIEW' || s === 'AUTHORITY CONFLICT') return 'warn';
  if (s === 'ALMOST') return 'warn';
  if (s === 'BLOCKED' || s === 'BELOW STOP') return 'bad';
  return 'info';
}
