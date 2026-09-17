#!/usr/bin/env python3
"""Gate: the CI proof channel waits for the network instead of racing it, and names its failures.

WHY THIS EXISTS

`moos-ci-runtime-proof.service` is the fixture that lets the QCOW2 and ISO proofs reach a booted
MoOS over SSH: on a disposable CI disk it starts sshd and adds ONE source-scoped firewall rule to
the zone of the interface that carries the default route.

It read that route ONCE. MoOS disables NetworkManager-wait-online for boot speed, so nothing
orders the helper after DHCP. On a first boot sshd generates host keys for seconds before the
read and the lease is there; on every later boot nothing delays it. A read that finds no route
fails the oneshot, the rule is never added, and the channel stays shut for that whole boot.

That is plan row P0.8: the ISO installed-reboot proof timed out "during banner exchange" on three
release candidates out of four, for its whole 1000 s, while sshd listened and QGA called the boot
healthy. The first ISO proof run with the wait (35265328509) caught the race in the act, because
the helper now speaks on the console: on the first boot the route line follows "daemons active"
by 16 ms; on the SECOND boot by 1.02 s — the first read came back empty, and one retry found the
route. The old helper died on that empty read.

Two lessons are recorded because both cost time. The evidence that seemed to clear the helper —
`systemctl --failed` was empty in the failed runs — came from the harness's QGA context, which
SELinux confines: it cannot read unit state, so its silence meant nothing. And the fix that was
written on the more plausible theory (one slirp forward per boot, as the QCOW2 proof does) was
measured by that same run as irrelevant: the first-boot forward was alive after the reboot.
A fixture whose silent failure costs a two-hour release cycle must not race and must not be mute.

This gate runs the SHIPPED helper, not a copy:

  * the route wait is lifted out of the file and run against an `ip` that has no default route
    for its first N calls — it must keep asking, return the interface, and give up (non-zero)
    when the route never comes;
  * where bubblewrap can give the helper the two facts it reads directly (/proc/cmdline and
    /home/*/.ssh/authorized_keys), the WHOLE helper runs end to end against recording stubs:
    late route -> rule added to the interface's zone and read back; no route -> it fails AT a
    named stage and adds nothing; rule accepted but absent on read-back -> it fails;
  * the unit must send that output to the console, where the harness can always read it.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "system_files/usr/libexec/moos-ci-runtime-proof-firewall"
UNIT = ROOT / "system_files/usr/lib/systemd/system/moos-ci-runtime-proof.service"
BASH = shutil.which("bash")
RULE = 'rule family="ipv4" source address="10.0.2.2/32" service name="ssh" accept'


def lifted_route_wait() -> str:
    """The shipped `default_route_iface` function, verbatim."""
    text = HELPER.read_text(encoding="utf-8")
    match = re.search(r"^default_route_iface\(\) \{\n.*?^\}\n", text, flags=re.DOTALL | re.MULTILINE)
    if not match:
        raise AssertionError(
            "moos-ci-runtime-proof-firewall has no default_route_iface(): the default route is "
            "read once again, and nothing orders that read after DHCP (wait-online is disabled)")
    return match.group(0)


def write_stub(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/usr/bin/env bash\n" + textwrap.dedent(body), encoding="utf-8", newline="\n")
    path.chmod(0o755)


@unittest.skipUnless(BASH and sys.platform.startswith("linux"), "needs bash on Linux")
class RouteWait(unittest.TestCase):
    def run_wait(self, routeless_calls: int, attempts: int) -> tuple[int, str, int]:
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            stubs = work / "bin"
            stubs.mkdir()
            counter = work / "ip-calls"
            counter.write_text("0")
            write_stub(stubs, "ip", f"""
                calls=$(( $(cat "{counter}") + 1 )); echo "$calls" > "{counter}"
                [ "$calls" -gt {routeless_calls} ] || exit 0
                echo "default via 10.0.2.2 dev enp0s2 proto dhcp src 10.0.2.15 metric 100"
                echo "default via 192.168.9.1 dev wlp3s0 proto dhcp metric 600"
            """)
            write_stub(stubs, "sleep", "exit 0\n")
            script = lifted_route_wait() + f"\ndefault_route_iface {attempts}\n"
            done = subprocess.run(
                [BASH, "-euo", "pipefail", "-c", script], text=True, capture_output=True, timeout=60,
                env={"PATH": f"{stubs}:{os.environ['PATH']}"}, check=False)
            return done.returncode, done.stdout.strip(), int(counter.read_text())

    def test_it_keeps_asking_until_the_lease_arrives(self) -> None:
        code, iface, calls = self.run_wait(routeless_calls=7, attempts=120)
        self.assertEqual((code, iface), (0, "enp0s2"))
        self.assertEqual(calls, 8, "it must stop asking the moment a route exists")

    def test_a_route_that_is_already_there_costs_one_read(self) -> None:
        self.assertEqual(self.run_wait(routeless_calls=0, attempts=120), (0, "enp0s2", 1))

    def test_it_gives_up_and_says_so_with_its_exit_status(self) -> None:
        code, iface, calls = self.run_wait(routeless_calls=10**6, attempts=5)
        self.assertNotEqual(code, 0)
        self.assertEqual(iface, "")
        self.assertEqual(calls, 5, "the wait must be bounded by the attempts it was given")


@unittest.skipUnless(BASH and sys.platform.startswith("linux") and shutil.which("bwrap"),
                     "the end-to-end run needs bubblewrap to supply /proc/cmdline and /home")
class WholeHelper(unittest.TestCase):
    def run_helper(self, *, routeless_calls: int, rule_sticks: bool = True,
                   marked_keys: int = 1) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            stubs, home, state = work / "bin", work / "home", work / "state"
            for directory in (stubs, home, state):
                directory.mkdir()
            for index in range(marked_keys):
                ssh = home / f"user{index}" / ".ssh"
                ssh.mkdir(parents=True)
                (ssh / "authorized_keys").write_text("ssh-ed25519 AAAA moos-ci-runtime-proof\n")
            (work / "cmdline").write_text("root=UUID=x rw quiet moos.ci-runtime-proof=1 console=ttyS0\n")
            (state / "ip-calls").write_text("0")
            write_stub(stubs, "systemd-detect-virt", "echo kvm\n")
            write_stub(stubs, "systemctl", f"""
                echo "systemctl $*" >> "{state}/calls"
                exit 0
            """)
            write_stub(stubs, "sleep", "exit 0\n")
            write_stub(stubs, "ip", f"""
                [ "$*" = "-4 route show default" ] || exit 0
                calls=$(( $(cat "{state}/ip-calls") + 1 )); echo "$calls" > "{state}/ip-calls"
                [ "$calls" -gt {routeless_calls} ] || exit 0
                echo "default via 10.0.2.2 dev enp0s2 proto dhcp src 10.0.2.15 metric 100"
            """)
            add_action = f'echo "$*" > "{state}/rule"' if rule_sticks else ":"
            write_stub(stubs, "firewall-cmd", f"""
                echo "firewall-cmd $*" >> "{state}/calls"
                case "$*" in
                    --get-zone-of-interface=enp0s2) echo moos-desktop ;;
                    --get-default-zone) echo FALLBACK ;;
                    *--add-rich-rule=*) {add_action} ;;
                    *--query-rich-rule=*) [ -s "{state}/rule" ] ;;
                esac
            """)
            done = subprocess.run(
                ["bwrap", "--dev-bind", "/", "/", "--bind", str(home), "/home",
                 "--ro-bind", str(work / "cmdline"), "/proc/cmdline",
                 "--setenv", "PATH", f"{stubs}:{os.environ['PATH']}",
                 BASH, str(HELPER)],
                text=True, capture_output=True, timeout=120, check=False)
            if done.returncode != 0 and re.search(
                    r"bwrap: .*(namespace|Operation not permitted|Permission denied|setting up uid map)",
                    done.stderr):
                self.skipTest("this kernel forbids unprivileged user namespaces")
            calls = (state / "calls").read_text() if (state / "calls").exists() else ""
            return done.returncode, done.stdout + done.stderr, calls

    def test_a_late_lease_still_opens_the_channel(self) -> None:
        code, said, calls = self.run_helper(routeless_calls=9)
        self.assertEqual(code, 0, said)
        self.assertIn(f"firewall-cmd --zone=moos-desktop --add-rich-rule={RULE}", calls)
        self.assertIn(f"firewall-cmd --zone=moos-desktop --query-rich-rule={RULE}", calls)
        self.assertNotIn("FALLBACK", calls)
        self.assertIn("IPv4 default route is on enp0s2", said)
        self.assertIn("channel ready", said)

    def test_no_route_fails_at_a_named_stage_and_opens_nothing(self) -> None:
        code, said, calls = self.run_helper(routeless_calls=10**6)
        self.assertNotEqual(code, 0)
        self.assertIn("FAILED at default route", said)
        self.assertNotIn("--add-rich-rule", calls)

    def test_a_rule_that_did_not_stick_is_a_failure(self) -> None:
        code, said, _calls = self.run_helper(routeless_calls=0, rule_sticks=False)
        self.assertNotEqual(code, 0)
        self.assertIn("FAILED at rule read-back", said)

    def test_two_marked_keys_refuse_before_any_daemon_starts(self) -> None:
        code, said, calls = self.run_helper(routeless_calls=0, marked_keys=2)
        self.assertNotEqual(code, 0)
        self.assertIn("FAILED at key marker", said)
        self.assertEqual(calls, "", "nothing may be started or opened when the guard refuses")


class UnitContract(unittest.TestCase):
    def test_the_route_is_never_read_once_at_top_level(self) -> None:
        body = HELPER.read_text(encoding="utf-8").replace(lifted_route_wait(), "")
        code = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("#"))
        self.assertNotIn("route show default", code,
                         "read the default route only through default_route_iface(): nothing "
                         "orders a single read after DHCP, because wait-online is disabled")
        self.assertRegex(code, r'iface="\$\(default_route_iface \d+\)"')

    def test_the_unit_speaks_on_the_console(self) -> None:
        unit = UNIT.read_text(encoding="utf-8")
        for key in ("StandardOutput=journal+console", "StandardError=journal+console"):
            self.assertIn(key, unit, "the serial log is the only record the ISO harness always "
                                     "keeps; SELinux denies its QGA context the journal")
        # Inert everywhere else: the guards that make it so must survive this change.
        for guard in ("ConditionKernelCommandLine=moos.ci-runtime-proof=1", "ConditionVirtualization=yes"):
            self.assertIn(guard, unit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
