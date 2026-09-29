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
        fake_urlopen({'output': [{'type': 'function_call', 'name': 'ping'}]}))
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


def test_key_sent_but_never_in_reason_or_request(monkeypatch):
    seen = {}
    def opener(request, timeout=None):
        seen['auth'] = request.headers.get('Authorization')
        return io.BytesIO(json.dumps({'output': [{'type': 'function_call', 'name': 'ping'}]}).encode())
    monkeypatch.setattr(checker.urllib.request, 'urlopen', opener)
    ok, reason, _ = checker.check('https://example.invalid/v1/responses', SECRET, 'test/model')
    assert seen['auth'] == 'Bearer ' + SECRET
    assert SECRET not in reason


def test_load_config_env_overrides_file(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    env_file.write_text('FLWR_MODEL_API_ENDPOINT=https://from-file.example/v1/responses\n'
                         'FLWR_MODEL_API_KEY=from-file\n'
                         'INVESTIGATOR_MODEL=from-file/model\n')
    endpoint, key, model = checker.load_config(env_file, {'INVESTIGATOR_MODEL': 'from-env/model'})
    assert endpoint == 'https://from-file.example/v1/responses'
    assert key == 'from-file'
    assert model == 'from-env/model'


def test_load_config_blank_endpoint_defaults_to_flower_gateway(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('FLWR_MODEL_API_ENDPOINT=\nINVESTIGATOR_MODEL=flwrlabs/endeavor-1.0\n')
    endpoint, key, model = checker.load_config(env_file, {})
    assert endpoint == checker.DEFAULT_ENDPOINT == 'https://api.flower.ai/v1/responses'
    assert key == ''
    assert model == 'flwrlabs/endeavor-1.0'


def test_missing_model_fails_cleanly(monkeypatch, capsys):
    monkeypatch.setattr(checker, 'load_config', lambda: ('https://example.invalid', '', ''))
    assert checker.main() == 1
    out = capsys.readouterr().out
    assert 'FAIL' in out and SECRET not in out
