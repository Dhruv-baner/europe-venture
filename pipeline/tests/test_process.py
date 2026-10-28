import json
import shutil
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import process  # noqa: E402
from funding import build, dedupe, fx as fxmod, geo, label, parse  # noqa: E402

FIX = Path(__file__).parent / 'fixtures'
TAX = label.load_taxonomy(Path(__file__).resolve().parents[1] / 'taxonomy.json')


# ------------------------------------------------------------------ reading the sentence
@pytest.mark.parametrize('text,value,cur,rnd', [
    ('Nevis raised €62M Series B to expand its AI agents.', 62e6, 'EUR', 'Series B'),
    ('Cognitive Credit raised €35.73M strategic growth investment to expand in the US.', 35.73e6, 'EUR', 'Growth Funding'),
    ('Phononic Vibes raised €25M to expand its noise control technology.', 25e6, 'EUR', 'Undisclosed/Other'),
    ('adsilico raised £10M Series A to develop its virtual heart models.', 10e6, 'GBP', 'Series A'),
    ('Sonexos raised around €5.4M to take its technology to production.', 5.4e6, 'EUR', 'Undisclosed/Other'),
    ('Epoch raised $4.25M seed to grow its team.', 4.25e6, 'USD', 'Seed'),
    ('Pigment raised $250M at a $2.3B valuation led by the Scaleup Europe Fund.', 250e6, 'USD', 'Undisclosed/Other'),   # valuation is not the raise
    ('Legora raised €489M Series E at a €7.8B valuation.', 489e6, 'EUR', 'Series E'),
    ('Voi secured a €150m revolving credit facility.', 150e6, 'EUR', 'Debt Financing'),
    ('Siloton won a €9.98M Innovate UK contract.', 9.98e6, 'EUR', 'Grant'),
    ('Sovera Security secured €535,000 to develop security infrastructure.', 535000, 'EUR', 'Undisclosed/Other'),   # about £452k, above the £400k pre-seed line
    ('CMR Surgical secured a $400m preferred equity investment from Stryker.', 400e6, 'USD', 'Strategic Investment'),
    ('Coding Giants secured up to €6M venture debt.', 6e6, 'EUR', 'Debt Financing'),
    ('Plinto raised €2.9M pre-Seed led by People Ventures and Emblem.', 2.9e6, 'EUR', 'Pre-Seed'),
    ('Foo raised 3.5 million euros to build robots.', 3.5e6, 'EUR', 'Undisclosed/Other'),
    ('Bar raised £300k pre-seed.', 300000, 'GBP', 'Pre-Seed'),
    ('Baz raised a $3.36 billion convertible note.', 3.36e9, 'USD', 'Debt Financing'),
])
def test_amount_currency_and_round(text, value, cur, rnd):
    a = parse.parse_amount(text)
    assert a['value'] == pytest.approx(value) and a['currency'] == cur
    gbp = value if cur == 'GBP' else None
    assert parse.parse_round(text, gbp)[0] == rnd


def test_vague_and_missing_amounts():
    assert parse.parse_amount('NOVUS raised an undisclosed amount led by 468 Capital.')['vague']
    assert parse.parse_amount('Skeleton Technologies secured a nine-figure strategic investment led by Siemens.')['vague']
    assert parse.parse_amount('Good Tape raised funding to develop a context layer.') == {'value': None, 'currency': None, 'vague': False, 'unparsed': False}
    assert parse.parse_amount('Foo raised 50 million kr.')['unparsed'] or parse.parse_amount('Foo raised kr 50 million.')['unparsed']


def test_pre_series_a_follows_house_rule_and_extensions():
    assert parse.parse_round('X raised a pre-Series A round.')[0] == 'Series A'
    assert parse.parse_round('X raised a Series A+ round.')[0] == 'Series A Extension'
    assert parse.parse_round('X raised a Series B extension.')[0] == 'Series B Extension'


def test_investors():
    assert parse.parse_investors('XRlabs raised €7.48M seed led by Playground Global, with Eka Ventures, to bring AI into the operating room.') == 'Playground Global, Eka Ventures'
    assert parse.parse_investors('Pigment raised $250M led by the Scaleup Europe Fund for its platform.') == 'Scaleup Europe Fund'
    assert parse.parse_investors('Nevis raised €62M Series B to expand its AI agents.') == ''


