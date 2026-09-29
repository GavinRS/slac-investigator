"""Offline exporter fixtures, never presented as real model runs."""
import importlib.util
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('export_replay', Path(__file__).parents[1] / 'export_replay.py')
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def saved_report(execution_mode='model'):
    return {'report': {'event_id': 'slac-001', 'mode': 'grid', 'execution_mode': execution_mode,
                      'flower_run_id': '123', 'flower_series_id': '456', 'model': 'offline-fixture',
                      'runtime_status': 'status: "finished"\nsub_status: "completed"',
                      'final': {}, 'findings': [], 'evidence': [], 'metrics': {'accounting_complete': True},
                      'result_schema_version': 2, 'grid': {'nodes_seen': 3, 'assignment': {}, 'fallback': False},
                      'node_reports': [{'instrument': 'rf', 'tool_refs': ['T-rf']}],
                      'data_shared': {'percent_shared': 0.5, 'raw_samples_shared': 0, 'complete': True}},
            'events': [{'kind': 'node_report', 'report': {'instrument': 'rf'}},
                       {'kind': 'data_shared', 'data_shared': {'percent_shared': 0.5}},
                       {'kind': 'private_reasoning', 'text': 'excluded'}]}


def test_explicit_export_preserves_grid_schema_and_events(tmp_path):
    runs = tmp_path / 'runs'; runs.mkdir()
    (runs / '123.json').write_text(json.dumps(saved_report()))
    out = tmp_path / 'replay'
    exporter.build(['123'], out, runs)
    data = json.loads((out / 'slac-001.json').read_text())
    run = data['runs'][0]
    assert run['report']['mode'] == 'grid'
    assert run['report']['grid']['nodes_seen'] == 3
    assert run['report']['data_shared']['raw_samples_shared'] == 0
    assert [event['kind'] for event in run['events']] == ['node_report', 'data_shared']
    assert run['recorded_state'] == 'completed' and run['phase'] == 'initial'
    assert json.loads((out / 'manifest.json').read_text())['events'][0]['file'] == './slac-001.json'
    assert 'runtime_status' not in run['report']


@pytest.mark.parametrize('change', ['smoke', 'failed', 'missing-status', 'wrong-id'])
def test_explicit_export_rejects_unverified_model_completion_before_writing(tmp_path, change):
    data = saved_report()
    if change == 'smoke': data['report']['execution_mode'] = 'smoke'
    if change == 'failed': data['report']['runtime_status'] = 'status: "finished"\nsub_status: "failed"'
    if change == 'missing-status': data['report'].pop('runtime_status')
    if change == 'wrong-id': data['report']['flower_run_id'] = '999'
    (tmp_path / '123.json').write_text(json.dumps(data))
    out = tmp_path / 'replay'
    with pytest.raises(ValueError): exporter.build(['123'], out, tmp_path)
    assert not out.exists()


@pytest.mark.parametrize('private_value', [
    {'api_key': 'synthetic-private-value'},
    {'nested': [{'FLWR_MODEL_API_KEY': 'synthetic-private-value'}]},
    {'observation': 'Stored at /Users/example/private/file'},
    {'observation': 'Stored at /home/example/private/file'},
    {'observation': 'Bearer synthetic-private-value'},
    {'observation': 'sk-proj-synthetic-private-value'},
])
def test_export_fails_closed_for_nested_secrets_and_private_paths(tmp_path, private_value):
    data = saved_report()
    data['events'].append({'kind': 'started', 'extra': private_value})
    (tmp_path / '123.json').write_text(json.dumps(data))
    out = tmp_path / 'replay'
    with pytest.raises(ValueError, match='Export refused') as error:
        exporter.build(['123'], out, tmp_path)
    assert 'synthetic-private-value' not in str(error.value)
    assert not list(out.glob('*.json'))


def test_safe_usage_fields_are_not_mistaken_for_credentials():
    usage = {'input_tokens': 100, 'output_tokens': 200, 'tool_result_refs': ['T-rf']}
    assert exporter.screen_export(usage) == usage


def test_export_accepts_sanitized_completed_runtime_status(tmp_path):
    data = saved_report()
    data['report']['runtime_status'] = 'finished/completed'
    (tmp_path / '123.json').write_text(json.dumps(data))
    out = tmp_path / 'replay'
    exporter.build(['123'], out, tmp_path)
    assert (out / 'manifest.json').exists()


@pytest.mark.parametrize('section,field', [('data_shared', 'complete'), ('metrics', 'accounting_complete')])
def test_export_rejects_partial_successful_flower_run(tmp_path, section, field):
    data = saved_report()
    data['report']['runtime_status'] = 'finished/completed'
    data['report'][section][field] = False
    (tmp_path / '123.json').write_text(json.dumps(data))
    out = tmp_path / 'replay'
    with pytest.raises(ValueError, match='complete accounting'):
        exporter.build(['123'], out, tmp_path)
    assert not out.exists()
