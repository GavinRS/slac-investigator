#!/usr/bin/env python3
"""Launch SuperLink with the model provider from the private, git-ignored .env."""
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = 'https://api.flower.ai/v1/responses'
KEYS = ('FLWR_MODEL_API_ENDPOINT', 'FLWR_MODEL_API_KEY', 'INVESTIGATOR_MODEL')


def read_env(env_file):
    if env_file.is_symlink():
        raise ValueError('.env must not be a symlink.')
    info = env_file.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError('.env must be owned by you with mode 600 (chmod 600 .env).')
    values = {}
    for line in env_file.read_text().splitlines():
        name, sep, value = line.strip().removeprefix('export ').partition('=')
        if sep and name.strip() in KEYS:
            values[name.strip()] = value.strip().strip('\'"')
    return values


def flower_environment(inherited, env_file):
    cfg = read_env(env_file)
    endpoint, key = cfg.get('FLWR_MODEL_API_ENDPOINT', ''), cfg.get('FLWR_MODEL_API_KEY', '')
    if endpoint and not endpoint.rstrip('/').endswith('/responses'):
        raise ValueError('FLWR_MODEL_API_ENDPOINT must end with /responses.')
    if not endpoint and not key:
        raise ValueError('FLWR_MODEL_API_KEY is required for the Flower gateway.')
    if any(c.isspace() for c in key):
        raise ValueError('FLWR_MODEL_API_KEY is not a valid credential.')
    # Stale shell settings must never redirect SuperLink or supply its key.
    env = {k: v for k, v in inherited.items()
           if not k.startswith(('OPENAI_', 'FLWR_MODEL_', 'FLWR_RUNTIME_', 'INVESTIGATOR_'))}
    env.update(FLWR_MODEL_API_ENDPOINT=endpoint or GATEWAY,
               FLWR_HOME=str(ROOT / '.flower'), MPLBACKEND='Agg',
               MPLCONFIGDIR='/tmp/slac-mpl', XDG_CACHE_HOME='/tmp/slac-cache',
               PATH=str(ROOT / '.venv/bin') + os.pathsep + env.get('PATH', ''))
    if key:
        env['FLWR_MODEL_API_KEY'] = key
    if cfg.get('INVESTIGATOR_MODEL'):
        env['INVESTIGATOR_MODEL'] = cfg['INVESTIGATOR_MODEL']
    return env


def main():
    try:
        env = flower_environment(os.environ, ROOT / '.env')
    except OSError:
        raise SystemExit('No private .env found. Run .venv/bin/python scripts/configure_flower.py in your terminal.') from None
    except ValueError as exc:
        raise SystemExit(f'Invalid .env: {exc}') from None
    print('SuperLink model endpoint:', env['FLWR_MODEL_API_ENDPOINT'],
          '| model:', env.get('INVESTIGATOR_MODEL', 'app default'), file=sys.stderr)
    os.chdir(ROOT)
    (ROOT / 'artifacts').mkdir(exist_ok=True)
    (ROOT / '.flower').mkdir(exist_ok=True)
    # No --database: flwr 1.39's Alembic setup splits migration paths on spaces, so a
    # SQLite file under a path with spaces gets no tables. In-memory state works.
    os.execve(ROOT / '.venv/bin/flower-superlink', [
        'flower-superlink', '--insecure', '--host', '127.0.0.1',
        '--fleet-api-address', '127.0.0.1:19092',
        '--disable-runtime-dependency-installation',
    ], env)


if __name__ == '__main__':
    main()
