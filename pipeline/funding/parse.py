"""Reads amount, round type and investors out of one newsletter sentence. Plain rules, no AI."""
import re

SYMBOLS = {'€': 'EUR', '$': 'USD', '£': 'GBP'}
CODES = ('EUR', 'USD', 'GBP', 'CHF', 'SEK', 'NOK', 'DKK', 'PLN', 'CZK')
UNIT = {'billion': 1e9, 'bn': 1e9, 'b': 1e9, 'million': 1e6, 'mn': 1e6, 'm': 1e6, 'thousand': 1e3, 'k': 1e3}
WORD_CUR = {'euro': 'EUR', 'euros': 'EUR', 'dollar': 'USD', 'dollars': 'USD', 'pound': 'GBP', 'pounds': 'GBP'}

AMT = re.compile(r'(?P<cur>[€$£]|\b(?:' + '|'.join(CODES) + r')\b)\s?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?(?P<unit>billion|bn|b|million|mn|m|thousand|k)?\b', re.I)
AMT_WORDS = re.compile(r'(?P<num>\d+(?:\.\d+)?)\s?(?P<unit>billion|bn|million|mn|m)\s?(?P<word>euros?|dollars?|pounds?)\b', re.I)
VAGUE = re.compile(r'\b(undisclosed|nine-figure|eight-figure|seven-figure|multi-million|an unspecified)\b', re.I)
OTHER_CURRENCY = re.compile(r'\b(?:kr|zł|zl|Kč|RON|HUF|BGN|TRY)\b\s?\d|\d\s?(?:kr|zł)\b', re.I)


def _is_valuation(text, m):
    """True when the amount is a valuation, not the money raised: "$2.3B valuation", "at a valuation of nearly $400M", "valued at ..."."""
    after = text[m.end():m.end() + 30].lower()
    before = text[max(0, m.start() - 45):m.start()].lower()
    if re.match(r'\s*(post-money\s+|pre-money\s+)?valuation', after):
        return True
    if re.search(r'\bat an?\s*$', before):
        return True
    return bool(re.search(r'(valuation|valued)\b[^.;,\u20ac$\u00a3\d]{0,30}$', before))     # nothing but filler words between "valuation" and the amount


def parse_amount(text: str) -> dict:
    """Returns {value (in the original currency), currency, vague, unparsed}. Valuations are not mistaken for the raise."""
    for m in AMT.finditer(text):
        if _is_valuation(text, m):
            continue
        cur = m.group('cur').upper()
        cur = SYMBOLS.get(m.group('cur'), cur)
        unit = (m.group('unit') or '').lower()
        value = float(m.group('num').replace(',', '')) * UNIT.get(unit, 1)
        return {'value': value, 'currency': cur, 'vague': False, 'unparsed': False}
    m = AMT_WORDS.search(text)
    if m and not _is_valuation(text, m):
        return {'value': float(m.group('num')) * UNIT[m.group('unit').lower()], 'currency': WORD_CUR[m.group('word').lower()], 'vague': False, 'unparsed': False}
    if OTHER_CURRENCY.search(text):
        return {'value': None, 'currency': None, 'vague': False, 'unparsed': True}   # a currency we do not convert yet: hold for review
    return {'value': None, 'currency': None, 'vague': bool(VAGUE.search(text)), 'unparsed': False}


def parse_round(text: str, amount_gbp=None):
    """Returns (round_type, guessed). Names match the ones already used in rounds.json."""
    t = text.lower()
    if re.search(r'pre-?\s?series\s+a', t):
        return 'Series A', False
    if re.search(r'venture debt|debt financing|credit facility|credit line|revolving credit|convertible (?:note|loan|bond)s?|\bloans?\b|\bdebt\b', t):
        return 'Debt Financing', False
    if re.search(r'\bgrants?\b|innovate uk|horizon europe|\beic\b|awarded|won an? .{0,30}contract', t):
        return 'Grant', False
    m = re.search(r'\bseries\s+([a-h])\b(\s*(?:\+|extension|ext\b|extended))?', t)
    if m:
        return 'Series ' + m.group(1).upper() + (' Extension' if m.group(2) else ''), False
    if re.search(r'extended (?:its )?series\s+([a-h])', t):
        return 'Series ' + re.search(r'extended (?:its )?series\s+([a-h])', t).group(1).upper() + ' Extension', False
    if re.search(r'pre-?\s?seed', t):
        if re.search(r'\bseed\b', re.sub(r'pre-?\s?seed', '', t)):
            return 'Seed', False                      # "across seed and pre-seed": the bigger label
        return 'Pre-Seed', False
    if re.search(r'\bseed\b', t):
        return 'Seed', False
    if re.search(r'preferred equity|strategic investment|minority investment', t):
        return 'Strategic Investment', False
    if re.search(r'\bgrowth (?:investment|round|equity|capital|financing|funding)\b|strategic growth|growth investment', t):
        return 'Growth Funding', False
    if amount_gbp is not None and amount_gbp < 400_000:
        return 'Pre-Seed', True
    return 'Undisclosed/Other', True


_INV_SPAN = re.compile(r'\b(?:co-led by|led by|backed by|investment from|funding from|from)\s+(?:the\s+)?(?P<span>[A-Z0-9][^.]*?)(?=\s+(?:to|for|as|which|that|in order)\b|\.|$)')


def parse_investors(text: str) -> str:
    m = _INV_SPAN.search(text)
    if not m:
        return ''
    span = m.group('span')
    span = re.sub(r',?\s+with\s+', ', ', span)
    parts = [p.strip(' ,') for p in re.split(r',| and ', span) if p.strip(' ,')]
    parts = [p for p in parts if p and p[0].isupper() or p[:1].isdigit()]
    parts = [p for p in parts if not re.match(r'(The|Its|Their|New)\b', p) and len(p) < 40]
    return ', '.join(dict.fromkeys(parts))
