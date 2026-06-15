// ── Overview tab ──────────────────────────────────────────────────────────────

function renderAlerts() {
  const deltaSummary = DELTA && !DELTA.first_run
    ? `<div class="alert info"><div>◉</div><div><strong>Changes since last run</strong><div class="small">${esc(DELTA.summary)}</div></div></div>`
    : '';
  const alerts = (DATA.ui?.alerts || []).map(a =>
    `<div class="alert ${toneMap[a.tone]||a.tone}"><div>⚠</div><div><strong>${esc(a.title)}</strong><div class="small">${esc(a.detail)}</div></div></div>`
  ).join('');
  $('alerts').innerHTML = deltaSummary + alerts;
}

function renderTrust() {
  $('trustSummary').textContent = DATA.trust.summary;
  
  const con = DATA.trust.consistency || {};
  const conTone = con.status === 'ok' ? 'ok' : 'bad';
  const conLabel = con.status === 'ok' ? 'CLEAN' : (con.status ? 'DRIFT DETECTED' : 'UNAVAILABLE');
  const conIssues = con.warnings?.length ? `<div class="small tone-bad" style="margin-top:6px">${con.warnings.map(esc).join('<br>')}</div>` : '';
  const conCounts = con.counts ? `<div class="small mono" style="margin-top:6px">Tracked: ${con.counts.tracked} | Tech: ${con.counts.expected_tech} | Triggers: ${con.counts.expected_trig}</div>` : '';
  const conCard = `<div class="card" style="padding:12px; margin-bottom:10px; border-left:3px solid var(--${conTone})"><div class="row"><div><strong>Universe Consistency Gate</strong></div><div style="text-align:right">${pill(conLabel, conTone)}</div></div>${conCounts}${conIssues}</div>`;
  const handoffs = DATA.trust.handoff_proof_state || [];
  const handoffCard = handoffs.length ? `<div class="card" style="padding:12px; margin-bottom:10px; border-left:3px solid var(--warn)"><div><strong>Handoff Proof State</strong></div><div class="small" style="margin-top:4px">First-proof gates stay pending until a live artifact proves the lane.</div><div style="margin-top:8px;display:flex;flex-direction:column;gap:6px">${handoffs.map(h => `<div class="row"><div><strong>${esc(h.label)}</strong><div class="small mono">${esc(h.source_path || '—')}</div></div><div style="text-align:right">${pill(h.state || 'PENDING_FIRST_PROOF', h.tone || 'warn')}<div class="small mono">${esc(h.generated_at_utc || 'no proof artifact')}</div></div></div>`).join('')}</div></div>` : '';

  $('trustSources').innerHTML = conCard + handoffCard + DATA.trust.sources.map(s => {
    const issues = s.issues?.length ? `<div class="small" style="margin-top:6px">${s.issues.map(esc).join(' · ')}</div>` : '';
    const tags = s.tags?.length ? `<div style="margin-top:6px">${s.tags.map(t => pill(t.replaceAll('_',' '), toneMap[s.status]||'info')).join(' ')}</div>` : '';
    return `<div class="card" style="padding:12px"><div class="row"><div><strong>${esc(s.label)}</strong><div class="small mono">${esc(s.generatedLabel)}</div></div><div style="text-align:right">${pill(s.statusLabel, toneMap[s.status])}<div class="small">Age ${esc(s.ageLabel)}</div></div></div>${tags}${issues}</div>`;
  }).join('');
}

function renderVaultFreshness() {
  const notes = DATA.vault_freshness || {};
  $('vaultFreshness').innerHTML = Object.entries(notes).map(([key, n]) => {
    const tone = n.status === 'fresh' ? 'ok' : (n.status === 'missing' ? 'bad' : 'warn');
    const ageLabel = n.age_h != null ? `${n.age_h}h` : '—';
    return `<div class="row"><div><strong>${esc(n.label)}</strong><div class="small">${esc(n.last_updated_date || 'No date line')}</div></div><div style="text-align:right">${pill(n.status, tone)}<div class="small">${ageLabel}</div></div></div>`;
  }).join('');
}

function renderValidation() {
  const sum = DATA.validation.summary;
  $('validationSummary').textContent = `${sum.critical} critical, ${sum.warning} warning, ${sum.info} info.`;
  const warns = DATA.validation.warnings || [];
  $('validationWarnings').innerHTML = warns.length
    ? warns.slice(0,12).map(w =>
        `<div class="card" style="padding:12px"><div>${pill(w.severity, toneMap[w.severity])}${w.ticker ? pill(w.ticker,'info') : ''}</div><div style="margin-top:6px"><strong>${esc(w.code)}</strong></div><div class="small" style="margin-top:4px">${esc(w.message)}</div></div>`
      ).join('')
    : `<div class="small">No integrity warnings.</div>`;
}

