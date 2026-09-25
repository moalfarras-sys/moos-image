#!/usr/bin/env python3
"""Contracts and executable SSH identity checks for the final-ISO proof."""

import ast
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


root = Path(__file__).resolve().parents[1]
script_path = root / "tests/install_live_iso.sh"
workflow_path = root / ".github/workflows/build-iso.yml"
script = script_path.read_text(encoding="utf-8")
workflow = workflow_path.read_text(encoding="utf-8")

required_script = (
    'file=$iso,media=cdrom,format=raw,readonly=on',
    "systemctl stop NetworkManager.service",
    "source: local containers-storage (offline)",
    "install-source-digest",
    "/usr/bin/moos-install-to-disk",
    "start_qemu live-install install-2d",
    "! findmnt -rn -o SOURCE | grep -qE '^/dev/vda",
    '"path": "/usr/bin/systemctl"',
    '"arg": ["poweroff", "--no-wall", "--force", "--force"]',
    "start_qemu installed proof-virgl -boot order=c",
    "! grep -qw rd.live.image /proc/cmdline",
    "ostree-image-signed:docker://${expected}",
    # The wake must still send both keys, and must ALSO move the pointer: keys
    # alone provably do not dismiss PLM's idle clock (runs 34167769770,
    # 34170891110, 34187614662 all sent them and all three captures show the
    # clock still painted). These are asserted as the command strings rather
    # than as one literal call, so the calls can be batched without the gate
    # going quiet about the contract.
    '"sendkey shift"',
    '"sendkey spc"',
    '"mouse_move',
    "-device virtio-keyboard-pci",
    "-device virtio-tablet-pci",
    '"sendkey ret"',
    # The password field is emptied first: a wake space typed into an
    # already-focused field made PAM reject the right password (run 34650456175).
    '"sendkey ctrl-a", "sendkey backspace"',
    # hmp() must READ QEMU's reply. Sending blind made a rejected command
    # indistinguishable from a delivered keystroke, which is why three runs
    # could not establish whether any input reached the guest at all.
    "client.recv(8192)",
    # The login must be confirmed by logind opening a session for the CI user.
    # kwin and plasmashell are downstream of that; reporting their absence is
    # what disguised a login that never happened as a compositor failure.
    "def session_for_uid",
    "loginctl list-sessions",
    # The AccountsService step must be able to FAIL. It was a bare command
    # sequence ending in `sleep 10`, so it always exited 0 and its output was
    # discarded -- on the critical path for whether the greeter has any user.
    "AccountsService does not publish moosci",
    "accounts-probe.txt",
    "pgrep -u \"$uid\" -x kwin_wayland",
    "pgrep -u \"$uid\" -x plasmashell",
    '("dolphin", "dolphin")',
    '("mo-ai", "moai")',
    '("mo-store", "moos-store")',
    '("updater", "moos-update")',
    '("recovery", "moos-rollback")',
    '("themes", "moos-theme-picker")',
    '("moplayer", "moplayer")',
    '("mo-pc-remote", "mo-pc-remote")',
    "opened-closed-reopened",
    "systemctl --user --failed --no-legend --plain",
    "moos-ci-runtime-proof",
    "ci-proof=ephemeral-ssh",
    '"BatchMode=yes"',
    '"IdentitiesOnly=yes"',
    "root@127.0.0.1",
    '"mode": "reboot"',
    'qga_boot_id = ""',
    'ssh_boot_id = ""',
    'reboot-qga-state.txt',
    '-machine q35,accel=kvm -cpu host -m 6144 -smp 4',
    '"mode": "powerdown"',
    "qemu-img check",
)
for needle in required_script:
    assert needle in script, f"ISO install proof lost required contract: {needle}"

proof_unit = (
    root / "system_files/usr/lib/systemd/system/moos-ci-runtime-proof.service"
).read_text(encoding="utf-8")
assert "ConditionPathExists=|/home/mo/.ssh/authorized_keys" in proof_unit
assert "ConditionPathExists=|/home/moosci/.ssh/authorized_keys" in proof_unit

