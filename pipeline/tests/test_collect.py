import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import collect  # noqa: E402

FIX = Path(__file__).parent / 'fixtures'


# ---------- which issues we follow ----------
def test_titles_followed_and_ignored():
    follow = ['Scaling Europe Daily - 27.10', 'Scaling Europe Daily - 27.10.', 'Scaling Europe Daily - 5.10.', 'Scaling Europe Daily – 1.9.', 'scaling europe daily - 14.1.']
    ignore = ['Scaling Europe Daily', 'Welcome to Scaling Europe Daily...', 'Scaling Europe Weekly - 27.10.', 'Scaling Europe #61', 'Scaling Europe Podcast: an interview', 'Scaling Europe Daily - Special edition']
    assert all(collect.is_daily_title(t) for t in follow)
    assert not any(collect.is_daily_title(t) for t in ignore)


def test_issue_date_uses_title_day_month_and_publish_year():
    pub = datetime(2026, 10, 27, 7, 0, tzinfo=timezone.utc)
    assert collect.issue_date_from('Scaling Europe Daily - 27.10.', pub) == date(2026, 10, 27)
    assert collect.issue_date_from('Scaling Europe Daily - 31.12.', datetime(2027, 1, 2, 7, 0, tzinfo=timezone.utc)) == date(2026, 12, 31)
    assert collect.issue_date_from('Scaling Europe Daily - 31.2.', pub) is None  # impossible date


def test_weekday_counting():
    assert collect.weekdays_between(date(2026, 10, 23), date(2026, 10, 26)) == 1   # Fri -> Mon
    assert collect.weekdays_between(date(2026, 10, 26), date(2026, 10, 28)) == 2
    assert collect.weekdays_between(date(2026, 10, 28), date(2026, 10, 28)) == 0


# ---------- reading the Funding rounds section ----------
def test_only_funding_section_is_read():
    found, entries = collect.extract_funding_entries((FIX / 'issue_5_10.html').read_text(encoding='utf-8'))
    assert found
    assert [e['company'] for e in entries] == ['Breye Therapeutics', 'Trustly', 'Kuro', 'Omnio']   # not the Other news / M&A items
    assert entries[0]['text'] == 'Breye Therapeutics raised €67.5m Series A to advance oral therapies for early treatment of retinal diseases toward clinical studies.'
    assert not entries[0]['text'].endswith('here.') and 'Read more' not in entries[0]['text']
    assert entries[0]['source_url'].startswith('https://www.eu-startups.com/2026/10/denmarks-breye-therapeutics')
    assert entries[1]['source_url'].startswith('https://tech.eu/2026/10/02/')


def test_intro_sentence_mentioning_funding_rounds_is_not_mistaken_for_the_heading():
    # the 5.10 fixture's intro says "Funding rounds dominated the weekend..." (long sentence), the real heading is the h3
    found, entries = collect.extract_funding_entries((FIX / 'issue_5_10.html').read_text(encoding='utf-8'))
    assert len(entries) == 4


def test_layout_variation_bold_label_and_plain_paragraphs():
    feed = collect.issues_from_feed_xml((FIX / 'feed_sample.xml').read_bytes())
    html = next(i['html'] for i in feed if i['title'].endswith('6.10.'))
    found, entries = collect.extract_funding_entries(html)
    assert found and [e['company'] for e in entries] == ['ExampleCo', 'SampleLabs']   # stops at the bold "Other news" label


def test_issue_without_funding_section():
    feed = collect.issues_from_feed_xml((FIX / 'feed_sample.xml').read_bytes())
    html = next(i['html'] for i in feed if i['title'].endswith('7.10.'))
    assert collect.extract_funding_entries(html) == (False, [])


# ---------- the whole run ----------
def run(tmp_path, feed='feed_sample.xml', today='2026-10-08', extra=()):
    out, log = tmp_path / 'entries.jsonl', tmp_path / 'issues.json'
    args = ['--feed-file', str(FIX / feed), '--out', str(out), '--issues-log', str(log), '--today', today, '--since-days', '14', *extra]
    return collect.main(args), out, log


