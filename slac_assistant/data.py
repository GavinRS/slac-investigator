"""Read-only event access. Evaluation labels deliberately have no loader here."""
from pathlib import Path
import json, re
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def event_ids(root=None): return sorted(p.stem for p in Path(root or ROOT/'data/events').glob('slac-???.json'))
def load_event(event_id,root=None):
    if not re.fullmatch(r'slac-\d{3}',event_id) or event_id not in event_ids(root): raise ValueError('Unknown event')
    d=Path(root or ROOT/'data/events')
    meta=json.loads((d/f'{event_id}.json').read_text())
    payload=json.loads((d/f'{event_id}.arrays.json').read_text())
    arrays={k:np.asarray(v,dtype=np.int64 if k.endswith('_time_ns') else float) for k,v in payload.items()}
    for a in arrays.values(): a.flags.writeable=False
    return meta,arrays

def plot_event(event_id, label=None):
    import matplotlib.pyplot as plt
    m,a=load_event(event_id); end=m['candidate_end_ns']; start=(m['candidate_start_ns']-end)/1e9
    fig,axes=plt.subplots(3,1,figsize=(12,8),sharex=True,layout='constrained')
    i=m['channels']['health'].index(m['station']+':AMPL'); x=a['health'][:,i]; t=(a['health_time_ns']-end)/1e9; ok=np.isfinite(x)
    axes[0].step(t[ok],x[ok],where='post',color='#008d94',label=m['station']+':AMPL'); axes[0].plot(t[ok],x[ok],'.',color='#008d94')
    axes[0].set_ylabel('AMPL (source units)')
    bt=(a['bpm_time_ns']-end)/1e9
    for j,c in enumerate(m['channels']['bpm']):
        if c.endswith('TMIT'): axes[2].plot(bt,a['bpm'][:,j],lw=.8,label=c)
        else:
            # The published transform uses 100 for invalid low-charge positions.
            v=a['bpm'][:,j].copy(); v[a['bpm'][:,j-1]<1e8]=np.nan
            axes[1].plot(bt,v,lw=.8,label=c)
    axes[1].set_ylabel('Scaled position\n(source transform)');axes[2].set_ylabel('TMIT (source units)')
    for ax in axes:
        ax.axvspan(start,0,alpha=.12,color='#eeac45'); ax.grid(alpha=.15); ax.legend(fontsize=7,loc='upper left')
    axes[-1].set_xlim(max(-20,bt[0]),max(1,float(t[-1]))); axes[-1].set_xlabel('Seconds relative to recorded candidate end • no timestamp shifts')
    title=f'{event_id} | SLAC public measured data | {m["station"]}'
    if label is not None: title+=f' | human label: {label}'
    fig.suptitle(title,fontsize=13)
    return fig
