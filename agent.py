"""Experience-grounded explorer with optional local language comprehension."""
import copy
import json
import math
import os
from pathlib import Path
import random
import re
from collections import Counter

import genome
import personality

STOP = set('the and for that this with from are was have has not you your can will more our its into about'.split())


def tokens(text):
    return [w for w in re.findall(r'[^\W\d_]{3,30}', text.lower(), re.UNICODE) if w not in STOP]


class Agent:
    def __init__(self, seed=7):
        self.rng = random.Random(seed)
        traits = genome.express(genome.founder(4096, seed))
        proxy = {'affect': {}, 'appraisal': {}, 'learned_values': {}}
        personality.initialize(proxy, traits)
        self.data = {'version': 1, 'identity': {'exists': True, 'name': None,
            'origin': None, 'biography': []}, 'traits': traits,
            'dispositions': proxy['personality']['dispositions'], 'tick': 0,
            'frontier': [], 'seen': [], 'memories': [], 'vocabulary': {},
            'interests': {}, 'domain_values': {}, 'events': [],
            'last_decision': None, 'last_page': None, 'errors': 0}
        self.upgrade()

    def upgrade(self):
        d = self.data
        d.setdefault('cognition', {'mode': 'word_learning_only', 'model': None,
            'pretrained_knowledge': False, 'completed': 0, 'error': None})
        for name, default in [('journal', []), ('beliefs', []), ('questions', []),
                              ('semantic_interests', {}), ('link_intentions', {}), ('reflected_steps', [])]:
            d.setdefault(name, copy.deepcopy(default))
        d.setdefault('mental_state', {'curiosity': .5, 'satisfaction': 0., 'uncertainty': 1.,
                                     'fatigue': 0., 'status': 'engineered_motivational_proxies'})
        d.setdefault('self_description', {'text': f"I have recorded {d['tick']} page experiences; no semantic reflections yet.",
            'basis': 'recorded_behavior_only', 'observed_interests': [], 'revisions': 0})

    def cognitive_context(self):
        return ([{'step': j['step'], 'summary': j['summary'], 'url': j['url']} for j in self.data['journal'][-3:]],
                sorted(self.data['semantic_interests'].items(), key=lambda x: -x[1]['strength'])[:8])

    def integrate(self, result, page, step):
        """Only validated results enter memory; a model cannot patch identity/state."""
        from urllib.parse import urlsplit
        d = self.data
        if step in d['reflected_steps']:
            return False
        # Validate again at this boundary, including for injected/custom providers.
        from cognition import validate
        candidates = page['links'][:35]
        raw = {k: result[k] for k in ('summary', 'claims', 'interests', 'questions', 'reflection', 'uncertainty')}
        raw['next_links'] = []
        checked = validate(raw, page, candidates)
        allowed = {x['url'] for x in candidates}
        next_links = [x for x in result.get('next_links', []) if x.get('url') in allowed
                      and isinstance(x.get('reason'), str) and len(x['reason']) <= 200]
        if not checked['claims']:
            raise ValueError('No source-grounded claims survived validation')
        d['reflected_steps'] = (d['reflected_steps']+[step])[-2000:]
        evidence_ids = []
        for i, claim in enumerate(checked['claims']):
            evidence_id = f'{step}:{i}'
            evidence_ids.append(evidence_id)
            matches = [b for b in d['beliefs'] if b['statement'].casefold() == claim['statement'].casefold()]
            evidence = {'id': evidence_id, 'step': step, 'url': page['url'], 'quote': claim['quote']}
            if matches:
                b = matches[0]
                if page['url'] not in [s['url'] for s in b['sources']]:
                    b['sources'] = (b['sources']+[evidence])[-5:]
                b['independent_domains'] = len({urlsplit(s['url']).hostname for s in b['sources']})
            else:
                d['beliefs'].append({'statement': claim['statement'], 'sources': [evidence],
                    'independent_domains': 1, 'status': 'source_claim_not_verified_fact'})
        d['beliefs'] = d['beliefs'][-300:]
        alpha = .1+.3*d['traits']['plasticity']
        for interest in d['semantic_interests'].values():
            interest['strength'] *= .98
        for item in checked['interests']:
            topic = item['topic']
            previous = d['semantic_interests'].get(topic, {'strength': .2, 'encounters': 0})
            d['semantic_interests'][topic] = {'strength': (1-alpha)*previous['strength']+alpha*item['strength'],
                'encounters': previous['encounters']+1, 'reason': item['reason'],
                'quote': item['quote'], 'url': page['url'], 'last_step': step}
        d['semantic_interests'] = dict(sorted(d['semantic_interests'].items(), key=lambda x: -x[1]['strength'])[:80])
        for question in checked['questions']:
            if not any(q['text'] == question for q in d['questions']):
                d['questions'].append({'text': question, 'step': step, 'source': page['url'], 'status': 'open'})
        d['questions'] = d['questions'][-30:]
        for i, link in enumerate(next_links):
            d['link_intentions'][link['url']] = {'reason': link['reason'], 'source': page['url'],
                                                 'step': step, 'weight': 1/(1+i)}
        d['link_intentions'] = dict(list(d['link_intentions'].items())[-150:])
        d['journal'].append({'step': step, 'url': page['url'], 'summary': checked['summary'],
            'reflection': checked['reflection'], 'uncertainty': checked['uncertainty'],
            'evidence_ids': evidence_ids, 'evidence': checked['claims'],
            'model': result.get('model'), 'status': 'generated_public_reflection_not_subjective_thought'})
        d['journal'] = d['journal'][-80:]
        d['cognition'].update({'completed': d['cognition']['completed']+1, 'error': None})
        m = d['mental_state']
        m['satisfaction'] = min(1., len(checked['claims'])/4)
        m['uncertainty'] = .7 if checked['uncertainty'] else .4
        m['curiosity'] = min(1., .3+.15*len(checked['questions'])+.2*d['traits']['curiosity'])
        m['fatigue'] = min(1., m['fatigue']+.03)
        interests = sorted(d['semantic_interests'], key=lambda k: -d['semantic_interests'][k]['strength'])[:4]
        old = d['self_description']
        d['self_description'] = {'text': f"I have recorded {d['tick']} page experiences and reflected on {d['cognition']['completed']}. "
            + ('My current reading interests include '+', '.join(interests)+'. ' if interests else '')
            + 'These preferences are provisional. I have no recorded human biography or established account of my origin.',
            'basis': 'recorded_behavior_only', 'observed_interests': interests, 'revisions': old['revisions']+1,
            'evidence_steps': [j['step'] for j in d['journal'][-8:]]}
        self.event('reflected', url=page['url'], claims=len(checked['claims']), topics=interests)
        return True

    def event(self, kind, **fields):
        self.data['events'].append({'step': self.data['tick'], 'kind': kind, **fields})
        self.data['events'] = self.data['events'][-200:]

    def seed(self, url):
        # A sensory starting location, not personal history or a life goal.
        if url not in self.data['seen'] and not any(x['url'] == url for x in self.data['frontier']):
            self.data['frontier'].append({'url': url, 'label': '', 'via': None})
            self.data['frontier'] = self.data['frontier'][-500:]

    def choose(self):
        from urllib.parse import urlsplit
        t, p, d = self.data['traits'], self.data['dispositions'], self.data
        if not d['frontier']:
            return None
        rows = []
        for item in d['frontier']:
            words = tokens(item['label'])
            novelty = sum(w not in d['vocabulary'] for w in words) / max(1, len(words))
            interest = sum(d['interests'].get(w, 0) for w in words) / max(1, len(words))
            domain = urlsplit(item['url']).hostname
            expected = d['domain_values'].get(domain, {'mean': 0})['mean']
            intention = d['link_intentions'].get(item['url'])
            semantic = sum(v['strength']*len(set(tokens(topic)) & set(words))/max(1, len(tokens(topic)))
                           for topic, v in d['semantic_interests'].items())
            reflective_bonus = (1.2*intention['weight'] if intention else 0)+.4*semantic
            motivation = .5+.5*d['mental_state']['curiosity']
            score = ((.3+t['curiosity']*motivation+t['novelty_preference'])*novelty
                     + (.2+t['persistence'])*interest + (.2+t['planning'])*expected
                     + .2*p['cognitive_flexibility'] / (1+sum(urlsplit(u).hostname == domain for u in d['seen'][-20:]))
                     + reflective_bonus + self.rng.random()*(.05+.2*(1-p['deliberation'])))
            rows.append((score, item, novelty, interest, expected))
        score, selected, novelty, interest, expected = max(rows, key=lambda x: x[0])
        d['last_decision'] = {'url': selected['url'], 'score': round(score, 5),
            'novelty': novelty, 'learned_interest': interest, 'learned_domain_value': expected,
            'source': selected['via'], 'reflection_intention': d['link_intentions'].get(selected['url']),
            'mechanism': 'traits, novelty, semantic interests and grounded reflection; not an inner monologue'}
        d['frontier'].remove(selected)
        return selected

    def experience(self, page, decision):
        from urllib.parse import urlsplit
        d, t = self.data, self.data['traits']
        d['tick'] += 1
        words = Counter(tokens(page['text']))
        new = [w for w in words if w not in d['vocabulary']]
        reward = len(new) / max(1, len(words))
        alpha = .05+.35*t['plasticity']
        for w, count in words.most_common(200):
            d['vocabulary'][w] = d['vocabulary'].get(w, 0)+count
            d['interests'][w] = (1-alpha)*d['interests'].get(w, 0)+alpha*reward
        if len(d['vocabulary']) > 10000:
            d['vocabulary'] = dict(Counter(d['vocabulary']).most_common(10000))
        if len(d['interests']) > 10000:
            d['interests'] = dict(sorted(d['interests'].items(), key=lambda x: -x[1])[:10000])
        domain = urlsplit(page['url']).hostname
        model = d['domain_values'].setdefault(domain, {'n': 0, 'mean': 0})
        model['n'] += 1
        model['mean'] += (reward-model['mean'])/model['n']
        if len(d['domain_values']) > 500:
            del d['domain_values'][next(iter(d['domain_values']))]
        d['seen'] = (d['seen']+[decision['url'], page['url']])[-2000:]
        memory = {'step': d['tick'], 'url': page['url'], 'title': page['title'],
            'excerpt': page['text'][:6000], 'new_words': len(new), 'reward': reward,
            'status': 'source_observation_not_verified_fact'}
        d['memories'].append(memory)
        d['memories'] = d['memories'][-int(40+160*t['memory_retention']):]
        d['last_page'] = {**page, 'text': page['text'][:16000]}
        for link in page['links']:
            if link['url'] not in d['seen'] and not any(x['url'] == link['url'] for x in d['frontier']):
                d['frontier'].append({**link, 'via': page['url']})
        d['frontier'] = d['frontier'][:500]
        self.event('read', url=page['url'], title=page['title'], new_words=len(new), reward=round(reward, 4))

    def fail(self, item, error):
        self.data['errors'] += 1
        self.data['seen'] = (self.data['seen']+[item['url']])[-2000:]
        self.event('blocked_or_failed', url=item['url'], detail=str(error)[:200])

    def recall(self, question):
        """Retrieve observed passages; never turn web assertions into autobiography."""
        query = set(tokens(question))
        ranked = sorted(((len(query & set(tokens(m['excerpt']))), m) for m in self.data['memories']), key=lambda x: -x[0])
        return [{'url': m['url'], 'title': m['title'], 'excerpt': m['excerpt'][:1000],
                 'status': m['status']} for score, m in ranked[:5] if score]

    def snapshot(self):
        return copy.deepcopy(self.data)

    def save(self, path):
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix('.tmp')
        temp.write_text(json.dumps({'data': self.data, 'rng': self.rng.getstate()}, allow_nan=False), encoding='utf8')
        os.replace(temp, target)

    @classmethod
    def load(cls, path):
        raw = json.loads(Path(path).read_text(encoding='utf8'))
        if raw['data']['version'] != 1:
            raise ValueError('Unsupported save version')
        agent = cls.__new__(cls)
        agent.data = raw['data']
        agent.upgrade()
        agent.rng = random.Random()
        def tup(x):
            return tuple(tup(v) for v in x) if isinstance(x, list) else x
        agent.rng.setstate(tup(raw['rng']))
        return agent
