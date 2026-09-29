"""How much Mira moves on this machine: read from MoOS, never guessed.

MoOS has one authority on "what can this machine afford to draw", `moos-visual-tier`. It probes
the graphics, cores and memory, picks flagship / balanced / essential, writes the Plasma motion
profile and records its answer in ~/.local/state/moos-visual-tier.json (`moos-apply-theme` runs it
at every login; `moos-theme perf` pins a tier in ~/.config/moos-visual-tier). The owner has one
animation-speed control of his own, [KDE] AnimationDurationFactor in kdeglobals. Mira reads those
and probes nothing herself: no /sys, no subprocess, no GPU classification of her own. That stays
with moos-visual-tier (and usr/lib/moos/moos_hardware.py, which asks it).

One fact is hers alone: how SHE is drawn. MoOS ARM sets LIBGL_ALWAYS_SOFTWARE=1,
GALLIUM_DRIVER=llvmpipe and QT_QUICK_BACKEND=software for every session
(/etc/environment.d/60-moos-arm-llvmpipe.conf), and /usr/bin/mira chooses Qt's software scene graph
itself where no real graphics device exists, exporting MIRA_STILL=1. Measured on the station on
2026-09-29, Mira at 1480x920 for 20 s in review mode:

  OpenGL through llvmpipe, ambient motion on    40.7 s of CPU
  OpenGL through llvmpipe, still                  3.7 s (start-up included)
  Qt's software scene graph, ambient motion on  22.0 s

An Oracle A1 has two cores. Qt's software scene graph also draws no ShaderEffect, and her aura,
face portal and nebula are shaders: there MiraCore, Avatar and Nebula draw the still face instead
(the face provider's portrait already cut to the portal's circle, `?round`) inside a static ring,
over a static glow. Nothing in that picture is meant to move.

The answer, strongest reason first:

  off      the owner turned animations off (AnimationDurationFactor=0). Nothing moves, and no
           Mira switch overrides it: transitions stop too (scale 0).
  still    Qt's software scene graph (QT_QUICK_BACKEND=software, or the launcher's MIRA_STILL=1):
           she is drawn as the still face there, so an ambient loop would only repaint it on the
           processor. No pin and no Mira switch turns the loop back on.
  (pin)    the owner pinned a tier with `moos-visual-tier --set`: that tier decides, even when
           OpenGL runs on the processor. It is his machine and his stated choice.
  still    OpenGL on Mesa's software rasterizer, or the essential tier: no ambient loop.
  reduced  the balanced tier: the same life, lighter.
  full     the flagship tier, or nothing is known.

`still` is about the ambient loop only (the breathing face, the drifting nebula). A transition
(a sheet sliding in, a colour blending to the next phase) still runs at `scale`, the owner's own
speed, at every level but `off`.

Every read is small, bounded and never raises; a file that is missing, unreadable or malformed
simply says nothing.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Optional

TIERS = ('essential', 'balanced', 'flagship')
LEVELS = ('off', 'still', 'reduced', 'full')
# moos-visual-tier's tiers and the `motion` word each profile records, in Mira's terms.
TIER_LEVEL = {'essential': 'still', 'balanced': 'reduced', 'flagship': 'full'}
MOTION_TIER = {'still': 'essential', 'gentle': 'balanced', 'alive': 'flagship'}
# The AnimationDurationFactor each tier writes (moos-visual-tier PROFILES), used as Mira's speed
# only when kdeglobals itself says nothing.
TIER_FACTOR = {'essential': 0.4, 'balanced': 0.85, 'flagship': 1.0}
STATE_FILE = 'moos-visual-tier.json'
PIN_FILE = 'moos-visual-tier'
_MAX_READ = 256 * 1024
_SOFTWARE_BACKENDS = ('software', 'softwarecontext')
_SOFTWARE_GALLIUM = ('llvmpipe', 'softpipe', 'swrast')

_TEXT = {
    'off': ('الحركة متوقفة لأنك أوقفت الحركات في إعدادات النظام.',
            'Motion is off because animations are off in System Settings.'),
    'pinned': ('ثبّتَّ طبقة العرض على «{tier}»، وميرا تتبع اختيارك.',
               'You pinned the visual tier to {tier}; Mira follows your choice.'),
    'software-scene-graph': ('ميرا ساكنة: تُرسم واجهتها هنا بلا تسريع رسومي.',
                             'Mira stays still: her window is drawn here without graphics acceleration.'),
    'software-renderer': ('ميرا ساكنة: هذا الكمبيوتر يرسم بلا معالج رسوميات، فكل حركة تكلّف المعالج.',
                          'Mira stays still: this computer draws without a GPU, so every frame costs the processor.'),
    'tier': ('طبقة العرض في هذا الجهاز «{tier}»، فميرا {level}.',
             "This machine's visual tier is {tier}, so Mira {level}."),
    'default': ('ميرا تتحرك بكامل حيويتها.', 'Mira moves fully.'),
}
# The tier names as moos-visual-tier itself says them («الطبقة: أساسية»).
_TIER_WORDS = {'essential': ('أساسية', 'essential'), 'balanced': ('متوازنة', 'balanced'),
               'flagship': ('قوية', 'flagship')}
_LEVEL_WORDS = {'still': ('تبقى ساكنة', 'stays still'), 'reduced': ('تتحرك بخفة', 'moves lightly'),
                'full': ('تتحرك بكامل حيويتها', 'moves fully'), 'off': ('لا تتحرك', 'does not move')}


@dataclass(frozen=True)
class Policy:
    level: str                  # off | still | reduced | full
    reason: str                 # off | software-scene-graph | pinned | software-renderer | tier | default
    tier: str = ''              # the MoOS tier that applies ('' when none is known)
    pinned: bool = False        # the tier came from the owner's `moos-visual-tier --set`
    factor: Optional[float] = None   # AnimationDurationFactor in effect (None when kdeglobals is silent)
    software: bool = False      # Mira is drawn on the processor in this session

    @property
    def owner_off(self) -> bool:
        """The owner's Plasma-wide 'animations off'. Nothing in Mira may turn motion back on."""
        return self.level == 'off'

    @property
    def still(self) -> bool:
        """Mira should run without her ambient loop (the breathing face, the drifting nebula)."""
        return self.level in ('off', 'still')

    @property
    def scale(self) -> float:
        """The speed of a transition: 0 when motion is off, else the owner's one control."""
        if self.level == 'off':
            return 0.0
        speed = self.factor if self.factor is not None else TIER_FACTOR.get(self.tier, 1.0)
        return round(min(8.0, max(0.05, speed)), 3)

    def explain(self, lang: str = 'ar') -> str:
        index = 1 if lang == 'en' else 0
        template = _TEXT[self.reason][index]
        tier = _TIER_WORDS.get(self.tier, ('', ''))[index]
        return template.format(tier=tier, level=_LEVEL_WORDS[self.level][index])

    def as_dict(self) -> dict:
        data = asdict(self)
        data.update(still=self.still, owner_off=self.owner_off, scale=self.scale)
        return data


