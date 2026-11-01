#!/usr/bin/env python3
"""Bounded Flatpak host-font lifecycle, ownership, generations and refusals."""
import fcntl
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('flatpak_fonts', ROOT / 'system_files/usr/lib/moos/moos_flatpak_fonts.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)
APP = 'org.example.Editor'
RT = 'org.freedesktop.Platform/x86_64/26.08'


def deployment(value='a'):
    return {'booted': True, 'checksum': value * 64,
            'container-image-reference': 'ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos@sha256:' + value * 64}


class Inventory:
    def __init__(self):
        self.apps = {'user': [APP], 'system': []}
        self.runtimes = {'user': {RT: 'c' * 64}, 'system': {RT: 'd' * 64}}
        self.status = {'deployments': [dict(deployment('b'), booted=False), deployment()]}
        self.calls = []
        self.extra_rows = []

    def __call__(self, args):
        self.calls.append(args)
        if args[0] == '/usr/bin/rpm-ostree': return json.dumps(self.status)
        if args[1:] == ['list', '--columns=installation']: return 'user\nsystem'
        if args[1] == 'list':
            return '\n'.join([f'{app}\t{RT}\t{scope}' for scope, apps in self.apps.items()
                              for app in apps] + self.extra_rows)
        runtime = args[-1].removeprefix('runtime/')
        for scope in ('user', 'system'):
            if runtime in self.runtimes[scope]: return self.runtimes[scope][runtime]
        raise ValueError('runtime is not installed')


class FlatpakFonts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='moos-font-discovery-')
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.conf = self.home / '.var/app' / APP / 'config/fontconfig/conf.d'
        self.path = self.conf / policy.FILE
        self.a = policy.fragment('a' * 64, RT, 'c' * 64)
        self.b = policy.fragment('b' * 64, RT, 'c' * 64)

    def install(self, data=None, **kw):
        return policy.install(self.home, APP, data or self.a, **kw)

    def test_booted_signed_generation_ignores_stage_and_rollback(self):
        self.assertEqual(policy.signed_generation({'deployments': [dict(deployment('c'), booted=False),
                         deployment(), dict(deployment('b'), booted=False)]}), 'a' * 64)
        bad = [None, [], 'text', {}, {'deployments': {}}, {'deployments': []},
               {'deployments': [deployment(), deployment()]},
               {'deployments': [dict(deployment(), checksum=1)]},
               {'deployments': [dict(deployment(), **{'container-image-reference':
                   'ostree-unverified-registry:ghcr.io/moalfarras-sys/moos@sha256:' + 'a' * 64})]}]
        for document in bad:
            with self.subTest(document=document), self.assertRaises(ValueError): policy.signed_generation(document)

    def test_exact_existing_mono_scan_rules_and_policy_generation_upgrade(self):
        # The same native grid metadata belongs to both image and sandbox
        # caches; named-only pairing has its own separate assertions below.
        installed = ET.parse(ROOT / 'system_files/etc/fonts/conf.d/61-moos-brand.conf').getroot().findall('match')
        fragment = ET.fromstring(self.a)
        scans = fragment.findall('match')
        self.assertEqual(len(scans), 2)
        def fields(match):
            return (match.attrib, match.find('test').attrib, match.findtext('test/string'),
                    match.find('edit').attrib, match.findtext('edit/int'))
        self.assertEqual([fields(m) for m in scans], [fields(m) for m in installed])
        aliases = fragment.findall('alias')
        self.assertEqual(len(aliases), 2)
        for alias, primary, fallback in zip(aliases, ('Meyar Sans', 'Meyar Mono'), ('Meyar Arabic', 'Meyar Mono Arabic')):
            self.assertEqual(alias.attrib, {'binding': 'strong'})
            self.assertEqual(alias.findtext('family'), primary)
            self.assertEqual(alias.findtext('default/family'), fallback)
            self.assertIsNone(alias.find('prefer')); self.assertIsNone(alias.find('accept'))
        legacy = policy._render_fragment('a' * 64, [(RT, 'c' * 64)], 1)
        self.assertTrue(policy.owned(legacy))
        self.assertNotEqual(legacy.split(b'salt="')[1].split(b'"')[0], self.a.split(b'salt="')[1].split(b'"')[0])
        self.install(legacy)
        self.assertTrue(self.install())
        recovery = self.conf / '.moos-host-font-cache-recovery'
        self.assertEqual([p.read_bytes() for p in recovery.iterdir()], [legacy])
        self.assertFalse(policy.owned(legacy.replace(b'</fontconfig>', policy.SCAN_RULES + b'</fontconfig>')))
        # Scan bytes must change the cache generation even if someone forgets
        # a revision bump. An unknown revised body is never admitted as owned.
        with patch.object(policy, 'SCAN_RULES', policy.SCAN_RULES.replace(b'<int>100</int>', b'<int>90</int>')):
            changed = policy.fragment('a' * 64, RT, 'c' * 64)
            self.assertNotEqual(self.a.split(b'salt="')[1].split(b'"')[0], changed.split(b'salt="')[1].split(b'"')[0])
        self.assertFalse(policy.owned(changed))

    def test_new_update_idempotence_rollback_and_unique_recovery(self):
        self.assertTrue(self.install())
        self.assertEqual(self.path.read_bytes(), self.a)
        before = self.path.stat()
        self.assertFalse(self.install())
        self.assertEqual(self.path.stat(), before)
        personal = self.conf.parent / 'fonts.conf'
        personal.write_text('<fontconfig><!-- personal choice --></fontconfig>')
        self.assertTrue(self.install(self.b))
        self.assertTrue(self.install(self.a))
        recovery = self.conf / '.moos-host-font-cache-recovery'
        self.assertCountEqual([p.read_bytes() for p in recovery.iterdir()], [self.a, self.b])
        self.assertEqual(personal.read_text(), '<fontconfig><!-- personal choice --></fontconfig>')
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.conf.glob('.moos-host-font-cache-*')), [recovery])

    def test_actual_inventory_prepares_first_launch_and_preserves_personal_configs(self):
        inventory = Inventory()
        self.assertEqual(policy.refresh([APP], home=self.home, query=inventory), [APP])
        self.assertEqual(self.path.read_bytes(), self.a)
        self.assertEqual(policy.refresh([APP], home=self.home, query=inventory), [])
        self.assertFalse((self.home / '.var/app/org.example.Uninstalled').exists())
        with self.assertRaisesRegex(ValueError, 'not installed'):
            policy.refresh(['org.example.Uninstalled'], home=self.home, query=inventory)

    def test_system_app_uses_global_user_runtime_and_falls_back_to_system(self):
        inventory = Inventory()
        inventory.apps = {'user': [], 'system': [APP]}
        policy.refresh(home=self.home, query=inventory)
        self.assertEqual(self.path.read_bytes(), self.a)
        self.assertIn(['/usr/bin/flatpak', 'info', '--show-commit', 'runtime/' + RT], inventory.calls)
        self.assertFalse(any('--show-runtime' in call for call in inventory.calls))
        inventory.runtimes['user'] = {}
        policy.refresh(home=self.home, query=inventory)
        self.assertEqual(self.path.read_bytes(), policy.fragment('a' * 64, RT, 'd' * 64))
        self.assertIn(['/usr/bin/flatpak', 'info', '--show-commit', 'runtime/' + RT], inventory.calls)

    def test_duplicate_app_branches_and_runtime_update_refresh_generation(self):
        inventory = Inventory()
        inventory.apps['system'] = [APP]
        policy.refresh(home=self.home, query=inventory)
        self.assertEqual(inventory.calls.count(['/usr/bin/flatpak', 'info', '--show-commit', 'runtime/' + RT]), 1)
        inventory.runtimes['user'][RT] = 'e' * 64
        self.assertEqual(policy.refresh(home=self.home, query=inventory), [APP])
        self.assertEqual(self.path.read_bytes(), policy.fragment('a' * 64, RT, 'e' * 64))
        inventory.status['deployments'][1]['checksum'] = 'b' * 64
        self.assertEqual(policy.refresh(home=self.home, query=inventory), [APP])
        other = 'org.gnome.Platform/x86_64/51'
        inventory.extra_rows = [f'{APP}\t{other}\tsystem', f'{APP}\t{RT}\tuser']
        inventory.runtimes['system'][other] = 'f' * 64
        self.assertEqual(policy.refresh(home=self.home, query=inventory), [APP])
        expected = policy.runtime_fragment('b' * 64, [(RT, 'e' * 64), (other, 'f' * 64)])
        self.assertEqual(self.path.read_bytes(), expected)
        inventory.extra_rows.reverse()
        self.assertEqual(policy.refresh(home=self.home, query=inventory), [])
        self.assertEqual(policy.runtime_fragment('b' * 64, [(other, 'f' * 64), (RT, 'e' * 64), (RT, 'e' * 64)]), expected)

    def test_unavailable_or_unknown_inventory_refuses_before_home_writes(self):
        inventory = Inventory()
        inventory.runtimes = {'user': {}, 'system': {}}
        with self.assertRaisesRegex(ValueError, 'runtime is not installed'):
            policy.refresh(home=self.home, query=inventory)
        self.assertFalse((self.home / '.var').exists())
        def custom(args):
            return 'custom-owner-installation' if '--columns=installation' in args else inventory(args)
        with self.assertRaisesRegex(ValueError, 'custom Flatpak'):
            policy.refresh(home=self.home, query=custom)
        inventory.apps['user'] = ['../../escape']
        with self.assertRaisesRegex(ValueError, 'inventory'):
            policy.refresh(home=self.home, query=inventory)

    def test_no_app_incomplete_metadata_and_runtime_drift_preserve_prior_policy(self):
        inventory = Inventory()
        inventory.apps = {'user': [], 'system': []}
        self.assertEqual(policy.refresh(home=self.home, query=inventory), [])
        self.assertFalse(any(c[0] == '/usr/bin/rpm-ostree' for c in inventory.calls))
        self.assertFalse((self.home / '.var').exists())
        inventory.apps['user'] = [APP]
        policy.refresh(home=self.home, query=inventory)
        inventory.extra_rows = ['missing-fields']
        with self.assertRaisesRegex(ValueError, 'Incomplete'): policy.refresh(home=self.home, query=inventory)
        inventory.extra_rows = []
        inventory.runtimes['user'][RT] = 'not-a-commit'
        with self.assertRaisesRegex(ValueError, 'runtime commit'): policy.refresh(home=self.home, query=inventory)
        self.assertEqual(self.path.read_bytes(), self.a)

    def test_unknown_file_edit_and_hardlink_refuse(self):
        self.install()
        original_salt = self.a.split(b'salt="moos-host-v1-')[1][:64]
        salt_edited = self.a.replace(original_salt, b'e' * 64)
        self.assertFalse(policy.owned(salt_edited))
        nested_json = ('[' * 1200 + '0' + ']' * 1200).encode().hex().encode()
        nested = policy.PREFIX + nested_json + policy.MIDDLE + b'e' * 64 + policy.SUFFIX
        self.assertLess(len(nested), policy.MAX_FILE)
        self.assertFalse(policy.owned(nested))
        for data in (b'personal\n', self.a + b' ', b'x' * (policy.MAX_FILE + 1), salt_edited, nested):
            with self.subTest(data=data[:20]):
                self.path.write_bytes(data)
                with self.assertRaises(ValueError): self.install(self.b)
                self.assertEqual(self.path.read_bytes(), data)
        self.path.write_bytes(self.a)
        linked = self.home / 'retained'; os.link(self.path, linked)
        with self.assertRaises(ValueError): self.install(self.b)
        self.assertEqual(linked.read_bytes(), self.a)
        self.assertFalse((self.conf / '.moos-host-font-cache-recovery').exists())

    def test_each_path_ancestor_and_destination_refuses_links_and_mounts(self):
        self.install()
        outside = self.home / 'outside'; outside.mkdir()
        for target in [self.home / '.var', self.home / '.var/app', self.conf.parent.parent,
                       self.conf.parent, self.conf]:
            with self.subTest(path=target):
                saved = target.with_name(target.name + '-saved')
                target.rename(saved); target.symlink_to(outside, target_is_directory=True)
                try:
                    with self.assertRaises(OSError): self.install(self.b)
                finally: target.unlink(); saved.rename(target)
                with self.assertRaisesRegex(ValueError, 'mounted'):
                    self.install(self.b, mounts={str(target)})
        for target in (self.path, self.conf / '.moos-host-font-cache.lock'):
            original = target.read_bytes(); target.unlink(); target.symlink_to(self.home / 'foreign')
            with self.assertRaises(OSError): self.install(self.b)
            target.unlink(); target.write_bytes(original)
            with self.assertRaisesRegex(ValueError, 'mounted'):
                self.install(self.b, mounts={str(target)})
        self.assertFalse((self.home / 'foreign').exists())

    def test_unknown_recovery_link_mount_lock_busy_and_permissions_refuse(self):
        self.install()
        recovery = self.conf / '.moos-host-font-cache-recovery'
        recovery.symlink_to(self.home, target_is_directory=True)
        with self.assertRaises(OSError): self.install(self.b)
        recovery.unlink()
        with self.assertRaisesRegex(ValueError, 'mounted'):
            self.install(self.b, mounts={str(recovery)})
        lock = self.conf / '.moos-host-font-cache.lock'
        lock.write_text('personal lock')
        with self.assertRaisesRegex(ValueError, 'unknown.*lock'): self.install(self.b)
        lock.write_bytes(policy.LOCK)
        with lock.open('r+') as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): self.install(self.b)
        self.conf.chmod(0o777)
        with self.assertRaises(ValueError): self.install(self.b)
        self.conf.chmod(0o700)
        with patch.object(policy.os, 'getuid', return_value=os.getuid() + 1):
            with self.assertRaises(ValueError): self.install(self.b)
        self.assertEqual(self.path.read_bytes(), self.a)

    def test_explicit_predecessor_retirement_keeps_exact_recovery_and_caches(self):
        inventory = Inventory()
        self.assertEqual(policy.refresh(home=self.home, query=inventory, retire=True), [])
        self.assertFalse((self.home / '.var').exists())
        policy.refresh(home=self.home, query=inventory)
        cache = self.home / '.var/app' / APP / 'cache/fontconfig'
        cache.mkdir(parents=True); (cache / 'retained.cache-12').write_bytes(b'cache sentinel')
        self.assertEqual(policy.refresh(home=self.home, query=inventory, retire=True), [APP])
        self.assertFalse(self.path.exists())
        self.assertEqual([p.read_bytes() for p in (self.conf / '.moos-host-font-cache-recovery').iterdir()], [self.a])
        self.assertEqual((cache / 'retained.cache-12').read_bytes(), b'cache sentinel')
        self.assertEqual(policy.refresh(home=self.home, query=inventory, retire=True), [])
        self.path.write_bytes(b'personal edit')
        with self.assertRaisesRegex(ValueError, 'edited'): policy.refresh(home=self.home, query=inventory, retire=True)
        self.assertEqual(self.path.read_bytes(), b'personal edit')

    def test_store_failure_is_visible_after_successful_package_transaction(self):
        loader = importlib.machinery.SourceFileLoader('font_store_test', str(ROOT / 'system_files/usr/bin/moos-storectl'))
        import sys
        store = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
        sys.modules[loader.name] = store; loader.exec_module(store)
        errors = []
        events = type('Events', (), {'requested': [APP], 'error': staticmethod(lambda app, msg: errors.append((app, msg)))})()
        with patch('importlib.import_module', return_value=policy), patch.object(policy, 'refresh', side_effect=ValueError('edited fragment')):
            with self.assertRaisesRegex(store.StoreError, 'Applications are retained'):
                store.FlatpakAdapter._refresh_fonts(events)
        self.assertEqual(errors[0][0], APP)
        self.assertIn('edited fragment', errors[0][1])

        order = []
        adapter = object.__new__(store.FlatpakAdapter)
        transaction = type('Transaction', (), {'add_update': staticmethod(lambda *args: order.append('runtime-update') or True)})()
        adapter._transaction = lambda configure, _events, _cancel: configure(transaction)
        adapter._refresh_fonts = lambda _events: order.append('font-discovery')
        adapter.update_many([('org.freedesktop.Platform', 'runtime/' + RT)], events, lambda: False)
        self.assertEqual(order, ['runtime-update', 'font-discovery'])


if __name__ == '__main__': unittest.main(verbosity=2)
