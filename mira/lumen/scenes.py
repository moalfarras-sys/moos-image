"""Lumen's scenes: a mood for a whole room, not one colour for one lamp.

A scene is a palette spread across the lights it is given (each lamp its own stop of the palette,
so a room shows a gradient instead of one flat colour), a brightness, and optionally motion: the
palette drifts slowly around the room ("aurora"), or a light's own built-in effect runs where the
lamp has one (Hue's candle and fire are rendered inside the bulb and look better than anything a
computer can stream to it). White scenes are colour temperatures, because lamps with a white
channel render kelvin far better than an RGB mix.

Every scene says how the PC case should join it: the same palette streamed along its addressable
fans, or the motherboard controller's own effect (it keeps running when Lumen is not).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from lumen.colors import from_hex


@dataclass(frozen=True)
class Scene:
    id: str
    name_ar: str
    name_en: str
    palette: tuple = ()             # hex stops; empty for a white scene
    brightness: int = 80            # 0–100
    kelvin: Optional[int] = None    # a white scene
    period: float = 0.0             # seconds for the palette to drift once around the room; 0 = still
    hue_effect: Optional[str] = None  # a lamp's own effect where it has it (Hue: candle, fire, prism …)
    pc: str = 'palette'             # 'palette' | 'breathe' | 'cycle' | 'wave' | 'off'
    mood_ar: str = ''
    mood_en: str = ''
    category: str = 'color'         # 'color' | 'white' | 'living'

    def rgb_palette(self):
        return [from_hex(c) for c in self.palette]

    def describe(self, lang: str = 'ar') -> dict:
        return {'id': self.id, 'name': self.name_ar if lang == 'ar' else self.name_en,
                'name_ar': self.name_ar, 'name_en': self.name_en,
                'mood': self.mood_ar if lang == 'ar' else self.mood_en,
                'palette': list(self.palette), 'brightness': self.brightness, 'kelvin': self.kelvin,
                'living': self.period > 0 or bool(self.hue_effect), 'category': self.category}


SCENES: list[Scene] = [
    Scene('aurora', 'شفق', 'Aurora', ('#00F5A0', '#00D9F5', '#7B5CFF', '#FF4FD8'), 70, period=48,
          mood_ar='أخضر وسماوي وبنفسجي يتمايلون ببطء', mood_en='Teal, cyan and violet drifting slowly',
          pc='palette', category='living'),
    Scene('moos', 'زجاج MoOS', 'MoOS Glass', ('#9B7BFF', '#35D8F4', '#FF6FB5', '#3DF2C4'), 75, period=60,
          mood_ar='ألوان MoOS: بنفسجي وسماوي ووردي', mood_en='The MoOS colours: violet, cyan and rose',
          pc='palette', category='living'),
    Scene('sunset', 'غروب', 'Sunset', ('#FF4E2A', '#FF8A3D', '#FFC46B', '#C2366B'), 65, period=90,
          mood_ar='برتقالي ووردي دافئ مثل آخر النهار', mood_en='Warm orange and pink like the end of the day',
          pc='palette', category='living'),
    Scene('ocean', 'محيط', 'Ocean', ('#0050FF', '#00B4D8', '#48CAE4', '#1B2CC1'), 60, period=56,
          mood_ar='أزرق عميق يتموّج', mood_en='Deep blues that ripple', pc='palette', category='living'),
    Scene('forest', 'غابة', 'Forest', ('#1B7F4B', '#52B788', '#A7E163', '#0E5C46'), 55, period=80,
          mood_ar='أخضر هادئ', mood_en='Calm greens', pc='palette', category='living'),
    Scene('neon', 'نيون', 'Neon', ('#FF00A8', '#00E5FF', '#7A00FF', '#FF2E63'), 90, period=24,
          mood_ar='فوشي وسماوي بطاقة عالية', mood_en='High-energy magenta and cyan', pc='palette', category='living'),
    Scene('party', 'حفلة', 'Party', ('#FF1744', '#FF9100', '#FFEA00', '#00E676', '#00B0FF', '#D500F9'), 100,
          period=8, mood_ar='كل الألوان تدور', mood_en='Every colour, spinning', pc='wave', category='living'),
    Scene('cinema', 'سينما', 'Cinema', ('#2A1B6B', '#FF7B39'), 14,
          mood_ar='إضاءة خافتة خلف الشاشة للأفلام', mood_en='Dim bias light for films', pc='palette'),
    Scene('candle', 'شموع', 'Candlelight', ('#FF8C2B', '#FFB25C'), 35, hue_effect='candle',
          mood_ar='وهج شموع يرتجف', mood_en='Flickering candle glow', pc='breathe', category='living'),
    Scene('fire', 'مدفأة', 'Fireplace', ('#FF3D00', '#FF8F00', '#FFB300'), 55, hue_effect='fire', period=6,
          mood_ar='نار دافئة', mood_en='A warm fire', pc='palette', category='living'),
    Scene('focus', 'تركيز', 'Focus', (), 100, kelvin=5000,
          mood_ar='أبيض نهاري ساطع للشغل', mood_en='Bright daylight white for work', pc='off', category='white'),
    Scene('read', 'قراءة', 'Reading', (), 85, kelvin=4000,
          mood_ar='أبيض محايد مريح للعين', mood_en='Neutral white, easy on the eyes', pc='off', category='white'),
    Scene('relax', 'استرخاء', 'Relax', (), 45, kelvin=2700,
          mood_ar='أبيض دافئ وهادئ', mood_en='Calm warm white', pc='palette', category='white'),
    Scene('night', 'ليل', 'Night light', ('#FF6A00',), 4,
          mood_ar='ضوء خافت جداً للمشي بالليل', mood_en='A very dim glow for the night', pc='off', category='white'),
]

BY_ID = {s.id: s for s in SCENES}

# How the owner might name them (the brain resolves free words through this, then the ids).
ALIASES = {
    'شفق قطبي': 'aurora', 'اورورا': 'aurora', 'أورورا': 'aurora', 'غروب الشمس': 'sunset', 'الغروب': 'sunset',
    'بحر': 'ocean', 'المحيط': 'ocean', 'البحر': 'ocean', 'الغابة': 'forest', 'طبيعة': 'forest',
    'سهرة': 'party', 'ديسكو': 'party', 'رقص': 'party', 'فيلم': 'cinema', 'افلام': 'cinema', 'أفلام': 'cinema',
    'السينما': 'cinema', 'شمعة': 'candle', 'الشموع': 'candle', 'نار': 'fire', 'المدفأة': 'fire', 'دفاية': 'fire',
    'شغل': 'focus', 'دراسة': 'focus', 'التركيز': 'focus', 'القراءة': 'read', 'راحة': 'relax', 'هدوء': 'relax',
    'الاسترخاء': 'relax', 'نوم': 'night', 'الليل': 'night', 'ليلي': 'night', 'موس': 'moos', 'MoOS': 'moos',
}


def find(name: str) -> Optional[Scene]:
    if not name:
        return None
    key = name.strip()
    low = key.lower()
    if low in BY_ID:
        return BY_ID[low]
    if key in ALIASES:
        return BY_ID[ALIASES[key]]
    for scene in SCENES:
        if key in (scene.name_ar, scene.name_en) or low == scene.name_en.lower():
            return scene
    return None


def catalog(lang: str = 'ar') -> list[dict]:
    return [s.describe(lang) for s in SCENES]
