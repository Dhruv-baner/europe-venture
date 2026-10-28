"""Works out a company's country from the link to the article about it (EU-Startups and Tech.eu put it in the web address)."""
import re
from urllib.parse import urlparse

COUNTRIES = ['United Kingdom', 'Germany', 'France', 'Netherlands', 'Sweden', 'Switzerland', 'Spain', 'Italy', 'Finland', 'Belgium', 'Denmark', 'Ireland', 'Austria', 'Poland',
             'Czechia', 'Norway', 'Estonia', 'Ukraine', 'Lithuania', 'Portugal', 'Hungary', 'Bulgaria', 'Croatia', 'Luxembourg', 'Cyprus', 'Latvia', 'Romania', 'Iceland', 'Greece',
             'Moldova', 'Slovenia', 'Slovakia', 'Serbia', 'Turkey', 'Malta', 'Albania', 'North Macedonia', 'Bosnia and Herzegovina', 'Montenegro', 'Georgia', 'Armenia', 'Liechtenstein']
_BY_KEY = {c.lower().replace(' ', '-'): c for c in COUNTRIES}
_ALIASES = {'uk': 'United Kingdom', 'britain': 'United Kingdom', 'england': 'United Kingdom', 'scotland': 'United Kingdom', 'wales': 'United Kingdom', 'czech-republic': 'Czechia',
            'the-netherlands': 'Netherlands', 'holland': 'Netherlands', 'macedonia': 'North Macedonia', 'bosnia': 'Bosnia and Herzegovina'}
_DEMONYMS = {'british': 'United Kingdom', 'english': 'United Kingdom', 'scottish': 'United Kingdom', 'welsh': 'United Kingdom', 'german': 'Germany', 'french': 'France', 'dutch': 'Netherlands',
             'swedish': 'Sweden', 'swiss': 'Switzerland', 'spanish': 'Spain', 'italian': 'Italy', 'finnish': 'Finland', 'belgian': 'Belgium', 'danish': 'Denmark', 'irish': 'Ireland',
             'austrian': 'Austria', 'polish': 'Poland', 'czech': 'Czechia', 'norwegian': 'Norway', 'estonian': 'Estonia', 'ukrainian': 'Ukraine', 'lithuanian': 'Lithuania',
             'portuguese': 'Portugal', 'hungarian': 'Hungary', 'bulgarian': 'Bulgaria', 'croatian': 'Croatia', 'luxembourgish': 'Luxembourg', 'cypriot': 'Cyprus', 'latvian': 'Latvia',
             'romanian': 'Romania', 'icelandic': 'Iceland', 'greek': 'Greece', 'moldovan': 'Moldova', 'slovenian': 'Slovenia', 'slovak': 'Slovakia', 'serbian': 'Serbia', 'turkish': 'Turkey',
             'maltese': 'Malta', 'albanian': 'Albania', 'georgian': 'Georgia', 'armenian': 'Armenia'}
_CITIES = {
    'United Kingdom': 'london cambridge oxford manchester edinburgh glasgow bristol leeds birmingham belfast cardiff brighton sheffield liverpool newcastle nottingham reading southampton harwell harpenden crawley plymouth stafford lancaster aberdeen exeter bath guildford milton-keynes',
    'Germany': 'berlin munich hamburg cologne frankfurt stuttgart dusseldorf leipzig dresden nuremberg hannover heidelberg aachen karlsruhe bonn darmstadt potsdam freiburg jena mannheim dortmund essen bremen tubingen constance',
    'France': 'paris lyon marseille toulouse bordeaux lille nantes nice grenoble montpellier strasbourg rennes aix-en-provence palaiseau sophia-antipolis',
    'Netherlands': 'amsterdam rotterdam utrecht eindhoven delft the-hague groningen leiden maastricht enschede',
    'Sweden': 'stockholm gothenburg malmo uppsala linkoping lund',
    'Switzerland': 'zurich geneva lausanne basel bern zug lugano neuchatel',
    'Spain': 'madrid barcelona valencia malaga seville bilbao san-sebastian elche zaragoza palma',
    'Italy': 'milan rome turin bologna florence naples padua venice trieste',
    'Finland': 'helsinki espoo tampere turku oulu joensuu vantaa',
    'Belgium': 'brussels antwerp ghent leuven liege',
    'Denmark': 'copenhagen aarhus odense aalborg',
    'Ireland': 'dublin cork galway limerick',
    'Austria': 'vienna graz linz salzburg innsbruck',
    'Poland': 'warsaw krakow wroclaw gdansk poznan',
    'Czechia': 'prague brno', 'Norway': 'oslo bergen trondheim stavanger', 'Estonia': 'tallinn tartu', 'Ukraine': 'kyiv kiev lviv kharkiv odesa',
    'Lithuania': 'vilnius kaunas', 'Latvia': 'riga', 'Portugal': 'lisbon porto', 'Hungary': 'budapest', 'Bulgaria': 'sofia', 'Romania': 'bucharest cluj cluj-napoca',
    'Croatia': 'zagreb', 'Iceland': 'reykjavik', 'Greece': 'athens', 'Luxembourg': 'luxembourg-city', 'Slovenia': 'ljubljana', 'Serbia': 'belgrade',
    'Cyprus': 'nicosia limassol', 'Turkey': 'istanbul ankara', 'Malta': 'valletta',
}
_CITY = {c: country for country, cs in _CITIES.items() for c in cs.split()}


