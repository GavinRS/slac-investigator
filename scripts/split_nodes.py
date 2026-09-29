"""Write nodes/<instrument>/ local slice folders (per-event files + instrument.txt) for the local Grid demo."""
import argparse,json
from pathlib import Path
from slac_assistant.data import ROOT,event_ids
from slac_assistant.instruments import INSTRUMENTS,load_slice

def split(out=ROOT/'nodes'):
    for inst in INSTRUMENTS:
        d=Path(out)/inst;d.mkdir(parents=True,exist_ok=True);(d/'instrument.txt').write_text(inst+'\n')
        for e in event_ids():
            m,a=load_slice(e,inst)
            (d/f'{e}.json').write_text(json.dumps(m,indent=2))
            (d/f'{e}.arrays.json').write_text(json.dumps({k:v.tolist() for k,v in a.items()}))
    return Path(out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default=ROOT/'nodes')
    print(split(p.parse_args().out))
