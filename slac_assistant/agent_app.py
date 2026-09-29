"""Flower 1.39.0 is the actual application executor, not an imported decoration."""
import json,os
from flwr.agentapp import AgentApp,AgentSession
from flwr.app import Context,ConfigRecord
from .workflow import Investigation
app=AgentApp()
@app.main()
def main(agent:AgentSession,context:Context)->None:
    request=json.loads(agent.prompt)
    mode=request.get('mode','collaborative')
    if mode not in ('collaborative','baseline','smoke'):raise ValueError('Unknown mode')
    def emit(payload):
        # Only concise application events. No private model/reasoning events are forwarded.
        agent.events.emit({'type':'response.output_text.delta','delta':json.dumps(payload)+'\n'})
    client=None
    if mode!='smoke':
        from openai import OpenAI
        client=OpenAI(base_url=os.environ['FLWR_RUNTIME_BASE_URL'],api_key=os.environ['FLWR_RUNTIME_API_KEY'],max_retries=0,timeout=120)
    model=request.get('model') or context.run_config.get('model','openai/gpt-5.6-sol')
    inv=Investigation(request['event_id'],emit,client,model,mode)
    prior=None
    if 'investigation' in context.state:
        state=context.state['investigation']
        if state.get('event_id')==request['event_id']:prior=json.loads(state['final'])
    report=inv.smoke(request.get('question','')) if mode=='smoke' else inv.run(request.get('question',''),prior)
    context.state['investigation']=ConfigRecord({'event_id':request['event_id'],'final':json.dumps(report['final'])})
    agent.events.emit({'type':'response.completed'})
