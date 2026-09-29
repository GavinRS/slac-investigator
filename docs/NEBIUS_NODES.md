# Instrument SuperNodes on Nebius Serverless

Runs the three instrument SuperNodes (`rf`, `ltu`, `dump`) as Nebius Serverless AI endpoints registered to SuperGrid. Each node holds only its own instrument folder, so the node agent reports `role_source=local_data` (spec §1, §9). If this is blocked, the local 3-node runtime (`scripts/start_grid.sh`, spec §6) is the fallback.

Never commit keys, tokens or private key files. `nebius-supernode-key-*` is gitignored. Everything in `<angle brackets>` is a placeholder.

## 0. Instrument folders

`scripts/split_nodes.py` (issue #1) writes one folder per instrument:

```text
nodes/rf/     nodes/ltu/     nodes/dump/
```

Each has per-event slice files plus `instrument.txt` naming the instrument. `nodes/` is generated and gitignored. Upload each folder only to its own node.

## 1. Log in and make one key per node

Run from the repo root (the key files land here and are ignored by git):

```sh
flwr login supergrid

ssh-keygen -t ecdsa -b 384 -N "" -f nebius-supernode-key-rf
ssh-keygen -t ecdsa -b 384 -N "" -f nebius-supernode-key-ltu
ssh-keygen -t ecdsa -b 384 -N "" -f nebius-supernode-key-dump

flwr supernode register nebius-supernode-key-rf.pub supergrid
flwr supernode register nebius-supernode-key-ltu.pub supergrid
flwr supernode register nebius-supernode-key-dump.pub supergrid
```

Note each node ID that `register` prints.

## 2. Create one endpoint per node

console.nebius.com → Serverless AI → Endpoints → Create Endpoint. Repeat for `rf`, `ltu`, `dump`, replacing `<instrument>` each time.

| Field | Value |
|---|---|
| Configuration | Custom |
| Image | `docker.io/flwr/supernode:1.39.0-py3.12-ubuntu24.04` |
| Port | `9092`, TCP |
| Entrypoint (single line) | see below |
| Files | `nebius-supernode-key-<instrument>` (private key) mounted at `/tmp/nebius-supernode-key-<instrument>` |
| Files | contents of `nodes/<instrument>/` mounted at `/data/<instrument>/` |
| Environment variables | `SLAC_NODE_DATA_DIR=/data/<instrument>` |
| Secret environment variables | `FLWR_MODEL_API_KEY=<Flower API key>` (leave `FLWR_MODEL_API_ENDPOINT` unset) |
| Compute | CPU preset is fine (no training). Otherwise the default. |
| Network | Public |

Entrypoint:

```sh
exec flower-supernode --superlink=fleet-supergrid.flower.ai:443 --auth-supernode-private-key=/tmp/nebius-supernode-key-<instrument> --allow-runtime-dependency-installation
```

### Model access on the node

Default (Endeavor bonus): only `FLWR_MODEL_API_KEY=<Flower API key>` (flower.ai → Profile → Settings → API Keys). No endpoint means Flower's default gateway. Run with model `flwrlabs/endeavor-1.0`.

Fallback (Nebius Token Factory), both as secret env vars:

```text
FLWR_MODEL_API_ENDPOINT=https://api.tokenfactory.tf-ca1.nebius.com/v1/responses
FLWR_MODEL_API_KEY=<Nebius Token Factory event key>
```

with a Token Factory model ID from the spec §5 table (e.g. `dedicated/flowerai/MiniMax-M3-OOLI9o`).

## 3. Confirm the nodes are online

```sh
flwr supernode list supergrid --verbose
```

All three should show as online. If they are not in the federation you run in, add each one:

```sh
flwr federation add-supernode <node-id> <federation> supergrid
```

## 4. Run through `flwr chat`

```sh
flwr chat
```

Then inside the chat:

```text
/load <absolute path to this repo>
/federation        # pick the federation the three nodes joined
```

Ask for a smoke run of one event (e.g. `slac-001`). Done when the orchestrator's `get_nodes` lists the 3 Nebius nodes and every `node_report` has `role_source=local_data`. `role_source=assigned` means the node did not find its folder: check the `/data/<instrument>/` mount, `instrument.txt` and `SLAC_NODE_DATA_DIR`.

## Version

Use the `1.39.0` SuperNode image (it matches the repo's pinned flwr 1.39.0). Flower's guide shows `1.37.0`; with that image the node agent may lack `push_reply_message`, and the node path falls back to `push_messages`.

## Tear down

Delete the three endpoints in the Nebius console, then `flwr supernode unregister <node-id> supergrid` for each. Delete the local `nebius-supernode-key-*` files.
