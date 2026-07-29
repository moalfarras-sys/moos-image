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

    # 1. The bug condition: an update is staged (index 0), booted is index 1, prior is index 2.
    booted, target = run_with([
        {"version": "44.NEW", "booted": False, "staged": True},
        {"version": "44.BOOTED", "booted": True, "staged": False},
        {"version": "44.PRIOR", "booted": False, "staged": False},
    ])
    if booted != "44.BOOTED":
        errors.append(f"booted misread as {booted!r}, expected '44.BOOTED'")
    if target == "44.NEW":
        errors.append("rollback target is the STAGED update '44.NEW' — that is the version "
                      "rollback moves AWAY from, shown as the thing it returns to. The "
                      "selection loop must skip staged deployments.")
    elif target != "44.PRIOR":
        errors.append(f"rollback target is {target!r}, expected the prior deployment '44.PRIOR'")

    # 2. The normal condition (no staged update): booted index 0, prior index 1 — still correct.
    booted2, target2 = run_with([
        {"version": "44.BOOTED", "booted": True, "staged": False},
        {"version": "44.PRIOR", "booted": False, "staged": False},
    ])
    if target2 != "44.PRIOR":
        errors.append(f"with no staged update, target is {target2!r}, expected '44.PRIOR'")

    # 3. THE SAME LAYOUT WITH NO `staged` KEY AT ALL. rpm-ostree's JSON is not guaranteed to
    #    carry that flag — on this machine's own output the deployments expose only `booted`.
    #    A reader that depends on the flag silently reverts to the original bug the moment the
    #    key is absent, so the positional rule (the rollback target follows the booted entry)
    #    must stand on its own.
    booted3, target3 = run_with([
        {"version": "44.NEW"},                       # queued for next boot, unflagged
        {"version": "44.BOOTED", "booted": True},
        {"version": "44.PRIOR"},
    ])
    if booted3 != "44.BOOTED":
        errors.append(f"booted misread as {booted3!r} when no staged flag is present")
    if target3 != "44.PRIOR":
        errors.append(f"with no `staged` key present the target is {target3!r}, expected "
                      f"'44.PRIOR'. Anything listed BEFORE the booted deployment is newer than "
                      f"what is running and can never be what rollback returns to — the rule has "
                      f"to be positional, not flag-dependent.")

    # 4. A machine with nothing to roll back to must say so rather than inventing a target.
    booted4, target4 = run_with([{"version": "44.ONLY", "booted": True}])
    if booted4 != "44.ONLY" or target4 is not None:
        errors.append(f"with a single deployment the target must be None, got {target4!r} — "
                      f"Recovery would offer a rollback that cannot happen")

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
