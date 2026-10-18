#!/usr/bin/env python3
"""Contracts and executable SSH identity checks for the final-ISO proof."""

import ast
import contextlib
import io
from pathlib import Path
import re
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


root = Path(__file__).resolve().parents[1]
script_path = root / "tests/install_live_iso.sh"
workflow_path = root / ".github/workflows/build-iso.yml"
script = script_path.read_text(encoding="utf-8")
workflow = workflow_path.read_text(encoding="utf-8")

# Load the live helper's deadline and bounded collector without running QEMU.
live_start = script.index('qga, qemu_pid, expected, password, evidence_arg, proof_key')
live_start = script.rfind("<<'PY'\n", 0, live_start) + len("<<'PY'\n")
live_code = script[live_start:].split('\nPY\n', 1)[0]
live_tree = ast.parse(live_code)
live_functions = ast.Module(body=[n for n in live_tree.body
                                 if isinstance(n, ast.FunctionDef)
                                 and n.name in {'exec_wait', 'collect_installer_diagnostics'}],
                            type_ignores=[])


class LiveDiagnosticTests(unittest.TestCase):
    def test_timeout_reports_its_actual_deadline(self):
        request = Mock(return_value={'pid': 123})
        clock = Mock(side_effect=[0, 31])
        namespace = {'request': request, 'time': SimpleNamespace(monotonic=clock)}
        exec(compile(live_functions, str(script_path), 'exec'), namespace)
        with self.assertRaisesRegex(TimeoutError, '123.*30 seconds'):
            namespace['exec_wait']('read log', [], 30)

    def test_collector_is_bounded_and_requires_success(self):
        namespace = {}
        exec(compile(live_functions, str(script_path), 'exec'), namespace)
        fake_file = Mock()
        class Sink:
            def __truediv__(self, name):
                return fake_file
        namespace['evidence'] = Sink()
        run = Mock(return_value=(0, 'captured', ''))
        namespace['exec_wait'] = run
        self.assertTrue(namespace['collect_installer_diagnostics']())
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertIn('head -c 65536', call.args[0])
            self.assertIn('tail -c 65536', call.args[0])
            self.assertEqual(call.args[2], 30)
        run.return_value = (1, '', 'permission denied')
        self.assertFalse(namespace['collect_installer_diagnostics']())
        command = run.call_args_list[0].args[0]
        with tempfile.TemporaryDirectory(prefix='moos-iso-log-') as directory:
            path = Path(directory) / 'log'
            missing = subprocess.run(['bash', '-c', command, '--', str(path)],
                                     capture_output=True)
            self.assertNotEqual(missing.returncode, 0)
            path.write_bytes(b'first\n' + b'x' * 300000 + b'\nlast\n')
            actual = subprocess.run(['bash', '-c', command, '--', str(path)],
                                    capture_output=True)
            self.assertEqual(actual.returncode, 0)
            self.assertLess(len(actual.stdout), 131200)
            self.assertTrue(actual.stdout.startswith(b'first\n'))
            self.assertTrue(actual.stdout.endswith(b'\nlast\n'))

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



