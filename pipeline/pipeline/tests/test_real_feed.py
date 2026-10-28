"""Tests built from the REAL Scaling Europe Daily feed (four issues, four different layouts), as seen on 28 Oct 2026."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import collect  # noqa: E402
from funding import build, geo, parse  # noqa: E402

FIX = Path(__file__).parent / 'fixtures'
EXPECTED = json.loads((FIX / 'feed_real_expected.json').read_text(encoding='utf-8'))
ISSUES = {i['title'].split('- ')[1].strip(' .'): i for i in collect.issues_from_feed_xml((FIX / 'feed_real_layouts.xml').read_bytes())}


def entries(key):
    found, ents = collect.extract_funding_entries(ISSUES[key]['html'])
    assert found
    return ents


def test_titles_with_leading_and_trailing_spaces_are_still_followed():
    assert all(collect.is_daily_title(i['title']) for i in ISSUES.values()) and len(ISSUES) == 4


@pytest.mark.parametrize('key,hkey', [('27.10', '2710'), ('22.10', '2210'), ('2.10', '210'), ('4.9', '49')])
def test_every_funding_entry_found_in_order_with_its_link(key, hkey):
    got = entries(key)
    want = EXPECTED[hkey]
    assert [e['company'] for e in got] == [w[0] for w in want]
    assert [e['source_url'] for e in got] == [w[1] for w in want]


def test_other_sections_are_never_mixed_in():
    names = {e['company'] for k in ISSUES for e in entries(k)}
    for decoy in ('Helsing', 'Alex Depledge', 'Veck', 'Eureka! Venture', 'Creandum', 'Checkout.com', 'Mika Games', 'ElevenLabs', 'DIG Ventures', 'Nvidia', 'Hugging Face'):
        assert decoy not in names


def test_bulleted_paragraph_layout_has_clean_company_and_text():
    got = entries('2.10')
    assert got[0]['company'] == 'Foundational' and got[0]['text'].startswith('Foundational raised €9.6m')
    assert got[1]['company'] == 'Osavul' and got[1]['text'].startswith('Osavul raised €8.5m Series A')
    assert all(not e['text'].startswith(('•', '-', '*')) for e in got)


def test_sentence_text_and_link_for_the_issue_in_the_brief():
    nevis = entries('27.10')[0]
    assert nevis['text'] == 'Nevis raised €62M Series B to expand its AI agents for wealth advisers and grow its product and go-to-market teams.'
    assert nevis['source_url'].startswith('https://www.eu-startups.com/2026/10/wealthtech-startup-nevis')
    assert entries('27.10')[9]['text'].startswith('Intuitivo raised €1.35M seed to ease teachers’ workload')    # curly apostrophe survives


def test_amounts_and_rounds_read_from_all_real_sentences():
    no_amount = {'Good Tape'}
    for key in ISSUES:
        for e in entries(key):
            a = parse.parse_amount(e['text'])
            if e['company'] in no_amount:
                assert a['value'] is None
            else:
                assert a['value'] is not None and a['currency'] in ('EUR', 'USD', 'GBP'), e['text']
    t = {e['company']: e['text'] for k in ISSUES for e in entries(k)}
    assert parse.parse_round(t['Nevis'])[0] == 'Series B' and parse.parse_round(t['Epoch'])[0] == 'Seed' and parse.parse_round(t['Tensive'])[0] == 'Debt Financing'
    assert parse.parse_round(t['Cognitive Credit'])[0] == 'Growth Funding' and parse.parse_round(t['Legora'])[0] == 'Series E'
    assert parse.parse_amount(t['Legora'])['value'] == 489e6 and parse.parse_amount(t['Pigment'])['value'] == 250e6     # not the valuation


def test_country_from_real_links():
    want = {'Cognitive Credit': 'United Kingdom', 'Phononic Vibes': 'Italy', 'adsilico': 'United Kingdom', 'Volare': 'Finland', 'Sonexos': 'Switzerland', 'Cygrid': 'Germany', 'Intuitivo': 'Portugal',
            'Photon Bridge': 'Netherlands', 'Skyfly': 'United Kingdom', 'YGO': 'Germany', 'Foundational': 'United Kingdom',
            'Nevis': None, 'Nous': None, 'Epoch': None, 'CHD': None, 'Legora': None, 'Pigment': None, 'Opply': None, 'Osavul': None, 'Deepslate': None}
    got = {e['company']: geo.country_from_url(e['source_url']) for k in ('27.10', '22.10', '2.10') for e in entries(k)}
    for company, country in want.items():
        assert got[company] == country, company


def test_country_from_the_sentence_in_september_style_entries():
    want = {w[0]: geo.canon_country(w[2]) or {'Milan': 'Italy', 'Munich': 'Germany', 'Stafford': 'United Kingdom', 'Brussels': 'Belgium'}[w[2]] for w in EXPECTED['49']}
    for e in entries('4.9'):
        assert geo.country_from_text(e['text']) == want[e['company']], e['company']
    assert geo.country_from_text('Nevis raised €62M Series B.') is None


def test_month_comes_from_the_article_link_around_month_ends():
    e = {'issue_date': '2026-11-02', 'source_url': 'https://tech.eu/2026/10/30/some-startup-raises-5m/'}
    assert build.month_for(e) == '2026-10'                                                  # Monday's issue reporting Friday's news
    assert build.month_for({'issue_date': '2026-11-02', 'source_url': 'https://tech.eu/2026/09/30/x/'}) == '2026-11'   # too old to trust: use the issue month
    assert build.month_for({'issue_date': '2026-10-27', 'source_url': 'https://techfundingnews.com/epoch/'}) == '2026-10'
    assert build.month_for({'issue_date': '2027-01-04', 'source_url': 'https://tech.eu/2026/12/31/x/'}) == '2026-12'
