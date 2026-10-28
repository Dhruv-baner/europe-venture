import time

import requests

USER_AGENT = 'Mozilla/5.0 (compatible; FundingDashboardBot/1.0; personal research project)'


def get_json(url, params=None, retries=3, timeout=30):
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers={'User-Agent': USER_AGENT}, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f'could not fetch {url}: {last}')
