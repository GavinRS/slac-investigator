"""Export reviewed historical runs for the static UI. No backend calls or labels."""
import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent/'data'
CASES={'slac-001':['4210859065409350628','16085169257987671247'],'slac-003':['1795740798858395915']}
def safe_numbers(obj):
    if isinstance(obj,dict): return {k:safe_numbers(v) for k,v in obj.items()}
    if isinstance(obj,list): return [safe_numbers(v) for v in obj]
    if isinstance(obj,int) and abs(obj)>2**53-1:return str(obj)
    if isinstance(obj,float) and not math.isfinite(obj):return None
    return obj
def build():
    OUT.mkdir(exist_ok=True)
    cases=[]
    for event_id,ids in CASES.items():
        meta=json.loads((ROOT/'data/events'/f'{event_id}.json').read_text())
        a=json.loads((ROOT/'data/events'/f'{event_id}.arrays.json').read_text())
        end=meta['candidate_end_ns'];channel=meta['station']+':AMPL';column=meta['channels']['health'].index(channel)
        rf=[[round((t-end)/1e9,9),row[column]] for t,row in zip(a['health_time_ns'],a['health']) if row[column] is not None]
        series=[]
        for j,name in enumerate(meta['channels']['bpm']):
            points=[]
            for t,row in zip(a['bpm_time_ns'],a['bpm']):
                y=row[j]
                if not name.endswith(':TMIT') and (row[j-1] is None or row[j-1]<1e8):y=None
                points.append([round((t-end)/1e9,9),y])
            series.append({'channel':name,'kind':'charge' if name.endswith(':TMIT') else 'position','points':points})
        runs=[]
        for i,rid in enumerate(ids):
            d=json.loads((ROOT/'artifacts/runs'/f'{rid}.json').read_text());r=d['report']
            # mode may be 'collaborative' (single-agent) or 'grid'.
            assert r['event_id']==event_id and r['mode'] in ('collaborative','grid')
            keep={k:r[k] for k in ('event_id','mode','model','model_execution_path','final','findings','evidence','metrics')}
            runs.append({'id':rid,'series_id':d.get('flower_series_id',r.get('flower_series_id')),
                'phase':'initial' if i==0 else 'followup','question':d.get('human_question',''),
                'wall_latency_s':d.get('wall_latency_s',r.get('wall_latency_s')),
                'review':d.get('evidence_review'), 'report':keep,
                'events':[e for e in d['events'] if e.get('kind') in ('started','delegation','tool_request','tool_result','finding','finding_rejected','node_report','data_shared')],
                'recorded_state':'completed','execution_source':'saved_run'})
        payload={'id':event_id,'station':meta['station'],'provenance':{k:meta[k] for k in ('source_url','hdf5_group','license','timing','timestamp_unit','limitations')},
            'time_origin_ns':str(end),'candidate_interval_s':[(meta['candidate_start_ns']-end)/1e9,0],
            'plots':{'rf':{'channel':channel,'points':rf},'beam':series},'runs':runs}
        (OUT/f'{event_id}.json').write_text(json.dumps(safe_numbers(payload),separators=(',',':'),allow_nan=False))
        cases.append({'id':event_id,'station':meta['station'],'file':f'./data/{event_id}.json','run_count':len(runs)})
    (OUT/'manifest.json').write_text(json.dumps({'schema':'frontend-replay-v1','execution_source':'saved_run','description':'Historical real Flower runs. Opening or replaying does not execute a model.','events':cases},indent=2))
    print('Exported',len(cases),'events and',sum(len(v) for v in CASES.values()),'real saved runs; no labels or credentials read.')
if __name__=='__main__':build()
