// ── Macro ─────────────────────────────────────────────────────────────────────

function macroCard(label, value, sub, tone='info') {
  return `<div class="card macro-stat-card"><div class="macro-stat-label">${esc(label)}</div><div class="big ${toneClass(tone)}">${esc(value)}</div>${sub?`<div class="small">${esc(sub)}</div>`:''}</div>`;
}

function renderRegimeBanner() {
  const r = DATA.macro_regime || {};
  if (!r.regime_label) {
    $('regimeBanner').innerHTML = '';
    return;
  }
  const pillarChip = (p, fallback) => p?.label
    ? `<div class="regime-pillar"><div class="regime-pillar-key">${esc((p.key||fallback).replace(/_/g,' '))}</div><div class="regime-pillar-label">${esc(p.label)}</div></div>`
    : '';
  // Only show a status pill if the regime feed itself is degraded — "ok"
  // adds no information next to the regime label.
  const statusPill = r.status && r.status !== 'ok'
    ? `<div class="regime-banner-status">${pill(r.status, toneMap[r.status]||'warn')}</div>`
    : '';
  $('regimeBanner').innerHTML = `<div class="card regime-banner">
    <div class="regime-banner-row">
      <div>
        <div class="tiny">Composite regime</div>
        <div class="regime-banner-label">${esc(r.regime_label)}</div>
      </div>
      ${statusPill}
    </div>
    <div class="regime-pillars">
      ${pillarChip(r.policy_pillar, 'policy')}
      ${pillarChip(r.credit_pillar, 'credit')}
      ${pillarChip(r.breadth_pillar, 'breadth')}
    </div>
  </div>`;
}

function renderRatesStrip() {
  const m = DATA.market || {};
  const t = m.treasuries || {};
  const curveLabel = (bps) => bps == null ? 'Source unavailable' : bps > 0 ? 'Positive — normal slope' : 'Inverted';
  const curveTone  = (bps) => bps == null ? 'info' : bps > 0 ? 'ok' : 'warn';
  const cards = [
    ['3M T-Bill', t.m3!=null?`${t.m3}%`:'—', 'Short rate', 'info'],
    ['2Y',        t.y2!=null?`${t.y2}%`:'—', 'Policy-sensitive', 'info'],
    ['10Y',       t.y10!=null?`${t.y10}%`:'—', 'Long rate', 'info'],
    ['2s10s',     t.curve_2s10s!=null?`${t.curve_2s10s}bps`:'—', curveLabel(t.curve_2s10s), curveTone(t.curve_2s10s)],
    ['3m10y',     t.curve_3m10y!=null?`${t.curve_3m10y}bps`:'—', curveLabel(t.curve_3m10y), curveTone(t.curve_3m10y)],
    ['DXY',       m.dxy!=null?m.dxy:'—', 'Dollar index', 'info'],
  ];
  $('ratesStrip').innerHTML = cards.map(([l,v,s,tone]) => macroCard(l,v,s,tone)).join('');
}

function renderRiskStrip() {
  const m = DATA.market || {};
  const c = DATA.credit_spreads || {};
  const ig = c.investment_grade_oas?.value;
  const hy = c.high_yield_oas?.value;
  const vixSub  = m.vix == null ? 'Source unavailable' : m.vix>=25?'High volatility':m.vix>=20?'Elevated':'Calm';
  const vixTone = m.vix == null ? 'info' : m.vix>=25?'bad':m.vix>=20?'warn':'ok';
  const igTone  = ig == null ? 'info' : ig > 1.5 ? 'warn' : 'ok';
  const hyTone  = hy == null ? 'info' : hy > 5 ? 'bad' : hy > 3.5 ? 'warn' : 'ok';
  const cards = [
    ['VIX', m.vix??'—', vixSub, vixTone],
    ['IG OAS', ig!=null?`${ig}%`:'—', c.direction?.ig_20d?`20d ${c.direction.ig_20d}`:'—', igTone],
    ['HY OAS', hy!=null?`${hy}%`:'—', c.direction?.hy_20d?`20d ${c.direction.hy_20d}`:'—', hyTone],
    ['S&P 500', m.spx??'—', 'Cash index', 'ok'],
    ['Brent', m.brent!=null?`$${m.brent}`:'—', 'Energy complex', 'info'],
    ['WTI', m.wti!=null?`$${m.wti}`:'—', 'Crude — US benchmark', 'info'],
  ];
  $('riskStrip').innerHTML = cards.map(([l,v,s,tone]) => macroCard(l,v,s,tone)).join('');
}

