#!/usr/bin/env python3
"""Native Store result bits, without an owner installation or app transaction."""
from pathlib import Path
import importlib.machinery
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import warnings

if __name__ == '__main__' and '--private-profile' not in sys.argv:
    # Import GI and the Store only in the child: GLib caches HOME/XDG paths.
    # No owner bus, desktop, personal Flatpak installation or logs are inherited.
    with tempfile.TemporaryDirectory(prefix='moos-flatpak-signal-profile-') as temporary:
        home = Path(temporary)
        for name in ('config', 'data', 'cache', 'state', 'runtime'):
            (home/name).mkdir(mode=0o700)
        env = {key: value for key, value in os.environ.items()
               if key in ('PATH', 'LANG', 'LC_ALL', 'LANGUAGE')}
        env.update(HOME=str(home), XDG_CONFIG_HOME=str(home/'config'),
                   XDG_DATA_HOME=str(home/'data'), XDG_CACHE_HOME=str(home/'cache'),
                   XDG_STATE_HOME=str(home/'state'), XDG_RUNTIME_DIR=str(home/'runtime'),
                   XDG_CONFIG_DIRS=str(home/'config'),
                   DBUS_SESSION_BUS_ADDRESS='unix:path='+str(home/'no-session-bus'),
                   DBUS_SYSTEM_BUS_ADDRESS='unix:path='+str(home/'no-system-bus'))
        result = subprocess.run([sys.executable, '-B', '-s', str(Path(__file__).resolve()),
                                 *sys.argv[1:], '--private-profile'], env=env)
    raise SystemExit(result.returncode)
if '--private-profile' in sys.argv:
    sys.argv.remove('--private-profile')

INSTALLED = '--installed' in sys.argv
if INSTALLED:
    sys.argv.remove('--installed')
ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/usr/bin/moos-storectl') if INSTALLED else ROOT/'system_files/usr/bin/moos-storectl'
loader = importlib.machinery.SourceFileLoader('moos_store_native_signals', str(SOURCE))
spec = importlib.util.spec_from_loader(loader.name, loader)
store = importlib.util.module_from_spec(spec)
sys.modules[loader.name] = store
loader.exec_module(store)
try:
    import gi
    gi.require_version('Flatpak', '1.0')
    from gi.repository import Flatpak, Gio, GLib, GObject
    NATIVE = True
except (ImportError, ValueError):
    NATIVE = False


class Initialization(unittest.TestCase):
    def test_private_child_preserves_no_bytecode_and_no_user_site(self):
        self.assertTrue(sys.dont_write_bytecode)
        self.assertTrue(sys.flags.no_user_site)

    def test_a_false_initializer_never_returns_a_transaction(self):
        class Base:
            def __init__(self, installation):
                self.installation = installation
        api = SimpleNamespace(Transaction=Base)
        gio = SimpleNamespace(Initable=SimpleNamespace(init=lambda tx, cancel: False))
        with self.assertRaises(store.StoreError):
            store.new_native_flatpak_transaction(api, gio, object(), None, None, None)

    def test_an_initializer_exception_is_not_turned_into_success(self):
        class Base:
            def __init__(self, installation):
                self.installation = installation
        def refused(tx, cancel):
            raise RuntimeError('private initializer refusal')
        api = SimpleNamespace(Transaction=Base)
        gio = SimpleNamespace(Initable=SimpleNamespace(init=refused))
        with self.assertRaisesRegex(RuntimeError, 'private initializer refusal'):
            store.new_native_flatpak_transaction(api, gio, object(), None, None, None)


