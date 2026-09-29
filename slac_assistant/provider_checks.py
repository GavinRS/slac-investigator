"""Small live protocol probes, explicitly requested through Flower's AgentApp."""
import json,time
from .tools import analyze

def run_probe(client, model, probe, event_id, emit):
    if probe not in ('text','tool'): raise ValueError('Unknown provider probe')
    started=time.perf_counter(); calls=0; tokens_in=0;tokens_out=0;usage_known=True
    def call(history,tools=None,force=None):
        nonlocal calls,tokens_in,tokens_out,usage_known
        response=client.responses.create(model=model,input=history,
            instructions='Follow the protocol test instructions. Return only the requested final text or JSON, with no reasoning.',
            tools=tools or [],max_output_tokens=256,tool_choice=force)
        calls+=1
        if response.usage:
            tokens_in+=response.usage.input_tokens;tokens_out+=response.usage.output_tokens
        else:usage_known=False
        return response
    evidence=[]
    if probe=='text':
        response=call([{'role':'user','content':'Reply with exactly NEBIUS_TEXT_OK'}])
        if response.output_text.strip()!='NEBIUS_TEXT_OK':raise ValueError('Text probe did not return the requested text')
        checks=['Received expected text from Chat Completions']
    else:
        tool={'type':'function','name':'read_beam_quality','description':'Read deterministic beam recording quality for the selected SLAC event.',
              'parameters':{'type':'object','properties':{},'additionalProperties':False,'required':[]}}
        history=[{'role':'user','content':'Call read_beam_quality once. Then respond with ONLY JSON containing ref and bpm_samples, copied exactly from the result.'}]
        response=call(history,[tool],'read_beam_quality')
        calls_out=[x for x in response.output if x.type=='function_call']
        if len(calls_out)!=1 or calls_out[0].name!='read_beam_quality' or json.loads(calls_out[0].arguments)!={}:
            raise ValueError('Tool probe did not produce the expected single function call')
        history.extend(x.model_dump() for x in response.output)
        emit({'kind':'tool_request','agent':'provider probe','analysis':'quality'})
        result=analyze(event_id,'quality');evidence.append(result)
        emit({'kind':'tool_result','agent':'provider probe','evidence':result})
        expected={'ref':result['ref'],'bpm_samples':result['result']['bpm']['samples']}
        history.append({'type':'function_call_output','call_id':calls_out[0].call_id,'output':json.dumps(expected)})
        followup=call(history)
        if any(x.type=='function_call' for x in followup.output) or json.loads(followup.output_text)!=expected:
            raise ValueError('Tool probe follow-up did not reproduce the actual local result')
        checks=['Model produced a function call','Read-only SLAC tool executed locally','Follow-up model response matched the actual tool reference and sample count']
    return dict(event_id=event_id,mode='provider-probe',provider='nebius-chat',model=model,probe=probe,
        final={'assessment':'provider_probe_passed','observation':'; '.join(checks)},findings=[],evidence=evidence,
        metrics=dict(model_calls=calls,tool_calls=len(evidence),latency_s=round(time.perf_counter()-started,3),
                     input_tokens=tokens_in if usage_known else None,output_tokens=tokens_out if usage_known else None,cost_usd=None),
        checks=checks)