# The installed QEMU command is deliberately constructed without the ISO. A
# future refactor must not make the second boot silently fall back to the LiveOS.
installed_start = script.index("start_qemu installed proof-virgl -boot order=c")
installed_python = script.index('python3 - "$qga" "$monitor"', installed_start)
assert "media=cdrom" not in script[installed_start:installed_python]

assert "tests/install_live_iso.sh \"$FINAL_ISO\"" in workflow
assert workflow.index("Boot and prove the exact final live ISO") < workflow.index(
    "Install the exact final ISO offline and boot the target disk"
)
assert "name: moos-iso-install-proof" in workflow
assert "timeout-minutes: 180" in workflow

# Load only the installed-proof functions, never its QEMU/SSH main program.
installed_code = script[installed_python:].split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
installed_tree = ast.parse(installed_code)
functions = ast.Module(body=[node for node in installed_tree.body
                            if isinstance(node, ast.FunctionDef)
                            and node.name in {"ssh_exec", "gate_until"}], type_ignores=[])


# The second boot is reached through a forward that no pre-reboot connection touched, as
# tests/boot_x86_qcow2.sh does. Be exact about why this is pinned: it was written as the FIX
# for plan row P0.8 and run 35265328509 measured that it was not — the first-boot forward was
# alive after the reboot (`reboot-channel.txt`), and the real cause was the proof-channel
# helper reading the default route once (tests/test_ci_proof_channel.py). It stays because it
# costs nothing, matches the other proofs, and keeps the measurement that told the two apart.
assert ("hostfwd=tcp:127.0.0.1:${ssh_port}-:22,"
        "hostfwd=tcp:127.0.0.1:${ssh_port_after_reboot}-:22") in script, \
    "the installed VM needs one SSH forward per boot"
assert '[ "$ssh_port" != "$ssh_port_after_reboot" ]' in script
reboot_request = installed_code.index('"mode": "reboot"')
forward_switch = installed_code.index("\nssh_port = ssh_port_after_reboot\n", reboot_request)
second_boot_wait = installed_code.index('last_reboot_error = "SSH has not returned after reboot"')
assert reboot_request < forward_switch < second_boot_wait, \
    "switch to the fresh forward after the reboot request and BEFORE waiting for the second boot"
# The health gate of the second boot must run on the fresh forward too: every later
# assignment back to the first-boot forward is a bounded probe that restores it.
second_gate = installed_code.index('"installed second boot never became healthy"')
last_assignment = max(match.start() for match in re.finditer(r"^ssh_port = (\w+)$",
                                                             installed_code[:second_gate], re.M))
assert installed_code[last_assignment:].startswith("ssh_port = ssh_port_after_reboot"), \
    "the second-boot health gate must not run through the first-boot forward"
assert "reboot-channel.txt" in installed_code and "first-boot-forward=" in installed_code, \
    "record whether the first-boot forward survived: that measurement is what closes P0.8"


