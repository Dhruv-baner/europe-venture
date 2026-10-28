import json
import shutil
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import daily  # noqa: E402
import notify  # noqa: E402
from funding import fx as fxmod  # noqa: E402

FIX = Path(__file__).parent / 'fixtures'
REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeGh:
    """Stands in for the GitHub command line tool and remembers what it was asked to do."""
    def __init__(self):
        self.issues, self.calls, self.n = {}, [], 1

    def __call__(self, args):
        self.calls.append(args)
        cmd = ' '.join(args[:2])
        label = args[args.index('--label') + 1] if '--label' in args else None
        if cmd == 'issue list':
            i = self.issues.get(label)
            return json.dumps([{'number': i['number'], 'body': i['body']}] if i and i['open'] else [])
        if cmd == 'issue create':
            self.issues[label] = {'number': self.n, 'body': Path(args[args.index('--body-file') + 1]).read_text(encoding='utf-8'), 'open': True, 'comments': [], 'title': args[args.index('--title') + 1]}
            self.n += 1
        elif cmd in ('issue edit', 'issue comment', 'issue close'):
            i = next(x for x in self.issues.values() if x['number'] == int(args[2]))
            if cmd == 'issue edit':
                i['body'] = Path(args[args.index('--body-file') + 1]).read_text(encoding='utf-8')
            elif cmd == 'issue comment':
                i['comments'].append(args[args.index('--body') + 1])
            else:
                i['open'] = False
        return ''

    def created(self):
        return [c for c in self.calls if c[:2] == ['issue', 'create']]


def held_row(name, sid):
    return {'name': name, 'month': '2026-10', 'amount': 5_000_000, 'round': 'Seed', 'country': 'France', 'category': 'Health', 'sub': 'Biotech', 'url': 'https://tech.eu/x',
            'flags': ['label_low_confidence'], 'source_entry': sid, 'approved': False}


def make_root(tmp_path, held=(), rounds=None, issues=None):
    (tmp_path / 'data/staged').mkdir(parents=True)
    (tmp_path / 'data/raw').mkdir(parents=True)
    (tmp_path / 'rounds.json').write_text(json.dumps(rounds or []))
    (tmp_path / 'data/staged/held_rows.json').write_text(json.dumps(list(held)))
    (tmp_path / 'data/raw/issues.json').write_text(json.dumps(issues or {'u': {'title': 't', 'issue_date': '2026-10-07', 'funding_section': True, 'entries': 3}}))
    return tmp_path


# ------------------------------------------------------------------ the review issue
def test_review_issue_lifecycle(tmp_path):
    gh, root = FakeGh(), make_root(tmp_path, held=[held_row('A', 'e1'), held_row('B', 'e2')])
    today = date(2026, 10, 8)
    out, _ = notify.run(root, today, 0, 0, gh, repo='me/dash', branch='main')
    assert out['review'] == 'created' and len(gh.created()) == 1
    body = gh.issues['data-review']['body']
    assert '2 funding rows are waiting' in body and '| A |' in body and '| B |' in body and 'label_low_confidence' in body and 'github.com/me/dash/edit/main/data/staged/held_rows.json' in body
    # same list again: nothing happens (no email noise)
    assert notify.run(root, today, 0, 0, gh, repo='me/dash')[0]['review'] == 'unchanged' and len(gh.created()) == 1
    # a row is added: body updated AND a comment posted (the comment is what emails you)
    (root / 'data/staged/held_rows.json').write_text(json.dumps([held_row('A', 'e1'), held_row('B', 'e2'), held_row('C', 'e3')]))
    assert notify.run(root, today, 0, 0, gh, repo='me/dash')[0]['review'] == 'updated'
    assert '3 funding rows' in gh.issues['data-review']['body'] and len(gh.issues['data-review']['comments']) == 1
    # everything resolved: closed
    (root / 'data/staged/held_rows.json').write_text('[]')
    assert notify.run(root, today, 0, 0, gh, repo='me/dash')[0]['review'] == 'closed' and gh.issues['data-review']['open'] is False


