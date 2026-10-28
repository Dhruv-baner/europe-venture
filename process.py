#!/usr/bin/env python3
"""
Stage 2: turn collected newsletter entries into dashboard rows.

Reads   data/raw/funding_entries.jsonl   (from collect.py)
Updates rounds.json                      (the file the website reads)
        data/staged/held_rows.json       (rows that need a human decision)
        data/staged/review.md            (a readable list of what was held or needs a look)
        data/processed_entries.json      (which entries are done, so nothing is processed twice)
        data/fx_rates.json               (monthly average exchange rates)

For every new entry it: reads amount / round / investors, converts to pounds, finds the country (from the article link),
asks the AI model for sector, sub-sector and a one-line description (checked before it is trusted), then compares with rounds.json.
  - already in the dashboard      -> skipped (and the existing row gets its missing link / country filled in)
  - clean                         -> added to rounds.json
  - needs a decision              -> held in data/staged/held_rows.json

To approve a held row: open data/staged/held_rows.json on GitHub, fix anything wrong, set  "approved": true,  and save.
The next run publishes it.

Exit codes: 0 ok, 6 the labelling service failed completely (nothing was changed; the next run retries).
"""
import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from funding import build, label  # noqa: E402
from funding.fx import FX  # noqa: E402


def read_json(path, default):
    p = Path(path)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() and p.read_text(encoding='utf-8').strip() else default


def read_jsonl(path):
    p = Path(path)
    return [json.loads(line) for line in p.read_text(encoding='utf-8').splitlines() if line.strip()] if p.exists() else []


def write_rounds(path, rows):
    """One row per line, so changes show up cleanly on GitHub."""
    Path(path).write_text('[\n' + ',\n'.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) for r in rows) + '\n]\n', encoding='utf-8')


class FileLabeller:
    """Reads labels from a file instead of calling the AI (for tests, or to hand-label something)."""

    def __init__(self, mapping):
        self.map = {k.lower(): v for k, v in mapping.items()}

    def label(self, system, items):
        return [{'i': it['i'], **self.map[it['company'].lower()]} for it in items if it['company'].lower() in self.map]


def choose_labeller(mode, labels_file):
    if labels_file:
        return FileLabeller(json.loads(Path(labels_file).read_text(encoding='utf-8'))), 'file'
    key = os.environ.get('ANTHROPIC_API_KEY')
    if mode == 'none' or (mode == 'auto' and not key):
        return None, 'none'
    if not key:
        raise SystemExit('ANTHROPIC_API_KEY is not set')
    return label.AnthropicLabeller(key), 'anthropic'


def attention_notes(rounds, today, days=45):
    """Published rows from the last `days` days that still deserve a glance (country still unknown, shared name, undisclosed amount)."""
    cutoff = (today - timedelta(days=days)).isoformat()
    out = []
    for r in rounds:
        if not r.get('source_entry') or (r.get('issue_date') or '') < cutoff:
            continue
        why = []
        if r.get('country_src') == 'unknown':
            why.append('country unknown')
        if 'name_collision' in r.get('flags', []):
            why.append('shares a name with another company')
        if 'amount_vague' in r.get('flags', []):
            why.append('amount not disclosed')
        if 'country_from_model' in r.get('flags', []):
            why.append('country read from the text by the AI: check it')
        if why:
            out.append({'name': r['name'], 'month': r['month'], 'note': ', '.join(why)})
    return out


def review_markdown(held, notes):
    L = ['# Review list', '', 'Rows held back need a decision. To publish one: edit `data/staged/held_rows.json`, fix anything wrong, set `"approved": true`, save.', '']
    if held:
        L += ['## Held', '', '| Company | Month | Amount (£) | Round | Country | Sector | Why held | Source |', '|---|---|---|---|---|---|---|---|']
        for r in held:
            why = ', '.join(f for f in r['flags'] if f in build.BLOCKING)
            amt = f"{r['amount']:,}" if r.get('amount') else '–'
            L.append(f"| {r['name']} | {r['month']} | {amt} | {r['round']} | {r['country']} | {r['category']} › {r['sub']} | {why} | {r.get('url') or '–'} |")
    else:
        L += ['## Held', '', 'Nothing is waiting.']
    if notes:
        L += ['', '## Published, but worth a glance', '', '| Company | Month | Note |', '|---|---|---|']
        L += [f"| {n['name']} | {n['month']} | {n['note']} |" for n in notes]
    return '\n'.join(L) + '\n'


