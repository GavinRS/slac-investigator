# Nebius compatibility assessment

Inspected 2026-09-29. Installed packages: **Flower 1.39.0**, **OpenAI Python SDK 2.54.0**. The SDK is used as an HTTP client; it does not imply OpenAI is the provider.

## Existing path, preserved

`Investigation.loop` → `client.responses.create` → Flower-injected `FLWR_RUNTIME_BASE_URL` / `FLWR_RUNTIME_API_KEY` → Flower model task → the SuperLink's `FLWR_MODEL_API_ENDPOINT` (default `https://api.flower.ai/v1/responses`).

The installed `flwr/supercore/task_process/model/provider.py`, lines 78–95, explicitly rejects endpoints not ending in `/responses`. It forwards a Responses payload; it contains no Chat Completions conversion. An offline test exercises that actual installed guard and verifies no HTTP request is sent. The [Flower local runtime guide](https://flower.ai/docs/agent/how-to-guides/run-with-local-superlink.html) likewise requires an Open Responses-compatible endpoint.

`pyproject.toml`, `scripts/start.sh`, UI defaults, and existing provider environment settings were not changed. No existing server was restarted. Current task-shell credential presence checks found neither Flower nor Nebius keys; this alone does not establish what another already-running process has inherited.

## Provider/protocol conclusion

Flower's installed model runtime **does not directly support the supplied Chat Completions protocol**. A base-URL swap is insufficient.

Nebius's [general API reference](https://api.tokenfactory.nebius.com/docs) advertises `/v1/chat/completions`, `/v1/responses`, and `/v1/models`. The downloaded general OpenAPI schema identifies version `20260928-144ca2fd4`. That is evidence about the general reference, not an authenticated capability check of the US regional service or the event model. The exact US host's public `/openapi.json` returned HTTP 404. No authenticated regional Responses request was made, and support for that route is **unverified**, not disproven. If its Responses implementation is subsequently verified against Flower, a native runtime path could be assessed separately.

Nebius documents the Chat Completions [function-call round trip](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling): assistant `tool_calls`, application-side execution, then `role=tool` messages carrying matching `tool_call_id`. We use that explicit contract.

## Opt-in application adapter

`Flower SuperLink → AgentApp subprocess → Investigation → NebiusChatAdapter → OpenAI SDK chat.completions.create → https://api.tokenfactory.us-central1.nebius.com/v1/chat/completions`

Flower continues to install and execute the AgentApp, persist Context, and transport application findings/events. **These calls bypass Flower's model tasks, Grid model routing and model-task usage accounting.** Application reports collect Nebius's returned token usage; monetary cost remains unknown. This is not a new Flower-native provider integration, distributed deployment or federated learning.

The adapter exposes only the small responses-shaped interface used by this application. It translates text history, function definitions, assistant calls and local tool outputs; groups multiple calls into one assistant message; preserves call IDs; maps `max_output_tokens` to Chat Completions `max_tokens`; maps prompt/completion usage to the report fields. It rejects incomplete/truncated responses, unadvertised tools, malformed histories and unsupported message types. It makes non-streaming requests with no automatic retry. Separate reasoning fields are not persisted or emitted; reasoning markup in visible text is rejected. Provider error bodies and credentials are not printed.

No attempt is made to offer a complete Responses API, arbitrary connector support or streaming translation. Same model/analysis budgets and read-only evidence tools apply. The current UI stays on its original provider; the Nebius path is explicitly selected by CLI/test runner.

## Required configuration and live checks

These values must be available in the shell starting the **new** test SuperLink:

- `NEBIUS_API_KEY`: locally configured token. Never paste it into chat or store it in the repo.
- `NEBIUS_MODEL`: exact event-approved model identifier, without an invented routing prefix. There is no default. Before any inference, the adapter requires this ID to appear in the authenticated regional `GET /v1/models` response. Catalog presence does not prove tool support; the tool probe tests that.
- `NEBIUS_EVENT_CREDITS_CONFIRMED=1`: set only after the organizers/account owner confirm event credits cover Token Factory serverless inference for this account, region and model. This is an operator attestation, not an automatic billing verification.

No dedicated endpoint, GPU, account, token or cloud resource is provisioned by these scripts.

After confirmation and local configuration, use a separate terminal for:

```sh
PYTHONPATH=. .venv/bin/python scripts/start_nebius_check.py
```

This creates a new **local** Flower runtime on `127.0.0.1:8001` (Fleet `127.0.0.1:19093`), with state under ignored `.flower-nebius-check/`. It does not touch the existing server on 8000 or UI on 8501. It removes `FLWR_MODEL_API_KEY` and `FLWR_MODEL_API_ENDPOINT` only from the new child environment so automatic Flower conversation-title generation cannot charge the existing provider. Consequently, a missing-Flower-key title-generation log message is expected on this isolated runtime. Nebius model calls use separate variables inside the AgentApp. No provider settings in the parent shell or existing service are altered.

In another terminal with the same confirmed configuration:

```sh
PYTHONPATH=. .venv/bin/python scripts/verify_nebius.py
```

The runner stops at the first failed stage:

1. **Text**: one Chat Completions response with an expected marker, inside a Flower AgentApp.
2. **Tool round trip**: one explicitly forced read-only function call, local SLAC quality analysis, then a second model response whose reference and sample count must equal the actual result. Forcing a tool here is a protocol test, not scripted investigator behavior.
3. **Investigation**: a complete collaborative investigation of `slac-001`, with schema/reference checks and actual Flower `finished/completed` status.

Results go to `artifacts/nebius-live-verification.json` and individual `artifacts/runs/` reports. They include the exact model, provider path, run IDs, token usage and latency. Probes do not write investigation Context. Credit exhaustion, unsupported tools, unavailable model, invalid JSON or incomplete output can still block live completion; they do not trigger fallback to another billed provider.

Optional individual execution:

```sh
.venv/bin/python -m slac_assistant.runtime --address http://127.0.0.1:8001 --provider nebius-chat --probe text
.venv/bin/python -m slac_assistant.runtime --address http://127.0.0.1:8001 --provider nebius-chat --probe tool
.venv/bin/python -m slac_assistant.runtime --address http://127.0.0.1:8001 --provider nebius-chat --event slac-001
```

## Verification status at implementation

**26 offline tests pass.** New HTTP-mocked tests cover text, local-tool round trip, model-ID verification, a complete specialist/coordinator protocol flow with a follow-up, usage mapping, multiple tool calls, incomplete output, safe error messages and preservation of the Flower default. They are contract tests with explicit fixture replies, **not live Nebius results**.

All three requested live stages remain **not run**: event credit coverage is unconfirmed, no Nebius token is configured in the inspected shell, and no approved model ID has been supplied. No inference charges were intentionally incurred during this assessment. Public documentation GETs were the only external Nebius requests.
