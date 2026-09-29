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
    for (const node of run.report.node_reports || []) for (const ref of node.tool_refs || []) refs.add(ref);
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

// Small compatibility bridge for Grid reports; the full instrument UI is separate work.
export const ACTIVITY_KINDS = ['started','delegation','tool_request','tool_result','finding','finding_rejected','node_report','data_shared','failed'];
export function sharingHeadline(report) {
  if (report.mode === 'baseline') return 'Centralized data access: 100% (conceptual; not raw arrays sent to the model).';
  const shared = report.data_shared;
  if (!shared) return '';
  const percent = shared.complete !== false && Number.isFinite(shared.percent_shared) ? `${shared.percent_shared.toFixed(3)}%` : 'unavailable';
  const fallback = report.grid?.fallback ? ' Local fallback.' : '';
  return `Summary / raw bytes: ${percent}. Raw samples shared: ${shared.raw_samples_shared === 0 ? '0' : 'unavailable'}. This ratio measures summary size, not raw-sample disclosure.${fallback}`;
}
export function sharingHTML(report) {
  const headline = sharingHeadline(report);
  return headline ? `<p class="small muted" data-sharing-headline>${escapeHTML(headline)}</p>` : '';
}
export function verdictHTML(final) {
  if (!final.beam_disturbance || !final.unique_cause) return '<div class="dimension-grid legacy"><div><strong>Beam disturbance corroborated?</strong><span>Not assessed in legacy schema</span></div><div><strong>Unique cause established?</strong><span>Not assessed in legacy schema</span></div></div><p class="small muted">Legacy mixed-scope output; requires review. The original mixed-scope label is not mapped to either question.</p>';
  return `<div class="dimension-grid">${[['beam_disturbance','Beam disturbance corroborated?'],['unique_cause','Unique cause established?']].map(([key,title])=>`<div><strong>${title}</strong><span>${escapeHTML(pretty(final[key].status))}</span><p>${escapeHTML(final[key].rationale)}</p></div>`).join('')}</div>`;
}

export function evidenceDetails(reports, ref) {
  const found = reports.flatMap(report=>report.evidence||[]).find(item=>item.ref===ref);
  const node = reports.flatMap(report=>report.node_reports||[]).find(item=>(item.tool_refs||[]).includes(ref));
  if (!found && !node) return null;
  if (found?.kind === 'node_summary' || !found) {
    return {title:`${ref} · ${found?.instrument || node?.instrument || 'instrument'} summary`,
      note:'Recorded node summary; raw samples are not included.', evidence:found||node};
  }
  const interval = Array.isArray(found.interval_ns) ? `Original interval (Unix nanoseconds): ${found.interval_ns.join(' → ')}` : 'Interval not recorded in this evidence entry.';
  return {title:`${ref} · ${pretty(found.analysis || found.kind || 'evidence')}`,
    note:`${found.event_id || ''} · ${interval}`, evidence:found};
}
