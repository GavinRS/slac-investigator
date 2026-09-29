# Frontend API contract (v1)

Authoritative implementation: `slac_assistant/api.py`. Start with `./scripts/start_api.sh` after starting Flower with `./scripts/start.sh`. Default API base is **http://127.0.0.1:8080**. Interactive OpenAPI documentation: `/docs`; machine-readable schema: `/openapi.json`. The existing Streamlit UI remains usable independently.

For the three-node demo started by `./scripts/start_grid.sh`, instead use `FLOWER_CONTROL_URL=http://127.0.0.1:18000 ./scripts/start_api.sh`. This selects the isolated Grid runtime rather than the port-8000 developer runtime.

## Deployment, credentials and ownership

This is a **local, single-user development API**, bound to loopback, with **one Uvicorn worker**. There is no frontend login or public authentication endpoint. Default CORS origins are `http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:5173`, and `http://127.0.0.1:5173`. `INVESTIGATOR_CORS_ORIGINS` can set an explicit comma-separated list. Cookies are not used; allowed methods are GET/POST and the allowed request header is Content-Type. Only localhost/127.0.0.1 hosts are accepted. CORS is not authentication.

**GitHub Pages stays in saved-run replay mode.** This service is not a hosted backend and does not promise that an HTTPS Pages origin can reach localhost. Public live execution requires an authenticated HTTPS backend deployment, explicit origin configuration, and an authorization policy; that deployment is not implemented by this local API. Do not expose this server publicly or add a provider credential to browser code.

The browser never supplies provider keys, provider names, model IDs, Flower addresses, or Flower internal credentials. Unknown request fields are rejected without echoing their values. SuperLink alone loads the model provider from the private `.env` through `scripts/start.sh`. The API reads the model from `INVESTIGATOR_MODEL` (environment, then `.env`, then the app default), uses Flower's Control API (`FLOWER_CONTROL_URL`, default `http://127.0.0.1:8000`), and never makes direct provider requests. The API never reads the provider key.

## Endpoints

| Method | Path | Success | Purpose |
|---|---|---|---|
| GET | `/api/v1/events` | 200 | `{ "event_ids": ["slac-001", ...] }` |
| GET | `/api/v1/events/{event_id}` | 200 | Source metadata, channel catalog, candidate interval and limitations; no evaluation labels |
| GET | `/api/v1/events/{event_id}/plot` | 200 | Original sampled plot traces described below |
| POST | `/api/v1/investigations` | 202 | Queue a new investigation and series |
| GET | `/api/v1/investigations/{id}` | 200 | Status and links |
| GET | `/api/v1/investigations/{id}/activity?after=0&limit=100` | 200 | Ordered activity page |
| GET | `/api/v1/investigations/{id}/result` | 200 | Completed result; 409 until completed, including failures |
| POST | `/api/v1/series/{series_id}/follow-ups` | 202 | New investigation run in the same series |

POST requests must use `Content-Type: application/json`. There is no SSE or WebSocket contract; poll status/activity approximately once per second. A POST creates work once per request; **there is no idempotency-key support or automatic retry**. Disable duplicate submissions. If a POST's network response is lost, do not silently resend it: work may already be running.

### Start investigation

```json
{"event_id":"slac-001","mode":"grid"}
```

`mode` accepts `grid` (default), `collaborative` (legacy alias), `baseline`, or `smoke`. Grid executes instrument-local agents and a summary-only lead. Smoke exercises the Grid routing deterministically without inference. Grid-path reports use `mode: "grid"` and distinguish `execution_mode: "model"` from `"smoke"`; baseline preserves the single-process Finding v2 workflow. The event must exist in `/events`. No human question or series ID is accepted here; use the follow-up route to continue.

The 202 response and subsequent status responses use the same shape (the job may already be running when 202 arrives):

