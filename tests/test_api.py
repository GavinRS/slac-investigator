"""API contract tests use a protocol fixture; no paid model calls."""
import json
from pathlib import Path
import threading
import time

from fastapi.testclient import TestClient
import pytest

from slac_assistant.api import create_app, public
from slac_assistant.workflow import Investigation


class Runner:
    def __init__(self, gate=None, error=None):
        self.calls = []
        self.gate = gate
        self.error = error

    def __call__(self, event_id, **kwargs):
        self.calls.append((event_id, kwargs))
        run_id = str(100 + len(self.calls))
        sid = kwargs['series_id'] or 18337307573841650565
        kwargs['on_started'](run_id, sid)
        kwargs['on_event']({'kind': 'started', 'time_ns': 1604277203201922048})
        if self.gate:
            assert self.gate.wait(5)
        if self.error:
            raise RuntimeError(self.error)
        report = Investigation(event_id, kwargs['on_event']).smoke()
        report.update(flower_run_id=run_id, flower_series_id=str(sid), runtime_status='internal')
        return report, sid


def terminal(client, job):
    for _ in range(250):
        state = client.get(job['links']['status']).json()
        if state['status'] in ('completed', 'failed', 'interrupted'):
            return state
        time.sleep(.01)
    raise AssertionError('fixture did not complete')


def test_start_poll_result_and_same_series_followup(tmp_path):
    runner = Runner()
    with TestClient(create_app(tmp_path/'api.db', runner)) as client:
        response = client.post('/api/v1/investigations', json={'event_id':'slac-001'})
        assert response.status_code == 202
        job = response.json()
        assert response.headers['location'] == job['links']['status']
        assert terminal(client, job)['status'] == 'completed'
        page = client.get(job['links']['activity'], params={'limit':2}).json()
        assert page['events'][0]['event']['time_ns'] == '1604277203201922048'
        assert page['has_more'] and page['next_cursor'] == 2
        next_page = client.get(job['links']['activity'], params={'after':2}).json()
        assert next_page['events'][0]['seq'] == 3
        result = client.get(job['links']['result']).json()['report']
        assert result['benchmark_eligible'] is False
        assert 'assessment' not in result['final'] and 'runtime_status' not in result
        assert set(('beam_disturbance','unique_cause')) <= result['final'].keys()
        assert isinstance(result['final']['time_interval_ns'][0], str)
        follow = client.post(job['links']['followup'], json={'question':'Could low charge explain the positions?'}).json()
        assert terminal(client, follow)['status'] == 'completed'
        assert follow['series_id'] == job['series_id']
        assert runner.calls[1][1]['series_id'] == 18337307573841650565
        assert runner.calls[1][1]['question'] == 'Could low charge explain the positions?'
        assert runner.calls[0][1]['model'] == runner.calls[1][1]['model']


def test_pending_result_and_overlapping_followup_are_rejected(tmp_path):
    gate = threading.Event()
    runner = Runner(gate)
    with TestClient(create_app(tmp_path/'api.db', runner)) as client:
        job = client.post('/api/v1/investigations', json={'event_id':'slac-001'}).json()
        try:
            assert client.get(job['links']['result']).status_code == 409
            assert client.post(job['links']['followup'], json={'question':'Check again'}).status_code == 409
        finally:
            gate.set()
        assert terminal(client, job)['status'] == 'completed'
        gate.clear()
        first = client.post(job['links']['followup'], json={'question':'First'}).json()
        try:
            assert client.post(job['links']['followup'], json={'question':'Second'}).status_code == 409
        finally:
            gate.set()
        assert terminal(client, first)['status'] == 'completed'
        assert len(runner.calls) == 2


