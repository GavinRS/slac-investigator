import test from 'node:test';
import assert from 'node:assert/strict';
import {ACTIVITY_KINDS,sharingHeadline,sharingHTML,verdictHTML} from '../assets/replay.js';

test('Grid bridge includes node and sharing events',()=>{
 assert.ok(ACTIVITY_KINDS.includes('node_report'));
 assert.ok(ACTIVITY_KINDS.includes('data_shared'));
});
test('sharing distinguishes summary size, incomplete accounting, fallback and baseline',()=>{
 const r={mode:'grid',grid:{fallback:true},data_shared:{percent_shared:0.25,raw_samples_shared:0,complete:true}};
 assert.match(sharingHeadline(r),/0.250%.*Raw samples shared: 0.*not raw-sample disclosure.*Local fallback/);
 r.data_shared.complete=false;
 assert.match(sharingHeadline(r),/Summary \/ raw bytes: unavailable/);
 assert.match(sharingHeadline({mode:'baseline'}),/100% \(conceptual/);
 assert.equal(sharingHTML({}), '');
});
test('new saved findings show both verdicts and safely escape model rationale',()=>{
 const html=verdictHTML({beam_disturbance:{status:'corroborated',rationale:'<script>unsafe</script>'},unique_cause:{status:'not_established',rationale:'No causal proof'}});
 assert.match(html,/Beam disturbance corroborated/);
 assert.match(html,/not established/);
 assert.match(html,/&lt;script&gt;/);
 assert.doesNotMatch(html,/Not assessed in legacy/);
 assert.match(verdictHTML({assessment:'corroborated'}),/Not assessed in legacy/);
});

test('actual Grid evidence entries without intervals open as node summaries',async()=>{
 const {evidenceDetails}=await import('../assets/replay.js');
 const item={ref:'T-rf',kind:'node_summary',event_id:'slac-001',instrument:'rf',result:{peak_deviation:0.1}};
 const reports=[{evidence:[item],node_reports:[{instrument:'rf',tool_refs:['T-rf']}]}];
 const detail=evidenceDetails(reports,'T-rf');
 assert.equal(detail.title,'T-rf · rf summary');
 assert.match(detail.note,/raw samples are not included/);
 assert.equal(detail.evidence,item);
 assert.equal(evidenceDetails(reports,'T-missing'),null);
 const legacy={ref:'T-old',event_id:'slac-001',analysis:'beam',interval_ns:['1','2']};
 assert.match(evidenceDetails([{evidence:[legacy]}],'T-old').note,/1 → 2/);
 const noInterval={ref:'T-no-time',analysis:'quality'};
 assert.match(evidenceDetails([{evidence:[noInterval]}],'T-no-time').note,/Interval not recorded/);
});