```json
{
  "id": "api-investigation-uuid",
  "series_id": "api-series-uuid",
  "event_id": "slac-001",
  "mode": "grid",
  "model": "dedicated/flowerai/MiniMax-M3-OOLI9o",
  "status": "queued",
  "created_at": "2026-09-29T22:00:00+00:00",
  "updated_at": "2026-09-29T22:00:00+00:00",
  "flower_run_id": null,
  "flower_series_id": null,
  "error": null,
  "links": {
    "status": "/api/v1/investigations/api-investigation-uuid",
    "activity": "/api/v1/investigations/api-investigation-uuid/activity",
    "result": "/api/v1/investigations/api-investigation-uuid/result",
    "followup": "/api/v1/series/api-series-uuid/follow-ups"
  }
}
```

The response includes a `Location` header equal to the status URL. Follow returned links. API UUIDs are distinct from Flower IDs; never interchange them. Flower IDs become decimal **strings** once Flower accepts the run.

States: `queued` → `running` → `completed` or `failed`; `interrupted` marks unfinished records after an API restart. All three of `completed`, `failed`, and `interrupted` are terminal. Only `completed` has an accepted result. Receiving a `report` activity event is not completion: Flower must still confirm finished/completed.

### Retrieve activity

```json
{
  "investigation_id": "api-investigation-uuid",
  "status": "running",
  "events": [
    {"seq":1,"created_at":"2026-09-29T22:00:01+00:00","event":{"kind":"started","event_id":"slac-001","mode":"grid","model":"dedicated/flowerai/MiniMax-M3-OOLI9o"}},
    {"seq":2,"created_at":"2026-09-29T22:00:02+00:00","event":{"kind":"tool_request","agent":"equipment","analysis":"equipment"}}
  ],
  "next_cursor": 2,
  "has_more": false
}
```

`after` is an exclusive integer sequence cursor, initially 0. `limit` is 1–200 (default 100). Fetch additional pages immediately while `has_more`; otherwise resume polling with `next_cursor`. An empty page leaves the cursor unchanged. On terminal status, drain remaining pages; activity is durable and can be replayed after reload. Deduplicate by `(investigation_id, seq)`.

Activity `event.kind` values:

- `started`: `event_id`, `mode`, `model`, optional `budget`; Grid also supplies `execution_mode`.
- `delegation`: `agent`, `to`, `question`, `analysis`; Grid adds `node_id` (null for local fallback) and `instrument` (`rf`, `ltu`, or `dump`).
- `tool_request`: `agent`, `analysis`.
- `tool_result`: `agent`, `evidence`. Baseline evidence includes ref, analysis, event_id, source, hdf5_group, interval_ns, result, and limitations. Grid evidence contains `ref`, `kind: "node_summary"`, and compact numeric `result`; the event adds `instrument`.
- `finding`: `finding` with schema-v2 fields described below.
- `finding_rejected`: `agent`, `error`, optional `draft`; validation feedback, not an accepted finding.
- `node_report`: `report` with the instrument-local contract below.
- `data_shared`: `data_shared` with raw array byte count, serialized report byte count, and their percentage.
- `report`: `report`, provisional until completed status; runtime IDs/metrics may only be final in `/result`.
- `failed`: sanitized `error` with `code` and `message`.

Ignore unfamiliar event kinds gracefully. These are application activity and concise findings, not private model reasoning.

#### Grid event envelopes

Node events use `{"kind":"node_report","report":{...}}`; the nested report follows the instrument contract below. Sharing events use `{"kind":"data_shared","data_shared":{"raw_bytes_held":370368,"payload_bytes":1536,"percent_shared":0.4147,"raw_samples_shared":0,"complete":true}}`. These are illustrative values, not measurements from a run.

`payload_bytes / raw_bytes_held * 100` is the summary/raw byte ratio, not raw-sample disclosure. Label it **summary / raw bytes**. Baseline 100% represents conceptual centralized access, not raw arrays sent to the model. Incomplete accounting must be displayed as unavailable.

