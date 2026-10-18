#!/usr/bin/env python3
"""Prove that both scheduled application updaters exist and are wired."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

TIMER_KEYS = {'OnActiveSec', 'OnBootSec', 'OnStartupSec', 'OnUnitActiveSec',
              'OnUnitInactiveSec', 'OnCalendar'}
LIST_KEYS = TIMER_KEYS | {'ExecStart', 'ExecCondition', 'WantedBy'}
# Exact reviewed condition: a second false condition can stop every update,
# and a comment containing the property name does not enforce network policy.
METERED_CONDITION = (
    '/bin/bash -c \'metered="$(busctl --timeout=5s get-property '
    'org.freedesktop.NetworkManager /org/freedesktop/NetworkManager '
    'org.freedesktop.NetworkManager Metered)" && '
    '[[ "$metered" == "u 2" || "$metered" == "u 4" ]]\''
)


def configuration(root: Path, scope: str, name: str) -> dict[tuple[str, str], list[str]]:
    directories = [root / prefix / 'systemd' / scope
                   for prefix in ('usr/lib', 'usr/local/lib', 'run', 'etc')]
    bases = [directory / name for directory in directories
             if os.path.lexists(directory / name)]
    if not bases or not bases[-1].is_file():
        raise RuntimeError(f'missing or masked {scope} unit: {name}')
    dropins: dict[str, Path] = {}
    for directory in directories:
        for path in (directory / (name + '.d')).glob('*.conf'):
            dropins[path.name] = path
    values: dict[tuple[str, str], list[str]] = {}
    for path in [bases[-1], *(dropins[key] for key in sorted(dropins))]:
        section = ''
        for raw in path.read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith(('#', ';')):
                continue
            if line.endswith('\\'):
                raise RuntimeError(f'unreviewed multiline app-update setting: {path}')
            if line.startswith('[') and line.endswith(']'):
                section = line[1:-1]
                continue
            key, sep, value = line.partition('=')
            if not sep:
                raise RuntimeError(f'invalid app-update setting: {path}')
            key, value = key.strip(), value.strip()
            if section == 'Timer' and key in TIMER_KEYS and not value:
                for timer_key in TIMER_KEYS:
                    values[(section, timer_key)] = []
            elif key in LIST_KEYS:
                if value:
                    values.setdefault((section, key), []).append(value)
                else:
                    values[(section, key)] = []
            else:
                values[(section, key)] = [value]
    return values


def verify(root: Path) -> None:
    root = root.resolve()
    helper = root / 'usr/libexec/moos-flatpak-update'
    if not helper.is_file() or not os.access(helper, os.X_OK):
        raise RuntimeError('missing executable application-update helper')
    for relative in ('usr/bin/flatpak', 'usr/bin/busctl', 'usr/bin/bash'):
        provider = root / relative
        if not provider.is_file() or not os.access(provider, os.X_OK):
            raise RuntimeError(f'missing executable app-update provider: /{relative}')
    for scope, delay in [('system', '30min'), ('user', '25min')]:
        name = f'flatpak-{scope}-update'
        service = configuration(root, scope, name + '.service')
        expected = {'Type': 'oneshot', 'ExecStart': f'/usr/libexec/moos-flatpak-update --{scope}',
                    'Nice': '19', 'CPUSchedulingPolicy': 'idle', 'IOSchedulingClass': 'idle'}
        for key, value in expected.items():
            if service.get(('Service', key)) != [value]:
                raise RuntimeError(f'{scope} updater lost {key}={value}')
        conditions = service.get(('Service', 'ExecCondition'), [])
        if conditions != [METERED_CONDITION]:
            raise RuntimeError(f'{scope} updater changed its reviewed metered-network condition')
        timer = configuration(root, scope, name + '.timer')
        if timer.get(('Timer', 'Unit'), [name + '.service']) != [name + '.service']:
            raise RuntimeError(f'{scope} timer targets another update service')
        expected_timers = {'OnBootSec': [delay], 'OnCalendar': ['*-*-* 4:00:00']}
        for key in TIMER_KEYS:
            if timer.get(('Timer', key), []) != expected_timers.get(key, []):
                raise RuntimeError(f'{scope} updater has an unreviewed {key} schedule')
        if 'timers.target' not in timer.get(('Install', 'WantedBy'), []):
            raise RuntimeError(f'{scope} updater has no timers.target installation')
        if scope == 'system' and timer.get(('Timer', 'Persistent')) != ['false']:
            raise RuntimeError('system application updates could catch up during boot')
        link = root / 'etc/systemd' / scope / 'timers.target.wants' / (name + '.timer')
        if not link.is_symlink():
            raise RuntimeError(f'{scope} application-update timer is not enabled')
        raw = Path(os.readlink(link))
        target = root / raw.relative_to('/') if raw.is_absolute() else link.parent / raw
        unit = root / 'usr/lib/systemd' / scope / (name + '.timer')
        if target.resolve() != unit.resolve() or not unit.is_file():
            raise RuntimeError(f'{scope} application-update want targets another unit')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/'))
    options = parser.parse_args()
    try:
        verify(options.root)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f'MoOS app-update gate failed: {error}\n')
    print('MoOS app updates: both scopes exist, are enabled and retain delayed idle scheduling')
