"""Gives each new entry a sector, sub-sector and one-line description.

Main route: an AI model (Anthropic API), told the exact taxonomy and shown real examples from the existing dashboard.
Its answer is CHECKED before it is trusted: the sector and sub-sector must exist, the description must be short and free of
fundraising words, and a country is only accepted if the model is confident. Anything that fails is retried once, then falls back
to rough keyword rules, and rows labelled by the fallback are always held for a human look.
"""
import json
import os
import re

import requests

from .geo import COUNTRIES, canon_country
from .http import USER_AGENT

API_URL = 'https://api.anthropic.com/v1/messages'
DEFAULT_MODEL = 'claude-haiku-5-5'
BAD_BLURB = re.compile(r'[€$£\d]|\b(raised|raises|secured|funding|investment|round|series|seed|valuation)\b', re.I)
MIN_BLURB_WORDS, MAX_BLURB_WORDS = 2, 14


def load_taxonomy(path):
    return json.loads(open(path, encoding='utf-8').read())


def pick_examples(rows, per_cat=2):
    """A few real labelled rows per sector, so the model matches the dashboard's existing style."""
    seen, out = {}, []
    for r in rows:
        c, b = r.get('category'), (r.get('blurb') or '').strip()
        if not c or not b or 'unavailable' in b.lower() or seen.get(c, 0) >= per_cat:
            continue
        seen[c] = seen.get(c, 0) + 1
        out.append(f"- {r['name']} | {b} -> {c}/{r.get('sub')}")
    return out


def build_system_prompt(tax, examples):
    cats = []
    for c, d in tax['categories'].items():
        cats.append(f"- {c}: {d['definition']}")
        cats += [f"    - {s}: {desc}" for s, desc in d['subs'].items()]
    return '\n'.join([
        'You label European startup funding announcements for a public dashboard. Reply with JSON only.',
        '', 'PRINCIPLE: ' + tax['principle'], '', 'CATEGORIES AND SUB-CATEGORIES (use these exact names):', *cats,
        '', 'BOUNDARY RULES:', *[f'- {r}' for r in tax['rules']],
        '', 'DESCRIPTION ("blurb"): 3 to 12 words, a noun phrase saying what the company does or sells and to whom. No company name, no amounts, no fundraising or growth words '
            '(raised, funding, round, expand, scale), no full stop. Say "AI" only if AI is the product itself.',
        '', 'COUNTRY: fill it in ONLY if the entry text itself says where the company is based (for example "London-based", "a Berlin startup", a named home city). '
            'Do NOT use your own memory of the company, and do not treat expansion targets ("expand in the UK", "enter the US") as the home country. '
            'Copy the exact words from the text that show it into country_evidence. If the text does not say, use null for both. Use one of: ' + ', '.join(COUNTRIES) + '.',
        '', 'EXAMPLES OF EXISTING LABELS (company | description -> category/sub):', *examples,
        '', 'INPUT is a JSON list of {"i", "company", "text", "link"}. OUTPUT is a JSON list, one object per input, in the same order:',
        '{"i": 0, "category": "...", "sub": "...", "blurb": "...", "country": "..." or null, "country_evidence": "exact words from the text" or null, "country_confidence": 0.0-1.0, "confidence": 0.0-1.0}',
        'Use confidence below 0.7 whenever the text is too thin to be sure.'])


