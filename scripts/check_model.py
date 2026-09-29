#!/usr/bin/env python3
"""Check the private configured Responses provider with one forced tool call."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

# Also support importlib-based offline tests, without executing configuration.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from start_flower import ROOT, ENDPOINT, read_configuration, flower_environment

DEFAULT_ENDPOINT = ENDPOINT
PING_TOOL = {'type': 'function', 'name': 'ping', 'description': 'Trivial read-only protocol check.',
             'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False, 'required': []}}


def parse_env_file(path):
    """Use the same nonexecuting, owner-only parser as SuperLink startup."""
    return read_configuration(Path(path))


def load_config(env_path=None, environ=None):
    # Private file settings are authoritative; inherited provider settings never win.
    env = flower_environment(os.environ if environ is None else environ, Path(env_path) if env_path else ROOT / '.env')
    return env['FLWR_MODEL_API_ENDPOINT'], env['FLWR_MODEL_API_KEY'], env['INVESTIGATOR_MODEL']


def check(endpoint, key, model, timeout=120):
    """Return (ok, sanitized_reason, elapsed_seconds), never provider response text."""
    body = json.dumps({'model': model, 'input': [{'role': 'user', 'content': 'Call ping exactly once with no arguments.'}],
                       'tools': [PING_TOOL], 'tool_choice': {'type': 'function', 'name': 'ping'},
                       'max_output_tokens': 1024}).encode()
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    request = urllib.request.Request(endpoint, data=body, headers=headers, method='POST')
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
        calls = [item for item in payload.get('output', []) if item.get('type') == 'function_call']
        valid = (payload.get('status') == 'completed' and len(calls) == 1
                 and calls[0].get('name') == 'ping' and json.loads(calls[0].get('arguments', 'null')) == {})
        reason = 'Received completed ping function_call' if valid else 'Expected one completed ping function_call with empty arguments'
        return valid, reason, time.perf_counter() - started
    except urllib.error.HTTPError as exc:
        return False, f'HTTP {exc.code} from provider', time.perf_counter() - started
    except TimeoutError:
        return False, 'Request timed out', time.perf_counter() - started
    except Exception as exc:
        return False, type(exc).__name__, time.perf_counter() - started


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = {'passed': False}
    try:
        endpoint, key, model = load_config()
        if not model:
            raise ValueError('Missing model identifier')
        result.update(endpoint=endpoint, model=model)
        result['passed'], reason, result['latency_s'] = check(endpoint, key, model)
    except Exception as exc:
        result['error_type'] = type(exc).__name__
        result['latency_s'] = round(time.perf_counter() - started, 3)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: Model tool protocol' if result['passed'] else 'FAIL: Model tool protocol')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
