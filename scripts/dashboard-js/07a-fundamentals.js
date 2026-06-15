function fmtTrendPct(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '—';
  const n = Number(v);
  return `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`;
}

function fmtFcfMetric(r, value) {
  if (r.fcfInterpretation === 'bank_structural') return 'bank n/a';
  return fmtTrendPct(value);
}

function fmtFcfPerShareYoY(r) {
  if (r.fcfInterpretation === 'bank_structural') {
    const suffix = r.fcfPerShareYoYBase === 'negative' ? 'neg-base' : 'bank n/a';
    return `${fmtTrendPct(r.fcfPerShareYoY)} (${suffix})`;
  }
  return fmtTrendPct(r.fcfPerShareYoY);
}

function fmtBankRatio(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return 'manual required';
  return `${Number(v).toFixed(1)}%`;
}

function fmtBankNative(r) {
  if (r.wf65BankNativeVersion !== 'v1_5_partial') return '';
  const autoCount = r.bankNativeAutoResolvedCount ?? '?';
  const manualCount = r.bankNativeManualRequiredCount ?? '?';
  const secStatus = r.bankNativeSecStatus || 'manual_required';
  const confirmed = r.cet1Ratio !== null && r.cet1Ratio !== undefined && r.tier1Ratio !== null && r.tier1Ratio !== undefined;
  const riskBased = confirmed
    ? `CET1 ${fmtBankRatio(r.cet1Ratio)} (${esc(r.cet1RatioBasis || r.riskBasedCapitalPrimaryFramework || 'official')}; Std ${fmtBankRatio(r.cet1RatioStandardized)} / Adv ${fmtBankRatio(r.cet1RatioAdvanced)}) ? Tier 1 ${fmtBankRatio(r.tier1Ratio)} (${esc(r.tier1RatioBasis || r.riskBasedCapitalPrimaryFramework || 'official')}; Std ${fmtBankRatio(r.tier1RatioStandardized)} / Adv ${fmtBankRatio(r.tier1RatioAdvanced)}) ? official source, not derived`
    : 'CET1/Tier1 risk-based manual required';
  const leverage = r.tier1LeverageRatio === null || r.tier1LeverageRatio === undefined ? 'not available' : `${Number(r.tier1LeverageRatio).toFixed(2)}% auto (NOT risk-based)`;
  return `<div class="small muted">WF65 bank-native: SEC ${esc(secStatus)} ? ${esc(autoCount)} auto-resolved ? ${esc(manualCount)} manual-required ? ${riskBased} ? Tier 1 leverage ${esc(leverage)} ? status ${esc(r.bankNativeStatus || 'partial')}</div>`;
}

function renderFundamentals() {
  const ft = DATA.fundamental_trends || {};
  const rows = ft.rows || [];
  const summary = ft.summary || {};
  const quality = ft.quality_counts || summary.quality_counts || {};
  const sec = ft.sec_reconciliation_counts || summary.sec_reconciliation_counts || {};
  const irPackets = ft.ir_packet_summary || {};
  const authority = ft.authority || {};
  if ($('fundamentalSummary')) {
    $('fundamentalSummary').innerHTML = [
      `<div class="card"><h3>Coverage</h3>${row('Equity rows', esc(summary.equity_tickers ?? rows.length))}${row('Clean equity rows', esc(summary.clean_equity_tickers ?? '—'))}${row('Generated', esc(ft.generated_at || 'Unavailable'))}</div>`,
      `<div class="card"><h3>Data Quality</h3>${row('Clean', esc(quality.clean || 0))}${row('Partial', esc(quality.partial || 0))}${row('N/A proxies', esc(quality.not_applicable || 0))}</div>`,
      `<div class="card"><h3>Per-Share Quality</h3>${row('Tracked/caution', esc(`${summary.capital_allocation_quality_counts?.tracked || 0}/${summary.capital_allocation_quality_counts?.caution || 0}`))}${row('Bank manual review', esc(summary.capital_allocation_quality_counts?.bank_manual_review || 0))}${row('Manual review', esc(summary.capital_allocation_quality_counts?.manual_review_required || 0))}${row('No action authority', 'True')}</div>`,
      `<div class="card"><h3>Trust Gate</h3>${row('SEC matched', esc(sec.matched || 0))}${row('SEC conflicts', esc(sec.conflict || 0))}${row('IR packets', esc(irPackets.packets || 0))}${row('Manual required', esc(irPackets.manual_required || 0))}${row('Authority', esc(authority.deployment_authority_allowed ? 'BROKEN' : 'Review-only'))}</div>`,
    ].join('');
  }
  if (!$('fundamentalTable')) return;
  $('fundamentalTable').innerHTML = rows.map(r => {
    const anomalyNotes = (r.capitalAllocationAnomalies || []).map(a => a.message || a.code).filter(Boolean);
    const notes = anomalyNotes.join('; ') || (r.notes || []).join('; ') || (r.secStatus === 'conflict' ? 'SEC conflict: manual review required' : '—');
    const irLink = r.earningsUrl ? `<a href="${esc(r.earningsUrl)}" target="_blank" rel="noopener">IR source</a>` : '—';
    return `<tr>
      <td><strong>${esc(r.ticker)}</strong><div class="small muted">${esc(r.sector || '—')}</div></td>
      <td>${pill(r.quality || 'unknown', r.quality === 'clean' ? 'ok' : (r.quality === 'partial' ? 'warn' : 'info'))}</td>
      <td>${pill(r.secStatus || 'unknown', r.secStatus === 'matched' ? 'ok' : (r.secStatus === 'conflict' ? 'bad' : 'warn'))}</td>
      <td>${pill(r.irPacketStatus || r.irStatus || 'manual_required', 'warn')}<div class="small muted">adj EPS: ${esc(r.adjustedEpsStatus || 'manual_required')} · guidance: ${esc(r.guidanceStatus || 'manual_required')} · bridge: ${esc(r.officialEarningsBridgeStatus || 'manual_required')} · ${irLink}</div></td>
      <td>${esc(r.period || '—')}</td>
      <td class="${toneClass(r.tone)}">${fmtTrendPct(r.epsYoY)}</td>
      <td>${fmtTrendPct(r.dilutedSharesYoY)}<div class="small muted">buyback yield ${fmtTrendPct(r.buybackYield)}</div></td>
      <td>${fmtFcfPerShareYoY(r)}<div class="small muted">FCF/sh ${r.fcfInterpretation === 'bank_structural' ? 'bank structural' : esc(r.fcfPerShare ?? '—')} · SBC/FCF ${fmtFcfMetric(r, r.sbcPctFcf)}</div></td>
      <td class="${toneClass(r.tone)}">${fmtTrendPct(r.revenueYoY)}</td>
      <td class="${toneClass(r.tone)}">${fmtTrendPct(r.netIncomeYoY)}</td>
      <td>${fmtTrendPct(r.operatingMargin)}<div class="small muted">capital allocation: ${esc(r.capitalAllocationQuality || 'unknown')} · return/FCF ${fmtFcfMetric(r, r.capitalReturnToFcf)} · ROIC proxy ${fmtTrendPct(r.roicProxy)}</div></td>
      <td><span class="small">${esc(notes)}</span>${fmtBankNative(r)}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="12" class="muted">No fundamental metrics artifact found.</td></tr>';
}
