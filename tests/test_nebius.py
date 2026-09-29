"""Offline HTTP contract tests. Fixture replies are NOT Nebius/live-model results."""
import json
from types import SimpleNamespace
import httpx
import pytest
from openai import OpenAI
from slac_assistant.nebius import (NebiusChatAdapter,chat_messages,create_model_client,
    require_nebius_environment,ProviderConfigurationError,ProviderRequestError,NEBIUS_BASE_URL)
from slac_assistant.provider_checks import run_probe
from slac_assistant.workflow import Investigation

MODEL='test/model-id'

def completion(text=None,calls=None,finish=None,**extra):
    return {'id':'test-completion','object':'chat.completion','created':0,'model':MODEL,
        'choices':[{'index':0,'finish_reason':finish or ('tool_calls' if calls else 'stop'),
                    'message':{'role':'assistant','content':text,'tool_calls':calls,**extra}}],
        'usage':{'prompt_tokens':20,'completion_tokens':10,'total_tokens':30}}

def sdk_with_handler(handler):
    requests=[]
    def transport(request):
        requests.append(request)
        if request.url.path=='/v1/models':return httpx.Response(200,json={'object':'list','data':[{'id':MODEL,'object':'model','created':0,'owned_by':'fixture'}]})
        assert request.url.path=='/v1/chat/completions'
        return handler(json.loads(request.content))
    sdk=OpenAI(api_key='unit-test-placeholder',base_url=NEBIUS_BASE_URL,max_retries=0,
               http_client=httpx.Client(transport=httpx.MockTransport(transport)))
    return sdk,requests


def test_credit_and_credentials_gate_precedes_network():
    with pytest.raises(ProviderConfigurationError,match='credit'):
        create_model_client('nebius-chat',env={})
    with pytest.raises(ProviderConfigurationError,match='NEBIUS_API_KEY, NEBIUS_MODEL'):
        create_model_client('nebius-chat',env={'NEBIUS_EVENT_CREDITS_CONFIRMED':'1'})
    with pytest.raises(ProviderConfigurationError,match='match NEBIUS_MODEL'):
        create_model_client('nebius-chat','wrong',env={'NEBIUS_EVENT_CREDITS_CONFIRMED':'1','NEBIUS_API_KEY':'test','NEBIUS_MODEL':MODEL})


def test_existing_flower_config_unchanged(monkeypatch):
    env={'FLWR_RUNTIME_BASE_URL':'http://127.0.0.1:9999/v1','FLWR_RUNTIME_API_KEY':'test-runtime',
         'FLWR_MODEL_API_ENDPOINT':'https://existing.example/v1/responses','FLWR_MODEL_API_KEY':'test-existing'}
    before=env.copy();seen={}
    monkeypatch.setattr('slac_assistant.nebius.OpenAI',lambda **kwargs:seen.update(kwargs) or 'sdk')
    client,model=create_model_client('flower',default_model='existing/model',env=env)
    assert env==before and model=='existing/model' and client=='sdk'
    assert seen['base_url']==env['FLWR_RUNTIME_BASE_URL'] and seen['api_key']==env['FLWR_RUNTIME_API_KEY']


def test_installed_flower_rejects_chat_endpoint_without_network(monkeypatch):
    from flwr.supercore.task_process.model.provider import invoke_model_provider
    monkeypatch.setenv('FLWR_MODEL_API_ENDPOINT',NEBIUS_BASE_URL+'chat/completions')
    monkeypatch.setenv('FLWR_MODEL_API_KEY','unit-test-placeholder')
    def no_post(*args,**kwargs):pytest.fail('Unexpected network call')
    monkeypatch.setattr('flwr.supercore.task_process.model.provider.requests.post',no_post)
    with pytest.raises(RuntimeError,match='/responses path'):
        invoke_model_provider({'model':MODEL,'input':'hello'},usage_recorder=None)


def test_text_probe_and_usage_mapping():
    def handler(body):
        assert body['max_tokens']==256 and body['stream'] is False
        assert 'max_output_tokens' not in body and 'input' not in body
        assert body['messages'][0]['role']=='system'
        return httpx.Response(200,json=completion('NEBIUS_TEXT_OK',reasoning_content='PRIVATE_FIXTURE_REASONING'))
    sdk,requests=sdk_with_handler(handler);adapter=NebiusChatAdapter(sdk,MODEL)
    report=run_probe(adapter,MODEL,'text','slac-001',lambda e:None)
    assert report['metrics']['input_tokens']==20 and report['metrics']['output_tokens']==10
    assert 'PRIVATE_FIXTURE_REASONING' not in json.dumps(report)
    assert [r.url.path for r in requests]==['/v1/models','/v1/chat/completions']


def test_tool_probe_local_execution_and_followup():
    def handler(body):
        if 'tools' in body:
            assert body['tools'][0]['function']['name']=='read_beam_quality'
            assert body['tool_choice']['function']['name']=='read_beam_quality'
            return httpx.Response(200,json=completion(calls=[{'id':'call-1','type':'function','function':{'name':'read_beam_quality','arguments':'{}'}}]))
        messages=body['messages'];assert messages[-2]['tool_calls'][0]['id']=='call-1'
        assert messages[-1]['role']=='tool' and messages[-1]['tool_call_id']=='call-1'
        result=json.loads(messages[-1]['content']);assert result['bpm_samples']==2075
        return httpx.Response(200,json=completion(json.dumps(result)))
    sdk,requests=sdk_with_handler(handler);events=[]
    report=run_probe(NebiusChatAdapter(sdk,MODEL),MODEL,'tool','slac-001',events.append)
    assert report['metrics']['model_calls']==2 and report['metrics']['tool_calls']==1
    assert len(requests)==3 and len(events)==2


