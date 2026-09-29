// Frontend view helpers only. This schema is for exported replay files, not an API contract.
export function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
export function validateReplay(data) {
  if (!data || !Array.isArray(data.runs) || !data.runs.length || !data.plots) throw new Error('The saved event is incomplete.');
  for (const run of data.runs) {
    if (run.execution_source !== 'saved_run' || run.recorded_state !== 'completed') throw new Error('This is not a completed saved run.');
    if (run.report.event_id !== data.id) throw new Error('The saved run belongs to a different event.');
    const refs = new Set(run.report.evidence.map(e => e.ref));
    for (const finding of run.report.findings) {
      if (!finding.tool_result_refs.every(ref => refs.has(ref))) throw new Error('A finding refers to missing evidence.');
    }
  }
  return data;
}
export function plotPath(points, x, y, step = false) {
  let path = '', open = false;
  for (const [t,v] of points) {
    if (v === null || !Number.isFinite(v)) { open = false; continue; }
    const xy = `${x(t).toFixed(2)},${y(v).toFixed(2)}`;
    path += open ? (step ? `H${x(t).toFixed(2)}V${y(v).toFixed(2)}` : `L${xy}`) : `M${xy}`;
    open = true;
  }
  return path;
}
export const pretty = value => String(value).replaceAll('_',' ');
const ROLE_SOURCE_LABEL = {local_data: 'Local data', assigned: 'Assigned by orchestrator'};
// Grid node report: one card per instrument. role_source is shown as text + class, never colour alone.
export function nodeReportCard(e) {
  const cls = e.role_source === 'local_data' ? 'role-local' : 'role-assigned';
  const label = ROLE_SOURCE_LABEL[e.role_source] || pretty(e.role_source);
  return `<div class="node-card ${cls}"><h3>${escapeHTML(pretty(e.instrument))}</h3>` +
    `<p><span class="role-badge ${cls}">${escapeHTML(label)}</span> <span class="status-tag">${escapeHTML(pretty(e.assessment))}</span></p>` +
    `<p>${escapeHTML(e.observation)}</p>` +
    `<p class="node-bytes small muted"><span>Payload sent: ${Number(e.payload_bytes)} bytes</span> <span>Raw held: ${Number(e.raw_bytes_held)} bytes</span></p></div>`;
}
export function dataSharedHeadline(e) {
  const pct = Number(e.percent_shared);
  return `<div class="data-shared-headline"><strong>${pct.toFixed(1)}%</strong> <span>of raw data shared</span></div>`;
}
const kb = n => `${(Number(n) / 1024).toFixed(1)} KB`;
// 'deterministic combine' when the backend fell back from the model final (grid_workflow data_limitations).
export function finalSource(final) {
  return (final?.data_limitations || []).some(l => /model final was not accepted|No model was called/.test(l)) ? 'deterministic combine' : 'model';
}
const DIMENSIONS = [['beam_disturbance', 'Beam disturbance corroborated?'], ['unique_cause', 'Unique cause established?']];
// Chat-style transcript of a grid run: human question, orchestrator delegations, node replies, final verdict.
// `report` is omitted until the run is complete; the verdict is only shown from an accepted report.
export function conversationHTML(events, {question = '', report = null, eventId = ''} = {}) {
  const msg = (who, body, cls) => `<li class="chat-msg ${cls}"><p class="chat-who">${escapeHTML(who)}</p>${body}</li>`;
  const out = [msg('You', question ? `<p>${escapeHTML(question)}</p>` :
    `<p>Investigate event ${escapeHTML(eventId || events.find(e => e.event_id)?.event_id || '')}.</p><p class="small muted">The question text was not saved with this run.</p>`, 'chat-human')];
  for (const e of events) {
    if (e.kind === 'delegation' && e.instrument) out.push(msg(`Orchestrator → ${pretty(e.instrument).toUpperCase()} node`,
      `<p>${escapeHTML(e.question || e.task || `Run the ${pretty(e.instrument)} checks.`)}</p><p class="small muted">Node <span class="code">${escapeHTML(e.node_id)}</span></p>`, 'chat-orchestrator'));
    else if (e.kind === 'node_report') out.push(msg(`${pretty(e.instrument).toUpperCase()} node`,
      `<p><span class="status-tag">${escapeHTML(pretty(e.assessment))}</span> <span class="small muted">${escapeHTML(ROLE_SOURCE_LABEL[e.role_source] || pretty(e.role_source))}</span></p><p>${escapeHTML(e.observation)}</p><p class="small muted">Sent ${kb(e.payload_bytes)}, holds ${kb(e.raw_bytes_held)}</p>`, 'chat-node'));
  }
  if (report?.final) {
    const f = report.final, shared = report.data_shared;
    out.push(msg(`Orchestrator · final (${finalSource(f)})`,
      `<dl class="chat-verdict">${DIMENSIONS.filter(([k]) => f[k]).map(([k, title]) => `<dt>${title}</dt><dd><strong>${escapeHTML(pretty(f[k].status))}</strong> · ${escapeHTML(f[k].rationale)}</dd>`).join('')}</dl>` +
      (shared ? `<p class="small muted">${Number(shared.percent_shared).toFixed(1)}% of raw data shared</p>` : ''), 'chat-orchestrator chat-final'));
  }
  return `<ol class="chat" aria-label="Conversation between the operator and the agents">${out.join('')}</ol>`;
}
