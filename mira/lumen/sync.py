"""Lumen's screen colour: what a light beside the picture should show, frame after frame.

A frame arrives as a tiny RGB thumbnail of the desktop (capture.py shrinks the 4K screen to 64x36
before any colour work). Every light asks the same question of it, "what colour is my part of the
picture?", and the plain pixel average is the wrong answer to that question. The choices below, and
why each was made:

Colours are mixed in LINEAR light. Screen bytes are sRGB-encoded: 128 carries about 22 % of the light
of 255, not half. A lamp mixes light, so averaging encoded bytes would make every boundary between a
bright and a dark area read too dark and would wash saturated colours towards grey. Each pixel goes
through a 256-entry table to linear light before anything is summed.

Pixels are WEIGHTED by colourfulness and brightness. A room lit by the mean of a mostly dark picture
is grey-brown whatever the picture shows, yet people read a scene by its accents: the red sun, the
blue neon sign. A pixel's weight therefore grows with saturation squared times value, plus a smaller
brightness term so that a white moon still counts. A small floor weight keeps a picture with no
colour in it averaging honestly: when nothing is colourful, every pixel weighs the same. The
weighting decides the HUE. The BRIGHTNESS blends the weighted luminance with the plain mean, so a
dark scene with a small sun is red but clearly dimmer than a sunset that fills the screen.

Black bars are not picture. A 2.39:1 film on a 16:9 screen has a black band above and below it, and
a light assigned to "the top of the screen" would show black for the whole film. Bars are found in
every frame as rows or columns that are essentially black. They are trusted only when both sides
agree, because a single dark edge is a dark scene. The bottom bar tolerates subtitles, because that
is where players draw them. A run of darkness longer than any real bar, such as a black frame
between scenes, says nothing about bars and changes nothing. Bars may disappear at once, since
picture inside a bar proves the bar is gone. A larger bar is believed only after it has held steady,
because a dark scene also has dark edges for a second or two. The regions a caller names are mapped
into the picture area, never onto the bars.

Smoothing is exponential in TIME, not per frame, and runs in linear light. A screencast delivers
frames only when the desktop changes, about one a second on a still screen, so a per-frame filter
would fade thirty times slower on a paused film than on a playing one. Exponential decay of linear
intensity looks like a steady fade to the eye, which is how a fade should look. Brightening uses a
shorter time constant than dimming: an explosion should arrive with the picture, and its afterglow
may linger. The modes differ mainly in those constants. A game needs the light within a frame or two
of the action. A film wants cuts to glide rather than strobe. Ambient lighting should be a slow wash
that nobody notices changing. One coefficient moves all three channels, so a transition is a
straight line between two colours and cannot overshoot either of them.

Saturation is boosted after smoothing, and each colour keeps its peak channel. A lamp's diffuser and
the room's walls wash colour out compared with the panel, so a moderate boost restores what the room
loses. The boost fades out near grey, because amplifying the faint tint of a grey picture turns
compression noise into colour flicker. It never pushes a channel below zero, so the hue stays exact.

A GAMMA on the light's level keeps dim scenes dim. A lamp is a linear emitter in a room. If a
picture's dark third (encoded 0 to 80) drove it proportionally, a night scene would light the room
at up to a third of full power, and every bit of noise in those dark pixels would become visible
flicker on the wall. Raising the level to a power above one compresses the darks, where its slope is
small, and leaves bright scenes bright. It acts on the colour's value, never per channel, so it
changes brightness without quietly changing saturation.

Below a FLOOR the light goes dark rather than glimmering. A real lamp cannot render one percent of a
colour: Hue at its lowest step is visibly on and the wrong hue. Near-black output is therefore
black. The floor has hysteresis (the light returns 25 % above the level where it went off), so a
scene hovering at the threshold does not blink.

Output colours are sRGB-encoded, the way a screen colour is written, with brightness carried in their
magnitude. A solid picture colour at full brightness comes out as itself apart from the saturation
boost and the gamma.

Cost: the analysis is pure Python, because numpy is not guaranteed in Mira's runtime. Per-pixel work
runs inside builtin map() calls over byte slices. Every rectangle is answered in constant time from
summed-area tables, so analysing a frame for any number of lights is one pass over its 2304 pixels
plus a few lookups per light. Measured on the station (i5-14400F, Python 3.14) for seven lights plus
the ambient colour: about 1.0 ms per 64x36 frame in a tight loop, and 1.8 to 2.2 ms per frame
inside the live 30 fps capture loop, where the work arrives in bursts and the thread does not keep a
core at full clock. That is 6 to 7 % of one core at 30 fps; the cost scales with frames analysed, so
a capture at the mode's own rate costs proportionally less.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from itertools import accumulate
from operator import add, mul
from typing import Callable

Rect = tuple[float, float, float, float]
RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Mode:
    smoothing: tuple[float, float]  # seconds: time constant when the light brightens, when it dims
    saturation: float               # boost factor; 1 keeps the picture's own saturation
    min_brightness: float           # output level 0..1 below which the light is switched dark
    gamma: float                    # exponent on the output level; above 1 keeps dark scenes dark
    rate: float                     # updates per second a light driver should push in this mode


MODES = {
    'video': Mode(smoothing=(0.12, 0.35), saturation=1.25, min_brightness=0.04, gamma=1.4, rate=25),
    'game': Mode(smoothing=(0.04, 0.08), saturation=1.35, min_brightness=0.03, gamma=1.25, rate=25),
    'ambient': Mode(smoothing=(1.5, 2.5), saturation=1.1, min_brightness=0.06, gamma=1.6, rate=5),
}

# ── letterbox detection ──────────────────────────────────────────────
BAR_LEVEL = 24        # a pixel whose brightest channel is at or below this is black (video black is 16)
BAR_STRICT = 0.97     # share of black pixels a top or side bar row/column needs
BAR_SUBTITLE = 0.75   # bottom bar rows may carry subtitle text
BAR_MAX = 0.3         # no real bar covers more than this share of a dimension
BAR_HOLD = 1.5        # seconds a larger bar must hold steady before it is believed

# ── colour ───────────────────────────────────────────────────────────
WEIGHT_FLOOR = 0.02   # every pixel's minimum weight, so a grey picture averages plainly
WEIGHT_BRIGHT = 0.15  # weight from brightness alone (white highlights)
ACCENT = 0.4          # share of the weighted (accent) luminance in the light's brightness
BOOST_GATE = (0.04, 0.20)   # saturation range over which the boost fades in
FLOOR_RETURN = 1.25   # a dark light returns at this multiple of the floor
SNAP = 1e-4           # linear-light distance at which smoothing has arrived
GRADIENT_DEPTH = 0.25       # how far into the picture an edge segment reads
AROUND_DEPTH = 0.2          # the same for 'around', as a share of the picture's shorter side

EDGES = ('left', 'right', 'top', 'bottom', 'around')

_LY = (0.2126, 0.7152, 0.0722)   # Rec. 709 / sRGB luminance of linear R, G, B


def _to_linear(i: int) -> float:
    c = i / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _encode(v: float) -> float:
    if v <= 0.0:
        return 0.0
    if v >= 1.0:
        return 1.0
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


LIN = [_to_linear(i) for i in range(256)]
# Five sums per rectangle (weight, weighted R, G, B, plain luminance) would need five summed-area
# tables. A complex number carries two floats through the same C-level additions, so the weighted
# channels travel in pairs: (R + iG) and (B + i*1), each times the pixel's weight. Three tables.
_LRC = [complex(v, 0.0) for v in LIN]
_LGC = [complex(0.0, v) for v in LIN]
_LBC = [complex(v, 1.0) for v in LIN]
_YR = [_LY[0] * v for v in LIN]
_YG = [_LY[1] * v for v in LIN]
_YB = [_LY[2] * v for v in LIN]
_DARK = [1 if i <= BAR_LEVEL else 0 for i in range(256)]

# The weight depends on a pixel's brightest and dimmest channel. Quantized to 6 bits each, the table
# has 4096 entries instead of 65536; a weighting function needs no finer steps than that.
_QHI = [(i >> 2) << 6 for i in range(256)]
_QLO = [i >> 2 for i in range(256)]


def _weight(q: int) -> float:
    hi, lo = q >> 6, q & 63
    value = (4 * hi + 1.5) / 255.0
    sat = min(1.0, max(0.0, (hi - lo) / (hi + 0.375)))
    return WEIGHT_FLOOR + value * (WEIGHT_BRIGHT * value + sat * sat)


_WEIGHT = [_weight(q) for q in range(4096)]


def _integral(vals: list, w: int, h: int) -> list:
    """Summed-area table, (w+1) x (h+1), row-major: any rectangle's sum in four lookups."""
    zero = vals[0] * 0                    # 0.0 or 0j: the table keeps the values' type
    prev = [zero] * (w + 1)
    out = list(prev)
    for y in range(h):
        prev = list(map(add, prev, accumulate(vals[y * w:(y + 1) * w], initial=zero)))
        out.extend(prev)
    return out


