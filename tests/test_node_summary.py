import json
import pytest
from slac_assistant.data import event_ids
from slac_assistant.instruments import INSTRUMENTS,load_slice
from slac_assistant.tools import analyze,node_summary

FIELDS={'kind','instrument','role_source','event_id','assessment','observation','summary','tool_refs','raw_bytes_held','payload_bytes','limitations'}

def lists(x):
    if isinstance(x,dict):
        for v in x.values():yield from lists(v)
    elif isinstance(x,list):
        yield x
        for v in x:yield from lists(v)

@pytest.mark.parametrize('event_id',event_ids())
@pytest.mark.parametrize('instrument',INSTRUMENTS)
def test_node_report_contract(event_id,instrument):
    _,arrays=load_slice(event_id,instrument)
    r=node_summary(event_id,instrument,arrays,role_source='local_data');text=json.dumps(r)
    assert set(r)==FIELDS and r['kind']=='node_report' and r['instrument']==instrument and r['event_id']==event_id and r['role_source']=='local_data'
    assert r['assessment'] in ('suspicious','normal','insufficient_evidence') and r['observation'] and r['limitations']
    assert all(len(x)<=10 for x in lists(r['summary']))
    assert r['payload_bytes']==len(text.encode()) and r['payload_bytes']*20<r['raw_bytes_held']==sum(v.nbytes for v in arrays.values())
    assert all(t.startswith('T-') for t in r['tool_refs']) and len(r['tool_refs'])==3
    other={'rf':('BPMS:',),'ltu':('DMPH','KLYS:'),'dump':('LTUH','KLYS:')}[instrument]
    assert not any(o in text for o in other)
    assert node_summary(event_id,instrument,arrays,role_source='local_data')==r

def test_instrument_checks_restricted_and_match_full_event():
    with pytest.raises(ValueError):analyze('slac-001','equipment','ltu')
    with pytest.raises(ValueError):analyze('slac-001','beam','rf')
    full={c['channel']:c for c in analyze('slac-001','beam')['result']['channels']}
    for inst,prefix in (('ltu','BPMS:LTUH:'),('dump','BPMS:DMPH:')):
        rows=analyze('slac-001','beam',inst)['result']['channels']
        assert rows and all(c['channel'].startswith(prefix) and c==full[c['channel']] for c in rows)
        assert list(analyze('slac-001','quality',inst)['result'])==['bpm']
    assert analyze('slac-001','equipment','rf')['result']==analyze('slac-001','equipment')['result']
