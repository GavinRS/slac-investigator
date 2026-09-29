"""Grid orchestrator (spec §4): Python drives get_nodes/push_messages/pull_messages; nodes reply with summaries only."""
import json
from .instruments import INSTRUMENTS,load_slice
from .tools import INSTRUMENT_KINDS,node_summary
from .workflow import Investigation
from .node import model_note

def grid_call(grid,name,args):
    return json.loads(grid.call({'type':'function_call','name':name,'arguments':args,'call_id':'grid-'+name})['output'])

def assign(node_ids):
    """3+ nodes: one instrument each. Fewer: round-robin, so a node takes several. None: in-process."""
    if not node_ids:return {i:'local' for i in INSTRUMENTS},'none (local fallback)'
    return {i:node_ids[k%len(node_ids)] for k,i in enumerate(INSTRUMENTS)},None if len(node_ids)>=3 else f'{len(node_ids)} node(s) for {len(INSTRUMENTS)} instruments; nodes take several instruments'

def shared(reports):
    raw=sum(r['raw_bytes_held'] for r,_ in reports.values());sent=sum(n for _,n in reports.values())
    return dict(raw_bytes_held=raw,payload_bytes=sent,percent_shared=round(100*sent/raw,3) if raw else None)

def collect(grid,event_id,assignment,mode,question,timeout,model=None,client=None):
    """Push every node_task first, then pull once so nodes work in parallel. Returns {instrument:(report,bytes_received)}, problems.
    A node holding a local slice answers for that instrument (role_source local_data), so assignment is updated from the replies."""
    reports,problems={},[]
    if all(n=='local' for n in assignment.values()):
        for i in INSTRUMENTS:
            r=node_summary(event_id,i,load_slice(event_id,i)[1])
            if model:r=model_note(model,r,client)
            reports[i]=(r,len(json.dumps(r).encode()))
        return reports,problems
    tasks=[(i,n,json.dumps(dict(kind='node_task',event_id=event_id,instrument=i,mode=mode,question=question,model=model))) for i,n in assignment.items()]
    results=grid_call(grid,'push_messages',{'messages':[dict(dst_node_id=n,payload=p,reply_to_message_id=None) for _,n,p in tasks]})['results']
    sent={}
    for (i,n,_),res in zip(tasks,results):
        if res['message_id']:sent[res['message_id']]=i
        else:problems.append(f'{i} task was not accepted by node {n}: {res["error"]}')
    if not sent:return reports,problems
    out=grid_call(grid,'pull_messages',{'message_ids':list(sent),'timeout':timeout})
    for m in out['messages']:
        try:r=json.loads(m['payload']) if m['payload'] and m['reply_to_message_id'] in sent else None
        except ValueError:r=None
        i=r.get('instrument') if isinstance(r,dict) else None
        if not(i in INSTRUMENTS and i not in reports and r.get('kind')=='node_report' and r.get('event_id')==event_id):
            problems.append(f'reply from node {m["src_node_id"]} unusable: {m["error"] or "not a new matching node_report"}');continue
        reports[i]=(r,len(m['payload'].encode()));assignment[i]=m['src_node_id']
    problems+=[f'{sent[x]} task: no reply within {timeout} s' for x in out['pending_message_ids']]
    return reports,problems