def test_approved_rows_do_not_count_as_waiting(tmp_path):
    gh = FakeGh()
    ok = held_row('A', 'e1')
    ok['approved'] = True
    root = make_root(tmp_path, held=[ok])
    assert notify.run(root, date(2026, 10, 8), 0, 0, gh)[0]['review'] == 'nothing'


# ------------------------------------------------------------------ the alert issue
def test_alert_for_each_kind_of_failure_and_it_closes_itself(tmp_path):
    root = make_root(tmp_path)
    for stage_codes, phrase in [((2, 0), 'could not be fetched'), ((3, 0), 'No new Scaling Europe Daily issue'), ((4, 0), 'layout'), ((0, 6), 'labelling service failed'), ((1, 0), 'unexpected error')]:
        gh = FakeGh()
        out, reasons = notify.run(root, date(2026, 10, 8), *stage_codes, gh, run_url='https://github.com/me/dash/actions/runs/9')
        assert out['alert'] == 'created' and phrase in gh.issues['pipeline-alert']['body'] and 'actions/runs/9' in gh.issues['pipeline-alert']['body']
        assert out['status'] is None                                            # a failed run never moves the "last updated" date
    healthy, _ = notify.run(root, date(2026, 10, 9), 0, 0, gh)
    assert healthy['alert'] == 'closed' and gh.issues['pipeline-alert']['open'] is False


def test_alert_when_no_new_rows_for_too_long(tmp_path):
    rows = [{'name': 'X', 'source_entry': 'e1', 'issue_date': '2026-10-01'}]
    root = make_root(tmp_path, rounds=rows)
    gh = FakeGh()
    out, reasons = notify.run(root, date(2026, 10, 20), 0, 0, gh)
    assert out['alert'] == 'created' and any('No new funding rows' in r for r in reasons)
    gh2 = FakeGh()
    assert notify.run(root, date(2026, 10, 7), 0, 0, gh2)[0]['alert'] == 'nothing'          # only 4 weekdays: fine
    # no pipeline rows yet (first days): no false alarm
    root2 = make_root(tmp_path / 'b', rounds=[{'name': 'Old', 'issue_date': None}])
    assert notify.run(root2, date(2026, 12, 1), 0, 0, FakeGh())[0]['alert'] == 'nothing'


def test_problems_with_issues_never_fail_the_run(tmp_path):
    def broken(args):
        raise RuntimeError('issues are disabled for this repository')
    root = make_root(tmp_path, held=[held_row('A', 'e1')])
    out, _ = notify.run(root, date(2026, 10, 8), 0, 0, broken)
    assert out['status'] == '2026-10-08'                                              # status still written


# ------------------------------------------------------------------ the site's "last updated"
def test_status_moves_only_after_a_fully_successful_run(tmp_path):
    root = make_root(tmp_path)
    notify.run(root, date(2026, 10, 8), 0, 0, FakeGh())
    s = json.loads((root / 'status.json').read_text())
    assert s == {'updated': '2026-10-08', 'latest_issue': '2026-10-07', 'rows': 0}
    notify.run(root, date(2026, 10, 9), 3, 0, FakeGh())                              # newsletter stale
    notify.run(root, date(2026, 10, 9), 0, 6, FakeGh())                              # labelling failed
    assert json.loads((root / 'status.json').read_text())['updated'] == '2026-10-08'
    notify.run(root, date(2026, 10, 10), 0, 0, FakeGh(), dry=True)                   # dry run
    assert json.loads((root / 'status.json').read_text())['updated'] == '2026-10-08'


