#!/usr/bin/env python3
"""Execute the privileged boundary in isolation; never change the live host.

Native user-unit/cold-login acceptance remains a separate private VM proof.
"""
import copy
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "system_files/usr/libexec/mo-remote-greeter"
loader = importlib.machinery.SourceFileLoader("isolated_greeter", str(HELPER))
spec = importlib.util.spec_from_loader(loader.name, loader)
G = importlib.util.module_from_spec(spec)
loader.exec_module(G)


class ManagementTests(unittest.TestCase):
    def test_request_is_closed_and_pin_never_accepts_account_password_or_shell(self):
        self.assertEqual(G.validate_request({"port": 8865, "pin": "123456"}), (8865, "123456"))
        for value in (None, [], {}, {"port": True, "pin": "123456"},
                      {"port": 22, "pin": "123456"}, {"port": 65535, "pin": "123456"},
                      {"port": 8765, "pin": "123456", "path": "/etc/shadow"},
                      {"port": 8765, "pin": "$(touch /tmp/owned)"},
                      {"port": 8765, "pin": "１２３４５６"},
                      {"port": 8765, "pin": "123456789012"}):
            with self.subTest(value=value), self.assertRaises(G.Refused):
                G.validate_request(value)

    def test_no_privileged_action_without_kernel_root_and_pkexec_caller(self):
        with patch.object(G, "command") as command:
            for uid, caller in ((1000, "1000"), (0, ""), (0, "0"), (0, "owner")):
                with patch.object(G.os, "geteuid", return_value=uid), patch.dict(G.os.environ, {"PKEXEC_UID": caller}):
                    with self.assertRaisesRegex(G.Refused, "administrator_required"):
                        G.change("disable", None)
            command.assert_not_called()

    def test_exact_private_https_route_and_funnel_refusal(self):
        node = {"BackendState": "Running", "Self": {"DNSName": "review.tail123.ts.net."}}
        good = {"TCP": {"443": {"HTTPS": True}}, "Web": {"review.tail123.ts.net:443": {
            "Handlers": {"/": {"Proxy": "http://127.0.0.1:8865"}}}}}
        self.assertTrue(G.private_tls_proxy(good, node, 8865))
        self.assertFalse(G.private_tls_proxy(good, node, 8765))
        controls = []
        for replacement in (False, "true", None):
            value = copy.deepcopy(good);value["TCP"]["443"]["HTTPS"] = replacement;controls.append(value)
        for proxy in ("http://0.0.0.0:8865", "http://127.0.0.1:88650", "https://127.0.0.1:8865", "http://127.0.0.1:8865/other"):
            value = copy.deepcopy(good);value["Web"]["review.tail123.ts.net:443"]["Handlers"]["/"]["Proxy"] = proxy;controls.append(value)
        value = copy.deepcopy(good);value["Web"]["review.tail123.ts.net:443"]["Handlers"]["/remote"] = value["Web"]["review.tail123.ts.net:443"]["Handlers"].pop("/");controls.append(value)
        value = copy.deepcopy(good);value["AllowFunnel"] = {"review.tail123.ts.net:443": True};controls.append(value)
        value = copy.deepcopy(good);value["AllowFunnel"] = {"review.tail123.ts.net:443": "false"};controls.append(value)
        for value in (*controls, None, [], {"TCP": None}, {"TCP": {"443": True}, "Web": []}):
            with self.subTest(value=value):
                self.assertFalse(G.private_tls_proxy(value, node, 8865))
        for bad_node in ({}, {**node, "BackendState": "NeedsLogin"}, {"BackendState": "Running", "Self": True}):
            self.assertFalse(G.private_tls_proxy(good, bad_node, 8865))

    def test_safe_files_reject_links_fifo_permissions_owner_and_oversize(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); path = root / "settings.json"
            G.write_json(path, {"test": 1}, os.getuid(), os.getgid(), 0o600)
            self.assertEqual(G.read_json(path, os.getuid(), 0o600), {"test": 1})
            old = root / "old";path.rename(old);path.symlink_to(old)
            with self.assertRaises(OSError): G.read_json(path, os.getuid(), 0o600)
            # Atomic replacement replaces the link, preserving its target bytes.
            G.write_json(path, {"test": 2}, os.getuid(), os.getgid(), 0o600)
            self.assertEqual(json.loads(old.read_text()), {"test": 1})
            os.link(path, root / "hardlink")
            with self.assertRaises(G.Refused): G.read_json(path, os.getuid(), 0o600)
            (root / "hardlink").unlink();path.chmod(0o644)
            with self.assertRaises(G.Refused): G.read_json(path, os.getuid(), 0o600)
            path.chmod(0o600)
            with self.assertRaises(G.Refused): G.read_json(path, os.getuid() + 1, 0o600)
            with self.assertRaises(G.Refused): G.read_json(path, os.getuid(), 0o600, limit=2)
            path.unlink();os.mkfifo(path, 0o600)
            with self.assertRaises(G.Refused): G.read_json(path, os.getuid(), 0o600)
            linked = root / "linked";linked.symlink_to(root, target_is_directory=True)
            with self.assertRaises(G.Refused): G.private_directory(linked, os.getuid(), os.getgid(), 0o700)

    def test_failed_stop_removes_authority_first_and_does_not_erase_account_data(self):
        with tempfile.TemporaryDirectory() as name:
            marker = Path(name) / "enabled.json";marker.write_text("{}")
            record=[]
            def call(*args, **kwargs):
                self.assertFalse(marker.exists(), "authority must disappear before stop")
                record.append(args)
                return subprocess.CompletedProcess([], 1, "", "")
            with patch.object(G, "MARKER", marker), patch.object(G, "bus_present", return_value=True), patch.object(G, "user_command", side_effect=call):
                with self.assertRaisesRegex(G.Refused, "stop_failed"):
                    G.retire(SimpleNamespace(pw_uid=967))
            self.assertEqual(len(record), 1)
            self.assertEqual(record[0][1][3:], list(G.UNITS))

    def test_disabled_session_revokes_only_greeter_app_grant(self):
        account=SimpleNamespace(pw_uid=967,pw_dir="/var/lib/plasmalogin")
        with patch.object(G, "greeter", return_value=account), patch.object(G.os, "geteuid", return_value=967), patch.object(G, "status", return_value={"enabled": False}), patch.object(G, "command") as command:
            self.assertEqual(G.session(), {"enabled": False})
            args=command.call_args.args[0]
            self.assertIn("DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/967/bus",args)
            self.assertEqual(args[-5:], ["/usr/bin/flatpak", "permission-remove", "kde-authorized", "remote-desktop", "org.moos.remote"])
            self.assertNotIn("permission-set",args)

    def test_policy_requires_admin_and_exact_helper_without_cached_authorization(self):
        policy=ET.parse(ROOT / "system_files/usr/share/polkit-1/actions/org.moos.remote-greeter.policy")
        action=policy.getroot().find("action")
        self.assertEqual(action.attrib["id"],"org.moos.remote-greeter")
        self.assertEqual({node.text for node in action.find("defaults")},{"auth_admin"})
        self.assertEqual(action.find("annotate").text,"/usr/libexec/mo-remote-greeter")
        self.assertTrue(any(node.attrib.get("{http://www.w3.org/XML/1998/namespace}lang")=="ar" for node in action.findall("message")))

    def test_source_wiring_off_by_default_and_no_authentication_fork(self):
        directory=ROOT / "system_files/usr/lib/systemd/user"
        for unit in ("mo-remote-greeter.service","mo-remote-greeter-session.service"):
            link=directory / "plasma-login-wayland.target.wants" / unit
            self.assertTrue(link.is_symlink());self.assertEqual(link.resolve(),directory / unit)
            self.assertIn("ConditionUser=plasmalogin",(directory / unit).read_text())
        for unit in G.UNITS[:2]:
            source=(directory / unit).read_text()
            self.assertIn("ConditionPathExists=/var/lib/mo-remote-greeter/enabled.json",source)
            self.assertIn("BindsTo=plasma-login-kwin_wayland.service",source)
            self.assertIn("PartOf=plasma-login-wayland.target",source)
            self.assertIn("TimeoutStopFailureMode=kill",(directory / (unit+".d") / "20-stop-policy.conf").read_text())
        self.assertFalse((ROOT / "system_files/var/lib/mo-remote-greeter/enabled.json").exists())
        source=HELPER.read_text()
        for forbidden in ("shell=True", "/etc/pam.d", "autologin", "funnel --", "sudo -"):
            self.assertNotIn(forbidden,source)

    def test_system_stop_revokes_enrollment_before_disabling_account_service(self):
        control_path=ROOT / "system_files/usr/bin/moos-control"
        loader=importlib.machinery.SourceFileLoader("private_control_stop",str(control_path))
        spec=importlib.util.spec_from_loader(loader.name,loader);control=importlib.util.module_from_spec(spec);loader.exec_module(control)
        calls=[]
        replies=[subprocess.CompletedProcess([],0,json.dumps({"enabled":True}),""),
                 subprocess.CompletedProcess([],0,json.dumps({"enabled":False}),"")]
        with patch.object(control.os.path,"isfile",return_value=True), patch.object(control.subprocess,"run",side_effect=replies), patch.object(control,"run",side_effect=lambda argv,**_: calls.append(argv)), patch.object(control,"remote_state",return_value="inactive"):
            control.remote("off")
        self.assertEqual(calls,[["pkexec","/usr/libexec/mo-remote-greeter","disable"],
                                ["systemctl","--user","disable","--now","mo-remote-personal.service"]])
        with patch.object(control.os.path,"isfile",return_value=True), patch.object(control.subprocess,"run",return_value=replies[0]), patch.object(control,"run",side_effect=control.Unavailable("authorization refused")):
            with self.assertRaisesRegex(control.Unavailable,"authorization refused"):
                control.remote("off")
        # On never enrolls/opens the greeter, even if the user previously stopped it.
        with patch.object(control,"disable_login_remote") as disable, patch.object(control,"run"), patch.object(control,"remote_came_up",return_value=(True,"active")):
            control.remote("on");disable.assert_not_called()


if __name__ == "__main__":
    unittest.main()