def smoke_final(inv,reports,problems):
    """Deterministic combine: align beam onsets across ltu/dump, cite node tool refs, never establish a unique cause."""
    rep={i:r for i,(r,_) in reports.items()};beam=[rep[i] for i in ('ltu','dump') if i in rep];rf=rep.get('rf')
    beam_refs=[x for r in beam for x in r['tool_refs']];all_refs=[x for r in rep.values() for x in r['tool_refs']]
    onsets={r['instrument']:r['summary']['onset_ns'] for r in beam if r['summary']['onset_ns'] is not None}
    if any(r['assessment']=='suspicious' for r in beam):status='corroborated'
    elif beam and all(r['assessment']=='normal' for r in beam):status='not_corroborated'
    else:status='insufficient_evidence'
    align=[f'{i} onset {t} ns' for i,t in sorted(onsets.items(),key=lambda x:x[1])]
    if len(onsets)==2:align.append(f"dump-ltu onset offset {(onsets['dump']-onsets['ltu'])/1e3:.1f} us")
    supporting=[f"{r['instrument']}: {r['assessment']}. {r['observation']}" for r in rep.values()]+align
    channels=([rf['summary']['station']] if rf else [])+[c for r in beam for c in r['summary']['channels']]
    f=dict(finding_id='F-001',agent='lead',observation=f'Instrument node summaries: beam disturbance {status.replace("_"," ")}; RF node {rf["assessment"] if rf else "missing"}.',
        source_channels=channels,time_interval_ns=[inv.meta['candidate_start_ns'],inv.meta['candidate_end_ns']],tool_result_refs=all_refs,
        supporting_evidence=supporting,conflicting_evidence=['Unique RF cause is not established.'],
        data_limitations=sorted({x for r in rep.values() for x in r['limitations']})+problems+['No model was called; deterministic combine of node summaries (smoke).' if inv.client is None else 'Deterministic combine of node summaries; the model final was not accepted.'],
        requested_next_check='Review timing, station completeness, and attribution with an operator.',
        beam_disturbance=dict(status=status,rationale='Deterministic beam heuristic from the ltu/dump node summaries only; independent of RF amplitude.',tool_result_refs=beam_refs or all_refs),
        unique_cause=dict(status='not_established',rationale='Summary-level replay checks cannot establish a unique causal RF station.',tool_result_refs=all_refs))
    return inv.validate(json.dumps(f),'lead',all_refs)

def model_final(inv,reports,problems,question,prior):
    """Model modes: one Finding v2 call over the node reports, reusing Investigation.loop's validate() and one correction turn."""
    rep={i:{k:v for k,v in r.items() if k not in ('raw_bytes_held','payload_bytes')} for i,(r,_) in reports.items()}
    task=('Reconcile the instrument node reports into one final finding. Node assessments are per-instrument signals, not verdicts. '
        'Align the ltu/dump beam onsets with the RF excursion; cite only the node tool refs. Node reports: '+json.dumps(rep)+
        ' Transport problems: '+json.dumps(problems)+' Human question: '+question+' Prior operator-visible assessment: '+json.dumps(prior))
    return inv.loop('lead',task,[inv.results[x] for r,_ in reports.values() for x in r['tool_refs']],1)

def run_grid(agent,event_id,emit,mode='smoke',question='',timeout=120,model=None,client=None,prior=None):
    """mode 'smoke': deterministic nodes and combine. Model modes need client+model: 1 model call per node, 1-2 for the final."""
    if mode!='smoke' and (client is None or not model):raise ValueError('Model grid modes need a model client and model')
    inv=Investigation(event_id,emit,client if mode!='smoke' else None,model if mode!='smoke' else 'none (deterministic harness)','grid')
    inv.publish('started',dict(event_id=event_id,mode='grid',model=inv.model))
    nodes=grid_call(agent.grid,'get_nodes',{'sample_size':None})['nodes']
    assignment,fallback=assign([n['id'] for n in nodes])
    for i,n in assignment.items():
        inv.publish('delegation',dict(agent='orchestrator',node_id=n,instrument=i,question=f'Run the {i} checks locally and reply with summary numbers only.'))
        for k in INSTRUMENT_KINDS[i]:inv.publish('tool_request',dict(agent=i,analysis=k))
    reports,problems=collect(agent.grid,event_id,assignment,mode,question,min(max(float(timeout),0),300),model if inv.client else None,inv.client)
    if not reports:raise RuntimeError('No node reports received: '+'; '.join(problems))
    for i,(r,_) in reports.items():
        inv.emit(dict(r,node_id=assignment[i]))
        for ref,k in zip(r['tool_refs'],INSTRUMENT_KINDS[i]):
            ev=dict(ref=ref,analysis=k,event_id=event_id,instrument=i,node_id=assignment[i]);inv.results[ref]=ev;inv.tool_calls+=1
            inv.publish('tool_result',dict(agent=i,evidence=ev))
    data=shared(reports);inv.publish('data_shared',data)
    final=None
    if inv.client is not None:
        try:final=model_final(inv,reports,problems,question,prior)
        except Exception as exc:problems=problems+[f'Model final not accepted ({type(exc).__name__}'+(f': {str(exc)[:200]}' if isinstance(exc,ValueError) else '')+').']
    if final is None:final=smoke_final(inv,reports,problems)
    return inv.finish(final,grid=dict(nodes_seen=len(nodes),assignment=assignment,fallback=fallback),data_shared=data,
        node_observation_source={i:r.get('observation_source','deterministic') for i,(r,_) in reports.items()})
