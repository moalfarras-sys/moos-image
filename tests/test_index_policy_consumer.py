#!/usr/bin/env python3
"""Gate: the file-indexing budget has exactly one consumer, and no second authority.

WHY THIS EXISTS

`moos-visual-tier` is the single authority on what this machine can afford. Its
`budget()` block publishes `file_indexing` as "content" or "filenames", and its
docstring is explicit that the value is ADVISORY -- the tool deliberately does
not write baloofilerc, because that file has its own owner.

For as long as the budget existed, nothing consumed it. Measured on the live
Oracle A1 on 2026-09-07, on a signed image, tier `essential`:

    budget.file_indexing   filenames
    baloofilerc            only basic indexing=false   <- full content extraction
    baloo_file RSS         439.3 MiB                   <- largest MoOS process
    index database         2.8 GB for 12,460 files

After wiring the consumer, on the same machine, same boot:

    baloo_file RSS         36.1 MiB    (-92%)
    index database         108 MB      (-2.7 GB)
    files indexed          12,468      (filename search intact)

THE FAILURE MODE THIS GUARDS

The obvious "fix" for a slow indexer is to add a core count or a memory
threshold to whichever script is in front of you. Do that and the machine has
two performance authorities that will disagree the moment either is edited --
which is precisely what `moos-visual-tier` centralises to prevent. So this gate
asserts the consumer reads the budget and owns no thresholds of its own, and
that it can never turn indexing off (the filename index is what the Launcher's
file results and the Places page's search promise depend on; content EXTRACTION
is the cost, and that is all that is allowed to stop).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import importlib.machinery
import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSUMER = ROOT / "system_files/usr/libexec/moos-index-policy"
UNIT = ROOT / "system_files/usr/lib/systemd/user/moos-index-policy.service"
AUTHORITY = ROOT / "system_files/usr/bin/moos-visual-tier"
KEY_LABEL = "only basic indexing"


def _load_consumer():
    loader = importlib.machinery.SourceFileLoader("moos_index_policy_probe", str(CONSUMER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def check_effective_config() -> list[str]:
    """Read the setting the way Baloo reads it, stale wrong-group keys included.

    Measured on the A1 (2026-09-12), with balooctl6 as the judge:

        [Basic Settings] only basic indexing=true   -> contentIndexing: yes
        [General]        only basic indexing=true   -> contentIndexing: no

    So the key only takes effect under [General]. The version that wrote
    [Basic Settings] read its own write back through kreadconfig6, reported
    "already applied", and left content extraction running on a machine whose
    budget said filenames. A readback that agrees with a write the application
    ignores is not evidence, which is why this gate asks Baloo itself whenever
    the KDE tools exist and pins the group in source when they do not.
    """
    errors: list[str] = []
    consumer = _load_consumer()

    if consumer.GROUP != "General":
        errors.append(
            f"the consumer writes 'only basic indexing' under {consumer.GROUP!r}; "
            f"Baloo reads it from 'General' and silently ignores any other group")

    with tempfile.TemporaryDirectory(prefix="moos-index-policy-") as directory:
        config = Path(directory) / "baloofilerc"
        old_environ = {k: os.environ.get(k) for k in ("HOME", "XDG_CONFIG_HOME", "LC_ALL")}
        old_which = consumer.shutil.which
        try:
            os.environ.update(HOME=directory, XDG_CONFIG_HOME=directory, LC_ALL="C")

            # Without the KDE tools the consumer parses the file itself. That
            # parser must be group-aware, or a leftover key from the wrong-group
            # version answers for the one Baloo actually consults.
            consumer.shutil.which = lambda _name: None
            config.write_text("[Basic Settings]\nonly basic indexing=true\n"
                              "[General]\nonly basic indexing=false\n")
            if consumer.current_value() != "false":
                errors.append("the file fallback trusts an ignored [Basic Settings] key")
            config.write_text("[Basic Settings]\nonly basic indexing=true\n")
            if consumer.current_value() is not None:
                errors.append("the file fallback invents a [General] value from another group")
            consumer.shutil.which = old_which

            # Where the real tools exist, let Baloo itself judge the write. No
            # daemon is started: kwriteconfig6 touches only this isolated file
            # and `balooctl6 config list` reads it back through Baloo's config.
            if all(shutil.which(tool) for tool in ("kwriteconfig6", "kreadconfig6", "balooctl6")):
                for value, expected in (("true", "no"), ("false", "yes")):
                    config.write_text("[Basic Settings]\nonly basic indexing=true\n"
                                      "[General]\nonly basic indexing=false\n")
                    if not consumer.write_value(value):
                        errors.append(f"the consumer could not write {value} to an isolated config")
                        continue
                    seen = subprocess.run(
                        ["balooctl6", "config", "list", "contentIndexing"],
                        text=True, capture_output=True, timeout=30, check=False).stdout.strip()
                    if seen != expected:
                        errors.append(
                            f"Baloo ignored the consumer's '{KEY_LABEL}={value}': "
                            f"contentIndexing is {seen!r}, expected {expected!r}")
                    if consumer.current_value() != value:
                        errors.append("the consumer's readback disagrees with its effective setting")
            else:
                print("SKIP real Baloo readback: kwriteconfig6/kreadconfig6/balooctl6 not installed")
        finally:
            consumer.shutil.which = old_which
            for key, value in old_environ.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    return errors


def check_diagnostics() -> list[str]:
    """Both diagnostics must judge Baloo against the budget, not against "yes".

    moos-visual-tier publishes filenames-only on the essential tier, so a check
    that demands content extraction everywhere reports a correctly configured
    machine as broken -- and that false failure is what hid the real defect.
    """
    errors: list[str] = []
    for path in (ROOT / "system_files/usr/bin/moos-selfcheck",
                 ROOT / "tests/post-update-check.sh"):
        block = re.search(r"# BEGIN INDEXING BUDGET CHECK\n(.*?)# END INDEXING BUDGET CHECK",
                          path.read_text(encoding="utf-8"), re.S)
        if not block:
            errors.append(f"{path.name}: missing the effective indexing-budget check")
            continue
        harness = ("ok() { echo PASS; }\n"
                   "bad() { echo FAIL; }\n"
                   "moos-visual-tier() { printf '%s\\n' \"$TEST_BUDGET\"; }\n"
                   "balooctl6() { printf '%s\\n' \"$TEST_CONTENT\"; }\n")
        for budget, content, agrees in (("filenames", "no", True),
                                        ("content", "yes", True),
                                        ("filenames", "yes", False),
                                        ("content", "no", False),
                                        ("unknown", "no", False),
                                        ("filenames", "", False)):
            env = os.environ | {
                "TEST_BUDGET": json.dumps({"budget": {"file_indexing": budget}}),
                "TEST_CONTENT": content,
            }
            result = subprocess.run(["bash", "-c", harness + block[1]], env=env,
                                    capture_output=True, text=True, timeout=30, check=False)
            if result.stdout.strip() != ("PASS" if agrees else "FAIL"):
                errors.append(
                    f"{path.name}: budget={budget}, contentIndexing={content!r} should "
                    f"{'pass' if agrees else 'fail'}, got {result.stdout.strip()!r}")
    return errors



def main() -> int:
    errors: list[str] = []

    if not CONSUMER.is_file():
        print("INDEX POLICY GATE FAIL: the consumer is missing entirely; the "
              "published file_indexing budget would go unread again.")
        return 1
    source = CONSUMER.read_text(encoding="utf-8")
    errors.extend(check_effective_config())
    errors.extend(check_diagnostics())

    # The physical first ISO install exposed a lifecycle split: `balooctl6
    # enable` launched baloo_file under flatpak-session-helper.service while
    # kde-baloo.service stayed inactive.  Starting the real unit then failed
    # with "Another instance is running".  Exercise both policy-change paths
    # and require systemd to remain the sole process owner.
    loader = importlib.machinery.SourceFileLoader("moos_index_policy", str(CONSUMER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    policy = importlib.util.module_from_spec(spec)
    loader.exec_module(policy)
    calls: list[tuple[str, ...]] = []
    owner_reply, owner_rc, stop_rc = "b false", 0, 0

    def fake_run(argv, **_kwargs):
        calls.append(tuple(argv))
        class Result:
            returncode = (owner_rc if argv[0].endswith("busctl") else
                          stop_rc if "stop" in argv else 0)
            stdout = owner_reply if argv[0].endswith("busctl") else ""
        return Result()

    old_run = policy.subprocess.run
    old_which = policy.shutil.which
    old_data = policy.os.environ.get("XDG_DATA_HOME")
    try:
        policy.subprocess.run = fake_run
        policy.shutil.which = lambda name: f"/usr/bin/{name}" if name in {"systemctl", "busctl"} else None
        policy.restart_baloo()
        with tempfile.TemporaryDirectory() as tmp:
            policy.os.environ["XDG_DATA_HOME"] = tmp
            database = Path(tmp) / "baloo/index"
            database.parent.mkdir(parents=True)
            database.write_bytes(b"derived-index")
            policy.purge_content_index()
            if database.exists():
                errors.append("the purge path did not remove Baloo's derived index")
            normal_calls = calls[:]

            # An inactive unit can stop successfully while a legacy daemon
            # outside systemd still owns org.kde.baloo. Neither policy-change
            # path may start a duplicate, and purge must preserve its open DB.
            # Unknown ownership and a failed stop must be equally conservative.
            for scenario, owner_reply, owner_rc, stop_rc in (
                ("unmanaged daemon", "b true", 0, 0),
                ("unavailable session bus", "", 1, 0),
                ("malformed ownership answer", "unexpected", 0, 0),
                ("failed managed stop", "b false", 0, 1),
            ):
                database.write_bytes(b"live-derived-index")
                calls.clear()
                policy.restart_baloo()
                policy.purge_content_index()
                if not database.exists() or database.read_bytes() != b"live-derived-index":
                    errors.append(f"{scenario}: the live index was removed or modified")
                if any("start" in call or "restart" in call for call in calls):
                    errors.append(f"{scenario}: a second Baloo daemon could be started")
    finally:
        policy.subprocess.run = old_run
        policy.shutil.which = old_which
        if old_data is None:
            policy.os.environ.pop("XDG_DATA_HOME", None)
        else:
            policy.os.environ["XDG_DATA_HOME"] = old_data

    ownership_query = (
        "/usr/bin/busctl", "--user", "call", "org.freedesktop.DBus",
        "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner", "s",
        "org.kde.baloo",
    )
    wanted_calls = [
        ("/usr/bin/systemctl", "--user", "stop", "kde-baloo.service"),
        ownership_query,
        ("/usr/bin/systemctl", "--user", "start", "kde-baloo.service"),
        ("/usr/bin/systemctl", "--user", "stop", "kde-baloo.service"),
        ownership_query,
        ("/usr/bin/systemctl", "--user", "start", "kde-baloo.service"),
    ]
    if normal_calls != wanted_calls:
        errors.append(
            "Baloo lifecycle must prove the owner left before restarting kde-baloo.service; expected "
            f"{wanted_calls!r}, got {normal_calls!r}"
        )

    # It must ask the authority, by running it -- not re-derive the answer.
    if "moos-visual-tier" not in source:
        errors.append("the consumer does not read moos-visual-tier; a budget it "
                      "does not ask for is a second authority")
    if '["budget"]["file_indexing"]' not in source:
        errors.append("the consumer does not read budget.file_indexing specifically")

    # No thresholds of its own. These are the exact facts moos-visual-tier owns;
    # seeing one here means the two will drift.
    for token in ("cores", "memory_gib", "gpu_class", "FLAGSHIP", "nproc"):
        if re.search(rf"\b{re.escape(token)}\b", source):
            errors.append(
                f"the consumer references {token!r} -- it must apply the budget, "
                f"not re-derive it. Put new reasoning in moos-visual-tier.budget().")

    # It may never disable indexing.
    if re.search(r"Indexing-Enabled", source):
        errors.append("the consumer touches Indexing-Enabled; it may only change "
                      "'only basic indexing'. Disabling the index deletes the "
                      "Launcher's file search from the machines that need it most.")

    # Fail closed: an unreachable authority must leave Baloo alone.
    if "leaving Baloo untouched" not in source:
        errors.append("the consumer must do nothing when the budget cannot be "
                      "read, rather than guess a policy")

    if not UNIT.is_file():
        errors.append("moos-index-policy.service is missing; the consumer would "
                      "never run")
    else:
        unit = UNIT.read_text(encoding="utf-8")
        if "graphical-session.target" not in unit:
            errors.append("the unit is not bound to the graphical session")
        # A rebuild must never compete with the desktop it is meant to help.
        if "IOSchedulingClass=idle" not in unit:
            errors.append("the unit must rebuild the index at idle IO priority")

    # The authority must still be the one publishing the value.
    if AUTHORITY.is_file():
        auth = AUTHORITY.read_text(encoding="utf-8")
        if '"file_indexing"' not in auth:
            errors.append("moos-visual-tier no longer publishes file_indexing; "
                          "the consumer would silently stop applying anything")
        # ai_default advertised a local route that stage C2b removed. It must
        # stay constant until a local engine actually exists again.
        if re.search(r'"ai_default":\s*\(', auth):
            errors.append(
                'budget.ai_default branches on hardware again. Mo AI is '
                'cloud-only (tests/test_moai_cloud_only.py: "the one door to a '
                'local engine is closed"), so a hardware branch here advertises '
                'a route the OS does not have.')

    if errors:
        print("INDEX POLICY GATE FAIL:\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("index policy gate passed (one authority, one consumer, fails closed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
