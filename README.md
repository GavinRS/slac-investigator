# RF investigation assistant — Flower hackathon prototype

A human-supervised replay tool for investigating SLAC RF candidates against beam evidence. It uses one Flower AgentApp with equipment, beam and lead investigator loops. Python handles calculations and read-only data access. There are no equipment-write tools.

**Status:** real public SLAC cases, deterministic tools, model collaboration inside the Flower AgentApp, a human follow-up, and the operator dashboard have been exercised. Those earlier live runs used OpenAI models (api.openai.com), not the Nebius or Endeavor models this project now defaults to. In their review, the slac-001 main conclusions were supported with an onset-precision caveat; slac-003 exposed a misleading assessment headline despite a supported explanation. The baseline comparison remains unevaluated. Deterministic checks remain explicitly labeled and are not model results.

## Start locally

Frontend integrations use the [HTTP API contract](docs/API.md). Start the local API with `./scripts/start_api.sh` after SuperLink; interactive documentation is at `http://127.0.0.1:8080/docs`. It supports asynchronous investigation start, durable activity polling/results, event plots, and same-series follow-ups. This is a local development service; GitHub Pages remains saved-run replay until an authenticated HTTPS backend exists.

New result schema v2 separates **beam disturbance corroboration** from **unique causal attribution**, with independent evidence and rationale. Earlier runs, including those in the frontend's saved-run replay, used a single mixed-scope label; it is not converted into scores.

