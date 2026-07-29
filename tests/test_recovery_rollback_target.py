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
import sys
import types
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "system_files/usr/bin/moos-rollback"


def load_deployments():
    """Import moos-rollback's deployments() without a real GTK/moos_ui2 present."""
    gi = types.ModuleType("gi")
    gi.require_version = lambda *a, **k: None
    repo = types.ModuleType("gi.repository")
    repo.GLib = types.SimpleNamespace(markup_escape_text=lambda s: s)
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
    stubs = {"gi": gi, "gi.repository": repo, "moos_ui2": moos_ui2}
    saved = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        # The script has no .py extension, so give importlib an explicit source loader.
        loader = SourceFileLoader("_moos_rollback_under_test", str(SCRIPT))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        return module.deployments
    finally:
        for name, prior in saved.items():
            if prior is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior


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

    if errors:
        print("GATE FAIL: MoOS Recovery would name the wrong rollback target.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: Recovery names the deployment AFTER the booted one — correct with a staged update, "
          "with no staged flag at all, and None when there is nothing to roll back to.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
