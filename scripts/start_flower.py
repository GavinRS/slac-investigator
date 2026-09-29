#!/usr/bin/env python3
"""Launch SuperLink with an isolated, explicit Flower inference configuration."""
import json
import os
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = 'https://api.flower.ai/v1/responses'


def flower_environment(inherited, key_file):
    if key_file.is_symlink():
        raise ValueError('Flower key file must not be a symlink.')
    info = key_file.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError('Flower key file must be owned by you with mode 600.')
    key = json.loads(key_file.read_text()).get('api_key', '')
    if not isinstance(key, str) or not key or any(c.isspace() for c in key):
        raise ValueError('Flower key file does not contain a valid credential.')
    env = {k: v for k, v in inherited.items()
           if not k.startswith(('OPENAI_', 'FLWR_MODEL_', 'FLWR_RUNTIME_', 'PACTERRA_'))}
    env.update(FLWR_MODEL_API_ENDPOINT=ENDPOINT, FLWR_MODEL_API_KEY=key,
               FLWR_HOME=str(ROOT / '.flower'), MPLBACKEND='Agg',
               MPLCONFIGDIR='/tmp/slac-mpl', XDG_CACHE_HOME='/tmp/slac-cache',
               PATH=str(ROOT / '.venv/bin') + os.pathsep + env.get('PATH', ''))
    return env


def main():
    try:
        env = flower_environment(os.environ, ROOT / '.env.flower.json')
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
