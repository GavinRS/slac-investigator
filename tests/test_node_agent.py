import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from slac_assistant.node_agent import run_node,ModelBudget

class FixtureClient:
    def __init__(self,bad_first=False,always_bad=False):
        self.responses=self; self.calls=[]; self.bad_first=bad_first; self.always_bad=always_bad
    def create(self,**kwargs):
        self.calls.append(kwargs); payload=json.loads(kwargs['input'][0]['content']); report=payload['report']
        text=json.dumps(dict(assessment='suspicious',observation='Aggregate evidence warrants review.',tool_refs=report['tool_refs']))
        if self.always_bad or (self.bad_first and len(self.calls)==1): text='{}'
        return SimpleNamespace(status='completed',output_text='',output=[SimpleNamespace(type='function_call',name='submit_assessment',arguments=text)],usage=None)

class NodeTests(unittest.TestCase):
    def test_model_sees_only_summary_and_missing_usage_unknown(self):
        client=FixtureClient(); report=run_node(dict(kind='node_task',event_id='slac-001',instrument='rf',mode='collaborative'),client,'fixture')
        self.assertEqual(report['metrics']['model_calls'],1)
        self.assertIsNone(report['metrics']['input_tokens'])
        self.assertEqual(report['assessment'],'suspicious')
        self.assertNotIn('arrays',client.calls[0]['input'][0]['content'])
    def test_invalid_response_stops_after_one_model_call(self):
        client=FixtureClient(bad_first=True)
        with self.assertRaisesRegex(ValueError,'one-call budget'):
            run_node(dict(kind='node_task',event_id='slac-001',instrument='ltu',mode='grid'),client,'fixture')
        self.assertEqual(len(client.calls),1)
    def test_local_mismatch_fails_closed(self):
        with patch('slac_assistant.node_agent.detect_local_instrument',return_value='rf'):
            with self.assertRaises(ValueError): run_node(dict(kind='node_task',event_id='slac-001',instrument='dump',mode='smoke'))
    def test_budget_blocks_before_model(self):
        client=FixtureClient()
        with self.assertRaises(RuntimeError): ModelBudget(max_calls=0).request(client,'fixture','instructions',{})
        self.assertEqual(client.calls,[])

    def test_incomplete_output_never_accepted(self):
        client=FixtureClient()
        original=client.create
        def incomplete(**kwargs):
            response=original(**kwargs)
            response.status='incomplete'
            return response
        client.create=incomplete
        with self.assertRaisesRegex(ValueError,'one-call budget'):
            run_node(dict(kind='node_task',event_id='slac-001',instrument='rf',mode='collaborative'),client,'fixture')
        self.assertEqual(len(client.calls),1)
        from slac_assistant.workflow import MAX_OUTPUT_TOKENS
        self.assertTrue(all(call['max_output_tokens']==MAX_OUTPUT_TOKENS for call in client.calls))


class JsonFramingTests(unittest.TestCase):
    def test_forced_function_arguments_are_used_with_one_call(self):
        client=FixtureClient()
        report=run_node(dict(kind='node_task',event_id='slac-001',instrument='rf',mode='grid'),client,'fixture')
        self.assertEqual(report['metrics']['model_calls'],1)
        self.assertEqual(client.calls[0]['tool_choice'],{'type':'function','name':'submit_assessment'})
        self.assertTrue(client.calls[0]['tools'][0]['strict'])

    def test_plain_text_is_not_a_function_output_fallback(self):
        client=FixtureClient(); original=client.create
        def plain(**kwargs):
            result=original(**kwargs)
            result.output_text=result.output[0].arguments
            result.output=[]
            return result
        client.create=plain
        with self.assertRaisesRegex(ValueError,'one-call budget'):
            run_node(dict(kind='node_task',event_id='slac-001',instrument='rf',mode='grid'),client,'fixture')
        self.assertEqual(len(client.calls),1)
    def test_prose_and_incomplete_fences_are_rejected(self):
        from slac_assistant.node_agent import normalize_json_response
        for text in ('Here is JSON: {"a":1}', '```json\n{"a":1}\n```\nMore prose', '```json\n{"a":1}', '```python\n{"a":1}\n```'):
            with self.subTest(text=text),self.assertRaises(ValueError):
                json.loads(normalize_json_response(text))
