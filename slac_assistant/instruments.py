"""Read-only instrument partitions of bundled or node-local event data."""
import json
import os
from pathlib import Path
import re

import numpy as np

from .data import ROOT

INSTRUMENTS = ("rf", "ltu", "dump")


def local_data_dir():
    """Explicit node data takes precedence over the first filesystem directory."""
    configured = os.environ.get("SLAC_NODE_DATA_DIR")
    if not configured:
        configured = os.environ.get("FLWR_FILESYSTEM_ALLOWED_DIRS", "").split(",")[0].strip()
    return Path(configured).expanduser() if configured else None


def detect_local_instrument():
    root = local_data_dir()
    if root is None:
        return None
    try:
        instrument = (root / "instrument.txt").read_text().strip()
    except (OSError, UnicodeError):
        return None
    return instrument if instrument in INSTRUMENTS else None


def load_slice(event_id, instrument, root=None):
    """Return only the requested channel family and its original int64 timestamps.

    Local folders have the same flat <event>.json / <event>.arrays.json layout
    as data/events. Metadata retains provenance, but its channel catalog is sliced.
    """
    if instrument not in INSTRUMENTS:
        raise ValueError("Unknown instrument")
    if not isinstance(event_id, str) or not re.fullmatch(r"slac-\d{3}", event_id):
        raise ValueError("Unknown event")
    folder = Path(root) if root is not None else ROOT / "data/events"
    try:
        meta = json.loads((folder / f"{event_id}.json").read_text())
        payload = json.loads((folder / f"{event_id}.arrays.json").read_text())
    except FileNotFoundError as exc:
        raise ValueError("Unknown event in instrument data folder") from exc
    family = "health" if instrument == "rf" else "bpm"
    prefix = "BPMS:LTUH:" if instrument == "ltu" else "BPMS:DMPH:"
    channels = meta["channels"].get(family, [])
    indices = [i for i, channel in enumerate(channels)
               if instrument == "rf" or channel.startswith(prefix)]
    if not indices:
        raise ValueError("Instrument channels are absent from this data folder")
    values = np.asarray(payload[family], dtype=float)
    times = np.asarray(payload[family + "_time_ns"], dtype=np.int64)
    if values.ndim != 2 or values.shape != (len(times), len(channels)) or times.ndim != 1:
        raise ValueError("Invalid instrument array dimensions")
    arrays = {family: values[:, indices], family + "_time_ns": times}
    meta["channels"] = {family: [channels[i] for i in indices]}
    for array in arrays.values():
        array.flags.writeable = False
    return meta, arrays
