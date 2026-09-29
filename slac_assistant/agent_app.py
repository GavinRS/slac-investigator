"""Flower 1.39.0 is the actual application executor, not an imported decoration."""
import json,os
from flwr.agentapp import AgentApp,AgentSession
from flwr.app import Context,ConfigRecord
from .workflow import Investigation
from .grid_workflow import GridInvestigation
from .node_agent import reply_to_node
from openai import OpenAI
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
    mode=request.get('mode','grid')
    if mode not in ('grid','collaborative','baseline','smoke'):raise ValueError('Unknown mode')
    def emit(payload):
        # Only concise application events. No private model/reasoning events are forwarded.
        agent.events.emit({'type':'response.output_text.delta','delta':json.dumps(payload)+'\n'})
    client=None
    model=request.get('model') or os.environ.get('INVESTIGATOR_MODEL') or context.run_config.get('model') or 'flwrlabs/endeavor-1.0'
    if mode!='smoke':
        client=OpenAI(base_url=os.environ['FLWR_RUNTIME_BASE_URL'],api_key=os.environ['FLWR_RUNTIME_API_KEY'],max_retries=0,timeout=300)
    if node_request:
        reply_to_node(agent,request,client,model)
        return
    inv=(Investigation(request['event_id'],emit,client,model,mode) if mode=='baseline' else
         GridInvestigation(request['event_id'],emit,agent.grid,client,model,mode,request.get('node_timeout',context.run_config.get('node-timeout',120))))
    prior=None
    if 'investigation' in context.state:
        state=context.state['investigation']
        if state.get('event_id')==request['event_id']:prior=json.loads(state['final'])
    report=inv.run(request.get('question',''),prior)
    context.state['investigation']=ConfigRecord({'event_id':request['event_id'],'final':json.dumps(report['final'])})
    agent.events.emit({'type':'response.completed'})
