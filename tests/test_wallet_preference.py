#!/usr/bin/env python3
"""Wallet preferences use native KConfig and providers; no owner bus or secrets."""
from pathlib import Path
import fcntl
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

INSTALLED = "--installed" in sys.argv
if INSTALLED: sys.argv.remove("--installed")
ROOT = Path(__file__).resolve().parents[1]
SYS = Path("/") if INSTALLED else ROOT/"system_files"
DEFAULTS = SYS/"etc/xdg"
spec = importlib.util.spec_from_file_location("wallet", SYS/"usr/lib/moos/moos_wallet.py")
wallet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wallet)

KCONFIG = all(shutil.which(tool) for tool in ("kreadconfig6", "kwriteconfig6"))

@unittest.skipUnless(KCONFIG, "native KConfig unavailable on this source-only runner")
class Preference(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="moos-wallet-test-")
        self.addCleanup(self.tmp.cleanup)
        self.config = Path(self.tmp.name)
        self.target = self.config/"kwalletrc"
        for name in ("home", "data", "cache", "state", "runtime"):
            (self.config/name).mkdir(mode=0o700)
        env = patch.dict(os.environ, {"HOME": str(self.config/"home"),
            "XDG_CONFIG_HOME": str(self.config), "XDG_CONFIG_DIRS": str(DEFAULTS),
            "XDG_DATA_HOME": str(self.config/"data"), "XDG_CACHE_HOME": str(self.config/"cache"),
            "XDG_STATE_HOME": str(self.config/"state"), "XDG_RUNTIME_DIR": str(self.config/"runtime")})
        env.start(); self.addCleanup(env.stop)
        mock = patch.object(wallet, "owned_processes", return_value={})
        mock.start(); self.addCleanup(mock.stop)
        mock = patch.object(wallet, "names", return_value=set())
        mock.start(); self.addCleanup(mock.stop)

    def test_off_preserves_unrelated_preferences_and_encrypted_data(self):
        self.target.write_text("[Custom]\nName=مستخدم\n[Wallet]\nEnabled=true\n")
        data = self.config/"encrypted-wallet.kwl"
        data.write_bytes(b"private-sentinel")
        result = wallet.change("off")
        self.assertTrue(result["known"])
        self.assertFalse(result["enabled"])
        self.assertEqual(result["choice"], "off")
        self.assertIn("Name=مستخدم", self.target.read_text())
        self.assertEqual(data.read_bytes(), b"private-sentinel")
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        before = self.target.read_bytes()
        wallet.change("off")
        self.assertEqual(self.target.read_bytes(), before)

    def test_symlink_hardlink_fifo_and_large_input_remain_untouched(self):
        sentinel = self.config/"keep"
        sentinel.write_bytes(b"keep")
        for kind in ("symlink", "hardlink", "fifo", "large"):
            with self.subTest(kind=kind):
                if kind == "symlink": self.target.symlink_to(sentinel)
                elif kind == "hardlink": os.link(sentinel, self.target)
                elif kind == "fifo": os.mkfifo(self.target)
                else: self.target.write_bytes(b"x"*(256*1024+1))
                with self.assertRaises(wallet.WalletError): wallet.change("off")
                self.assertEqual(sentinel.read_bytes(), b"keep")
                self.target.unlink()

    def test_foreign_provider_refusal_precedes_any_write(self):
        self.target.write_bytes(b"[Wallet]\nEnabled=true\n")
        before = self.target.read_bytes()
        with patch.object(wallet, "owned_processes", side_effect=wallet.WalletError("foreign")):
            with self.assertRaises(wallet.WalletError): wallet.change("off")
        self.assertEqual(self.target.read_bytes(), before)

    def test_silent_writer_and_concurrent_edit_are_refused(self):
        self.target.write_bytes(b"[Wallet]\nEnabled=true\n")
        before = self.target.read_bytes()
        real = wallet.command
        def silent(argv):
            return "" if argv[0] == "kwriteconfig6" else real(argv)
        with patch.object(wallet, "command", side_effect=silent):
            with self.assertRaises(wallet.WalletError): wallet.change("off")
        self.assertEqual(self.target.read_bytes(), before)
        def edit(argv):
            if argv[0] == "kwriteconfig6": self.target.write_bytes(b"[Concurrent]\nKeep=true\n")
            return real(argv)
        with patch.object(wallet, "command", side_effect=edit):
            with self.assertRaises(wallet.WalletError): wallet.change("off")
        self.assertEqual(self.target.read_bytes(), b"[Concurrent]\nKeep=true\n")

    def test_failed_activation_restores_prior_preference(self):
        self.target.write_bytes(b"[Custom]\nKeep=true\n")
        before = self.target.read_bytes()
        with patch.object(wallet, "bus", side_effect=wallet.WalletError("activation refused")):
            with self.assertRaises(wallet.WalletError): wallet.change("on")
        self.assertEqual(self.target.read_bytes(), before)

    def test_another_change_and_foreign_lock_remain_untouched(self):
        lock = self.config/".moos-wallet.lock"
        with lock.open("w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(wallet.WalletError): wallet.change("off")
            self.assertFalse(self.target.exists())
        lock.unlink(); lock.symlink_to(self.config/"sentinel")
        with self.assertRaises(wallet.WalletError): wallet.change("off")
        self.assertTrue(lock.is_symlink())

    def test_a_preference_edit_during_collection_save_is_preserved(self):
        self.target.write_bytes(b"[Wallet]\nEnabled=true\n")
        def edit(_): self.target.write_bytes(b"[Concurrent]\nKeep=true\n")
        with patch.object(wallet,"save_and_lock",side_effect=edit):
            with self.assertRaises(wallet.WalletError): wallet.change("off")
        self.assertEqual(self.target.read_bytes(), b"[Concurrent]\nKeep=true\n")

    def test_collection_save_failure_refuses_termination_and_preference_write(self):
        self.target.write_bytes(b"[Wallet]\nEnabled=true\n")
        before = self.target.read_bytes()
        with patch.object(wallet, "save_and_lock", side_effect=wallet.WalletError("save refused")), patch.object(wallet, "stop") as stop:
            with self.assertRaises(wallet.WalletError): wallet.change("off")
            stop.assert_not_called()
        self.assertEqual(self.target.read_bytes(), before)

    def test_collection_lock_precedes_provider_shutdown_and_does_not_read_items(self):
        collection = "/org/freedesktop/secrets/collection/test"
        replies = [json.dumps({"type":"ao","data":[collection]}),
                   json.dumps({"type":"b","data":False}),
                   json.dumps({"type":"aoo","data":[[collection],"/"]})]
        with patch.object(wallet, "names", return_value={"org.freedesktop.secrets"}), patch.object(wallet, "bus", side_effect=[":1.2",123]), patch.object(wallet, "command", side_effect=replies) as call:
            wallet.save_and_lock({123:4})
            self.assertEqual(call.call_args_list[-1].args[0][-4:], ["Lock","ao","1",collection])
            self.assertFalse(any("GetSecret" in str(c) or "GetItems" in str(c) for c in call.call_args_list))


ORIGINAL_OWNERS = wallet.owned_processes

class BusSafety(unittest.TestCase):
    def test_bad_bus_shape_and_foreign_pid_never_receive_a_signal(self):
        with patch.object(wallet, "command", return_value='{"data": []}'):
            with self.assertRaises(wallet.WalletError): wallet.bus("ListNames")
        # Test the actual identity checker, not setUp's provider stand-in.
        with patch.object(wallet, "names", return_value={"org.freedesktop.secrets"}), patch.object(wallet, "bus", side_effect=[":1.9", 1, os.getuid()]), patch("signal.pidfd_send_signal") as send:
            with self.assertRaises(wallet.WalletError): ORIGINAL_OWNERS()
            send.assert_not_called()


class HealthPreference(unittest.TestCase):
    def test_explicit_on_off_unknown_and_contradictory_live_states(self):
        source=(SYS/"usr/bin/moos-selfcheck").read_text()
        section=source.split("# ── The wallet policy",1)[1].split("# ── The MoOS Store",1)[0]
        section=section[section.index('head_ '):]
        with tempfile.TemporaryDirectory(prefix="moos-wallet-health-") as temp:
            root=Path(temp)
            (root/"check").write_text('head_() { :; }; ok() { echo "PASS $*"; }; bad() { echo "FAIL $*"; exit 13; };\n'+section)
            (root/"moos-control").write_text('#!/bin/sh\nprintf "%s" "$WALLET_STATUS"\n')
            (root/"gdbus").write_text('#!/bin/sh\nprintf "%s" "$WALLET_NAMES"\n')
            for n in ("moos-control","gdbus"): (root/n).chmod(0o700)
            base={"known":True,"available":True,"enabled":False,"active":False,"ready":False,"choice":"off"}
            cases=[(base,"",0), (base,"org.freedesktop.secrets",13),
                   (dict(base,enabled=True,active=True,ready=True,choice="on"),"org.freedesktop.secrets",0),
                   (dict(base,enabled=True,choice="on"),"",13),
                   (dict(base,enabled=True,ready=True,choice=""),"",13),
                   (dict(base,known=False),"",13), ([],"",13),
                   ({"known":True,"enabled":False},"",13),
                   (dict(base,active=True),"",13)]
            for state,names,exit in cases:
                result=subprocess.run(["bash",str(root/"check")],env=os.environ|{"PATH":str(root)+":"+os.environ["PATH"],"WALLET_STATUS":json.dumps(state),"WALLET_NAMES":names},capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,exit,result.stdout+result.stderr)

class NativeProviders(unittest.TestCase):
    @unittest.skipUnless(all(Path(p).is_file() for p in ("/usr/bin/kwalletd6", "/usr/bin/ksecretd")) and shutil.which("dbus-daemon") and KCONFIG, "native KDE wallet providers unavailable on this source-only runner")
    def test_real_on_off_and_disabled_activation_in_private_session(self):
        with tempfile.TemporaryDirectory(prefix="moos-wallet-native-") as temp:
            root = Path(temp)
            for name in ("home", "config", "data", "cache", "state", "runtime", "services"):
                (root/name).mkdir(mode=0o700)
            for name, exe in (("org.kde.kwalletd6", "kwalletd6"), ("org.freedesktop.impl.portal.desktop.kwallet", "ksecretd")):
                (root/"services"/(name+".service")).write_text("[D-BUS Service]\nName="+name+"\nExec=/usr/bin/"+exe+"\n")
            config = root/"bus.conf"
            config.write_text(f'<busconfig><type>session</type><listen>unix:path={root}/runtime/bus</listen><auth>EXTERNAL</auth><servicedir>{root}/services</servicedir><policy context="default"><allow user="{os.getuid()}"/><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
            env = {k:v for k,v in os.environ.items() if k not in ("DBUS_SESSION_BUS_ADDRESS", "DISPLAY", "WAYLAND_DISPLAY")}
            env.update(HOME=str(root/"home"), XDG_CONFIG_HOME=str(root/"config"), XDG_DATA_HOME=str(root/"data"), XDG_CACHE_HOME=str(root/"cache"), XDG_STATE_HOME=str(root/"state"), XDG_RUNTIME_DIR=str(root/"runtime"), XDG_CONFIG_DIRS=str(DEFAULTS), QT_QPA_PLATFORM="offscreen")
            with (root/"bus.log").open("w+") as log:
                daemon = subprocess.Popen(["dbus-daemon", "--config-file="+str(config), "--nofork", "--print-address=1"], env=env, stdout=subprocess.PIPE, stderr=log, text=True)
                try:
                    env["DBUS_SESSION_BUS_ADDRESS"] = daemon.stdout.readline().strip()
                    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), *(["--installed"] if INSTALLED else []), "--native-case"], env=env, capture_output=True, text=True, timeout=40)
                    log.flush(); log.seek(0)
                    self.assertEqual(result.returncode, 0, result.stdout+result.stderr+log.read())
                    self.assertIn("MOOS_WALLET_NATIVE_PASS", result.stdout)
                finally:
                    daemon.terminate(); daemon.wait(timeout=5)
                    daemon.stdout.close()