@pytest.mark.parametrize('message,code', [
    ('Model API key is not set (FLWR_MODEL_API_KEY).', 'missing_environment'),
    ('401 invalid_api_key sk-test-secret', 'credential_rejected'),
    ('429 insufficient_quota', 'billing_quota'),
    ('404 model_not_found', 'model_unavailable'),
    ('429 rate_limit_exceeded', 'rate_limited'),
    ('Unexpected SDK error sk-test-secret', 'workflow_failed'),
])
def test_failure_is_sanitized_and_never_retried(tmp_path, message, code):
    runner = Runner(error=message)
    with TestClient(create_app(tmp_path/'api.db', runner)) as client:
        job = client.post('/api/v1/investigations', json={'event_id':'slac-001'}).json()
        state = terminal(client, job)
        assert state['status'] == 'failed' and state['error']['code'] == code
        assert len(runner.calls) == 1
        responses = [state, client.get(job['links']['activity']).json(), client.get(job['links']['result']).json()]
        assert 'sk-test-secret' not in json.dumps(responses)
        assert client.post(job['links']['followup'], json={'question':'Again'}).status_code == 409
    assert b'sk-test-secret' not in (tmp_path/'api.db').read_bytes()


def test_input_validation_does_not_echo_keys_or_accept_overrides(tmp_path):
    runner = Runner()
    with TestClient(create_app(tmp_path/'api.db', runner)) as client:
        for extra in ({'api_key':'sk-secret'}, {'model':'arbitrary'}, {'provider':'nebius-chat'}, {'address':'https://example.com'}):
            response = client.post('/api/v1/investigations', json={'event_id':'slac-001', **extra})
            assert response.status_code == 422 and 'sk-secret' not in response.text
        assert client.post('/api/v1/investigations', json={'event_id':'slac-999'}).status_code == 404
        assert client.post('/api/v1/series/missing/follow-ups', json={'question':' '}).status_code == 422
        assert client.get('/api/v1/investigations/missing').status_code == 404
        assert not runner.calls


def test_restart_preserves_results_and_interrupts_unfinished_jobs(tmp_path):
    path = tmp_path/'api.db'
    app = create_app(path, Runner())
    with TestClient(app) as client:
        job = client.post('/api/v1/investigations', json={'event_id':'slac-001'}).json()
        terminal(client, job)
    app.state.store.update(job['id'], status='running')
    runner = Runner()
    with TestClient(create_app(path, runner)) as client:
        assert client.get(job['links']['status']).json()['status'] == 'interrupted'
        assert client.get(job['links']['activity']).json()['events']
        assert not runner.calls
    # A separately completed record stays readable across API restarts.
    app.state.store.update(job['id'], status='completed', error=None)
    with TestClient(create_app(path, Runner())) as client:
        assert client.get(job['links']['result']).status_code == 200


def test_smoke_followup_rejected_and_public_redaction(tmp_path, monkeypatch):
    monkeypatch.setenv('TEST_API_KEY', 'very-private-value')
    assert public({'api_key':'secret', 'observation':'very-private-value sk-secret'}) == {'observation':'[REDACTED] [REDACTED]'}
    with TestClient(create_app(tmp_path/'api.db', Runner())) as client:
        job = client.post('/api/v1/investigations', json={'event_id':'slac-001','mode':'smoke'}).json()
        terminal(client, job)
        assert client.post(job['links']['followup'], json={'question':'Why?'}).status_code == 409


