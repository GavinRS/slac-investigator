"""Export reviewed historical runs for the static UI. No backend calls or labels."""
import argparse, json, math, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent/'data'
CASES={'slac-001':['4210859065409350628','16085169257987671247'],'slac-003':['1795740798858395915']}
SENSITIVE_FIELDS = {'apikey', 'authorization', 'accesstoken', 'refreshtoken', 'password', 'secret', 'credentials', 'credential', 'apisecret', 'privatekey'}
PRIVATE_VALUE = re.compile(r'(?:/Users/|/home/|/private/|/tmp/|[A-Za-z]:[\\/]Users[\\/]|\bsk-(?:proj-)?[A-Za-z0-9_-]{8,}|\bBearer\s+\S+)', re.IGNORECASE)


def screen_export(value):
    """Reject private data recursively; never include its contents in errors."""
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r'[^a-z0-9]', '', key.lower())
            if any(normalized == field or normalized.endswith(field) for field in SENSITIVE_FIELDS):
                raise ValueError('Export refused: sensitive configuration field in replay payload')
            screen_export(item)
    elif isinstance(value, list):
        for item in value: screen_export(item)
    elif isinstance(value, str) and PRIVATE_VALUE.search(value):
        raise ValueError('Export refused: credential-like value or private filesystem path in replay payload')
    return value


def safe_numbers(obj):
    if isinstance(obj,dict): return {k:safe_numbers(v) for k,v in obj.items()}
    if isinstance(obj,list): return [safe_numbers(v) for v in obj]
    if isinstance(obj,int) and abs(obj)>2**53-1:return str(obj)
    if isinstance(obj,float) and not math.isfinite(obj):return None
    return obj
def selected_cases(run_ids, run_dir):
    cases = {}
    for rid in run_ids:
        if not re.fullmatch(r'[0-9]+', rid):
            raise ValueError('Run IDs must contain decimal digits only')
        saved = json.loads((run_dir / f'{rid}.json').read_text())
        report = saved['report']
        status = report.get('runtime_status', '')
        completed = status == 'finished/completed' or (re.search(r'status:\s*"finished"', status) and re.search(r'sub_status:\s*"completed"', status))
        if (report.get('mode') != 'grid' or report.get('execution_mode') != 'model'
                or report.get('flower_run_id') != rid
                or not completed
                or report.get('data_shared', {}).get('complete') is not True
                or report.get('metrics', {}).get('accounting_complete') is not True):
            raise ValueError('Only complete model Grid runs with complete accounting can be explicitly exported')
        event_id = report['event_id']
        if not re.fullmatch(r'slac-[0-9]{3}', event_id):
            raise ValueError('Invalid saved event ID')
        if rid not in cases.setdefault(event_id, []):
            cases[event_id].append(rid)
    return cases


def build(run_ids=None, output_dir=None, run_dir=None):
    run_dir = Path(run_dir) if run_dir else ROOT/'artifacts/runs'
    out = Path(output_dir) if output_dir else OUT
    selection = selected_cases(run_ids, run_dir) if run_ids else CASES
    out.mkdir(parents=True, exist_ok=True)
    cases=[]
    pending=[]
    for event_id,ids in selection.items():
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
            d=json.loads((run_dir/f'{rid}.json').read_text());r=d['report']
            if r['event_id'] != event_id:raise ValueError('Saved event mismatch')
            if not run_ids and not (r['mode']=='collaborative' and r['provider']=='flower'):raise ValueError('Unexpected historical run')
            keep={k:r[k] for k in ('event_id','mode','model','provider','model_execution_path','final','findings','evidence','metrics','result_schema_version','execution_mode','grid','node_reports','data_shared') if k in r}
            runs.append({'id':rid,'series_id':d.get('flower_series_id',r.get('flower_series_id')),
                'phase':'followup' if i>0 and d.get('human_question') and runs[-1]['series_id']==r.get('flower_series_id') else 'initial','question':d.get('human_question',''),
                'wall_latency_s':d.get('wall_latency_s',r.get('wall_latency_s')),
                'review':d.get('evidence_review'), 'report':keep,
                'events':[e for e in d['events'] if e.get('kind') in ('started','delegation','tool_request','tool_result','finding','finding_rejected','node_report','data_shared')],
                'recorded_state':'completed','execution_source':'saved_run'})
        payload={'id':event_id,'station':meta['station'],'provenance':{k:meta[k] for k in ('source_url','hdf5_group','license','timing','timestamp_unit','limitations')},
            'time_origin_ns':str(end),'candidate_interval_s':[(meta['candidate_start_ns']-end)/1e9,0],
            'plots':{'rf':{'channel':channel,'points':rf},'beam':series},'runs':runs}
        pending.append((out/f'{event_id}.json', json.dumps(screen_export(safe_numbers(payload)),separators=(',',':'),allow_nan=False)))
        cases.append({'id':event_id,'station':meta['station'],'file':f'./{event_id}.json' if run_ids else f'./data/{event_id}.json','run_count':len(runs)})
    for path, body in pending:path.write_text(body)
    (out/'manifest.json').write_text(json.dumps({'schema':'frontend-replay-v1','execution_source':'saved_run','description':'Completed recorded model Grid runs. Opening or replaying does not execute a model.' if run_ids else 'Historical real Flower runs. Opening or replaying does not execute a model.','events':cases},indent=2))
    print('Exported',len(cases),'events and',sum(len(v) for v in selection.values()),'real saved runs; no labels or credentials read.')
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', action='append', help='Completed model Grid run ID; repeat for several runs.')
    parser.add_argument('--output-dir', type=Path, help='Separate replay output directory; required with --run-id.')
    parser.add_argument('--run-dir', type=Path, default=ROOT/'artifacts/runs')
    args=parser.parse_args()
    if args.run_id and (not args.output_dir or args.output_dir.resolve()==OUT.resolve()):
        parser.error('--run-id requires a separate --output-dir to preserve historical replay data')
    build(args.run_id, args.output_dir, args.run_dir)
