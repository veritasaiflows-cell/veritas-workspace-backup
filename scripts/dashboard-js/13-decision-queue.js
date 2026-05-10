// ── Decision Queue / Daily Intelligence ──────────────────────────────────────

function renderQueueItem(item) {
  const evidence = (item.evidence || []).length
    ? `<ul class="watch-list">${item.evidence.map(e => `<li>${esc(e)}</li>`).join('')}</ul>`
    : '';
  const score = item.score != null ? pill(`score ${item.score}`, 'info') : '';
  const rank = item.rank != null ? pill(`#${item.rank}`, 'info') : '';
  return `<div class="dq-item">
    <div class="dq-item-head">
      <div><span class="mono dq-ticker">${esc(item.ticker)}</span> ${rank} ${score}</div>
      <div>${pill(item.route || 'owner_review', 'warn')} ${pill(item.urgency || 'review', 'info')}</div>
    </div>
    <div class="dq-title">${esc(item.title)}</div>
    <div class="small" style="margin-top:6px">${esc(item.next_step)}</div>
    ${item.owner_question ? `<div class="dq-question">${esc(item.owner_question)}</div>` : ''}
    ${evidence}
  </div>`;
}

function renderCountRow(label, value, tone='info') {
  return row(`<strong>${esc(label)}</strong>`, pill(value ?? 0, tone));
}

function renderDecisionQueue() {
  const queue = DATA.decision_queue || {};
  const daily = queue.daily_review || DATA.daily_review || {};
  const intel = queue.market_intelligence || DATA.market_intelligence || {};
  const authority = queue.authority || {};
  const dailyCounts = daily.counts || {};
  const intelCounts = intel.counts || {};

  $('decisionQueueHeader').innerHTML = `<div class="card" style="padding:12px;border-left:3px solid var(--warn)">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap">
      <div>
        <strong>Daily Intelligence / Decision Queue</strong>
        <div class="small">Window: ${esc(queue.window || 'post-close')} · Daily review: ${esc(daily.generated_at_utc || 'missing')} · Market intelligence: ${esc(intel.generated_at_utc || 'missing')}</div>
      </div>
      <div>${pill('review-only', 'warn')} ${pill('owner approval required', 'bad')}</div>
    </div>
    <div class="small" style="margin-top:8px">${esc(authority.language || 'Review-only queue. Owner approval is required before canonical, portfolio, deployment-state, or trade action.')}</div>
  </div>`;

  $('dailyReviewQueue').innerHTML = [
    renderCountRow('Review objects', dailyCounts.review_object_count, 'info'),
    renderCountRow('Escalations', dailyCounts.escalated_count, dailyCounts.escalated_count ? 'warn' : 'ok'),
    renderCountRow('Capital recommendations', dailyCounts.capital_recommendation_count, dailyCounts.capital_recommendation_count ? 'warn' : 'info'),
  ].join('') + `<div class="dq-list">${(daily.escalations || []).map(renderQueueItem).join('') || '<div class="small muted">No daily review escalations surfaced.</div>'}</div>`;

  $('marketIntelligenceQueue').innerHTML = [
    renderCountRow('Events', intelCounts.event_count, 'info'),
    renderCountRow('Escalations', intelCounts.escalated_count, intelCounts.escalated_count ? 'warn' : 'ok'),
    row('<strong>Top routes</strong>', `<span class="small">${esc((intelCounts.top_routes || []).join(' · ') || '—')}</span>`),
    row('<strong>Top tickers / sleeves</strong>', `<span class="small mono">${esc((intelCounts.top_tickers_or_sleeves || []).join(' · ') || '—')}</span>`),
  ].join('') + `<div class="dq-list">${(intel.escalations || []).map(renderQueueItem).join('') || '<div class="small muted">No market-intelligence escalations surfaced.</div>'}</div>`;

  const portfolioCall = daily.portfolio_call || {};
  const recs = daily.capital_recommendations || [];
  $('capitalRecommendationQueue').innerHTML = `<div class="alert warn"><div>!</div><div><strong>Capital action remains owner-gated</strong><div class="small">${esc(portfolioCall.reason || authority.language || 'No capital action is approved by this generated queue.')}</div></div></div>` +
    (recs.length ? `<div class="dq-list">${recs.map(renderQueueItem).join('')}</div>` : '<div class="small muted">No capital recommendations surfaced.</div>');
}