def test_grid_mode_accepted_and_node_events_pass_through_intact(tmp_path):
    def grid_runner(event_id, **kwargs):
        kwargs['on_started']('500', 999)
        node_report = {'kind': 'node_report', 'instrument': 'rf', 'role_source': 'local_data',
                       'event_id': event_id, 'assessment': 'suspicious', 'observation': 'RF deviation noted.',
                       'summary': {'baseline': 1.0, 'peak_deviation': 2.5}, 'tool_refs': ['T-rf-1'],
                       'raw_bytes_held': 123456, 'payload_bytes': 512, 'limitations': []}
        data_shared = {'kind': 'data_shared', 'raw_bytes_held': 123456, 'payload_bytes': 512, 'percent_shared': 0.41}
        kwargs['on_event']({'kind': 'delegation', 'node_id': 7, 'instrument': 'rf'})
        kwargs['on_event'](node_report)
        kwargs['on_event'](data_shared)
        report = Investigation(event_id, kwargs['on_event']).smoke()
        report.update(mode='grid', flower_run_id='500', flower_series_id='999', runtime_status='internal',
                      grid={'nodes_seen': 3, 'assignment': {'rf':'node-1','ltu':'node-2','dump':'node-3'}, 'fallback': None},
                      data_shared=data_shared)
        return report, 999

    with TestClient(create_app(tmp_path/'api.db', grid_runner)) as client:
        response = client.post('/api/v1/investigations', json={'event_id':'slac-001', 'mode':'grid'})
        assert response.status_code == 202
        job = response.json()
        assert job['mode'] == 'grid'
        assert terminal(client, job)['status'] == 'completed'
        events = client.get(job['links']['activity']).json()['events']
        by_kind = {e['event']['kind']: e['event'] for e in events}
        assert by_kind['node_report'] == {'kind': 'node_report', 'instrument': 'rf', 'role_source': 'local_data',
                       'event_id': 'slac-001', 'assessment': 'suspicious', 'observation': 'RF deviation noted.',
                       'summary': {'baseline': 1.0, 'peak_deviation': 2.5}, 'tool_refs': ['T-rf-1'],
                       'raw_bytes_held': 123456, 'payload_bytes': 512, 'limitations': []}
        assert by_kind['delegation'] == {'kind': 'delegation', 'node_id': 7, 'instrument': 'rf'}
        assert by_kind['data_shared'] == {'kind': 'data_shared', 'raw_bytes_held': 123456, 'payload_bytes': 512, 'percent_shared': 0.41}
        report = client.get(job['links']['result']).json()['report']
        assert report['mode'] == 'grid'
        assert report['grid'] == {'nodes_seen': 3, 'assignment': {'rf':'node-1','ltu':'node-2','dump':'node-3'}, 'fallback': None}
        assert report['data_shared'] == {'kind': 'data_shared', 'raw_bytes_held': 123456, 'payload_bytes': 512, 'percent_shared': 0.41}


def test_cors_and_trusted_host_stay_localhost_only(tmp_path):
    with TestClient(create_app(tmp_path/'api.db', Runner())) as client:
        assert client.get('/api/v1/events', headers={'host': 'evil.example.com'}).status_code == 400
        blocked = client.get('/api/v1/events', headers={'Origin': 'https://evil.example.com'})
        assert blocked.status_code == 200 and 'access-control-allow-origin' not in blocked.headers
        allowed = client.get('/api/v1/events', headers={'Origin': 'http://localhost:5173'})
        assert allowed.headers['access-control-allow-origin'] == 'http://localhost:5173'


def test_plot_preserves_exact_timestamps_and_masks_invalid_positions(tmp_path):
    with TestClient(create_app(tmp_path/'api.db', Runner())) as client:
        meta = client.get('/api/v1/events/slac-001').json()
        assert isinstance(meta['candidate_start_ns'], str)
        assert 'is_anom' not in meta
        plot = client.get('/api/v1/events/slac-001/plot').json()
        assert not plot['downsampled']
        traces = {t['channel']:t for t in plot['traces']}
        position = traces['BPMS:DMPH:502:Y']
        charge = traces['BPMS:DMPH:502:TMIT']
        assert any(v is None for v in position['values'])
        assert all(p is None for p,c in zip(position['values'],charge['values']) if c is not None and c<1e8)
        assert len(position['time_ns']) == len(position['relative_s']) == len(position['values'])
        assert all(isinstance(t,str) for t in position['time_ns'])
        assert client.get('/api/v1/events/slac-999/plot').status_code == 404
        assert client.get('/api/v1/events/slac-999').status_code == 404
