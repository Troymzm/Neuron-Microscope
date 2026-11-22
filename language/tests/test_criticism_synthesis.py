import unittest
from copy import deepcopy

from language.workflow.contracts import validate
from language.workflow.report_synthesis import synthesize, synthesize_criticism


class CriticismSynthesisTests(unittest.TestCase):
    def test_synthesis_uses_only_linked_questions_and_measured_evidence(self):
        rows = [
            {'attack': 'Is this token sufficient?', 'verdict': 'narrowed',
             'evidence': [{'text': 'Prefix target suffix', 'activation': 3.0, 'peak_index': 1,
                           'tokens': ['Prefix', ' target', ' suffix']}]},
            {'attack': 'Does it generalize?', 'verdict': 'inconclusive'},
            {'attack': 'Untouched question', 'verdict': 'survived'},
            {'investigation_id': 'r1-i1', 'criticism_ids': ['C1', 'C2', 'C1'], 'round': 1,
             'attack': 'Measure matched controls', 'verdict': 'rejected', 'result': 'Original target was low.',
             'evidence': [{'id': 'trial', 'activation': -2.0, 'text': 'Matched control'}]},
            {'investigation_id': 'r2-i1', 'criticism_ids': ['C2'], 'round': 2,
             'attack': 'Retest on natural cases', 'verdict': 'inconclusive',
             'result': 'Investigation failed: private runtime details'},
        ]
        bundle = {'criticism': rows, 'claim': {'title': 'Frozen explanation'}}
        original = deepcopy(bundle)

        class Client:
            def request(self, name, prompt, packet, stage_schema, stage, check):
                self.args = name, prompt, packet, stage, stage_schema, check
                return {'C1': {'verdict': 'narrowed', 'conclusion': 'The token is context dependent.',
                               'evidence_ids': ['criticism:original-1:1', 'criticism:r1-i1:trial']},
                        'C2': {'verdict': 'inconclusive', 'conclusion': 'The generalization remains open.',
                               'evidence_ids': ['criticism:r2-i1']}}

        client = Client()
        output = synthesize_criticism(client, bundle, 6)
        name, prompt, packet, stage, schema, check = client.args
        validate(output, schema)
        check(output)
        self.assertEqual(name, 'report-synthesis/criticism-judgments')
        self.assertEqual(stage, 6)
        self.assertIn('not to the competing hypothesis', prompt)
        self.assertEqual(bundle, original)
        self.assertEqual(list(packet['questions']), ['C1', 'C2'])
        self.assertEqual([x['id'] for x in packet['questions']['C1']['followups']], ['r1-i1'])
        self.assertEqual([x['id'] for x in packet['questions']['C2']['followups']], ['r1-i1', 'r2-i1'])
        evidence = packet['questions']['C1']['original']['evidence']['criticism:original-1:1']
        self.assertEqual(evidence['observed_prefix_excerpt'], 'Prefix target')
        self.assertEqual(evidence['following_text'], ' suffix')
        self.assertEqual(evidence['details']['activation'], 3.0)
        self.assertNotIn('private runtime details', str(packet))

        with self.assertRaises(ValueError):
            validate({'C1': output['C1']}, schema)
        wrong = deepcopy(output)
        wrong['C1']['evidence_ids'] = ['criticism:r2-i1']
        with self.assertRaises(ValueError):
            validate(wrong, schema)
        wrong['C1']['evidence_ids'] = ['criticism:r1-i1:trial'] * 2
        with self.assertRaises(ValueError):
            check(wrong)
        wrong['C1'] = {**output['C1'], 'conclusion': ' '}
        with self.assertRaises(ValueError):
            check(wrong)

    def test_no_investigated_questions_needs_no_request(self):
        self.assertEqual(synthesize_criticism(None, {'criticism': [{'attack': 'Untouched'}]}, 4), {})
        self.assertEqual(synthesize_criticism(None, {'criticism': [
            {'attack': 'Untouched'}, {'investigation_id': 'r1-i1', 'criticism_ids': ['C2']}]}, 6), {})

    def test_claim_uses_final_criticism_and_its_cited_measurements(self):
        bundle = {'criticism': [
            {'attack': 'Exact phrase only', 'result': 'Initial account', 'evidence': [
                {'id': 'first', 'text': 'An initial example', 'activation': 10}]},
            {'investigation_id': 'r1-i1', 'criticism_ids': ['C1'], 'attack': 'Test a shorter prefix', 'evidence': [
                {'id': 'measured', 'text': 'The shorter prefix', 'activation': 12}]},
        ]}
        evidence = 'criticism:r1-i1:measured'
        conclusion = 'The matched prefix was sufficient in this frame.'
        findings = {'C1': {'verdict': 'narrowed', 'conclusion': conclusion, 'evidence_ids': [evidence]}}

        class Client:
            calls = {}

            def request_text(self, name, prompt, packet, stage):
                self.calls[name] = packet
                return 'Fixture synthesis'

        client = Client()
        result = synthesize(client, bundle, 6, criticism_findings=findings)
        self.assertNotIn('report-synthesis/sections/criticism', client.calls)
        self.assertEqual(result['section_prose']['criticism'], {'summary': conclusion})
        self.assertEqual(list(result['evidence']), [evidence])
        for kind in result['claim']['findings']:
            packet = client.calls[f'report-synthesis/final-claim/findings/{kind}']
            self.assertEqual(packet['section_summaries']['criticism'], conclusion)
            self.assertEqual(list(packet['cases']), [evidence])
