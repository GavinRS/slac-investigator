# Existing Flower provider: live preflight blocked

Run ID: `68148113580483690`. Run series: `862020108881045729`.

Flower 1.39.0 executed a real diagnostic AgentApp subprocess. It called the installed SDK Responses interface through Flower's injected runtime URL and credential, requesting the configured model `openai/gpt-5.6-sol`. No mock, deterministic fallback or alternate provider was used.

The running AgentApp reported that internal runtime credentials were present, but `FLWR_MODEL_API_KEY` was absent. The provider path resolved to `https://api.flower.ai/v1/responses`.

The runtime returned HTTP **502**, error code **model_provider_error**, with the exact message:

> Model API key is not set (FLWR_MODEL_API_KEY).

Flower recorded the run as `finished / failed`. Its provider guard rejected the request before external inference. The subsequent tool-call exchange, collaborative SLAC investigation and dashboard verification of live findings were not run. No SLAC evidence was analyzed in this probe; no answer labels were supplied.

Configure the existing Flower API key locally as `FLWR_MODEL_API_KEY` in the environment starting SuperLink, then restart `./scripts/start.sh`. Leave the existing endpoint and model configuration unchanged. The UI can remain running. A successful key setup is still only the first prerequisite: model authorization and tool-call support need the requested live checks afterward.

The optional Nebius adapter, existing provider settings and running services were left unchanged. The diagnostic component was selected only in an in-memory probe bundle; the project AgentApp configuration was not modified. The safe application event trace and status are in `flower-live-check.json`.
