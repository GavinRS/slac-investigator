# Grid investigator design (2026-09-29, rev 2)

> **Rev 2 (after reviewing `backup/pre-grid-prototype`):** keep this spec's Grid topology; adopt the prototype's product layer (Finding v2 result schema, FastAPI job API, static Fieldnote frontend, single-process `Investigation` as the baseline). See §10.

## Goal

Proof of concept for the Flower Collaborative Agent Hackathon: three SLAC instruments each keep their own readings, run their own read-only checks, and send back only summary findings. An orchestrator agent combines them into one assessment for a human. We report how much raw data was shared.

**Why not pool the data:** rf, ltu and dump are separate subsystems that keep their own raw streams. The single-agent baseline needs 100% of the raw samples in one place; the Grid version reaches a verdict from summaries, sharing only a small percentage. That, plus independent per-instrument agents, is the "more than a single agent" claim. We make no accuracy claim (4 hand-picked cases; labels are not adjudicated per verdict dimension).

Architecture, bottom to top: **machines (instrument nodes) → tools (local read-only checks) → node agents → orchestrator → human.**

## Decisions

| Topic | Decision |
|---|---|
| Data | The 4 real SLAC cases already in `data/events/`, replayed as if freshly recorded. No new fetching. |
| Nodes | 3: `rf` (klystron `health` columns), `ltu` (`BPMS:LTUH:*`), `dump` (`BPMS:DMPH:*`). |
| Node role | **C with A fallback.** A node first looks for a local instrument slice (C). If none, it uses the role the orchestrator assigns and loads that slice from the bundled data (A). |
| Node replies | Assessment plus summary numbers only. **Never raw samples.** Matches Flower's federated-analytics pattern. |
| Model | **Endeavor** (`flwrlabs/endeavor-1.0` via Flower's gateway; challenge bonus) by default; Nebius Token Factory (`MiniMax-M3`) as the fast fallback; Groq and Ollama as further swaps. Provider is swappable by env vars only (see Providers). |
| Result schema | **Finding v2** from the prototype: two separate verdicts, `beam_disturbance` (`corroborated\|not_corroborated\|insufficient_evidence\|not_assessed`) and `unique_cause` (`established\|not_established\|insufficient_evidence\|not_assessed`), each with its own rationale and evidence refs; `unique_cause=established` requires `beam_disturbance=corroborated`; `result_schema_version=2`. Used for the orchestrator's final and the baseline. |
| Baseline | The prototype's single-process `Investigation` (`workflow.py`, v2) is the `baseline` mode for the Grid-vs-single-agent comparison (#14). |
| Human surfaces | `flwr chat` (always works), the prototype's **FastAPI job API** (`/api/v1`, polling), and the prototype's **static Fieldnote frontend** (`frontend/`, live on localhost:5173, replay of recorded runs as the stage fallback). Streamlit stays as-is as a dev view. Lovable is dropped. |
| Hub | The AgentApp (with bundled data) is what gets published. UIs never go to the Hub. |
| Git | Old `main` saved as `backup/streamlit-local`. Gavin's prototype is on `backup/pre-grid-prototype` and gets merged into `main` once, in the integration issue #15 (merge verified conflict-free). |

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
  "assessment": "suspicious|normal|insufficient_evidence",  // per-instrument signal, not the final verdict
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
   Push to all nodes first, then one pull, so nodes work in parallel (Endeavor is ~21 s per call). Each node makes at most 1 model call; the orchestrator 1-2.
3. Combine: align onsets across `rf`, `ltu`, `dump`; model (or deterministic smoke rule) writes the final **Finding v2** citing node `tool_refs`, reusing `workflow.py`'s `Finding` model, `validate()` guards and one correction turn.
4. Events (frozen list): `started`, `delegation` (with `node_id`, `instrument`), `tool_request`, `tool_result`, `finding`, `finding_rejected`, `node_report`, `data_shared` = `{raw_bytes_held, payload_bytes, percent_shared}`, `report`. Same framing as today (NDJSON lines inside `response.output_text.delta`). Report keys: `final` (Finding v2), `findings`, `metrics`, `evidence`, `mode` (`grid` for this path), `result_schema_version: 2`, `grid` = `{nodes_seen, assignment, fallback}`, `data_shared`.

`agent_app.py` dispatches: if the prompt is a node task (has `src_node_id`), run the node path and reply with `push_reply_message`; otherwise run the orchestrator. The old single-process `Investigation` stays as the `baseline` mode for comparison.

### 5. Providers (`.env.example`, `scripts/check_model.py`)

| Provider | `FLWR_MODEL_API_ENDPOINT` | `FLWR_MODEL_API_KEY` | model |
|---|---|---|---|
| Nebius Token Factory (fast fallback, event keys) | `https://api.tokenfactory.tf-ca1.nebius.com/v1/responses` | event key (shared privately, never commit) | `dedicated/flowerai/MiniMax-M3-OOLI9o` or `dedicated/flowerai/Kimi-K2.7-Code-1OUHWL` |
| Groq | `https://api.groq.com/openai/v1/responses` | Groq key | `openai/gpt-oss-20b` |
| Ollama | `http://localhost:11434/v1/responses` | blank | `gpt-oss:20b` |
| **Flower gateway: Endeavor (default)** | blank (Flower's default `https://api.flower.ai/v1/responses`) | Flower key (flower.ai → Profile → Settings → API Keys; never commit) | `flwrlabs/endeavor-1.0` |

Rules: agent code never names a provider; it uses only `FLWR_RUNTIME_BASE_URL`/`FLWR_RUNTIME_API_KEY` injected by Flower (the prototype's `provider`/`probe` request fields and `nebius.py` chat adapter are removed). `scripts/start.sh` runs the prototype's `scripts/start_flower.py`, changed to read `FLWR_MODEL_API_ENDPOINT` (blank = Flower gateway), `FLWR_MODEL_API_KEY` and `INVESTIGATOR_MODEL` from a gitignored `.env` and pass them **into the SuperLink's environment** (the prototype's gateway runs failed with 502 `FLWR_MODEL_API_KEY not set` because the key didn't reach the SuperLink). Keep its key hygiene (getpass setup via `configure_flower.py`, mode 600, no keys in output). Replace every hard-coded `openai/gpt-5.6-sol` with `INVESTIGATOR_MODEL` (default `flwrlabs/endeavor-1.0`). `check_model.py` sends one tool-calling Responses request to the configured provider and prints pass/fail. The run-config `model` default follows `INVESTIGATOR_MODEL` from `.env`.

### 6. Local demo runtime (`scripts/start_grid.sh`)

Starts one local SuperLink (via the same environment setup as `start_flower.py`) plus 3 SuperNodes, each with its own `nodes/<instrument>/` folder exposed through `FLWR_FILESYSTEM_ALLOWED_DIRS` / `SLAC_NODE_DATA_DIR`. This is the "data really lives on the node" mode.

### 7. API (prototype's `slac_assistant/api.py`, FastAPI, loopback)

Reuse the prototype's job API and `docs/FRONTEND_API.md` (renamed `docs/API.md`): `GET /api/v1/events`, `GET /api/v1/events/{id}`, `GET /api/v1/events/{id}/plot` (JSON traces), `POST /api/v1/investigations` (202, creates a job), `GET /api/v1/investigations/{id}`, `GET /api/v1/investigations/{id}/activity` (polling). SQLite job store, secret redaction, localhost-only CORS/TrustedHost. Changes: add mode `grid`; pass the new event kinds through; document `node_report`, `data_shared` and the grid report fields. The stdlib NDJSON design in rev 1 is dropped.

### 8. Front ends

- **Fieldnote** (prototype's `frontend/`): the one demo UI. Add a card per instrument from `node_report` (instrument, role_source, assessment, observation, payload_bytes vs raw_bytes_held) and a headline `% raw data shared` from `data_shared`; add both kinds to the activity whitelists (`live.js`, `app.js`, `export_replay.py`). Export 1-2 recorded Grid runs with `export_replay.py` as the replay fallback. GitHub Pages deploy only after the repo is public.
- `flwr chat`: `/load` this repo; works with no API or UI.
- Streamlit: unchanged dev view (already shows the v2 verdicts).

## Testing

- Existing tests stay green (the prototype suite minus its Nebius-adapter tests, plus `node --test frontend/tests/*.test.js`).
- New: slices partition the data exactly; node payloads contain no raw arrays; `% shared` math; orchestrator routing with a fake grid (3 nodes, 1 node, 0 nodes); API endpoints respond.
- Live, in this order: one local 3-node **smoke** round trip (no model); `check_model.py` against Endeavor; one Endeavor Grid run, recorded and exported as a Fieldnote replay before the demo.

## Out of scope today

Live control, new data fetching, a published detector benchmark, accuracy claims, Lovable, the Nebius chat-completions adapter, GitHub Pages until the repo is public.

### 9. Remote nodes on Nebius (stretch)

Run the 3 instrument SuperNodes on Nebius Serverless following Flower's guide, each with its own `nodes/<instrument>/` folder, connected to our federation. Same code as the local runtime (§6).

### 10. Merging the pre-grid prototype (issue #15, first, ~30-45 min, one person)

Merge `origin/backup/pre-grid-prototype` into `main` once, then:
- **Keep:** `workflow.py` v2, `api.py`, `scripts/start_api.sh`, fastapi/uvicorn deps, `tests/test_api.py`, `tests/test_flower_configuration.py`, `docs/FRONTEND_API.md` (→ `docs/API.md`), `frontend/**`, `scripts/start_flower.py` + `configure_flower.py` (generalized per §5), `scripts/evaluate.py` (no accuracy scoring), `runtime.py`'s `on_started`, `ui.py` v2 display, `.gitignore` additions.
- **Delete:** `slac_assistant/nebius.py`, `provider_checks.py`, `scripts/start_nebius_check.py`, `scripts/verify_nebius.py`, `tests/test_nebius.py`, `docs/NEBIUS_INTEGRATION.md`, `docs/FRONTEND_HANDOFF.md`, all prototype-added `artifacts/**` (they contain local machine paths and runs routed to a non-Flower provider), the `provider`/`probe` plumbing in `agent_app.py` and `runtime.py`.
- **Change:** `openai/gpt-5.6-sol` → `INVESTIGATOR_MODEL` (default `flwrlabs/endeavor-1.0`); start scripts read `.env` per §5.
- Then Soren's `soren/3-node-agent-path` rebases on top (one small `agent_app.py` conflict).

## Team split (3 people, file ownership)

| Person | Owns | Issues |
|---|---|---|
| Gavin | Prototype merge; Finding v2 + orchestrator/model logic (`workflow.py`, `grid_workflow.py` combine step, `tools.py`) | #15 → #1 → #2 → #4 → #7 → #14 |
| Soren | Grid transport and nodes (`agent_app.py` dispatch, `node.py`, `start_grid.sh`, Nebius nodes), release | #3 → #6 → #13 → #11, #12 |
| Teammate 3 | Models + API + Fieldnote (`start_flower.py`/`.env`, `check_model.py`, `api.py`, `frontend/**`) | #5 → #8 → #10 |

## Work breakdown

GitHub issues #1-#15 implement this spec; #12 tracks questions for Flower. #9 (Streamlit rewire) is closed as won't-do; #10 is now the Fieldnote frontend work.

## Open

Remote Nebius nodes need the SuperLink fleet API reachable beyond 127.0.0.1 (or SuperGrid's own); whether Nebius-hosted SuperNodes can join the hackathon federation; Hub bundle size limits; team registration (Typeform).
