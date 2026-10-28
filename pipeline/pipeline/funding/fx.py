"""Converts amounts to pounds at the MONTHLY AVERAGE rate, the same method the dashboard's existing numbers use.

Rates live in data/fx_rates.json:  {"2026-10": {"EUR": 0.8447, "USD": 0.7535}, ..., "_provisional": ["2026-10"]}
- A finished month uses its fixed average.
- The current month uses the average so far (provisional) and is recalculated once the month ends.
- If the rate service is unreachable, the latest known rate is used and the row is flagged.
Daily rates come from the free Frankfurter service (European Central Bank data).
"""
import json
import statistics
from datetime import date, timedelta
from pathlib import Path

from .http import get_json

FRANKFURTER = 'https://api.frankfurter.dev/v1/{start}..{end}'


def month_bounds(month: str):
    y, m = int(month[:4]), int(month[5:7])
    start = date(y, m, 1)
    end = (date(y + (m == 12), (m % 12) + 1, 1)) - timedelta(days=1)
    return start, end


def fetch_monthly_average(currency: str, month: str, today: date):
    """Average GBP per 1 unit of `currency` for the month so far. Returns (rate, last_day_used)."""
    start, end = month_bounds(month)
    end = min(end, today)
    data = get_json(FRANKFURTER.format(start=start.isoformat(), end=end.isoformat()), params={'base': currency, 'symbols': 'GBP'})
    rates = [v['GBP'] for v in data['rates'].values() if 'GBP' in v]
    if not rates:
        raise RuntimeError(f'no rates returned for {currency} {month}')
    return round(statistics.mean(rates), 6), max(data['rates'])


class FX:
    def __init__(self, path, today: date, fetcher=None):
        self.path, self.today = Path(path), today
        self.fetcher = fetcher or fetch_monthly_average
        self.table = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
        self.table.setdefault('_provisional', [])      # entries like "2026-10:EUR": a rate that is still a month-so-far average
        self._memo = {}
        self.changed = False

    def _is_open(self, month):  # the month has not finished yet
        return month >= self.today.strftime('%Y-%m')

    def rate(self, currency: str, month: str):
        """Returns (rate, provisional, fallback_used)."""
        if currency == 'GBP':
            return 1.0, False, False
        key = (currency, month)
        if key in self._memo:
            return self._memo[key]
        tag = f'{month}:{currency}'
        have = self.table.get(month, {}).get(currency)
        open_month = self._is_open(month)
        if have is not None and not open_month and tag not in self.table['_provisional']:
            out = (have, False, False)                     # a finished month with a final rate
        else:
            try:
                r, _ = self.fetcher(currency, month, self.today)
                self.table.setdefault(month, {})[currency] = r
                if open_month and tag not in self.table['_provisional']:
                    self.table['_provisional'].append(tag)
                if not open_month and tag in self.table['_provisional']:
                    self.table['_provisional'].remove(tag)
                self.changed = True
                out = (r, open_month, False)
            except Exception:
                if have is not None:
                    out = (have, True, True)               # service down: keep what we had, flagged
                else:
                    older = sorted((k for k in self.table if k[:2] == '20' and currency in self.table[k]), reverse=True)
                    if not older:
                        raise
                    out = (self.table[older[0]][currency], True, True)   # latest known month, flagged
        self._memo[key] = out
        return out

    def to_gbp(self, value, currency, month):
        """Returns (gbp_amount or None, rate, provisional, fallback_used)."""
        if value is None or currency is None:
            return None, None, False, False
        r, prov, fb = self.rate(currency, month)
        return round(value * r), r, prov, fb

    def save(self):
        if self.changed:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.table, indent=1, sort_keys=True), encoding='utf-8')