function actionCard(item, accent) {
  const earningsLine = item.daysToEarnings != null
    ? `${esc(item.earnings)}${item.daysToEarnings <= 7 ? ' <span class="pill warn" style="margin-left:6px">≤7d</span>' : ''}${item.earningsDateConfirmed === false ? ' <span class="pill warn" style="margin-left:6px">UNCONFIRMED DATE</span>' : ''}`
    : esc(item.earnings || '—');
  const bandGapLine = item.bandGap
    ? `${esc(item.bandGap)}${item.bandGapPct && item.bandGapPct !== '—' ? ` (${esc(item.bandGapPct)})` : ''}`
    : '—';
  const stateLabel = item.state || (accent==='earnings'?'EARNINGS PENDING':accent==='risk'?'BELOW STOP':accent.toUpperCase());
  const stateTone = item.proseConflict ? 'warn' : (accent==='deployable'?'ok':accent==='almost'||accent==='review'?'warn':accent==='earnings'?'info':'bad');
  const substateLine = item.displaySubState ? `<div class="action-card-foot tone-warn">${esc(item.displaySubState)}</div>` : '';
  const reviewOnlyLine = item.reviewOnlyNoApplyArtifact ? `<div class="action-card-foot tone-warn">REVIEW ONLY — NO APPLY ARTIFACT</div>` : '';
  const conflictLine = item.proseConflict ? `<div class="action-card-foot tone-warn">${esc(item.conflictProseState || 'Authority conflict')} · source: ${esc(item.proseConflictSource || 'prose')}</div>` : '';
  const proofLine = `<div class="action-card-foot small muted">Proof: ${esc(item.sourceArtifactPath || 'artifact unavailable')}${item.sourceGeneratedAtUtc ? ` · ${esc(item.sourceGeneratedAtUtc)}` : ''}${item.bandStale ? ' · BAND STALE' : ''}${item.overrideRule ? ` · override ${esc(item.overrideRule)}` : ''}</div>`;
  return `<div class="action-card action-${accent}">
    <div class="action-card-head">
      <div><span class="mono" style="font-size:16px;font-weight:700">${esc(item.ticker)}</span></div>
      <div>${pill(stateLabel, stateTone)}</div>
    </div>
    <div class="kv">
      <div>Close</div><div class="mono">${esc(item.close)}</div>
      <div>Entry band</div><div class="mono">${esc(item.entryBand || '—')}</div>
      <div>Stop</div><div class="mono">${esc(item.stop || '—')}</div>
      ${accent==='deployable' || accent==='almost' || accent==='blocked' ? `<div>Band gap</div><div>${bandGapLine}</div><div>Stop dist</div><div class="mono">${esc(item.stopDist || '—')}</div>` : ''}
      ${accent==='review' ? `<div>Band gap</div><div>${bandGapLine}</div><div>Stop dist</div><div class="mono">${esc(item.stopDist || '—')}</div><div>Authority</div><div>Owner approval required</div>` : ''}
      ${accent==='risk' ? `<div>Stop dist</div><div class="mono tone-bad">${esc(item.stopDist || '—')}</div>` : ''}
      <div>Posture</div><div>${esc(item.posture || '—')}</div>
      <div>Earnings</div><div>${earningsLine}</div>
    </div>
    ${item.triggerLabel ? `<div class="action-card-foot">${esc(item.triggerLabel)}</div>` : ''}
    ${item.reason ? `<div class="action-card-foot">${esc(item.reason)}</div>` : ''}
    ${substateLine}${reviewOnlyLine}${conflictLine}${proofLine}
  </div>`;
}

function actionSection(label, sublabel, items, accent) {
  const body = items && items.length
    ? items.map(i => actionCard(i, accent)).join('')
    : `<div class="card" style="padding:12px"><div class="small muted">No names currently in this bucket.</div></div>`;
  return `<div class="action-section">
    <div class="action-section-head">
      <span class="action-section-label action-${accent}-label">${esc(label)}</span>
      <span class="small">${esc(sublabel)}</span>
    </div>
    <div class="action-section-grid">${body}</div>
  </div>`;
}

