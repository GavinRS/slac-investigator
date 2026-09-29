# Demo guide

What to type, and what each case should show. Four real SLAC events, replayed. Nothing here controls equipment.

## What to ask

Ask about one event. The question goes to all three instrument agents.

- "Was the beam disturbed during slac-001, and do we know why?"
- "The klystron at slac-003 looks off. Did it actually disturb the beam?"
- "Could low charge explain the position readings?" (follow-up question after a run)

In `flwr chat` you can type the sentence directly; mention the event id (`slac-001` … `slac-004`). Without one it uses `slac-001`.

## The two cases worth showing

| Case | Events | RF node | LTU node | Dump node | What it means |
|---|---|---|---|---|---|
| Beam really disturbed | slac-001, slac-002 | suspicious | suspicious | suspicious | All three instruments see it at the same time. Live Nebius run on slac-001: beam disturbance **corroborated**, unique cause **not established**, 0.9% of raw data shared. |
| RF glitch, beam fine | slac-003, slac-004 | suspicious | normal | normal | The klystron looks off but neither beam instrument saw anything. Live Nebius runs: beam disturbance **not corroborated**, unique cause **not established**, under 1% of raw data shared. |

The node columns come from the deterministic per-instrument checks; live model runs can word them differently. All four events have been run live on the grid and on the single agent; see the README comparison table.

Each node sends about 1-2 KB of summary numbers and holds 83-545 KB of raw samples, so the orchestrator sees under 1% of the raw data. A single agent would need all of it.

## How to run it

Local 3-node grid (each node holds only its own instrument's data):

```sh
./scripts/start_grid.sh          # terminal 1: SuperLink + rf, ltu, dump nodes
./scripts/start_api.sh           # terminal 2: API on 127.0.0.1:8080
python3 -m http.server 5173 --bind 127.0.0.1 --directory frontend   # terminal 3
```

Open `http://127.0.0.1:5173/?mode=live`, pick an event, type the question, start. Without `?mode=live` the page plays saved replays, which is the fallback if a live run is slow.

Terminal only: `.venv/bin/python -m slac_assistant.runtime --mode collaborative --event slac-001`.

Model: set in `.env` (Nebius MiniMax-M3 by default, about 25 s per grid run; Endeavor via Flower's gateway as the fallback, slower). See the README.

## Honest limits

- Four hand-picked events. No accuracy claim.
- The orchestrator's model answer sometimes comes back incomplete; the app then combines the node reports with fixed rules and says so.
- Older saved replays (slac-001, slac-003 from the first prototype) used OpenAI models, not Nebius or Endeavor.
