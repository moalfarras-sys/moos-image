#!/usr/bin/env python3
"""Mo PC Remote recovers from a crash, and stays off when the owner stops it.

WHY THIS GATE EXISTS
--------------------
mo-remote-personal.service has StartLimitIntervalSec=300 / StartLimitBurst=5,
Restart=on-failure and RestartSec=3. Five failures inside fifteen seconds
exhaust the limit and systemd then refuses to start the unit for the rest of
the session. On moos-cloud and on the ARM Oracle host that is not a degraded
feature -- Mo PC Remote IS the screen, so there is no local session left to
type the recovery into.

A hand-written watchdog had lived in ~/.config/systemd/user on the A1 since
2026-08-30 and never reached the image, so generic x86 and NVIDIA had no
recovery path at all. That is the edition drift the shared tree exists to stop.

It also had a defect worth not shipping: it ran `systemctl --user start`
unconditionally once a minute, which also restarts a Remote the OWNER stopped
-- and `systemctl --user stop mo-remote-personal.service` is precisely what
moos-selfcheck tells them to use. On that machine the documented off switch was
a lie; Remote came back within sixty seconds.

systemd separates the two cases, measured on the live A1 with a throwaway unit:

    after `systemctl --user start`   is-active=active    is-failed=active
    after `systemctl --user stop`    is-active=inactive  is-failed=inactive
    after the process crashed        is-active=failed    is-failed=failed

So the contract is: recover `failed`, touch nothing else, and honour `disable`.
This gate drives the real script with a stubbed systemctl and asserts exactly
that, because the whole value of the unit is in which of these it does NOT do.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "system_files/usr/libexec/mo-remote-watchdog"
UNITS = REPO / "system_files/usr/lib/systemd/user"
SERVICE = UNITS / "mo-remote-watchdog.service"
TIMER = UNITS / "mo-remote-watchdog.timer"
X86 = (REPO / "build_files/build.sh").read_text(encoding="utf-8")
ARM = (REPO / "build_files/build-arm.sh").read_text(encoding="utf-8")

STUB = r"""#!/usr/bin/env bash
# Records every systemctl call and answers is-enabled/is-failed from the
# environment, so the script under test sees a scripted machine state.
printf '%s\n' "$*" >> "$CALLS"
args=" $* "
case "$args" in
    *" is-enabled "*) [ "${ENABLED:-yes}" = yes ] ; exit $? ;;
    *" is-failed "*)  [ "${FAILED:-no}"   = yes ] ; exit $? ;;
    *" reset-failed "*) exit 0 ;;
    *" start "*) exit "${START_RC:-0}" ;;
esac
exit 0
"""


def run(enabled="yes", failed="no", start_rc="0"):
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        bindir = tmp / "bin"; bindir.mkdir()
        stub = bindir / "systemctl"
        stub.write_text(STUB); stub.chmod(0o755)
        calls = tmp / "calls.txt"; calls.write_text("")
        env = dict(os.environ)
        env.update(PATH=f"{bindir}:/usr/bin:/bin", CALLS=str(calls),
                   ENABLED=enabled, FAILED=failed, START_RC=start_rc)
        proc = subprocess.run(["bash", str(SCRIPT)], env=env,
                              capture_output=True, text=True, timeout=60)
        return proc, calls.read_text()


class Watchdog(unittest.TestCase):
    def test_a_crashed_remote_is_restarted(self):
        proc, calls = run(enabled="yes", failed="yes")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("reset-failed", calls,
                      "the start limit must be cleared, or `start` is refused "
                      "with 'start request repeated too quickly'")
        self.assertRegex(calls, r"(?m)^--user start mo-remote-personal\.service$")

    def test_a_stopped_remote_is_left_stopped(self):
        """The documented off switch must keep working."""
        proc, calls = run(enabled="yes", failed="no")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("start mo-remote-personal", calls,
                         "an inactive unit was stopped on purpose; restarting "
                         "it breaks `systemctl --user stop`, which selfcheck "
                         "tells the owner to use")
        self.assertNotIn("reset-failed", calls)

    def test_a_disabled_remote_is_never_started(self):
        proc, calls = run(enabled="no", failed="yes")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("start mo-remote-personal", calls,
                         "`disable` is the persistent off switch")

    def test_a_failed_restart_does_not_fail_the_unit(self):
        """A failed oneshot would add a second failed unit to a session that
        already has a problem; the timer is the retry."""
        proc, _ = run(enabled="yes", failed="yes", start_rc="1")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("will retry", proc.stdout)

    def test_the_timer_installs_and_the_service_does_not(self):
        """`systemctl enable` on a unit with no [Install] prints a warning,
        returns 0, and creates NO symlink -- the unit stays static and never
        runs. That shipped once already (4bf615a6, moos-visual-tier)."""
        # Match real section HEADERS at line start: both files discuss
        # "[Install]" and "[Service]" in their comments.
        self.assertIn("\n[Install]\n", TIMER.read_text(),
                      "the timer would never be wired by `systemctl --global enable`")
        self.assertIn("WantedBy=timers.target", TIMER.read_text())
        self.assertNotIn("\n[Install]\n", SERVICE.read_text(),
                         "the oneshot is started by its timer, not by a target")

    def test_the_session_guard_is_in_the_unit_section(self):
        """Condition* in [Service] is ignored: systemd logs 'Unknown key ...
        ignoring' and the guard never applies. That exact mistake fired this
        watchdog's ancestor 12.65s into the session, before the Wayland session
        existed, and took xdg-desktop-portal-kde down with SIGABRT every boot."""
        text = SERVICE.read_text()
        unit_section = text.split("[Unit]\n", 1)[1].split("\n[Service]\n", 1)[0]
        self.assertIn("ConditionPathExists=%t/wayland-0", unit_section,
                      "the graphical-session guard must be in [Unit], and "
                      "%t/wayland-0 is what 'the session is up' means -- "
                      "%t/bus exists before it")

    def test_every_edition_enables_it(self):
        """The whole point is that ARM, generic x86, NVIDIA and cloud stop
        drifting apart. Enabling it in one build script is the bug repeating."""
        self.assertIn("systemctl --global enable mo-remote-watchdog.timer", X86,
                      "the x86 editions (moos, moos-nvidia, moos-cloud) must "
                      "enable the watchdog")
        self.assertIn("mo-remote-watchdog.timer", ARM,
                      "the ARM edition must enable the watchdog")
        # ARM proves the unit exists before enabling it; keep that.
        presence = ARM.split("for unit in", 1)[1].split("; do", 1)[0]
        self.assertIn("mo-remote-watchdog.timer", presence,
                      "ARM must keep the missing-unit FATAL check over it")


if __name__ == "__main__":
    unittest.main(verbosity=2)
