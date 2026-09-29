#!/bin/sh
set +x
set -eu
cd "$(dirname "$0")/.."
# Model endpoint, key and INVESTIGATOR_MODEL come from the private .env.
exec .venv/bin/python scripts/start_flower.py
