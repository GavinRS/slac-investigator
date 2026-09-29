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
        return SimpleNamespace(status='completed',output_text=text,usage=None)

class NodeTests(unittest.TestCase):
    def test_model_sees_only_summary_and_missing_usage_unknown(self):
        client=FixtureClient(); report=run_node(dict(kind='node_task',event_id='slac-001',instrument='rf',mode='collaborative'),client,'fixture')
        self.assertEqual(report['metrics']['model_calls'],1)
        self.assertIsNone(report['metrics']['input_tokens'])
        self.assertEqual(report['assessment'],'suspicious')
        self.assertNotIn('arrays',client.calls[0]['input'][0]['content'])
    def test_one_validation_retry(self):
        client=FixtureClient(bad_first=True)
        report=run_node(dict(kind='node_task',event_id='slac-001',instrument='ltu',mode='collaborative'),client,'fixture')
        self.assertEqual(report['metrics']['model_calls'],2)
        client=FixtureClient(always_bad=True)
        with self.assertRaises(ValueError): run_node(dict(kind='node_task',event_id='slac-001',instrument='ltu',mode='collaborative'),client,'fixture')
        self.assertEqual(len(client.calls),2)
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
        with self.assertRaisesRegex(ValueError,'after one retry'):
            run_node(dict(kind='node_task',event_id='slac-001',instrument='rf',mode='collaborative'),client,'fixture')
        self.assertEqual(len(client.calls),2)
        from slac_assistant.workflow import MAX_OUTPUT_TOKENS
        self.assertTrue(all(call['max_output_tokens']==MAX_OUTPUT_TOKENS for call in client.calls))
