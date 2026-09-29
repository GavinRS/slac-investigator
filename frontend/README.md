# Fieldnote frontend

## Preview and verification

```sh
python3 -m http.server 5173 --bind 127.0.0.1 --directory frontend
node --test frontend/tests/*.test.js
PYTHONPATH=. .venv/bin/pytest -q frontend/tests/test_export_replay.py
```

Open [the saved replay](http://127.0.0.1:5173/). Replay makes no backend/model calls and requires no provider credentials. The existing `data/` library retains its historical results and caveats.

## Current Grid replay

A completed Endeavor model Grid run for `slac-001`, **2134321731300912044**, is exported separately under `grid-replay/`. It used three nodes with no local fallback and complete accounting. The node reports contain **9,037 summary bytes / 647,400 raw instrument bytes (1.396%)**, with **zero raw samples shared**. This percentage measures summary size, not raw-sample disclosure. One completed run does not establish accuracy or performance superiority.

Open [the current Grid replay](http://127.0.0.1:5173/?manifest=./grid-replay/manifest.json). This uses the saved model output; opening it does not start another investigation. The view displays the two Finding v2 assessments, node/data-sharing activity, a sharing headline and inspectable summary citations. Full instrument cards remain separate frontend integration work.

Re-export a verified run without overwriting historical replay data:

```sh
.venv/bin/python frontend/export_replay.py --run-id 2134321731300912044 --output-dir frontend/grid-replay
```

Repeat `--run-id` for additional runs; `--run-dir` selects a different trace directory. Explicit exports require completed model Grid reports and complete node/accounting flags. Smoke, failed and partial runs are rejected. The exporter screens nested fields and text for sensitive configuration, credential-like values and private filesystem paths before writing replay files. It reads no credentials or evaluation labels, preserves exact large integers as strings, and leaves source traces untouched.

Custom replay manifests must be on the same origin. Their event file paths resolve relative to the manifest. Historical mixed-scope assessments remain labeled legacy and are never automatically converted to Finding v2.

## Local live mode and API contract

[docs/API.md](../docs/API.md) defines the `/api/v1` job API. Open [local live mode](http://127.0.0.1:5173/?mode=live) only with the backend running. Nothing is submitted until the operator starts an investigation.

- Start body: `{event_id, mode: "grid"}`. The browser supplies no provider, model, key or Flower address.
- Follow-up body: `{question}`, using the returned API series UUID.
- Status and activity are polled; a report event stays provisional until terminal completion and result retrieval.
- Failed/interrupted jobs never become replay results. Lost POST responses are not retried automatically.
- Grid `node_report` and `data_shared` events are supported. Finding v2 keeps beam disturbance and unique cause separate.
- Live mode is restricted to the documented localhost origins; other origins remain saved replay.

Current focused verification: **18 JavaScript tests and 15 exporter Python tests pass**. These cover transport guards, replay compatibility, actual Grid summary evidence shape, partial-accounting display and export rejection of partial/private payloads. Fixtures are offline tests, not evidence of live model success. Browser verification of the newly exported Grid replay is a separate check.

## Packaging and publication

```sh
node frontend/build.mjs
```

The static build copies only `index.html`, `assets/`, historical `data/`, `.nojekyll`, and the explicitly allowed `grid-replay/manifest.json` and `grid-replay/slac-001.json` into `frontend/dist/`. The custom `?manifest=./grid-replay/manifest.json` URL works when serving either `frontend/` or `frontend/dist/`. Additional files in the Grid replay directory are not automatically packaged. Source scripts, tests, runtime logs, configuration and raw source datasets are excluded.

GitHub Pages publication is deferred until the repository is public and the replay payload is reviewed. No deployment is performed by export or local preview. API, authentication and the full Fieldnote instrument-card design remain owned by the corresponding integration work; this bridge adds compatibility without changing that contract.
