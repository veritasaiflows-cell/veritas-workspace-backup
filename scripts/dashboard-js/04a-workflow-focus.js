// ── Workflow focus (WF63 readiness) ──────────────────────────────────────────
// Two surfaces:
//   #workflowFocusRibbon  — compact governance strip at the top of Overview.
//   #workflowFocusDetail  — full authority/stop-line panel placed below the
//                           decision/action content so it never displaces the
//                           primary deployment surface.

function _wfStatusTone(top) {
  const paperBlocked = top.paper_submit_allowed === false && top.live_submit_allowed === false;
  return paperBlocked ? 'warn' : 'bad';
}

function _wfRibbon(top) {
  const tone = _wfStatusTone(top);
  const statusLabelText = top.paper_trading_status || '—';
  // Always-on stop chips — the three most load-bearing for trust posture.
  const chips = ['No API calls', 'No order submit', 'No credentials']
    .map(t => `<span class="pill bad" style="text-transform:none;letter-spacing:0;font-size:10px;font-weight:600;margin:0">${esc(t)}</span>`).join(' ');
  // Short next-gate phrase. Trim verbose owner-decision prose so the strip
  // stays single-line on a 1080p screen.
  let gate = top.next_approval_gate || '—';
  gate = gate.replace(/^Approve or deny\s*/i, '');
  if (gate.length > 110) gate = gate.slice(0, 107) + '…';
  return `
    <div class="card" style="padding:8px 14px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;border-left:3px solid var(--${tone});border-radius:10px">
      <div style="display:flex;align-items:center;gap:8px;min-width:0">
        <span class="tiny">Top WF</span>
        <strong style="font-size:13px">${esc(top.id)}: ${esc(top.title || '')}</strong>
      </div>
      <div>${pill(statusLabelText, tone)}</div>
      <div style="display:flex;gap:6px;flex-wrap:wrap">${chips}</div>
      <div class="small muted" style="flex:1;min-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(top.next_approval_gate || '')}">Next gate: ${esc(gate)}</div>
      <a href="#workflowFocusDetail" onclick="document.getElementById('workflowFocusDetail').scrollIntoView({behavior:'smooth',block:'start'});return false;" class="small" style="color:var(--info);text-decoration:none;white-space:nowrap">Details ↓</a>
    </div>
  `;
}

function _wfDetailPanel(wf, top) {
  const authority = top.authority || {};
  const authorityRows = [
    ['Readiness design', authority.readiness_design_allowed === true],
    ['Read-only paper connection', authority.read_only_connection_allowed === true],
    ['Order-preview generation', authority.order_preview_generation_allowed === true],
    ['Shadow mode', authority.shadow_mode_allowed === true],
    ['OpenClaw paper-order submit', authority.openclaw_paper_submit_allowed === true],
    ['Live order submit', authority.live_submit_allowed === true],
    ['Trade or account action', authority.trade_or_account_action_allowed === true],
    ['Money movement', authority.money_movement_allowed === true],
    ['Credential handling approved', authority.credential_handling_approved === true],
    ['Config or auth mutation', authority.config_or_auth_mutation_allowed === true],
  ];
  const authorityHtml = authorityRows.map(([label, allowed]) => {
    const tone = allowed ? 'warn' : 'ok';
    const text = allowed ? 'allowed' : 'blocked';
    return `<div class="row" style="padding:6px 0"><div class="small">${esc(label)}</div><div>${pill(text, tone)}</div></div>`;
  }).join('');

  const stopLines = (top.stop_lines || []).map(line =>
    `<li class="small">${esc(line)}</li>`
  ).join('');
  const proofItems = (top.proof_artifacts || []).map(artifact =>
    `<li class="small mono">${esc(artifact)}</li>`
  ).join('');
  const monitorRows = (wf.monitors || []).map(m => {
    const tag = m.brokerage_authority === false
      ? pill('not brokerage authority', 'ok')
      : pill('verify authority', 'warn');
    return `<div class="row" style="padding:6px 0">
      <div>
        <strong>${esc(m.id)}</strong> — ${esc(m.title || '')}
        <div class="small">${esc(m.status || '')}</div>
        ${m.role ? `<div class="small muted">${esc(m.role)}</div>` : ''}
      </div>
      <div style="text-align:right">${tag}</div>
    </div>`;
  }).join('') || '<div class="small muted">No monitor lanes recorded.</div>';

  const tone = _wfStatusTone(top);
  return `
    <div class="card" style="border-left:3px solid var(--${tone})">
      <div class="row" style="padding-top:0;border-bottom:none">
        <div>
          <div class="tiny">Workflow governance detail</div>
          <div style="font-size:15px;font-weight:700;margin-top:2px">${esc(top.id)} — ${esc(top.title || '')}</div>
          <div class="small" style="margin-top:2px">${esc(top.phase_label || top.phase_key || '—')}</div>
          <div class="small muted">${esc(top.status_label || '—')}</div>
        </div>
        <div style="text-align:right">
          ${pill(top.paper_trading_status || '—', tone)}
          <div class="small" style="margin-top:6px">${esc(top.readiness_report_status || '—')}</div>
        </div>
      </div>
      <div class="grid cols-2" style="margin-top:12px;gap:14px">
        <div>
          <div class="tiny" style="margin-bottom:6px">Next approval gate</div>
          <div class="small">${esc(top.next_approval_gate || '—')}</div>
          <div class="tiny" style="margin:12px 0 6px">Readiness verdict</div>
          <div class="small">${esc(top.readiness_verdict || '—')}</div>
          ${top.required_endpoint ? `<div class="tiny" style="margin:12px 0 6px">Required endpoint</div><div class="small mono">${esc(top.required_endpoint)}</div>` : ''}
          ${top.forbidden_endpoint ? `<div class="tiny" style="margin:6px 0 6px">Forbidden endpoint</div><div class="small mono">${esc(top.forbidden_endpoint)}</div>` : ''}
        </div>
        <div>
          <div class="tiny" style="margin-bottom:6px">Stop lines (active under current phase)</div>
          <ul style="margin:0;padding-left:18px">${stopLines}</ul>
        </div>
      </div>
      <div class="grid cols-2" style="margin-top:14px;gap:14px">
        <div>
          <div class="tiny" style="margin-bottom:6px">Current authority snapshot</div>
          <div class="list">${authorityHtml}</div>
        </div>
        <div>
          <div class="tiny" style="margin-bottom:6px">Proof artifacts</div>
          <ul style="margin:0;padding-left:18px">${proofItems}</ul>
          <div class="tiny" style="margin:12px 0 6px">Other active workflows (monitors)</div>
          <div class="list">${monitorRows}</div>
        </div>
      </div>
    </div>
  `;
}

function renderWorkflowFocus() {
  const wf = DATA.workflow_focus || {};
  const top = wf.top_workflow || {};
  const ribbon = $('workflowFocusRibbon');
  const detail = $('workflowFocusDetail');
  if (!top.id) {
    if (ribbon) ribbon.innerHTML = '';
    if (detail) detail.innerHTML = '';
    return;
  }
  if (ribbon) ribbon.innerHTML = _wfRibbon(top);
  if (detail) detail.innerHTML = _wfDetailPanel(wf, top);
}
