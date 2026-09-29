"""Small adapter for Flower 1.39.0's Control API (version-pinned internal client)."""
import hashlib,io,json,time,zipfile
from pathlib import Path
from flwr.cli.build import build_fab_from_disk
from flwr.cli.chat.chat_app import start_chat_run,parse_task_event
from flwr.proto.control_pb2 import StreamRunEventsRequest,ListRunsRequest
from flwr.supercore.control.control_http_client import ControlHttpClient
from .data import ROOT

def build_bundle():
    fab=build_fab_from_disk(ROOT)
    with zipfile.ZipFile(io.BytesIO(fab)) as z:
        names=z.namelist()
        if any('labels' in n or n.startswith(('artifacts/','data/raw/','scripts/','nodes/')) or Path(n).name.startswith('.env') for n in names):raise ValueError('Evaluation material or private configuration leaked into bundle')
        if 'data/events/slac-001.arrays.json' not in names:raise ValueError('Event data missing from bundle')
    return fab

def run_flower(event_id,mode='grid',question='',model=None,series_id=None,on_event=None,address='http://127.0.0.1:8000',on_started=None,node_timeout=None):
    if node_timeout is not None and (not isinstance(node_timeout,(int,float)) or not 0<=node_timeout<=300):raise ValueError('Node timeout must be between 0 and 300 seconds')
    fab=build_bundle();client=ControlHttpClient(address,timeout=330)
    request=dict(event_id=event_id,mode=mode,question=question)
    if model:request['model']=model
    if node_timeout is not None:request['node_timeout']=node_timeout
    started=time.perf_counter(); events=[];report=None;buffer=''
    try:
        run_id,series_id=start_chat_run(client,json.dumps(request),None,series_id,fab_hash=hashlib.sha256(fab).hexdigest(),fab_content=fab)
        if on_started:on_started(str(run_id),str(series_id))
        for response in client.StreamRunEvents(StreamRunEventsRequest(run_id=run_id)):
            kind,payload=parse_task_event(response.task_event)
            if kind in ('error','response.failed','run.failed'):raise RuntimeError('Flower run failed: '+json.dumps(payload))
            if kind=='response.output_text.delta':
                buffer+=payload.get('delta','')
                while '\n' in buffer:
                    line,buffer=buffer.split('\n',1)
                    if not line.strip():continue
                    event=json.loads(line);events.append(event)
                    if event['kind']=='report':report=event['report']
                    if on_event:on_event(event)
        if report is None:raise RuntimeError(f'Flower run {run_id} ended without a completed report; inspect SuperLink logs.')
        status=client.ListRuns(ListRunsRequest(run_id=run_id))
        run=status.run_dict.get(run_id)
        if run is None or run.status.status!='finished' or run.status.sub_status!='completed':
            raise RuntimeError(f'Flower run {run_id} did not reach finished/completed.')
        report.update(flower_run_id=str(run_id),flower_series_id=str(series_id),runtime='Flower 1.39.0 local SuperLink',runtime_status='finished/completed',wall_latency_s=round(time.perf_counter()-started,3))
        folder=ROOT/'artifacts/runs';folder.mkdir(parents=True,exist_ok=True)
        (folder/f'{run_id}.json').write_text(json.dumps(dict(report=report,events=events),indent=2))
        return report,series_id
    finally:client.close()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--event',default='slac-001');p.add_argument('--mode',choices=['smoke','grid','collaborative','baseline'],default='grid');p.add_argument('--question',default='');p.add_argument('--model')
    p.add_argument('--address',default='http://127.0.0.1:8000');p.add_argument('--node-timeout',type=float);args=p.parse_args()
    report,_=run_flower(args.event,args.mode,args.question,args.model,on_event=lambda e:print(json.dumps(e),flush=True),address=args.address,node_timeout=args.node_timeout)
    print('Flower run',report['flower_run_id'],'beam disturbance',report['final']['beam_disturbance']['status'],'unique cause',report['final']['unique_cause']['status'])
