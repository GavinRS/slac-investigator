import numpy as np
import pytest

from slac_assistant.data import event_ids, load_event
from slac_assistant.instruments import INSTRUMENTS, detect_local_instrument, load_slice
from scripts.split_nodes import split_nodes


@pytest.mark.parametrize('event_id', event_ids())
def test_slices_partition_every_channel_and_preserve_time(event_id):
    meta, arrays = load_event(event_id)
    found = []
    for instrument in INSTRUMENTS:
        sliced, values = load_slice(event_id, instrument)
        family = 'health' if instrument == 'rf' else 'bpm'
        assert set(values) == {family, family + '_time_ns'}
        for j, channel in enumerate(sliced['channels'][family]):
            original = meta['channels'][family].index(channel)
            np.testing.assert_array_equal(values[family][:, j], arrays[family][:, original])
            found.append(channel)
        np.testing.assert_array_equal(values[family + '_time_ns'], arrays[family + '_time_ns'])
        assert values[family + '_time_ns'].dtype == np.int64
        assert not any(a.flags.writeable for a in values.values())
    assert sorted(found) == sorted(meta['channels']['health'] + meta['channels']['bpm'])
    assert len(set(found)) == len(found)


def test_split_local_roundtrip_and_role_detection(tmp_path, monkeypatch):
    split_nodes(tmp_path)
    monkeypatch.delenv('SLAC_NODE_DATA_DIR', raising=False)
    monkeypatch.setenv('FLWR_FILESYSTEM_ALLOWED_DIRS', str(tmp_path / 'rf') + ',' + str(tmp_path / 'dump'))
    assert detect_local_instrument() == 'rf'
    monkeypatch.setenv('SLAC_NODE_DATA_DIR', str(tmp_path / 'ltu'))
    assert detect_local_instrument() == 'ltu'
    for instrument in INSTRUMENTS:
        meta, arrays = load_slice('slac-001', instrument)
        local_meta, local_arrays = load_slice('slac-001', instrument, tmp_path / instrument)
        assert meta == local_meta
        for key, value in arrays.items():
            np.testing.assert_array_equal(value, local_arrays[key])
    (tmp_path / 'ltu' / 'instrument.txt').write_text('invalid')
    assert detect_local_instrument() is None
    monkeypatch.setenv('SLAC_NODE_DATA_DIR', str(tmp_path / 'missing'))
    assert detect_local_instrument() is None


@pytest.mark.parametrize('event,instrument', [('../secret', 'rf'), ('slac-001', '../rf'), ('slac-999', 'rf')])
def test_reject_unknown_event_and_instrument(event, instrument):
    with pytest.raises(ValueError):
        load_slice(event, instrument)