function renderFomcCard() {
  const p = DATA.policy_expectations || {};
  const tr = p.current_target_range || {};
  const next = p.next_fomc || {};
  const dist = next.distribution || [];
  const distMap = Object.fromEntries(dist.map(d => [d.outcome, d.probability]));
  const hold = distMap.hold || 0;
  const cut  = (distMap.cut_25bp||0) + (distMap.cut_50bp||0);
  const hike = (distMap.hike_25bp||0) + (distMap.hike_50bp||0);
  const totalProb = cut + hold + hike;
  const bar = totalProb > 0
    ? `<div class="prob-bar">
        <div class="prob-segment prob-cut" style="flex:${cut}" title="Cut ${cut}%">${cut>8?`${Math.round(cut)}%`:''}</div>
        <div class="prob-segment prob-hold" style="flex:${hold}" title="Hold ${hold}%">${hold>8?`Hold ${Math.round(hold)}%`:''}</div>
        <div class="prob-segment prob-hike" style="flex:${hike}" title="Hike ${hike}%">${hike>8?`${Math.round(hike)}%`:''}</div>
      </div>`
    : '<div class="prob-bar prob-bar-empty"><span class="small muted">No probability data</span></div>';
  const manualBadge = p.status === 'manual' ? pill('manual dependency', 'warn') : '';
  $('fomcCard').innerHTML = `
    <div class="kv" style="margin-bottom:12px">
      <div>Target range</div><div class="mono">${tr.low!=null?`${tr.low}–${tr.high}%`:'—'}</div>
      <div>Implied rate</div><div class="mono">${next.implied_rate!=null?`${next.implied_rate}%`:'—'}</div>
      <div>Most likely</div><div>${esc(next.most_likely_outcome||'—')}</div>
      <div>Next meeting</div><div class="mono">${esc(next.meeting_date||'—')}${next.days_until!=null?` (${next.days_until}d)`:''}</div>
    </div>
    <div class="tiny" style="margin-bottom:6px">Probability distribution</div>
    ${bar}
    <div class="prob-legend"><span><span class="prob-dot prob-cut"></span>Cut ${cut.toFixed(0)}%</span><span><span class="prob-dot prob-hold"></span>Hold ${hold.toFixed(0)}%</span><span><span class="prob-dot prob-hike"></span>Hike ${hike.toFixed(0)}%</span></div>
    <div style="margin-top:10px">${manualBadge}<span class="small" style="margin-left:6px">${esc(p.source_label||'')}</span></div>
  `;
}

function renderCreditCard() {
  const c = DATA.credit_spreads || {};
  const ig = c.investment_grade_oas || {};
  const hy = c.high_yield_oas || {};
  const dir = c.direction || {};
  const stressTone = c.stress_regime === 'benign' ? 'ok' : c.stress_regime === 'elevated' ? 'warn' : c.stress_regime === 'stressed' ? 'bad' : 'info';
  $('creditCard').innerHTML = `
    <div style="margin-bottom:10px">${pill(`stress: ${c.stress_regime||'—'}`, stressTone)}</div>
    <div class="kv">
      <div>IG OAS</div><div class="mono">${ig.value!=null?`${ig.value}%`:'—'}</div>
      <div>HY OAS</div><div class="mono">${hy.value!=null?`${hy.value}%`:'—'}</div>
      <div>HY − IG</div><div class="mono">${c.hy_minus_ig_spread!=null?`${c.hy_minus_ig_spread}%`:'—'}</div>
      <div>IG 5d / 20d</div><div>${esc(dir.ig_5d||'—')} / ${esc(dir.ig_20d||'—')}</div>
      <div>HY 5d / 20d</div><div>${esc(dir.hy_5d||'—')} / ${esc(dir.hy_20d||'—')}</div>
      <div>As of</div><div class="mono">${esc(ig.as_of||hy.as_of||'—')}</div>
    </div>
  `;
}

