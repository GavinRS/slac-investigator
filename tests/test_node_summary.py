import json
import numpy as np
import pytest

from slac_assistant.data import event_ids
from slac_assistant.instruments import INSTRUMENTS, load_slice
from slac_assistant.tools import node_summary, serialize_node_report


def assert_compact(value):
    if isinstance(value, dict):
        for child in value.values():
            assert_compact(child)
    elif isinstance(value, list):
        assert len(value) <= 10
        for child in value:
            assert_compact(child)
    else:
        assert value is None or isinstance(value, (int, float))


@pytest.mark.parametrize('event_id', event_ids())
@pytest.mark.parametrize('instrument', INSTRUMENTS)
def test_report_is_compact_deterministic_and_exactly_counted(event_id, instrument):
    meta, arrays = load_slice(event_id, instrument)
    report = node_summary(event_id, instrument, arrays, meta=meta)
    assert report == node_summary(event_id, instrument, arrays, meta=meta)
    assert_compact(report['summary'])
    payload = serialize_node_report(report)
    assert len(payload.encode('utf-8')) == report['payload_bytes']
    assert json.loads(payload) == report
    assert report['raw_bytes_held'] == sum(a.nbytes for a in arrays.values())
    assert report['payload_bytes'] < report['raw_bytes_held']
    assert len(report['tool_refs']) == 3
    assert set(report) == {'kind', 'instrument', 'role_source', 'event_id', 'assessment', 'observation', 'summary', 'tool_refs', 'raw_bytes_held', 'payload_bytes', 'limitations'}


def test_missing_evidence_is_insufficient():
    for instrument in INSTRUMENTS:
        meta, arrays = load_slice('slac-001', instrument)
        family = 'health' if instrument == 'rf' else 'bpm'
        arrays[family] = np.full_like(arrays[family], np.nan)
        report = node_summary('slac-001', instrument, arrays, 'local_data', meta=meta)
        assert report['assessment'] == 'insufficient_evidence'
        assert report['role_source'] == 'local_data'


def test_dump_masks_invalid_positions_without_hiding_charge_disturbance():
    meta, arrays = load_slice('slac-001', 'dump')
    report = node_summary('slac-001', 'dump', arrays, meta=meta)
    channels = report['summary']['channels']
    position = channels['BPMS:DMPH:502:Y']
    assert position['masked_samples'] > 0
    assert position['sustained'] == 0
    assert channels['BPMS:DMPH:502:TMIT']['sustained'] == 1


def test_cannot_run_other_instrument_checks():
    meta, arrays = load_slice('slac-001', 'dump')
    with pytest.raises(ValueError):
        node_summary('slac-001', 'ltu', arrays, meta=meta)


def test_utf8_payload_size_updates_after_model_observation():
    meta, arrays = load_slice('slac-001', 'rf')
    report = node_summary('slac-001', 'rf', arrays, meta=meta)
    report['observation'] = 'Δ amplitude — check RF.'
    assert len(serialize_node_report(report).encode('utf-8')) == report['payload_bytes']