def run(a):
    today = a.today or datetime.now(timezone.utc).date()
    entries, state, rounds = read_jsonl(a.entries), read_json(a.state, {}), read_json(a.rounds, [])
    held = read_json(a.held, [])
    tax = label.load_taxonomy(a.taxonomy)
    fx = FX(a.fx, today)

    todo = [e for e in entries if e['id'] not in state]
    print(f'{len(entries)} collected entries, {len(todo)} not processed yet.')

    # 1. previous held rows the human has approved
    approved = [h for h in held if h.get('approved')]
    held = [h for h in held if not h.get('approved')]

    # 2. entries that are clearly already in the dashboard need no labelling
    pool = rounds + held
    skip = build.prelim_duplicates(todo, pool, fx) if todo else set()
    to_label = [build.entry_for_labelling(e) for e in todo if e['id'] not in skip]
    labeller, mode = choose_labeller(a.llm, a.labels_file)
    if to_label and labeller is None:
        print('WARNING: no labelling service configured. Rows get rough keyword labels and are all held for review.')
    labels = label.label_all(to_label, labeller, tax, label.pick_examples(rounds)) if to_label else {}
    if labeller is not None and mode == 'anthropic' and labels and all(l['source'] == 'rules' for l in labels.values()):
        reason = next((p for l in labels.values() for p in l['problems'] if 'API' in p or 'could not' in p), 'unknown')
        print(f'ERROR (exit 6): the labelling service failed for every entry ({reason}). Nothing was changed; the next run will retry.')
        return 6

    # 3. build, compare, decide
    results = build.process_entries(todo, pool, fx, labels, skip)
    recalculated = build.recalc_fx(rounds, fx)
    next_id = max((r['id'] for r in rounds), default=0) + 1
    published, enriched = [], 0
    for h in approved:
        h.pop('approved', None)
        h['conf'] = 'reviewed'
        published.append(h)
    for res in results:
        e, row = res['entry'], res['row']
        if res['status'] == 'duplicate':
            state[e['id']] = 'duplicate'
            if res['enrich']:
                target = next((r for r in rounds if r['name'] == res['enrich']['name'] and r['month'] == res['enrich']['month']), None)
                if target:
                    target.update(res['enrich']['changes'])
                    enriched += 1
        elif res['status'] == 'held':
            row['approved'] = False
            held.append(row)
            state[e['id']] = 'held'
        else:
            published.append(row)
            state[e['id']] = 'published'
    for row in published:
        row['id'] = next_id
        next_id += 1
        rounds.append(row)

    c = {k: sum(1 for v in state.values() if v == k) for k in ('published', 'held', 'duplicate')}
    print(f"This run: {len(published)} published, {sum(1 for r in results if r['status'] == 'held')} held, {sum(1 for r in results if r['status'] == 'duplicate')} duplicates skipped, "
          f"{enriched} existing rows enriched, {recalculated} rows re-converted at final month rates, {len(approved)} approved rows published.")
    for row in published:
        amt = f"£{row['amount'] / 1e6:,.1f}m" if row.get('amount') else 'amount n/a'
        print(f"  + {row['month']}  {row['name']}  {amt}  {row['round']}  {row['country']}  [{row['category']}/{row['sub']}]  {', '.join(f for f in row['flags'] if f not in ('fx_provisional',)) }")
    for row in held:
        if row['source_entry'] in {r['entry']['id'] for r in results}:
            print(f"  ? HELD {row['name']}: {', '.join(f for f in row['flags'] if f in build.BLOCKING)}")

    if a.dry_run:
        print('(dry run: nothing saved)')
    else:
        write_rounds(a.rounds, rounds)
        Path(a.state).parent.mkdir(parents=True, exist_ok=True)
        Path(a.state).write_text(json.dumps(state, indent=0, sort_keys=True), encoding='utf-8')
        Path(a.held).parent.mkdir(parents=True, exist_ok=True)
        Path(a.held).write_text(json.dumps(held, indent=1, ensure_ascii=False), encoding='utf-8')
        Path(a.review).write_text(review_markdown(held, attention_notes(rounds, today)), encoding='utf-8')
        fx.save()

    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf-8') as f:
            f.write(f"### Rows built\n- Published: **{len(published)}**\n- Held for review: **{len(held)}**\n- Duplicates skipped: {sum(1 for r in results if r['status'] == 'duplicate')}\n")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--entries', default='data/raw/funding_entries.jsonl')
    ap.add_argument('--rounds', default='rounds.json')
    ap.add_argument('--fx', default='data/fx_rates.json')
    ap.add_argument('--state', default='data/processed_entries.json')
    ap.add_argument('--held', default='data/staged/held_rows.json')
    ap.add_argument('--review', default='data/staged/review.md')
    ap.add_argument('--taxonomy', default=str(Path(__file__).resolve().parent / 'taxonomy.json'))
    ap.add_argument('--llm', choices=['auto', 'anthropic', 'none'], default='auto')
    ap.add_argument('--labels-file', help='labels from a file instead of the AI (tests / manual)')
    ap.add_argument('--today', type=lambda s: date.fromisoformat(s))
    ap.add_argument('--dry-run', action='store_true')
    return run(ap.parse_args(argv))


if __name__ == '__main__':
    sys.exit(main())
