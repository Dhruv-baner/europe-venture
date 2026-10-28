#!/usr/bin/env python3
"""
Stage 1: collect the "Funding rounds" entries from Scaling Europe Daily.

What it does
  1. Reads the newsletter's Substack feed (falls back to Substack's archive API if the feed fails).
  2. Keeps ONLY issues titled "Scaling Europe Daily - <day>.<month>"  (e.g. "Scaling Europe Daily - 27.10.").
  3. From each of those, takes ONLY the entries under the "Funding rounds" heading.
  4. Appends each entry (company, sentence, source link) to data/raw/funding_entries.jsonl, once.

No AI is used here: the layout is regular, so plain parsing is cheaper, faster and fully predictable.

It is built to fail loudly. Exit codes:
  0  all good
  2  could not fetch the newsletter at all
  3  no new Daily issue for too many weekdays (source may have moved, e.g. to LinkedIn)
  4  an issue has a "Funding rounds" heading but nothing could be read from it (layout changed)
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

FEED_URL = 'https://scalingeurope.substack.com/feed'
ARCHIVE_API = 'https://scalingeurope.substack.com/api/v1/archive'
POST_API = 'https://scalingeurope.substack.com/api/v1/posts/{slug}'
# A plain browser-style identity. Some sites refuse anything whose name contains "bot". This only changes how we introduce ourselves for a public
# feed; it does nothing to hide where requests come from.
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
HEADERS = {'User-Agent': USER_AGENT, 'Accept': 'application/rss+xml, application/xml;q=0.9, application/json;q=0.8, */*;q=0.5', 'Accept-Language': 'en-GB,en;q=0.9'}

# "Scaling Europe Daily - 27.10."  also accepts "27.10" (no final dot) and en/em dashes. Anything else is ignored.
TITLE_RE = re.compile(r'^\s*Scaling Europe Daily\s*[-\u2013\u2014]\s*(\d{1,2})\.(\d{1,2})\.?\s*$', re.IGNORECASE)
FUNDING_RE = re.compile(r'funding\s+rounds?', re.IGNORECASE)
HEADINGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
NS = {'content': 'http://purl.org/rss/1.0/modules/content/'}
VERBS = r'raised|raises|secured|secures|closed|closes|landed|lands|received|receives|announced|announces|bags|nabs|snags|completed|completes|launched|launches|unveiled|emerged|exited'


# ----------------------------------------------------------------------------------------------
# titles and dates
# ----------------------------------------------------------------------------------------------
def is_daily_title(title: str) -> bool:
    return bool(TITLE_RE.match(title or ''))


def issue_date_from(title: str, published: datetime):
    """Date of the issue, from the day.month in the title; the year comes from the publish date."""
    m = TITLE_RE.match(title or '')
    if not m:
        return None
    day, month = int(m.group(1)), int(m.group(2))
    try:
        cand = date(published.year, month, day)
    except ValueError:
        return None
    if cand - published.date() > timedelta(days=60):  # e.g. an issue titled 31.12. published in early January
        cand = date(published.year - 1, month, day)
    return cand


def weekdays_between(start: date, end: date) -> int:
    """Number of weekdays in (start, end]."""
    n, d = 0, start
    while d < end:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


# ----------------------------------------------------------------------------------------------
# reading the "Funding rounds" section out of an issue
# ----------------------------------------------------------------------------------------------
def _text(el) -> str:
    return re.sub(r'\s+', ' ', el.get_text(' ', strip=True).replace('\u00a0', ' ')).strip()


def _is_bold_label(el) -> bool:
    """A paragraph that is just a bold label starting with an emoji/symbol, e.g. <p><strong>💡 Other news</strong></p>."""
    if el.name != 'p':
        return False
    t = _text(el)
    bold = el.find(['strong', 'b'])
    return bool(bold) and _text(bold) == t and len(t) < 60 and bool(t) and not t[0].isalnum()


def _blocks(soup):
    """Headings, rules, paragraphs and list items in reading order (paragraphs inside list items are skipped)."""
    out = []
    for el in soup.find_all(HEADINGS + ['hr', 'p', 'li']):
        if el.name == 'p' and el.find_parent('li'):
            continue
        out.append(el)
    return out


def _parse_entry(el):
    links = el.find_all('a', href=True)
    source = ''
    for a in links:
        if _text(a).lower() in ('here', 'read more', 'read more here'):
            source = a['href']
            break
    if not source and links:
        source = links[-1]['href']
    text = re.sub(r'\s*Read more(?:\s+here)?\s*\.?\s*$', '', _text(el), flags=re.IGNORECASE).strip()
    text = re.sub(r'\s+([.,;:])', r'\1', text)
    company = ''
    bold = el.find(['strong', 'b'])
    if bold:
        company = _text(bold)
    if not company:
        m = re.match(r'^(.+?)\s+(?:' + VERBS + r')\b', text, flags=re.IGNORECASE)
        company = m.group(1).strip() if m else ''
    return {'company': company, 'text': text, 'source_url': source}


def extract_funding_entries(html: str):
    """Returns (heading_found, entries). Entries are only those between the Funding rounds heading and the next section."""
    soup = BeautifulSoup(html or '', 'html.parser')
    blocks = _blocks(soup)
    start = None
    for i, el in enumerate(blocks):
        if el.name in HEADINGS or el.name == 'p':
            t = _text(el)
            if 0 < len(t) <= 60 and FUNDING_RE.search(t):
                start = i
                break
    if start is None:
        return False, []
    entries = []
    for el in blocks[start + 1:]:
        if el.name in HEADINGS or el.name == 'hr' or _is_bold_label(el):
            break  # next section
        if len(_text(el)) < 25:
            continue
        entry = _parse_entry(el)
        if entry['text']:
            entries.append(entry)
    return True, entries


# ----------------------------------------------------------------------------------------------
# getting the issues
# ----------------------------------------------------------------------------------------------
def _get(url, **kw):
    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30, **kw)
            r.raise_for_status()
            return r
        except requests.HTTPError as e:
            last = e
            if e.response is not None and e.response.status_code in (401, 403, 404):
                break                      # blocked or missing: trying again will not help
            time.sleep(2 * (attempt + 1))
        except Exception as e:             # network trouble, 5xx
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f'could not fetch {url}: {last}')


def issues_from_feed_xml(xml_bytes: bytes):
    root = ET.fromstring(xml_bytes)
    out = []
    for item in root.iter('item'):
        title = (item.findtext('title') or '').strip()
        pub = item.findtext('pubDate')
        if not pub:
            continue
        published = parsedate_to_datetime(pub)
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        html = item.findtext('content:encoded', namespaces=NS) or item.findtext('description') or ''
        out.append({'title': title, 'url': (item.findtext('link') or '').strip(), 'published': published, 'html': html})
    return out


def issues_from_archive_api(limit=30):
    posts = _get(ARCHIVE_API, params={'sort': 'new', 'search': '', 'offset': 0, 'limit': limit}).json()
    out = []
    for p in posts:
        title = (p.get('title') or '').strip()
        published = datetime.fromisoformat(p['post_date'].replace('Z', '+00:00'))
        html = ''
        if is_daily_title(title):  # only download the full text of issues we actually want
            html = _get(POST_API.format(slug=p['slug'])).json().get('body_html') or ''
        out.append({'title': title, 'url': p.get('canonical_url', ''), 'published': published, 'html': html})
    return out


def fetch_issues(feed_file=None, feed_url=FEED_URL):
    """Feed first; if it fails or has no Daily issues, use the archive API. Returns (issues, how)."""
    problems = []
    try:
        xml = Path(feed_file).read_bytes() if feed_file else _get(feed_url).content
        issues = issues_from_feed_xml(xml)
        if any(is_daily_title(i['title']) for i in issues):
            return issues, 'feed'
        problems.append('feed had no Daily issues')
    except Exception as e:
        problems.append(f'feed failed: {e}')
    if feed_file:
        raise RuntimeError('; '.join(problems))
    try:
        issues = issues_from_archive_api()
        if any(is_daily_title(i['title']) for i in issues):
            return issues, 'archive-api'
        problems.append('archive API had no Daily issues')
    except Exception as e:
        problems.append(f'archive API failed: {e}')
    raise RuntimeError('; '.join(problems))


# ----------------------------------------------------------------------------------------------
# saving
# ----------------------------------------------------------------------------------------------
def entry_id(issue_date: date, entry: dict) -> str:
    key = f"{issue_date.isoformat()}|{entry['company'].lower()}|{entry['source_url']}|{entry['text'][:80].lower()}"
    return hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]


def load_ids(path: Path):
    ids = set()
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                ids.add(json.loads(line)['id'])
    return ids


def run(args) -> int:
    out_path, issues_path = Path(args.out), Path(args.issues_log)
    today = args.today or datetime.now(timezone.utc).date()
    since = today - timedelta(days=args.since_days)
    try:
        issues, how = fetch_issues(args.feed_file, args.feed_url)
    except RuntimeError as e:
        print(f'ERROR (exit 2): {e}')
        return 2

    daily = []
    for i in issues:
        d = issue_date_from(i['title'], i['published'])
        if d is not None:
            i['issue_date'] = d
            daily.append(i)
    skipped = len(issues) - len(daily)
    print(f'Read {len(issues)} posts via {how}: {len(daily)} Daily issues, {skipped} other posts ignored.')
    if not daily:
        print('ERROR (exit 3): no Daily issues found at all.')
        return 3

    # is the source still alive?
    latest = max(i['issue_date'] for i in daily)
    gap = weekdays_between(latest, today)
    stale = gap > args.max_gap_weekdays
    if stale:
        print(f'ERROR (exit 3): newest Daily issue is {latest} ({gap} weekdays ago). The newsletter may have moved or stopped.')

    have = load_ids(out_path)
    new_rows, problems, quiet, weekend = [], [], [], []
    seen_dates = set()
    for i in sorted(daily, key=lambda x: x['issue_date']):
        d = i['issue_date']
        seen_dates.add(d)
        if d < since:
            continue
        if d.weekday() >= 5:
            weekend.append(d)
        found, entries = extract_funding_entries(i['html'])
        if found and not entries:
            problems.append(f'{i["title"]} ({d}): "Funding rounds" heading found but no entries could be read')
        elif not found:
            quiet.append(d)
        for e in entries:
            row = {'id': entry_id(d, e), 'issue_date': d.isoformat(), 'issue_title': i['title'], 'issue_url': i['url'], **e,
                   'collected_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
            if row['id'] not in have:
                have.add(row['id'])
                new_rows.append(row)

    missing = [d for n in range(args.since_days + 1) if (d := since + timedelta(days=n)).weekday() < 5 and d <= today and d not in seen_dates]
    print(f'New entries: {len(new_rows)}')
    for r in new_rows:
        print(f'  + {r["issue_date"]}  {r["company"]}: {r["text"][:90]}')
    if quiet:
        print('Issues with no Funding rounds section (quiet days?): ' + ', '.join(map(str, quiet)))
    if missing:
        print('Weekdays with no Daily issue (holiday or missed?): ' + ', '.join(map(str, missing)))
    if weekend:
        print('Note: Daily issues dated on a weekend: ' + ', '.join(map(str, weekend)))

    if not args.dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if new_rows:
            with out_path.open('a', encoding='utf-8') as f:
                for r in new_rows:
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
        log = json.loads(issues_path.read_text(encoding='utf-8')) if issues_path.exists() else {}
        for i in daily:
            if i['issue_date'] >= since:
                found, entries = extract_funding_entries(i['html'])
                log[i['url'] or i['title']] = {'title': i['title'], 'issue_date': i['issue_date'].isoformat(), 'funding_section': found, 'entries': len(entries)}
        issues_path.write_text(json.dumps(log, indent=1, ensure_ascii=False, sort_keys=True), encoding='utf-8')
    else:
        print('(dry run: nothing saved)')

    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as f:
            f.write(f'### Funding rounds collected\n- Source: {how}\n- Daily issues read: {len(daily)}\n- New entries: **{len(new_rows)}**\n- Newest issue: {latest}\n')
            if problems:
                f.write('- Problems:\n' + ''.join(f'  - {p}\n' for p in problems))

    if problems:
        for p in problems:
            print('ERROR (exit 4): ' + p)
        return 4
    return 3 if stale else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--feed-url', default=FEED_URL)
    ap.add_argument('--feed-file', help='read a saved feed file instead of the web (for tests)')
    ap.add_argument('--out', default='data/raw/funding_entries.jsonl')
    ap.add_argument('--issues-log', default='data/raw/issues.json')
    ap.add_argument('--since-days', type=int, default=14, help='only look at issues from the last N days')
    ap.add_argument('--max-gap-weekdays', type=int, default=2, help='alert if the newest Daily issue is older than this')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--today', type=lambda s: date.fromisoformat(s), help='override today (for tests)')
    return run(ap.parse_args(argv))


if __name__ == '__main__':
    sys.exit(main())
