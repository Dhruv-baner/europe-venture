#!/usr/bin/env python3
"""
Stage 3: say what happened.

1. status.json   The site shows "Last updated <date>". It moves forward only after a run that fully succeeded,
                 so if the pipeline stops, the date visibly stops too.
2. Review issue  If rows are held for a decision, one GitHub issue ("Funding rows waiting for review") lists them.
                 It is created when the first row is held, updated and re-commented when the list changes (a comment is what emails you),
                 and closed when nothing is waiting.
3. Alert issue   If a stage failed, or no new rows have been published for too long, one issue ("Funding pipeline needs attention") says why,
                 and closes itself once things are healthy again.

Issues are a convenience on top of GitHub's own failure emails. If issues cannot be updated (disabled, no permission) it only warns.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect import weekdays_between  # noqa: E402

REVIEW_LABEL, REVIEW_TITLE = 'data-review', 'Funding rows waiting for review'
ALERT_LABEL, ALERT_TITLE = 'pipeline-alert', 'Funding pipeline needs attention'
STALE_AFTER_WEEKDAYS = 5
REASONS = {
    ('collect', 2): 'The newsletter could not be fetched from Substack (both the feed and the archive failed).',
    ('collect', 3): 'No new Scaling Europe Daily issue for more than 2 weekdays. The newsletter may have stopped or moved (it moved to LinkedIn in September and came back to Substack in October).',
    ('collect', 4): 'A "Funding rounds" heading was found but nothing could be read from it. The newsletter layout has probably changed.',
    ('process', 6): 'The AI labelling service failed for every entry (check the ANTHROPIC_API_KEY secret and the model name). Nothing was changed; the next run retries.',
}


def read_json(path, default):
    p = Path(path)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() and p.read_text(encoding='utf-8').strip() else default


def real_runner(args):
    r = subprocess.run(['gh', *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip())
    return r.stdout


def print_runner(args):  # used when not running on GitHub (local trial)
    print('   [would run] gh ' + ' '.join(args[:6]))
    return '[]'


# ----------------------------------------------------------------------------- status.json
def latest_issue_date(issues_log):
    ds = [v['issue_date'] for v in issues_log.values() if v.get('issue_date')]
    return max(ds) if ds else None


def latest_pipeline_row_date(rounds):
    ds = [r['issue_date'] for r in rounds if r.get('source_entry') and r.get('issue_date')]
    return date.fromisoformat(max(ds)) if ds else None


def write_status(path, today, latest_issue, total_rows):
    Path(path).write_text(json.dumps({'updated': today.isoformat(), 'latest_issue': latest_issue, 'rows': total_rows}, indent=1) + '\n', encoding='utf-8')


# ----------------------------------------------------------------------------- issues
def _marker(kind, value):
    return f'<!-- {kind}:{value} -->'


def _find_marker(body, kind):
    m = re.search(rf'<!-- {kind}:(\S+) -->', body or '')
    return m.group(1) if m else None


def review_body(held, repo, branch):
    edit = f'https://github.com/{repo}/edit/{branch}/data/staged/held_rows.json' if repo else 'data/staged/held_rows.json'
    ids = hashlib.sha1(','.join(sorted(h['source_entry'] for h in held)).encode()).hexdigest()[:12]
    L = [f'**{len(held)} funding row{"s" if len(held) != 1 else ""} {"are" if len(held) != 1 else "is"} waiting for a decision.**', '',
         f'**To publish a row:** open [held_rows.json]({edit}), fix anything wrong in that row, change `"approved": false` to `"approved": true`, and commit. '
         'The next run (weekdays, 08:30 UTC) publishes it. To drop a row, delete it from the file.', '',
         '| Company | Month | Amount (£) | Round | Country | Sector | Why held | Source |', '|---|---|---|---|---|---|---|---|']
    from funding.build import BLOCKING
    for h in held:
        why = ', '.join(f for f in h['flags'] if f in BLOCKING)
        amt = f"{h['amount']:,}" if h.get('amount') else '–'
        src = f"[link]({h['url']})" if h.get('url') else '–'
        L.append(f"| {h['name']} | {h['month']} | {amt} | {h['round']} | {h['country']} | {h['category']} › {h['sub']} | {why} | {src} |")
    L += ['', _marker('held', ids)]
    return '\n'.join(L), ids


def sync_issue(runner, label, title, wanted, color, description, dry=False):
    """wanted = (body, marker_value, comment_when_changed) or None (meaning: nothing to report, close any open issue).
       Returns 'created' | 'updated' | 'unchanged' | 'closed' | 'nothing'."""
    kind = 'held' if label == REVIEW_LABEL else 'alert'
    found = json.loads(runner(['issue', 'list', '--label', label, '--state', 'open', '--json', 'number,body', '--limit', '1']) or '[]')
    open_issue = found[0] if found else None
    if wanted is None:
        if not open_issue:
            return 'nothing'
        if not dry:
            runner(['issue', 'comment', str(open_issue['number']), '--body', 'Resolved: nothing needs attention now. Closing.'])
            runner(['issue', 'close', str(open_issue['number'])])
        return 'closed'
    body, marker_value, comment = wanted
    if open_issue and _find_marker(open_issue.get('body'), kind) == marker_value:
        return 'unchanged'
    if dry:
        return 'created' if not open_issue else 'updated'
    with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(body)
        path = f.name
    try:
        if not open_issue:
            runner(['label', 'create', label, '--color', color, '--description', description, '--force'])
            runner(['issue', 'create', '--title', title, '--body-file', path, '--label', label])
            return 'created'
        runner(['issue', 'edit', str(open_issue['number']), '--body-file', path])
        runner(['issue', 'comment', str(open_issue['number']), '--body', comment])
        return 'updated'
    finally:
        os.unlink(path)


def alert_body(reasons, run_url):
    L = ['**The funding pipeline needs attention.**', '', *[f'- {r}' for r in reasons], '']
    if run_url:
        L += [f'Latest run: {run_url}', '']
    L += ['This issue closes itself after the next healthy run.', '', _marker('alert', hashlib.sha1('|'.join(reasons).encode()).hexdigest()[:12])]
    return '\n'.join(L)


def run(root, today, collect_code, process_code, runner, dry=False, repo='', branch='main', run_url='', stale_after=STALE_AFTER_WEEKDAYS):
    root = Path(root)
    rounds = read_json(root / 'rounds.json', [])
    held = [h for h in read_json(root / 'data/staged/held_rows.json', []) if not h.get('approved')]
    issues_log = read_json(root / 'data/raw/issues.json', {})
    out = {'status': None, 'review': None, 'alert': None}

    # reasons something is wrong
    reasons = [text for (stage, code), text in REASONS.items() if (stage == 'collect' and collect_code == code) or (stage == 'process' and process_code == code)]
    other = [c for c in (collect_code, process_code) if c not in (0, 2, 3, 4, 6)]
    if other:
        reasons.append(f'A stage ended with an unexpected error (exit code {other[0]}). See the latest run log.')
    last = latest_pipeline_row_date(rounds)
    if last and weekdays_between(last, today) > stale_after:
        reasons.append(f'No new funding rows have been published for {weekdays_between(last, today)} weekdays (newest is from {last}). Rows may be held for review, or the newsletter had no funding sections.')

    # 1. the site's "last updated" date
    if collect_code == 0 and process_code == 0:
        if dry:
            print(f'   [dry run] would set status.json updated={today}')
        else:
            write_status(root / 'status.json', today, latest_issue_date(issues_log), len(rounds))
        out['status'] = today.isoformat()

    # 2 and 3. issues
    try:
        wanted_review = (review_body(held, repo, branch)[0], review_body(held, repo, branch)[1], f'The list changed: {len(held)} row(s) are now waiting for review.') if held else None
        out['review'] = sync_issue(runner, REVIEW_LABEL, REVIEW_TITLE, wanted_review, 'FBCA04', 'Funding rows held for a decision', dry)
        wanted_alert = (alert_body(reasons, run_url), hashlib.sha1('|'.join(reasons).encode()).hexdigest()[:12], 'The problem has changed:\n' + '\n'.join(f'- {r}' for r in reasons)) if reasons else None
        out['alert'] = sync_issue(runner, ALERT_LABEL, ALERT_TITLE, wanted_alert, 'D93F0B', 'The funding pipeline needs attention', dry)
    except Exception as e:  # issues disabled, no permission, gh missing: never fail the run for this
        print(f'WARNING: could not update GitHub issues: {e}')
    shown = {k: (f'would be {v}' if dry and v in ('created', 'updated', 'closed') else v) for k, v in out.items()}
    print(f"Notify: status={shown['status']} | review issue={shown['review']} ({len(held)} held) | alert issue={shown['alert']}" + (f' | reasons: {len(reasons)}' if reasons else '') + (' (dry run: no issue is really opened)' if dry else ''))
    return out, reasons
