#!/usr/bin/env python3
"""Enter the model API key privately (outside chat and shell history) into .env."""
import getpass
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / '.env'


def main():
    if not sys.stdin.isatty():
        raise SystemExit('Run this script in your own interactive terminal; never paste a key into chat.')
    key = getpass.getpass('Model API key for FLWR_MODEL_API_KEY (hidden): ').strip()
    if not key or any(c.isspace() for c in key):
        raise SystemExit('No valid key entered; existing configuration is unchanged.')
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    lines = [l for l in lines if l.strip().removeprefix('export ').partition('=')[0].strip() != 'FLWR_MODEL_API_KEY']
    fd, temporary = tempfile.mkstemp(prefix='.env-', dir=ROOT)  # created with mode 600
    try:
        with os.fdopen(fd, 'w') as output:
            output.write('\n'.join(lines + [f'FLWR_MODEL_API_KEY={key}']) + '\n')
        os.replace(temporary, ENV_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('Key saved to .env (owner access only). Set FLWR_MODEL_API_ENDPOINT and INVESTIGATOR_MODEL there; restart SuperLink to use them.')


if __name__ == '__main__':
    main()