function renderBreadthCard() {
  const b = DATA.market_breadth || {};
  const sp = b.sector_participation || {};
  const ew = b.equal_weight_vs_cap_weight || {};
  const dirTone = ew.direction === 'improving' ? 'ok' : ew.direction === 'deteriorating' ? 'warn' : 'info';
  const partTone = sp.participation_pct == null ? 'info' : sp.participation_pct >= 70 ? 'ok' : sp.participation_pct >= 50 ? 'warn' : 'bad';
  const sectorBars = (sp.sectors || []).map(s => {
    const above = s.above_50dma;
    return `<div class="breadth-sector ${above?'above':'below'}" title="${esc(s.label)} ${above?'above':'below'} 50DMA">${esc(s.ticker)}</div>`;
  }).join('');
  $('breadthCard').innerHTML = `
    <div class="kv" style="margin-bottom:10px">
      <div>Sectors > 50DMA</div><div><span class="${toneClass(partTone)}">${sp.sectors_above_50dma||0}/${sp.sectors_total||0}</span> <span class="small">(${sp.participation_pct!=null?sp.participation_pct.toFixed(1):'—'}%)</span></div>
      <div>Participation regime</div><div>${pill(sp.participation_regime||'—', partTone)}</div>
      <div>RSP/SPY 5d</div><div class="mono ${ew.rsp_spy_ratio_5d_change_pct==null?'':ew.rsp_spy_ratio_5d_change_pct<0?'tone-warn':'tone-ok'}">${ew.rsp_spy_ratio_5d_change_pct!=null?`${ew.rsp_spy_ratio_5d_change_pct.toFixed(2)}%`:'—'}</div>
      <div>RSP/SPY 20d</div><div class="mono ${ew.rsp_spy_ratio_20d_change_pct==null?'':ew.rsp_spy_ratio_20d_change_pct<0?'tone-warn':'tone-ok'}">${ew.rsp_spy_ratio_20d_change_pct!=null?`${ew.rsp_spy_ratio_20d_change_pct.toFixed(2)}%`:'—'}</div>
      <div>Direction</div><div>${pill(ew.direction||'—', dirTone)}</div>
    </div>
    <div class="tiny" style="margin-bottom:6px">Sector posture (above/below 50DMA)</div>
    <div class="breadth-sector-grid">${sectorBars||'<span class="small muted">No sector data.</span>'}</div>
  `;
}

function renderSectorRelative() {
  const sectors = DATA.sectors_relative || [];
  if (!sectors.length) {
    $('sectorRelative').innerHTML = '<div class="small muted">No sector relative-strength data.</div>';
    return;
  }
  const maxAbs = Math.max(0.5, ...sectors.map(s => Math.abs(s.relative_vs_spx_pct||0)));
  $('sectorRelative').innerHTML = sectors.map(s => {
    const v = s.relative_vs_spx_pct;
    if (v == null) return '';
    const pct = Math.min(100, Math.abs(v)/maxAbs*100);
    const positive = v >= 0;
    const tone = v >= 1 ? 'ok' : v <= -1 ? 'bad' : 'info';
    return `<div class="rs-row">
      <div class="rs-label"><span class="mono">${esc(s.ticker)}</span> <span class="small">${esc(s.label)}</span></div>
      <div class="rs-bar-wrap">
        <div class="rs-bar-axis"></div>
        <div class="rs-bar ${positive?'pos':'neg'}" style="width:${pct/2}%; ${positive?'left':'right'}:50%"></div>
      </div>
      <div class="rs-value mono ${toneClass(tone)}">${v>=0?'+':''}${v.toFixed(2)}%</div>
    </div>`;
  }).join('');
}

function renderMacro() {
  const m = DATA.market || {};
  renderRegimeBanner();
  renderRatesStrip();
  renderRiskStrip();
  renderFomcCard();
  renderCreditCard();
  renderBreadthCard();
  renderSectorRelative();
  $('regimeIndicators').innerHTML = (DATA.regime_indicators||[]).map(item =>
    row(
      `<div><strong>${esc(item.label)}</strong><div class="small">${esc(item.detail)}</div></div>`,
      `<span class="${toneClass(item.colorKey==='red'?'bad':(item.colorKey==='amber'?'warn':'info'))}">${esc(item.value)}</span>`
    )
  ).join('') || '<div class="small">No regime indicators.</div>';
  $('macroWarnings').innerHTML = (m.warnings||[]).map(w =>
    `<div class="row"><div>${pill('warn','warn')}</div><div class="small" style="max-width:70%;text-align:right">${esc(w)}</div></div>`
  ).join('') || '<div class="small">No macro warnings.</div>';
}