# ------------------------------------------------------------------ country from the link
@pytest.mark.parametrize('url,country', [
    ('https://www.eu-startups.com/2026/10/denmarks-breye-therapeutics-raises-e67-5-million-to-advance-oral-therapies', 'Denmark'),
    ('https://tech.eu/2026/10/02/swedish-fintech-receives-40m-equity-commitment-from-key-shareholders/', 'Sweden'),
    ('https://www.eu-startups.com/2026/10/berlin-based-kuro-raises-e10-million-to-build-the-ai-foundation', 'Germany'),
    ('https://www.eu-startups.com/2026/10/swedens-omnio-raises-e2-9-million-to-advance-its-plasminogen-based-therapy', 'Sweden'),
    ('https://tech.eu/2026/10/05/san-sebastian-based-foo-raises-e1m/', 'Spain'),
    ('https://tech.eu/2026/10/06/uk-based-samplelabs-raises-4m/', 'United Kingdom'),
    ('https://www.eu-startups.com/2026/10/french-startup-abc-raises-e3-million', 'France'),
    ('https://tech.eu/2026/10/27/nevis-raises-62m-series-b-for-ai-agents', None),
    ('https://tech.eu/2026/10/04/germany-funds-tens-of-thousands-of-interceptor-drones/', None),   # a story about a country, not a company's home
    ('', None),
])
def test_country_from_link(url, country):
    assert geo.country_from_url(url) == country


# ------------------------------------------------------------------ exchange rates
def make_fx(tmp_path, today='2026-10-28', fetcher=None, table=None):
    p = tmp_path / 'fx.json'
    p.write_text(json.dumps(table if table is not None else {'2026-09': {'EUR': 0.8581, 'USD': 0.745193}, '2026-10': {'EUR': 0.84, 'USD': 0.75}, '_provisional': ['2026-10:EUR', '2026-10:USD']}))
    return fxmod.FX(p, date.fromisoformat(today), fetcher=fetcher)


def test_fx_finished_month_uses_fixed_rate_without_network(tmp_path):
    f = make_fx(tmp_path, fetcher=lambda *a: (_ for _ in ()).throw(AssertionError('no network wanted')))
    assert f.to_gbp(1_000_000, 'EUR', '2026-09') == (858100, 0.8581, False, False)
    assert f.to_gbp(5, 'GBP', '2026-09')[0] == 5


def test_fx_open_month_is_refreshed_and_marked_provisional(tmp_path):
    f = make_fx(tmp_path, fetcher=lambda cur, month, today: (0.85, '2026-10-27'))
    amt, rate, prov, fb = f.to_gbp(1_000_000, 'EUR', '2026-10')
    assert (amt, rate, prov, fb) == (850000, 0.85, True, False)
    f.save()
    assert json.loads((tmp_path / 'fx.json').read_text())['2026-10']['EUR'] == 0.85


def test_fx_service_down_keeps_last_rate_and_flags_it(tmp_path):
    f = make_fx(tmp_path, fetcher=lambda *a: (_ for _ in ()).throw(RuntimeError('down')))
    amt, rate, prov, fb = f.to_gbp(1_000_000, 'EUR', '2026-10')
    assert (rate, prov, fb) == (0.84, True, True)


def test_fx_month_end_replaces_provisional_rate_with_final(tmp_path):
    f = make_fx(tmp_path, today='2026-11-03', fetcher=lambda cur, month, today: (0.8447, '2026-10-30'))
    rows = [{'month': '2026-10', 'amount_native': 1_000_000, 'currency': 'EUR', 'amount': 840000, 'fx_rate': 0.84, 'fx_final': False}]
    assert build.recalc_fx(rows, f) == 1
    assert rows[0]['amount'] == 844700 and rows[0]['fx_final'] is True
    f.save()
    assert '2026-10:EUR' not in json.loads((tmp_path / 'fx.json').read_text())['_provisional']


# ------------------------------------------------------------------ the AI's answer is checked
GOOD = {'category': 'Fintech', 'sub': 'Wealth', 'blurb': 'AI agents for wealth advisers', 'country': None, 'confidence': 0.9}


def test_validate_accepts_good_and_rejects_bad_answers():
    assert label.validate(GOOD, TAX) == []
    assert label.validate({**GOOD, 'sub': 'Drones'}, TAX)
    assert label.validate({**GOOD, 'category': 'Crypto'}, TAX)
    assert label.validate({**GOOD, 'blurb': 'Raised €62M to expand'}, TAX)
    assert label.validate({**GOOD, 'blurb': 'AI'}, TAX)
    assert label.validate({**GOOD, 'country': 'Atlantis'}, TAX)
    assert label.validate({**GOOD, 'confidence': None}, TAX)