class AnthropicLabeller:
    def __init__(self, api_key, model=None):
        self.api_key, self.model = api_key, model or os.environ.get('LABEL_MODEL') or DEFAULT_MODEL

    def label(self, system, items):
        body = {'model': self.model, 'max_tokens': 4000, 'system': system, 'messages': [{'role': 'user', 'content': json.dumps(items, ensure_ascii=False)}]}
        r = requests.post(API_URL, json=body, timeout=90, headers={'x-api-key': self.api_key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json', 'User-Agent': USER_AGENT})
        if r.status_code >= 400:
            raise RuntimeError(f'labelling API error {r.status_code}: {r.text[:200]}')
        text = ''.join(b.get('text', '') for b in r.json().get('content', []) if b.get('type') == 'text')
        return parse_json_list(text)


def parse_json_list(text):
    a, b = text.find('['), text.rfind(']')
    if a < 0 or b < a:
        raise ValueError('no JSON list in model reply')
    return json.loads(text[a:b + 1])


def validate(lab, tax):
    problems = []
    cat, sub = lab.get('category'), lab.get('sub')
    if cat not in tax['categories']:
        problems.append(f'unknown category {cat!r}')
    elif sub not in tax['categories'][cat]['subs']:
        problems.append(f'sub-category {sub!r} is not in {cat}')
    blurb = (lab.get('blurb') or '').strip()
    n = len(blurb.split())
    if not (MIN_BLURB_WORDS <= n <= MAX_BLURB_WORDS):
        problems.append(f'description has {n} words')
    if BAD_BLURB.search(blurb):
        problems.append('description contains amounts or fundraising words')
    c = lab.get('confidence')
    if not isinstance(c, (int, float)) or not 0 <= c <= 1:
        problems.append('missing confidence')
    if lab.get('country') and not canon_country(lab['country']):
        problems.append(f"unknown country {lab['country']!r}")
    return problems


# ---- rough fallback (poor on purpose: every row it labels is held for review) ----
_RULES = [
    ('Cyber', r'security|cyber|threat|vulnerab|pentest|identity|fraud|deepfake'),
    ('Defence & Space', r'satellite|rocket|\bspace\b|orbit|missile|military|defen[cs]e|drone|counter-uas'),
    ('Climate', r'energy|battery|solar|carbon|climate|hydrogen|nuclear|fusion|wind|recycl|plastic|protein|fermentation|\bfood|agri|crop|farm|waste|sustainab|grid|electric|noise|vibration'),
    ('Health', r'health|patient|clinic|drug|medic|therap|biotech|diagnos|pharma|disease|surgical|cancer|heart|genom'),
    ('Fintech', r'payment|\bbank|lending|credit|insur|invest|wealth|accounting|\btax\b|financ|treasury|invoice|payroll|trading|crypto'),
    ('AI Infra', r'foundation model|\bllm|gpu|compute|inference|data cent|developer|devops|database|vector|observab|open-source'),
    ('Consumer', r'\bgame|gaming|music|creator|video|fitness|consumer|fashion|shopping|travel'),
    ('Industry', r'construction|industrial|manufactur|hotel|hospitality|restaurant|retail|logistics|supply chain|real estate|property|warehouse'),
    ('Deep Tech', r'quantum|semiconductor|photonic|\bchip|robot|lidar|laser|sensor'),
]
_DEFAULT_SUB = {'Enterprise': 'Productivity', 'Industry': 'Industrial', 'Fintech': 'Payments', 'Health': 'Digital', 'Climate': 'Energy', 'Deep Tech': 'Hardware', 'AI Infra': 'Dev Tools',
                'Defence & Space': 'Defence', 'Consumer': 'Apps', 'Cyber': 'Threat'}


def rules_label(text):
    t = text.lower()
    cat = next((c for c, p in _RULES if re.search(p, t)), 'Enterprise')
    m = re.search(r'\bto\s+(?:expand|build|develop|scale|launch|grow|accelerate|bring|take|advance|create|power)?\s*(?:its\s+|the\s+|a\s+)?(.+?)(?:\.|$)', text)
    words = (m.group(1) if m else text).split()[:10]
    blurb = ' '.join(words).strip(' ,;') or 'Description unavailable'
    blurb = blurb[0].upper() + blurb[1:]
    return {'category': cat, 'sub': _DEFAULT_SUB[cat], 'blurb': blurb, 'country': None, 'country_confidence': 0.0, 'confidence': 0.2}


def label_all(entries, labeller, tax, examples, batch_size=12):
    """entries: list of {id, company, text, link}. Returns {id: label dict with 'source' and 'problems'}."""
    system = build_system_prompt(tax, examples)
    results = {}

    def run(batch, note=None):
        items = [{'i': k, 'company': e['company'], 'text': e['text'], 'link': e.get('link', '')} for k, e in enumerate(batch)]
        if note:
            for it in items:
                it['fix'] = note.get(it['i'], '')
        return {r.get('i'): r for r in labeller.label(system, items) if isinstance(r, dict)}

    for s in range(0, len(entries), batch_size):
        batch = entries[s:s + batch_size]
        got, failed = {}, None
        if labeller is not None:
            try:
                got = run(batch)
            except Exception as e:  # network, bad key, unparsable reply
                failed = str(e)
        bad = {}
        for k, e in enumerate(batch):
            lab = got.get(k)
            probs = validate(lab, tax) if lab else ['no answer from model']
            if probs:
                bad[k] = probs
            else:
                results[e['id']] = {**lab, 'source': 'llm', 'problems': []}
        if bad and labeller is not None and failed is None:     # one retry, telling the model what was wrong
            try:
                again = run(batch, {k: 'Fix: ' + '; '.join(p) for k, p in bad.items()})
                for k in list(bad):
                    lab = again.get(k)
                    if lab and not validate(lab, tax):
                        results[batch[k]['id']] = {**lab, 'source': 'llm', 'problems': []}
                        del bad[k]
            except Exception as e:
                failed = str(e)
        for k, probs in bad.items():
            e = batch[k]
            results[e['id']] = {**rules_label(e['text']), 'source': 'rules', 'problems': probs + ([failed] if failed else [])}
    return results
