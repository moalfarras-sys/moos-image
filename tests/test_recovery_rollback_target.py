#!/usr/bin/env python3
"""Gate: MoOS Recovery must name the PRIOR deployment as the rollback target,
never a staged (pending) update.

WHY THIS EXISTS

Recovery is the calmest, most trust-critical screen in the OS: "if the last update
broke something, go back". It reads rpm-ostree's deployment list and shows the user
the version rollback would return them to.

rpm-ostree lists a freshly *staged* update at index 0 — BEFORE the booted deployment.
`bootc rollback` goes the OTHER way, to the prior deployment. The old selection loop
took "the first deployment that isn't booted", so the moment an update was staged (by
`moos-update` or `moai-do update`) it picked the staged update — telling the user
"roll back to <the newer version>", the exact opposite of what the button does, on the
one screen that must never mislead.

This imports the REAL deployments() from the shipped script (stubbing its GTK imports,
which the function itself does not use) and drives it with a synthetic rpm-ostree
payload that has a staged update — the condition under which the bug appears.
"""

import importlib.util
import json
import subprocess
import sys
import types
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/bin/moos-rollback"


def load_module():
    """Import moos-rollback without a real GTK/moos_ui2 present."""
    gi = types.ModuleType("gi")
    gi.require_version = lambda *a, **k: None
    repo = types.ModuleType("gi.repository")
    repo.GLib = types.SimpleNamespace(
        markup_escape_text=lambda s: s,
        Error=RuntimeError,
        IO_IN=1,
        IO_HUP=2,
        IO_ERR=4,
        io_add_watch=lambda *_a, **_k: None,
        timeout_add=lambda *_a, **_k: None,
    )
    repo.Gtk = types.SimpleNamespace(Label=object)
    gi.repository = repo
    # The script ends with `Recovery().run()` and has no __main__ guard, so importing
    # it constructs and "runs" the app. Make MoOSApp a no-op base so that import is
    # harmless and never touches GTK; deployments() is a module-level function either way.
    class _StubApp:
        def __init__(self, *a, **k):
            pass

        def run(self, *a, **k):
            return 0

    moos_ui2 = types.ModuleType("moos_ui2")
    moos_ui2.MoOSApp = _StubApp
    moos_ui2.local_text = lambda _arabic, english: english
    moos_ui2.logical_start = lambda: 0.0
    stubs = {"gi": gi, "gi.repository": repo, "moos_ui2": moos_ui2}
    saved = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        # The script has no .py extension, so give importlib an explicit source loader.
        loader = SourceFileLoader("_moos_rollback_under_test", str(SCRIPT))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module
    finally:
        for name, prior in saved.items():
            if prior is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior


def load_deployments():
    """Import moos-rollback's deployments() without a real GTK/moos_ui2 present."""
    return load_module().deployments


def run_with(deployments_payload):
    fake = mock.Mock()
    fake.returncode = 0
    fake.stdout = json.dumps({"deployments": deployments_payload})
    deployments = load_deployments()
    with mock.patch("subprocess.run", return_value=fake):
        return deployments()


