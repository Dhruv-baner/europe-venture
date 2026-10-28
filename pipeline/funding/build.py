"""Turns collected entries into dashboard rows and decides what is safe to publish. No file or network work happens here
except through the FX object and the labeller that are passed in, so it is easy to test."""
from . import dedupe
import re

from .geo import country_from_text, country_from_url
from .parse import parse_amount, parse_investors, parse_round

BLOCKING = {'label_fallback', 'label_low_confidence', 'possible_duplicate', 'amount_unparsed', 'fx_failed', 'unconfirmed'}
# informational flags are published as they are and listed in the review file: country_unknown, country_from_model, name_collision,
# amount_vague, amount_missing, fx_provisional, fx_fallback, round_guessed
LEGACY_SECTOR = {'AI Infra': 'AI and Software', 'Enterprise': 'AI and Software', 'Fintech': 'Fintech', 'Health': 'Healthtech', 'Climate': 'Climate Tech', 'Deep Tech': 'Deep Tech',
                 'Defence & Space': 'Defence', 'Cyber': 'Cybersecurity'}
UNKNOWN = 'Europe (unspecified)'
UNCONFIRMED = re.compile(r'\b(reportedly|rumou?red|is said to|in talks|according to (?:reports|sources)|sources say|set to raise|plans? to raise|is raising|looking to raise)\b', re.I)
EXPANSION_WORDS = re.compile(r'\b(expand|expansion|enter|entering|launch|launching|into|market)\b', re.I)
MIN_CONFIDENCE = 0.6
COUNTRY_MODEL_CONFIDENCE = 0.85


def _prev_month(m):
    y, mo = int(m[:4]), int(m[5:7])
    return f'{y - 1}-12' if mo == 1 else f'{y}-{mo - 1:02d}'


def month_for(e):
    """The month of the round. The newsletter reports yesterday's news, so on the 1st or 2nd of a month the article link
    (".../2026/10/30/...") shows the news was really from the month before. The link's month is used only if it is this issue's month or the one before."""
    issue_month = e['issue_date'][:7]
    m = re.search(r'/(20\d\d)/(0[1-9]|1[0-2])/', e.get('source_url', '') or '')
    if m:
        link_month = f'{m.group(1)}-{m.group(2)}'
        if link_month in (issue_month, _prev_month(issue_month)):
            return link_month
    return issue_month


def legacy_sector(cat, sub):
    if cat == 'Industry':
        return 'Real Estate' if sub == 'Property' else 'AI and Software'
    if cat == 'Consumer':
        return 'Education' if sub == 'Education' else 'Consumer'
    return LEGACY_SECTOR.get(cat, 'AI and Software')


def entry_for_labelling(e):
    return {'id': e['id'], 'company': e['company'], 'text': e['text'], 'link': e.get('source_url', '')}


def prelim_duplicates(entries, existing, fx):
    """Entries that are clearly already in the dashboard (name, month, amount) do not need paid labelling."""
    skip = set()
    for e in entries:
        month = month_for(e)
        a = parse_amount(e['text'])
        try:
            gbp = fx.to_gbp(a['value'], a['currency'], month)[0]
        except Exception:
            gbp = None
        verdict, _ = dedupe.classify({'name': e['company'], 'month': month, 'amount': gbp}, existing)
        if verdict == 'duplicate':
            skip.add(e['id'])
    return skip


