#!/usr/bin/env python3
"""Contracts and executable SSH identity checks for the final-ISO proof."""

import ast
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
