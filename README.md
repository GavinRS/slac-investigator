# RF investigation assistant — Flower hackathon prototype

A human-supervised replay tool for investigating SLAC RF candidates against beam evidence. Its Flower AgentApp dispatches RF, LTU and dump instrument agents through the Grid and combines their summaries in a lead investigator. Python handles calculations and read-only data access. There are no equipment-write tools.

**Status:** real public SLAC cases, deterministic tools, Flower model collaboration, a human follow-up, and the operator dashboard have been exercised with live OpenAI responses through Flower. The default launcher now uses Flower inference with a separate private local credential; the historical runs below used direct OpenAI inference through Flower. The slac-001 main conclusions are supported with an onset-precision caveat; slac-003 exposed a misleading assessment headline despite a supported explanation. See the [live execution and evidence review](artifacts/flower-provider-resolution.md). The four-case Grid/baseline evaluator now records measured runs and explicit failures; see the generated comparison artifacts for verification status. Deterministic checks remain explicitly labeled and are not model results.

## Start locally

Frontend integrations use the [HTTP API contract](docs/FRONTEND_API.md). Start the local API with `./scripts/start_api.sh` after SuperLink; interactive documentation is at `http://127.0.0.1:8080/docs`. It supports asynchronous investigation start, durable activity polling/results, event plots, and same-series follow-ups. This is a local development service; GitHub Pages remains saved-run replay until an authenticated HTTPS backend exists.

New result schema v2 separates **beam disturbance corroboration** from **unique causal attribution**, with independent evidence and rationale. The three earlier successful runs are preserved byte-for-byte in [the archive](artifacts/preserved-successful-runs/manifest.json). Their mixed-scope labels are not converted into scores; original traces and review caveats remain available.