class SessionIdentityTests(unittest.TestCase):
    def setUp(self):
        self.run = Mock(return_value=SimpleNamespace(returncode=0, stdout="healthy", stderr=""))
        self.namespace = {
            "subprocess": SimpleNamespace(run=self.run, TimeoutExpired=TimeoutError),
            "ssh_key": "/fixture/key", "ssh_port": "2200",
            "time": SimpleNamespace(monotonic=lambda: 0),
        }
        exec(compile(functions, str(script_path), "exec"), self.namespace)

    def remote_command(self):
        command = self.run.call_args.args[0]
        return command[command.index("root@127.0.0.1") + 1:]

    def test_system_proof_retains_root_and_script_stdin(self):
        result = self.namespace["ssh_exec"]("read origin", ["digest"])
        self.assertEqual(result, (0, "healthy", ""))
        self.assertEqual(self.remote_command(), ["/usr/bin/bash", "-s", "--", "digest"])
        self.assertEqual(self.run.call_args.kwargs["input"], "read origin")

    def test_session_gate_drops_credentials_before_executing_shell(self):
        result = self.namespace["gate_until"]("inspect desktop", ["dolphin"], 10,
                                               "desktop", desktop_user=True)
        self.assertEqual(result, "healthy")
        self.assertEqual(self.remote_command(), ["/usr/sbin/runuser", "-u", "moosci", "--",
                                                 "/usr/bin/bash", "-s", "--", "dolphin"])
        self.assertEqual(self.run.call_args.kwargs["input"], "inspect desktop")

    def test_failed_session_probe_cannot_report_success(self):
        self.run.return_value = SimpleNamespace(returncode=1, stdout="", stderr="bus denied")
        self.assertEqual(self.namespace["ssh_exec"]("probe", desktop_user=True),
                         (1, "", "bus denied"))

    def test_all_session_checks_select_desktop_uid(self):
        session_scripts = {"desktop", "open_app", "close_app", "user_health"}
        counts = {name: 0 for name in session_scripts}
        for node in ast.walk(installed_tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "gate_until" and node.args
                    and isinstance(node.args[0], ast.Name)):
                continue
            name = node.args[0].id
            options = {kw.arg: kw.value for kw in node.keywords}
            enabled = ("desktop_user" in options
                       and isinstance(options["desktop_user"], ast.Constant)
                       and options["desktop_user"].value is True)
            self.assertEqual(enabled, name in session_scripts, name)
            if name in counts:
                counts[name] += 1
        self.assertEqual(counts, {"desktop": 1, "open_app": 2, "close_app": 2, "user_health": 1})


def installed_assignment(name):
    for node in installed_tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name):
            return ast.literal_eval(node.value)
    raise AssertionError(f"the installed proof lost {name}")


