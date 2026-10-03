"""Colours as people say them, and the conversions every light needs.

The owner names colours in Arabic (often Levantine: «زهري», «موف», «ليلكي»), in English, or as a hex
value from the colour wheel. One table answers all three so the voice brain, the typed brain and the
Lumen page agree on what «بنفسجي» is. White light is a temperature, not an RGB triple: «أبيض دافئ» is
2700 K and lamps that have a white channel render it far better from kelvin than from (255, 200, 150).
"""
from __future__ import annotations

import colorsys
import math
import re
from typing import Optional

RGB = tuple[int, int, int]

# name → (r, g, b). Saturated on purpose: a lamp shows a pastel as washed-out white.
NAMED: dict[str, RGB] = {
    'red': (255, 30, 45), 'crimson': (220, 20, 60), 'maroon': (150, 20, 45),
    'orange': (255, 115, 20), 'amber': (255, 160, 20), 'gold': (255, 190, 40),
    'yellow': (255, 220, 40), 'lime': (160, 255, 40), 'green': (30, 220, 90),
    'mint': (60, 242, 196), 'teal': (0, 190, 170), 'turquoise': (30, 225, 210),
    'cyan': (40, 215, 245), 'sky': (70, 170, 255), 'blue': (40, 90, 255),
    'navy': (20, 40, 160), 'indigo': (80, 40, 220), 'violet': (155, 100, 255),
    'purple': (140, 60, 255), 'lavender': (175, 140, 255), 'magenta': (255, 30, 200),
    'pink': (255, 80, 170), 'rose': (255, 110, 180), 'fuchsia': (255, 20, 150),
}

# Arabic (MSA and Levantine spellings, with and without hamza) → the English key above.
ARABIC = {
    'احمر': 'red', 'أحمر': 'red', 'حمرا': 'red', 'حمراء': 'red', 'قرمزي': 'crimson',
    'خمري': 'maroon', 'ماروني': 'maroon', 'عنابي': 'maroon',
    'برتقالي': 'orange', 'برتقاني': 'orange', 'كهرماني': 'amber', 'ذهبي': 'gold', 'دهبي': 'gold',
    'اصفر': 'yellow', 'أصفر': 'yellow', 'صفرا': 'yellow', 'صفراء': 'yellow', 'ليموني': 'lime',
    'اخضر': 'green', 'أخضر': 'green', 'خضرا': 'green', 'خضراء': 'green', 'نعناعي': 'mint',
    'فيروزي': 'turquoise', 'تركوازي': 'turquoise', 'تركواز': 'turquoise', 'زيتي': 'teal',
    'سماوي': 'cyan', 'سماوي فاتح': 'sky', 'لبني': 'sky', 'ازرق': 'blue', 'أزرق': 'blue', 'زرقا': 'blue',
    'زرقاء': 'blue', 'كحلي': 'navy', 'نيلي': 'indigo',
    'بنفسجي': 'violet', 'موف': 'purple', 'ارجواني': 'purple', 'أرجواني': 'purple', 'ليلكي': 'lavender',
    'لافندر': 'lavender', 'فوشي': 'fuchsia', 'فوشيا': 'fuchsia', 'ماجنتا': 'magenta',
    'وردي': 'pink', 'زهري': 'pink', 'بمبي': 'pink', 'روز': 'rose',
}

# Whites, as colour temperatures (kelvin).
WHITES = {
    'warm white': 2700, 'white': 4000, 'neutral white': 4000, 'cool white': 5500, 'daylight': 6500,
    'candle': 2000, 'soft white': 3000,
    'أبيض دافئ': 2700, 'ابيض دافئ': 2700, 'ابيض دافي': 2700, 'دافئ': 2700, 'دافي': 2700, 'أصفر دافئ': 2400,
    'أبيض': 4000, 'ابيض': 4000, 'بيضا': 4000, 'بيضاء': 4000, 'أبيض محايد': 4000,
    'أبيض بارد': 5500, 'ابيض بارد': 5500, 'بارد': 5500, 'ضوء النهار': 6500, 'نهاري': 6500,
    'شمعة': 2000, 'ضوء شموع': 2000,
}

HEX = re.compile(r'#?([0-9a-fA-F]{6})')


def _norm(text: str) -> str:
    text = text.strip().lower()
    text = re.sub('[ً-ْـ]', '', text)          # tashkeel and tatweel
    text = re.sub(r'^(?:لون|اللون|color|colour)\s+', '', text)
    return re.sub(r'\s+', ' ', text)


def _without_article(text: str) -> str:
    # «الأحمر», «الأبيض الدافئ» → «أحمر», «أبيض دافئ»
    return ' '.join(w[2:] if w.startswith('ال') and len(w) > 4 else w for w in text.split(' '))