def canon_country(name: str):
    """'germany' -> 'Germany', 'UK' -> 'United Kingdom'. None if it is not a country we know."""
    if not name:
        return None
    k = re.sub(r'[\s_]+', '-', name.strip().lower())
    return _ALIASES.get(k) or _BY_KEY.get(k)


def _place(token_key: str):
    return canon_country(token_key) or _CITY.get(token_key)


def country_from_url(url: str):
    """Reads the start of the article's web address. Examples that work:
       .../denmarks-breye-therapeutics-raises...      -> Denmark
       .../berlin-based-kuro-raises-e10-million...     -> Germany
       .../swedish-fintech-receives-40m...             -> Sweden
       .../uk-based-startup-...                        -> United Kingdom
       Returns None when the address does not say (e.g. '.../nevis-raises-62m-series-b')."""
    if not url:
        return None
    path = urlparse(url).path.strip('/')
    slug = path.split('/')[-1].lower() if path else ''
    if not slug:
        return None
    tokens = slug.split('-')
    # "<place>-based"  (place can be 1-3 words, e.g. san-sebastian-based)
    for j in range(1, 4):
        if len(tokens) > j and tokens[j] == 'based':
            c = _place('-'.join(tokens[:j]))
            if c:
                return c
    # "<country>s-..." possessive  (denmarks, swedens, frances ...)  and "<country>-..." / "the-netherlands-..."
    for j in (3, 2, 1):
        key = '-'.join(tokens[:j])
        if key.endswith('s') and (canon_country(key[:-1]) or _CITY.get(key[:-1])):
            return canon_country(key[:-1]) or _CITY.get(key[:-1])
        nxt = tokens[j] if len(tokens) > j else ''
        if canon_country(key) and nxt in ('startup', 'startups', 'scaleup', 'company', 'fintech', 'healthtech', 'biotech', 'deeptech', 'cleantech', 'spinout'):
            return canon_country(key)       # a bare country name only counts when it describes the company
    if tokens[0] in _DEMONYMS:
        return _DEMONYMS[tokens[0]]
    # a city first, in a link that is clearly about a funding round: "leeds-ai-spinout-adsilico-raises-..."
    if tokens[0] in _CITY and any(t in _FUNDING_WORDS for t in tokens[1:]):
        return _CITY[tokens[0]]
    return None


_FUNDING_WORDS = {'raises', 'raise', 'secures', 'lands', 'bags', 'closes', 'funding', 'receives', 'wins', 'scores', 'nabs', 'exits', 'emerges', 'launches'}


def country_from_text(text: str):
    """Older newsletter entries start with the place: "Milan-based Tensive received ...", "UK-based Rightcharge raised ..."."""
    m = re.match(r"^\s*([A-Za-z][A-Za-z .'\u00c0-\u017f]*?)-based\s", text or '')
    if not m:
        return None
    place = re.sub(r'[\s_]+', '-', m.group(1).strip().lower())
    return _place(place)