class Flaky:
    """First answer breaks the rules; the retry (which includes the fix note) is right."""
    def __init__(self):
        self.calls = 0

    def label(self, system, items):
        self.calls += 1
        if self.calls == 1:
            return [{'i': it['i'], **GOOD, 'sub': 'Drones'} for it in items]
        assert all(it.get('fix') for it in items)
        return [{'i': it['i'], **GOOD} for it in items]


def test_one_retry_then_accepted():
    out = label.label_all([{'id': 'a', 'company': 'A', 'text': 'A raised €1m.', 'link': ''}], Flaky(), TAX, [])
    assert out['a']['source'] == 'llm' and out['a']['sub'] == 'Wealth'


class AlwaysWrong:
    def label(self, system, items):
        return [{'i': it['i'], **GOOD, 'sub': 'Drones'} for it in items]


def test_still_wrong_after_retry_falls_back_to_rules():
    out = label.label_all([{'id': 'a', 'company': 'A', 'text': 'A raised €1m to build payment software.', 'link': ''}], AlwaysWrong(), TAX, [])
    assert out['a']['source'] == 'rules' and out['a']['problems'] and out['a']['confidence'] < 0.5


# ------------------------------------------------------------------ duplicates
def test_dedupe_rules():
    existing = [{'name': 'Breye Therapeutics', 'month': '2026-10', 'amount': 57_000_000, 'category': 'Health', 'country': 'Denmark'}]
    base = {'name': 'Breye Therapeutics', 'month': '2026-10', 'amount': 57_100_000, 'category': 'Health', 'country': 'Denmark'}
    assert dedupe.classify(base, existing)[0] == 'duplicate'
    assert dedupe.classify({**base, 'amount': None}, existing)[0] == 'duplicate'
    assert dedupe.classify({**base, 'amount': 30_000_000}, existing)[0] == 'conflict'
    assert dedupe.classify({**base, 'category': 'Fintech'}, existing)[0] == 'collision'
    assert dedupe.classify({**base, 'country': 'France'}, existing)[0] == 'collision'
    assert dedupe.classify({**base, 'month': '2026-01', 'amount': 5_000_000}, existing)[0] == 'new'
    assert dedupe.classify({**base, 'name': 'Other Co'}, existing)[0] == 'new'
    assert dedupe.same_company('Aisel', 'Aisel Health') and not dedupe.same_company('Nous', 'Nova')


# ------------------------------------------------------------------ the whole thing
@pytest.fixture
def workdir(tmp_path, monkeypatch):
    for n in ('entries_sample.jsonl', 'existing_rows.json', 'labels_sample.json'):
        shutil.copy(FIX / n, tmp_path / n)
    shutil.copy(Path(__file__).resolve().parents[2] / 'data' / 'fx_rates.json', tmp_path / 'fx_rates.json')
    (tmp_path / 'rounds.json').write_text((tmp_path / 'existing_rows.json').read_text())
    def fake_json(url, params=None, **kw):                       # stands in for the exchange-rate service
        r = {'EUR': 0.8447, 'USD': 0.7535}[params['base']]
        return {'rates': {'2026-10-01': {'GBP': r}, '2026-10-28': {'GBP': r}}}
    monkeypatch.setattr(fxmod, 'get_json', fake_json)
    return tmp_path


def go(w, *extra):
    return process.main(['--entries', str(w / 'entries_sample.jsonl'), '--rounds', str(w / 'rounds.json'), '--fx', str(w / 'fx_rates.json'), '--state', str(w / 'state.json'),
                         '--held', str(w / 'held.json'), '--review', str(w / 'review.md'), '--today', '2026-10-28', *extra])


def load(w, name):
    return json.loads((w / name).read_text(encoding='utf-8'))


