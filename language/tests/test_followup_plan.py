import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from language.workflow import contracts, followup_protocol as protocol, prompts
from language.workflow.client import Client
from language.workflow.state import write


class FollowupPlanTests(unittest.TestCase):
    def test_resume_old_plan_and_recover_ten_citations(self):
        ids = [f'sample-{i}' for i in range(10)]
        schema = protocol.plan_schema(['C1'], ids)
        old_schema = protocol.plan_schema(['C1'], ids, evidence_limit=8)
        question = dict(question='Which explanation fits?', criticism_ids=['C1'], action='review',
                        hypothesis='A', rival='B', prediction_if_hypothesis='positive',
                        prediction_if_rival='negative', distinguishing_observation='sign', why_new='context')
        short = {**question, 'evidence_ids': ids[:1]}
        original = dict(decision='continue', reason='test', investigations=[short])
        second = {**original, 'investigations': [short, short, {**question, 'evidence_ids': ids}]}
        prompt = prompts.FOLLOWUP_PLAN
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = Client({}, root / 'api', root / 'slots')
            with patch.object(client, '_stream', return_value=json.dumps(original)):
                client.request('round-1/plan', prompt, {'round': 1}, old_schema, 1)

            attempt = client.root / 'round-2/plan/attempt-002'
            write(attempt / 'request.json', {'messages': [
                {'role': 'system', 'content': prompt + prompts.SCHEMA_HEADER + json.dumps(old_schema)},
                {'role': 'user', 'content': json.dumps({'round': 2})}]})
            write(attempt / 'completion.json', {'finish_reason': 'stop'})
            (attempt / 'output.txt').write_text(json.dumps(second))

            with patch.object(client, '_stream', side_effect=AssertionError('Unexpected API call')):
                for number, expected in ((1, original), (2, second)):
                    actual = client.request(f'round-{number}/plan', prompt, {'round': number}, schema, 1,
                                            check=lambda p: protocol.check_plan(p, ids), previous_schema=lambda: old_schema)
                    self.assertEqual(actual, expected)
                with self.assertRaisesRegex(ValueError, 'Inputs changed'):
                    client.request('round-1/plan', prompt, {'round': 2}, schema, 1, previous_schema=lambda: old_schema)

        with self.assertRaisesRegex(ValueError, 'unexpected value'):
            contracts.validate({**original, 'investigations': [{**question, 'evidence_ids': ids + ['unknown']}]}, schema)
        with self.assertRaisesRegex(ValueError, 'unexpected item count 6'):
            contracts.validate({**original, 'investigations': [short] * 6}, schema)
