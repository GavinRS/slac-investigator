# Local three-instrument Grid

The Grid demo uses Flower 1.39.0 with one orchestrator and three SuperNodes. The nodes read RF, LTU and dump slices from separate local folders and send compact reports to the orchestrator. This is process and data-access separation on one machine, not a filesystem security boundary: the application bundle still contains all four demo events for assigned-role fallback.

## Run

```sh
uv sync
.venv/bin/python scripts/configure_flower.py
./scripts/start_grid.sh
```

The first command requiring a credential prompts privately in your terminal. The key is stored in an ignored mode-600 file. Startup never sources the preserved `.env.local` or Pacterra configuration, and inherited OpenAI/model-provider settings cannot redirect inference. The selected model comes from `pyproject.toml`; the current default is `flwrlabs/endeavor-1.0`, verified against Flower's authenticated `/v1/models` catalog.

The supervisor generates `nodes/{rf,ltu,dump}/`, starts a separate persistent SuperLink on `127.0.0.1:18000`, and starts three SuperNodes on runtime ports 19094–19096, connected through Fleet port 19093. Existing port-8000 services are untouched. Occupied ports cause startup to stop without killing existing services. Ctrl+C stops only the four processes started by this supervisor and their workers. State is under ignored `.flower-grid/`; logs are under ignored `artifacts/grid-logs/*.log`.

In another terminal:

```sh
.venv/bin/python -m slac_assistant.runtime --address http://127.0.0.1:18000 --mode smoke --event slac-001
.venv/bin/python -m slac_assistant.runtime --address http://127.0.0.1:18000 --mode collaborative --event slac-001
PYTHONPATH=. .venv/bin/python scripts/evaluate.py --address http://127.0.0.1:18000 --output-dir artifacts/grid-comparison
```

Smoke mode performs deterministic checks with no model calls. Collaborative mode invokes the model on each instrument's aggregates and then on the lead's collected summaries. Baseline mode retains the centralized single-agent workflow. Human follow-ups reuse a Flower series and the prior assessment; they do not use provider response IDs.

## Routing and measurements

The orchestrator discovers node capabilities before assigning work because local unauthenticated Flower nodes have random IDs and no reliable instrument names. A node with local `instrument.txt` owns that instrument. Flexible nodes without local data can use assigned roles from bundled events. No connected nodes triggers an explicitly labeled in-process fallback; it is not presented as a remote Grid demonstration.

Each report contains instrument-local aggregates, tool references, byte counts and model usage when the provider supplies it. Raw sample arrays never enter node replies or node model prompts. `percent_shared` is serialized report bytes divided by instrument array bytes, including repeated follow-up reports and excluding transport overhead. It is not the percentage of raw samples disclosed (that count is zero). The baseline's 100% represents centralized access to all instrument data, not raw arrays sent to the model.

Four label-selected cases are a demonstration, not a benchmark. Source RF anomaly labels do not adjudicate the separate beam-disturbance and unique-cause findings, so the comparison leaves agreement unscored. Missing usage is null, failed attempts are explicit, and results do not establish multi-agent accuracy superiority.
