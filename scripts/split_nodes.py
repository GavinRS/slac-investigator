#!/usr/bin/env python3
"""Split bundled replay events into isolated instrument folders for a local Grid."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from slac_assistant.data import ROOT, event_ids
from slac_assistant.instruments import INSTRUMENTS, load_slice


def split_nodes(output=None):
    output = Path(output) if output is not None else ROOT / "nodes"
    for instrument in INSTRUMENTS:
        folder = output / instrument
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "instrument.txt").write_text(instrument + "\n")
        for event_id in event_ids():
            meta, arrays = load_slice(event_id, instrument)
            (folder / f"{event_id}.json").write_text(json.dumps(meta, indent=2) + "\n")
            # Preserve the source export's sparse RF NaNs (no new update).
            (folder / f"{event_id}.arrays.json").write_text(
                json.dumps({k: v.tolist() for k, v in arrays.items()}, separators=(",", ":")) + "\n")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "nodes")
    args = parser.parse_args()
    print(f"Instrument data written to {split_nodes(args.output)}")
