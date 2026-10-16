"""Read effective native desktop launchers; never infer ownership from an executable name.

Mo Store may open these through the same desktop service as the menu. Image-owned
apps stay owned by MoOS, and untracked user apps remain explicit external installs.
Their presence never authorizes deleting arbitrary executable/configuration paths.
"""
from __future__ import annotations
import configparser
import os
from pathlib import Path
import re
import shutil
import shlex
from functools import lru_cache

PREFIX = 'native.'
ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,235}\.desktop$')
MARKERS = ('X-Flatpak', 'X-MoOS-AppDrop', 'X-MoOS-WebApp', 'X-MoOS-Windows', 'X-MoOS-Vendor')

def application_dirs() -> list[Path]:
    home = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    roots = [home, *[Path(p) for p in os.environ.get('XDG_DATA_DIRS', '/usr/local/share:/usr/share').split(':') if p.startswith('/')]]
    return list(dict.fromkeys(p / 'applications' for p in roots))

@lru_cache(maxsize=256)
def theme_icon(name: str, roots: tuple[Path, ...]) -> str:
    for root in roots:
        for theme in ('hicolor', 'breeze', 'breeze-dark'):
            for size in ('128x128', '256x256', '64x64', '48x48', 'scalable', '48'):
                for suffix in ('.png', '.svg'):
                    candidate = root.parent / 'icons' / theme / size / 'apps' / (name + suffix)
                    if candidate.is_file(): return candidate.as_uri()
                    candidate = root.parent / 'icons' / theme / 'apps' / size / (name + suffix)
                    if candidate.is_file(): return candidate.as_uri()
    return ''

def inventory(roots: list[Path] | None = None, language: str | None = None) -> list[dict]:
    roots = application_dirs() if roots is None else roots
    locale = (language or os.environ.get('LANGUAGE') or os.environ.get('LANG') or 'en').split(':')[0].split('.')[0]
    langs = list(dict.fromkeys([locale, locale.split('_')[0], 'en']))
    desktop = set((os.environ.get('XDG_CURRENT_DESKTOP') or 'KDE').split(':'))
    seen: set[str] = set()
    result = []
    for root in roots:
        try: files = sorted(root.glob('*.desktop'))
        except OSError: continue
        for path in files:
            filename = path.name
            if not ID.fullmatch(filename) or filename in seen: continue
            seen.add(filename)  # Hidden/invalid stronger entries also mask the lower copy.
            try:
                if not path.is_file() or path.stat().st_size > 256 * 1024: continue
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                parser.optionxform = str
                parser.read_string(path.read_text(encoding='utf-8'))
                entry = parser['Desktop Entry']
                if entry.get('Type') != 'Application' or not entry.get('Exec', '').strip(): continue
                if any(entry.get(k, '').lower() == 'true' for k in ('Hidden', 'NoDisplay')): continue
                if any(entry.get(k, '') for k in MARKERS): continue
                only = set(filter(None, entry.get('OnlyShowIn', '').split(';')))
                never = set(filter(None, entry.get('NotShowIn', '').split(';')))
                if only and not only.intersection(desktop) or never.intersection(desktop): continue
                probe = entry.get('TryExec', '')
                if probe and not (shutil.which(probe) or Path(probe).is_absolute() and os.access(probe, os.X_OK)): continue
                def text(key):
                    value = next((entry.get(f'{key}[{lang}]') for lang in langs if entry.get(f'{key}[{lang}]')), entry.get(key, ''))
                    return ''.join(c for c in value if c >= ' ' and c != '\x7f')[:500]
                command = shlex.split(entry.get('Exec', ''))
                provided = ''
                if len(command) >= 4 and Path(command[0]).name == 'waydroid' and command[1:3] == ['app', 'launch']:
                    provided = command[3]
                name = text('Name')
                if not name: continue
                user = root == roots[0] and root == application_dirs()[0]
                icon = entry.get('Icon', '')
                if Path(icon).is_absolute(): icon = Path(icon).as_uri() if Path(icon).is_file() else ''
                elif re.fullmatch(r'[A-Za-z0-9._+-]+', icon): icon = theme_icon(icon, tuple(roots))
                else: icon = ''
                result.append({'id': PREFIX + filename[:-8], 'desktop_id': filename,
                    'kind': 'native', 'source': 'native', 'provided_id': provided, 'name': name,
                    'name_en': entry.get('Name[en]', entry.get('Name', name)),
                    'summary': text('Comment') or text('GenericName'), 'description': text('Comment'),
                    'developer': '', 'icon': icon, 'installed': True, 'listed': False,
                    'installable': False, 'curated': False, 'verified': False, 'version': '',
                    'installed_version': None, 'update_available': False, 'eol': False,
                    'management': 'external' if user else 'os', 'installed_scope': 'user' if user else 'system',
                    'categories': list(filter(None, entry.get('Categories', '').split(';'))), 'cat': 'util'})
            except (OSError, UnicodeError, configparser.Error, KeyError, ValueError): continue
    return result

def find(app_id: str) -> dict | None:
    if not app_id.startswith(PREFIX): return None
    return next((a for a in inventory() if a['id'] == app_id), None)
