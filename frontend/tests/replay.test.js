import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {validateReplay,plotPath,escapeHTML} from '../assets/replay.js';
const read=id=>JSON.parse(fs.readFileSync(new URL(`../data/${id}.json`,import.meta.url)));
test('historical runs preserve explicit origin, evidence links and distinct follow-up',()=>{
 const event=validateReplay(read('slac-001'));
 assert.equal(event.runs.length,2);
 assert.equal(event.runs[0].series_id,event.runs[1].series_id);
 assert.equal(event.runs[1].phase,'followup');
 assert.match(event.runs[1].question,/low charge/);
 assert.equal(typeof event.time_origin_ns,'string');
 assert.equal(typeof event.runs[0].report.final.time_interval_ns[0],'string');
});
test('slac-003 replay preserves the model-label mismatch and the review warning',()=>{
 const event=validateReplay(read('slac-003'));
 assert.equal(event.runs[0].report.final.assessment,'corroborated');
 assert.match(event.runs[0].review.overall,/not supported/);
 assert.equal(event.runs[0].report.evidence.find(e=>e.analysis==='beam').result.disturbance_detected,false);
});
test('no line bridges invalid low-charge position samples',()=>{
 assert.equal(plotPath([[0,1],[1,null],[2,3]],x=>x,y=>y),'M0.00,1.00M2.00,3.00');
 const event=read('slac-001');
 const p=event.plots.beam.find(x=>x.channel==='BPMS:DMPH:502:Y');
 assert.equal(p.points.filter(x=>x[1]===null).length,300);
});
test('unknown evidence and non-replay origin fail closed',()=>{
 const bad=read('slac-001');bad.runs[0].report.findings[0].tool_result_refs=['T-made-up'];
 assert.throws(()=>validateReplay(bad),/missing evidence/);
 const live=read('slac-001');live.runs[0].execution_source='live';
 assert.throws(()=>validateReplay(live),/saved run/);
});
test('all model prose is escaped before HTML rendering',()=>{
 assert.equal(escapeHTML('<img onerror="oops"> &'), '&lt;img onerror=&quot;oops&quot;&gt; &amp;');
});
