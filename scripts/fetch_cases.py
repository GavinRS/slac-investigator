"""Extract a few public SLAC cases using verified HTTP byte ranges, not a 3 GB download."""
import io, subprocess, hashlib, json
from pathlib import Path
import h5py
import numpy as np
import pandas as pd
BASE='https://www.slac.stanford.edu/grp/ad/ard/rfanom/'
class RangeFile(io.RawIOBase):
    def __init__(self, url, size): self.url=url; self.size=size; self.pos=0; self.cache={}; self.downloaded=0
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        return self.pos
    def readinto(self,b):
        data=self.read(len(b)); b[:len(data)]=data; return len(data)
    def read(self,n=-1):
        n=min(n if n>=0 else self.size-self.pos,self.size-self.pos); out=bytearray()
        while n:
            block=self.pos//262144; start=block*262144; end=min(start+262144,self.size)-1
            if block not in self.cache:
                p=subprocess.run(['curl','-fLsS','--max-time','30','-r',f'{start}-{end}',self.url],capture_output=True,check=True)
                if len(p.stdout)!=end-start+1: raise ValueError('Server did not honor byte range')
                self.cache[block]=p.stdout; self.downloaded+=len(p.stdout)
            offset=self.pos-start; part=self.cache[block][offset:offset+n]; out.extend(part); self.pos+=len(part); n-=len(part)
        return bytes(out)

def main():
    out=Path('data/events'); out.mkdir(parents=True,exist_ok=True)
    labels=pd.read_csv('data/raw/labels_AMPL.csv'); candidates=pd.read_csv('data/raw/candidates_AMPL.csv')
    # Purposeful demo selection, not a representative test set. Labels stay outside events.
    chosen=pd.concat([labels[labels.is_anom].head(2),labels[~labels.is_anom].head(2)])
    f=RangeFile(BASE+'klys_anom_dset_AMPL.h5',3222346816)
    manifest=[]; truth={}
    with h5py.File(f,'r') as h:
        print('Top groups',list(h),flush=True)
        for i,row in enumerate(chosen.itertuples()):
            key=str(pd.Timestamp(row.end).value); g=h['candidates'][key]
            c=candidates[candidates.end==row.end].iloc[0]
            eid=f'slac-{i+1:03d}'
            arrays={}; channels={}
            for kind in ['health','bpm']:
                ds=g[kind]; arrays[kind]=ds[:]; arrays[kind+'_time_ns']=np.asarray(ds.attrs['index'],dtype=np.int64)
                channels[kind]=[x.decode() if isinstance(x,bytes) else str(x) for x in ds.attrs['columns']]
                print(eid,kind,ds.shape,channels[kind],flush=True)
            np.savez_compressed(out/f'{eid}.npz',**arrays)
            json_arrays={k:v.tolist() if k.endswith('_time_ns') else np.where(np.isfinite(v),v,None).tolist() for k,v in arrays.items()}
            (out/f'{eid}.arrays.json').write_text(json.dumps(json_arrays,separators=(',',':'),allow_nan=False))
            meta=dict(event_id=eid,provenance='SLAC public measured data',synthetic=False,source_url=f.url,hdf5_group='candidates/'+key,station=str(c.klys),candidate_start_ns=pd.Timestamp(c.start).value,candidate_end_ns=pd.Timestamp(c.end).value,channels=channels,timestamp_unit='nanoseconds since Unix epoch; UTC',license='No explicit dataset license located in inspected index/catalog; do not infer from paper license.',timing='RF diagnostics are asynchronous; documented approximate reporting delay up to 5 seconds, not a calibrated per-event delay.',limitations=['No RF phase data in this extract','No protein measurements','Sparse RF updates; leading missing values remain unknown','BPM position channels are preprocessed/scaled; low-charge positions can be sentinel 100','Candidate association is not proof of causation','Neighboring station columns may be missing or inactive'])
            (out/f'{eid}.json').write_text(json.dumps(meta,indent=2)); manifest.append(dict(event_id=eid,sha256=hashlib.sha256((out/f'{eid}.npz').read_bytes()).hexdigest(),hdf5_group=meta['hdf5_group']))
            truth[eid]=dict(is_anom=bool(row.is_anom),anom_type=str(row.anom_type) if pd.notna(row.anom_type) else None)
    Path('data/evaluation_labels.json').write_text(json.dumps(truth,indent=2))
    Path('data/manifest.json').write_text(json.dumps(dict(source=BASE,retrieved='2026-09-29',selection='First two positive and first two negative AMPL labels; demo selection only',downloaded_hdf5_bytes=f.downloaded,events=manifest),indent=2))
    print('Downloaded HDF5 bytes',f.downloaded)
if __name__=='__main__': main()
