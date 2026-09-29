#!/usr/bin/env python3
"""Enter a provider credential privately, outside chat and shell history."""
import getpass
import json
import os
from pathlib import Path
import sys
import tempfile
import argparse
from start_flower import read_configuration, DEFAULT_MODEL, DEFAULT_ENDPOINT, ENDPOINT, FLOWER_MODEL

ROOT = Path(__file__).resolve().parents[1]
KEY_FILE = ROOT / '.env'
ENV_FILE = KEY_FILE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', help='Full Responses URL; empty means the Flower gateway.')
    parser.add_argument('--model', help='Provider model identifier.')
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise SystemExit('Run this script in your own interactive terminal; never paste a key into chat.')
    try:
        settings = read_configuration(KEY_FILE) if KEY_FILE.exists() else {}
    except (OSError, ValueError):
        raise SystemExit('Existing private configuration is invalid; unchanged.') from None
    settings['FLWR_MODEL_API_ENDPOINT'] = args.endpoint if args.endpoint is not None else settings.get('FLWR_MODEL_API_ENDPOINT', '' if KEY_FILE.exists() else DEFAULT_ENDPOINT)
    settings['INVESTIGATOR_MODEL'] = args.model or settings.get('INVESTIGATOR_MODEL') or (FLOWER_MODEL if not settings['FLWR_MODEL_API_ENDPOINT'] or settings['FLWR_MODEL_API_ENDPOINT'] == ENDPOINT else DEFAULT_MODEL)
    key = getpass.getpass('Provider API key (hidden; blank only for local endpoints): ').strip()
    if any(c.isspace() for c in key):
        raise SystemExit('No valid key entered; existing configuration is unchanged.')
    settings['FLWR_MODEL_API_KEY'] = key
    fd, temporary = tempfile.mkstemp(prefix='.env.flower-', dir=ROOT)
    try:
        with os.fdopen(fd, 'w') as output:
            for name, value in settings.items():
                output.write(name + '=' + json.dumps(value) + '\n')
        from start_flower import flower_environment
        try:
            flower_environment({}, Path(temporary))
        except ValueError:
            raise SystemExit('Provider settings are invalid; existing configuration is unchanged.') from None
        os.replace(temporary, KEY_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('Provider settings saved privately in .env (owner access only). Restart SuperLink to use them.')


if __name__ == '__main__':
    main()