def test_full_run_collects_only_daily_funding_entries(tmp_path):
    code, out, log = run(tmp_path)
    assert code == 0
    rows = [json.loads(line) for line in out.read_text(encoding='utf-8').splitlines()]
    assert [r['company'] for r in rows] == ['Breye Therapeutics', 'Trustly', 'Kuro', 'Omnio', 'ExampleCo', 'SampleLabs']
    assert {r['issue_date'] for r in rows} == {'2026-10-05', '2026-10-06'}
    assert all(r['issue_title'].startswith('Scaling Europe Daily') for r in rows)       # the podcast post and welcome post never appear
    issues = json.loads(log.read_text(encoding='utf-8'))
    assert len(issues) == 3                                                              # three Daily issues logged (5.10, 6.10, 7.10)


def test_running_twice_adds_nothing_new(tmp_path):
    run(tmp_path)
    code, out, _ = run(tmp_path)
    assert code == 0
    assert len(out.read_text(encoding='utf-8').splitlines()) == 6


def test_dry_run_saves_nothing(tmp_path):
    code, out, log = run(tmp_path, extra=['--dry-run'])
    assert code == 0 and not out.exists() and not log.exists()


def test_alert_when_the_newsletter_goes_quiet(tmp_path):
    code, _, _ = run(tmp_path, today='2026-10-20')      # newest issue is 7.10 -> 9 weekdays ago
    assert code == 3


def test_alert_when_layout_changes(tmp_path):
    code, _, _ = run(tmp_path, feed='feed_layout_changed.xml', today='2026-10-08')
    assert code == 4


def test_unreadable_source_exits_2(tmp_path):
    code, _, _ = run(tmp_path, feed='does_not_exist.xml')
    assert code == 2


# ---------- fallback when the feed is unavailable ----------
class _Resp:
    def __init__(self, data):
        self._d = data
        self.content = data if isinstance(data, bytes) else b''

    def json(self):
        return self._d


def test_falls_back_to_archive_api_when_feed_fails(monkeypatch, tmp_path):
    html_510 = (FIX / 'issue_5_10.html').read_text(encoding='utf-8')

    def fake_get(url, **kw):
        if url.endswith('/feed'):
            raise RuntimeError('feed blocked')
        if 'archive' in url:
            return _Resp([
                {'title': 'Scaling Europe Daily - 5.10.', 'slug': 'scaling-europe-daily-510', 'post_date': '2026-10-05T07:00:56.719Z', 'canonical_url': 'https://scalingeurope.substack.com/p/scaling-europe-daily-510'},
                {'title': 'Scaling Europe Podcast: an interview', 'slug': 'podcast', 'post_date': '2026-10-04T12:00:00.000Z', 'canonical_url': 'https://scalingeurope.substack.com/p/podcast'},
            ])
        if '/posts/scaling-europe-daily-510' in url:
            return _Resp({'body_html': html_510})
        raise AssertionError('unexpected url ' + url)

    monkeypatch.setattr(collect, '_get', fake_get)
    out, log = tmp_path / 'e.jsonl', tmp_path / 'i.json'
    code = collect.main(['--out', str(out), '--issues-log', str(log), '--today', '2026-10-06', '--since-days', '14'])
    assert code == 0
    rows = [json.loads(line) for line in out.read_text(encoding='utf-8').splitlines()]
    assert [r['company'] for r in rows] == ['Breye Therapeutics', 'Trustly', 'Kuro', 'Omnio']


def test_exit_2_when_feed_and_archive_both_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(collect, '_get', lambda url, **kw: (_ for _ in ()).throw(RuntimeError('blocked')))
    assert collect.main(['--out', str(tmp_path / 'e.jsonl'), '--issues-log', str(tmp_path / 'i.json')]) == 2
