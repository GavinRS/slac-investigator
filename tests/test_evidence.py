import io,json,zipfile
import numpy as np
import pytest
from slac_assistant.data import load_event,ROOT
from slac_assistant.tools import analyze,timing_quality,sustained,beam_summary,equipment_summary
from slac_assistant.runtime import build_bundle

def test_epoch_precision_and_export_match():
    m,a=load_event('slac-001')
    with np.load(ROOT/'data/events/slac-001.npz') as raw:
        for k in raw.files:np.testing.assert_array_equal(a[k],raw[k])
    assert a['bpm_time_ns'].dtype==np.int64
    assert not a['bpm'].flags.writeable

def test_invalid_event_cannot_traverse():
    with pytest.raises(ValueError):load_event('../evaluation_labels')

def test_label_material_absent_from_bundle():
    b=build_bundle()
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        assert 'data/events/slac-001.arrays.json' in z.namelist()
        assert not any('labels' in n or n.startswith(('scripts/','artifacts/','data/raw/','nodes/')) for n in z.namelist())
        assert not any(part.startswith('.env') for n in z.namelist() for part in n.split('/'))
        for n in z.namelist():
            if n.startswith('data/'):
                text=z.read(n).decode();assert 'is_anom' not in text and 'anom_type' not in text

def test_no_timing_shift():
    result=analyze('slac-001','timing')['result']
    assert result['applied_shift_s']==0
    assert result['delay_is_approximate']
    assert result['recorded_rf_updates'][0]['relative_s']==0

def test_gaps_break_sustained_changes():
    t=np.arange(18,dtype=np.int64)*8_333_333;t[9:]+=1_000_000_000
    result=sustained(np.ones(18,bool),t)
    assert not result['sustained']
    assert result['longest_consecutive_samples']==9

def test_duplicates_and_reversal_reported():
    q=timing_quality(np.array([0,8_333_333,8_333_333,1],dtype=np.int64))
    assert q['duplicates']==1 and q['nonmonotonic']==1

def test_low_charge_positions_not_validated_by_sentinel():
    m,a=load_event('slac-001');result=beam_summary(m,a)
    row=next(x for x in result['channels'] if x['channel']=='BPMS:DMPH:502:Y')
    assert row['invalid_position_samples']>0
    assert not row['sustained']
    assert next(x for x in result['channels'] if x['channel']=='BPMS:DMPH:502:TMIT')['sustained']

def test_all_missing_rf_stays_unknown():
    m,a=load_event('slac-001');a['health']=np.full_like(a['health'],np.nan)
    result=equipment_summary(m,a)
    assert result['baseline_time_weighted_median'] is None
    assert result['max_abs_deviation_pct'] is None
    assert not result['suspicious']

def test_missing_beam_is_insufficient():
    m,a=load_event('slac-001');a['bpm']=np.full_like(a['bpm'],np.nan)
    result=beam_summary(m,a)
    assert not result['quality_adequate'] and not result['disturbance_detected']

def test_results_are_stable_and_json_safe():
    for kind in ['quality','equipment','beam','charge_validity','timing','neighbors']:
        one=analyze('slac-001',kind);two=analyze('slac-001',kind)
        assert one==two
        json.dumps(one,allow_nan=False)

def test_no_write_tool():
    with pytest.raises(ValueError):analyze('slac-001','set_amplitude')