# ------------------------------------------------------------------ the whole daily command
@pytest.fixture
def repo(tmp_path, monkeypatch):
    shutil.copy(FIX / 'existing_rows.json', tmp_path / 'rounds.json')
    (tmp_path / 'data').mkdir()
    shutil.copy(REPO_ROOT / 'data' / 'fx_rates.json', tmp_path / 'data' / 'fx_rates.json')
    (tmp_path / 'labels.json').write_text(json.dumps({
        'exampleco': {'category': 'Enterprise', 'sub': 'Productivity', 'blurb': 'Test software for example customers', 'country': None, 'country_confidence': 0, 'confidence': 0.9},
        'samplelabs': {'category': 'Enterprise', 'sub': 'Agents', 'blurb': 'Sample platform for sample teams', 'country': None, 'country_confidence': 0, 'confidence': 0.9}}))
    monkeypatch.setattr(fxmod, 'get_json', lambda url, params=None, **kw: {'rates': {'2026-10-01': {'GBP': 0.8447}, '2026-10-08': {'GBP': 0.8447}}})
    return tmp_path


def daily_run(repo, gh, *extra, feed='feed_sample.xml'):
    return daily.main(['--root', str(repo), '--feed-file', str(FIX / feed), '--labels-file', str(repo / 'labels.json'), '--today', '2026-10-08', *extra], runner=gh)


def snapshot(root):
    return {str(p.relative_to(root)): p.read_text(encoding='utf-8') for p in sorted(root.rglob('*')) if p.is_file()}


def test_a_full_daily_run(repo):
    before = json.loads((repo / 'rounds.json').read_text())
    gh = FakeGh()
    assert daily_run(repo, gh) == 0
    rounds = json.loads((repo / 'rounds.json').read_text())
    assert [r['name'] for r in rounds[len(before):]] == ['ExampleCo', 'SampleLabs']                    # the 4 repeats from 5.10 were recognised
    assert len((repo / 'data/raw/funding_entries.jsonl').read_text().splitlines()) == 6                # collected: 4 + 2
    assert json.loads((repo / 'status.json').read_text()) == {'updated': '2026-10-08', 'latest_issue': '2026-10-07', 'rows': len(rounds)}
    assert next(r for r in rounds if r['name'] == 'Kuro')['url'].startswith('https://www.eu-startups.com/2026/10/berlin-based-kuro')   # repeats got their link
    assert gh.created() == []                                                                          # nothing to report


def test_running_the_day_twice_changes_nothing(repo):
    daily_run(repo, FakeGh())
    snap = snapshot(repo)
    assert daily_run(repo, FakeGh()) == 0
    assert snapshot(repo) == snap


def test_unreachable_newsletter_turns_the_run_red_and_opens_an_alert(repo):
    gh = FakeGh()
    code = daily_run(repo, gh, feed='does_not_exist.xml')
    assert code == 2
    assert 'could not be fetched' in gh.issues['pipeline-alert']['body']
    assert not (repo / 'status.json').exists()


def test_dry_run_touches_nothing(repo):
    snap = snapshot(repo)
    gh = FakeGh()
    assert daily_run(repo, gh, '--dry-run') == 0
    assert snapshot(repo) == snap and gh.created() == []


def test_low_confidence_rows_are_held_and_reported(repo):
    labels = json.loads((repo / 'labels.json').read_text())
    labels['exampleco']['confidence'] = 0.3
    (repo / 'labels.json').write_text(json.dumps(labels))
    gh = FakeGh()
    assert daily_run(repo, gh) == 0
    assert [h['name'] for h in json.loads((repo / 'data/staged/held_rows.json').read_text())] == ['ExampleCo']
    assert 'ExampleCo' in gh.issues['data-review']['body'] and '1 funding row is waiting' in gh.issues['data-review']['body']


def test_the_log_starts_with_the_pipeline_version(repo, capsys):
    daily_run(repo, FakeGh(), '--dry-run')
    out = capsys.readouterr().out
    assert 'Pipeline version: v2026' in out and out.index('Pipeline version') < out.index('1. Collect')