def parse(text: str) -> Optional[dict]:
    """{'rgb': (r,g,b)} or {'kelvin': K} for a colour the owner named, or None.

    Accepts names in Arabic/English, '#RRGGBB', 'RRGGBB', 'rgb(r, g, b)' and '2700K'."""
    if not isinstance(text, str) or not text.strip():
        return None
    key = _norm(text)
    for candidate in (key, _without_article(key)):
        if candidate in WHITES:
            return {'kelvin': WHITES[candidate]}
        if candidate in NAMED:
            return {'rgb': NAMED[candidate]}
        if candidate in ARABIC:
            return {'rgb': NAMED[ARABIC[candidate]]}
    m = re.fullmatch(r'(\d{4,5})\s*k', key)
    if m:
        return {'kelvin': max(1500, min(9000, int(m.group(1))))}
    m = HEX.fullmatch(key)
    if m:
        value = m.group(1)
        return {'rgb': tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))}
    m = re.fullmatch(r'rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)', key)
    if m:
        return {'rgb': tuple(max(0, min(255, int(v))) for v in m.groups())}
    return None


def hex_of(rgb) -> str:
    return '#%02X%02X%02X' % tuple(max(0, min(255, int(round(c)))) for c in rgb)


def from_hex(value: str) -> Optional[RGB]:
    m = HEX.fullmatch((value or '').strip())
    if not m:
        return None
    return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))


def kelvin_to_rgb(kelvin: float) -> RGB:
    """Black-body colour of a temperature (Tanner Helland's fit, good to ~1 % in 1000–40000 K)."""
    t = max(1000.0, min(40000.0, float(kelvin))) / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    else:
        r = 329.698727446 * (t - 60) ** -0.1332047592
        g = 288.1221695283 * (t - 60) ** -0.0755148492
        b = 255.0
    return tuple(int(max(0, min(255, v))) for v in (r, g, b))


def xy_to_rgb(x: float, y: float) -> RGB:
    """The sRGB colour of a CIE xy point at full brightness (to paint a Hue lamp's read-back)."""
    if not y:
        return (255, 255, 255)
    Y = 1.0
    X, Z = (Y / y) * x, (Y / y) * (1 - x - y)
    r = X * 1.656492 - Y * 0.354851 - Z * 0.255038
    g = -X * 0.707196 + Y * 1.655397 + Z * 0.036152
    b = X * 0.051713 - Y * 0.121364 + Z * 1.011530
    top = max(r, g, b, 1e-9)
    out = []
    for c in (r / top, g / top, b / top):
        c = max(0.0, c)
        c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        out.append(int(round(max(0.0, min(1.0, c)) * 255)))
    return tuple(out)


def mix(a, b, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def palette_at(palette, phase: float) -> RGB:
    """A colour along a closed palette loop; phase in [0, 1) walks the whole loop once."""
    if not palette:
        return (255, 255, 255)
    if len(palette) == 1:
        return tuple(palette[0])
    phase = phase % 1.0
    pos = phase * len(palette)
    i = int(pos)
    # ease in-out between stops so a drifting scene breathes instead of moving linearly
    t = pos - i
    t = t * t * (3 - 2 * t)
    return mix(palette[i], palette[(i + 1) % len(palette)], t)


def scale(rgb, factor: float) -> RGB:
    return tuple(int(max(0, min(255, round(c * factor)))) for c in rgb)


def close(a, b, tolerance: float = 0.12) -> bool:
    """Whether a lamp's read-back colour is the one asked for.

    Bulbs convert RGB into their own gamut (Hue: CIE xy inside gamut C), so the read-back is never
    the same triple. Hue and saturation are what a person sees; brightness is checked separately."""
    if not a or not b:
        return False
    ha, sa, va = colorsys.rgb_to_hsv(*(c / 255 for c in a))
    hb, sb, vb = colorsys.rgb_to_hsv(*(c / 255 for c in b))
    if sa < 0.2 and sb < 0.2:              # both whitish
        return True
    hue_gap = min(abs(ha - hb), 1 - abs(ha - hb))
    return hue_gap <= tolerance and abs(sa - sb) <= 0.45


def name_of(rgb, lang: str = 'ar') -> str:
    """The nearest named colour, for a spoken read-back («صار بنفسجي»)."""
    if not rgb:
        return ''
    h, s, v = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
    if s < 0.18:
        return 'أبيض' if lang == 'ar' else 'white'
    best, gap = 'red', 9.0
    for key in ('red', 'orange', 'yellow', 'green', 'turquoise', 'cyan', 'blue', 'violet', 'purple', 'pink', 'magenta'):
        hh = colorsys.rgb_to_hsv(*(c / 255 for c in NAMED[key]))[0]
        d = min(abs(h - hh), 1 - abs(h - hh))
        if d < gap:
            best, gap = key, d
    if lang != 'ar':
        return best
    return {'red': 'أحمر', 'orange': 'برتقالي', 'yellow': 'أصفر', 'green': 'أخضر', 'turquoise': 'فيروزي',
            'cyan': 'سماوي', 'blue': 'أزرق', 'violet': 'بنفسجي', 'purple': 'موف', 'pink': 'زهري',
            'magenta': 'فوشي'}[best]


def spoken_names(lang: str = 'ar') -> list[str]:
    """Names the brain may use, for the tool description."""
    if lang == 'ar':
        return sorted(ARABIC) + sorted(k for k in WHITES if not k.isascii())
    return sorted(NAMED) + sorted(k for k in WHITES if k.isascii())