Python 3.11+ and uv are required. Flower is pinned to **1.39.0**, matching the APIs inspected in the installed package and [current AgentApp documentation](https://flower.ai/docs/agent/explanations/agentapp-runtime.html).

```sh
uv sync
```

In terminal 1, enter your Flower key privately, then start SuperLink:

```sh
.venv/bin/python scripts/configure_flower.py
./scripts/start.sh
```

The helper requires an interactive terminal and hides input. It writes only to `.env.flower.json`, which is git-ignored and owner-readable/writable (mode 600). Never put a key into chat, a command argument, or source code. Re-run the helper to replace the key, then restart SuperLink.

The launcher explicitly uses `https://api.flower.ai/v1/responses` and the app defaults to Endeavor (`flwrlabs/endeavor-1.0`), verified against Flower’s authenticated `/v1/models` catalog on 2026-09-29. The endpoint is also the installed Flower 1.39.0 default in `flwr/supercore/task_process/model/provider.py`. The app continues to use Flower's injected runtime endpoint and credential through the OpenAI-compatible SDK.

The previous `.env.local` remains intact for recovery, but the launcher no longer sources it or Pacterra. It discards inherited OpenAI, Pacterra, Flower model and Flower runtime variables before setting the explicit Flower endpoint and private key. Missing or invalid private configuration stops startup; it never falls back to an inherited credential. The pre-migration startup script, project configuration and README are preserved locally under ignored `.flower/provider-migration-backup/`. Saved completed-run files and archived results are retained; records from an earlier in-memory SuperLink are not migrated into the new persistent database.

In terminal 2:

```sh
PYTHONPATH=. .venv/bin/streamlit run slac_assistant/ui.py --server.address 127.0.0.1 --server.port 8501
```

Open http://127.0.0.1:8501. Select an event, mode and provider model ID, then **Start investigation**. **Deterministic runtime check** works without model credentials and is suitable for verifying installation and viewing the evidence. **Specialist collaboration** and **Single-agent baseline** require real model access. Model failures do not silently fall back to the deterministic check.

For the three-instrument Grid demo, use a separate supervised terminal:

```sh
./scripts/start_grid.sh
```

This starts an independent local SuperLink on port **18000** and three instrument nodes, preserving the existing port-8000 service. Stop the demo services together with **Ctrl+C** in that terminal. See [Grid runtime instructions](docs/GRID_RUNTIME.md) for details. Point the evaluator at `http://127.0.0.1:18000` to compare actual Grid runs.

To run from the terminal:

```sh
.venv/bin/python -m slac_assistant.runtime --mode smoke --event slac-001
.venv/bin/python -m slac_assistant.runtime --mode collaborative --event slac-001 --model flwrlabs/endeavor-1.0
.venv/bin/python -m slac_assistant.runtime --mode baseline --event slac-001 --model flwrlabs/endeavor-1.0
```

Use Ctrl+C in the server terminals to stop. All services bind to loopback. `scripts/start.sh` puts the venv on PATH so Flower can launch its workers. State is local under ignored `.flower/`; the startup script configures `.flower/slac.sqlite` for subsequent launches. Restart durability of the currently serving instance has not been verified; completed JSON traces are saved independently. Credentials are never stored in the bundle. The Control API adapter uses version-pinned Flower Python helpers; revalidate it when upgrading Flower.

## Demonstration flow

1. Select a measured event and inspect its source, RF and beam plots. The shaded candidate interval comes from the source metadata; no timestamp fitting occurs.
2. Collaborative Grid mode assigns RF, LTU and dump instruments to available nodes. Each node runs local read-only checks and returns summary findings. Reports explicitly identify an in-process fallback when no Grid nodes are available.
3. The coordinator combines instrument summaries into separate beam-disturbance and unique-cause assessments. The baseline keeps the existing single-investigator tool loop for comparison; diagnoses are not scripted.
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

## Four-case Grid and baseline demonstration

After starting the Grid and configuring a model, run all four events in both modes using the same model:

```sh
PYTHONPATH=. .venv/bin/python scripts/evaluate.py --model flwrlabs/endeavor-1.0
# For a separate local Grid instance:
PYTHONPATH=. .venv/bin/python scripts/evaluate.py --model flwrlabs/endeavor-1.0 --address http://127.0.0.1:18000
```

The evaluator alternates mode order across events and saves `artifacts/comparison.json`, a readable `artifacts/comparison.md` table, and `artifacts/comparison-claim-review.csv` after every attempt. Use `--output-dir PATH` to preserve a separate run. Use `--resume` with the same model, address and output directory to retain completed pairs and retry unfinished ones. Failed attempts remain visible even after recovery; the command exits nonzero while any required pair is incomplete. It never substitutes a smoke result for a model result. The table reports actual model calls, input/output tokens, end-to-end latency and data sharing. Missing provider usage stays unavailable. Both paths cap each model response at 4,096 output tokens and permit at most 12 model calls. The protocols may use different call counts; identical models do not imply equal actual usage or establish superiority.

**Data locality headline:** instrument agents return compact summaries; raw samples stay on the instrument side of the Grid protocol. Grid “data shared %” is serialized summary payload bytes divided by raw instrument bytes held. It is a summary-size ratio, not a measure of raw-sample disclosure. Baseline **100%** is a conceptual centralized-access counterfactual: its tools can access all instrument data, but this does not mean raw arrays are sent to the model. Reports identify local fallback explicitly; it does not demonstrate remote data locality. The current bundle still includes replay data for assigned-role fallback, so summary-only messaging alone is not proof of filesystem isolation.

Agreement is **N/A**: the evaluator reads source RF anomaly labels only after investigations, but those labels are not separately adjudicated labels for beam disturbance and unique cause. Historical mixed-scope assessments are unsuitable for scoring. Four deliberately label-selected cases are a demonstration, **not a benchmark**. Cost is null when provider cost is unavailable. Unsupported claims require manual review; invalid-reference counts check citation existence only. The claim-review CSV has reviewer fields.

## Evidence and limitations

Each finding includes its ID/agent, observation, channels and interval, tool references, supporting and conflicting evidence, limitations and requested next check. Tools return stable content-derived references. Schema, reference and channel checks reject malformed evidence; semantic claim support still needs operator review.

The signal detector is a transparent demonstration heuristic, not a reproduction or improvement of SLAC's published detector. It uses a time-weighted RF baseline and robust beam deviations sustained for ten valid consecutive samples, with charge checks. Four label-selected cases are not a benchmark. There is no training, federated learning, live control or protein analysis. Local Grid execution is a replay demonstration; remote deployment requires separate verification.

See [data provenance](docs/DATA_PROVENANCE.md) for exact source files, channels, transformations, timestamps and unresolved dataset licensing. `scripts/fetch_cases.py` documents the small extraction. Raw downloads and all labels stay outside the AgentApp bundle.

## Optional Nebius Chat Completions path

The original Flower Responses configuration remains the default. See [Nebius compatibility and gated validation](docs/NEBIUS_INTEGRATION.md) for the opt-in AgentApp adapter, protocol limits, credit/credential prerequisites and three-stage live test runner. Offline adapter tests do not establish live provider compatibility.
