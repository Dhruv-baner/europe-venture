# The daily pipeline

Three stages, run in order by `daily.py`, each safe to run on its own.

## Stage 1: collect (`collect.py`)
Reads the Scaling Europe Daily newsletter (Substack feed, archive API as backup) and saves the entries under its
**💰 Funding rounds** heading to `data/raw/funding_entries.jsonl`. Only posts titled `Scaling Europe Daily - <day>.<month>` are used.
Fails loudly (exit 2 unreachable, 3 no new issue for 2+ weekdays, 4 layout changed).

## Stage 2: build rows (`process.py`)
For every collected entry that has not been processed yet:

| Step | How |
|---|---|
| Amount, round, investors | plain rules on the sentence (valuations are not mistaken for the raise) |
| Pounds | monthly average rate from the European Central Bank (Frankfurter service). The current month is provisional and is re-converted at month end |
| Country | from the article link (`denmarks-…`, `berlin-based-…`, `swedish-…`), else from an existing row of the same company, else the AI model if it is confident, else "Europe (unspecified)" |
| Sector, sub-sector, description | the AI model (`ANTHROPIC_API_KEY`), told the exact taxonomy and shown real existing labels. Its answer is checked; one retry; then rough keyword rules |
| Already in the dashboard? | same company + within 2 months + amount agrees = skipped, and the existing row gets its missing link / country filled in |

### What publishes and what is held
Published straight to `rounds.json`: rows with no problems. Notes (unknown country, name shared with another company, vague amount)
do not stop publication; they are listed in `data/staged/review.md`.

**Held** in `data/staged/held_rows.json`: low AI confidence, labelled by the fallback rules (no key or failed check),
same company within 2 months with a different amount, amount that could not be read, or an exchange rate that could not be found.

To publish a held row: open `data/staged/held_rows.json` on GitHub, fix anything wrong, set `"approved": true`, save. The next run publishes it.

### Safety
- If the labelling service fails for every entry (bad key, outage, wrong model name) the run stops with exit 6 and **changes nothing**; the next run retries.
- If the exchange-rate service is down, the latest known rate is used and the row is flagged.
- Every run is repeatable: entries already processed are remembered in `data/processed_entries.json`.

### Settings
- `ANTHROPIC_API_KEY` (GitHub: Settings, Secrets and variables, Actions)
- `LABEL_MODEL` (optional) overrides the model name (default in `funding/label.py`).

## Try it
```
pip install -r pipeline/requirements.txt
python -m pytest -q pipeline/tests
python pipeline/collect.py --dry-run
python pipeline/process.py --dry-run
```

## Stage 3: notify (`notify.py`)
- **`status.json`**: the site shows "Last updated <date>". It moves forward only after a run where every stage succeeded.
- **Review issue** ("Funding rows waiting for review"): lists held rows. Created when the first row is held, re-commented when the list changes
  (a comment is what emails you), closed when nothing is waiting.
- **Alert issue** ("Funding pipeline needs attention"): opens if a stage fails, or if no new rows were published for more than 5 weekdays;
  closes itself after the next healthy run.

## The daily run (`daily.py` + `.github/workflows/daily-update.yml`)
Weekdays at 08:30 UTC (second try 12:30): collect, build rows, notify; then the workflow commits `rounds.json`, `status.json` and `data/` in ONE commit,
and the site redeploys. The run turns red (GitHub emails you) if any stage failed.
`python pipeline/daily.py --dry-run` simulates everything and saves nothing.

## One-time set-up
1. Add `ANTHROPIC_API_KEY` under Settings, Secrets and variables, Actions, New repository secret. (Set a monthly spending limit on the key.)
2. Make sure Issues are enabled (Settings, General, Features).
3. Settings, Actions, General, Workflow permissions: Read and write permissions.
4. Run the workflow by hand with "dry run" ticked and read the log.
5. If, after the first real run, the site does not redeploy by itself (some Vercel plans ignore commits made by bots), create a Deploy Hook
   (Vercel project, Settings, Git, Deploy Hooks) and save its URL as a secret named `VERCEL_DEPLOY_HOOK`.
