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

    def test_separate_public_community_does_not_publish_the_private_login_screen(self):
        node = {"BackendState": "Running", "Self": {"DNSName": "review.tail123.ts.net."}}
        serve = {"TCP": {"443": {"HTTPS": True}, "10000": {"HTTPS": True}},
                 "Web": {"review.tail123.ts.net:443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8865"}}},
                         "review.tail123.ts.net:10000": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8102"}}}},
                 "AllowFunnel": {"review.tail123.ts.net:10000": True}}
        self.assertTrue(G.private_tls_proxy(serve, node, 8865))
        # The old all-Funnel refusal rejects this real Oracle topology.
        self.assertTrue(any(v is not False for v in serve["AllowFunnel"].values()))
        for proxy in ("http://127.0.0.1:8865", "http://localhost:8865/remote", "http://[::1]:8865",
                      "https://another-node.invalid:8865/path", "bad proxy", "http://127.0.0.1:bad"):
            value = copy.deepcopy(serve)
            value["Web"]["review.tail123.ts.net:10000"]["Handlers"]["/remote"] = {"Proxy": proxy}
            with self.subTest(proxy=proxy):
                self.assertFalse(G.private_tls_proxy(value, node, 8865))
        for tcp in ({"TCPForward": "127.0.0.1:8865"}, {"HTTPS": True, "TCPForward": "127.0.0.1:8865"}, True):
            value=copy.deepcopy(serve);value["TCP"]["10000"]=tcp
            self.assertFalse(G.private_tls_proxy(value, node, 8865))
        for endpoint in ("not-an-endpoint", "review.tail123.ts.net:65536", "review.tail123.ts.net:443"):
            value=copy.deepcopy(serve);value["AllowFunnel"][endpoint]=True
            self.assertFalse(G.private_tls_proxy(value, node, 8865))

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
        replies = [subprocess.CompletedProcess([], 0, "", ""),
                   subprocess.CompletedProcess([], 0, "wayland-0\n", ""),
                   subprocess.CompletedProcess([], 0, "", "")]
        with patch.object(G, "greeter", return_value=account), patch.object(G.os, "geteuid", return_value=967), patch.object(G, "status", return_value={"enabled": False}), patch.object(G, "command", side_effect=replies) as command, patch.dict(G.os.environ, {}, clear=True):
            self.assertEqual(G.session(), {"enabled": False})
            args=command.call_args_list[0].args[0]
            self.assertIn("DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/967/bus",args)
            self.assertEqual(args[-5:], ["/usr/bin/flatpak", "permission-remove", "kde-authorized", "remote-desktop", "org.moos.remote"])
            self.assertEqual(command.call_count, 3)
            imported = command.call_args_list[2].args[0]
            self.assertIn("WAYLAND_DISPLAY=wayland-0", imported)
            self.assertIn("XDG_CURRENT_DESKTOP=KDE", imported)
            self.assertEqual(imported[-3:], ["import-environment", "WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP"])
            self.assertTrue(all("permission-set" not in call.args[0] for call in command.call_args_list))

    def test_disabled_session_rejects_missing_display_after_revocation(self):
        account=SimpleNamespace(pw_uid=967,pw_dir="/var/lib/plasmalogin")
        replies=[subprocess.CompletedProcess([],0,"",""),subprocess.CompletedProcess([],1,"","")]
        with patch.object(G,"greeter",return_value=account),patch.object(G.os,"geteuid",return_value=967),patch.object(G,"status",return_value={"enabled":False}),patch.object(G,"command",side_effect=replies) as call:
            with self.assertRaisesRegex(G.Refused,"wayland_required"):
                G.session()
            self.assertIn("permission-remove",call.call_args_list[0].args[0])

    def test_portal_probe_requires_both_actual_direct_interfaces(self):
        good='<node><interface name="org.freedesktop.impl.portal.RemoteDesktop"/><interface name="org.freedesktop.impl.portal.ScreenCast"/></node>'
        self.assertTrue(G.portal_interfaces_present(subprocess.CompletedProcess([],0,good,"")))
        for code, xml in ((1,good),(0,""),(0,"<node>"),(0,good.replace("ScreenCast","Screenshot")),
                          (0,'<node><!-- '+good+' --></node>'),(0,'<node><node>'+good+'</node></node>'),
                          (0,good+' '*65536)):
            with self.subTest(code=code,xml=xml[:60]):
                self.assertFalse(G.portal_interfaces_present(subprocess.CompletedProcess([],code,xml,"")))

    def test_warm_enable_preserves_healthy_backend_and_renews_only_incomplete_greeter_backend(self):
        good='<node><interface name="org.freedesktop.impl.portal.RemoteDesktop"/><interface name="org.freedesktop.impl.portal.ScreenCast"/></node>'
        account=SimpleNamespace(pw_uid=967)
        for missing in (False,True):
            replies=[subprocess.CompletedProcess([],0,"","")]
            if missing:replies += [subprocess.CompletedProcess([],0,"<node/>",""),subprocess.CompletedProcess([],0,"","")]
            replies.append(subprocess.CompletedProcess([],0,good,""))
            with patch.object(G,"user_command",side_effect=replies) as call:
                G.prepare_portal_backend(account)
                self.assertEqual(call.call_args_list[0].args,(account,["/usr/bin/systemctl","--user","start",G.UNITS[2]]))
                self.assertTrue(all(c.args[0] is account for c in call.call_args_list))
                renewals=[c.args[1] for c in call.call_args_list if "restart" in c.args[1]]
                self.assertEqual(renewals,[["/usr/bin/systemctl","--user","restart",G.KDE_PORTAL_UNIT]] if missing else [])

    def test_warm_enable_refuses_failed_policy_missing_interfaces_and_transport_errors(self):
        ok=subprocess.CompletedProcess([],0,"","");bad=subprocess.CompletedProcess([],1,"","")
        for replies in ([bad],[ok,bad,bad],[ok,bad,ok,ok],
                        [subprocess.TimeoutExpired("probe",10)], [OSError("private failure")]):
            with self.subTest(replies=replies),patch.object(G,"user_command",side_effect=replies):
                with self.assertRaises(G.Refused):G.prepare_portal_backend(SimpleNamespace(pw_uid=967))

    def test_policy_requires_admin_and_exact_helper_without_cached_authorization(self):
        # The grant remains administrator-owned even when desktop facts are
        # published while access is disabled.
        policy=ET.parse(ROOT / "system_files/usr/share/polkit-1/actions/org.moos.remote-greeter.policy")
        action=policy.getroot().find("action")
        self.assertEqual(action.attrib["id"],"org.moos.remote-greeter")
        self.assertEqual({node.text for node in action.find("defaults")},{"auth_admin"})
        self.assertEqual(action.find("annotate").text,"/usr/libexec/mo-remote-greeter")
        self.assertTrue(any(node.attrib.get("{http://www.w3.org/XML/1998/namespace}lang")=="ar" for node in action.findall("message")))

    def test_live_activation_failures_retire_enrollment_but_absent_login_target_does_not(self):
        ok=subprocess.CompletedProcess([],0,"","");bad=subprocess.CompletedProcess([],1,"","")
        account=SimpleNamespace(pw_uid=967)
        cases=([ok,bad],[ok,ok,bad],[subprocess.TimeoutExpired("private",10)],[OSError("private")])
        for replies in cases:
            with self.subTest(replies=replies),patch.object(G,"user_command",side_effect=replies),patch.object(G,"prepare_portal_backend"),patch.object(G,"retire") as retire:
                with self.assertRaises(G.Refused):G.start_live_greeter(account)
                retire.assert_called_once_with(account)
        with patch.object(G,"user_command",side_effect=[ok,ok]),patch.object(G,"prepare_portal_backend",side_effect=G.Refused("portal_backend_required")),patch.object(G,"retire") as retire:
            with self.assertRaisesRegex(G.Refused,"portal_backend_required"):G.start_live_greeter(account)
            retire.assert_called_once_with(account)
        for replies,ready in (([bad],False),([ok,ok,ok],True)):
            with patch.object(G,"user_command",side_effect=replies),patch.object(G,"prepare_portal_backend") as prepare,patch.object(G,"retire") as retire:
                G.start_live_greeter(account)
                self.assertEqual(prepare.call_count,1 if ready else 0)
                retire.assert_not_called()

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