Python 3.11+ and uv are required. Flower is pinned to **1.39.0**, matching the APIs inspected in the installed package and [current AgentApp documentation](https://flower.ai/docs/agent/explanations/agentapp-runtime.html).

```sh
uv sync
```

In terminal 1, set the model provider in a private `.env` at the repository root, then start SuperLink:

```sh
.venv/bin/python scripts/configure_flower.py
./scripts/start.sh
```

The helper requires an interactive terminal and hides input. It writes only the `FLWR_MODEL_API_KEY` line of `.env`, which is git-ignored and owner-readable/writable (mode 600). Never put a key into chat, a command argument, or source code. Re-run the helper to replace the key, then restart SuperLink.

`.env` holds three settings, which `scripts/start.sh` passes into the SuperLink's environment:

- `FLWR_MODEL_API_ENDPOINT`: the provider's Responses endpoint. Blank means Flower's gateway (`https://api.flower.ai/v1/responses`).
- `FLWR_MODEL_API_KEY`: the key for that provider. Required when the endpoint is blank.
- `INVESTIGATOR_MODEL`: the model ID. The default is Nebius Token Factory's `dedicated/flowerai/MiniMax-M3-OOLI9o`; the fallback is Endeavor (`flwrlabs/endeavor-1.0`) through Flower's gateway. Set the endpoint and key to match the model.

Provider endpoints and where each key comes from are listed in the [design spec's provider table](docs/superpowers/specs/2026-09-29-grid-investigator-design.md). The AgentApp never talks to a provider directly; it uses only the `FLWR_RUNTIME_BASE_URL`/`FLWR_RUNTIME_API_KEY` that Flower injects. The launcher discards inherited `OPENAI_*`, `FLWR_MODEL_*`, `FLWR_RUNTIME_*` and `INVESTIGATOR_*` variables, so shell settings cannot redirect it. A missing or invalid `.env` stops startup; it never falls back to an inherited credential. It prints the endpoint and model at startup, never the key.

In terminal 2:

```sh
PYTHONPATH=. .venv/bin/streamlit run slac_assistant/ui.py --server.address 127.0.0.1 --server.port 8501
```

Open http://127.0.0.1:8501. Select an event, mode and provider model ID, then **Start investigation**. **Deterministic runtime check** works without model credentials and is suitable for verifying installation and viewing the evidence. **Specialist collaboration** and **Single-agent baseline** require real model access. Model failures do not silently fall back to the deterministic check.

To run from the terminal:

```sh
.venv/bin/python -m slac_assistant.runtime --mode smoke --event slac-001
.venv/bin/python -m slac_assistant.runtime --mode collaborative --event slac-001
.venv/bin/python -m slac_assistant.runtime --mode baseline --event slac-001
```

To run the instrument nodes on Nebius Serverless via SuperGrid, see [docs/NEBIUS_NODES.md](docs/NEBIUS_NODES.md).

### 3-node Grid (data lives on the node)

Instead of `start.sh`, run one SuperLink plus 3 SuperNodes (`rf`, `ltu`, `dump`) on this laptop:

```sh
./scripts/start_grid.sh
```

It loads `.env`, starts the SuperLink through `scripts/start_flower.py` when a model key is configured (same model credentials as `start.sh`), runs `scripts/split_nodes.py` to write `nodes/<instrument>/`, then starts each SuperNode with `SLAC_NODE_DATA_DIR` and `FLWR_FILESYSTEM_ALLOWED_DIRS` set to its own folder (runtime ports 9094-9096). Both variables are visible inside each node's agent process. Without a configured key, it starts a plain smoke-only SuperLink instead. Ctrl+C stops everything. To see the nodes, add a connection to `.flower/config.toml` and list them:

```toml
[superlink.grid]
address = "127.0.0.1:8000"
insecure = true
```

```sh
FLWR_HOME=$PWD/.flower .venv/bin/flwr supernode list grid   # 3 nodes, status online
```

Use Ctrl+C in the server terminals to stop. All services bind to loopback. `scripts/start.sh` puts the venv on PATH so Flower can launch its workers. The SuperLink keeps its state in memory (flwr 1.39 creates no SQLite tables when the repo path contains a space), so Flower runs and follow-up context are lost when it stops; completed JSON traces are saved independently. Credentials are never stored in the bundle. The Control API adapter uses version-pinned Flower Python helpers; revalidate it when upgrading Flower.

## Talk to it in flwr chat

```sh
flwr chat
/load <repo path>
/federation            # pick @<you>/personal
Was the beam disturbed during slac-001, and do we know why?
```

Plain-English prompts run the collaborative Grid on the event named in the text (`slac-001` if none). The personal federation has no nodes unless you add your own, so the three instruments run in-process (fallback `none (local fallback)`); the local 3-node grid (`scripts/start_grid.sh`) is where nodes really hold their own data.

## Demonstration flow

1. Select a measured event and inspect its source, RF and beam plots. The shaded candidate interval comes from the source metadata; no timestamp fitting occurs.
2. The lead's initial assignments send RF evidence to equipment and beam/quality evidence to beam. They inspect independently in separate model contexts (executed sequentially, not on separate machines).
3. The coordinator shares structured findings and exact tool results. The lead can request analyses or delegate a focused check to either specialist, then revise its assessment. Follow-ups depend on findings; disagreements and diagnoses are not scripted.
4. The operator sees concise findings, tool requests, the evidence ledger and limitations. Private model reasoning is not emitted. A human question starts another Flower run in the same series with the prior final assessment persisted in Context and fresh evidence checks.
5. Download the report. An `insufficient_evidence` result is valid; `not_corroborated` means these checks did not establish corroboration, not proof of normality. `corroborated` does not establish a unique RF cause.

## What was actually verified

- Four real AMPL cases fetched by byte ranges; first labeled case plotted before workflow implementation. See `artifacts/first_labeled_case.png`.
- JSON/NPZ array equality and exact integer timestamp preservation.
- Sparse RF handling, missing beam, timing anomalies, gap-aware sustained detection and low-charge position masking.
- Label and development-artifact exclusion from the Flower bundle.
- Separate specialist input contexts and coordinator follow-up routing with an explicit protocol test fixture (not a live model evaluation).
- Real local SuperLink execution: Flower installs the FAB and launches `flwr-agentapp`; event output and completed run status were retrieved through its Control API.
- Four deterministic Flower runs agree with the four deliberately selected labels. This only checks software behavior on chosen examples.

Run checks:

```sh
MPLBACKEND=Agg PYTHONPATH=. .venv/bin/pytest -q
PYTHONPATH=. .venv/bin/python scripts/evaluate.py --smoke-only
.venv/bin/flwr build
```

## Matched baseline evaluation

After configuring a model:

```sh
PYTHONPATH=. .venv/bin/python scripts/evaluate.py --model YOUR_PROVIDER_MODEL_ID
```

The single investigator gets the same initial equipment, beam and quality results, all six deterministic analysis tools, and the same model as the specialists. Each approach has at most 12 total model calls, 1,600 output tokens per call, 300,000 cumulative input characters and 24 analysis calls. The specialist budget includes lead and delegated calls. These are equal ceilings, not a claim of equal actual usage; reports record usage and alternate execution order across events.

The external evaluator reads source labels only after investigations and records the two separate assessments, tool calls, model calls, token usage, application and end-to-end latency. It does not score agreement: source anomaly labels are not separately adjudicated labels for beam disturbance and unique cause, and historical mixed-scope labels are unsuitable for scoring. Cost is null when provider cost is unavailable. Unsupported claims require manual review; invalid-reference counts are a separate structural measure, not a substitute. The generated claim-review CSV has reviewer fields.

## Data credit and disclaimer

The four events in `data/events/` are small extracts (about 3 MB) from SLAC National Accelerator Laboratory's public klystron RF anomaly dataset ([dataset index](https://www.slac.stanford.edu/grp/ad/ard/rfanom/rfanom.html), [DOE catalog entry](https://www.osti.gov/biblio/1869296)). All credit for the data goes to SLAC and the dataset authors. We did not find an explicit reuse license. They are included here, and in the Flower Hub app, only to demo this non-commercial hackathon project, and we will remove them if asked. This project is not affiliated with or endorsed by SLAC. See [data provenance](docs/DATA_PROVENANCE.md).

## Evidence and limitations

Grid vs single agent (`scripts/evaluate.py --events slac-001`, one live run, same model): both reported beam disturbance corroborated / unique cause not established. The Grid (3 node agents + orchestrator, 4 model calls, 23.7 s) shared 0.92% of the raw bytes, while the single-agent baseline (2 model calls, 21.2 s) needs 100% of them in one place. In that Grid run the orchestrator's model reply came back incomplete, so its final was the deterministic combine of the three node reports; the model final was accepted in only 2 of the 4 recorded Grid model runs at a 4000-token output budget. One case, not a benchmark.

Each finding includes its ID/agent, observation, channels and interval, tool references, supporting and conflicting evidence, limitations and requested next check. Tools return stable content-derived references. Schema, reference and channel checks reject malformed evidence; semantic claim support still needs operator review.

The signal detector is a transparent demonstration heuristic, not a reproduction or improvement of SLAC's published detector. It uses a time-weighted RF baseline and robust beam deviations sustained for ten valid consecutive samples, with charge checks. Four label-selected cases are not a benchmark. There is no training, distributed deployment, federated learning, live control or protein analysis.

See [data provenance](docs/DATA_PROVENANCE.md) for exact source files, channels, transformations, timestamps and unresolved dataset licensing. `scripts/fetch_cases.py` documents the small extraction. Raw downloads and all labels stay outside the AgentApp bundle.

## Switching models

Copy `.env.example` to `.env` and fill in a key (`.env` stays gitignored; never commit a key). `.env.example` lists all four provider blocks — Nebius, Endeavor, Groq and Ollama — with the Nebius Token Factory default active and the rest commented out. After editing `.env`, verify the provider responds with:

```sh
.venv/bin/python scripts/check_model.py
```

It sends one Responses API request with a trivial tool and prints PASS/FAIL, a reason and latency; it never prints the key.