class LoginFrameIdentityTests(unittest.TestCase):
    """Execute the real wake/type/session loop without QEMU, SSH or owner input."""

    @staticmethod
    def frames():
        header = b"P6\n64 48\n255\n"
        first = header + (b"\x0e\x15\x24" * 32 + b"\xa0\xc0\xe0" * 32) * 48
        second = header + (b"\x15\x24\x35" * 32 + b"\xe0\xb0\x80" * 32) * 48
        handoff = header + b"\x0e\x15\x24" * (64 * 48)
        return first, second, handoff

    def run_login(self, accepted_attempt=1, frames=None):
        first, second, handoff = frames or self.frames()
        start = next(i for i, node in enumerate(installed_tree.body)
                     if isinstance(node, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == "logged_in"
                             for target in node.targets))
        stop = next(i for i, node in enumerate(installed_tree.body)
                    if i > start and isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "desktop"
                            for target in node.targets))
        sequence = ast.Module(body=installed_tree.body[start:stop], type_ignores=[])
        with tempfile.TemporaryDirectory(prefix="moos-iso-frame-") as directory:
            evidence = Path(directory)
            state = {"phase": "greeter"}
            before_type = []
            captures = []
            namespace = {
                "evidence": evidence, "password": "ci-fixture",
                "time": SimpleNamespace(sleep=lambda _seconds: None),
                "sys": SimpleNamespace(stderr=None),
                "print": lambda *_args, **_kwargs: None,
            }

            def hmp(commands, label):
                if "sendkey ret" in commands:
                    historical = evidence / "installed-login.ppm"
                    before_type.append(historical.read_bytes() if historical.exists() else None)
                    state["phase"] = "handoff"
                elif label.startswith("wake-"):
                    state["phase"] = "greeter"
                return "fixture input delivered"

            def capture(path):
                pixels = ((first if namespace["attempt"] == 1 else second)
                          if state["phase"] == "greeter" else handoff)
                path.write_bytes(pixels)
                for suffix in ("-capture.log", "-windows.txt"):
                    (evidence / f"{path.stem}{suffix}").write_text(
                        f"{path.name}: {state['phase']}", encoding="utf-8")
                captures.append((path.name, state["phase"]))

            namespace.update(hmp=hmp, capture=capture,
                             session_for_uid=lambda: namespace["attempt"] >= accepted_attempt)
            exec(compile(sequence, str(script_path), "exec"), namespace)
            return ({path.name: path.read_bytes() for path in evidence.iterdir() if path.is_file()},
                    before_type, captures)

    def visual_check(self, pixels):
        with tempfile.TemporaryDirectory(prefix="moos-iso-visual-") as directory:
            frame = Path(directory) / "frame.ppm"
            frame.write_bytes(pixels)
            return subprocess.run(
                ["python3", str(root / "tests/assert_visual_frame.py"), str(frame)],
                capture_output=True, text=True, timeout=5, check=False,
            )

    def test_historical_login_is_the_exact_first_pre_authentication_frame(self):
        first, _second, _handoff = self.frames()
        files, before_type, captures = self.run_login()
        self.assertEqual(files["installed-login.ppm"], first)
        self.assertEqual(files["installed-login-attempt1.ppm"], first)
        self.assertEqual(before_type, [first], "the login picture was not saved before Return")
        for suffix in ("-capture.log", "-windows.txt"):
            self.assertEqual(files[f"installed-login{suffix}"],
                             files[f"installed-login-attempt1{suffix}"])
        self.assertEqual(files["installed-login-source.txt"],
                         b"alias-of=installed-login-attempt1.ppm\nphase=pre-authentication\n")
        self.assertEqual(captures, [("installed-login-attempt1.ppm", "greeter")])
        checked = self.visual_check(files["installed-login.ppm"])
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_retry_preserves_first_picture_and_every_attempt(self):
        first, second, _handoff = self.frames()
        files, before_type, captures = self.run_login(accepted_attempt=2)
        self.assertEqual(files["installed-login.ppm"], first)
        self.assertEqual(files["installed-login-attempt1.ppm"], first)
        self.assertEqual(files["installed-login-attempt2.ppm"], second)
        self.assertEqual(before_type, [first, first])
        self.assertEqual(captures, [("installed-login-attempt1.ppm", "greeter"),
                                    ("installed-login-attempt2.ppm", "greeter")])

    def test_visual_gate_still_rejects_flat_post_authentication_handoff(self):
        checked = self.visual_check(self.frames()[2])
        self.assertNotEqual(checked.returncode, 0)
        self.assertIn("is black/flat", checked.stderr)
        self.assertIn("stddev=0.000000", checked.stderr)