def test_multiple_tool_calls_grouped_and_matched():
    history=[{'role':'user','content':'inspect'},
        {'type':'message','role':'assistant','content':[{'type':'output_text','text':'Checking.'}]},
        {'type':'function_call','call_id':'one','name':'a','arguments':'{}'},
        {'type':'function_call','call_id':'two','name':'b','arguments':'{}'},
        {'type':'function_call_output','call_id':'one','output':'1'},
        {'type':'function_call_output','call_id':'two','output':'2'}]
    messages=chat_messages(history,'policy')
    assert len(messages)==5 and len(messages[2]['tool_calls'])==2
    assert messages[2]['content']=='Checking.'
    with pytest.raises(ValueError,match='Missing tool results'):chat_messages(history[:-1],'policy')
    with pytest.raises(ValueError,match='Unmatched'):chat_messages([history[-1]],'policy')
    with pytest.raises(ValueError,match='Unsupported'):chat_messages([{'type':'reasoning','summary':[]}],'policy')


@pytest.mark.parametrize('finish',['length','content_filter'])
def test_incomplete_responses_rejected(finish):
    sdk,_=sdk_with_handler(lambda body:httpx.Response(200,json=completion('partial',finish=finish)))
    with pytest.raises(ProviderRequestError,match='incomplete'):
        NebiusChatAdapter(sdk,MODEL).create(model=MODEL,input='test',instructions='',tools=[],max_output_tokens=10)


def test_errors_do_not_echo_provider_body():
    sdk,requests=sdk_with_handler(lambda body:httpx.Response(401,json={'error':{'message':'sensitive-placeholder-do-not-echo','type':'authentication_error'}}))
    with pytest.raises(ProviderRequestError) as error:
        NebiusChatAdapter(sdk,MODEL).create(model=MODEL,input='test',instructions='',tools=[],max_output_tokens=10)
    assert 'sensitive-placeholder' not in str(error.value) and '401' in str(error.value)
    assert len(requests)==2  # No retry.


def test_unavailable_model_does_not_infer():
    sdk,requests=sdk_with_handler(lambda body:pytest.fail('Unexpected inference'))
    with pytest.raises(ProviderConfigurationError,match='model list'):
        NebiusChatAdapter(sdk,'missing/model').create(model='missing/model',input='test',instructions='',tools=[],max_output_tokens=10)
    assert len(requests)==1


def test_unadvertised_tool_rejected():
    sdk,_=sdk_with_handler(lambda body:httpx.Response(200,json=completion(calls=[{'id':'x','type':'function','function':{'name':'write_equipment','arguments':'{}'}}])))
    with pytest.raises(ProviderRequestError,match='unadvertised'):
        NebiusChatAdapter(sdk,MODEL).create(model=MODEL,input='test',instructions='',tools=[],max_output_tokens=10)


def test_full_investigation_protocol_fixture_with_followup():
    seen_roles=[]
    def handler(body):
        role=body['messages'][0]['content'].split('Your role is ')[-1].split('.')[0];seen_roles.append(role)
        payload=json.loads(body['messages'][1]['content'].split('\nShared tool evidence:')[0])
        if role=='beam' and len(seen_roles)==2:assert payload['shared_findings']==[]
        if role=='lead' and body['messages'][-1]['role']!='tool':
            return httpx.Response(200,json=completion(calls=[{'id':'delegate-1','type':'function','function':{'name':'delegate','arguments':json.dumps({'agent':'beam','kind':'charge_validity','question':'Inspect low-charge validity.'})}}]))
        refs=[r['ref'] for r in payload['initial_evidence']] or [r for f in payload['shared_findings'] for r in f['tool_result_refs']]
        m=payload['event'];finding=dict(finding_id='fixture',agent=role,observation='OFFLINE protocol fixture; not a model investigation.',source_channels=[m['station']+':AMPL'],time_interval_ns=[m['candidate_start_ns'],m['candidate_end_ns']],tool_result_refs=refs,supporting_evidence=['Fixture'],conflicting_evidence=[],data_limitations=['No live model'],requested_next_check='charge_validity' if role!='lead' else None,beam_disturbance=dict(status='insufficient_evidence',rationale='Fixture',tool_result_refs=refs),unique_cause=dict(status='not_established',rationale='Fixture',tool_result_refs=refs))
        return httpx.Response(200,json=completion(json.dumps(finding)))
    sdk,requests=sdk_with_handler(handler);events=[]
    report=Investigation('slac-001',events.append,client=NebiusChatAdapter(sdk,MODEL),model=MODEL).run()
    assert seen_roles==['equipment','beam','lead','beam','lead']
    assert report['provider']=='nebius-chat' and report['metrics']['model_calls']==5
    assert report['metrics']['input_tokens']==100
    assert any(e['kind']=='delegation' and e['analysis']=='charge_validity' for e in events)
    assert len([r for r in requests if r.url.path=='/v1/models'])==1
