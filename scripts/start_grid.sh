#!/bin/sh
set +x
set -eu
cd "$(dirname "$0")/.."
exec .venv/bin/python scripts/start_grid.py "$@"
