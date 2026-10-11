#!/usr/bin/env python3
"""Verify the reviewed vendor oomd policy on finished image bytes.

This is compose evidence, not pressure-recovery or runtime-monitoring evidence.
It refuses the ARM failure where systemd-oomd ran with zero monitored cgroups.
Do not replace vendor policy with a second MoOS set of thresholds.
"""
from __future__ import annotations

import argparse
import configparser
import os
from pathlib import Path


POLICIES = {
    'usr/lib/systemd/oomd.conf.d/10-oomd-defaults.conf':
        ('OOM', {'DefaultMemoryPressureDurationSec': '20s'}),
    'usr/lib/systemd/system/system.slice.d/10-oomd-per-slice-defaults.conf':
        ('Slice', {'ManagedOOMMemoryPressure': 'kill', 'ManagedOOMMemoryPressureLimit': '80%'}),
    'usr/lib/systemd/user/slice.d/10-oomd-per-slice-defaults.conf':
        ('Slice', {'ManagedOOMMemoryPressure': 'kill', 'ManagedOOMMemoryPressureLimit': '80%'}),
}


def verify(root: Path) -> None:
    for relative, (section, expected) in POLICIES.items():
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f'missing regular vendor memory policy: /{relative}')
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        parser.optionxform = str
        parser.read_string(path.read_text(encoding='utf-8'))
        for name, value in expected.items():
            if parser.get(section, name, fallback=None) != value:
                raise RuntimeError(f'unreviewed vendor memory policy: /{relative}: {name}')
    for relative in ('usr/lib/systemd/systemd-oomd', 'usr/lib/systemd/system/systemd-oomd.service'):
        if not (root / relative).is_file():
            raise RuntimeError(f'missing memory policy runtime: /{relative}')
    helper = root / 'usr/libexec/moos-memory-policy-check'
    if helper.is_symlink() or not helper.is_file() or not os.access(helper, os.X_OK):
        raise RuntimeError('missing executable native monitoring readback')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', type=Path, default=Path('/'))
    args = ap.parse_args()
    try:
        verify(args.root)
    except (OSError, ValueError, configparser.Error, RuntimeError) as exc:
        ap.exit(1, f'MoOS memory policy gate failed: {exc}\n')
    print('MoOS memory policy: system and user slice monitoring defaults present (80%, 20s); runtime proof still required')
