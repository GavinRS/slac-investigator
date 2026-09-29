"""Per-instrument data slices: each Grid node owns one instrument's readings (spec §1)."""
from pathlib import Path
import os
from .data import load_event
INSTRUMENTS=('rf','ltu','dump')
BPM_PREFIX={'ltu':'BPMS:LTUH:','dump':'BPMS:DMPH:'}

def select(meta,arrays,instrument):
    if instrument not in INSTRUMENTS: raise ValueError('Unknown instrument')
    group='health' if instrument=='rf' else 'bpm'; names=meta['channels'][group]
    idx=[i for i,c in enumerate(names) if instrument=='rf' or c.startswith(BPM_PREFIX[instrument])]
    m={**meta,'instrument':instrument,'channels':{group:[names[i] for i in idx]}}
    a={group:arrays[group][:,idx],f'{group}_time_ns':arrays[f'{group}_time_ns']}
    for v in a.values(): v.flags.writeable=False
    return m,a

def load_slice(event_id,instrument,root=None):
    """root=None reads bundled data/events/; a path reads a local folder with the same layout."""
    return select(*load_event(event_id,root),instrument)

def detect_local_instrument():
    d=os.environ.get('SLAC_NODE_DATA_DIR') or os.environ.get('FLWR_FILESYSTEM_ALLOWED_DIRS','').split(os.pathsep)[0]
    try: name=(Path(d)/'instrument.txt').read_text().strip() if d else None
    except OSError: return None
    return name if name in INSTRUMENTS else None
