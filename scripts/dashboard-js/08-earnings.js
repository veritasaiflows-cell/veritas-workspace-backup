// ── Earnings ──────────────────────────────────────────────────────────────────

function renderEarnings() {
  $('earningsList').innerHTML = (DATA.earnings||[]).slice(0,20).map(item =>
    row(`<strong class="mono">${esc(item.ticker)}</strong>`, esc(item.date))
  ).join('') || '<div class="small">No earnings records.</div>';
  $('earningsAlerts').innerHTML = (DATA.earnings_alerts||[]).map(a =>
    `<div class="row"><div>${pill(a.includes('DATE CHANGED')?'date changed':'alert', a.includes('DATE CHANGED')?'warn':'info')}</div><div class="small" style="max-width:70%;text-align:right">${esc(a)}</div></div>`
  ).join('') || '<div class="small">No earnings alerts.</div>';
}