### Retrieve results: two independent questions

`GET .../result` returns `{ "investigation_id": "...", "series_id": "...", "report": {...} }`.

The report contains `result_schema_version: 2`, `benchmark_eligible: false`, `event_id`, `mode`, `model`, `model_execution_path`, `final`, `findings`, `evidence`, `metrics`, `flower_run_id`, `flower_series_id`, `runtime`, and `wall_latency_s`. Metrics include actual model/tool calls, token usage (nullable), latency, and cost (nullable); null cost does not mean free.

Every finding, including `final`, has independent dimensions:

```json
{
  "beam_disturbance": {
    "status": "not_corroborated",
    "rationale": "No sustained disturbance was corroborated in the available charge-valid BPM readings.",
    "tool_result_refs": ["T-example-beam"]
  },
  "unique_cause": {
    "status": "not_established",
    "rationale": "The replay evidence does not establish a unique causal RF station.",
    "tool_result_refs": ["T-example-rf","T-example-beam"]
  }
}
```

This example illustrates the shape, not a newly verified live finding. The remaining finding fields are `finding_id`, `agent`, `observation`, `source_channels`, `time_interval_ns`, `tool_result_refs`, `supporting_evidence`, `conflicting_evidence`, `data_limitations`, and nullable `requested_next_check`.

Display headings **“Beam disturbance corroborated?”** and **“Unique cause established?”** independently:

- Beam status: `corroborated`, `not_corroborated`, `insufficient_evidence`, or `not_assessed`. An RF-only excursion cannot make beam corroboration positive. A negative heuristic is not proof of normality.
- Unique cause status: `established`, `not_established`, `insufficient_evidence`, or `not_assessed`. `not_established` does not assert that causation is absent. Coincidence or a positive beam heuristic is insufficient to establish a unique cause.
- Each dimension has its own rationale and evidence refs; assessed dimensions require refs validated against the finding's available evidence. Structural citation validation does not establish semantic accuracy.
- There is **no combined `assessment` field in v2**. The external evaluator emits no prediction/agreement scores; the source anomaly labels do not provide separately adjudicated truth for these questions.

Grid reports additionally contain `node_reports`, `grid`, `data_shared`, and `onset_alignment`. The frozen Grid shape is:

```json
{
  "mode": "grid",
  "execution_mode": "model",
  "result_schema_version": 2,
  "grid": {
    "nodes_seen": 3,
    "assignment": {"rf": "14", "ltu": "7", "dump": "23"},
    "fallback": false
  },
  "data_shared": {
    "raw_bytes_held": 1000000,
    "payload_bytes": 9000,
    "percent_shared": 0.9,
    "raw_samples_shared": 0,
    "complete": true
  }
}
```

These numbers illustrate the schema, not a measured run. `fallback: true` means no Grid nodes were available and the instrument checks ran in the orchestrator process; label this explicitly in the UI. A smaller node count can assign several instrument roles to one capable node. Node IDs are strings. `data_shared.percent_shared` is serialized UTF-8 node-report bytes divided by instrument array bytes, multiplied by 100; it excludes transport overhead and is not an inference token or network billing measurement. Repeated follow-up reports count toward the numerator; raw arrays are counted once per instrument. `complete: false` marks incomplete reply accounting.

Each node report has `kind: "node_report"`, `instrument`, `role_source` (`local_data` or `assigned`), `event_id`, `assessment` (`suspicious`, `normal`, or `insufficient_evidence`), `observation`, compact numeric `summary`, `tool_refs`, `raw_bytes_held`, `payload_bytes`, `limitations`, and model-call `metrics`. This local `assessment` is a heuristic instrument result, never a replacement for either final Finding v2 dimension. No raw sample arrays are included; numeric lists are bounded to 10 entries. `payload_bytes` includes the byte-count field itself. `onset_alignment` compares recorded integer nanoseconds without timestamp shifts or a fixed RF delay assumption; coincidence does not establish a unique cause.