class AppCloseDiagnosticTests(unittest.TestCase):
    def helpers(self):
        selected = ast.Module(body=[node for node in installed_tree.body
                                    if isinstance(node, ast.FunctionDef)
                                    and node.name in {"observe_app_close", "collect_app_close_diagnostics"}],
                              type_ignores=[])
        namespace = {"sys": SimpleNamespace(stderr=io.StringIO()), "subprocess": subprocess,
                     "contextlib": contextlib}
        exec(compile(selected, str(script_path), "exec"), namespace)
        return namespace

    def close_fixture(self, failure=None, diagnostic_error=None):
        namespace = self.helpers()
        events = []
        stop = SimpleNamespace(set=lambda: events.append("input stopped"))
        thread = SimpleNamespace(join=lambda: events.append("input joined"))
        gate = Mock(side_effect=failure)
        def diagnose(*args):
            events.append("diagnose")
            if diagnostic_error is not None:
                raise diagnostic_error
        namespace.update(threading=SimpleNamespace(Event=lambda: stop),
                         start_close_resends=Mock(return_value=thread),
                         gate_until=gate, close_app="existing close predicate",
                         collect_app_close_diagnostics=Mock(side_effect=diagnose))
        return namespace, events, gate

    def test_success_keeps_the_same_real_close_predicate_and_deadline(self):
        namespace, events, gate = self.close_fixture()
        with namespace["observe_app_close"]("moai-open-12-34", "themes", "open"):
            gate()
        gate.assert_called_once_with()
        calls = [node for node in ast.walk(installed_tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id == "gate_until" and node.args
                 and isinstance(node.args[0], ast.Name) and node.args[0].id == "close_app"]
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(isinstance(node.args[2], ast.Constant) and node.args[2].value == 75
                            for node in calls))
        self.assertEqual(events, ["input stopped", "input joined"])
        namespace["collect_app_close_diagnostics"].assert_not_called()

    def test_failure_stops_resends_before_observing_and_keeps_the_original_verdict(self):
        original = SystemExit("fixture: unit stayed active")
        namespace, events, gate = self.close_fixture(original)
        with self.assertRaises(SystemExit) as caught:
            with namespace["observe_app_close"]("moai-open-12-34", "themes", "reopen"):
                gate()
        self.assertIs(caught.exception, original)
        self.assertEqual(events, ["input stopped", "input joined", "diagnose"])

    def test_broken_diagnostics_cannot_hide_or_replace_the_functional_failure(self):
        for diagnostic_error in (OSError("fixture unreadable"), SystemExit(47)):
            original = SystemExit(23)
            namespace, events, gate = self.close_fixture(original, diagnostic_error)
            with self.subTest(error=type(diagnostic_error).__name__), self.assertRaises(SystemExit) as caught:
                with namespace["observe_app_close"]("moai-open-12-34", "themes", "open"):
                    gate()
            self.assertIs(caught.exception, original)
            self.assertEqual(events[-1], "diagnose")

    def test_failed_capture_still_saves_bounded_native_unit_readback(self):
        namespace = self.helpers()
        with tempfile.TemporaryDirectory(prefix="moos-close-evidence-") as directory:
            capture = Mock(side_effect=SystemExit("fixture display ended"))
            query = Mock(return_value=(1, "fixture retained helper", "fixture journal unreadable"))
            namespace.update(capture=capture, evidence=Path(directory), ssh_exec=query,
                             app_close_diagnosis="read-only named-unit diagnostic")
            namespace["collect_app_close_diagnostics"]("moai-open-12-34", "themes", "open")
            query.assert_called_once_with("read-only named-unit diagnostic", ["moai-open-12-34"],
                                          30, desktop_user=True)
            path = Path(directory) / "installed-app-themes-open-close-failed.txt"
            text = path.read_text()
            self.assertIn("diagnosis-exit=1", text)
            self.assertIn("fixture retained helper", text)
            self.assertIn("fixture journal unreadable", text)
            self.assertFalse((Path(directory) / "installed-login.ppm").exists())


if __name__ == "__main__":
    unittest.main()
