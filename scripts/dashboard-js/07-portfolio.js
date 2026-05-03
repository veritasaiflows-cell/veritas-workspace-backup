// ── Portfolio ─────────────────────────────────────────────────────────────────

function renderPortfolio() {
  const p = DATA.portfolio || {};
  const all = [
    ...(p.core||[]).map(x=>({...x,sleeve:'Core'})),
    ...(p.tactical||[]).map(x=>({...x,sleeve:'Tactical'})),
    ...(p.speculative||[]).map(x=>({...x,sleeve:'Speculative'})),
  ];
  $('portfolioCards').innerHTML = [
    ['Posture',      p.posture||'—',          'info'],
    ['Capital base', p.capital||'—',          'ok'],
    ['Cash',         `${p.cash??'—'}%`,       'warn'],
  ].map(([label,value,tone]) =>
    `<div class="card"><h3>${esc(label)}</h3><div class="big ${toneClass(tone)}">${esc(value)}</div></div>`
  ).join('');
  $('sectorWeights').innerHTML = Object.entries(DATA.sector_weights||{}).sort((a,b)=>b[1]-a[1]).map(([sector,weight]) =>
    row(`<strong>${esc(sector)}</strong>`, `${esc(weight)}%`)
  ).join('') || '<div class="small">No sector concentration data.</div>';
  $('allocationMix').innerHTML =
    row('Core',        `${(p.core||[]).reduce((a,x)=>a+(x.weight||0),0)}%`) +
    row('Tactical',    `${(p.tactical||[]).reduce((a,x)=>a+(x.weight||0),0)}%`) +
    row('Speculative', `${(p.speculative||[]).reduce((a,x)=>a+(x.weight||0),0)}%`) +
    row('Cash',        `${p.cash||0}%`);
  $('portfolioTable').innerHTML = all.map(pos =>
    `<tr><td class="mono"><strong>${esc(pos.ticker)}</strong></td><td>${esc(pos.weight)}%</td><td>${esc(pos.sleeve)}</td><td>${esc(pos.thesis||pos.risk||'—')}</td><td>${esc(pos.entry||pos.thesis||'—')}</td><td>${esc(pos.stop||pos.risk||'—')}</td></tr>`
  ).join('');
}
