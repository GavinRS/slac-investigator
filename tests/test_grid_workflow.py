import json
import unittest
from slac_assistant.grid_workflow import GridInvestigation
from slac_assistant.node_agent import run_node
from slac_assistant.tools import serialize_node_report

class FakeGrid:
    def __init__(self,roles,corrupt=None):
        self.roles=roles; self.tasks={}; self.calls=[]; self.corrupt=corrupt
    def call(self,call):
        self.calls.append(call); args=call['arguments']; name=call['name']
        if name=='get_nodes': result={'nodes':[{'id':n,'name':None,'location':None} for n in self.roles],'num_available':len(self.roles)}
        elif name=='push_messages':
            results=[]
            for task in args['messages']:
                mid=str(len(self.tasks)+1); self.tasks[mid]=task; results.append({'message_id':mid,'error':None})
            result={'results':results}
        elif name=='pull_messages':
            assert 0<=args['timeout']<=300
            messages=[]
            for mid in args['message_ids']:
                task=self.tasks[mid]; payload=json.loads(task['payload'])
                if payload.get('discover'): out=json.dumps({'kind':'node_capabilities','instruments':self.roles[task['dst_node_id']]})
                else:
                    report=run_node(payload)
                    if self.corrupt=='raw': report['summary']['raw']=list(range(11))
                    out=serialize_node_report(report)
                messages.append(dict(message_id='r'+mid,reply_to_message_id=mid,src_node_id=task['dst_node_id'],payload=out,error=None))
            if self.corrupt=='source' and not payload.get('discover'): messages[0]['src_node_id']='999'
            if self.corrupt=='missing' and not payload.get('discover'): messages=messages[:-1]
            result={'messages':messages,'pending_message_ids':[]}
        return dict(type='function_call_output',call_id=call['call_id'],output=json.dumps(result))

class GridTests(unittest.TestCase):
    def run_grid(self,roles,corrupt=None):
        events=[]; grid=FakeGrid(roles,corrupt)
        report=GridInvestigation('slac-001',events.append,grid,mode='smoke').run()
        return report,events,grid
    def test_three_unnamed_fixed_nodes_discovered(self):
        report,events,_=self.run_grid({'23':['dump'],'14':['rf'],'7':['ltu']})
        self.assertEqual(report['node_assignments'],{'rf':'14','ltu':'7','dump':'23'})
        self.assertEqual(len(report['node_reports']),3)
        self.assertEqual(report['data_shared']['raw_samples_shared'],0)
        self.assertEqual(report['metrics']['model_calls'],0)
        self.assertTrue(any(e['kind']=='report' for e in events))
    def test_one_flexible_node(self):
        report,_,_=self.run_grid({'7':['rf','ltu','dump']})
        self.assertEqual(set(report['node_assignments'].values()),{'7'})
        self.assertTrue(report['limitations'])
    def test_zero_local(self):
        report,_,grid=self.run_grid({})
        self.assertEqual(report['grid'],'none (local fallback)')
        self.assertEqual(len(grid.calls),1)
        shared=report['data_shared']; self.assertAlmostEqual(shared['percent_shared'],100*shared['payload_bytes']/shared['raw_bytes_held'])
    def test_privacy_and_correlation(self):
        for corrupt in ('raw','source'):
            with self.subTest(corrupt=corrupt),self.assertRaises(ValueError): self.run_grid({'7':['rf','ltu','dump']},corrupt)
    def test_missing_reply_is_explicit(self):
        report,_,_=self.run_grid({'7':['rf','ltu','dump']},'missing')
        self.assertFalse(report['data_shared']['complete'])
        self.assertFalse(report['metrics']['accounting_complete'])
        self.assertEqual(report['final']['beam_disturbance']['status'],'insufficient_evidence')
    def test_fixed_node_cannot_serve_other_roles(self):
        with self.assertRaisesRegex(RuntimeError,'ltu'): self.run_grid({'7':['rf']})
    def test_timeout_rejected(self):
        with self.assertRaises(ValueError): GridInvestigation('slac-001',lambda _:None,FakeGrid({}),timeout=301)