# ── the readers ──────────────────────────────────────────────────────
def _read(path: Path) -> str:
    try:
        with open(path, 'rb') as handle:
            return handle.read(_MAX_READ).decode('utf-8', errors='replace')
    except (OSError, ValueError):
        return ''


def _home(env: Mapping[str, str], home: Optional[Path]) -> Path:
    if home is not None:
        return Path(home)
    try:
        return Path.home()
    except (KeyError, RuntimeError):
        return Path(env.get('HOME') or '/')


def _dir(env: Mapping[str, str], names: tuple, fallback: Path) -> Path:
    for name in names:
        value = (env.get(name) or '').strip()
        if value and os.path.isabs(value):
            return Path(value)
    return fallback


def _flag(value: Optional[str]) -> bool:
    """Mesa's reading of a boolean environment variable (env_var_as_boolean)."""
    return (value or '').strip().lower() in ('1', 'true', 'yes', 'y')


def software_scene_graph(env: Optional[Mapping[str, str]] = None) -> bool:
    """Is Qt Quick's software scene graph drawing Mira? It runs no ShaderEffect at all.

    QT_QUICK_BACKEND=software (every MoOS ARM session) or MIRA_STILL=1, which /usr/bin/mira exports
    whenever it leaves her on that scene graph, including when it chose it for a machine with no
    real graphics device.
    """
    env = os.environ if env is None else env
    if (env.get('QT_QUICK_BACKEND') or '').strip().lower() in _SOFTWARE_BACKENDS:
        return True
    return (env.get('MIRA_STILL') or '').strip() == '1'


def software_renderer(env: Optional[Mapping[str, str]] = None) -> bool:
    """Does this session draw Mira on the processor, by either road?

    Only what the session DECLARES about rendering: Qt's software scene graph, or Mesa told to use
    its software rasterizer for OpenGL. No hardware probing: that is moos-visual-tier's.
    """
    env = os.environ if env is None else env
    if software_scene_graph(env) or _flag(env.get('LIBGL_ALWAYS_SOFTWARE')):
        return True
    return (env.get('GALLIUM_DRIVER') or '').strip().lower() in _SOFTWARE_GALLIUM


_GROUP = re.compile(r'\[([^\]]*)\]')
_KEY = re.compile(r'([^\[\s=]+)((?:\[[^\]]*\])*)\s*')


