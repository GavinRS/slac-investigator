# SLAC instrument Grid investigator

A human-supervised replay tool for four public SLAC RF events. RF, LTU and dump instrument agents run read-only checks on their own data slices and send compact summaries through Flower's Grid. A lead combines them into Finding v2: separate **beam disturbance** and **unique cause** assessments, each with rationale and evidence references. The existing single-process investigator is the baseline.

This is a four-case demonstration, not an accuracy benchmark. Source RF anomaly labels do not adjudicate the two assessment dimensions. A local Grid demonstrates separate processes and summary-only messaging; bundled fallback data means it is not a filesystem security boundary.

## Local setup

Python 3.11+, uv, and Flower **1.39.0** are required:

```sh
uv sync
.venv/bin/python scripts/configure_flower.py
./scripts/start_grid.sh
```

The credential helper uses hidden terminal input and private, gitignored local storage. Never paste a key into chat, command arguments or source code. The default provider is Flower's Responses endpoint, `https://api.flower.ai/v1/responses`, with Endeavor (`flwrlabs/endeavor-1.0`). Startup reads the explicit local provider configuration and passes it to SuperLink; it must not inherit unrelated provider credentials. See `.env.example` for `FLWR_MODEL_API_ENDPOINT`, `FLWR_MODEL_API_KEY` and `INVESTIGATOR_MODEL`. A blank endpoint selects Flower's gateway. Agent code uses only Flower's injected runtime endpoint and credential.

The Grid supervisor starts an independent SuperLink on **127.0.0.1:18000** and three instrument nodes. Existing port-8000 services stay untouched. Stop the demo processes with **Ctrl+C** in the supervisor terminal. See [Grid runtime instructions](docs/GRID_RUNTIME.md) for routing, ports and data-locality limits.

In another terminal:

```sh
.venv/bin/python -m slac_assistant.runtime --address http://127.0.0.1:18000 --mode smoke --event slac-001
.venv/bin/python scripts/check_model.py
.venv/bin/python -m slac_assistant.runtime --address http://127.0.0.1:18000 --mode grid --event slac-001
```

Smoke requests exercise deterministic Grid routing without model calls. Their reports carry `mode: grid` and `execution_mode: smoke`; they are never treated as model results. A model request uses `mode: grid`, `execution_mode: model`. Failed model runs never silently become smoke results. Completed runtime traces are written locally under `artifacts/runs/`; use the actual trace and terminal outcome to establish live verification status.

## Demo surfaces and team handoff

**Fieldnote** in `frontend/` is the demo UI, with local live operation and recorded-run replay. The FastAPI job API, documented in [docs/API.md](docs/API.md), supports investigation creation with `mode: grid`, durable status/activity polling and same-series follow-ups under `/api/v1`. API and Fieldnote integration are owned separately; the frozen Grid contract below is the dependency handoff. GitHub Pages deployment is a separate manual step; see the frontend deployment instructions.

For local live Fieldnote against the three-node Grid, start the API with `FLOWER_CONTROL_URL=http://127.0.0.1:18000 ./scripts/start_api.sh`. Its default port-8000 target is the separate developer runtime; the explicit address connects the API to the Grid supervisor.

The report keeps Finding v2 in `final`/`findings`, with `result_schema_version: 2`, `mode: grid`, `grid: {nodes_seen, assignment, fallback}`, `node_reports`, `data_shared` and `metrics`. Grid adds `node_report` and `data_shared` events while preserving the existing event framing. Consumers should distinguish `execution_mode: smoke` and explicitly display fallback. Instrument replies contain assessments, numeric summaries, tool references and byte counts; no raw sample arrays.

A completed three-node Endeavor `slac-001` run, **2134321731300912044**, is preserved as a separate [Grid replay manifest](frontend/grid-replay/manifest.json). Serve `frontend/` locally and open `http://127.0.0.1:5173/?manifest=./grid-replay/manifest.json`. It records 9,037 summary bytes over 647,400 raw instrument bytes (1.396%), with zero raw samples in node replies. This is one demonstration run, not an accuracy result. Historical replay data remains separate; the static build also includes the two explicitly allowed Grid replay files. See [frontend instructions](frontend/README.md).

Streamlit remains the existing developer view:

```sh
./scripts/start.sh
PYTHONPATH=. .venv/bin/streamlit run slac_assistant/ui.py --server.address 127.0.0.1 --server.port 8501
```

It is not the Grid demo frontend. There are no equipment-write tools. Human follow-ups start another Flower run in the same series; `insufficient_evidence` is a valid result. Corroboration does not establish a unique RF cause.

## Four-case Grid versus baseline comparison

Run all four events with the same configured model:

```sh
PYTHONPATH=. .venv/bin/python scripts/evaluate.py --model flwrlabs/endeavor-1.0 --address http://127.0.0.1:18000 --output-dir artifacts/grid-comparison
# Resume the same comparison after checking that interrupted server runs have ended:
PYTHONPATH=. .venv/bin/python scripts/evaluate.py --resume --model flwrlabs/endeavor-1.0 --address http://127.0.0.1:18000 --output-dir artifacts/grid-comparison
```

Use `--node-timeout SECONDS` to set the Grid reply wait (0–300 seconds; default 120). A longer wait can accommodate slower provider calls; it does not change the model budget.

The evaluator runs serially, alternates Grid/baseline order across events, and saves `comparison.json`, `comparison.md` and `comparison-claim-review.csv` after every attempt. Resume requires the same model and SuperLink address, skips completed event/mode pairs and retains failed or partial attempts even if retries succeed. Partial node/accounting results remain incomplete and are retried on resume. The command exits nonzero while a required pair is incomplete. Ctrl+C saves the interrupted attempt but does not claim the server run was canceled.

The table reports actual model calls, input/output tokens, end-to-end latency and summary/raw byte ratio. Missing usage stays unavailable. Grid uses at most one model call per instrument and two lead calls; the baseline retains its existing bounded tool loop. Both cap model responses at 4,096 output tokens. These are different protocols and budgets, not a matched-compute experiment.

**Data locality:** Grid “data shared %” is serialized summary report bytes divided by raw instrument bytes held. It measures summary size, not raw-sample disclosure; raw samples in node replies are zero. Baseline **100%** describes centralized access to all instrument data, not raw arrays sent to the model. Grid reports identify local fallback and incomplete accounting explicitly. Payload measurements exclude transport overhead.

Agreement is **N/A**. The evaluator reads source RF labels only after investigations, and those labels cannot score beam disturbance or unique cause. Four deliberately selected cases support no accuracy-superiority claim. Invalid-reference counts check citation existence only; semantic support needs human review in the generated claim-review CSV. Cost is null when unavailable.

Recorded [comparison results](artifacts/grid-comparison/comparison.md): all four Grid runs and three baseline runs completed; the `slac-003` baseline failed. Grid summary/raw byte ratios range from 1.187% to 1.396%, with zero raw samples in replies. Earlier failed attempts are retained.

## Verification and limits

```sh
MPLBACKEND=Agg PYTHONPATH=. .venv/bin/pytest -q
node --test frontend/tests/*.test.js
.venv/bin/flwr build
```

Offline tests cover slice partitioning, read-only instrument checks, raw-array exclusion, schema/reference guards, Grid routing and byte accounting. They do not establish live provider availability or remote deployment. The live sequence is three-node smoke, provider check, then an Endeavor Grid run; only actual completed traces count as live results.

See [data provenance](docs/DATA_PROVENANCE.md) for source files, timestamps, transformations and unresolved dataset licensing. Labels and development artifacts stay outside the AgentApp bundle. There is no training, federated learning or live machine control.
