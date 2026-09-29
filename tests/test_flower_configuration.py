"""Ensure stale provider settings cannot redirect Flower or supply its key."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('start_flower', Path(__file__).resolve().parents[1] / 'scripts/start_flower.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_flower_overrides_stale_provider_configuration(tmp_path):
    key_file = tmp_path / 'key.json'
    key_file.write_text(json.dumps({'api_key': 'test-flower-placeholder'}))
    key_file.chmod(0o600)
    inherited = {'FLWR_MODEL_API_ENDPOINT': 'https://api.openai.com/v1/responses',
                 'FLWR_MODEL_API_KEY': 'test-old-placeholder',
                 'OPENAI_API_KEY': 'test-openai-placeholder',
                 'OPENAI_BASE_URL': 'https://wrong.example',
                 'PACTERRA_API_KEY': 'test-pacterra-placeholder',
                 'FLWR_RUNTIME_API_KEY': 'test-stale-runtime',
                 'PATH': '/usr/bin', 'UNRELATED_SETTING': 'preserved'}
    env = launcher.flower_environment(inherited, key_file)
    assert env['FLWR_MODEL_API_ENDPOINT'] == 'https://api.flower.ai/v1/responses'
    assert env['FLWR_MODEL_API_KEY'] == 'test-flower-placeholder'
    assert not any(k.startswith(('OPENAI_', 'PACTERRA_', 'FLWR_RUNTIME_')) for k in env)
    assert env['UNRELATED_SETTING'] == 'preserved'
    assert inherited['FLWR_MODEL_API_KEY'] == 'test-old-placeholder'


def test_missing_private_key_never_falls_back(tmp_path):
    with pytest.raises(FileNotFoundError):
        launcher.flower_environment({'FLWR_MODEL_API_KEY': 'test-old'}, tmp_path / 'missing')


def test_publicly_readable_key_rejected(tmp_path):
    key_file = tmp_path / 'key.json'
    key_file.write_text('{"api_key":"test-placeholder"}')
    key_file.chmod(0o644)
    with pytest.raises(ValueError, match='mode 600'):
        launcher.flower_environment({}, key_file)
