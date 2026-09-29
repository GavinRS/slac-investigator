#!/usr/bin/env python3
"""Load private provider settings without executing shell code, then run SuperLink."""
import os
from pathlib import Path
import stat
import shlex
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = 'https://api.flower.ai/v1/responses'
GATEWAY = ENDPOINT
DEFAULT_ENDPOINT = 'https://api.tokenfactory.tf-ca1.nebius.com/v1/responses'
DEFAULT_MODEL = 'dedicated/flowerai/MiniMax-M3-OOLI9o'
FLOWER_MODEL = 'flwrlabs/endeavor-1.0'


def read_configuration(key_file):
    if key_file.is_symlink():
        raise ValueError('Flower key file must not be a symlink.')
    info = key_file.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError('Flower key file must be owned by you with mode 600.')
    settings = {}
    for line in key_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('export '): line = line[7:]
        name, separator, value = line.partition('=')
        if not separator or name.strip() not in ('FLWR_MODEL_API_ENDPOINT', 'FLWR_MODEL_API_KEY', 'INVESTIGATOR_MODEL'):
            raise ValueError('Private configuration contains an unsupported setting.')
        tokens = shlex.split(value, comments=True)
        if len(tokens) > 1: raise ValueError('Private configuration values must be quoted.')
        settings[name.strip()] = tokens[0] if tokens else ''
    return settings


# Public compatibility name used by the provider configuration helpers.
read_env = read_configuration


def flower_environment(inherited, key_file):
    settings = read_configuration(key_file)
    endpoint = settings.get('FLWR_MODEL_API_ENDPOINT') or ENDPOINT
    parsed = urlparse(endpoint)
    local = parsed.hostname in ('localhost', '127.0.0.1', '::1')
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or (parsed.scheme == 'http' and not local) or parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.path.endswith('/responses'):
        raise ValueError('Provider must use a full HTTPS Responses URL, or local HTTP.')
    key = settings.get('FLWR_MODEL_API_KEY', '')
    if (not key and not local) or any(c.isspace() for c in key):
        raise ValueError('Private configuration requires a valid provider key.')
    model = settings.get('INVESTIGATOR_MODEL') or (FLOWER_MODEL if endpoint == ENDPOINT else DEFAULT_MODEL)
    if any(c.isspace() for c in model): raise ValueError('Invalid model identifier.')
    env = {k: v for k, v in inherited.items()
           if not k.startswith(('OPENAI_', 'FLWR_MODEL_', 'FLWR_RUNTIME_', 'PACTERRA_', 'INVESTIGATOR_'))}
    env.update(FLWR_MODEL_API_ENDPOINT=endpoint, FLWR_MODEL_API_KEY=key, INVESTIGATOR_MODEL=model,
               FLWR_HOME=str(ROOT / '.flower'), MPLBACKEND='Agg',
               MPLCONFIGDIR='/tmp/slac-mpl', XDG_CACHE_HOME='/tmp/slac-cache',
               PATH=str(ROOT / '.venv/bin') + os.pathsep + env.get('PATH', ''))
    return env


def main():
    try:
        env = flower_environment(os.environ, ROOT / '.env')
    except (OSError, ValueError):
        raise SystemExit('Private Flower configuration is missing or invalid. Run .venv/bin/python scripts/configure_flower.py in your terminal.') from None
    os.chdir(ROOT)
    (ROOT / 'artifacts').mkdir(exist_ok=True)
    (ROOT / '.flower').mkdir(exist_ok=True)
    os.execve(ROOT / '.venv/bin/flower-superlink', [
        'flower-superlink', '--insecure', '--host', '127.0.0.1',
        '--fleet-api-address', '127.0.0.1:19092',
        '--database', str(ROOT / '.flower/slac.sqlite'),
        '--disable-runtime-dependency-installation',
    ], env)


if __name__ == '__main__':
    main()
