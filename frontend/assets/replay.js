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