def _box(t: list, stride: int, x0: int, y0: int, x1: int, y1: int) -> float:
    return t[y1 * stride + x1] - t[y0 * stride + x1] - t[y1 * stride + x0] + t[y0 * stride + x0]


def _run(fractions, need: float) -> int:
    n = 0
    for f in fractions:
        if f < need:
            break
        n += 1
    return n


def _pair(a: int, b: int, size: int):
    """Bars on two opposite sides, or None when the measurement carries no information."""
    if a > size * BAR_MAX or b > size * BAR_MAX:
        return None                       # darkness deeper than any bar: a dark frame, not a bar
    if min(a, b) == 0:
        return (0, 0)                     # a dark edge on one side only is a dark scene
    if abs(a - b) <= max(1, max(a, b) // 4):
        return (a, b)                     # an odd remainder makes centred bars differ by a row
    m = min(a, b)
    return (m, m)


def _span(lo: int, hi: int, a: float, b: float) -> tuple[int, int]:
    """Pixels whose centres fall in [a, b) of the range lo..hi; never empty."""
    size = hi - lo
    fa, fb = lo + a * size, lo + b * size
    i0 = min(hi, max(lo, math.ceil(fa - 0.5)))
    i1 = min(hi, max(lo, math.ceil(fb - 0.5)))
    if i1 <= i0:
        c = min(hi - 1, max(lo, int((fa + fb) / 2)))
        i0, i1 = c, c + 1
    return i0, i1


def _smoothstep(e0: float, e1: float, x: float) -> float:
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def _boost(r: float, g: float, b: float, s: float) -> tuple[float, float, float]:
    m, n = max(r, g, b), min(r, g, b)
    if m <= 0.0 or s == 1.0 or m == n:
        return r, g, b
    k = 1.0 + (s - 1.0) * _smoothstep(BOOST_GATE[0], BOOST_GATE[1], (m - n) / m)
    k = min(k, m / (m - n))               # the dimmest channel stops at zero: the hue is kept
    return m - (m - r) * k, m - (m - g) * k, m - (m - b) * k


def _check_rect(key, rect) -> Rect:
    try:
        x0, y0, x1, y1 = (float(v) for v in rect)
    except (TypeError, ValueError):
        raise ValueError(f'region {key!r}: expected (x0, y0, x1, y1)') from None
    if not (0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0):
        raise ValueError(f'region {key!r}: {rect!r} is not a rectangle inside 0..1')
    return x0, y0, x1, y1


class _Frame:
    __slots__ = ('w', 'h', 'stride', 'rg', 'bw', 'yy', 'box')

    def __init__(self, w, h):
        self.w, self.h, self.stride = w, h, w + 1


class Analyzer:
    """Turns frames into light colours. Keeps per-light smoothing and the letterbox estimate, so one
    Analyzer serves one stream; call its methods from one thread at a time."""

    def __init__(self, mode: str = 'video', *, brightness: float = 1.0,
                 saturation: float | None = None, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._saturation = None
        self.mode = mode
        self.brightness = brightness
        self.saturation = saturation
        self.reset()

    # ── settings ─────────────────────────────────────────────────────
    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, name: str) -> None:
        if name not in MODES:
            raise ValueError(f'unknown mode {name!r}; expected one of {sorted(MODES)}')
        self._mode = name
        self.params = MODES[name]

    @property
    def brightness(self) -> float:
        return self._brightness

    @brightness.setter
    def brightness(self, value: float) -> None:
        value = float(value)
        if not 0.0 <= value <= 1.0:
            raise ValueError('brightness is a share of full level, 0..1')
        self._brightness = value

    @property
    def saturation(self) -> float:
        """The boost in use: the explicit setting, or the mode's own when none was given."""
        return self.params.saturation if self._saturation is None else self._saturation

    @saturation.setter
    def saturation(self, value: float | None) -> None:
        if value is not None:
            value = float(value)
            if not 0.0 <= value <= 3.0:
                raise ValueError('saturation boost must be within 0..3')
        self._saturation = value

    def reset(self) -> None:
        """Forget smoothing, light states and the letterbox estimate (a new source, a new film)."""
        self._lights: dict = {}
        self._crop = [None, None]         # (top, bottom), (left, right) in pixels; None = unknown
        self._pending = [None, None]      # a larger bar waiting out BAR_HOLD: (bars, since)
        self._size = None
        self._last = None                 # (bytes object, _Frame, bars) of the last frame analysed
        self.picture: Rect = (0.0, 0.0, 1.0, 1.0)

    # ── public answers ───────────────────────────────────────────────
    def regions(self, rgb: bytes, w: int, h: int,
                regions: dict[str, Rect]) -> dict[str, RGB]:
        """Colour of each named normalized rect (x0, y0, x1, y1) of the PICTURE (bars excluded)."""
        checked = {key: _check_rect(key, rect) for key, rect in regions.items()}
        frame = self._prepare(rgb, w, h)
        now = self._clock()
        return {key: self._light(('r', key), self._measure(frame, rect), now)
                for key, rect in checked.items()}

    def ambient(self, rgb: bytes, w: int, h: int) -> RGB:
        """One colour for the whole picture: a single lamp, or the PC case."""
        frame = self._prepare(rgb, w, h)
        return self._light(('a',), self._measure(frame, (0.0, 0.0, 1.0, 1.0)), self._clock())

    def gradient(self, rgb: bytes, w: int, h: int, n: int, edge: str = 'bottom') -> list[RGB]:
        """n colours along one edge of the picture, for an addressable strip.

        Order: 'top' and 'bottom' run left to right; 'left' and 'right' run top to bottom;
        'around' runs clockwise from the bottom-left corner: up the left side, along the top,
        down the right side and back along the bottom, spaced evenly by the picture's perimeter.
        """
        if edge not in EDGES:
            raise ValueError(f'unknown edge {edge!r}; expected one of {EDGES}')
        if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 4096:
            raise ValueError('n must be an integer 1..4096')
        frame = self._prepare(rgb, w, h)
        now = self._clock()
        rects = self._edge_rects(n, edge)
        return [self._light(('g', edge, n, i), self._measure(frame, rect), now)
                for i, rect in enumerate(rects)]

    # ── frame preparation ────────────────────────────────────────────
    def _prepare(self, rgb, w: int, h: int) -> _Frame:
        if isinstance(w, bool) or isinstance(h, bool) or not isinstance(w, int) or not isinstance(h, int):
            raise ValueError('width and height must be integers')
        if w < 1 or h < 1 or len(rgb) != w * h * 3:
            raise ValueError(f'expected {w}x{h} RGB24 ({w * h * 3} bytes), got {len(rgb)} bytes')
        if self._size != (w, h):
            self._size = (w, h)
            self._crop = [None, None]
            self._pending = [None, None]
            self._last = None
        last = self._last
        # bytes cannot change under us, so the same object is the same picture: several calls for one
        # frame (regions, then ambient, then a gradient) share one pass over the pixels
        if last is not None and last[0] is rgb:
            frame, bars = last[1], last[2]
        else:
            data = rgb if isinstance(rgb, bytes) else bytes(rgb)
            rs, gs, bs = data[0::3], data[1::3], data[2::3]
            hi = list(map(max, rs, gs, bs))
            lo = map(min, rs, gs, bs)
            wt = list(map(_WEIGHT.__getitem__,
                          map(add, map(_QHI.__getitem__, hi), map(_QLO.__getitem__, lo))))
            rg = map(mul, wt, map(add, map(_LRC.__getitem__, rs), map(_LGC.__getitem__, gs)))
            bw = map(mul, wt, map(_LBC.__getitem__, bs))
            yy = map(add, map(add, map(_YR.__getitem__, rs), map(_YG.__getitem__, gs)),
                     map(_YB.__getitem__, bs))
            bars = self._measure_bars(bytes(map(_DARK.__getitem__, hi)), w, h)
            frame = _Frame(w, h)
            frame.rg = _integral(list(rg), w, h)
            frame.bw = _integral(list(bw), w, h)
            frame.yy = _integral(list(yy), w, h)
            self._last = (rgb, frame, bars) if isinstance(rgb, bytes) else None

        # the bar estimate advances with time even when the picture is the same object again
        self._update_bars(bars, self._clock())
        (top, bottom), (left, right) = (c or (0, 0) for c in self._crop)
        frame.box = (left, top, w - right, h - bottom)
        self.picture = (left / w, top / h, (w - right) / w, (h - bottom) / h)
        return frame

    @staticmethod
    def _measure_bars(dark: bytes, w: int, h: int):
        rows = [dark[y * w:(y + 1) * w].count(1) / w for y in range(h)]
        cols = [dark[x::w].count(1) / h for x in range(w)]
        vertical = _pair(_run(rows, BAR_STRICT), _run(reversed(rows), BAR_SUBTITLE), h)
        horizontal = _pair(_run(cols, BAR_STRICT), _run(reversed(cols), BAR_STRICT), w)
        return vertical, horizontal

    def _update_bars(self, measured, now: float) -> None:
        for axis in (0, 1):
            m = measured[axis]
            if m is None:                 # no information: keep what we believe
                self._pending[axis] = None
                continue
            cur = self._crop[axis]
            if cur is None:               # the first real measurement is believed at once
                self._crop[axis] = m
                self._pending[axis] = None
                continue
            shrunk = (min(m[0], cur[0]), min(m[1], cur[1]))
            if shrunk != cur:             # picture where a bar was: the bar is gone, now
                self._crop[axis] = cur = shrunk
            if m == cur:
                self._pending[axis] = None
                continue
            pending = self._pending[axis]
            if pending is None or pending[0] != m:
                self._pending[axis] = (m, now)
            elif now - pending[1] >= BAR_HOLD:
                self._crop[axis] = m
                self._pending[axis] = None

    # ── measurement and output ───────────────────────────────────────
    @staticmethod
    def _measure(frame: _Frame, rect: Rect) -> tuple[float, float, float]:
        """Target colour of one rect, in linear light."""
        left, top, right, bottom = frame.box
        x0, x1 = _span(left, right, rect[0], rect[2])
        y0, y1 = _span(top, bottom, rect[1], rect[3])
        s = frame.stride
        rg = _box(frame.rg, s, x0, y0, x1, y1)
        bw = _box(frame.bw, s, x0, y0, x1, y1)
        weight = bw.imag
        if weight <= 0.0:
            return 0.0, 0.0, 0.0
        r, g, b = rg.real / weight, rg.imag / weight, bw.real / weight
        y_accent = _LY[0] * r + _LY[1] * g + _LY[2] * b
        if y_accent <= 1e-9:
            return 0.0, 0.0, 0.0
        y_mean = _box(frame.yy, s, x0, y0, x1, y1) / ((x1 - x0) * (y1 - y0))
        k = ((1.0 - ACCENT) * y_mean + ACCENT * y_accent) / y_accent
        r, g, b = r * k, g * k, b * k
        m = max(r, g, b)
        if m > 1.0:
            r, g, b = r / m, g / m, b / m
        return r, g, b

    def _light(self, key, target, now: float) -> RGB:
        state = self._lights.get(key)
        if state is None:
            state = self._lights[key] = [target[0], target[1], target[2], now, True]
        else:
            dt = max(0.0, now - state[3])
            state[3] = now
            rise, fall = self.params.smoothing
            brighter = (_LY[0] * target[0] + _LY[1] * target[1] + _LY[2] * target[2]
                        > _LY[0] * state[0] + _LY[1] * state[1] + _LY[2] * state[2])
            tau = rise if brighter else fall
            a = 1.0 if tau <= 0.0 else 1.0 - math.exp(-dt / tau)
            state[0] += a * (target[0] - state[0])
            state[1] += a * (target[1] - state[1])
            state[2] += a * (target[2] - state[2])
            # An exponential never arrives. Within 1e-4 of linear light (a third of one output step
            # even at the darkest) the light IS at its target, and a still picture then gives a
            # still output that a light driver can stop re-sending.
            if max(abs(target[0] - state[0]), abs(target[1] - state[1]),
                   abs(target[2] - state[2])) < SNAP:
                state[0], state[1], state[2] = target

        r, g, b = _boost(state[0], state[1], state[2], self.saturation)
        er, eg, eb = _encode(r), _encode(g), _encode(b)
        value = max(er, eg, eb)
        level = 0.0 if value <= 0.0 else min(1.0, value ** self.params.gamma * self._brightness)

        floor = self.params.min_brightness
        if state[4] and level < floor:
            state[4] = False
        elif not state[4] and level >= floor * FLOOR_RETURN:
            state[4] = True
        if not state[4] or level <= 0.0:
            return (0, 0, 0)
        k = level / value
        return (min(255, round(255 * er * k)), min(255, round(255 * eg * k)), min(255, round(255 * eb * k)))

    def _edge_rects(self, n: int, edge: str) -> list[Rect]:
        d = GRADIENT_DEPTH
        if edge == 'bottom':
            return [(i / n, 1 - d, (i + 1) / n, 1.0) for i in range(n)]
        if edge == 'top':
            return [(i / n, 0.0, (i + 1) / n, d) for i in range(n)]
        if edge == 'left':
            return [(0.0, i / n, d, (i + 1) / n) for i in range(n)]
        if edge == 'right':
            return [(1 - d, i / n, 1.0, (i + 1) / n) for i in range(n)]
        # around: walk the picture's perimeter in its own pixel proportions
        x0, y0, x1, y1 = self.picture
        pw = (x1 - x0) * (self._size[0] if self._size else 16)
        ph = (y1 - y0) * (self._size[1] if self._size else 9)
        perimeter = 2 * (pw + ph)
        depth = AROUND_DEPTH * min(pw, ph)
        dx, dy = depth / pw, depth / ph
        half = perimeter / (2 * n)
        hx, hy = half / pw, half / ph
        rects = []
        for i in range(n):
            t = (i + 0.5) * perimeter / n
            if t < ph:                                   # left side, going up
                c = 1 - t / ph
                rect = (0.0, c - hy, dx, c + hy)
            elif t < ph + pw:                            # top, going right
                c = (t - ph) / pw
                rect = (c - hx, 0.0, c + hx, dy)
            elif t < 2 * ph + pw:                        # right side, going down
                c = (t - ph - pw) / ph
                rect = (1 - dx, c - hy, 1.0, c + hy)
            else:                                        # bottom, going left
                c = 1 - (t - 2 * ph - pw) / pw
                rect = (c - hx, 1 - dy, c + hx, 1.0)
            ax, ay, bx, by = (min(1.0, max(0.0, v)) for v in rect)
            rects.append((ax, ay, max(bx, ax + 1e-6), max(by, ay + 1e-6)))
        return rects


# ── where on the screen each light looks ─────────────────────────────
SLICE = 0.36          # width of the screen slice a positioned light reads
CENTRE = 0.25         # |x| and |z| within this: the light sits behind the middle of the screen
CENTRE_RECT = (0.25, 0.25, 0.75, 0.75)
BAND = 1 / 3          # |z| beyond this picks the top or bottom third


def _coordinate(value, name: str) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'channel position {name} must be a number') from None
    if not math.isfinite(v):
        raise ValueError(f'channel position {name} must be finite')
    return min(1.0, max(-1.0, v))


