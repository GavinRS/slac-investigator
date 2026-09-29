"""Merged node dispatch: one validated path across both reply transports."""
import json
from types import SimpleNamespace
import pytest
from slac_assistant import agent_app,node_agent
from slac_assistant.node import node_task

class Grid:
    def __init__(self,names):self.names=names;self.calls=[]
    def tools(self):return [{'name':name} for name in self.names]
    def call(self,call):
        self.calls.append(call)
        result={'message_id':'reply-id','error':None}
        if call['name']=='push_messages':result={'results':[result]}
        return {'type':'function_call_output','call_id':call['call_id'],'output':json.dumps(result)}

def agent(task,names=('push_reply_message',)):
    return SimpleNamespace(prompt=json.dumps({'message_id':'m-1','src_node_id':'1','payload':json.dumps(task)}),grid=Grid(names),events=SimpleNamespace(emit=lambda event:None))

def task(instrument='ltu',**kwargs):
    return dict(kind='node_task',event_id='slac-001',instrument=instrument,mode='smoke',question='q',**kwargs)

@pytest.fixture(autouse=True)
def assigned(monkeypatch):
    monkeypatch.setattr(node_agent,'detect_local_instrument',lambda:None)

@pytest.mark.parametrize('transport',['push_reply_message','push_messages'])
def test_assigned_report_is_validated_and_correlated(transport):
    instance=agent(task(),(transport,))
    agent_app.main(instance,SimpleNamespace(run_config={},state={}))
    [call]=instance.grid.calls
    assert call['name']==transport
    if transport=='push_messages':
        [message]=call['arguments']['messages']
        assert message['dst_node_id']=='1' and message['reply_to_message_id']=='m-1'
        payload=message['payload']
    else:payload=call['arguments']['payload']
    report=json.loads(payload)
    assert report['role_source']=='assigned'
    assert report['instrument']=='ltu'
    assert report['payload_bytes']==len(payload.encode())
    assert report['metrics']['model_calls']==0
    node_agent.validate_node_report(report,'slac-001','ltu')

def test_local_instrument_cannot_be_reassigned(monkeypatch):
    monkeypatch.setattr(node_agent,'detect_local_instrument',lambda:'rf')
    with pytest.raises(ValueError,match='does not match local data'):
        agent_app.main(agent(task('ltu')),SimpleNamespace(run_config={},state={}))

def test_discovery_uses_local_capability_without_model_or_context(monkeypatch):
    monkeypatch.setattr(node_agent,'detect_local_instrument',lambda:'rf')
    instance=agent({'kind':'node_task','discover':True,'mode':'smoke'})
    agent_app.main(instance,None)
    payload=json.loads(instance.grid.calls[0]['arguments']['payload'])
    assert payload=={'kind':'node_capabilities','instruments':['rf']}

def test_non_node_smoke_uses_grid_path(monkeypatch):
    got=[]
    class Investigator:
        def __init__(self,*args):got.append(args)
        def run(self,question,prior):return {'final':{}}
    monkeypatch.setattr(agent_app,'GridInvestigation',Investigator)
    instance=SimpleNamespace(prompt=json.dumps({'event_id':'slac-001','mode':'smoke'}),grid=Grid([]),events=SimpleNamespace(emit=lambda event:None))
    agent_app.main(instance,SimpleNamespace(state={},run_config={}))
    assert got and got[0][0]=='slac-001' and instance.grid.calls==[]
    assert node_task(json.dumps({'src_node_id':'1','payload':'{"kind":"other"}'})) is None
