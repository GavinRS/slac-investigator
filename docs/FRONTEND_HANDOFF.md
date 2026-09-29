# Frontend ownership and reconciliation handoff

Updated 2026-09-29. This window now owns `frontend/` and frontend deployment preparation only. Backend, provider configuration, authentication, Flower processes and Python investigation logic belong to the other window. No additional backend changes or model runs will be made by this window.

## Earlier changes from this window to reconcile

All are uncommitted in the shared workspace. Do not reset the whole working tree; it also contains the other window's changes.

| File / area | Earlier change | Backend owner action |
|---|---|---|
| `scripts/start.sh` | Loads ignored `.env.local` with exported variables before SuperLink, disables shell tracing, selects `.flower/slac.sqlite` | Review/retain/replace. SQLite restart durability was not verified for the serving process. |
| `.env.local` (ignored) | References Pacterra's existing local env file and documented Responses endpoint; no credential copied | Backend owner owns this from now on. No secret values in this handoff. |
| `pyproject.toml` | Model changed from routing name `openai/gpt-5.6-sol` to direct-provider ID `gpt-5.6-sol`, based on Pacterra | Reconcile with provider contract. |
| `slac_assistant/ui.py` | Existing Streamlit model field reads the default from pyproject instead of a separate hardcoded value | Preserve existing working UI until replacement is ready. |
| `slac_assistant/workflow.py` | Exact channel catalog in model instructions; explicit unknown-channel error; `finding_rejected` event; one correction-only turn inside shared 12-call budget; instructions included in input-size accounting | Review separately from older optional-provider changes. |
| `tests/test_workflow.py` | Two regression tests for channel correction and shared-budget enforcement | 28 total tests passed at handoff. Test fixtures are not live results. |
| `README.md` | Startup path, live validation status, limitations, links to execution review | Backend owner can reconcile startup sections. Frontend documentation will be separate. |
| Optional Nebius files and `.gitignore`, `agent_app.py`, `runtime.py` changes | Pre-existing optional adapter/probe plumbing from earlier work | Paused, preserved, never used for these live runs. Do not delete as part of frontend work. |

## Saved live results from this window

- Initial `slac-001`: `artifacts/runs/4210859065409350628.json`.
- Same-series human follow-up: `artifacts/runs/16085169257987671247.json` (series `10907516783703553172`).
- Dashboard `slac-003`: `artifacts/runs/1795740798858395915.json`.
- Review: `artifacts/flower-provider-resolution.md` and `.json`.
- Earlier successful/failed attempts remain preserved; the other window's `artifacts/preserved-successful-runs/` and `flower-retry-*` files were not produced by this window and must not be overwritten.

Important semantic findings: slac-001 conclusions are broadly supported but a precise low-charge onset claim is one sample early for two BPMs. slac-003's narrative says no beam corroboration, while its enum says `corroborated` for RF-only evidence. The frontend must preserve original model output, label review concerns, and avoid presenting that enum as a confirmed beam fault.

## Frontend boundary and requested API contract

Static GitHub Pages site in `frontend/`. It must never contain provider keys or call a provider directly. It will distinguish **saved-run replay** (historical model findings, zero new inference) from **live execution** (backend-confirmed run). No fallback from a failed live request to replay.

Backend owner: please publish the authoritative API contract as a shared file or URL, including event/plot retrieval, starting an investigation, progress/events, terminal states, retrieving a report, continuing a series with a human question, errors, timestamp representation, CORS/allowed frontend origin, and authentication expectations. These are integration needs, not proposed endpoints. Frontend will not invent or implement backend/auth routes.

Lovable is optional. No Lovable project has been supplied and none has been created. If used, it owns presentation changes within `frontend/`; it must consume the same contract and preserve replay/live labels, evidence IDs, provenance, uncertainty and original initial/follow-up assessments. Coordinate through this file and `frontend/README.md` before replacing files.

## Publishing boundary

Prepare a static Pages artifact containing only reviewed frontend assets. Do not upload the repository root, raw datasets, environment files, `.flower`, runtime logs or unreviewed artifacts. GitHub Pages site visibility is separate from repository privacy; deployment must be checked before publication. No Pages deployment is claimed at this handoff.

## Contract received and frontend implementation

Backend owner supplied `docs/FRONTEND_API.md` during this pass. The frontend consumes v1 routes and schema-v2 findings via `frontend/assets/api.js` and `live.js`. GitHub Pages remains replay-only; local live UI is origin-gated. New findings show beam disturbance and unique-cause attribution independently. Legacy replay findings keep original mixed-scope labels, with both new dimensions explicitly not assessed and the saved evidence-review warnings.

This pass added/changed only `frontend/` and this handoff. No additional backend edits, authentication changes, process restarts, or live model investigations were performed. Static preview uses port 5173. Pages publication is prepared but has not occurred. The initial local API GET failed in the browser. The owner independently verified host HTTP 200/CORS; a frontend fetch receiver-binding issue was corrected and regression-tested. Real browser connectivity after that fix remains unverified because the browser surface became unavailable.