if __name__ == "__main__":
    if (INSTALLED or Path("/usr/lib/moos/edition").is_file()) and not (KCONFIG and shutil.which("dbus-daemon")
            and all(Path(p).is_file() for p in ("/usr/bin/kwalletd6", "/usr/bin/ksecretd"))):
        raise SystemExit("Native wallet proof dependencies are required on MoOS; no skipped acceptance.")
    if sys.argv[1:] == ["--native-case"]:
        assert not wallet.state()["enabled"]
        for executable in ("/usr/bin/kwalletd6", "/usr/bin/ksecretd"):
            disabled = subprocess.run([executable], capture_output=True, timeout=5)
            assert disabled.returncode != 0, "fresh default unexpectedly started " + executable
        assert not wallet.names()
        enabled = wallet.change("on")
        assert enabled["known"] and enabled["enabled"] and enabled["ready"] and enabled["choice"] == "on", enabled
        disabled = wallet.change("off")
        assert disabled["known"] and not disabled["active"] and not disabled["enabled"] and disabled["choice"] == "off", disabled
        for executable in ("/usr/bin/kwalletd6", "/usr/bin/ksecretd"):
            result = subprocess.run([executable], capture_output=True, timeout=5)
            assert result.returncode != 0, executable
        assert not wallet.names()
        print("MOOS_WALLET_NATIVE_PASS "+json.dumps({"on": enabled, "off": disabled}))
    else:
        result = unittest.main(verbosity=2, exit=False).result
        if INSTALLED and (result.skipped or result.testsRun < 12):
            raise SystemExit("Installed wallet proof must execute every native case.")
        if INSTALLED and result.wasSuccessful(): print("MOOS_IMAGE_WALLET_LIFECYCLE_PASS")
        raise SystemExit(0 if result.wasSuccessful() else 1)
