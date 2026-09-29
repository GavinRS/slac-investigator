#!/bin/sh
# 1 SuperLink + 3 SuperNodes (rf, ltu, dump), each seeing only nodes/<instrument>/. Ctrl+C stops all.
set -eu
cd "$(dirname "$0")/.."
if [ -f .env ]; then set -a; . ./.env; set +a; fi
export PATH="$PWD/.venv/bin:$PATH"
export MPLBACKEND=Agg MPLCONFIGDIR=/tmp/slac-mpl XDG_CACHE_HOME=/tmp/slac-cache
if [ -f scripts/split_nodes.py ]; then PYTHONPATH=. python scripts/split_nodes.py; else echo "scripts/split_nodes.py missing; nodes/ not refreshed"; fi
pids=""
trap 'kill $pids 2>/dev/null; wait' INT TERM EXIT
# Same SuperLink setup as start.sh, so the model key reaches the SuperLink. No key: smoke mode only.
if [ -f .env ] && grep -qE '^(export[[:space:]]+)?FLWR_MODEL_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]]' .env; then
  python scripts/start_flower.py & pids="$pids $!"
else echo "No model key configured: smoke mode only (see scripts/configure_flower.py)."
  mkdir -p .flower; FLWR_HOME="$PWD/.flower" flower-superlink --insecure --host 127.0.0.1 --fleet-api-address 127.0.0.1:19092 --database "$PWD/.flower/slac.sqlite" --disable-runtime-dependency-installation & pids="$pids $!"
fi
port=9094
for i in rf ltu dump; do
  mkdir -p "nodes/$i"
  SLAC_NODE_DATA_DIR="$PWD/nodes/$i" FLWR_FILESYSTEM_ALLOWED_DIRS="$PWD/nodes/$i" \
    flower-supernode --insecure --superlink 127.0.0.1:19092 --port $port & pids="$pids $!"
  port=$((port+1))
done
wait