def make_row(e, labels, existing, fx):
    text, month = e['text'], month_for(e)
    flags = []
    a = parse_amount(text)
    gbp = rate = None
    prov = fb = False
    if a['unparsed']:
        flags.append('amount_unparsed')
    elif a['value'] is None:
        flags.append('amount_vague' if a['vague'] else 'amount_missing')
    else:
        try:
            gbp, rate, prov, fb = fx.to_gbp(a['value'], a['currency'], month)
        except Exception:
            flags.append('fx_failed')
        if prov:
            flags.append('fx_provisional')
        if fb:
            flags.append('fx_fallback')
    if UNCONFIRMED.search(text):
        flags.append('unconfirmed')                       # a rumour or a plan, not a completed round: a human decides
    rtype, guessed = parse_round(text, gbp)
    if guessed:
        flags.append('round_guessed')

    lab = labels.get(e['id']) or {}
    if lab.get('source') != 'llm':
        flags.append('label_fallback')
    elif lab.get('confidence', 0) < MIN_CONFIDENCE:
        flags.append('label_low_confidence')

    country, csrc = country_from_url(e.get('source_url', '')), 'url'
    if not country:
        country, csrc = country_from_text(text), 'text'
    if not country:
        # borrow a country from an existing row only when it is clearly the same company (same name AND same sector)
        known = next((r['country'] for r in existing if dedupe.same_company(r['name'], e['company']) and r.get('country') not in (None, '', UNKNOWN)
                      and (not lab.get('category') or not r.get('category') or r['category'] == lab['category'])), None)
        country, csrc = (known, 'existing') if known else (None, '')
    evidence = (lab.get('country_evidence') or '').strip().lower()
    grounded = bool(evidence) and evidence in text.lower() and not EXPANSION_WORDS.search(evidence)   # the text itself must say where the company is based
    if not country and lab.get('country') and grounded and lab.get('country_confidence', 0) >= COUNTRY_MODEL_CONFIDENCE and lab.get('source') == 'llm':
        country, csrc = lab['country'], 'llm'
        flags.append('country_from_model')
    if not country:
        country, csrc = UNKNOWN, 'unknown'
        flags.append('country_unknown')

    cat, sub = lab.get('category', 'Enterprise'), lab.get('sub', 'Productivity')
    blurb = lab.get('blurb', '')
    row = {
        'name': e['company'].strip(' .,'), 'desc': blurb, 'month': month, 'country': country, 'amount': gbp, 'round': rtype, 'investors': parse_investors(text),
        'sector': legacy_sector(cat, sub), 'use': '', 'url': e.get('source_url', ''), 'category': cat, 'sub': sub, 'customer': '', 'ai': '',
        'conf': 'auto', 'blurb': blurb, 'blurb_src': lab.get('source', 'rules'), 'country_src': csrc,
        'amount_native': a['value'], 'currency': a['currency'], 'fx_rate': rate, 'fx_final': (not prov) if a['value'] is not None else None,
        'source_entry': e['id'], 'issue_date': e['issue_date'], 'flags': flags,
    }
    return row


def process_entries(entries, existing, fx, labels, skip=()):
    """Returns a list of results: {entry, status: new|held|duplicate, row, flags, match, enrich}.
    `skip` are entries already recognised as repeats before labelling: they are compared on name, month and amount only."""
    results, pool = [], list(existing)
    for e in sorted(entries, key=lambda x: (x['issue_date'], x['id'])):
        row = make_row(e, labels, pool, fx)
        probe = {**row, 'category': None, 'country': None} if e['id'] in skip else row
        verdict, other = dedupe.classify(probe, pool)
        res = {'entry': e, 'row': row, 'match': other['name'] if other else None, 'enrich': None}
        if verdict == 'duplicate':
            res['status'] = 'duplicate'
            changes = {}
            if not other.get('url') and row['url']:
                changes['url'] = row['url']
            if other.get('country') in (None, '', UNKNOWN) and row['country_src'] in ('url', 'text'):
                changes.update({'country': row['country'], 'country_src': row['country_src']})
            if not other.get('investors') and row['investors']:
                changes['investors'] = row['investors']
            if changes:
                res['enrich'] = {'name': other['name'], 'month': other['month'], 'changes': changes}
            results.append(res)
            continue
        if verdict == 'conflict':
            row['flags'].append('possible_duplicate')
        elif verdict == 'collision':
            row['flags'].append('name_collision')
            taken = {r.get('company_key') or r['name'] for r in pool}
            key = f"{row['name']} ({row['sub']})"
            row['company_key'] = key if key not in taken else f"{key} {row['month']}"
        blocking = [f for f in row['flags'] if f in BLOCKING]
        res['status'] = 'held' if blocking else 'new'
        if blocking:
            row['conf'] = 'review'
        res['blocking'] = blocking
        pool.append(row)
        results.append(res)
    return results


def recalc_fx(rows, fx):
    """Once a month has finished, replace its provisional rate with the final average. Returns how many rows changed."""
    n = 0
    for r in rows:
        if r.get('fx_final') is False and r.get('amount_native') and r['month'] < fx.today.strftime('%Y-%m'):
            try:
                rate, prov, fb = fx.rate(r['currency'], r['month'])
            except Exception:
                continue
            if not prov and not fb:
                r['amount'], r['fx_rate'], r['fx_final'] = round(r['amount_native'] * rate), rate, True
                n += 1
    return n
