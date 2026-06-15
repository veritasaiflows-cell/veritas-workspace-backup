// ── Deployment Board ──────────────────────────────────────────────────────────

let activeDeployFilter = 'all';
const deployFilters = [
  ['all',        'All'],
  ['deployable', 'Deployable'],
  ['review',     'Review'],
  ['almost',     'Almost'],
  ['blocked',    'Blocked / Stop'],
  ['watch',      'Watch / Bench'],
];

function stateRowClass(state) {
  if (!state) return '';
  const s = state.toUpperCase();
  if (s === 'AUTHORITY CONFLICT') return 'state-almost';
  if (s === 'REVIEW') return 'state-almost';
  if (s === 'ALMOST') return 'state-almost';
  if (s === 'BLOCKED') return 'state-blocked';
  if (s === 'BELOW STOP') return 'state-below-stop';
  return '';
}

function stateFilterMatch(state, filter) {
  if (filter === 'all') return true;
  const s = (state||'').toUpperCase();
  if (filter === 'deployable') return s === 'DEPLOYABLE';
  if (filter === 'review')     return s === 'REVIEW' || s === 'PROMOTION REVIEW' || s === 'AUTHORITY CONFLICT';
  if (filter === 'almost')     return s === 'ALMOST';
  if (filter === 'blocked')    return s === 'BLOCKED' || s === 'BELOW STOP';
  if (filter === 'watch')      return s === 'WATCH' || s === 'BENCH';
  return true;
}

function renderDeployFilterBar() {
  $('deployFilterBar').innerHTML = deployFilters.map(([key, label]) =>
    `<button class="filter-btn ${activeDeployFilter===key?'active':''}" data-filter="${key}">${label}</button>`
  ).join('');
  $('deployFilterBar').querySelectorAll('.filter-btn').forEach(btn =>
    btn.addEventListener('click', () => {
      activeDeployFilter = btn.dataset.filter;
      renderDeployFilterBar();
      renderDeploymentTable();
    })
  );
}

function bandPositionWidget(r) {
  if (r.bandVisualSuppressed || r.repairOverride) {
    return `<div class="band-widget band-widget-override muted"><div class="band-widget-label tone-warn">${esc(r.repairOverrideLabel || 'REPAIR OVERRIDE / band position irrelevant')}</div></div>`;
  }
  if (r.bandLow == null || r.bandHigh == null || r.closeRaw == null) {
    return `<span class="small muted">${esc(r.bandStatus || '—')}</span>`;
  }
  const range = r.bandHigh - r.bandLow;
  const raw = range > 0 ? ((r.closeRaw - r.bandLow) / range) * 100 : 50;
  const inBand = raw >= 0 && raw <= 100;
  const above = raw > 100;
  const clamped = Math.max(0, Math.min(100, raw));
  const markerClass = inBand ? 'in' : (above ? 'above' : 'below');
  const arrow = inBand ? '' : (above ? ' ▶' : '◀ ');
  const label = inBand ? `${Math.round(raw)}% in band` : (above ? `+${(raw-100).toFixed(1)}% above${arrow}` : `${arrow}${Math.abs(raw).toFixed(1)}% below`);
  return `<div class="band-widget">
    <div class="band-widget-track">
      <div class="band-widget-band"></div>
      <div class="band-widget-marker ${markerClass}" style="left:${clamped}%"></div>
    </div>
    <div class="band-widget-label">${esc(label)}</div>
  </div>`;
}

function earningsCell(r) {
  if (!r.earningsDate) return '<span class="small muted">—</span>';
  const d = r.daysToEarnings;
  const tone = d != null && d <= 7 ? 'tone-bad' : d != null && d <= 14 ? 'tone-warn' : 'tone-info';
  const dayLabel = d == null ? '' : d === 0 ? 'today' : d > 0 ? `${d}d` : `${Math.abs(d)}d ago`;
  const unconfirmed = r.earningsDateConfirmed === false ? `<div>${pill('UNCONFIRMED DATE','warn')}</div>` : '';
  return `<div class="mono small">${esc(r.earningsDate)}</div><div class="small ${tone}">${esc(dayLabel)}</div>${unconfirmed}`;
}

function stopDistCell(r) {
  if (r.stopDistPct == null) return '<span class="small muted">—</span>';
  const tone = r.stopDistPct < 0 ? 'tone-bad' : r.stopDistPct < 5 ? 'tone-warn' : 'tone-info';
  return `<span class="mono ${tone}">${r.stopDistPct.toFixed(1)}%</span>`;
}

function renderDeploymentTable() {
  const records = (DATA.deployment_records||[]).filter(r => stateFilterMatch(r.state, activeDeployFilter));
  $('deploymentTable').innerHTML = records.map(r => {
    const proof = `<div class="small muted">Proof: ${esc(r.sourceArtifactPath || 'artifact unavailable')}${r.sourceGeneratedAtUtc ? ` · ${esc(r.sourceGeneratedAtUtc)}` : ''}${r.bandStale ? ' · BAND STALE' : ''}${r.overrideRule ? ` · override ${esc(r.overrideRule)}` : ''}</div>`;
    return `<tr class="${stateRowClass(r.state)}">
      <td class="mono"><strong>${esc(r.ticker)}</strong><div class="small muted">${esc(r.posture||'')}</div></td>
      <td>${pill(r.state, stateTone(r.state))}</td>
      <td class="mono">${esc(r.close)}</td>
      <td class="mono small">${esc(r.bandLabel)}</td>
      <td>${bandPositionWidget(r)}</td>
      <td class="mono">${esc(r.stop)}</td>
      <td>${stopDistCell(r)}</td>
      <td>${earningsCell(r)}</td>
      <td class="small">${r.displaySubState ? `<div class="tone-warn"><strong>${esc(r.displaySubState)}</strong></div>` : ''}${r.proseConflict ? `<div class="tone-warn">${esc(r.conflictProseState || 'Authority conflict')}</div>` : ''}${r.reviewOnlyNoApplyArtifact ? `<div class="tone-warn">REVIEW ONLY — NO APPLY ARTIFACT</div>` : ''}${esc(r.reason)}${proof}</td>
      <td>${esc(r.priority)}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="10" class="muted" style="padding:16px;text-align:center">No records match this filter.</td></tr>';
}
