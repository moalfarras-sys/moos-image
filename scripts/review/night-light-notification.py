#!/usr/bin/env python3
"""Qualify the fixed native notification on a private bus, never the owner's.

Compile night-light-watcher.cpp with the existing development toolbox's Qt6Core
and KF6ConfigCore headers/libraries; run that binary here against the host's
runtime libraries. --output is a private executed receipt, not OS delivery.
"""
import argparse
import json
import os
from pathlib import Path
import runpy
import select
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def worker(watcher):
    config = Path(os.environ["XDG_CONFIG_HOME"]) / "kwinrc"
    config.write_text("[NightColor]\nActive=false\nMode=Constant\n")
    process = subprocess.Popen([watcher], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def event(timeout=3):
        if not select.select([process.stdout], [], [], timeout)[0]:
            raise RuntimeError("native KConfigWatcher did not publish within the bound")
        return json.loads(process.stdout.readline())

    try:
        ready = event()
        assert ready["event"] == "ready" and ready["active"] is False, ready
        libraries = sorted({line.split()[-1] for line in Path(f"/proc/{process.pid}/maps").read_text().splitlines()
                            if "/libKF6ConfigCore.so." in line})
        assert len(libraries) == 1, libraries
        # Create the original stuck-state precondition without notifying the watcher.
        subprocess.run(["kwriteconfig6", "--file", "kwinrc", "--group", "NightColor",
                        "--key", "Active", "--type", "bool", "true"], check=True, timeout=5)
        assert not select.select([process.stdout], [], [], 0.2)[0], "unnotified write unexpectedly published"
        before = config.read_bytes(), config.stat().st_mtime_ns
        module = runpy.run_path(str(ROOT / "system_files/usr/bin/moos-control"), run_name="private_notification")
        notify = module["night_light_notify"]
        execute = notify.__globals__["run"]
        notify()
        changed = event()
        assert changed["event"] == "changed" and changed["group"] == "NightColor", changed
        assert set(changed["keys"]) == {"Active", "Mode"}, changed
        assert changed["active"] is True and changed["mode"] == "Constant", changed
        negatives = []
        replays = []
        for kind in ("wrong-path", "wrong-key-type"):
            def wrong(argv, **kwargs):
                argv = list(argv)
                if kind == "wrong-path":
                    argv[3] = "/not_kwinrc"
                else:
                    argv = argv[:6] + ["a{sas}", "1", "NightColor", "2", "Active", "Mode"]
                return execute(argv, **kwargs)
            notify.__globals__["run"] = wrong
            notify()
            assert not select.select([process.stdout], [], [], 0.2)[0], kind + " reached the watcher"
            negatives.append(kind)
            notify.__globals__["run"] = execute
            if kind == "wrong-path":
                notify()
                replay = event()
                assert replay == changed, replay
                replays.append(replay)
            # The ill-typed control is terminal. On this native Qt/KConfig,
            # later valid source AND native-kwriteconfig notifications timed
            # out after it. Preserve that refusal; recovery is not qualified.
        assert before == (config.read_bytes(), config.stat().st_mtime_ns), "notification rewrote the file"
        print(json.dumps({"scope": "native KConfigWatcher reload on private bus; no owner KWin/device action",
                          "ready": ready, "changed": changed, "refused_notifications": negatives,
                          "valid_replays_after_negatives": len(replays),
                          "recovery_after_ill_typed_notification": "unqualified; retained source/native-producer replay timeouts",
                          "loaded_libraries": libraries, "content_and_mtime_unchanged": True,
                          "native_package": subprocess.check_output(["rpm", "-q", "kf6-kconfig"], text=True).strip()}))
    finally:
        process.terminate()
        remaining, errors = process.communicate(timeout=3)
        if sys.exc_info()[0] is not None:
            print("native watcher diagnostics: " + remaining + errors, file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watcher", required=True)
    parser.add_argument("--output")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    watcher = str(Path(args.watcher).resolve(strict=True))
    if args.worker:
        worker(watcher)
        return
    if not args.output:
        parser.error("--output is required")
    with tempfile.TemporaryDirectory(prefix="moos-night-notify-") as temporary:
        root = Path(temporary)
        for folder in ("config", "data", "cache", "runtime"):
            (root / folder).mkdir(mode=0o700)
        bus = root / "bus.conf"
        bus.write_text('<busconfig><type>session</type><listen>unix:tmpdir=/tmp</listen>'
                       '<auth>EXTERNAL</auth><policy context="default"><allow send_destination="*"/>'
                       '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        env = {**os.environ, "HOME": str(root), "XDG_CONFIG_HOME": str(root / "config"),
               "XDG_DATA_HOME": str(root / "data"), "XDG_DATA_DIRS": str(root / "data"),
               "XDG_CACHE_HOME": str(root / "cache"), "XDG_RUNTIME_DIR": str(root / "runtime")}
        result = subprocess.run(["dbus-run-session", "--config-file", str(bus), "--", sys.executable,
                                 __file__, "--worker", "--watcher", watcher], env=env,
                                capture_output=True, text=True, timeout=20)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        proof = json.loads(result.stdout)
        Path(args.output).write_text(json.dumps(proof, indent=2) + "\n")
        print(json.dumps(proof))


if __name__ == "__main__":
    main()
