"""Protocol fixtures test routing, not model intelligence or agent efficacy."""
import json
from types import SimpleNamespace
import pytest
from slac_assistant.workflow import Investigation,Finding

class Item:
    def __init__(self,kind,**kwargs):self.type=kind;self.__dict__.update(kwargs)
    def model_dump(self,**kwargs):return dict(self.__dict__)

class FixtureModel:
    def __init__(self):self.requests=[];self.responses=self
    def create(self,**kwargs):
        self.requests.append(kwargs)
        role=kwargs['instructions'].split('Your role is ')[-1].split('.')[0]
        # Deliberately route one follow-up only to test coordinator plumbing.
        if role=='lead' and not any(x.get('type')=='function_call_output' for x in kwargs['input']):
            item=Item('function_call',name='delegate',arguments=json.dumps(dict(agent='beam',kind='charge_validity',question='Check low-charge validity.')),call_id='fixture-call')
            return SimpleNamespace(output=[item],output_text='',usage=SimpleNamespace(input_tokens=100,output_tokens=100),status='completed')
        payload=json.loads(kwargs['input'][0]['content'].split('\nShared tool evidence:')[0]);initial=payload['initial_evidence']
        shared=payload['shared_findings'];refs=[r['ref'] for r in initial] or [r for f in shared for r in f['tool_result_refs']]
        m=payload['event']
        text=json.dumps(dict(finding_id='fixture',agent=role,observation='Protocol fixture only.',source_channels=[m['station']+':AMPL'],time_interval_ns=[m['candidate_start_ns'],m['candidate_end_ns']],tool_result_refs=refs,supporting_evidence=['Fixture'],conflicting_evidence=[],data_limitations=['Not a live model result'],requested_next_check='charge_validity' if role!='lead' else None,assessment='insufficient_evidence'))
        return SimpleNamespace(output=[],output_text=text,usage=SimpleNamespace(input_tokens=100,output_tokens=100),status='completed')

def test_independent_specialists_and_followup():
    model=FixtureModel();events=[];inv=Investigation('slac-001',events.append,client=model)
    report=inv.run()
    assert len(model.requests)==5
    beam_initial=model.requests[1]['input'][0]['content']
    assert 'Protocol fixture only.' not in beam_initial
    assert any(e['kind']=='delegation' and e.get('analysis')=='charge_validity' for e in events)
    assert len(report['findings'])==4
    assert report['metrics']['model_calls']<=12
    assert report['metrics']['unsupported_claims'] is None

def test_baseline_uses_same_budget_and_initial_evidence():
    model=FixtureModel();inv=Investigation('slac-001',lambda e:None,client=model,mode='baseline')
    report=inv.run();assert inv.max_calls==12
    assert {r['analysis'] for r in report['evidence']}=={'equipment','beam','quality'}
    assert [x['name'] for x in model.requests[0]['tools']]==['analyze']

def test_unknown_evidence_ref_rejected():
    inv=Investigation('slac-001',lambda e:None)
    f=dict(finding_id='X',agent='lead',observation='x',source_channels=[],time_interval_ns=[0,1],tool_result_refs=['invented'],supporting_evidence=[],conflicting_evidence=[],data_limitations=[],requested_next_check=None,assessment='corroborated')
    with pytest.raises(ValueError):inv.validate(json.dumps(f),'lead',[])