Historical prototype artifacts were removed from this working tree and remain available in Git history and `backup/pre-grid-prototype`. Any existing exported legacy replay must retain its original narrative and caveats; display missing v2 dimensions as `not_assessed`, never infer a v2 verdict from a historical mixed-scope label. Replay IDs cannot be used as API series UUIDs.

### Follow-up in the same series

```http
POST /api/v1/series/{series_id}/follow-ups
Content-Type: application/json
```

```json
{"question":"Could low charge explain the position readings?"}
```

Question: nonempty after trimming, maximum 4,000 characters. Response: 202 status object with a **new investigation ID** and the **same API series ID**. The event, mode, configured model, and Flower series ID are inherited from the initial run. The backend passes the exact integer Flower series ID to `run_flower`, allowing AgentApp Context to load the prior final assessment. It never silently creates a replacement series when continuation fails.

Only one pending/running job per series is allowed; follow-up requires the latest run to be completed and cannot follow smoke, failed, or interrupted runs. Conflicts return 409. Globally one background worker processes jobs in queue order. Keep the initial result visible and render the follow-up separately while it runs; do not overwrite historical conclusions.

### Event metadata and plot data

Metadata is the event's local provenance record, with exact nanosecond fields serialized as strings. No source labels are exposed.

Plot response: `event_id`, `reference_time_ns`, `candidate_interval_ns`, `traces`, `downsampled: false`, `notes`. Each trace has `channel`, `family` (`health` or `bpm`), `time_ns` (string array), `relative_s` (number array), and `values` (number/null array). Arrays in a trace have equal lengths. The health trace is the candidate AMPL channel; BPM traces contain the available charge and position channels.

RF nulls mean no new update, never zero: hold only a previously observed value. Position samples whose local TMIT is below 1e8 are masked as null. Plot `relative_s` relative to the recorded candidate end; do not infer or apply timing shifts. Exact `_ns` fields throughout API payloads—including lists such as `interval_ns`—are decimal strings to avoid JavaScript's 53-bit integer precision loss. Use `BigInt` for exact differences; use the supplied relative seconds for plotting.

## Errors and persistence

Request errors: 404 for unknown event/run/series, 422 for invalid bodies/query parameters, 409 for unavailable results or invalid follow-up state. Ordinary errors use `{ "detail": ... }`; validation errors list field location/type and a generic message without rejected input values. A 409 result response has `{ "detail": { "status": "running|queued|failed|interrupted", "error": null_or_error_object } }`.

Asynchronous failure is returned via status `failed`, its `error`, and a final activity event. Error codes are `missing_environment`, `credential_rejected`, `billing_quota`, `model_unavailable`, `rate_limited`, or `workflow_failed`; unrecognized failures remain unclassified. Provider exception bodies and credentials are not returned. `server_restarted` accompanies `interrupted` records. No automatic retry or replay fallback occurs.

API records/activity/results live in Git-ignored `artifacts/api/state.sqlite3` (user-only permissions). Reloading the browser loses no recorded activity. Restarting the API marks its queued/running records interrupted; it does not cancel or resubmit Flower work, which may still finish independently. Completed API records remain available. Follow-up continuity across a **Flower** restart additionally depends on Flower's own persistent series store; the API does not reconstruct missing Context. If that series is unavailable, continuation fails explicitly.

## Verification scope

Contract tests cover asynchronous start/poll/results, pagination, same-series continuation, concurrent follow-up rejection, input validation, error classification/redaction, interrupted-run recovery, smoke follow-up rejection, nanosecond strings, and Grid event forwarding. These tests use protocol fixtures and do not establish model accuracy. A separate local smoke check exercises real Flower through the HTTP API without new model inference.

Live runtime verification is reported separately from fixture contract tests; historical prototype checks do not establish the current Grid path or model accuracy.
