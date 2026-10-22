#!/usr/bin/env python3
"""Verify memory monitoring and the canonical TuneD/sysctl policy bridge.

This is compose evidence, not pressure-recovery or runtime-monitoring evidence.
It refuses the ARM failure where systemd-oomd ran with zero monitored cgroups.
Do not replace vendor policy with a second MoOS set of thresholds.
"""
from __future__ import annotations

import argparse
import configparser
import collections
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch


POLICIES = {
    'usr/lib/systemd/oomd.conf.d/10-oomd-defaults.conf':
        ('OOM', {'DefaultMemoryPressureDurationSec': '20s'}),
    'usr/lib/systemd/system/system.slice.d/10-oomd-per-slice-defaults.conf':
        ('Slice', {'ManagedOOMMemoryPressure': 'kill', 'ManagedOOMMemoryPressureLimit': '80%'}),
    'usr/lib/systemd/user/slice.d/10-oomd-per-slice-defaults.conf':
        ('Slice', {'ManagedOOMMemoryPressure': 'kill', 'ManagedOOMMemoryPressureLimit': '80%'}),
}

SYSCTL_POLICY = 'usr/lib/sysctl.d/90-moos-desktop.conf'
SYSCTL_ALIAS = 'etc/sysctl.d/90-moos-desktop.conf'
SYSCTL_LINK = '../../usr/lib/sysctl.d/90-moos-desktop.conf'
MEMORY = {'vm.swappiness': '150', 'vm.dirty_ratio': '10', 'vm.dirty_background_ratio': '5'}


def verify_sysctl_bridge(root: Path) -> None:
    source, alias = root / SYSCTL_POLICY, root / SYSCTL_ALIAS
    if source.is_symlink() or not source.is_file():
        raise RuntimeError('missing regular canonical desktop sysctl policy')
    if not alias.is_symlink() or os.readlink(alias) != SYSCTL_LINK:
        raise RuntimeError('missing canonical TuneD sysctl alias')
    if alias.resolve(strict=True) != source.resolve(strict=True):
        raise RuntimeError('TuneD sysctl alias does not resolve to the canonical policy')


def probe_native_tuned(policy: str) -> dict:
    """Use the installed parser with private files and intercepted kernel writes.

    TuneD reapplication searches run/etc, not the vendor sysctl directory. A
    second policy copy would drift; the relative alias keeps one authority.
    This does not switch profiles, contact D-Bus or write the running kernel.
    """
    import tuned.plugins.plugin_sysctl as native

    baseline = {'vm.swappiness': '10', 'vm.dirty_ratio': '40', 'vm.dirty_background_ratio': '10'}
    results = collections.OrderedDict()
    with tempfile.TemporaryDirectory(prefix='moos-tuned-policy-') as directory:
        root = Path(directory)
        source = root / SYSCTL_POLICY
        source.parent.mkdir(parents=True)
        source.write_text(policy)
        alias = root / SYSCTL_ALIAS
        alias.parent.mkdir(parents=True)
        runtime = root / 'run/sysctl.d'
        runtime.mkdir(parents=True)
        legacy = root / 'etc/sysctl.conf'
        legacy.write_text('')

        def evaluate(exclusions=()):
            plugin = native.SysctlPlugin.__new__(native.SysctlPlugin)
            plugin._variables = SimpleNamespace(expand=lambda value: value)
            plugin._global_cfg = SimpleNamespace(get_list=lambda *args: exclusions)
            state = dict(baseline)
            plugin._write_sysctl = lambda key, value, **kwargs: state.update({key: value})
            original = native.SysctlPlugin._apply_sysctl_config_file
            plugin._apply_sysctl_config_file = lambda path, instance, settings: original(
                plugin, str(legacy) if path == '/etc/sysctl.conf' else path, instance, settings)
            with patch.object(native, 'SYSCTL_CONFIG_DIRS', [str(runtime), str(alias.parent)]):
                plugin._apply_system_sysctl({'vm.swappiness': '10'})
            return {key: state[key] for key in MEMORY}

        def check(name, expected, exclusions=()):
            results[name] = evaluate(exclusions)
            if results[name] != expected:
                raise RuntimeError(f'native TuneD policy control failed: {name}: {results[name]}')

        check('vendor_only_old', baseline)
        alias.symlink_to(SYSCTL_LINK)
        check('canonical_alias', MEMORY)
        alias.unlink()
        alias.symlink_to('../../usr/lib/sysctl.d/missing.conf')
        check('broken_alias_negative', baseline)
        alias.unlink()
        alias.symlink_to(SYSCTL_LINK)
        administrator = alias.parent / '99-owner.conf'
        administrator.write_text('vm.swappiness=180\n')
        check('administrator_priority', dict(MEMORY, **{'vm.swappiness': '180'}))
        administrator.unlink()
        override = runtime / alias.name
        override.write_text('vm.swappiness=90\n')
        check('runtime_same_name_priority', dict(baseline, **{'vm.swappiness': '90'}))
        override.unlink()
        check('exclusion_preserved', dict(MEMORY, **{'vm.swappiness': '10'}), ('vm.swappiness',))
    return results


def verify_native_tuned(root: Path) -> dict | None:
    # The curated ARM/cloud base can legitimately omit TuneD. Do not install a
    # power daemon just to test a bridge it cannot consume. If any runtime
    # authority is present, an unavailable parser must remain a build failure.
    if not any((root / path).is_file() for path in (
            'usr/lib/systemd/system/tuned.service', 'usr/sbin/tuned', 'usr/bin/tuned')):
        return None
    return probe_native_tuned((root / SYSCTL_POLICY).read_text())


def verify(root: Path) -> None:
    verify_sysctl_bridge(root)
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
        native = None
        if args.root.resolve() == Path('/'):
            native = verify_native_tuned(args.root)
    except (OSError, ValueError, configparser.Error, RuntimeError, ImportError) as exc:
        ap.exit(1, f'MoOS memory policy gate failed: {exc}\n')
    print('MoOS memory policy: canonical TuneD alias and slice monitoring defaults present (80%, 20s)')
    if native is not None:
        print('Native TuneD parser: six controls passed; installed profile/cold proof remains separate')
    elif args.root.resolve() == Path('/'):
        print('TuneD runtime absent on this edition; canonical policy/alias checked, no daemon installed')
    else:
        print('Native TuneD parser not executed for a private root; installed profile/cold proof remains separate')
