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
