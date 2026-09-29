#!/bin/sh
set +x
set -eu
cd "$(dirname "$0")/.."
# Keep the previous .env.local intact; Flower credentials are isolated from it.
exec .venv/bin/python scripts/start_flower.py
