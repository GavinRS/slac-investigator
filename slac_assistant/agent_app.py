"""Flower 1.39.0 is the actual application executor, not an imported decoration."""
import json,os
from flwr.agentapp import AgentApp,AgentSession
from flwr.app import Context,ConfigRecord
from .workflow import Investigation
from .grid_workflow import GridInvestigation
from .node_agent import reply_to_node
from .nebius import create_model_client
from .provider_checks import run_probe
app=AgentApp()
@app.main()
def main(agent:AgentSession,context:Context)->None:
    request=json.loads(agent.prompt)
    node_request='src_node_id' in request
    if node_request:
        request=json.loads(request['payload'])
        if request.get('discover'):
            reply_to_node(agent,request)
            return
    mode=request.get('mode','collaborative')
    if mode not in ('collaborative','baseline','smoke'):raise ValueError('Unknown mode')
    def emit(payload):
        # Only concise application events. No private model/reasoning events are forwarded.
        agent.events.emit({'type':'response.output_text.delta','delta':json.dumps(payload)+'\n'})
    client=None
    provider=request.get('provider','flower')
    model=request.get('model') or context.run_config.get('model')
    if mode!='smoke':
        if not model: raise ValueError('A model identifier must be configured')
        client,model=create_model_client(provider,request.get('model'),model)
    if node_request:
        reply_to_node(agent,request,client,model)
        return
    if request.get('probe'):
        if provider!='nebius-chat' or client is None:raise ValueError('Provider probes require explicit nebius-chat selection')
        report=run_probe(client,model,request['probe'],request['event_id'],emit)
        emit({'kind':'report','report':report})
        agent.events.emit({'type':'response.completed'})
        return
    inv=(Investigation(request['event_id'],emit,client,model,mode) if mode=='baseline' else
         GridInvestigation(request['event_id'],emit,agent.grid,client,model,mode,context.run_config.get('node-timeout',120)))
    prior=None
    if 'investigation' in context.state:
        state=context.state['investigation']
        if state.get('event_id')==request['event_id']:prior=json.loads(state['final'])
    report=inv.run(request.get('question',''),prior)
    context.state['investigation']=ConfigRecord({'event_id':request['event_id'],'final':json.dumps(report['final'])})
    agent.events.emit({'type':'response.completed'})
