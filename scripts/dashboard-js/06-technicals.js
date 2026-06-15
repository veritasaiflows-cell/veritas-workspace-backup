// ── Technical Analysis ────────────────────────────────────────────────────────

let activeTechFilter = 'all';
const techFilters = [
  ['all',       'All'],
  ['deployable','Deployable'],
  ['review',    'Review'],
  ['almost',    'Almost'],
  ['blocked',   'Blocked / Stop'],
  ['watch',     'Watch / Bench'],
];

function techFilterMatch(state, filter) {
  if (filter === 'all') return true;
  const s = (state||'').toUpperCase();
  if (filter === 'deployable') return s === 'DEPLOYABLE';
  if (filter === 'review') return s === 'PROMOTION REVIEW' || s === 'REVIEW' || s === 'AUTHORITY CONFLICT';
  if (filter === 'almost') return s === 'ALMOST';
  if (filter === 'blocked') return s === 'BLOCKED' || s === 'BELOW STOP';
  if (filter === 'watch') return s === 'WATCH' || s === 'BENCH';
  return true;
}

function renderTechnicalFilterBar() {
  if (!$('technicalFilterBar')) return;
  $('technicalFilterBar').innerHTML = techFilters.map(([key, label]) =>
    `<button class="filter-btn ${activeTechFilter===key?'active':''}" data-filter="${key}">${label}</button>`
  ).join('');
  $('technicalFilterBar').querySelectorAll('.filter-btn').forEach(btn =>
    btn.addEventListener('click', () => {
      activeTechFilter = btn.dataset.filter;
      renderTechnicalFilterBar();
      renderTechnicalTable();
    })
  );
}

function parseBandLowHigh(entryLabel) {
  if (!entryLabel || typeof entryLabel !== 'string') return [null, null];
  const m = entryLabel.match(/(\d+(?:\.\d+)?)\s*[–—\-]\s*(\d+(?:\.\d+)?)/);
  if (!m) return [null, null];
  return [parseFloat(m[1]), parseFloat(m[2])];
}

function techBandWidget(t) {
  if (t.bandVisualSuppressed || t.repairOverride) {
    return `<div class="band-widget band-widget-override muted"><div class="band-widget-label tone-warn">${esc(t.repairOverrideLabel || 'REPAIR OVERRIDE / band position irrelevant')}</div></div>`;
  }
  const [low, high] = parseBandLowHigh(t.entry);
  if (low == null || high == null || t.close == null) {
    return `<span class="small muted">${esc(t.bandStatus || '—')}</span>`;
  }
  const range = high - low;
  const raw = range > 0 ? ((t.close - low) / range) * 100 : 50;
  const inBand = raw >= 0 && raw <= 100;
  const above = raw > 100;
  const clamped = Math.max(0, Math.min(100, raw));
  const markerClass = inBand ? 'in' : (above ? 'above' : 'below');
  const label = inBand ? `${Math.round(raw)}% in` : (above ? `+${(raw-100).toFixed(1)}% ▶` : `◀ ${Math.abs(raw).toFixed(1)}%`);
  return `<div class="band-widget">
    <div class="band-widget-track">
      <div class="band-widget-band"></div>
      <div class="band-widget-marker ${markerClass}" style="left:${clamped}%"></div>
    </div>
    <div class="band-widget-label">${esc(label)}</div>
  </div>`;
}

function renderTechnicalTable() {
  const rows = (DATA.technical||[]).filter(t => techFilterMatch(t.actionState, activeTechFilter));
  $('technicalTable').innerHTML = rows.map(t => {
    const stopTone = t.belowStop?'tone-bad':(t.stopDistPct!=null&&t.stopDistPct<5?'tone-warn':'tone-info');
    const [low, high] = parseBandLowHigh(t.entry);
    const ma20Tone = t.above20?'tone-ok':'tone-warn';
    const ma50Tone = t.above50?'tone-ok':'tone-warn';
    const ma200Tone = t.above200?'tone-ok':'tone-warn';
    const dte = t.daysToEarnings;
    const earningsTone = dte != null && dte <= 7 ? 'tone-bad' : dte != null && dte <= 14 ? 'tone-warn' : 'tone-info';
    const dteLabel = dte == null ? '' : dte === 0 ? 'today' : dte > 0 ? `${dte}d` : `${Math.abs(dte)}d ago`;
    const laneLabel = t.coverageLaneLabel || (t.coverageLane ? t.coverageLane.toUpperCase() : '—');
    const laneTone = t.coverageLane === 'execution' ? 'ok' : (t.coverageLane === 'watch' ? 'info' : 'warn');
    const stateDetail = `${t.displaySubState ? `<div class="small tone-warn">${esc(t.displaySubState)}</div>` : ''}${t.proseConflict ? `<div class="small tone-warn">${esc(t.conflictProseState || 'Authority conflict')}</div>` : ''}`;
    const proofDetail = `<div class="small muted">${esc(t.sourceArtifactPath || 'artifact unavailable')}${t.sourceGeneratedAtUtc ? ` · ${esc(t.sourceGeneratedAtUtc)}` : ''}${t.bandStale ? ' · BAND STALE' : ''}${t.overrideRule ? ` · override ${esc(t.overrideRule)}` : ''}</div>`;
    const earningsBadge = t.earningsDateConfirmed === false ? `<div>${pill('UNCONFIRMED DATE','warn')}</div>` : '';
    return `<tr>
      <td class="mono"><strong>${esc(t.ticker)}</strong>${t.triggerToday?` <span class="pill-tiny">LIVE</span>`:''}</td>
      <td>${pill(laneLabel, laneTone)}</td>
      <td class="mono">${esc(t.close??'—')}</td>
      <td class="mono ${ma20Tone}">${esc(t.ma20??'—')}</td>
      <td class="mono ${ma50Tone}">${esc(t.ma50??'—')}</td>
      <td class="mono ${ma200Tone}">${esc(t.ma200??'—')}</td>
      <td class="small">${esc(t.posture||'—')}</td>
      <td class="mono">${low!=null?low.toFixed(2):'—'}</td>
      <td class="mono">${high!=null?high.toFixed(2):'—'}</td>
      <td>${techBandWidget(t)}</td>
      <td class="mono">${esc(t.stop||'—')}</td>
      <td class="mono ${stopTone}">${t.stopDistPct==null?'—':`${esc(t.stopDistPct)}%`}</td>
      <td><div class="mono small">${esc(t.earningsDate||'Unconfirmed')}</div>${dteLabel?`<div class="small ${earningsTone}">${dteLabel}</div>`:''}${earningsBadge}</td>
      <td>${t.triggerToday?pill('Ready','ok'):pill('Wait','info')}</td>
      <td>${pill(t.actionState, stateTone(t.actionState))}${stateDetail}${proofDetail}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="15" class="muted" style="padding:16px;text-align:center">No records match this filter.</td></tr>';
}
