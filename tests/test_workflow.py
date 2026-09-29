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
        text=json.dumps(dict(finding_id='fixture',agent=role,observation='Protocol fixture only.',source_channels=[m['station']+':AMPL'],time_interval_ns=[m['candidate_start_ns'],m['candidate_end_ns']],tool_result_refs=refs,supporting_evidence=['Fixture'],conflicting_evidence=[],data_limitations=['Not a live model result'],requested_next_check='charge_validity' if role!='lead' else None,beam_disturbance=dict(status='insufficient_evidence',rationale='Fixture',tool_result_refs=refs),unique_cause=dict(status='not_established',rationale='Fixture',tool_result_refs=refs)))
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
    f=dict(finding_id='X',agent='lead',observation='x',source_channels=[],time_interval_ns=[0,1],tool_result_refs=['invented'],supporting_evidence=[],conflicting_evidence=[],data_limitations=[],requested_next_check=None,beam_disturbance=dict(status='corroborated',rationale='Fixture',tool_result_refs=['invented']),unique_cause=dict(status='not_established',rationale='Fixture',tool_result_refs=['invented']))
    with pytest.raises(ValueError):inv.validate(json.dumps(f),'lead',[])

class InvalidChannelThenCorrection(FixtureModel):
    def create(self,**kwargs):
        response=super().create(**kwargs)
        if len(self.requests)==1:
            payload=json.loads(response.output_text)
            payload['source_channels']=['BPMS:nonexistent']
            response.output_text=json.dumps(payload)
        return response

def test_final_channel_error_gets_bounded_correction():
    model=InvalidChannelThenCorrection();events=[]
    inv=Investigation('slac-001',events.append,client=model,max_calls=2)
    evidence=inv.tool('equipment','equipment')
    result=inv.loop('equipment','Inspect RF.',[evidence],cap=1)
    assert len(model.requests)==2 and inv.calls==2
    assert all(request['tools']==[] for request in model.requests)
    assert result['source_channels']==['KLYS:LI29:11:AMPL']
    assert len(inv.findings)==1
    assert any(e['kind']=='finding_rejected' and 'BPMS:nonexistent' in e['error'] for e in events)

def test_channel_correction_cannot_exceed_shared_budget():
    model=InvalidChannelThenCorrection()
    inv=Investigation('slac-001',lambda e:None,client=model,max_calls=1)
    evidence=inv.tool('equipment','equipment')
    with pytest.raises(ValueError,match='unavailable channels'):
        inv.loop('equipment','Inspect RF.',[evidence],cap=1)
    assert len(model.requests)==1 and not inv.findings


def test_rf_excursion_does_not_make_beam_corroboration_positive():
    report=Investigation('slac-003',lambda e:None).smoke()
    assert report['final']['beam_disturbance']['status']=='not_corroborated'
    assert report['final']['unique_cause']['status']=='not_established'
    assert 'assessment' not in report['final']
    assert report['benchmark_eligible'] is False


def test_evaluator_never_scores_legacy_mixed_scope_labels():
    from scripts.evaluate import summarize
    report=dict(event_id='slac-003',mode='collaborative',model='legacy',final=dict(assessment='corroborated'),findings=[],evidence=[],wall_latency_s=1.0,
                metrics=dict(model_calls=1,tool_calls=0,latency_s=1.0,input_tokens=None,output_tokens=None,cost_usd=None))
    row=summarize([report],{'slac-003':{'is_anom':False}})[0]
    assert row['prediction'] is None and row['agreement'] is None
    assert row['beam_disturbance']['status']=='not_assessed'
    assert row['benchmark_eligible'] is False


def test_unavailable_dimension_evidence_rejected():
    report=Investigation('slac-001',lambda e:None).smoke()
    finding=report['final'];finding['unique_cause']['tool_result_refs']=['invented']
    inv=Investigation('slac-001',lambda e:None)
    with pytest.raises(ValueError,match='Assessment references'):
        inv.validate(json.dumps(finding),'lead',finding['tool_result_refs'])


def test_model_setting_env_then_dotenv_then_default(tmp_path,monkeypatch):
    import tomllib
    from pathlib import Path
    from slac_assistant.workflow import configured_model,DEFAULT_MODEL
    pyproject=tomllib.loads((Path(__file__).resolve().parents[1]/'pyproject.toml').read_text())
    assert pyproject['tool']['flwr']['app']['config']['model']==DEFAULT_MODEL
    monkeypatch.delenv('INVESTIGATOR_MODEL',raising=False)
    env=tmp_path/'.env';assert configured_model(env)==DEFAULT_MODEL
    env.write_text('FLWR_MODEL_API_KEY=secret\nexport INVESTIGATOR_MODEL="flwrlabs/endeavor-1.0"\n')
    assert configured_model(env)=='flwrlabs/endeavor-1.0'
    monkeypatch.setenv('INVESTIGATOR_MODEL','from-env');assert configured_model(env)=='from-env'
