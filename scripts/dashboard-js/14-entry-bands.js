// ── Entry Bands tab ───────────────────────────────────────────────────────────

const BAND_STATUS_ORDER = {
  'BELOW STOP': 0, 'IN BAND': 1, 'NEAR BAND': 2,
  'BELOW BAND': 3, 'ABOVE BAND': 4, 'NO BAND': 5, 'NO DATA': 6,
};
const BAND_STATUS_TONE = {
  'BELOW STOP': 'bad', 'IN BAND': 'ok', 'NEAR BAND': 'warn',
  'BELOW BAND': 'warn', 'ABOVE BAND': 'info', 'NO BAND': 'info', 'NO DATA': 'info',
};
const ENTRY_BANDS_BASE = '../generated documents/entry-bands/';

let activeBandTicker = null;

function renderEntryBands() {
  const rows = (DATA.technical || [])
    .filter(t => t.bandStatus)
    .slice()
    .sort((a, b) =>
      (BAND_STATUS_ORDER[a.bandStatus] ?? 99) - (BAND_STATUS_ORDER[b.bandStatus] ?? 99) ||
      a.ticker.localeCompare(b.ticker)
    );

  if (!rows.length) {
    $('entryBandsList').innerHTML = '<div class="small muted" style="padding:16px">No band status data. Run entry_band_fetch.py --all-tracked.</div>';
    return;
  }

  $('entryBandsList').innerHTML = rows.map(t => {
    const tone = BAND_STATUS_TONE[t.bandStatus] || 'info';
    const earnFlag = t.blocked ? `<span style="font-size:10px;color:var(--warn);margin-left:6px">⚠ ERN</span>` : '';
    const distStr = t.bandDistPct != null
      ? `<span style="font-size:11px;color:var(--muted)">${t.bandDistPct > 0 ? '+' : ''}${t.bandDistPct.toFixed(1)}%</span>`
      : '';
    return `<div class="eb-row ${activeBandTicker === t.ticker ? 'active' : ''}" data-ticker="${t.ticker}">
      <div>
        <span class="mono" style="font-weight:700;font-size:14px">${esc(t.ticker)}</span>${earnFlag}
        <div class="small" style="margin-top:2px">${esc(t.posture || '—')}</div>
      </div>
      <div style="text-align:right">
        ${pill(t.bandStatus, tone)}
        ${distStr}
      </div>
    </div>`;
  }).join('');

  $('entryBandsList').querySelectorAll('.eb-row').forEach(el => {
    el.addEventListener('click', () => {
      activeBandTicker = el.dataset.ticker;
      const row = rows.find(r => r.ticker === activeBandTicker);
      loadBandViewer(row);
      renderEntryBands();
    });
  });

  if (!activeBandTicker && rows.length) {
    activeBandTicker = rows[0].ticker;
    loadBandViewer(rows[0]);
    renderEntryBands();
  }
}

function loadBandViewer(row) {
  const frame = $('entryBandFrame');
  if (!frame) return;
  if (row?.entryBandReportPath) {
    frame.src = row.entryBandReportPath;
  } else {
    frame.srcdoc = `<html><body style="margin:0;background:#0b1120;color:#94a3b8;font-family:Segoe UI,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;font-size:13px">No band report on file for ${esc(row?.ticker || '—')}. Run entry_band_fetch.py --all-tracked --html.</body></html>`;
  }
}
