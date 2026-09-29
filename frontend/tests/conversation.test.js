// Synthetic fixture only — hand-written, not a recorded Flower run.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {conversationHTML, finalSource} from '../assets/replay.js';
import {InvestigationAPI} from '../assets/api.js';

const events = [
  {kind:'started', event_id:'synthetic-1', mode:'grid', model:'m'},
  {kind:'delegation', agent:'orchestrator', node_id:'42', instrument:'rf', question:'Run the rf checks <b>locally</b>.'},
  {kind:'tool_request', agent:'rf', analysis:'equipment'},
  {kind:'node_report', instrument:'rf', role_source:'local_data', assessment:'suspicious', observation:'RF dipped.', payload_bytes:2048, raw_bytes_held:204800},
];
const report = {data_shared:{percent_shared:0.905}, final:{data_limitations:[],
  beam_disturbance:{status:'corroborated', rationale:'Beam moved.', tool_result_refs:[]},
  unique_cause:{status:'not_established', rationale:'RF data sparse.', tool_result_refs:[]}}};

test('transcript reads human -> orchestrator -> node -> verdict, in order', () => {
  const html = conversationHTML(events, {question:'Was the beam disturbed?', report});
  const order = ['>You<', 'Orchestrator → RF node', 'RF node<', 'Orchestrator · final (model)'].map(s => html.indexOf(s));
  assert.ok(order.every((v, i) => v >= 0 && (i === 0 || v > order[i - 1])), html);
  assert.match(html, /Sent 2\.0 KB, holds 200\.0 KB/);
  assert.match(html, /corroborated<\/strong> · Beam moved\./);
  assert.match(html, /not established<\/strong> · RF data sparse\./);
  assert.match(html, /0\.9% of raw data shared/);
  assert.match(html, /Local data/);
  assert.doesNotMatch(html, /<b>/, 'agent text is escaped');
  assert.doesNotMatch(html, /equipment/, 'tool chatter stays in the activity feed');
});

test('no verdict before the report; missing question is labelled, not invented', () => {
  const html = conversationHTML(events.slice(0, 2), {eventId:'synthetic-1'});
  assert.doesNotMatch(html, /final/);
  assert.match(html, /question text was not saved/);
});

test('deterministic fallback is labelled', () => {
  assert.equal(finalSource({data_limitations:['Deterministic combine of node summaries; the model final was not accepted.']}), 'deterministic combine');
  assert.equal(finalSource(report.final), 'model');
});

test('exported grid replay keeps the events the transcript needs', () => {
  const data = JSON.parse(fs.readFileSync(new URL('../data/slac-001-grid.json', import.meta.url)));
  const run = data.runs[0], kinds = new Set(run.events.map(e => e.kind));
  for (const k of ['delegation', 'node_report', 'data_shared']) assert.ok(kinds.has(k), k);
  assert.equal(finalSource(run.report.final), 'model');
  assert.equal(run.report.mode, 'grid');
  assert.ok(run.report.final.beam_disturbance && run.report.data_shared);
});

test('grid start sends the question; default body is unchanged', async () => {
  const calls = [];
  const api = new InvestigationAPI({pageOrigin:'http://127.0.0.1:5173', fetchImpl:async (url, options) => {calls.push(options); return {ok:true, json:async () => ({id:'x'})};}});
  await api.start('slac-001', {mode:'grid', question:'  Why?  '});
  await api.start('slac-001');
  assert.deepEqual(JSON.parse(calls[0].body), {event_id:'slac-001', mode:'grid', question:'Why?'});
  assert.deepEqual(JSON.parse(calls[1].body), {event_id:'slac-001', mode:'collaborative'});
});
