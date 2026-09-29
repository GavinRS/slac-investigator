"""Node path with a fake agent: role source, reply tool variant, payload is only the node_report."""
import json,sys
from types import ModuleType,SimpleNamespace
import pytest
from slac_assistant import agent_app,tools

class Grid:
    def __init__(self,names):self.names=names;self.calls=[]
    def tools(self):return [{'name':n} for n in self.names]
    def call(self,c):self.calls.append(c);return {'type':'function_call_output','call_id':c['call_id'],'output':'{}'}

def agent(prompt,names):
    return SimpleNamespace(prompt=prompt,grid=Grid(names),events=SimpleNamespace(emit=lambda e:None))

def node_prompt(**kw):
    task=dict(kind='node_task',event_id='slac-001',instrument='ltu',mode='smoke',question='q',**kw)
    return json.dumps({'message_id':'m-1','src_node_id':'1','payload':json.dumps(task)})

@pytest.fixture
def fakes(monkeypatch):
    seen={}
    inst=ModuleType('slac_assistant.instruments');inst.local=None
    inst.detect_local_instrument=lambda:inst.local
    def load_slice(e,i,root=None):seen['slice']=(e,i,root);return {},{'t':[1,2]}
    inst.load_slice=load_slice
    monkeypatch.setitem(sys.modules,'slac_assistant.instruments',inst)
    def node_summary(e,i,arrays,role_source='assigned'):return dict(kind='node_report',instrument=i,role_source=role_source,event_id=e)
    monkeypatch.setattr(tools,'node_summary',node_summary,raising=False)
    monkeypatch.setenv('SLAC_NODE_DATA_DIR','/data/node')
    return inst,seen

def run(prompt,names=('push_reply_message',)):
    a=agent(prompt,names);agent_app.main(a,None);return a.grid.calls

def test_assigned_role_push_reply(fakes):
    inst,seen=fakes;calls=run(node_prompt())
    assert seen['slice']==('slac-001','ltu',None)
    [c]=calls;assert c['name']=='push_reply_message' and set(c['arguments'])=={'payload'}
    assert json.loads(c['arguments']['payload'])==dict(kind='node_report',instrument='ltu',role_source='assigned',event_id='slac-001')

def test_local_role_push_messages_fallback(fakes):
    inst,seen=fakes;inst.local='rf';calls=run(node_prompt(),('push_messages',))
    assert seen['slice']==('slac-001','rf','/data/node')
    [c]=calls;assert c['name']=='push_messages'
    [m]=c['arguments']['messages'];assert m['dst_node_id']=='1' and m['reply_to_message_id']=='m-1'
    assert json.loads(m['payload'])['role_source']=='local_data'

def test_non_node_prompt_uses_old_path(fakes,monkeypatch):
    got=[]
    class Inv:
        def __init__(self,*a):got.append(a)
        def smoke(self,q):return {'final':{}}
    monkeypatch.setattr(agent_app,'Investigation',Inv)
    ctx=SimpleNamespace(state={},run_config={})
    a=agent(json.dumps({'event_id':'slac-001','mode':'smoke'}),());agent_app.main(a,ctx)
    assert got and got[0][0]=='slac-001' and a.grid.calls==[]
    assert agent_app.node_task(json.dumps({'src_node_id':'1','payload':'{"kind":"other"}'})) is None
