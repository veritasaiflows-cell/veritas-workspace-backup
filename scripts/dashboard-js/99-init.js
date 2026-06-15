// ── Init ──────────────────────────────────────────────────────────────────────

function init() {
  renderNav();
  renderShortcutList();

  const execTone = toneMap[DATA.exec_freshness] || 'warn';
  $('execBanner').className = `exec-banner ${execTone}`;
  $('execBanner').textContent = `${statusLabel[DATA.exec_freshness]||DATA.exec_freshness}: ${DATA.trust.summary}`;
  $('headerBadges').innerHTML = `${pill(DATA.trust.overall_label, execTone)} ${pill(DATA.portfolio?.posture||'No posture','info')}`;

  const session = DATA.market_session || 'unknown';
  const sessionTone = session === 'open' ? 'ok' : (session === 'pre_open' ? 'warn' : 'info');
  $('sessionPill').innerHTML = pill(session.replaceAll('_',' '), sessionTone);

  $('headerMeta').textContent = `Generated ${DATA.generated_at} · Data as of ${DATA.last_trade_date}`;
  $('footer').textContent = `Generated ${DATA.generated_at} from governed tmp artifacts. Trust follows upstream status, not visual polish.`;

  renderEarningsBar();
  renderAlerts();
  renderTrust();
  renderVaultFreshness();
  renderValidation();
  renderWorkflowFocus();
  renderDeploymentStrip();
  renderTodayAction();
  renderOverviewCards();
  renderDeploymentOverview();
  renderManualDependencies();
  renderDeployFilterBar();
  renderDeploymentTable();
  renderTechnicalFilterBar();
  renderTechnicalTable();
  renderPortfolio();
  renderFundamentals();
  renderEarnings();
  renderMacro();
  renderRisk();
  renderTriggerSheet();
  renderDecisionQueue();
  renderPostEarnings();
  renderEntryBands();

  updateAgeCounter();
  setInterval(updateAgeCounter, 10000);
}

document.addEventListener('DOMContentLoaded', init);
