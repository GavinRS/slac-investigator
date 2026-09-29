"""Orchestrator routing with a fake Grid (3, 1, 0 nodes); replies come from the real node path."""
import json
from types import SimpleNamespace
import pytest
from slac_assistant import agent_app,grid_workflow,instruments
from slac_assistant.node import node_task,run_node

class NodeGrid:
    def __init__(self):self.sent=None
    def tools(self):return [{'name':'push_reply_message'}]
    def call(self,c):self.sent=c['arguments']['payload'];return {'output':'{}'}

class FakeGrid:
    def __init__(self,n,drop=(),local=None):self.n=n;self.drop=drop;self.local=local or {};self.names=[];self.inbox={}
    def call(self,c):
        self.names.append(c['name']);a=c['arguments']
        if c['name']=='get_nodes':out={'nodes':[{'id':str(10+k),'name':None,'location':None} for k in range(self.n)],'num_available':self.n}
        elif c['name']=='push_messages':
            ids=[f'm{k}' for k in range(len(a['messages']))];self.inbox=dict(zip(ids,a['messages']))
            out={'results':[{'message_id':i,'error':None} for i in ids]}
        else:
            msgs,pending=[],[]
            for i in a['message_ids']:
                m=self.inbox[i];prompt=json.dumps({'message_id':i,'src_node_id':'1','payload':m['payload']})
                if json.loads(m['payload'])['instrument'] in self.drop:pending.append(i);continue
                instruments.detect_local_instrument=lambda:self.local.get(m['dst_node_id'])
                ng=NodeGrid();run_node(SimpleNamespace(grid=ng),*node_task(prompt))
                msgs.append({'message_id':'r'+i,'reply_to_message_id':i,'src_node_id':m['dst_node_id'],'payload':ng.sent,'error':None})
            out={'messages':msgs,'pending_message_ids':pending}
        return {'type':'function_call_output','call_id':c['call_id'],'output':json.dumps(out)}

@pytest.fixture(autouse=True)
def no_local(monkeypatch):
    monkeypatch.setattr(instruments,'detect_local_instrument',instruments.detect_local_instrument)
    monkeypatch.delenv('SLAC_NODE_DATA_DIR',raising=False);monkeypatch.delenv('FLWR_FILESYSTEM_ALLOWED_DIRS',raising=False)

def run(n,event='slac-001',**kw):
    events=[];g=FakeGrid(n,**kw)
    report=grid_workflow.run_grid(SimpleNamespace(grid=g),event,events.append)
    return report,events,g

def test_three_nodes_one_instrument_each():
    report,events,g=run(3)
    assert g.names==['get_nodes','push_messages','pull_messages']
    assert report['grid']=={'nodes_seen':3,'assignment':{'rf':'10','ltu':'11','dump':'12'},'fallback':None}
    assert report['mode']=='grid' and report['result_schema_version']==2 and report['model_execution_path']=='No model called'
    f=report['final'];assert f['beam_disturbance']['status']=='corroborated' and f['unique_cause']['status']=='not_established'
    assert set(f['tool_result_refs'])=={e['ref'] for e in report['evidence']} and len(report['evidence'])==9
    assert any('onset offset' in x for x in f['supporting_evidence'])
    kinds=[e['kind'] for e in events]
    assert kinds[0]=='started' and kinds[-1]=='report' and kinds.count('delegation')==3 and kinds.count('node_report')==3
    assert {'tool_request','tool_result','finding','data_shared'}<=set(kinds)
    assert {(e['node_id'],e['instrument']) for e in events if e['kind']=='delegation'}=={('10','rf'),('11','ltu'),('12','dump')}
    ds=next(e for e in events if e['kind']=='data_shared');assert ds=={'kind':'data_shared',**report['data_shared']}
    assert 0<ds['percent_shared']<5

