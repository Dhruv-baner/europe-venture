"""Decides whether a new entry is a round the dashboard already has."""
import re


def norm_name(n: str) -> str:
    n = re.sub(r'\(.*?\)', '', (n or '').lower())
    n = re.sub(r'\b(ltd|limited|gmbh|inc|ag|bv|sas|sa|plc|ab|oy)\b', '', n)
    return re.sub(r'[^a-z0-9]', '', n)


def same_company(a: str, b: str) -> bool:
    na, nb = norm_name(a), norm_name(b)
    if not na or not nb:
        return False
    return na == nb or (min(len(na), len(nb)) >= 5 and (na.startswith(nb) or nb.startswith(na)))


def month_index(m: str) -> int:
    return int(m[:4]) * 12 + int(m[5:7])


def amounts_close(a, b, tol=0.12):
    return a is not None and b is not None and abs(a - b) / max(a, b, 1) <= tol


def classify(row: dict, pool: list):
    """Returns (verdict, other_row).
       'duplicate'  same company, within 2 months, amount agrees (or one side has no amount)
       'conflict'   same company within 2 months but the amounts disagree: a human decides (correction? second tranche?)
       'collision'  same name but a different sector or country: probably a DIFFERENT company
       'new'        nothing similar"""
    near = None
    for r in pool:
        if not same_company(row['name'], r['name']):
            continue
        if r.get('category') and row.get('category') and r['category'] != row['category']:
            return 'collision', r
        if r.get('country') not in (None, '', 'Europe (unspecified)') and row.get('country') not in (None, '', 'Europe (unspecified)') and r['country'] != row['country']:
            return 'collision', r
        if abs(month_index(row['month']) - month_index(r['month'])) <= 2:
            if amounts_close(row.get('amount'), r.get('amount')) or row.get('amount') is None or r.get('amount') is None:
                return 'duplicate', r
            near = near or r
    return ('conflict', near) if near else ('new', None)