def test_end_to_end_with_labels(workdir):
    before = load(workdir, 'rounds.json')
    assert go(workdir, '--labels-file', str(workdir / 'labels_sample.json')) == 0
    rounds = load(workdir, 'rounds.json')
    by = {r['name']: r for r in rounds}
    new = rounds[len(before):]
    assert [r['name'] for r in new] == ['Nevis', 'Cognitive Credit', 'Phononic Vibes', 'Nous', 'adsilico', 'Volare', 'Epoch', 'ExampleCo']   # the 4 repeats and the low-confidence one are not added
    assert [r['id'] for r in new] == list(range(max(r['id'] for r in before) + 1, max(r['id'] for r in before) + 9))
    # amounts converted at the October monthly average
    assert by['Cognitive Credit']['amount'] == round(35.73e6 * 0.8447) and by['Cognitive Credit']['round'] == 'Growth Funding'
    assert by['Nevis']['amount'] == round(62e6 * 0.8447) and by['Nevis']['round'] == 'Series B' and by['Nevis']['currency'] == 'EUR' and by['Nevis']['fx_final'] is False
    assert by['adsilico']['amount'] == 10_000_000 and by['adsilico']['round'] == 'Series A'
    assert by['Epoch']['round'] == 'Seed' and by['Epoch']['amount'] == round(4.25e6 * 0.7535)
    # countries: from the link, from a confident model answer, or unknown
    assert by['ExampleCo']['country'] == 'United Kingdom' and by['ExampleCo']['country_src'] == 'url'
    assert by['adsilico']['country'] == 'United Kingdom' and by['adsilico']['country_src'] == 'llm' and 'country_from_model' in by['adsilico']['flags']
    assert by['Nevis']['country'] == 'Europe (unspecified)' and 'country_unknown' in by['Nevis']['flags']
    # same name, different company
    assert by['Nous']['company_key'] == 'Nous (Apps)' and 'name_collision' in by['Nous']['flags']
    assert by['Nous']['country'] == 'Europe (unspecified)'      # NOT Italy, which belongs to the other Nous
    # repeats of existing rows are skipped, and the existing rows get their missing link / country
    assert len(rounds) == len(before) + 8 and [r['name'] for r in rounds].count('Omnio') == 1
    assert by['Omnio']['country'] == 'Sweden' and by['Omnio']['country_src'] == 'url' and by['Omnio']['url'].startswith('https://www.eu-startups.com/2026/10/swedens-omnio')
    assert by['Kuro']['url'].startswith('https://www.eu-startups.com/2026/10/berlin-based-kuro')
    # the low-confidence row is held, not published
    held = load(workdir, 'held.json')
    assert [h['name'] for h in held] == ['Sonexos'] and held[0]['approved'] is False and 'label_low_confidence' in held[0]['flags']
    assert 'Sonexos' in (workdir / 'review.md').read_text() and 'label_low_confidence' in (workdir / 'review.md').read_text()
    assert len(load(workdir, 'state.json')) == 13
    # rounds.json keeps one row per line (clean GitHub diffs)
    text = (workdir / 'rounds.json').read_text(encoding='utf-8')
    assert text.startswith('[\n') and text.count('\n') == len(rounds) + 2


def test_running_again_changes_nothing(workdir):
    go(workdir, '--labels-file', str(workdir / 'labels_sample.json'))
    snap = {n: (workdir / n).read_text() for n in ('rounds.json', 'held.json', 'state.json')}
    assert go(workdir, '--labels-file', str(workdir / 'labels_sample.json')) == 0
    assert {n: (workdir / n).read_text() for n in snap} == snap


def test_approving_a_held_row_publishes_it(workdir):
    go(workdir, '--labels-file', str(workdir / 'labels_sample.json'))
    held = load(workdir, 'held.json')
    held[0]['approved'] = True
    (workdir / 'held.json').write_text(json.dumps(held))
    go(workdir, '--labels-file', str(workdir / 'labels_sample.json'))
    rounds = load(workdir, 'rounds.json')
    s = next(r for r in rounds if r['name'] == 'Sonexos')
    assert s['conf'] == 'reviewed' and 'approved' not in s and isinstance(s['id'], int)
    assert load(workdir, 'held.json') == []


def test_without_a_labelling_key_everything_new_is_held(workdir, monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    before = len(load(workdir, 'rounds.json'))
    assert go(workdir, '--llm', 'auto') == 0
    assert len(load(workdir, 'rounds.json')) == before                       # nothing published
    held = load(workdir, 'held.json')
    assert len(held) == 9 and all('label_fallback' in h['flags'] for h in held)


def test_labelling_outage_changes_nothing_and_alerts(workdir, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    def boom(self, system, items):
        raise RuntimeError('labelling API error 401: bad key')
    monkeypatch.setattr(label.AnthropicLabeller, 'label', boom)
    assert go(workdir, '--llm', 'anthropic') == 6
    assert not (workdir / 'state.json').exists() and len(load(workdir, 'rounds.json')) == 10