def test_one_node_takes_all_instruments():
    report,events,g=run(1,'slac-003')
    assert report['grid']['assignment']=={'rf':'10','ltu':'10','dump':'10'} and 'several' in report['grid']['fallback']
    assert report['final']['beam_disturbance']['status']=='not_corroborated'
    assert len([e for e in events if e['kind']=='node_report'])==3

def test_zero_nodes_local_fallback():
    report,events,g=run(0)
    assert g.names==['get_nodes'] and report['grid']=={'nodes_seen':0,'assignment':{'rf':'local','ltu':'local','dump':'local'},'fallback':'none (local fallback)'}
    assert report['final']['beam_disturbance']['status']=='corroborated'

def test_missing_reply_is_a_limitation():
    report,events,g=run(3,drop=('dump',))
    assert 'dump task: no reply within 120.0 s' in report['final']['data_limitations']
    assert {e['instrument'] for e in events if e['kind']=='node_report'}=={'rf','ltu'}

def test_local_data_node_overrides_assignment():
    # Node 10 was assigned rf but holds dump locally, and vice versa (spec: C with A fallback).
    report,events,g=run(3,local={'10':'dump','12':'rf'})
    assert report['grid']['assignment']=={'rf':'12','ltu':'11','dump':'10'}
    assert {e['instrument']:e['role_source'] for e in events if e['kind']=='node_report'}=={'rf':'local_data','ltu':'assigned','dump':'local_data'}

def test_percent_shared_math():
    r=lambda raw:{'raw_bytes_held':raw}
    assert grid_workflow.shared({'rf':(r(1000),10),'ltu':(r(3000),30)})=={'raw_bytes_held':4000,'payload_bytes':40,'percent_shared':1.0}
    assert grid_workflow.shared({'rf':(r(0),5)})['percent_shared'] is None

def test_agent_app_dispatches_grid_mode(monkeypatch):
    got=[];monkeypatch.setattr(agent_app,'run_grid',lambda *a,**k:got.append((a,k)) or {'final':{}})
    a=SimpleNamespace(prompt=json.dumps({'event_id':'slac-002','mode':'grid'}),grid=FakeGrid(3),events=SimpleNamespace(emit=lambda e:None))
    agent_app.main(a,SimpleNamespace(state={},run_config={'grid-timeout':30}))
    assert got[0][0][1]=='slac-002' and got[0][1]['timeout']==30

def test_agent_app_plain_text_prompt_runs_collaborative_grid(monkeypatch):
    got=[];monkeypatch.setattr(agent_app,'run_grid',lambda *a,**k:got.append((a,k)) or {'final':{}});monkeypatch.setattr(agent_app,'runtime_client',lambda:'client')
    q='Was the beam disturbed during SLAC-003?'
    a=SimpleNamespace(prompt=q,grid=FakeGrid(3),events=SimpleNamespace(emit=lambda e:None))
    agent_app.main(a,SimpleNamespace(state={},run_config={}))
    assert got[0][0][1]=='slac-003' and got[0][1]['mode']=='collaborative' and got[0][1]['question']==q and got[0][1]['client']=='client'

# Collaborative mode (#7): fixture model on nodes and orchestrator.
from slac_assistant import node as node_mod

class Item:
    def __init__(self,**kw):self.__dict__.update(kw)
    def model_dump(self,**kw):return dict(self.__dict__)

class FixtureModel:
    """Node calls get node_reply; lead calls pop from finals (callables of the evidence refs)."""
    def __init__(self,node_reply='{"assessment":"suspicious","observation":"Model note."}',finals=()):
        self.responses=self;self.node_reply=node_reply;self.finals=list(finals);self.node_calls=[];self.lead_calls=[]
    def create(self,**kw):
        if kw['instructions']==node_mod.NODE_RULES:self.node_calls.append(kw);text=self.node_reply
        else:
            self.lead_calls.append(kw);refs=[e['ref'] for e in json.loads(kw['input'][0]['content'])['initial_evidence']]
            text=self.finals.pop(0)(refs)
        return SimpleNamespace(status='completed',usage=None,output_text=text,output=[Item(type='message',role='assistant',content=[{'type':'output_text','text':text}])])