class CollaborativeFixture:
    def __init__(self):
        self.responses=self; self.calls=[]; self.lead_calls=0
    def create(self,**kwargs):
        from types import SimpleNamespace
        self.calls.append(kwargs); payload=json.loads(kwargs['input'][0]['content'])
        if 'report' in payload:
            value=dict(assessment='suspicious',observation='Instrument aggregate assessment.',tool_refs=payload['report']['tool_refs'])
        else:
            self.lead_calls+=1
            if self.lead_calls==1: value={}
            else:
                refs=list(dict.fromkeys(ref for report in payload['node_reports'] for ref in report['tool_refs']))
                value=dict(finding_id='draft',agent='draft',observation='Summary-only reconciled result.',source_channels=[],
                    time_interval_ns=payload['candidate_interval_ns'],tool_result_refs=refs,supporting_evidence=[],conflicting_evidence=[],data_limitations=[],
                    requested_next_check='rf: review local aggregate quality' if self.lead_calls==2 else None,
                    beam_disturbance=dict(status='insufficient_evidence',rationale='Review summary limitations.',tool_result_refs=refs),
                    unique_cause=dict(status='not_established',rationale='No unique causal inference.',tool_result_refs=refs))
        return SimpleNamespace(status='completed',output_text=json.dumps(value),usage=SimpleNamespace(input_tokens=10,output_tokens=5))

class CollaborativeTests(unittest.TestCase):
    def test_local_model_retry_followup_and_shared_accounting(self):
        client=CollaborativeFixture()
        report=GridInvestigation('slac-001',lambda _:None,FakeGrid({}),client,'fixture').run('Review event',{'operator':'prior'})
        self.assertEqual(len(report['node_reports']),4)
        self.assertEqual(report['node_reports'][-1]['instrument'],'rf')
        self.assertEqual(report['metrics']['model_calls'],7)
        self.assertEqual(report['metrics']['input_tokens'],70)
        self.assertEqual(len(report['findings']),2)
        self.assertTrue(report['evidence'])
        for request in client.calls:
            content=json.loads(request['input'][0]['content'])
            self.assertNotIn('arrays',content)
        self.assertEqual(report['final']['unique_cause']['status'],'not_established')

