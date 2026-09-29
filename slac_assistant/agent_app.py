"""Flower 1.39.0 is the actual application executor, not an imported decoration."""
import json,os
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
    request=json.loads(agent.prompt)
    mode=request.get('mode','collaborative')
    if mode not in ('collaborative','baseline','smoke','grid'):raise ValueError('Unknown mode')
    def emit(payload):
        # Only concise application events. No private model/reasoning events are forwarded.
        agent.events.emit({'type':'response.output_text.delta','delta':json.dumps(payload)+'\n'})
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
        agent.events.emit({'type':'response.completed'});return
    client=None
    if mode!='smoke':
        from openai import OpenAI
        client=OpenAI(base_url=os.environ['FLWR_RUNTIME_BASE_URL'],api_key=os.environ['FLWR_RUNTIME_API_KEY'],max_retries=0,timeout=120)
    model=request.get('model') or os.environ.get('INVESTIGATOR_MODEL') or context.run_config.get('model',DEFAULT_MODEL)
    inv=Investigation(request['event_id'],emit,client,model,mode)
    report=inv.smoke(request.get('question','')) if mode=='smoke' else inv.run(request.get('question',''),prior)
    context.state['investigation']=ConfigRecord({'event_id':request['event_id'],'final':json.dumps(report['final'])})
    agent.events.emit({'type':'response.completed'})
