"""Ensure stale provider settings cannot redirect Flower or supply its key."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('start_flower', Path(__file__).resolve().parents[1] / 'scripts/start_flower.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

STALE = {'FLWR_MODEL_API_ENDPOINT': 'https://api.openai.com/v1/responses',
         'FLWR_MODEL_API_KEY': 'test-old-placeholder',
         'OPENAI_API_KEY': 'test-openai-placeholder',
         'OPENAI_BASE_URL': 'https://wrong.example',
         'FLWR_RUNTIME_API_KEY': 'test-stale-runtime',
         'INVESTIGATOR_MODEL': 'stale/model',
         'PATH': '/usr/bin', 'UNRELATED_SETTING': 'preserved'}


def env_file(tmp_path, text, mode=0o600):
    path = tmp_path / '.env'
    path.write_text(text)
    path.chmod(mode)
    return path


def test_blank_endpoint_uses_flower_gateway_and_drops_stale_settings(tmp_path):
    path = env_file(tmp_path, '# comment\nFLWR_MODEL_API_ENDPOINT=\nexport FLWR_MODEL_API_KEY="test-flower-placeholder"\nOTHER=x\n')
    env = launcher.flower_environment(dict(STALE), path)
    assert env['FLWR_MODEL_API_ENDPOINT'] == 'https://api.flower.ai/v1/responses'
    assert env['FLWR_MODEL_API_KEY'] == 'test-flower-placeholder'
    assert not any(k.startswith(('OPENAI_', 'FLWR_RUNTIME_', 'INVESTIGATOR_')) for k in env)
    assert env['UNRELATED_SETTING'] == 'preserved' and 'OTHER' not in env


def test_custom_endpoint_and_model_reach_superlink(tmp_path):
    path = env_file(tmp_path, 'FLWR_MODEL_API_ENDPOINT=http://localhost:11434/v1/responses\nINVESTIGATOR_MODEL=gpt-oss:20b\n')
    env = launcher.flower_environment(dict(STALE), path)
    assert env['FLWR_MODEL_API_ENDPOINT'] == 'http://localhost:11434/v1/responses'
    assert env['INVESTIGATOR_MODEL'] == 'gpt-oss:20b'
    assert 'FLWR_MODEL_API_KEY' not in env


@pytest.mark.parametrize('text,match', [('FLWR_MODEL_API_ENDPOINT=\n', 'required'),
                                        ('FLWR_MODEL_API_ENDPOINT=https://x.example/v1\nFLWR_MODEL_API_KEY=k\n', '/responses')])
def test_invalid_configuration_rejected(tmp_path, text, match):
    with pytest.raises(ValueError, match=match):
        launcher.flower_environment(dict(STALE), env_file(tmp_path, text))


def test_missing_private_env_never_falls_back(tmp_path):
    with pytest.raises(FileNotFoundError):
        launcher.flower_environment(dict(STALE), tmp_path / 'missing')


def test_publicly_readable_env_rejected(tmp_path):
    with pytest.raises(ValueError, match='mode 600'):
        launcher.flower_environment({}, env_file(tmp_path, 'FLWR_MODEL_API_KEY=test-placeholder\n', 0o644))
