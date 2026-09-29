# RF investigation assistant — Flower hackathon prototype

A human-supervised replay tool for investigating SLAC RF candidates against beam evidence. It uses one Flower AgentApp with equipment, beam and lead investigator loops. Python handles calculations and read-only data access. There are no equipment-write tools.

**Status:** real public SLAC cases retrieved and plotted; deterministic tools, Flower execution and operator UI verified. Model collaboration and the single-agent baseline are implemented, but live model verification and their comparison require a configured model provider. The no-model runtime check is explicitly labeled and does not simulate intelligent agent findings.

## Start locally

Python 3.11+ and uv are required. Flower is pinned to **1.39.0**, matching the APIs inspected in the installed package and [current AgentApp documentation](https://flower.ai/docs/agent/explanations/agentapp-runtime.html).

```sh
uv sync
```

In terminal 1, configure the event-provided Flower key in your shell if available. Do not put keys into code, git or the UI. Then start the local runtime:

```sh
# FLWR_MODEL_API_KEY must be set for the default Flower provider.
./scripts/start.sh
```

Alternatively set `FLWR_MODEL_API_ENDPOINT` to a compatible provider's full `/responses` URL before starting SuperLink, and set its credential through `FLWR_MODEL_API_KEY` if required. The app itself uses Flower's injected runtime endpoint and credential. For local Ollama, see Flower's [official guide](https://flower.ai/docs/agent/how-to-guides/run-with-ollama.html); no Ollama model is installed by this project.

In terminal 2:

```sh
PYTHONPATH=. .venv/bin/streamlit run slac_assistant/ui.py --server.address 127.0.0.1 --server.port 8501
```

Open http://127.0.0.1:8501. Select an event, mode and provider model ID, then **Start investigation**. **Deterministic runtime check** works without model credentials and is suitable for verifying installation and viewing the evidence. **Specialist collaboration** and **Single-agent baseline** require real model access. Model failures do not silently fall back to the deterministic check.

To run from the terminal:

```sh
.venv/bin/python -m slac_assistant.runtime --mode smoke --event slac-001
.venv/bin/python -m slac_assistant.runtime --mode collaborative --event slac-001 --model openai/gpt-5.6-sol
.venv/bin/python -m slac_assistant.runtime --mode baseline --event slac-001 --model openai/gpt-5.6-sol
```

Use Ctrl+C in the server terminals to stop. All services bind to loopback. `scripts/start.sh` puts the venv on PATH so Flower can launch its workers. State is local under ignored `.flower/`. Credentials are never stored in the bundle. The Control API adapter uses version-pinned Flower Python helpers; revalidate it when upgrading Flower.

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

The external evaluator reads labels only after investigations. It records agreement, abstentions, tool calls, model calls, token usage, application and end-to-end latency. Cost is null when provider cost is unavailable. Unsupported claims require manual review; invalid-reference counts are a separate structural measure, not a substitute. The generated claim-review CSV has reviewer fields. No model comparison result is fabricated when provider access is absent.

## Evidence and limitations

Each finding includes its ID/agent, observation, channels and interval, tool references, supporting and conflicting evidence, limitations and requested next check. Tools return stable content-derived references. Schema, reference and channel checks reject malformed evidence; semantic claim support still needs operator review.

The signal detector is a transparent demonstration heuristic, not a reproduction or improvement of SLAC's published detector. It uses a time-weighted RF baseline and robust beam deviations sustained for ten valid consecutive samples, with charge checks. Four label-selected cases are not a benchmark. There is no training, distributed deployment, federated learning, live control or protein analysis.

See [data provenance](docs/DATA_PROVENANCE.md) for exact source files, channels, transformations, timestamps and unresolved dataset licensing. `scripts/fetch_cases.py` documents the small extraction. Raw downloads and all labels stay outside the AgentApp bundle.