class AgentContextTests(unittest.TestCase):
    def test_human_followup_uses_saved_same_event_assessment_only(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from slac_assistant.agent_app import main
        received=[]
        class Investigator:
            def __init__(self,event_id,*args): self.event_id=event_id
            def run(self,question,prior):
                received.append((self.event_id,question,prior))
                return {'final':{'observation':question,'event_id':self.event_id}}
        events=[]
        context=SimpleNamespace(state={},run_config={'model':'fixture'})
        agent=SimpleNamespace(prompt='',events=SimpleNamespace(emit=events.append),grid=object())
        with patch('slac_assistant.agent_app.GridInvestigation',Investigator),patch('slac_assistant.agent_app.create_model_client',return_value=(object(),'fixture')):
            for event,question in [('slac-001','Initial assessment'),('slac-001','Explain the beam limitations'),('slac-002','Different event')]:
                agent.prompt=json.dumps({'event_id':event,'mode':'collaborative','question':question})
                main(agent,context)
        self.assertIsNone(received[0][2])
        self.assertEqual(received[1][2],{'observation':'Initial assessment','event_id':'slac-001'})
        self.assertEqual(received[1][1],'Explain the beam limitations')
        self.assertIsNone(received[2][2])
        self.assertEqual(json.loads(context.state['investigation']['final'])['observation'],'Different event')
        self.assertEqual(sum(e['type']=='response.completed' for e in events),3)

    def test_node_discovery_does_not_overwrite_human_state_or_call_model(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from slac_assistant.agent_app import main
        state={'investigation':{'event_id':'slac-001','final':'{"observation":"saved"}'}}
        context=SimpleNamespace(state=state,run_config={})
        agent=SimpleNamespace(prompt=json.dumps({'src_node_id':'1','message_id':'m1','payload':json.dumps({'kind':'node_task','discover':True,'mode':'smoke'})}))
        with patch('slac_assistant.agent_app.reply_to_node') as reply,patch('slac_assistant.agent_app.create_model_client') as create:
            main(agent,context)
            reply.assert_called_once(); create.assert_not_called()
        self.assertEqual(context.state['investigation']['final'],'{"observation":"saved"}')


class OnsetAlignmentTests(unittest.TestCase):
    def test_integer_recorded_differences_preserve_unknown_and_no_shifts(self):
        inv=GridInvestigation('slac-001',lambda _:None,FakeGrid({}),mode='smoke')
        start=inv.meta['candidate_start_ns']; end=inv.meta['candidate_end_ns']
        inv.collect(('rf','ltu','dump'),'')
        for report in inv.reports:
            report['summary']['onset_ns']={'rf':end+1,'ltu':start+7,'dump':None}[report['instrument']]
        alignment=inv.onset_alignment()
        self.assertEqual(alignment['recorded_onset_ns'],{'rf':end+1,'ltu':start+7,'dump':None})
        self.assertEqual(alignment['pairwise_difference_ns']['ltu_minus_rf'],start+7-(end+1))
        self.assertIsNone(alignment['pairwise_difference_ns']['dump_minus_rf'])
        self.assertEqual(alignment['within_candidate_window'],{'rf':False,'ltu':True,'dump':None})
        self.assertEqual(alignment['applied_shift_ns'],0)
        final=inv.reconcile('',None)
        self.assertIn('1 of 2 available recorded instrument onsets',final['observation'])
        self.assertEqual(final['unique_cause']['status'],'not_established')
        self.assertIn('no fixed reporting delay',alignment['caveat'])

    def test_tool_count_does_not_depend_on_model_reference_pruning(self):
        client=CollaborativeFixture()
        original=client.create
        def prune(**kwargs):
            response=original(**kwargs)
            value=json.loads(response.output_text)
            if 'assessment' in value:
                value['tool_refs']=value['tool_refs'][:1]
                response.output_text=json.dumps(value)
            return response
        client.create=prune
        report=GridInvestigation('slac-001',lambda _:None,FakeGrid({}),client,'fixture').run()
        self.assertEqual(report['metrics']['tool_calls'],12)
        self.assertEqual(len(report['node_reports']),4)
        self.assertTrue(all(len(node['tool_refs'])==1 for node in report['node_reports']))
        self.assertIn('onset_alignment',report)


class BeamEvidenceCitationTests(unittest.TestCase):
    def test_corroboration_must_cite_the_adequate_positive_beam_report(self):
        inv=GridInvestigation('slac-001',lambda _:None,FakeGrid({}),mode='smoke')
        inv.reports=[
            dict(instrument='rf',tool_refs=['T-rf'],summary=dict(quality_adequate=1,suspicious=1)),
            dict(instrument='ltu',tool_refs=['T-negative'],summary=dict(quality_adequate=0,disturbance_detected=0)),
            dict(instrument='dump',tool_refs=['T-positive'],summary=dict(quality_adequate=1,disturbance_detected=1)),
        ]
        finding=dict(finding_id='draft',agent='lead',observation='Beam disturbance corroborated.',
            source_channels=[],time_interval_ns=[inv.meta['candidate_start_ns'],inv.meta['candidate_end_ns']],
            tool_result_refs=['T-rf','T-negative','T-positive'],supporting_evidence=[],conflicting_evidence=[],
            data_limitations=[],requested_next_check=None,
            beam_disturbance=dict(status='corroborated',rationale='Check cited support.',tool_result_refs=['T-negative']),
            unique_cause=dict(status='not_established',rationale='No causal inference.',tool_result_refs=['T-rf']))
        for inadequate_refs in (['T-negative'], ['T-rf']):
            finding['beam_disturbance']['tool_result_refs']=inadequate_refs
            with self.subTest(refs=inadequate_refs),self.assertRaisesRegex(ValueError,'must cite adequate positive'):
                inv.validate_finding(json.dumps(finding))
        finding['beam_disturbance']['tool_result_refs']=['T-positive']
        self.assertEqual(inv.validate_finding(json.dumps(finding))['beam_disturbance']['status'],'corroborated')
        inv.reports[-1]['summary']['quality_adequate']=0
        with self.assertRaisesRegex(ValueError,'must cite adequate positive'):
            inv.validate_finding(json.dumps(finding))
