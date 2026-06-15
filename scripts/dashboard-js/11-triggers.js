// ── Execution Board ───────────────────────────────────────────────────────────

function triggerCardClass(state) {
  if (!state) return 'donottouch';
  const s = state.toUpperCase();
  if (s.includes('DEPLOYABLE NOW')) return 'deployable';
  if (s.includes('AUTHORITY CONFLICT')) return 'almost';
  if (s.includes('PROMOTION REVIEW')) return 'almost';
  if (s.includes('ALMOST')) return 'almost';
  if (s === 'BLOCKED') return 'blocked';
  if (s.includes('WATCH') || s.includes('RESEARCH')) return 'watch';
  return 'donottouch';
}

function triggerStateTone(state) {
  if (!state) return 'info';
  const s = state.toUpperCase();
  if (s.includes('DEPLOYABLE NOW')) return 'ok';
  if (s.includes('AUTHORITY CONFLICT')) return 'warn';
  if (s.includes('PROMOTION REVIEW')) return 'warn';
  if (s.includes('ALMOST')) return 'warn';
  if (s === 'BLOCKED') return 'bad';
  if (s.includes('WATCH') || s.includes('RESEARCH')) return 'info';
  return 'info';
}

function renderTriggerCard(r) {
  const cardCls = triggerCardClass(r.action_state);
  const stateToneCls = triggerStateTone(r.action_state);
  const bandLabel = r.entry_band?.label || '—';
  const invalidation = r.invalidation != null ? `$${r.invalidation}` : '—';
  const substate = r.displaySubState ? `<div class="trigger-warn">${esc(r.displaySubState)}</div>` : '';
  const conflict = r.proseConflict ? `<div class="trigger-warn">⚠ ${esc(r.conflictProseState || 'Authority conflict')} · ${esc(r.proseConflictSource || 'prose conflict')}</div>` : '';
  const reviewOnly = r.action_state && r.action_state.toUpperCase().includes('DEPLOYABLE') ? `<div class="trigger-warn">REVIEW ONLY — NO APPLY ARTIFACT</div>` : '';
  const unconfirmedEarnings = r.earningsDateConfirmed === false ? `<div class="trigger-warn">UNCONFIRMED DATE</div>` : '';
  const proof = `<div class="small muted">Proof: tmp/trigger-sheet.json${r.generated_at_utc ? ` · ${esc(r.generated_at_utc)}` : ''}${r.override_rule ? ` · override ${esc(r.override_rule)}` : ''}</div>`;
  return `<div class="trigger-card ${cardCls}">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:10px">
      <div>
        <span class="mono" style="font-size:16px;font-weight:700">${esc(r.ticker)}</span>
        <span class="small" style="margin-left:8px">${esc(r.portfolio_role||'—')}</span>
      </div>
      <div style="text-align:right">
        ${pill(r.action_state||'—', stateToneCls)}
        <div class="small" style="margin-top:4px">${esc(r.size_tier||'—')}</div>
      </div>
    </div>
    <div class="trigger-why">${esc(r.why||'—')}</div>
    ${substate}${conflict}${reviewOnly}${unconfirmedEarnings}
    <div class="kv" style="margin-bottom:8px">
      <div>Close</div><div class="mono">${r.close!=null?`$${r.close}`:'—'}</div>
      <div>Entry band</div><div class="mono">${esc(bandLabel)}</div>
      <div>Invalidation</div><div class="mono">${invalidation}</div>
      <div>Thesis</div><div>${pill(r.thesis_status||'—', r.thesis_status?.includes('intact')?'ok':'warn')}</div>
    </div>
    ${r.technical_trigger ? `<div class="trigger-block"><strong class="trigger-block-label">Trigger</strong><br>${esc(r.technical_trigger)}</div>` : ''}
    ${proof}
    ${r.catalyst_blocker ? `<div class="trigger-warn">⚠ ${esc(r.catalyst_blocker)}</div>` : ''}
    ${r.macro_fit ? `<div class="trigger-macro">${esc(r.macro_fit)}</div>` : ''}
  </div>`;
}

function renderTriggerSheet() {
  const ts = DATA.trigger_sheet || {};
  const records = ts.records || [];

  const sum = ts.summary || {};
  const summaryParts = [
    sum.deployable_now?.length && `${pill(`${sum.deployable_now.length} deployable`,'ok')}`,
    sum.authority_conflict?.length && `${pill(`${sum.authority_conflict.length} authority conflict`,'warn')}`,
    sum.promotion_review?.length && `${pill(`${sum.promotion_review.length} promotion review`,'warn')}`,
    sum.almost_deployable?.length && `${pill(`${sum.almost_deployable.length} almost`,'warn')}`,
    sum.blocked?.length && `${pill(`${sum.blocked.length} blocked`,'bad')}`,
    sum.do_not_touch?.length && `${pill(`${sum.do_not_touch.length} do not touch`,'info')}`,
    sum.watch?.length && `${pill(`${sum.watch.length} watch`,'info')}`,
  ].filter(Boolean).join(' ');

  $('triggerHeader').innerHTML =
    `<div class="card" style="padding:12px">` +
    `<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px">` +
    `<div><strong>Execution Board</strong> <span class="small">as of ${esc(ts.last_trading_day||'—')}</span></div>` +
    `<div>${summaryParts}</div>` +
    `</div>` +
    (ts.warnings?.length
      ? `<div style="margin-top:10px;display:flex;flex-direction:column;gap:4px">${ts.warnings.slice(0,3).map(w=>`<div class="small" style="color:var(--warn)">⚠ ${esc(w)}</div>`).join('')}</div>`
      : '') +
    `</div>`;

  if (!records.length) {
    $('triggerGrid').innerHTML = '<div class="small muted">No trigger sheet records.</div>';
    return;
  }

  const isDeployable = r => (r.action_state||'').toUpperCase().includes('DEPLOYABLE NOW') && !r.proseConflict;
  const deployable = records.filter(isDeployable);
  const others = records.filter(r => !isDeployable(r));

  const order = {'ALMOST DEPLOYABLE':0,'BLOCKED':1,'DO NOT TOUCH':2,'WATCH / RESEARCH NEEDED':3};
  others.sort((a,b) => (order[a.action_state]??4) - (order[b.action_state]??4));

  const calloutStrip = deployable.length
    ? `<div class="trigger-callout">
        <div class="trigger-callout-header">
          <span class="trigger-callout-label">DEPLOYABLE NOW</span>
          <span class="small">${deployable.length} name${deployable.length===1?'':'s'} meeting trigger conditions — review before adding</span>
        </div>
        <div class="trigger-grid">${deployable.map(renderTriggerCard).join('')}</div>
      </div>`
    : '';

  $('triggerGrid').innerHTML = calloutStrip + others.map(renderTriggerCard).join('');
}
