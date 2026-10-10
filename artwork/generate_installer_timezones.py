#!/usr/bin/env python3
"""Build runtime labels from Unicode CLDR; Babel is a development dependency only.

Run with Babel 2.18.0 and the release's tzdata. All editions consume the same
committed data. The image gate refuses a new selectable zone without labels.
"""
import argparse
import json
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones


def generate():
    import babel
    from babel import Locale
    from babel.core import get_global
    from babel.dates import get_timezone_location
    if babel.__version__ != '2.18.0':
        raise RuntimeError('review data drift before changing Babel 2.18.0')
    locales = {code: Locale.parse(code) for code in ('ar', 'en')}
    aliases, territories = get_global('zone_aliases'), get_global('zone_territories')
    # tzdata has renamed IDs that CLDR still stores under the historical ID.
    # Resolve exemplar cities across the reviewed alias family, keeping an
    # explicit city for the requested ID ahead of its canonical representative.
    alias_families = {}
    for alias, canonical in aliases.items():
        alias_families.setdefault(canonical, []).append(alias)
    # tzdata can add a zone before CLDR does. Its country column remains the
    # authority, while a missing exemplar city stays an honest proper-name fallback.
    tab = Path('/usr/share/zoneinfo/zone1970.tab')
    countries = {row.split('\t')[2]: row.split('\t')[0].split(',')[0]
                 for row in tab.read_text().splitlines() if row and not row.startswith('#')}
    labels = {}
    untranslated = []
    for name in sorted(available_timezones()):
        if '/' not in name or name.startswith(('posix/', 'right/', 'Etc/')):
            continue
        zone = ZoneInfo(name)
        canonical = aliases.get(name, name)
        country = countries.get(name) or territories.get(canonical, territories.get(name))
        if not country:
            continue
        label = {}
        for code, locale in locales.items():
            candidates = [name, canonical] + sorted(alias_families.get(canonical, []))
            city = next((locale.time_zones[candidate]['city'] for candidate in candidates
                         if locale.time_zones.get(candidate, {}).get('city')), None)
            if city is None:
                city = get_timezone_location(zone, locale=locale, return_city=True)
            # Nested IANA IDs may otherwise leak a technical region prefix into
            # the proper-name fallback ("Argentina/Buenos Aires").
            if '/' in city:
                city = city.rsplit('/', 1)[-1]
            if code == 'ar' and not any('\u0600' <= char <= '\u06ff' for char in city):
                untranslated.append(name)
            territory = locale.territories.get(country, country)
            label[code] = city + ' · ' + territory
        labels[name] = label
    version = (Path('/usr/share/zoneinfo/tzdata.zi').read_text().splitlines()[0]).removeprefix('# version ')
    return {'schema': 1, 'source': 'Unicode CLDR through Babel 2.18.0',
            'tzdata': version, 'license': 'Unicode-3.0',
            'untranslated_city_fallbacks': untranslated, 'zones': labels}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(generate(), ensure_ascii=False, indent=2) + '\n')
