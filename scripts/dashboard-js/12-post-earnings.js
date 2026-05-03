// ── Post-Earnings ─────────────────────────────────────────────────────────────

function renderPostEarningsCard(p) {
  const phase = p.phase || (p.days_to_or_from_earnings == null ? 'unknown' : p.days_to_or_from_earnings < 0 ? 'post_earnings' : p.days_to_or_from_earnings === 0 ? 'reporting_today' : 'pre_earnings');
  const cardCls = phase === 'post_earnings' ? 'recent' : phase === 'pre_earnings' ? 'upcoming' : '';
  const priorityTone = p.priority==='critical' ? 'bad' : p.priority==='high' ? 'warn' : p.priority==='upcoming' ? 'warn' : 'info';
  const watchItems = (p.watch_items||[]).map(w => `<li>${esc(w)}</li>`).join('');
  const noteTargets = (p.note_targets||[]).map(t => `<li>${esc(t)}</li>`).join('');
  const techCtx = p.technical_context || {};
  const deployCtx = p.deployment_context || {};
  const d = p.days_to_or_from_earnings;
  const daysLabel = d == null ? '—' : d > 0 ? `in ${d}d` : d === 0 ? 'today' : `${Math.abs(d)}d ago`;
  const stageBadge = p.stage ? `<span class="pill info" style="margin-left:6px">${esc(p.stage)}</span>` : '';
  const interp = p.interpretation_slots || {};
  const needsInterpretation = phase === 'post_earnings' && !interp.what_happened;
  return `<div class="pe-card ${cardCls}">
    <div class="pe-card-head">
      <div>
        <span class="pe-card-ticker">${esc(p.ticker)}</span>
        <span class="small" style="margin-left:8px">${esc(p.next_earnings_date||'—')} (${daysLabel})</span>
        ${stageBadge}
      </div>
      ${pill(p.priority||'—', priorityTone)}
    </div>
    ${p.sector_read_through ? `<div class="pe-context">${esc(p.sector_read_through)}</div>` : ''}
    ${watchItems ? `<div style="margin-bottom:10px"><div class="pe-block-label">${phase==='post_earnings'?'Read through':'Watch items'}</div><ul class="watch-list">${watchItems}</ul></div>` : ''}
    <div class="kv" style="margin-bottom:8px">
      <div>Close</div><div class="mono">${techCtx.close!=null?`$${techCtx.close}`:'—'}</div>
      <div>Posture</div><div>${esc(techCtx.ma_posture||'—')}</div>
      <div>Deploy state</div><div>${pill(deployCtx.action_state||'—', stateTone(deployCtx.action_state))}</div>
      <div>Data date</div><div>${esc(techCtx.data_date||'—')}</div>
    </div>
    ${needsInterpretation ? `<div class="pe-interpret-prompt">⚑ Interpretation pending — fill what happened / what it means / what we do now</div>` : ''}
    ${noteTargets ? `<div><div class="pe-block-label">Note targets</div><ul class="watch-list">${noteTargets}</ul></div>` : ''}
  </div>`;
}

function renderPostEarnings() {
  const pe = DATA.post_earnings || {};
  const packets = pe.packets || [];

  if (!packets.length) {
    $('postEarningsHeader').innerHTML = '<div class="small muted">No post-earnings packets in current window.</div>';
    $('postEarningsGrid').innerHTML = '';
    return;
  }

  const phaseOf = p => p.phase || (p.days_to_or_from_earnings == null ? 'unknown' : p.days_to_or_from_earnings < 0 ? 'post_earnings' : p.days_to_or_from_earnings === 0 ? 'reporting_today' : 'pre_earnings');
  const reportingToday = packets.filter(p => phaseOf(p) === 'reporting_today');
  const preEarnings = packets.filter(p => phaseOf(p) === 'pre_earnings');
  const postEarnings = packets.filter(p => phaseOf(p) === 'post_earnings');

  const peWindow = pe.window || {};
  const windowLabel = peWindow.back_trading_days
    ? `Window: ${peWindow.back_trading_days} trading days back · ${peWindow.forward_days||0}d forward`
    : (peWindow.back_days ? `Window: ${peWindow.back_days}d back · ${peWindow.forward_days||0}d forward` : '');

  $('postEarningsHeader').innerHTML =
    `<div class="card" style="padding:12px">` +
    `<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">` +
    `<div><strong>Post-Earnings Context</strong> <span class="small">as of ${esc(pe.last_trading_day||'—')}${windowLabel?` · ${esc(windowLabel)}`:''}</span></div>` +
    `<div>` +
    (reportingToday.length ? pill(`${reportingToday.length} reporting today`, 'bad') : '') +
    (preEarnings.length ? pill(`${preEarnings.length} pre-print`, 'warn') : '') +
    (postEarnings.length ? pill(`${postEarnings.length} recently reported`, 'info') : '') +
    `</div></div>` +
    (pe.warnings?.length
      ? `<div style="margin-top:10px;display:flex;flex-direction:column;gap:4px">${pe.warnings.slice(0,2).map(w=>`<div class="small" style="color:var(--warn)">⚠ ${esc(w)}</div>`).join('')}</div>`
      : '') +
    `</div>`;

  const priorityRank = p => (p.priority==='critical'?0:p.priority==='high'?1:p.priority==='upcoming'?2:3);
  const sortByDays = (a,b) => Math.abs(a.days_to_or_from_earnings ?? 99) - Math.abs(b.days_to_or_from_earnings ?? 99);
  const sortPre = (a,b) => priorityRank(a) - priorityRank(b) || sortByDays(a,b);

  const preToday = [...reportingToday, ...preEarnings].sort(sortPre);
  const postSorted = [...postEarnings].sort(sortByDays);

  let html = '';
  if (preToday.length) {
    html += `<div class="pe-section-label">Reporting today and upcoming</div>` +
      `<div class="grid cols-2 pe-grid">${preToday.map(renderPostEarningsCard).join('')}</div>`;
  }
  if (postSorted.length) {
    html += `<div class="pe-section-label">Recently reported — interpret and update notes</div>` +
      `<div class="grid cols-2 pe-grid">${postSorted.map(renderPostEarningsCard).join('')}</div>`;
  }
  $('postEarningsGrid').innerHTML = html;
}
