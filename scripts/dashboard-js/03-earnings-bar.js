// ── Earnings imminence bar ────────────────────────────────────────────────────

function renderEarningsBar() {
  const imminent = (DATA.technical || [])
    .filter(t => t.daysToEarnings != null && t.daysToEarnings >= 0 && t.daysToEarnings <= 7)
    .sort((a, b) => a.daysToEarnings - b.daysToEarnings);
  if (!imminent.length) return;
  const bar = $('earningsBar');
  bar.classList.add('active');
  const parts = imminent.map(t =>
    `<span>${pill(t.ticker, 'bad')} <span style="font-size:11px;color:var(--muted)">${t.daysToEarnings === 0 ? 'today' : `${t.daysToEarnings}d`}</span></span>`
  ).join(' ');
  bar.innerHTML = `<strong>EARNINGS IMMINENT:</strong> ${parts}`;
}