def main() -> int:
    if not SCRIPT.is_file():
        print(f"GATE FAIL: {SCRIPT.relative_to(ROOT)} is missing — Recovery has no source.")
        return 1

    errors = []

    def check(name, deps, want_booted, want_target, want_queued):
        got_booted, got_target, got_queued = run_with(deps)
        if got_booted != want_booted:
            errors.append(f"{name}: booted read as {got_booted!r}, expected {want_booted!r}")
        if got_target != want_target:
            errors.append(f"{name}: target read as {got_target!r}, expected {want_target!r}")
        if got_queued != want_queued:
            errors.append(f"{name}: already-queued read as {got_queued!r}, expected {want_queued!r}")

    # 1. An update is staged (index 0), booted index 1, prior index 2. The staged entry is
    #    NEWER than what is running, so it can never be what rollback returns to.
    check("staged update queued",
          [{"version": "44.NEW", "booted": False, "staged": True},
           {"version": "44.BOOTED", "booted": True, "staged": False},
           {"version": "44.PRIOR", "booted": False, "staged": False}],
          "44.BOOTED", "44.PRIOR", False)

    # 2. The ordinary case.
    check("ordinary",
          [{"version": "44.BOOTED", "booted": True, "staged": False},
           {"version": "44.PRIOR", "booted": False, "staged": False}],
          "44.BOOTED", "44.PRIOR", False)

    # 3. THE ANSWER IS NOT THE LAST ENTRY. Three deployments: rollback goes to the one right
    #    after booted, not to the oldest. A "pick the oldest non-booted" implementation passes
    #    every test above and fails here — which is exactly how a wrong version shipped green.
    check("three deployments, target is not last",
          [{"version": "44.BOOTED", "booted": True, "staged": False},
           {"version": "44.PRIOR", "booted": False, "staged": False},
           {"version": "44.OLDEST", "booted": False, "staged": False}],
          "44.BOOTED", "44.PRIOR", False)
    check("staged + three, target is not last",
          [{"version": "44.NEW", "booted": False, "staged": True},
           {"version": "44.BOOTED", "booted": True, "staged": False},
           {"version": "44.PRIOR", "booted": False, "staged": False},
           {"version": "44.PINNED", "booted": False, "staged": False, "pinned": True}],
          "44.BOOTED", "44.PRIOR", False)

    # 4. A ROLLBACK IS ALREADY QUEUED — booted is no longer the default entry.
    #    `man rpm-ostree`: "If the current default is booted, then set the default to the
    #    previous entry. Otherwise, make the currently booted tree the default." So here the
    #    button CANCELS the queued rollback, and the screen must say what will actually boot.
    #    Reporting None here told a user mid-rescue "no previous version on this machine" and
    #    greyed out the only button.
    check("rollback already queued",
          [{"version": "44.PRIOR", "booted": False, "staged": False},
           {"version": "44.BOOTED", "booted": True, "staged": False}],
          "44.BOOTED", "44.PRIOR", True)

    # 5. Nothing to roll back to: say so rather than inventing a target.
    check("single deployment", [{"version": "44.ONLY", "booted": True, "staged": False}],
          "44.ONLY", None, False)

    # 6. TWO DEPLOYMENTS SHARING A BASE VERSION. Layered packages do not change the version
    #    string, so both cards would render the same bold text and the screen would say
    #    "you are running X" / "rollback returns you to X". The labels must differ.
    b6, t6, _ = run_with([
        {"version": "44.SAME", "checksum": "aaaaaaaaaaaabbbb", "booted": True, "staged": False},
        {"version": "44.SAME", "checksum": "ccccccccccccdddd", "booted": False, "staged": False},
    ])
    if b6 == t6:
        errors.append(f"two deployments with the same base version both render as {b6!r} — the "
                      f"user cannot tell which system is which on the rescue screen; "
                      f"disambiguate with the commit")

    # 7. EVERY RETURN MUST BE A 3-TUPLE, INCLUDING THE FAILURE PATHS.
    #
    #    Recovery's call site is `booted, target, queued = deployments()`. When the third
    #    element was added, two early returns kept returning pairs — `rpm-ostree status`
    #    exiting non-zero, and it failing to run or emitting unparseable JSON. Python does
    #    not degrade there; it raises ValueError and the window never draws.
    #
    #    Read what those two conditions actually describe: an rpm-ostree that is unwell. That
    #    is the only reason anybody opens Recovery. The screen worked on every healthy machine
    #    and crashed on the broken one, which is the inverse of its whole purpose, and no test
    #    here noticed because all six cases above hand it well-formed JSON and returncode 0.
    #
    #    So this case does not check the VALUES. It unpacks exactly the way Recovery does, and
    #    it does that for each way the command can let us down.
    def unpack_check(name, *, returncode=0, stdout="", raises=None):
        fake = mock.Mock()
        fake.returncode = returncode
        fake.stdout = stdout
        deployments = load_deployments()
        patch = (mock.patch("subprocess.run", side_effect=raises) if raises
                 else mock.patch("subprocess.run", return_value=fake))
        with patch:
            result = deployments()
        try:
            booted, target, queued = result
        except (ValueError, TypeError) as exc:
            errors.append(f"{name}: deployments() returned {result!r}, which Recovery cannot "
                          f"unpack ({exc}) — the rescue screen fails to open on precisely the "
                          f"machine that needs it")
            return
        if (booted, target, queued) != (None, None, False):
            errors.append(f"{name}: expected (None, None, False) when the state is unreadable, "
                          f"got {(booted, target, queued)!r}")

    unpack_check("rpm-ostree exits non-zero", returncode=1)
    unpack_check("rpm-ostree is not installed", raises=OSError("No such file or directory"))
    unpack_check("rpm-ostree times out", raises=subprocess.TimeoutExpired("rpm-ostree", 25))
    unpack_check("rpm-ostree emits unparseable JSON", stdout="<html>gateway timeout</html>")
    unpack_check("JSON parses but names no booted deployment",
                 stdout=json.dumps({"deployments": [{"version": "44.orphan"}]}))

    # 8. THE QUEUED STATE IS A CANCELLATION, ALL THE WAY THROUGH THE UI.
    #
    # The button already said "Cancel the queued rollback", but the confirmation
    # and success screen used to say "Go back" and "Restart to return to the
    # previous version". That made the most trust-sensitive screen contradict
    # itself. Exercise the real callbacks so the action, confirmation, and final
    # state cannot drift independently again.
    module = load_module()

    class FakeAlertDialog:
        last = None

        def __init__(self):
            FakeAlertDialog.last = self
            self.message = ""
            self.detail = ""
            self.buttons = []

        def set_message(self, value):
            self.message = value

        def set_detail(self, value):
            self.detail = value

        def set_buttons(self, value):
            self.buttons = value

        def set_cancel_button(self, _value):
            pass

        def set_default_button(self, _value):
            pass

        def choose(self, _win, _cancellable, callback):
            self.callback = callback

        def choose_finish(self, result):
            return result

    class FakeWidget:
        def __init__(self):
            self.sensitive = True
            self.visible = False
            self.started = False
            self.text = ""
            self.label = ""
            self.markup = ""
            self.classes = []

        def set_sensitive(self, value):
            self.sensitive = value

        def set_visible(self, value):
            self.visible = value

        def start(self):
            self.started = True

        def stop(self):
            self.started = False

        def add_css_class(self, value):
            self.classes.append(value)

        def set_text(self, value):
            self.text = value

        def set_label(self, value):
            self.label = value

        def set_markup(self, value):
            self.markup = value

    module.Gtk.AlertDialog = FakeAlertDialog
    recovery = module.Recovery()
    recovery.win = object()
    recovery.rollback_queued = True
    recovery.on_rollback(None)
    dialog = FakeAlertDialog.last
    if "Cancel the queued rollback?" not in dialog.message:
        errors.append("queued rollback confirmation still describes starting a rollback")
    if not dialog.buttons or "Cancel rollback" not in dialog.buttons[-1]:
        errors.append("queued rollback confirmation action does not say it cancels rollback")
    if "keep the version you are running" not in dialog.detail:
        errors.append("queued rollback confirmation does not name the version that will boot")

    recovery.back_btn = FakeWidget()
    recovery.spinner = FakeWidget()
    recovery.status = FakeWidget()
    recovery.target_heading = FakeWidget()
    recovery.target_version = FakeWidget()
    recovery.reboot_btn = FakeWidget()
    recovery.booted_label = "44.BOOTED"
    recovery.say = lambda _line: None
    launched = []
    recovery.run_async = lambda cmd, done: launched.append((cmd, done))
    recovery._confirmed(dialog, 1)
    if not recovery.action_cancels_rollback:
        errors.append("confirmation did not snapshot that the queued action is a cancellation")
    if not launched or launched[0][0] != ["pkexec", "bootc", "rollback"]:
        errors.append("confirmed Recovery action did not launch the fixed bootc rollback command")
    else:
        launched[0][1](0)
        if "Rollback cancelled." not in recovery.status.text:
            errors.append("successful queued cancellation still claims a rollback was prepared")
        if recovery.target_version.markup != "<b>44.BOOTED</b>":
            errors.append("successful cancellation does not update the next-boot version to current")

    # 9. THE PRIVILEGED ACTION MUST NOT FREEZE GTK.
    #
    # `subprocess.run(timeout=180)` in the confirmation callback froze painting
    # while both Polkit and bootc ran. Assert the real async helper returns after
    # registering a GLib watch, before it waits for the process, then stream and
    # finish it by driving that watch exactly as GTK would.
    module = load_module()
    recovery = module.Recovery()
    output = []
    completed = []
    recovery.say = output.append
    proc = mock.Mock()
    proc.stdout = mock.Mock()
    proc.stdout.readline.side_effect = ["first line\n", ""]
    proc.returncode = 0
    proc.poll.side_effect = [None, 0]
    watch = {}
    timeout = {}

    def add_watch(source, condition, callback):
        watch.update(source=source, condition=condition, callback=callback)
        return 1

    def add_timeout(interval, callback):
        timeout.update(interval=interval, callback=callback)
        return 2

    module.GLib.io_add_watch = add_watch
    module.GLib.timeout_add = add_timeout
    with mock.patch.object(module.subprocess, "Popen", return_value=proc) as popen:
        recovery.run_async(["pkexec", "bootc", "rollback"], completed.append)

    popen.assert_called_once()
    if proc.poll.called:
        errors.append("Recovery polls bootc before returning control to GTK")
    if watch.get("source") is not proc.stdout:
        errors.append("Recovery did not register bootc output with GLib's main loop")
    elif not watch["callback"](proc.stdout, module.GLib.IO_IN):
        errors.append("Recovery stopped its output watch before the process completed")
    elif output != ["first line"]:
        errors.append(f"Recovery did not stream bootc output into the UI: {output!r}")
    elif watch["callback"](proc.stdout, module.GLib.IO_HUP):
        errors.append("Recovery kept its GLib watch alive after bootc completed")
    elif completed:
        errors.append("Recovery reported completion while bootc was still running")
    elif timeout.get("interval") != 50:
        errors.append("Recovery did not defer an early-stdout-close process to GLib")
    elif timeout["callback"]():
        errors.append("Recovery kept polling after bootc exited")
    elif completed != [0]:
        errors.append("Recovery's GLib watch did not deliver bootc completion")

    if errors:
        print("GATE FAIL: MoOS Recovery target or interaction contract regressed.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: Recovery names the right deployment, describes queued cancellation accurately, "
          "and streams bootc through GLib without blocking GTK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
