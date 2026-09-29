#!/usr/bin/env python3
"""Enter a Flower credential privately, outside chat and shell history."""
import getpass
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
KEY_FILE = ROOT / '.env.flower.json'


def main():
    if not sys.stdin.isatty():
        raise SystemExit('Run this script in your own interactive terminal; never paste a key into chat.')
    key = getpass.getpass('Flower API key (hidden): ').strip()
    if not key or any(c.isspace() for c in key):
        raise SystemExit('No valid key entered; existing configuration is unchanged.')
    fd, temporary = tempfile.mkstemp(prefix='.env.flower-', dir=ROOT)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump({'api_key': key}, output)
            output.write('\n')
        os.replace(temporary, KEY_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('Flower key saved privately (owner access only). Restart SuperLink to use it.')


if __name__ == '__main__':
    main()
