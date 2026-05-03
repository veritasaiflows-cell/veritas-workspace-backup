// ── Age counter ───────────────────────────────────────────────────────────────

function updateAgeCounter() {
  const genAt = DATA.generated_at;
  if (!genAt) return;
  const parsed = new Date(genAt.replace(' ', 'T').endsWith('UTC') ? genAt.replace(' UTC','Z') : genAt);
  if (isNaN(parsed)) return;
  const ageMs = Date.now() - parsed.getTime();
  const ageMin = Math.floor(ageMs / 60000);
  const ageSec = Math.floor((ageMs % 60000) / 1000);
  const label = ageMin > 0 ? `${ageMin}m ${ageSec}s old` : `${ageSec}s old`;
  const el = $('ageCounter');
  el.textContent = label;
  el.className = 'age-counter ' + (ageMin < 15 ? 'fresh' : ageMin < 60 ? 'aging' : 'stale');
  el.title = `Data generated at ${genAt}`;
}
