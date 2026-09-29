"""Ensure stale provider settings cannot redirect Flower or supply its key."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('start_flower', Path(__file__).resolve().parents[1] / 'scripts/start_flower.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_flower_overrides_stale_provider_configuration(tmp_path):
    key_file = tmp_path / '.env'
    key_file.write_text('FLWR_MODEL_API_KEY="test-flower-placeholder"\nFLWR_MODEL_API_ENDPOINT=""\nINVESTIGATOR_MODEL="fixture/model"\n')
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
    assert env['INVESTIGATOR_MODEL'] == 'fixture/model'
    assert not any(k.startswith(('OPENAI_', 'PACTERRA_', 'FLWR_RUNTIME_')) for k in env)
    assert env['UNRELATED_SETTING'] == 'preserved'
    assert inherited['FLWR_MODEL_API_KEY'] == 'test-old-placeholder'


def test_missing_private_key_never_falls_back(tmp_path):
    with pytest.raises(FileNotFoundError):
        launcher.flower_environment({'FLWR_MODEL_API_KEY': 'test-old'}, tmp_path / 'missing')


def test_publicly_readable_key_rejected(tmp_path):
    key_file = tmp_path / '.env'
    key_file.write_text('FLWR_MODEL_API_KEY="test-placeholder"')
    key_file.chmod(0o644)
    with pytest.raises(ValueError, match='mode 600'):
        launcher.flower_environment({}, key_file)


def test_custom_local_provider_does_not_inherit_cloud_key(tmp_path):
    key_file = tmp_path / '.env'
    key_file.write_text('FLWR_MODEL_API_ENDPOINT="http://127.0.0.1:11434/v1/responses"\nINVESTIGATOR_MODEL="local-model"\n')
    key_file.chmod(0o600)
    env = launcher.flower_environment({'FLWR_MODEL_API_KEY':'old-cloud-key'}, key_file)
    assert env['FLWR_MODEL_API_KEY'] == ''
    assert env['INVESTIGATOR_MODEL'] == 'local-model'


def test_config_never_executes_shell_substitution(tmp_path):
    key_file = tmp_path / '.env'
    key_file.write_text('FLWR_MODEL_API_KEY="$(do-not-execute)"\n')
    key_file.chmod(0o600)
    assert launcher.flower_environment({}, key_file)['FLWR_MODEL_API_KEY'] == '$(do-not-execute)'


def test_remote_provider_requires_its_own_private_key(tmp_path):
    key_file = tmp_path / '.env'
    key_file.write_text('FLWR_MODEL_API_ENDPOINT="https://provider.example/v1/responses"\n')
    key_file.chmod(0o600)
    with pytest.raises(ValueError, match='provider key'):
        launcher.flower_environment({'FLWR_MODEL_API_KEY':'inherited-key'}, key_file)


@pytest.mark.parametrize('endpoint', ['', 'https://api.flower.ai/v1/responses'])
def test_explicit_flower_endpoint_defaults_to_endeavor(tmp_path, endpoint):
    key_file = tmp_path / '.env'
    key_file.write_text('FLWR_MODEL_API_ENDPOINT=' + endpoint + '\nFLWR_MODEL_API_KEY=test-placeholder\n')
    key_file.chmod(0o600)
    env = launcher.flower_environment({'INVESTIGATOR_MODEL':'stale/model'}, key_file)
    assert env['INVESTIGATOR_MODEL'] == 'flwrlabs/endeavor-1.0'


def test_nebius_default_model_matches_explicit_nebius_endpoint(tmp_path):
    key_file = tmp_path / '.env'
    key_file.write_text('FLWR_MODEL_API_ENDPOINT=' + launcher.DEFAULT_ENDPOINT + '\nFLWR_MODEL_API_KEY=test-placeholder\n')
    key_file.chmod(0o600)
    env = launcher.flower_environment({}, key_file)
    assert env['INVESTIGATOR_MODEL'] == 'dedicated/flowerai/MiniMax-M3-OOLI9o'


def test_unknown_private_settings_are_not_silently_loaded(tmp_path):
    key_file = tmp_path / '.env'
    key_file.write_text('FLWR_MODEL_API_KEY=test-placeholder\nPACTERRA_API_KEY=stale\n')
    key_file.chmod(0o600)
    with pytest.raises(ValueError, match='unsupported'):
        launcher.flower_environment({}, key_file)


@pytest.mark.parametrize('existing', [False, True])
def test_private_helper_pairs_new_defaults_and_preserves_existing_flower(tmp_path, monkeypatch, existing):
    import sys
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location('configure_flower_fixture', scripts / 'configure_flower.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    path = tmp_path / '.env'
    if existing:
        path.write_text('FLWR_MODEL_API_KEY=test-original\n')
        path.chmod(0o600)
    monkeypatch.setattr(helper, 'ROOT', tmp_path)
    monkeypatch.setattr(helper, 'KEY_FILE', path)
    monkeypatch.setattr(sys, 'argv', ['configure_flower.py'])
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr(helper.getpass, 'getpass', lambda prompt: 'test-new-placeholder')
    helper.main()
    values = launcher.flower_environment({}, path)
    assert path.stat().st_mode & 0o777 == 0o600
    assert values['FLWR_MODEL_API_ENDPOINT'] == (launcher.ENDPOINT if existing else launcher.DEFAULT_ENDPOINT)
    assert values['INVESTIGATOR_MODEL'] == (launcher.FLOWER_MODEL if existing else launcher.DEFAULT_MODEL)
