#!/usr/bin/env python3
"""
The one command the daily schedule runs:   collect  ->  build rows  ->  notify

  python pipeline/daily.py              the real thing (saves files; the workflow then commits them)
  python pipeline/daily.py --dry-run    simulates everything without saving or opening issues: it still reads the live newsletter,
                                        still calls the AI and the exchange-rate service, and prints what it WOULD publish and hold

Exit code is 0 only if every stage succeeded; otherwise the first failing stage's code, so GitHub marks the run red and emails you.
"""
import argparse
import os
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402
import notify  # noqa: E402
import process  # noqa: E402


def main(argv=None, runner=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default='.', help='repository folder (where rounds.json lives)')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--llm', choices=['auto', 'anthropic', 'none'], default='auto')
    ap.add_argument('--feed-file', help='read a saved newsletter feed instead of the web (tests)')
    ap.add_argument('--labels-file', help='labels from a file instead of the AI (tests)')
    ap.add_argument('--today', type=lambda s: date.fromisoformat(s))
    a = ap.parse_args(argv)

    root, today, dry = Path(a.root), a.today or datetime.now(timezone.utc).date(), a.dry_run
    raw = Path(tempfile.mkdtemp()) if dry else root / 'data' / 'raw'      # a dry run collects into a throwaway folder
    entries, log = raw / 'funding_entries.jsonl', raw / 'issues.json'
    print(f"=== {'DRY RUN' if dry else 'DAILY RUN'} for {today} ===")

    print('\n--- 1. Collect from the newsletter ---')
    c = collect.main(['--out', str(entries), '--issues-log', str(log), '--today', today.isoformat(), *(['--feed-file', a.feed_file] if a.feed_file else [])])

    print('\n--- 2. Build rows ---')
    p = process.main(['--entries', str(entries), '--rounds', str(root / 'rounds.json'), '--fx', str(root / 'data/fx_rates.json'), '--state', str(root / 'data/processed_entries.json'),
                      '--held', str(root / 'data/staged/held_rows.json'), '--review', str(root / 'data/staged/review.md'), '--today', today.isoformat(), '--llm', a.llm,
                      *(['--labels-file', a.labels_file] if a.labels_file else []), *(['--dry-run'] if dry else [])])

    print('\n--- 3. Notify ---')
    if runner is None:
        runner = notify.real_runner if os.environ.get('GITHUB_ACTIONS') else notify.print_runner
    repo, branch = os.environ.get('GITHUB_REPOSITORY', ''), os.environ.get('GITHUB_REF_NAME', 'main')
    run_url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{repo}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}" if repo else ''
    notify.run(root, today, c, p, runner, dry=dry, repo=repo, branch=branch, run_url=run_url)

    code = c or p
    print(f"\n=== {'finished OK' if code == 0 else f'finished with problems (exit {code})'} ===")
    return code


if __name__ == '__main__':
    sys.exit(main())