function renderTodayAction() {
  const ta = DATA.today_action || {};
  const downgraded = !ta.enabled
    ? `<div class="alert warn"><div>!</div><div><strong>Action card downgraded</strong><div class="small">Execution context not healthy enough for a clean action read.</div></div></div>`
    : '';
  const sections = [
    actionSection('Deployable now', 'Trigger conditions met — review sizing before adding', ta.deployable, 'deployable'),
    actionSection('Promotion review', 'In band / high-priority review — owner approval still required; not deployable-now', ta.promotionReview, 'review'),
    actionSection('Almost deployable', 'Constructive setup, waiting on price or band entry', ta.almost, 'almost'),
    actionSection('Blocked / revalidation', 'Do not deploy until the blocker is explicitly cleared in the trigger layer', ta.blocked, 'blocked'),
    actionSection('Earnings pending', 'Catalyst pause — do not deploy until print is reviewed', ta.earningsPending, 'earnings'),
    actionSection('Risk-off — below stop', 'Repair confirmation required before re-engagement', ta.riskOff, 'risk'),
  ].join('');
  $('todayAction').innerHTML =
    `<div class="small" style="margin-bottom:14px">${esc(ta.message||'')}</div>` +
    downgraded + sections;
}

function renderOverviewCards() {
  $('overviewCards').innerHTML = (DATA.ui?.overview_cards||[]).map(c =>
    `<div class="card"><h3>${esc(c.label)}</h3><div class="big ${toneClass(c.tone)}">${esc(c.value)}</div><div class="small">${esc(c.detail)}</div></div>`
  ).join('');
}

function renderDeploymentStrip() {
  const ds = DATA.deployment_summary || {};
  const cells = [
    {label:'Deployable', tickers:ds.deployable, tone:'ok',   filter:'deployable'},
    {label:'Promotion review', tickers:ds.promotion_review, tone:'warn', filter:'review'},
    {label:'Almost',     tickers:ds.almost,     tone:'warn', filter:'almost'},
    {label:'Blocked',    tickers:ds.blocked,    tone:'bad',  filter:'blocked'},
    {label:'Below stop', tickers:ds.below_stop, tone:'bad',  filter:'blocked'},
    {label:'Bench / do not touch', tickers:ds.bench, tone:'info', filter:'watch'},
    {label:'Watch',      tickers:ds.watch,      tone:'info', filter:'watch'},
  ];
  const html = cells.map(c => {
    const list = (c.tickers||[]);
    const tickerLine = list.length ? list.slice(0,4).join(' · ') + (list.length>4?` +${list.length-4}`:'') : '—';
    return `<div class="deployment-strip-cell ${c.tone}" data-deploy-filter="${c.filter}">
      <div class="deployment-strip-count tone-${c.tone}">${list.length}</div>
      <div class="deployment-strip-label">${esc(c.label)}</div>
      <div class="deployment-strip-tickers">${esc(tickerLine)}</div>
    </div>`;
  }).join('');
  $('deploymentStrip').innerHTML = `<div class="deployment-strip">${html}</div>`;
  $('deploymentStrip').querySelectorAll('[data-deploy-filter]').forEach(el =>
    el.addEventListener('click', () => {
      if (typeof activeDeployFilter !== 'undefined') {
        activeDeployFilter = el.dataset.deployFilter;
        if (typeof renderDeployFilterBar === 'function') renderDeployFilterBar();
        if (typeof renderDeploymentTable === 'function') renderDeploymentTable();
      }
      if (typeof switchTab === 'function') switchTab('deployment');
      else document.querySelector('.nav button[data-tab="deployment"]')?.click();
    })
  );
}

function renderDeploymentOverview() {
  const ds = DATA.deployment_summary || {};
  const entries = [
    ['Deployable',       ds.deployable, 'ok'],
    ['Promotion review', ds.promotion_review, 'warn'],
    ['Almost',           ds.almost,     'warn'],
    ['Blocked',          ds.blocked,    'bad'],
    ['Below stop',       ds.below_stop, 'bad'],
    ['Bench / do not touch', ds.bench,  'info'],
    ['Watch',            ds.watch,      'info'],
  ];
  $('deploymentOverview').innerHTML = entries.map(([label, list, tone]) => {
    const tickers = list?.length ? `<div class="small mono" style="margin-top:2px">${esc(list.join(' · '))}</div>` : '';
    return row(`<div><strong>${label}</strong>${tickers}</div>`, pill(list?.length||0, tone));
  }).join('');
}

function renderManualDependencies() {
  const deps = DATA.trust.manual_dependencies || [];
  $('manualDependencies').innerHTML = deps.length
    ? deps.map(d => {
        const tone = d.tone || (d.status === 'manual' ? 'warn' : 'bad');
        const label = d.statusLabel || d.status || '—';
        return `<div class="row"><div><strong>${esc(d.label)}</strong><div class="small">${esc(d.scope)}</div></div><div style="max-width:58%;text-align:right">${pill(label, tone)}<div class="small">${esc(d.detail)}</div></div></div>`;
      }).join('')
    : '<div class="small">No live manual dependencies flagged.</div>';
}
