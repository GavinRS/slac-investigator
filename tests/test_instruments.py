import numpy as np
import pytest
from slac_assistant.data import load_event,event_ids
from slac_assistant.instruments import INSTRUMENTS,load_slice,detect_local_instrument
from scripts.split_nodes import split

def test_slices_partition_originals_exactly():
    for e in event_ids():
        m,a=load_event(e);s={i:load_slice(e,i) for i in INSTRUMENTS}
        np.testing.assert_array_equal(s['rf'][1]['health'],a['health'])
        np.testing.assert_array_equal(s['rf'][1]['health_time_ns'],a['health_time_ns'])
        assert s['rf'][0]['channels']=={'health':m['channels']['health']}
        names=s['ltu'][0]['channels']['bpm']+s['dump'][0]['channels']['bpm']
        assert sorted(names)==sorted(m['channels']['bpm']) and len(set(names))==len(names)
        assert all(c.startswith('BPMS:LTUH:') for c in s['ltu'][0]['channels']['bpm'])
        bpm=np.hstack([s['ltu'][1]['bpm'],s['dump'][1]['bpm']])
        np.testing.assert_array_equal(bpm[:,[names.index(c) for c in m['channels']['bpm']]],a['bpm'])
        for i in ('ltu','dump'):
            np.testing.assert_array_equal(s[i][1]['bpm_time_ns'],a['bpm_time_ns'])
            assert set(s[i][1])=={'bpm','bpm_time_ns'}

def test_split_folders_round_trip(tmp_path):
    split(tmp_path)
    for i in INSTRUMENTS:
        assert (tmp_path/i/'instrument.txt').read_text().strip()==i
        for e in event_ids():
            m,a=load_slice(e,i,tmp_path/i);m0,a0=load_slice(e,i)
            assert m==m0 and a.keys()==a0.keys()
            for k in a: np.testing.assert_array_equal(a[k],a0[k]);assert a[k].dtype==a0[k].dtype
    with pytest.raises(ValueError):load_slice('../evaluation_labels','rf',tmp_path/'rf')

def test_detect_local_instrument(tmp_path,monkeypatch):
    monkeypatch.delenv('SLAC_NODE_DATA_DIR',raising=False);monkeypatch.delenv('FLWR_FILESYSTEM_ALLOWED_DIRS',raising=False)
    assert detect_local_instrument() is None
    monkeypatch.setenv('FLWR_FILESYSTEM_ALLOWED_DIRS',str(tmp_path))
    assert detect_local_instrument() is None
    (tmp_path/'instrument.txt').write_text('dump\n');assert detect_local_instrument()=='dump'
    other=tmp_path/'o';other.mkdir();(other/'instrument.txt').write_text('ltu')
    monkeypatch.setenv('SLAC_NODE_DATA_DIR',str(other));assert detect_local_instrument()=='ltu'
    (other/'instrument.txt').write_text('bogus');assert detect_local_instrument() is None
