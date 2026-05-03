// ── Risk & Rules ──────────────────────────────────────────────────────────────

function renderRisk() {
  const rt = DATA.risk_thresholds || {};
  $('riskCards').innerHTML = [
    ['Max single',     `${rt.max_single_position_normal??'—'}%`, 'warn'],
    ['Max sector',     `${rt.max_sector_pct??'—'}%`,             'info'],
    ['Drawdown review',`${rt.drawdown_review_trigger_pct??'—'}%`,'bad'],
  ].map(([label,value,tone]) =>
    `<div class="card"><h3>${esc(label)}</h3><div class="big ${toneClass(tone)}">${esc(value)}</div></div>`
  ).join('');
  $('complianceChecks').innerHTML = (DATA.ui?.compliance_checks||[]).map(c =>
    row(
      `<div><strong>${esc(c.label)}</strong><div class="small">${esc(c.detail)}</div></div>`,
      pill(c.status, c.status)
    )
  ).join('');
  const rules = (DATA.sizing_rules||[]).map(r =>
    row(`<div><strong>${esc(r.tier)}</strong></div>`, `<div class="small">${esc(r.range)} · max ${esc(r.max)}</div>`)
  ).join('');
  const escalations = (DATA.escalation_triggers||[]).map(t =>
    `<div class="row"><div class="small">${esc(t)}</div></div>`
  ).join('');
  $('rulesAndEscalation').innerHTML =
    `<div class="section-title">Sizing rules</div>${rules||'<div class="small">No sizing rules.</div>'}` +
    `<div class="section-title" style="margin-top:14px">Escalation triggers</div>${escalations||'<div class="small">No escalation triggers.</div>'}`;
}
