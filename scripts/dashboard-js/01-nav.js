// ── Navigation ───────────────────────────────────────────────────────────────

function switchTab(key) {
  $('nav').querySelectorAll('button').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  const btn = $('nav').querySelector(`[data-tab="${key}"]`);
  if (btn) btn.classList.add('active');
  const sec = $(`tab-${key}`);
  if (sec) sec.classList.add('active');
}

function renderNav() {
  const buttons = tabs.map(([key, label], i) =>
    `<button class="${i===0?'active':''}" data-tab="${key}" title="[${i+1}]">${label}</button>`
  ).join('');
  $('nav').innerHTML = buttons + `<span class="nav-hint">Press <span class="kbd">1–9</span> to switch &nbsp;·&nbsp; <span class="kbd">?</span> for shortcuts</span>`;
  $('nav').querySelectorAll('button').forEach(btn =>
    btn.addEventListener('click', () => switchTab(btn.dataset.tab))
  );
}

// ── Keyboard shortcuts ────────────────────────────────────────────────────────

function renderShortcutList() {
  $('shortcutList').innerHTML = SHORTCUTS.map(([key, label]) =>
    `<div class="shortcut-row"><span class="shortcut-label">${esc(label)}</span><span class="kbd">${esc(key)}</span></div>`
  ).join('');
}

function openOverlay() { $('shortcutOverlay').classList.add('open'); }
function closeOverlay() { $('shortcutOverlay').classList.remove('open'); }

document.addEventListener('keydown', e => {
  const tag = document.activeElement?.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA') return;
  if (e.key === '?') { $('shortcutOverlay').classList.toggle('open'); return; }
  if (e.key === 'Escape') {
    if ($('shortcutOverlay').classList.contains('open')) { closeOverlay(); return; }
    switchTab('overview'); return;
  }
  const n = parseInt(e.key, 10);
  if (n >= 1 && n <= tabs.length) { switchTab(tabs[n-1][0]); }
});

$('shortcutOverlay').addEventListener('click', e => { if (e.target === $('shortcutOverlay')) closeOverlay(); });
