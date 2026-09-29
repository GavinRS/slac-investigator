# Local three-instrument Grid

The Grid demo uses Flower 1.39.0 with one orchestrator and three SuperNodes. The nodes read RF, LTU and dump slices from separate local folders and send compact reports to the orchestrator. This is process and data-access separation on one machine, not a filesystem security boundary: the application bundle still contains all four demo events for assigned-role fallback.

## Run

```sh
uv sync
.venv/bin/python scripts/configure_flower.py
./scripts/start_grid.sh
```

The credential helper prompts privately in your terminal and stores the key in ignored mode-600 local configuration. The launcher passes the explicitly selected provider into SuperLink. It does not source unrelated provider settings. `.env` selects `FLWR_MODEL_API_ENDPOINT`, `FLWR_MODEL_API_KEY` and `INVESTIGATOR_MODEL`; a blank endpoint selects Flower’s gateway, and the default model is `flwrlabs/endeavor-1.0`. Agents consume only Flower’s injected runtime configuration.

The supervisor generates `nodes/{rf,ltu,dump}/`, starts a separate persistent SuperLink on `127.0.0.1:18000`, and starts three SuperNodes on runtime ports 19094–19096, connected through Fleet port 19093. Existing port-8000 services are untouched. Occupied ports cause startup to stop without killing existing services. Ctrl+C stops only the four processes started by this supervisor and their workers. State is under ignored `.flower-grid/`; logs are under ignored `artifacts/grid-logs/*.log`.

In another terminal:

```sh
.venv/bin/python -m slac_assistant.runtime --address http://127.0.0.1:18000 --mode smoke --event slac-001
.venv/bin/python -m slac_assistant.runtime --address http://127.0.0.1:18000 --mode grid --event slac-001
PYTHONPATH=. .venv/bin/python scripts/evaluate.py --address http://127.0.0.1:18000 --output-dir artifacts/grid-comparison
```

Smoke mode performs deterministic checks with no model calls. Grid mode invokes the model on each instrument's aggregates and then on the lead's collected summaries. Baseline mode retains the centralized single-agent workflow. Human follow-ups reuse a Flower series and the prior assessment; they do not use provider response IDs.

## Routing and measurements

The orchestrator discovers node capabilities before assigning work because local unauthenticated Flower nodes have random IDs and no reliable instrument names. A node with local `instrument.txt` owns that instrument. Flexible nodes without local data can use assigned roles from bundled events. No connected nodes triggers an explicitly labeled in-process fallback; it is not presented as a remote Grid demonstration.

Each report contains instrument-local aggregates, tool references, byte counts and model usage when the provider supplies it. Raw sample arrays never enter node replies or node model prompts. `percent_shared` is serialized report bytes divided by instrument array bytes, excluding transport overhead. It is not the percentage of raw samples disclosed (that count is zero). The baseline's 100% represents centralized access to all instrument data, not raw arrays sent to the model.

Four label-selected cases are a demonstration, not a benchmark. Source RF anomaly labels do not adjudicate the separate beam-disturbance and unique-cause findings, so the comparison leaves agreement unscored. Missing usage is null, failed attempts are explicit, and results do not establish multi-agent accuracy superiority.

## Report contract

Grid requests return `mode: grid`, `execution_mode: model`, and `grid: {nodes_seen, assignment, fallback}`. Deterministic smoke requests also return `mode: grid`, with `execution_mode: smoke`. Each instrument makes at most one model call; the lead makes at most two, including any correction. The final Finding v2 keeps beam disturbance separate from unique cause.

The API/Fieldnote team owns the demo frontend integration. Its frozen handoff is the existing `/api/v1` job/polling API plus `node_report` and `data_shared` events, `node_reports`, the Grid object, and Finding v2. Streamlit remains unchanged as a developer view.

Resume a long comparison with the same `--model`, `--address` and `--output-dir`, adding `--resume`. Completed event/mode pairs are reused, failed attempts remain in the artifacts, and unfinished pairs are retried serially. An interrupted evaluator does not guarantee cancellation of a running Flower job; check the server before resuming.

## Recorded Grid replay

Endeavor run `2134321731300912044` for `slac-001` completed with three instrument nodes, no fallback, and complete accounting. Its separate replay is in `frontend/grid-replay/`; open `http://127.0.0.1:5173/?manifest=./grid-replay/manifest.json` while serving `frontend/`. Export verified 9,037 summary bytes / 647,400 raw instrument bytes (1.396%) and zero raw samples shared. The static build includes this manifest and event file explicitly, so the same custom replay URL works when serving `frontend/dist/`.

The evaluator accepts `--node-timeout SECONDS` (0–300; default 120) for the Grid reply wait. Reports with incomplete instrument or usage accounting are marked partial and retried with `--resume`; Flower runtime completion alone does not make a partial report a complete comparison result.