@unittest.skipUnless(NATIVE, 'native libflatpak GI unavailable on this source-only runner')
class NativeSignals(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='moos-store-native-signals-')
        self.addCleanup(temporary.cleanup)
        self.installation = Flatpak.Installation.new_for_path(
            Gio.File.new_for_path(str(Path(temporary.name)/'repo')), True, None)
        # These controlled signals carry an operation object but never access
        # uninitialized operation payloads or execute a package transaction.
        self.operation = GObject.new(Flatpak.TransactionOperation)
        self.error = GLib.Error('private signal control', 'moos-proof', 1)

    def transaction(self, done, error):
        return store.new_native_flatpak_transaction(
            Flatpak, Gio, self.installation, Gio.Cancellable(), done, error)

    def test_old_connected_handlers_report_the_actual_native_control(self):
        transaction = Flatpak.Transaction.new_for_installation(self.installation, None)
        received = []
        transaction.connect('operation-done', lambda tx, op, commit, bits: received.append(int(bits)))
        transaction.connect('operation-error', lambda tx, op, error, bits: received.append(int(bits)) or False)
        rows = []
        for signal in ('operation-done', 'operation-error'):
            for sent in (0, 1, 3):
                args = (self.operation, '0'*64, sent) if signal == 'operation-done' else (self.operation, self.error, sent)
                with warnings.catch_warnings(record=True) as captured:
                    warnings.simplefilter('always')
                    transaction.emit(signal, *args)
                rows.append({'signal': signal, 'sent': sent, 'received': received[-1],
                             'warnings': [str(row.message) for row in captured]})
        healthy = all(row['sent'] == row['received'] and not row['warnings'] for row in rows)
        refused = all(row['received'] == 0 and any('G_VALUE_HOLDS_FLAGS' in text for text in row['warnings']) for row in rows)
        self.assertTrue(healthy or refused, json.dumps(rows))
        # A future vendor fix is a retained no-repro, never a reason to invent
        # a failing old control or reject a healthy native provider.
        print(('MOOS_NATIVE_FLATPAK_OLD_NO_REPRO ' if healthy else 'MOOS_NATIVE_FLATPAK_OLD_REFUSAL ')
              + json.dumps(rows), flush=True)

    def test_virtual_handlers_preserve_results_and_error_policy_without_warnings(self):
        done = []
        errors = []
        cancelled = False
        def on_error(tx, operation, error, bits):
            errors.append(int(bits))
            return store.continue_after_transaction_error(int(bits), 1, cancelled)
        transaction = self.transaction(lambda tx, operation, commit, bits: done.append(int(bits)), on_error)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            for bits in (0, 1, 3):
                transaction.emit('operation-done', self.operation, '0'*64, bits)
                self.assertEqual(transaction.emit('operation-error', self.operation, self.error, bits), bool(bits & 1))
            cancelled = True
            for bits in (0, 1, 3):
                self.assertFalse(transaction.emit('operation-error', self.operation, self.error, bits))
        self.assertEqual(done, [0, 1, 3])
        self.assertEqual(errors, [0, 1, 3, 0, 1, 3])
        self.assertEqual([str(row.message) for row in captured], [])

    def test_each_native_transaction_keeps_its_own_callbacks(self):
        first, second = [], []
        a = self.transaction(lambda tx, op, commit, bits: first.append(int(bits)), lambda *args: False)
        b = self.transaction(lambda tx, op, commit, bits: second.append(int(bits)), lambda *args: False)
        self.assertIs(type(a), type(b))
        a.emit('operation-done', self.operation, None, 3)
        b.emit('operation-done', self.operation, None, 1)
        self.assertEqual(first, [3])
        self.assertEqual(second, [1])

    def test_initialized_subtype_reaches_real_native_ready_and_run(self):
        ready = []
        transaction = self.transaction(lambda *args: None, lambda *args: False)
        transaction.set_no_interaction(True)
        def on_ready(tx):
            ready.append(len(tx.get_operations()))
            return True
        transaction.connect('ready', on_ready)
        self.assertTrue(transaction.run(None))
        self.assertEqual(ready, [0])  # constructor/run proof, not app acceptance
        print('MOOS_NATIVE_FLATPAK_SUBTYPE_RUN_PASS', flush=True)


if __name__ == '__main__':
    if (INSTALLED or Path('/usr/lib/moos/edition').is_file()) and not NATIVE:
        raise SystemExit('Native libflatpak proof dependencies are required on MoOS.')
    result = unittest.main(verbosity=2, exit=False).result
    if INSTALLED and (result.skipped or result.testsRun != 7):
        raise SystemExit('Installed transaction proof must execute every native case.')
    if INSTALLED and result.wasSuccessful():
        print('MOOS_IMAGE_FLATPAK_TRANSACTION_PASS')
    raise SystemExit(0 if result.wasSuccessful() else 1)
