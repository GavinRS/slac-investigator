#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
export PATH="$PWD/.venv/bin:$PATH"
export FLWR_HOME="$PWD/.flower"
export MPLBACKEND=Agg MPLCONFIGDIR=/tmp/slac-mpl XDG_CACHE_HOME=/tmp/slac-cache
mkdir -p artifacts
exec flower-superlink --insecure --host 127.0.0.1 --fleet-api-address 127.0.0.1:19092 --disable-runtime-dependency-installation
