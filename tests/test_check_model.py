"""check_model.py: offline unit tests. The HTTP call is monkeypatched; no network."""
import importlib.util
import io
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('check_model', Path(__file__).resolve().parents[1] / 'scripts/check_model.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

SECRET = 'test-secret-placeholder-do-not-print'


def fake_urlopen(payload_or_error):
    def opener(request, timeout=None):
        if isinstance(payload_or_error, Exception):
            raise payload_or_error
        return io.BytesIO(json.dumps(payload_or_error).encode())
    return opener


def test_pass_on_function_call(monkeypatch):
    monkeypatch.setattr(checker.urllib.request, 'urlopen',
        fake_urlopen({'status':'completed', 'output': [{'type': 'function_call', 'name': 'ping', 'arguments':'{}'}]}))
    ok, reason, elapsed = checker.check('https://example.invalid/v1/responses', SECRET, 'test/model')
    assert ok and 'ping' in reason and elapsed >= 0
    assert SECRET not in reason


def test_fail_on_missing_function_call(monkeypatch):
    monkeypatch.setattr(checker.urllib.request, 'urlopen',
        fake_urlopen({'output': [{'type': 'message', 'content': 'hi'}]}))
    ok, reason, _ = checker.check('https://example.invalid/v1/responses', SECRET, 'test/model')
    assert not ok and 'function_call' in reason
    assert SECRET not in reason


def test_fail_on_http_error(monkeypatch):
    import urllib.error
    error = urllib.error.HTTPError('https://example.invalid/v1/responses', 401, 'Unauthorized', {}, None)
    monkeypatch.setattr(checker.urllib.request, 'urlopen', fake_urlopen(error))
    ok, reason, _ = checker.check('https://example.invalid/v1/responses', SECRET, 'test/model')
    assert not ok and '401' in reason
    assert SECRET not in reason


def test_fail_on_timeout(monkeypatch):
    monkeypatch.setattr(checker.urllib.request, 'urlopen', fake_urlopen(TimeoutError('timed out')))
    ok, reason, _ = checker.check('https://example.invalid/v1/responses', SECRET, 'test/model')
    assert not ok and 'timed out' in reason
    assert SECRET not in reason


def test_key_sent_in_header_but_never_in_reason(monkeypatch):
    seen = {}
    def opener(request, timeout=None):
        seen['auth'] = request.headers.get('Authorization')
        return io.BytesIO(json.dumps({'status':'completed', 'output': [{'type': 'function_call', 'name': 'ping', 'arguments':'{}'}]}).encode())
    monkeypatch.setattr(checker.urllib.request, 'urlopen', opener)
    ok, reason, _ = checker.check('https://example.invalid/v1/responses', SECRET, 'test/model')
    assert seen['auth'] == 'Bearer ' + SECRET
    assert SECRET not in reason


def test_load_config_private_file_overrides_stale_env(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    env_file.write_text('FLWR_MODEL_API_ENDPOINT=https://from-file.example/v1/responses\n'
                         'FLWR_MODEL_API_KEY=from-file\n'
                         'INVESTIGATOR_MODEL=from-file/model\n')
    env_file.chmod(0o600)
    endpoint, key, model = checker.load_config(env_file, {'INVESTIGATOR_MODEL': 'from-env/model', 'FLWR_MODEL_API_KEY':'stale'})
    assert endpoint == 'https://from-file.example/v1/responses'
    assert key == 'from-file'
    assert model == 'from-file/model'


def test_load_config_blank_endpoint_defaults_to_flower_gateway(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('FLWR_MODEL_API_ENDPOINT=\nFLWR_MODEL_API_KEY=test-placeholder\nINVESTIGATOR_MODEL=flwrlabs/endeavor-1.0\n')
    env_file.chmod(0o600)
    endpoint, key, model = checker.load_config(env_file, {})
    assert endpoint == checker.DEFAULT_ENDPOINT == 'https://api.flower.ai/v1/responses'
    assert key == 'test-placeholder'
    assert model == 'flwrlabs/endeavor-1.0'


def test_missing_model_fails_cleanly(monkeypatch, capsys):
    monkeypatch.setattr(checker, 'load_config', lambda: ('https://example.invalid', '', ''))
    assert checker.main([]) == 1
    out = capsys.readouterr().out
    assert 'FAIL' in out and SECRET not in out


def test_main_output_never_contains_key(monkeypatch, capsys):
    monkeypatch.setattr(checker, 'load_config', lambda: ('https://example.invalid', SECRET, 'test/model'))
    for result in ({'status':'completed', 'output': [{'type': 'function_call', 'name': 'ping', 'arguments':'{}'}]},
                   checker.urllib.error.HTTPError('https://example.invalid', 401, 'Unauthorized', {}, None),
                   ['not', 'a', 'dict']):
        monkeypatch.setattr(checker.urllib.request, 'urlopen', fake_urlopen(result))
        checker.main([])
        out = capsys.readouterr().out
        assert out.startswith(('PASS', 'FAIL')) and SECRET not in out


@pytest.mark.parametrize('payload', [
    {'status':'incomplete', 'output':[{'type':'function_call','name':'ping','arguments':'{}'}]},
    {'status':'completed', 'output':[{'type':'function_call','name':'other','arguments':'{}'}]},
    {'status':'completed', 'output':[{'type':'function_call','name':'ping','arguments':'{"unexpected":1}'}]},
])
def test_only_exact_completed_protocol_call_passes(monkeypatch, payload):
    monkeypatch.setattr(checker.urllib.request, 'urlopen', fake_urlopen(payload))
    assert not checker.check('https://example.invalid/v1/responses', SECRET, 'test/model')[0]


def test_exception_body_never_leaks(monkeypatch):
    monkeypatch.setattr(checker.urllib.request, 'urlopen', fake_urlopen(ValueError(SECRET)))
    ok, reason, _ = checker.check('https://example.invalid/v1/responses', SECRET, 'test/model')
    assert not ok and SECRET not in reason


def test_request_forces_readonly_ping(monkeypatch):
    seen = {}
    def opener(request, timeout=None):
        seen.update(json.loads(request.data))
        return io.BytesIO(json.dumps({'status':'completed', 'output':[{'type':'function_call','name':'ping','arguments':'{}'}]}).encode())
    monkeypatch.setattr(checker.urllib.request,'urlopen',opener)
    assert checker.check('https://example.invalid/v1/responses', SECRET, 'test/model')[0]
    assert seen['tool_choice'] == {'type':'function','name':'ping'}
