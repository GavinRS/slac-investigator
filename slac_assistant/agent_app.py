"""Flower 1.39.0 is the actual application executor, not an imported decoration."""
import json,os,re
from flwr.agentapp import AgentApp,AgentSession
from flwr.app import Context,ConfigRecord
from .workflow import Investigation,DEFAULT_MODEL
from .node import node_task,run_node,runtime_client
from .grid_workflow import run_grid
app=AgentApp()
@app.main()
def main(agent:AgentSession,context:Context)->None:
    node=node_task(agent.prompt)
    if node:
        run_node(agent,*node);agent.events.emit({'type':'response.completed'});return
    try:request=json.loads(agent.prompt)
    except ValueError:request=None
    if not isinstance(request,dict):
        # Plain English from `flwr chat`: collaborative Grid run on the event named in the text.
        text=str(agent.prompt);m=re.search(r'slac-00[1-4]',text,re.I)
        request=dict(event_id=m.group(0).lower() if m else 'slac-001',mode='collaborative',question=text)
        chat=True
    else:chat=False
    mode=request.get('mode','collaborative')
    if mode not in ('collaborative','baseline','smoke','grid'):raise ValueError('Unknown mode')
    nodes=[]
    def say(text):agent.events.emit({'type':'response.output_text.delta','delta':text})
    def emit(payload):
        # Only concise application events. No private model/reasoning events are forwarded.
        if payload.get('kind')=='node_report':nodes.append(payload)
        say(json.dumps(payload)+'\n')
    if chat:say('── Agent messages (machine) ──\n')
    prior=None
    if 'investigation' in context.state:
        state=context.state['investigation']
        if state.get('event_id')==request['event_id']:prior=json.loads(state['final'])
    if mode in ('grid','collaborative'):
        # grid = deterministic smoke on the Grid; collaborative = models on nodes and orchestrator (spec §3-4).
        model=request.get('model') or os.environ.get('INVESTIGATOR_MODEL') or context.run_config.get('model',DEFAULT_MODEL)
        report=run_grid(agent,request['event_id'],emit,mode='smoke' if mode=='grid' else mode,question=request.get('question',''),
            timeout=context.run_config.get('grid-timeout',120),model=model,client=None if mode=='grid' else runtime_client(),prior=prior)
        context.state['investigation']=ConfigRecord({'event_id':request['event_id'],'final':json.dumps(report['final'])})
        if chat:say(answer(request['event_id'],report,nodes))
        agent.events.emit({'type':'response.completed'});return
    client=None
    if mode!='smoke':
        from openai import OpenAI
        client=OpenAI(base_url=os.environ['FLWR_RUNTIME_BASE_URL'],api_key=os.environ['FLWR_RUNTIME_API_KEY'],max_retries=0,timeout=120)
    model=request.get('model') or os.environ.get('INVESTIGATOR_MODEL') or context.run_config.get('model',DEFAULT_MODEL)
    inv=Investigation(request['event_id'],emit,client,model,mode)
    if mode=='baseline':inv.max_output_tokens=4000  # same per-call output budget as the Grid final (#14)
    report=inv.smoke(request.get('question','')) if mode=='smoke' else inv.run(request.get('question',''),prior)
    context.state['investigation']=ConfigRecord({'event_id':request['event_id'],'final':json.dumps(report['final'])})
    agent.events.emit({'type':'response.completed'})

def answer(event_id,report,nodes):
    """Plain-English summary for a human in `flwr chat`."""
    f=report.get('final',{});share=(report.get('data_shared') or {}).get('percent_shared')
    part=lambda k:f"{k.replace('_',' ').capitalize()}: {str((f.get(k) or {}).get('status','unknown')).replace('_',' ').upper()}. {(f.get(k) or {}).get('rationale','')}"
    lines=['','── Answer ──',f'Event {event_id}.',part('beam_disturbance'),part('unique_cause'),'What each instrument said:']
    lines+=[f"  {n.get('instrument','?').upper()}: {str(n.get('assessment','?')).replace('_',' ')}. {n.get('observation','')}" for n in nodes]
    if share is not None:lines.append(f'Raw data shared: {share}% (the orchestrator saw summaries from each instrument, not its raw samples).')
    return '\n'.join(lines)+'\n'
