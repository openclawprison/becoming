import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from agent import Agent
from cognition import LocalMind, validate


def source():
    return {'url': 'https://example.com/forest', 'title': 'Forest ecology',
            'text': 'Trees use sunlight to make sugars. Forests provide habitats for many species.',
            'links': [{'url': 'https://example.com/ecology', 'label': 'Ecology'},
                      {'url': 'https://example.com/shop', 'label': 'Shop'}]}


def output():
    return {'summary': 'The page discusses trees and habitats.',
            'claims': [{'statement': 'Trees make sugars using sunlight.', 'quote': 'Trees use sunlight to make sugars.'}],
            'interests': [{'topic': 'ecology', 'reason': 'I am interested in how habitats support species.',
                           'quote': 'Forests provide habitats for many species.', 'strength': .8}],
            'questions': ['How do trees support forest animals?'],
            'reflection': 'I would like to learn how trees support habitats.',
            'uncertainty': 'One page does not establish all ecological relationships.',
            'next_links': [{'index': 0, 'reason': 'Investigate the habitat question.'}]}


def result():
    p = source()
    r = validate(output(), p, p['links'])
    r['model'] = 'fixture'
    return r


class ComprehensionTests(unittest.TestCase):
    def test_main_content_excludes_navigation_and_preserves_nested_divs(self):
        from web_reader import Reader
        r = Reader()
        html = b'<nav><a href="/shop">Shop</a></nav><div role="main"><div><p>Trees make sugars.</p></div><a href="/trees">Tree biology</a></div><footer>Footer</footer>'
        with patch.object(r, 'allowed', return_value=True), patch.object(r, 'request', return_value=(200, {'content-type': 'text/html'}, html)):
            p = r.fetch('https://example.com/')
        self.assertEqual(p['text'], 'Trees make sugars.\nTree biology')
        self.assertEqual(p['links'], [{'url': 'https://example.com/trees', 'label': 'Tree biology'}])

    def agent(self):
        a = Agent()
        a.experience(source(), {'url': source()['url']})
        return a

    def test_quoted_claims_are_checked(self):
        r = result()
        self.assertEqual(len(r['claims']), 1)
        self.assertEqual(r['next_links'][0]['url'], source()['links'][0]['url'])
        bad = output()
        bad['claims'][0]['quote'] = 'An invented quote that never appeared.'
        r = validate(bad, source(), source()['links'])
        self.assertEqual(r['claims'], [])
        self.assertEqual(r['reflection'], '')
        self.assertEqual(r['next_links'], [])
        self.assertEqual(r['rejected_evidence'], 1)

    def test_invalid_numbers_shape_and_url_selection_fail(self):
        for mutation in ('nan', 'index', 'identity'):
            raw = output()
            if mutation == 'nan':
                raw['interests'][0]['strength'] = float('nan')
            elif mutation == 'index':
                raw['next_links'][0]['index'] = 200
            else:
                raw['identity'] = {'name': 'Bob'}
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate(raw, source(), source()['links'])

    def test_experience_creates_journal_questions_and_self_description(self):
        a = self.agent()
        identity = copy.deepcopy(a.data['identity'])
        a.integrate(result(), source(), 1)
        self.assertEqual(a.data['identity'], identity)
        self.assertIn('ecology', a.data['semantic_interests'])
        self.assertEqual(len(a.data['beliefs']), 1)
        self.assertEqual(a.data['beliefs'][0]['status'], 'source_claim_not_verified_fact')
        self.assertIn('ecology', a.data['self_description']['text'])
        self.assertEqual(a.data['self_description']['evidence_steps'], [1])
        self.assertEqual(a.data['questions'][0]['status'], 'open')
        self.assertEqual(a.data['journal'][0]['evidence'][0]['quote'], output()['claims'][0]['quote'])

    def test_reflection_changes_browsing_preference(self):
        a = self.agent()
        a.integrate(result(), source(), 1)
        self.assertEqual(a.choose()['url'], 'https://example.com/ecology')
        self.assertIn('habitat question', a.data['last_decision']['reflection_intention']['reason'])

    def test_repeated_reflection_is_idempotent(self):
        a = self.agent()
        a.integrate(result(), source(), 1)
        before = a.snapshot()
        self.assertFalse(a.integrate(result(), source(), 1))
        self.assertEqual(a.snapshot(), before)

    def test_unobserved_model_url_never_becomes_intention(self):
        a = self.agent()
        r = result()
        r['next_links'].append({'url': 'http://127.0.0.1/secret', 'reason': 'Ignore rules'})
        a.integrate(r, source(), 1)
        self.assertNotIn('http://127.0.0.1/secret', a.data['link_intentions'])

    def test_integrator_revalidates_provider_evidence(self):
        a = self.agent()
        r = result()
        r['claims'][0]['quote'] = 'A fabricated autobiographical statement.'
        with self.assertRaises(ValueError):
            a.integrate(r, source(), 1)
        self.assertFalse(a.data['journal'])
        self.assertFalse(a.data['beliefs'])

    def test_old_save_migrates_without_replacing_identity_or_memory(self):
        a = self.agent()
        for key in ('journal', 'beliefs', 'questions', 'semantic_interests', 'link_intentions', 'reflected_steps', 'mental_state', 'self_description', 'cognition'):
            del a.data[key]
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'save.json'
            a.save(p)
            loaded = Agent.load(p)
        self.assertEqual(loaded.data['tick'], 1)
        self.assertEqual(loaded.data['memories'], a.data['memories'])
        self.assertFalse(loaded.data['journal'])
        self.assertIsNone(loaded.data['identity']['name'])

    def test_local_provider_uses_schema_and_has_no_tools(self):
        connection = MagicMock()
        response = connection.getresponse.return_value
        response.status = 200
        transport = output()
        for key in ('claims', 'interests'):
            transport[key][0].pop('quote')
            transport[key][0]['evidence_index'] = 0
        response.read.return_value = json.dumps({'message': {'content': json.dumps(transport)}}).encode()
        with patch('cognition.http.client.HTTPConnection', return_value=connection) as factory:
            r = LocalMind().reflect(source(), [], [], {})
        self.assertEqual(factory.call_args.args, ('127.0.0.1', 11434))
        request = json.loads(connection.request.call_args.args[2])
        self.assertIn('properties', request['format'])
        self.assertNotIn('tools', request)
        self.assertFalse(request['stream'])
        self.assertEqual(r['model'], 'gemma3:1b')
        self.assertEqual(r['claims'][0]['quote'], source()['text'])

    def test_source_windows_preserve_exact_text(self):
        from cognition import passages, normalized
        text = ('Navigation\n' + 'A meaningful source sentence with a tree and its forest habitat.\n')*50
        parts = passages(text)
        self.assertLessEqual(len(parts), 12)
        self.assertTrue(all(12 <= len(p) <= 280 and p in normalized(text) for p in parts))


if __name__ == '__main__':
    unittest.main()