class SettingsPageProofTests(unittest.TestCase):
    """MoOS Themes opens INSIDE System Settings: the 'themes' smoke entry must prove the
    kcm_moos_appearance module loaded, not merely that a System Settings window mapped
    (an error page for a broken module, or the stock page moos-settings falls back to when
    the module is missing, both map a window)."""

    def run_check(self, unit, module, journal):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            stubs = Path(temp) / "bin"
            stubs.mkdir()
            calls = Path(temp) / "journalctl.args"
            fixture = Path(temp) / "journal.txt"
            fixture.write_text(journal, encoding="utf-8")
            (stubs / "journalctl").write_text(
                '#!/usr/bin/bash\nprintf "%s\\n" "$@" >"$CALLS"\ncat "$FIXTURE"\n', encoding="utf-8")
            (stubs / "id").write_text('#!/usr/bin/bash\necho 1000\n', encoding="utf-8")
            for stub in stubs.iterdir():
                stub.chmod(0o755)
            env = {"PATH": f"{stubs}:/usr/bin:/bin", "HOME": temp, "LANG": "C.UTF-8",
                   "CALLS": str(calls), "FIXTURE": str(fixture)}
            result = subprocess.run(["/usr/bin/bash", "-s", "--", unit, module],
                                    input=installed_assignment("kcm_ready"), text=True,
                                    capture_output=True, env=env, timeout=30, check=False)
            args = calls.read_text(encoding="utf-8").splitlines() if calls.exists() else []
            return result, args

    def test_the_module_marker_is_required_as_a_whole_line(self):
        for journal in ("Started page\nMOOS_KCM_READY kcm_moos_appearance\n",
                        "moos.settings: MOOS_KCM_READY kcm_moos_appearance\n"):
            with self.subTest(journal=journal):
                result, args = self.run_check("moai-open-12-34", "kcm_moos_appearance", journal)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "kcm_moos_appearance=ready\n")
                # Root reads the desktop user's unit by field; --user-unit would match uid 0.
                self.assertIn("_SYSTEMD_USER_UNIT=moai-open-12-34.service", args)
                self.assertIn("_UID=1000", args)
                self.assertNotIn("--user-unit", " ".join(args))
        for journal in ("",                                                  # module missing: stock page
                        "Could not find plugin kcm_moos_appearance\n",       # failed to load
                        "MOOS_KCM_READY kcm_lookandfeel\n",
                        "MOOS_KCM_READY kcm_moos_appearance_old\n",
                        "not MOOS_KCM_READY kcm_moos_appearance yet\n"):
            with self.subTest(journal=journal):
                result, _args = self.run_check("moai-open-12-34", "kcm_moos_appearance", journal)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("did not report ready in moai-open-12-34.service", result.stderr)
        # A shorter module id never passes on a longer one's line.
        result, _args = self.run_check("u.service", "kcm_moos", "MOOS_KCM_READY kcm_moos_update\n")
        self.assertEqual(result.returncode, 1)
        _result, args = self.run_check("u.service", "kcm_moos", "MOOS_KCM_READY kcm_moos\n")
        self.assertIn("_SYSTEMD_USER_UNIT=u.service", args)

    def test_the_themes_entry_is_held_to_its_module_on_both_opens(self):
        self.assertIn(("themes", "moos-theme-picker"), installed_assignment("app_specs"))
        self.assertEqual(installed_assignment("settings_modules"), {"themes": "kcm_moos_appearance"})
        # The module named is the one the launcher really opens.
        shim = (root / "system_files/usr/bin/moos-theme-picker").read_text(encoding="utf-8")
        self.assertIn("exec moos-settings --section=appearance", shim)
        settings = (root / "system_files/usr/bin/moos-settings").read_text(encoding="utf-8")
        self.assertRegex(settings, r"--section=appearance\|[^\n]*\) module=kcm_moos_appearance ;;")
        loop = next(node for node in installed_tree.body if isinstance(node, ast.For)
                    and isinstance(node.iter, ast.Name) and node.iter.id == "app_specs")
        calls = [node for node in ast.walk(loop) if isinstance(node, ast.Call)]

        def line_of(predicate, what):
            found = [node.lineno for node in calls if predicate(node)]
            self.assertTrue(found, what)
            return found

        def is_gate(node, units):
            return (isinstance(node.func, ast.Name) and node.func.id == "gate_until"
                    and isinstance(node.args[0], ast.Name) and node.args[0].id == "kcm_ready"
                    and isinstance(node.args[1], ast.List)
                    and [getattr(e, "id", None) for e in node.args[1].elts] == units)

        def named(node, name, first=None):
            return (isinstance(node.func, ast.Name) and node.func.id == name
                    and (first is None or (len(node.args) > 1 and isinstance(node.args[1], ast.Constant)
                                           and node.args[1].value == first)))

        opened = line_of(lambda n: named(n, "wait_for_window", "open"), "wait for the first window")[0]
        reopened = line_of(lambda n: named(n, "wait_for_window", "reopen"), "wait for the reopen")[0]
        first_ready = line_of(lambda n: is_gate(n, ["unit", "module"]), "first open unchecked")[0]
        second_ready = line_of(lambda n: is_gate(n, ["second_unit", "module"]), "reopen unchecked")[0]
        appended = line_of(lambda n: isinstance(n.func, ast.Attribute) and n.func.attr == "append"
                           and isinstance(n.func.value, ast.Name) and n.func.value.id == "app_proof",
                           "no app proof recorded")[0]
        self.assertLess(opened, first_ready)
        self.assertLess(first_ready, reopened)
        self.assertLess(reopened, second_ready)
        self.assertLess(second_ready, appended,
                        "themes=opened-closed-reopened, which promotion requires, is written only "
                        "after the module proved itself on both opens")


if __name__ == "__main__":
    unittest.main()