def finding(refs,beam='corroborated',cause='not_established'):
    d=lambda s:dict(status=s,rationale='r',tool_result_refs=refs[:1])
    return json.dumps(dict(finding_id='x',agent='x',observation='Model final.',source_channels=[],time_interval_ns=[0,1],tool_result_refs=refs,
        supporting_evidence=[],conflicting_evidence=[],data_limitations=[],requested_next_check=None,beam_disturbance=d(beam),unique_cause=d(cause)))

def run_collab(fm,n=3,monkeypatch=None):
    monkeypatch.setattr(node_mod,'runtime_client',lambda:fm)
    events=[];g=FakeGrid(n)
    return grid_workflow.run_grid(SimpleNamespace(grid=g),'slac-001',events.append,mode='collaborative',model='m',client=fm,prior={'p':1}),events

def test_collaborative_models_on_nodes_and_orchestrator(monkeypatch):
    fm=FixtureModel(finals=[finding]);report,events=run_collab(fm,monkeypatch=monkeypatch)
    assert len(fm.node_calls)==3 and len(fm.lead_calls)==1 and report['metrics']['model_calls']==1 and fm.lead_calls[0]['max_output_tokens']==4000
    assert all('arrays' not in c['input'] and json.loads(c['input'])['summary'] for c in fm.node_calls)
    assert report['node_observation_source']=={'rf':'model','ltu':'model','dump':'model'}
    assert {e['observation'] for e in events if e['kind']=='node_report'}=={'Model note.'}
    assert report['final']['observation']=='Model final.' and report['final']['agent']=='lead' and report['model_execution_path']!='No model called'
    assert set(report['final']['tool_result_refs'])=={e['ref'] for e in report['evidence']}
    assert 'assessment: {"p": 1}' in json.loads(fm.lead_calls[0]['input'][0]['content'])['task']

def test_invalid_node_reply_keeps_deterministic_observation(monkeypatch):
    fm=FixtureModel(node_reply='{"assessment":"broken"}',finals=[finding]);report,events=run_collab(fm,monkeypatch=monkeypatch)
    assert report['node_observation_source']=={'rf':'deterministic','ltu':'deterministic','dump':'deterministic'}
    assert all(any('Node model reply unusable (ValueError)' in x for x in e['limitations']) for e in events if e['kind']=='node_report')

def test_orchestrator_one_correction_turn(monkeypatch):
    fm=FixtureModel(finals=[lambda r:finding(['T-bogus']),finding]);report,events=run_collab(fm,monkeypatch=monkeypatch)
    assert report['metrics']['model_calls']==2 and [e['kind'] for e in events].count('finding_rejected')==1
    assert report['final']['observation']=='Model final.'

def test_orchestrator_rejected_twice_falls_back_to_deterministic(monkeypatch):
    fm=FixtureModel(finals=[lambda r:finding(r,'not_corroborated','established')]*2);report,events=run_collab(fm,monkeypatch=monkeypatch)
    assert report['metrics']['model_calls']==2 and [e['kind'] for e in events].count('finding_rejected')==2
    lim=report['final']['data_limitations'];assert any('Model final not accepted (ValueError' in x for x in lim)
    assert 'Deterministic combine of node summaries; the model final was not accepted.' in lim

def test_zero_nodes_collaborative_calls_node_model_in_process(monkeypatch):
    fm=FixtureModel(finals=[finding]);report,_=run_collab(fm,0,monkeypatch)
    assert len(fm.node_calls)==3 and report['grid']['fallback']=='none (local fallback)'

def test_model_mode_requires_client():
    with pytest.raises(ValueError):grid_workflow.run_grid(SimpleNamespace(grid=FakeGrid(3)),'slac-001',print,mode='collaborative')