def _kconfig_entry(paths: list, group: str, key: str) -> Optional[str]:
    """One KConfig value through an XDG cascade (paths highest priority first).

    Files are read lowest priority first so a higher one overrides a lower one, except that what a
    lower file marks immutable stays. [$i] on the key locks that entry. [$i] on the group header, or
    alone at the top of the file, locks the whole group as that file leaves it: every higher file's
    entries in it are ignored even when the locking file never sets the key (KConfig's kiosk rule).
    Localised variants (Key[ar]) are not the entry.
    """
    value = None
    for path in reversed(paths):
        text = _read(path)
        if not text:
            continue
        current, file_locked, group_locked, locked = None, False, False, False
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if line.startswith('['):
                names = _GROUP.findall(line)
                if current is None and names == ['$i']:
                    file_locked = True
                    continue
                group_locked = bool(names) and names[-1] == '$i'
                current = '/'.join(names[:-1] if group_locked else names)
                if current == group and (group_locked or file_locked):
                    locked = True
                continue
            if current != group or '=' not in line:
                continue
            name, _, raw_value = line.partition('=')
            match = _KEY.fullmatch(name)
            if not match or match.group(1) != key:
                continue
            options = _GROUP.findall(match.group(2))
            if any(not option.startswith('$') for option in options):
                continue          # Key[ar]: a translation, not the entry
            value = raw_value.strip()
            locked = locked or file_locked or group_locked or '$i' in options
        if locked:
            break
    return value


def animation_factor(env: Optional[Mapping[str, str]] = None, home: Optional[Path] = None) -> Optional[float]:
    """[KDE] AnimationDurationFactor as this session's KConfig resolves it, or None."""
    env = os.environ if env is None else env
    base = _home(env, home)
    config_home = _dir(env, ('XDG_CONFIG_HOME',), base / '.config')
    dirs = [Path(p) for p in (env.get('XDG_CONFIG_DIRS') or '/etc/xdg').split(':') if os.path.isabs(p)]
    raw = _kconfig_entry([config_home / 'kdeglobals', *(d / 'kdeglobals' for d in dirs)],
                         'KDE', 'AnimationDurationFactor')
    try:
        factor = float(raw) if raw is not None else None
    except ValueError:
        return None
    if factor is None or factor != factor or factor < 0 or factor == float('inf'):
        return None
    return factor


def pinned_tier(env: Optional[Mapping[str, str]] = None, home: Optional[Path] = None) -> str:
    """The tier the owner pinned with `moos-visual-tier --set`, or ''."""
    env = os.environ if env is None else env
    folder = _dir(env, ('MOOS_TIER_CONFIG_HOME', 'XDG_CONFIG_HOME'), _home(env, home) / '.config')
    value = _read(folder / PIN_FILE).strip()
    return value if value in TIERS else ''


def recorded_tier(env: Optional[Mapping[str, str]] = None, home: Optional[Path] = None) -> str:
    """The tier moos-visual-tier last applied in this account, or ''."""
    env = os.environ if env is None else env
    folder = _dir(env, ('MOOS_TIER_STATE_HOME', 'XDG_STATE_HOME'), _home(env, home) / '.local/state')
    try:
        state = json.loads(_read(folder / STATE_FILE) or 'null')
    except ValueError:
        return ''
    if not isinstance(state, dict):
        return ''
    tier = state.get('tier')
    if tier in TIERS:
        return tier
    # A record without a tier still names its profile's motion word.
    return MOTION_TIER.get(state.get('motion'), '')


# ── the answer ───────────────────────────────────────────────────────
def policy(env: Optional[Mapping[str, str]] = None, home: Optional[Path] = None) -> Policy:
    """How much Mira should move in this session (see the module text for the order)."""
    env = os.environ if env is None else env
    try:
        factor = animation_factor(env, home)
        scene_graph = software_scene_graph(env)
        software = software_renderer(env)
        pin = pinned_tier(env, home)
        tier = pin or recorded_tier(env, home)
    except Exception:            # a reader bug must never stop Mira from opening
        return Policy('full', 'default')
    if factor == 0:
        return Policy('off', 'off', tier, bool(pin), factor, software)
    if scene_graph:
        return Policy('still', 'software-scene-graph', tier, bool(pin), factor, True)
    if pin:
        return Policy(TIER_LEVEL[pin], 'pinned', pin, True, factor, software)
    if software:
        return Policy('still', 'software-renderer', tier, False, factor, True)
    if tier:
        return Policy(TIER_LEVEL[tier], 'tier', tier, False, factor, False)
    return Policy('full', 'default', '', False, factor, False)


def still(env: Optional[Mapping[str, str]] = None, home: Optional[Path] = None) -> bool:
    """True when Mira should run without her ambient loop on this machine."""
    return policy(env, home).still
