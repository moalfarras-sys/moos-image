#!/usr/bin/env python3
"""Run real setup against a private platform that silently refuses early writes.

No owner bus, session, administrator helper or Android data is contacted. The
platform matches upstream's stopped-session error with exit zero. The old
source fails these controls; a process exit alone never qualifies integration.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/bin/moai-do"

PLATFORM = r'''#!/usr/bin/python3
import json,os,pathlib,sys
path=pathlib.Path(os.environ["ANDROID_FIXTURE_STATE"])
state=json.loads(path.read_text());args=sys.argv[1:]
with open(os.environ["ANDROID_FIXTURE_LOG"],"a") as log:
 log.write(" ".join([pathlib.Path(sys.argv[0]).name,*args])+"\n")
code=0;name=pathlib.Path(sys.argv[0]).name
if name=="systemctl":
 if args[:2]==["enable","--now"] or args[:2]==["is-active","--quiet"]:
  code=0 if state["container_ok"] else 1
 elif args[:2]==["--user","start"]:
  state["starts"]+=1
  if state["fault"]=="restart-failed" and state["starts"]>1:code=1
  else:
   state["running"]=True
   if state["fault"]=="lost-on-restart" and state["starts"]>1:state["properties"]={}
 elif args[:2]==["--user","stop"]:state["running"]=False
elif name=="waydroid":
 if args==["status"]:
  if not state["initialized"]:print("[12:34:56] WayDroid is not initialized, run init")
  else:print("Session: "+("RUNNING" if state["running"] else "STOPPED"))
 elif args[0]=="init":state["initialized"]=True;state["initializations"]+=1
 elif args[:2]==["session","stop"]:state["running"]=False;state["stops"]+=1
 elif args[:2]==["prop","get"]:
  if not state["running"]:print("WayDroid session is stopped",file=sys.stderr)
  elif args[2]=="sys.boot_completed":print("0" if state["fault"]=="boot-incomplete" else "1")
  else:
   print(state["properties"].get(args[2],"false"))
   if state["fault"]=="failed-readback":print("ERROR: failed connection",file=sys.stderr)
 elif args[:2]==["prop","set"]:
  if not state["running"]:
   state["early_writes"]+=1
   print("WayDroid session is stopped",file=sys.stderr)
  elif state["fault"]!="silent-refusal":state["properties"][args[2]]=args[3]
path.write_text(json.dumps(state));sys.exit(code)
'''


def executable(path, body):
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def run(*, initialized=True, running=True, configured=True, container_ok=True,
        fault="", answer="y\n"):
    with tempfile.TemporaryDirectory(prefix="moos-android-setup-") as raw:
        root = Path(raw)
        binary = root / "bin"
        binary.mkdir()
        state = {"initialized": initialized, "running": running, "container_ok": container_ok,
                 "fault": fault, "starts": 0, "stops": 0, "initializations": 0,
                 "early_writes": 0, "properties": {
                     name: "true" for name in ("persist.waydroid.multi_windows",
                                               "persist.waydroid.cursor_on_subsurface")
                 } if configured else {}}
        state_path = root / "state.json"
        state_path.write_text(json.dumps(state))
        log = root / "calls.log"
        for name in ("waydroid", "systemctl"):
            executable(binary / name, PLATFORM)
        executable(binary / "pkexec", '#!/bin/sh\nexec "$@"\n')
        for name in ("logger", "moos-gpu-headroom"):
            executable(binary / name, "#!/bin/sh\nexit 0\n")
        executable(binary / "sleep", "#!/bin/sh\nexec /usr/bin/sleep 0.05\n")
        env = {**os.environ, "PATH": f"{binary}:/usr/bin:/bin", "HOME": raw,
               "XDG_CONFIG_HOME": raw, "XDG_DATA_HOME": raw, "XDG_STATE_HOME": raw,
               "XDG_RUNTIME_DIR": raw, "DBUS_SESSION_BUS_ADDRESS": f"unix:path={raw}/no-bus",
               "DISPLAY": "", "WAYLAND_DISPLAY": "",
               "ANDROID_FIXTURE_STATE": str(state_path), "ANDROID_FIXTURE_LOG": str(log)}
        result = subprocess.run(["bash", str(SCRIPT), "setup-waydroid"], input=answer,
                                text=True, capture_output=True, env=env, timeout=30)
        return result, json.loads(state_path.read_text()), log.read_text() if log.exists() else ""


class AndroidDesktopSetup(unittest.TestCase):
    def test_decline_changes_nothing_and_does_not_open_the_engine(self):
        result, state, log = run(answer="n\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(state["starts"], 0)
        self.assertEqual(state["stops"], 0)
        self.assertNotIn("systemctl enable", log)
        self.assertNotIn("prop set", log)

    def test_container_failure_never_reports_ready(self):
        result, state, log = run(container_ok=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Android جاهز", result.stdout)
        self.assertNotIn("show-full-ui", log)
        self.assertEqual(state["starts"], 0)

    def test_correct_existing_properties_need_no_writes_or_restart(self):
        result, state, log = run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(state["stops"], 0)
        self.assertNotIn("prop set", log)
        self.assertNotIn("show-full-ui", log, "setup must not open a separate phone desktop")
        self.assertIn("systemctl --user start moos-android-session.service", log)
        self.assertNotIn("waydroid session start", log)
        self.assertIn("Android جاهز", result.stdout)

    def test_fresh_setup_applies_readbacks_then_restarts_once(self):
        result, state, log = run(initialized=False, running=False, configured=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(state["initializations"], 1)
        self.assertIn("-c https://ota.waydro.id/system -v https://ota.waydro.id/vendor", log)
        self.assertEqual(state["early_writes"], 0)
        self.assertEqual(state["starts"], 2)
        self.assertEqual(state["stops"], 1)
        self.assertEqual(set(state["properties"].values()), {"true"})
        self.assertLess(log.index("prop get sys.boot_completed"), log.index("prop set"))
        self.assertNotIn("show-full-ui", log)
        self.assertIn("Android جاهز", result.stdout)

    def test_initialized_stopped_setup_does_not_redownload_android(self):
        result, state, log = run(running=False, configured=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(state["initializations"], 0)
        self.assertEqual(state["stops"], 1)
        self.assertEqual(state["early_writes"], 0)

    def test_zero_exit_or_failed_readback_never_becomes_ready(self):
        for fault in ("silent-refusal", "failed-readback", "restart-failed", "lost-on-restart"):
            with self.subTest(fault=fault):
                result, state, log = run(running=False, configured=False, fault=fault)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("Android جاهز", result.stdout)
                self.assertNotIn("show-full-ui", log)

    def test_running_container_is_not_a_booted_android_platform(self):
        result, state, log = run(running=False, configured=False, fault="boot-incomplete")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Android جاهز", result.stdout)
        self.assertNotIn("prop set", log)

    def test_existing_apps_get_the_restart_notice_before_consent(self):
        result, state, log = run(configured=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertLess(result.stdout.index("save their work first"), result.stdout.index("Continue?"))
        self.assertEqual(state["stops"], 1)

    def test_canonical_container_paths_and_boot_service_are_preserved(self):
        self.assertIn("systemctl enable waydroid-container.service",
                      (ROOT / "build_files/build.sh").read_text())
        tmpfiles = (ROOT / "system_files/usr/lib/tmpfiles.d/waydroid.conf").read_text()
        self.assertIn("/var/lib/waydroid", tmpfiles)
        self.assertIn("waydroid_data_t", tmpfiles)


if __name__ == "__main__":
    unittest.main(verbosity=2)
