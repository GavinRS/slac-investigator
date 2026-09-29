#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
# The API receives the model choice, never the provider key.
exec .venv/bin/python scripts/start_api.py
