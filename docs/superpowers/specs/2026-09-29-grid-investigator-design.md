# Grid investigator design (2026-09-29)

## Goal

Proof of concept for the Flower Collaborative Agent Hackathon: three SLAC instruments each keep their own readings, run their own read-only checks, and send back only summary findings. An orchestrator agent combines them into one assessment for a human. We report how much raw data was shared.

Architecture, bottom to top: **machines (instrument nodes) → tools (local read-only checks) → node agents → orchestrator → human.**

## Decisions

| Topic | Decision |
|---|---|
| Data | The 4 real SLAC cases already in `data/events/`, replayed as if freshly recorded. No new fetching. |
| Nodes | 3: `rf` (klystron `health` columns), `ltu` (`BPMS:LTUH:*`), `dump` (`BPMS:DMPH:*`). |
| Node role | **C with A fallback.** A node first looks for a local instrument slice (C). If none, it uses the role the orchestrator assigns and loads that slice from the bundled data (A). |
| Node replies | Assessment plus summary numbers only. **Never raw samples.** Matches Flower's federated-analytics pattern. |
| Model | **Endeavor** (`flwrlabs/endeavor-1.0` via Flower's gateway; challenge bonus) by default; Nebius Token Factory (`MiniMax-M3`) as the fast fallback; Groq and Ollama as further swaps. Provider is swappable by env vars only (see Providers). |
| Human surfaces | `flwr chat` (always works), a small HTTP API, and Streamlit and Lovable as thin clients of that API. |
| Hub | The AgentApp (with bundled data) is what gets published. UIs never go to the Hub. |
| Git | Old `main` saved as `backup/streamlit-local`. This work becomes `main`. |

## Flower facts this relies on (flwr 1.39.0 source)

- Orchestrator (runs on the SuperLink, `context.node_id == 1`) gets Grid tools `get_nodes`, `push_messages`, `pull_messages` (`supercore/task_process/agent/grid.py:41`).
- Node agents get only `push_reply_message(payload)`, which replies to the message that started them (`grid.py:42`, `_push_reply_message`).
- A node agent's `agent.prompt` is JSON `{"message_id", "src_node_id", "payload"}` (`run_agentapp.py:173`).
- Grid tools can be called from Python, not only by the model: `agent.grid.call({"type":"function_call","name":...,"arguments":{...},"call_id":...})`.
- `pull_messages` timeout is 0-300 s.
- The filesystem connector reads folders allowed by `FLWR_FILESYSTEM_ALLOWED_DIRS`, max 1 MB per file. In `flwr chat` it can only be attached in the personal federation.
- Probe on 2026-09-29: `@iamsorenl/workspace` on SuperGrid has 0 nodes. Access to Flower Agent is requested at flower.ai → personal federation → Request access.
- Flower's gateway lists `flwrlabs/endeavor-1.0` at `GET https://api.flower.ai/v1/models`; a Responses request with a tool returned a correct `function_call` (2026-09-29). One call took ~21 s and returned no usage block.
- Nebius Token Factory's event endpoint supports the Responses API with tool calling (verified 2026-09-29 with MiniMax-M3). No translator needed.
- We can run **our own SuperNodes on Nebius Serverless** (console.nebius.com, guide "Spinning up a Flower SuperNode on a Nebius Serverless AI endpoint" in the Flower Discuss post). That gives real remote nodes holding our instrument slices (mode C on real infrastructure).

## Components

### 1. Instrument data slices (`slac_assistant/instruments.py`)

- `INSTRUMENTS = ("rf", "ltu", "dump")`.
- `load_slice(event_id, instrument, root=None)` returns `(meta, arrays)` holding only that instrument's channels and timestamps. `root=None` reads the bundled `data/events/`; a path reads a local data folder with the same file layout.
- `detect_local_instrument()` returns the instrument name if a local slice folder is configured (env `SLAC_NODE_DATA_DIR`, or the first dir in `FLWR_FILESYSTEM_ALLOWED_DIRS`) and contains an `instrument.txt` naming it; otherwise `None`.
- `scripts/split_nodes.py` writes `nodes/<instrument>/` folders (per-event slice files plus `instrument.txt`) for the local demo. Generated folders are gitignored.
- Tests: the three slices together equal the original channels exactly.

### 2. Instrument tools (`slac_assistant/tools.py`, extended)

Existing tool math is reused. Each instrument only gets its own checks:

- `rf`: `equipment`, `neighbors`, `quality` (health side).
- `ltu` and `dump`: `beam`, `charge_validity`, `quality` (bpm side), restricted to that beamline's channels.

`node_summary(event_id, instrument, arrays)` returns the reply payload below.

### 3. Node reply contract (JSON string payload)

```json
{
  "kind": "node_report",
  "instrument": "rf|ltu|dump",
  "role_source": "local_data|assigned",
  "event_id": "slac-001",
  "assessment": "suspicious|normal|insufficient_evidence",
  "observation": "one or two sentences",
  "summary": {"...": "numbers only: baseline, peak deviation, onset_ns, valid/masked counts"},
  "tool_refs": ["T-..."],
  "raw_bytes_held": 123456,
  "payload_bytes": 0,
  "limitations": ["..."]
}
```

- `summary` must contain no arrays longer than 10 numbers (a test enforces this).
- In `smoke` mode the observation is deterministic. In model modes the node agent's model writes `observation` and `assessment` from the summary, validated against the schema.

### 4. Orchestrator (`slac_assistant/grid_workflow.py`)

Python-driven for reliability; the model is used for judgment, not plumbing.

1. `get_nodes`. If 3+ nodes: one instrument each. If fewer: nodes take several instruments (noted in the report). If 0 nodes: run all three instruments in-process and label the report `grid: none (local fallback)`.
2. `push_messages` with `{"kind":"node_task","event_id","instrument","mode","question"}` to each node, then `pull_messages` (timeout from run config, default 120 s).
3. Combine: align onsets across `rf`, `ltu`, `dump`; model (or deterministic smoke rule) writes the final assessment `corroborated|not_corroborated|insufficient_evidence` citing node reports.
4. Emit the same NDJSON event stream the current UI understands (`started`, `delegation`, `finding`, `report`), plus `node_report` events and `data_shared` = `{raw_bytes_held, payload_bytes, percent_shared}`.

`agent_app.py` dispatches: if the prompt is a node task (has `src_node_id`), run the node path and reply with `push_reply_message`; otherwise run the orchestrator. The old single-process `Investigation` stays as the `baseline` mode for comparison.

### 5. Providers (`.env.example`, `scripts/check_model.py`)

| Provider | `FLWR_MODEL_API_ENDPOINT` | `FLWR_MODEL_API_KEY` | model |
|---|---|---|---|
| Nebius Token Factory (fast fallback, event keys) | `https://api.tokenfactory.tf-ca1.nebius.com/v1/responses` | event key (shared privately, never commit) | `dedicated/flowerai/MiniMax-M3-OOLI9o` or `dedicated/flowerai/Kimi-K2.7-Code-1OUHWL` |
| Groq | `https://api.groq.com/openai/v1/responses` | Groq key | `openai/gpt-oss-20b` |
| Ollama | `http://localhost:11434/v1/responses` | blank | `gpt-oss:20b` |
| **Flower gateway: Endeavor (default)** | blank (Flower's default `https://api.flower.ai/v1/responses`) | Flower key (flower.ai → Profile → Settings → API Keys; never commit) | `flwrlabs/endeavor-1.0` |

Rules: agent code never names a provider; it uses only `FLWR_RUNTIME_BASE_URL`/`FLWR_RUNTIME_API_KEY` injected by Flower. `start.sh` loads `.env`. `check_model.py` sends one tool-calling Responses request to the configured provider and prints pass/fail. The run-config `model` default follows `INVESTIGATOR_MODEL` from `.env`.

### 6. Local demo runtime (`scripts/start_grid.sh`)

Starts one local SuperLink plus 3 SuperNodes, each with its own `nodes/<instrument>/` folder exposed through `FLWR_FILESYSTEM_ALLOWED_DIRS` / `SLAC_NODE_DATA_DIR`. This is the "data really lives on the node" mode.

### 7. API (`slac_assistant/api.py`, stdlib `http.server`, loopback)

- `GET /api/events` returns event IDs and metadata.
- `GET /api/plot/<event_id>.png` uses the existing `plot_event`.
- `POST /api/run` with `{event_id, mode, model?, question?, series_id?}` streams NDJSON events from `run_flower`; the last line is the report with `series_id`.
- SuperLink address from env `SLAC_SUPERLINK_ADDRESS` (default local). CORS allowed for `localhost` origins.
- `docs/API.md` documents all of this with example responses, for the Lovable builder.

### 8. Front ends

- Streamlit (`slac_assistant/ui.py`) calls the API instead of Flower directly, and shows node reports and `% raw data shared`.
- Lovable: built separately against `docs/API.md`, run locally for the demo.
- `flwr chat`: `/load` this repo; works with no API.

## Testing

- Existing tests stay green.
- New: slices partition the data exactly; node payloads contain no raw arrays; `% shared` math; orchestrator routing with a fake grid (3 nodes, 1 node, 0 nodes); API endpoints respond.
- Live: `check_model.py` against Groq; one local 3-node smoke run end to end; one Groq model run when a key is available.

## Out of scope today

Live control, new data fetching, a published detector benchmark, Lovable app code.

### 9. Remote nodes on Nebius (stretch)

Run the 3 instrument SuperNodes on Nebius Serverless following Flower's guide, each with its own `nodes/<instrument>/` folder, connected to our federation. Same code as the local runtime (§6).

## Work breakdown

GitHub issues #1-#13 implement this spec; #12 tracks questions for Flower.

## Open

Whether Nebius-hosted SuperNodes can join the hackathon federation; Hub bundle size limits; team registration (Typeform).