def regions_for_channels(channels: list[dict]) -> dict[str, Rect]:
    """Hue entertainment channels -> screen rects, keyed by str(channel id).

    x (-1 left .. +1 right) picks a horizontal slice centred where the light stands; z (-1 low ..
    +1 high) picks the top or bottom third, or the full height for a light at mid height; a light
    close to the middle on both axes reads the centre of the picture. y (back/front) is ignored on
    purpose: depth in the room does not correspond to any part of the picture. A channel may carry
    its position flat ({'id', 'x', 'y', 'z'}) or as the Hue API does ({'channel_id', 'position'}).
    """
    out = {}
    for ch in channels:
        cid = ch.get('id', ch.get('channel_id'))
        if cid is None:
            raise ValueError('every channel needs an id')
        pos = ch.get('position') if isinstance(ch.get('position'), dict) else ch
        x = _coordinate(pos.get('x', 0.0), 'x')
        z = _coordinate(pos.get('z', 0.0), 'z')
        if abs(x) <= CENTRE and abs(z) <= CENTRE:
            out[str(cid)] = CENTRE_RECT
            continue
        x0 = min(max((x + 1) / 2 - SLICE / 2, 0.0), 1.0 - SLICE)
        if z >= BAND:
            y0, y1 = 0.0, BAND
        elif z <= -BAND:
            y0, y1 = 1.0 - BAND, 1.0
        else:
            y0, y1 = 0.0, 1.0
        out[str(cid)] = (x0, y0, min(1.0, x0 + SLICE), y1)
    return out


def regions_for_names(names: list[str]) -> dict[str, Rect]:
    """Lights without a position, spread left to right across the screen in the given order."""
    n = len(names)
    return {str(name): (i / n, 0.0, (i + 1) / n, 1.0) for i, name in enumerate(names)}
