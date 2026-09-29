"""Python-owned Flower Grid routing with summary-only model reconciliation."""
from __future__ import annotations
import json
import re
import time
from .data import ROOT, event_ids
from .instruments import INSTRUMENTS
from .node_agent import ModelBudget, grid_call, run_node, validate_node_report
from .tools import serialize_node_report
from .workflow import Finding, RULES, MAX_OUTPUT_TOKENS

class GridInvestigation:
    def __init__(self,event_id,emit,grid,client=None,model='flwrlabs/endeavor-1.0',mode='collaborative',timeout=120):
        if event_id not in event_ids(): raise ValueError('Unknown event')
        if mode not in ('collaborative','smoke'): raise ValueError('Invalid Grid mode')
        if not 0<=float(timeout)<=300: raise ValueError('Node timeout must be between 0 and 300 seconds')
        self.event_id=event_id; self.emit=emit; self.grid=grid; self.client=client; self.model=model; self.mode=mode; self.timeout=float(timeout)
        # Metadata only: the orchestrator never loads raw event arrays.
        self.meta=json.loads((ROOT/'data/events'/f'{event_id}.json').read_text())
        self.reports=[]; self.findings=[]; self.limitations=[]; self.assignments={}; self.failed=False
        self.budget=ModelBudget(max_calls=4,max_input_chars=100000)
        self.started=time.perf_counter()

    def publish(self,kind,**data): self.emit(dict(kind=kind,**data))

    def collect(self,instruments,question):
        tasks=[dict(kind='node_task',event_id=self.event_id,instrument=i,mode=self.mode,question=question,model=self.model,provider=getattr(self.client,'provider','flower')) for i in instruments]
        for task in tasks:
            self.publish('delegation',agent='lead',to=task['instrument'],question=question,analysis='node_summary')
        if not self.assignments:
            results=[]
            for task in tasks:
                results.append(run_node(task,self.client,self.model))
        else:
            messages=[dict(dst_node_id=self.assignments[t['instrument']],payload=json.dumps(t),reply_to_message_id=None) for t in tasks]
            pushed=grid_call(self.grid,'push_messages',{'messages':messages}).get('results',[])
            if len(pushed)!=len(tasks): raise RuntimeError('Grid returned incorrect push result count')
            expected={}; results=[]
            for task,result in zip(tasks,pushed):
                mid=result.get('message_id')
                if result.get('error') or not mid:
                    self.limitations.append(f"{task['instrument']}: Grid rejected task"); self.failed=True
                elif mid in expected: raise ValueError('Duplicate Grid message ID')
                else: expected[mid]=task['instrument']
            if expected:
                pulled=grid_call(self.grid,'pull_messages',dict(message_ids=list(expected),timeout=self.timeout))
                seen=set()
                for message in pulled.get('messages',[]):
                    mid=message.get('reply_to_message_id')
                    if mid not in expected or mid in seen: raise ValueError('Uncorrelated or duplicate node reply')
                    seen.add(mid); instrument=expected[mid]
                    if str(message.get('src_node_id'))!=self.assignments[instrument]: raise ValueError('Unexpected node reply source')
                    if message.get('error') or not message.get('payload'):
                        self.limitations.append(f'{instrument}: node execution failed'); self.failed=True; continue
                    payload=message['payload']
                    if len(payload.encode())>64000: raise ValueError('Node payload exceeds summary limit')
                    report=validate_node_report(json.loads(payload),self.event_id,instrument)
                    if report['payload_bytes'] != len(payload.encode()): raise ValueError('Node payload byte count mismatch')
                    metrics=report.get('metrics')
                    if self.mode!='smoke' and (not metrics or not 1<=metrics.get('model_calls',0)<=2 or not 0<=metrics.get('input_characters',-1)<=50000):
                        raise ValueError('Invalid node model accounting')
                    results.append(report)
                for mid in expected.keys()-seen:
                    self.limitations.append(f'{expected[mid]}: node reply timed out'); self.failed=True
        for report in results:
            self.reports.append(report)
            self.publish('node_report',report=report)
        return results

    def validate_finding(self,text):
        finding=Finding.model_validate_json(text)
        allowed={ref for report in self.reports for ref in report['tool_refs']}
        if not finding.tool_result_refs or not set(finding.tool_result_refs)<=allowed: raise ValueError('Unavailable final references')
        for assessment in (finding.beam_disturbance,finding.unique_cause):
            if assessment.status=='not_assessed' or not assessment.tool_result_refs or not set(assessment.tool_result_refs)<=set(finding.tool_result_refs):
                raise ValueError('Final dimensions need available evidence references')
        positive_beam_refs={ref for r in self.reports if r['instrument'] in ('ltu','dump')
                            and r['summary'].get('quality_adequate') and r['summary'].get('disturbance_detected')
                            for ref in r['tool_refs']}
        if finding.beam_disturbance.status=='corroborated' and not set(finding.beam_disturbance.tool_result_refs)&positive_beam_refs:
            raise ValueError('Beam corroboration must cite adequate positive beam disturbance evidence')
        if finding.unique_cause.status=='established': raise ValueError('Summary replay cannot establish unique RF cause')
        channels=set(self.meta['channels']['health']+self.meta['channels']['bpm'])
        if not set(finding.source_channels)<=channels: raise ValueError('Unavailable channels')
        if finding.time_interval_ns[0]>finding.time_interval_ns[1]: raise ValueError('Reversed finding interval')
        finding.agent='lead'; finding.finding_id=f'F-{len(self.findings)+1:03d}'
        finding.data_limitations=list(dict.fromkeys(finding.data_limitations+self.limitations))
        return finding.model_dump()

    def onset_alignment(self):
        """Compare recorded aggregate timestamps without correcting device clocks."""
        latest={report['instrument']:report['summary'].get('onset_ns') for report in self.reports}
        onsets={instrument:latest.get(instrument) for instrument in INSTRUMENTS}
        if any(value is not None and type(value) is not int for value in onsets.values()):
            raise ValueError('Recorded onset timestamps must be integer nanoseconds')
        start=self.meta['candidate_start_ns']; end=self.meta['candidate_end_ns']
        pairs={f'{right}_minus_{left}':None if onsets[left] is None or onsets[right] is None else onsets[right]-onsets[left]
               for left,right in (('rf','ltu'),('rf','dump'),('ltu','dump'))}
        return dict(recorded_onset_ns=onsets,relative_to_candidate_start_ns={instrument:None if value is None else value-start for instrument,value in onsets.items()},
            pairwise_difference_ns=pairs,candidate_window_ns=[start,end],
            within_candidate_window={instrument:None if value is None else start<=value<=end for instrument,value in onsets.items()},
            applied_shift_ns=0,caveat='RF timestamps reflect sparse, approximately delayed reporting; no fixed reporting delay or timestamp shift is assumed. Recorded onset coincidence or ordering does not establish a unique RF cause.')

    def reconcile(self,question,prior):
        if not self.reports: raise RuntimeError('No validated node evidence received')
        alignment=self.onset_alignment()
        if self.mode=='smoke':
            known=[within for within in alignment['within_candidate_window'].values() if within is not None]
            timing_observation=(f'{sum(known)} of {len(known)} available recorded instrument onsets fall within the candidate window; no timestamp shifts were applied.' if known else 'No recorded instrument onset is available for timing comparison.')
            beams=[r for r in self.reports if r['instrument'] in ('ltu','dump')]
            status='insufficient_evidence' if len(beams)<2 or any(not r['summary'].get('quality_adequate') for r in beams) else 'corroborated' if any(r['summary'].get('disturbance_detected') for r in beams) else 'not_corroborated'
            refs=list(dict.fromkeys(ref for r in self.reports for ref in r['tool_refs']))
            beam_refs=list(dict.fromkeys(ref for r in beams for ref in r['tool_refs'])) or refs
            final=Finding(finding_id='F-001',agent='lead',observation='Deterministic instrument summaries reconciled; no model was called. '+timing_observation,
                source_channels=[],time_interval_ns=[self.meta['candidate_start_ns'],self.meta['candidate_end_ns']],tool_result_refs=refs,
                supporting_evidence=['Charge-valid beam aggregates assessed separately from RF amplitude.'],conflicting_evidence=[],
                data_limitations=self.limitations+['Smoke harness only; no causal inference.',alignment['caveat']],requested_next_check=None,
                beam_disturbance=dict(status=status,rationale='Deterministic charge-valid beam heuristic.',tool_result_refs=beam_refs),
                unique_cause=dict(status='not_established',rationale='Aggregate coincidence cannot establish unique RF causation.',tool_result_refs=refs)).model_dump()
        else:
            instructions=RULES+'\nYou are the lead. Only aggregate node reports are available. Unique RF cause cannot be established from these summaries. Set requested_next_check only for one useful instrument follow-up; name rf, ltu, or dump. Valid channel catalog: '+json.dumps(self.meta['channels'])
            payload=dict(node_reports=self.reports,question=question,prior_operator_assessment=prior,limitations=self.limitations,
                onset_alignment=alignment,candidate_interval_ns=[self.meta['candidate_start_ns'],self.meta['candidate_end_ns']])
            for attempt in range(2):
                try:
                    final=self.validate_finding(self.budget.request(self.client,self.model,instructions,payload)); break
                except (ValueError,TypeError,KeyError) as exc:
                    if attempt: raise ValueError('Lead finding invalid after one retry') from exc
                    payload['correction']='Return the required Finding schema with exact available references and separate assessments.'
        self.findings.append(final); self.publish('finding',finding=final)
        return final

    def run(self,question='',prior=None):
        if self.mode!='smoke' and self.client is None: raise RuntimeError('Model client required')
        self.publish('started',event_id=self.event_id,mode=self.mode,model=self.model,budget=dict(model_calls=12,total_input_characters=300000,max_output_tokens_per_call=MAX_OUTPUT_TOKENS))
        nodes=grid_call(self.grid,'get_nodes',{'sample_size':None})['nodes']
        unique={str(n['id']):n for n in nodes}
        nodes=list(unique.values())
        if nodes:
            messages=[dict(dst_node_id=str(n['id']),payload=json.dumps({'kind':'node_task','discover':True,'mode':'smoke'}),reply_to_message_id=None) for n in nodes]
            pushed=grid_call(self.grid,'push_messages',{'messages':messages})['results']
            if len(pushed)!=len(nodes): raise ValueError('Invalid discovery push results')
            expected={}
            for node,result in zip(nodes,pushed):
                if result.get('error') or not result.get('message_id'): continue
                if result['message_id'] in expected: raise ValueError('Duplicate discovery ID')
                expected[result['message_id']]=str(node['id'])
            capabilities={}; seen=set()
            if expected:
                discovery=grid_call(self.grid,'pull_messages',dict(message_ids=list(expected),timeout=self.timeout))
                for reply in discovery['messages']:
                    mid=reply.get('reply_to_message_id')
                    if mid not in expected or mid in seen or str(reply.get('src_node_id'))!=expected[mid]: raise ValueError('Invalid discovery reply correlation')
                    seen.add(mid)
                    if reply.get('error'): continue
                    result=json.loads(reply['payload'])
                    if result.get('kind')!='node_capabilities' or not isinstance(result.get('instruments'),list) or not set(result['instruments'])<=set(INSTRUMENTS): raise ValueError('Invalid node capabilities')
                    capabilities[expected[mid]]=result['instruments']
            for instrument in INSTRUMENTS:
                candidates=[node for node,roles in capabilities.items() if instrument in roles]
                if not candidates: raise RuntimeError(f'No available Grid node can serve {instrument}')
                self.assignments[instrument]=min(candidates,key=lambda n:(len(capabilities[n]),list(self.assignments.values()).count(n)))
            if len(set(self.assignments.values()))<3: self.limitations.append('Fewer than three instrument nodes: nodes execute multiple instrument roles.')
        else: self.limitations.append('grid: none (local fallback); all instruments execute in this process.')
        self.collect(INSTRUMENTS,question)
        final=self.reconcile(question,prior)
        if self.mode!='smoke' and final.get('requested_next_check'):
            follow=final['requested_next_check']
            target=next((i for i in INSTRUMENTS if re.search(r'\b'+i+r'\b',follow.lower())),None)
            if target is not None:
                self.collect([target],follow)
                final=self.reconcile(question,prior)
            else:
                final['data_limitations'].append('Follow-up did not name an instrument; no additional node task dispatched.')
            if final.get('requested_next_check'): final['data_limitations'].append('One follow-up budget exhausted; further checks require a human turn.')
        raw_by_instrument={r['instrument']:r['raw_bytes_held'] for r in self.reports}
        raw=sum(raw_by_instrument.values()); payload=sum(r['payload_bytes'] for r in self.reports)
        shared=dict(raw_bytes_held=raw,payload_bytes=payload,percent_shared=100*payload/raw if raw else None,raw_samples_shared=0,
            measurement='UTF-8 node report bytes / instrument array bytes; includes repeated follow-up reports, excludes transport overhead',complete=not self.failed)
        self.publish('data_shared',data_shared=shared)
        metrics=self.budget.metrics()
        for report in self.reports:
            node=report.get('metrics',{})
            for key in ('model_calls','input_characters'): metrics[key]+=node.get(key,0)
            for key in ('input_tokens','output_tokens'):
                metrics[key]=None if metrics[key] is None or node.get(key) is None else metrics[key]+node[key]
        if self.failed:
            metrics['input_tokens']=metrics['output_tokens']=None
        metrics.update(latency_s=round(time.perf_counter()-self.started,3),tool_calls=3*len(self.reports),cost_usd=None,
            cost_note='Provider cost not returned; no estimate assumed.',unsupported_claims=None,unsupported_claims_note='Requires human claim review.',accounting_complete=not self.failed)
        report=dict(result_schema_version=2,benchmark_eligible=False,event_id=self.event_id,mode=self.mode,model=self.model,
            final=final,findings=self.findings,evidence=[dict(ref=ref,kind='node_summary',event_id=self.event_id,instrument=r['instrument'],result=r['summary']) for r in self.reports for ref in r['tool_refs']],node_reports=self.reports,data_shared=shared,metrics=metrics,onset_alignment=self.onset_alignment(),
            grid='connected' if nodes else 'none (local fallback)',node_assignments=self.assignments,
            provider='none' if self.mode=='smoke' else getattr(self.client,'provider','flower'),
            model_execution_path='No model called' if self.mode=='smoke' else 'Instrument-local and lead Responses calls',limitations=self.limitations)
        self.publish('report',report=report)
        return report
