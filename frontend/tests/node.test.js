// Synthetic fixture only — hand-written, not a recorded Flower run. Never mirror this shape into frontend/data/.
import test from 'node:test';
import assert from 'node:assert/strict';
import {nodeReportCard, dataSharedHeadline} from '../assets/replay.js';

const SYNTHETIC_NODE_REPORTS = [
  {kind:'node_report', instrument:'rf', role_source:'local_data', event_id:'synthetic-grid-test',
    assessment:'suspicious', observation:'RF amplitude dipped <script>alert(1)</script> before the candidate window.',
    summary:{baseline:1.02, peak_deviation:0.31}, tool_refs:['T-synthetic-rf'],
    raw_bytes_held:48213, payload_bytes:412, limitations:['Synthetic test data, not a real reading.']},
  {kind:'node_report', instrument:'ltu', role_source:'assigned', event_id:'synthetic-grid-test',
    assessment:'normal', observation:'BPM readings stayed within the historical envelope.',
    summary:{baseline:0.4, peak_deviation:0.02}, tool_refs:['T-synthetic-ltu'],
    raw_bytes_held:91007, payload_bytes:388, limitations:['Synthetic test data, not a real reading.']},
];
const SYNTHETIC_DATA_SHARED = {kind:'data_shared', raw_bytes_held:139220, payload_bytes:800, percent_shared:0.5747};

test('node_report renders one card per instrument with the fields the spec requires', () => {
  for (const report of SYNTHETIC_NODE_REPORTS) {
    const html = nodeReportCard(report);
    assert.match(html, /<h3>/, 'instrument name uses a real heading, not a styled div');
    assert.match(html, new RegExp(report.instrument));
    assert.match(html, new RegExp(pretty_re(report.assessment)));
    assert.match(html, /RF amplitude dipped|BPM readings stayed/);
    assert.match(html, new RegExp(String(report.payload_bytes)));
    assert.match(html, new RegExp(String(report.raw_bytes_held)));
  }
});

test('role_source is visibly distinct by text and class, not colour alone', () => {
  const local = nodeReportCard(SYNTHETIC_NODE_REPORTS[0]);
  const assigned = nodeReportCard(SYNTHETIC_NODE_REPORTS[1]);
  assert.match(local, /role-local/);
  assert.match(local, /Local data/);
  assert.match(assigned, /role-assigned/);
  assert.match(assigned, /Assigned by orchestrator/);
  assert.notEqual(local.match(/role-badge[^<]*>([^<]*)</)[1], assigned.match(/role-badge[^<]*>([^<]*)</)[1]);
});

test('node_report observation text is escaped, never raw HTML', () => {
  const html = nodeReportCard(SYNTHETIC_NODE_REPORTS[0]);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&lt;script&gt;/);
});

test('data_shared headline is the % raw data shared, formatted to one decimal', () => {
  // percent_shared is already payload_bytes/raw_bytes_held*100 (800/139220*100 ≈ 0.57), not a 0–1 fraction.
  const html = dataSharedHeadline(SYNTHETIC_DATA_SHARED);
  assert.match(html, /0\.6%/);
  assert.match(html, /raw data shared/);
});

function pretty_re(value) { return String(value).replaceAll('_', ' '); }
