#!/usr/bin/python3
"""moai-do is MoOS's ONLY privileged entry point. This is the test that says so.

Mo AI is a QML app with no process API; every system action it can take goes out as a
`moos://do/<action>` URL, which moos-open hands to `moai-do <action>`, which confirms and
escalates through Polkit. That makes moai-do the whole security surface of Mo AI — and it is
reachable from a web page, because `moos:` is a registered URL scheme. Anything a page can
name, moai-do must either recognise as one of its own actions or refuse outright.

So this asserts the two properties that make that safe, and it asserts them by RUNNING the
script, not by reading it:

  1. Coverage — every action moai-do dispatches has an implementation and is documented in
     its help, and every do/* route moos-open forwards is an action moai-do actually has. A
     route with no action is a Mo AI button that pops "unknown command" and does nothing;
     that shipped once already.
  2. Refusal — anything outside the list is rejected with exit 2 and executes nothing. That
     includes the shapes an attacker would try: shell metacharacters, path traversal in an
     app id, and a flag pretending to be an action.

Nothing here installs, removes, or escalates anything: the only arguments given to moai-do
are ones it must refuse before it reaches a confirmation prompt or pkexec.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import journal_isolation  # noqa: E402

# Every moai-do run below writes its audit line with `logger`. `journalctl -t moai-do` is
# "everything the assistant has done" (moai-do's own words): a gate run must never add a
# refused "rm -rf /" or an approved update to it. They go to this process's recording logger.
journal_isolation.install()
LOGGER_STUB = journal_isolation.stub_dir()

ROOT = Path(__file__).resolve().parent.parent
MOAI_DO = ROOT / "system_files/usr/bin/moai-do"
MOOS_OPEN = ROOT / "system_files/usr/bin/moos-open"

errors = []


def bash_executable() -> str:
    """Use real Git Bash on Windows instead of the WSL app-execution alias."""
    override = os.environ.get("MOOS_TEST_BASH")
    if override:
        return override
    if os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe"
        if candidate.is_file():
            return str(candidate)
    return shutil.which("bash") or "bash"


BASH = bash_executable()


def check(condition, message):
    if not condition:
        errors.append(message)


do_text = MOAI_DO.read_text(encoding="utf-8")
open_text = MOOS_OPEN.read_text(encoding="utf-8")

# ── 1. Coverage ──────────────────────────────────────────────────────────────
# The dispatch arms, i.e. the actions moai-do answers to. Grab the case block, then the
# labels in it — skipping the help/default arms, which are not actions.
dispatch = re.search(r'case "\$cmd" in(.*?)\n    esac', do_text, re.S)
check(dispatch is not None, "moai-do must dispatch on $cmd in a case block")
actions = []
if dispatch:
    for label in re.findall(r'^\s{8}([a-z][a-z|-]*)\)', dispatch.group(1), re.M):
        actions.extend(a for a in label.split("|") if a not in ("help", "-h", "--help"))
check(len(actions) >= 10, f"moai-do should dispatch the full action set, found {actions}")

for action in actions:
    func = "do_" + action.replace("-", "_")
    # hw-report is implemented inline (it execs the Mo AI device panel), so accept either.
    check(f"{func}()" in do_text or f"{action})" in do_text,
          f"moai-do dispatches '{action}' but has no implementation")

usage = re.search(r"usage\(\) \{(.*?)\n\}", do_text, re.S)
check(usage is not None, "moai-do must have a usage() block")
if usage:
    for action in actions:
        check(action in usage.group(1),
              f"moai-do's help must document '{action}' — an action nobody can discover is "
              f"an action nobody uses")

# The do/* routes moos-open FORWARDS to moai-do must be actions moai-do has — every arm that
# reaches moai-do, whether in a terminal (`term moai-do "$tgt"`) or confirmed in the
# background (`moai_do_detached <action>`). Arms that open a page instead (do/hw-report,
# do/setup-brain) are not moai-do's problem.
def case_arms(text: str):
    """(labels, body) for every case arm of moos-open's dispatch."""
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    for match in re.finditer(r"^\s{4}([a-z0-9/*|.-]+)\)(.*?);;", code, re.M | re.S):
        yield [label for label in match.group(1).split("|") if label != "*"], match.group(2)


forwarded_routes = []
for labels, body in case_arms(open_text):
    calls = re.findall(r"(?:moai-do|moai_do_detached)\s+(\"\$tgt\"|[a-z][a-z-]*)", body)
    for call in calls:
        if call == '"$tgt"':
            # The action IS the route's name: only do/<action> labels may forward like this.
            for route in labels:
                check(route.startswith("do/") and "*" not in route,
                      f"moos-open passes URL text of {route} to moai-do as the action")
                forwarded_routes.append(route.removeprefix("do/"))
        else:
            forwarded_routes.append(call)
            for route in labels:
                if route.startswith("do/"):
                    check(route == f"do/{call}",
                          f"{route} runs moai-do {call}, not the action its name promises")
check(len(forwarded_routes) >= 15, f"moos-open forwards too few routes to moai-do: {forwarded_routes}")
for action in forwarded_routes:
    check(action in actions,
          f"moos-open forwards {action} to moai-do, which has no '{action}' action — that "
          f"button pops 'unknown command' and does nothing")

# Every other program that CALLS moai-do must name a real action too. moos-privacy-stop called
# `moai-do remote-stop` for weeks; it did not exist, so the call was refused and swallowed by
# `|| true`, and the stop it promised never happened. Commands only, not comments.
for script in sorted([*(ROOT / "system_files/usr/bin").iterdir(),
                      *(ROOT / "system_files/usr/libexec").iterdir()]):
    if script.name == "moai-do" or not script.is_file():
        continue
    try:
        text = script.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    if text.startswith("#!") and "python" in text.split("\n", 1)[0]:
        # An argv list: ["moai-do", "update"] / ["moai-do", "--confirmed", "update"].
        called = re.findall(r"[\"']moai-do[\"']\s*,\s*(?:[\"']--confirmed[\"']\s*,\s*)?"
                            r"[\"']([a-z][a-z-]+)[\"']", code)
    else:
        # A shell command in command position (start of a line or after ; & | ( && || then do).
        called = re.findall(r"(?:^|[;&|(]|\bthen|\bdo|\belse)\s*(?:command\s+|exec\s+)?"
                            r"moai-do\s+(?:--confirmed\s+)?([a-z][a-z-]+)", code, re.M)
    for action in called:
        check(action in actions,
              f"{script.name} runs `moai-do {action}`, which moai-do does not implement")

# And every `moai-do <action>` the UI NAMES must be real — including the ones inside Mo AI's
# system prompt, which is the assistant telling the user what to type. This is not academic:
# the prompt taught the model to answer "how do I run games?" with `moai-do setup-gaming`, an
# action that did not exist, so the assistant confidently handed out a dead command.
#
# Scan the CODE, not the comments explaining it. This regex reads any "moai-do <word>" in the
# file, and a QML comment is prose: the sentence "each is implemented in moai-do and routed in
# moos-open" makes it demand an action called `and`. That is a gate failing on a file that is
# perfectly correct — the mirror image of the trap in verify_user_experience.py's code(), where
# a comment SATISFIES a gate the code no longer passes. Both come from reading English as code.
#
# The old defence was a denylist — `if named in ("action", "actions")` — which is a losing game:
# it only ever names the prose words someone already tripped over, and the next comment finds
# the next hole. Stripping // comments removes the whole class instead. The denylist stays for
# the words that can still legitimately appear in user-visible STRINGS (which are code, and are
# not stripped): "moai-do <action>" is real placeholder text the prompt shows the user.
def qml_code(text: str) -> str:
    """Drop // line comments so English prose cannot be read as a command."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


for qml in sorted((ROOT / "system_files/usr/share/moos/apps").glob("*/main.qml")):
    source = qml_code(qml.read_text(encoding="utf-8"))
    for named in sorted(set(re.findall(r"moai-do ([a-z][a-z-]+)", source))):
        if named in ("action", "actions"):   # placeholder text in the prompt, not a command
            continue
        check(named in actions,
              f"{qml.parent.name}/main.qml tells the user to run `moai-do {named}`, but that "
              f"is not one of moai-do's actions")

    # The scan above only sees `moai-do <word>` with a real SPACE. But the whitelist that
    # actually decides which run-button appears is a different form — an authoritative regex
    # ALTERNATION whose members are what extractRuns matches:
    #     const re = /moai-do\s+(update|fix-audio|...|setup-brain)\b/g
    # After "moai-do" comes a backslash, not a space, so the space-form scan never matches this
    # line and a member that appears ONLY inside the alternation (fix-audio was exactly that) is
    # validated by nobody. Parse the alternation and assert every member is a real action, so a
    # renamed or typo'd action left stale in the whitelist fails the build instead of shipping a
    # run-button that pops 'unknown command'.
    for alt in re.findall(r"moai-do\\s\+\(([a-z0-9|_-]+)\)", source):
        for member in alt.split("|"):
            check(member in actions,
                  f"{qml.parent.name}/main.qml's run-button whitelist offers `moai-do {member}`, "
                  f"but that is not one of moai-do's actions — the button would pop 'unknown "
                  f"command'")

# ── 2. Refusal — run it ──────────────────────────────────────────────────────
def run(*args):
    """moai-do with no stdin: a prompt would read EOF and cancel, never hang."""
    return subprocess.run([BASH, str(MOAI_DO), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=30,
                          stdin=subprocess.DEVNULL)


for bad in ("rm -rf /",
            "update; rm -rf /",
            "$(reboot)",
            "../../bin/sh",
            "--exec",
            "setup_windows",        # underscore, not the real hyphenated action
            "INSTALL"):             # the list is case-sensitive on purpose
    result = run(bad)
    check(result.returncode == 2,
          f"moai-do must refuse {bad!r} with exit 2, got {result.returncode}")
    check("unknown command" in result.stdout + result.stderr,
          f"moai-do must say why it refused {bad!r}")

# An app id is the one free-form value that reaches moai-do (any web page can put one in a
# moos:// URL), so it is validated twice — here, and again in moos-open. These must all be
# refused BEFORE flatpak, a prompt, or pkexec is ever reached.
for bad_id in ("../../etc/passwd",
               "org.foo; rm -rf ~",
               "org.foo && reboot",
               "$(id)",
               "org foo"):
    result = run("install", bad_id)
    check(result.returncode == 2,
          f"moai-do install must refuse the id {bad_id!r} with exit 2, got {result.returncode}")
    check("invalid app id" in result.stdout + result.stderr,
          f"moai-do install must reject {bad_id!r} as an invalid id")
    check("flatpak install" not in result.stdout,
          f"moai-do must not reach flatpak with the id {bad_id!r}")

# And with no id at all it must ask for one rather than doing anything.
result = run("install")
check(result.returncode == 2, "moai-do install with no id must exit 2")

# Local packages have a stronger contract than a Flatpak id: only an existing,
# owned, non-symlink RPM in a common user folder may even reach signature
# inspection or Polkit. Public moos: URLs cannot turn an arbitrary path into a
# privileged package transaction.
for bad_rpm in ("",
                "../../etc/passwd",
                "/etc/passwd",
                "/tmp/not-a-package.rpm",
                "/var/home/moos/Downloads/pkg.rpm;reboot"):
    result = run("install-rpm", bad_rpm)
    check(result.returncode == 2,
          f"moai-do install-rpm must refuse {bad_rpm!r}, got {result.returncode}")
    check("Choose a regular RPM" in result.stdout + result.stderr,
          f"moai-do install-rpm must explain its safe path policy for {bad_rpm!r}")
    check("rpm-ostree install" not in result.stdout + result.stderr,
          f"moai-do install-rpm must not reach a transaction for {bad_rpm!r}")

# The assistant is a UX client, not a second update implementation. Its unprivileged
# resolver can be doubled, but the path handed to Polkit is fixed to the root-owned
# backend and carries only the digest the user confirmed.
with tempfile.TemporaryDirectory() as tmp:
    bindir = Path(tmp)
    log = bindir / "pkexec.log"
    digest = "sha256:" + "d" * 64
    current = "sha256:" + "b" * 64
    doubles = {
        "moos-image-update": (
            "#!/bin/sh\n"
            f"printf '%s\\n' 'available|moos-nvidia|{current}|{digest}'\n"
        ),
        "pkexec": '#!/bin/sh\nprintf "%s\\n" "$@" > "$MOOS_TEST_PKEXEC_LOG"\n',
    }
    for name, body in doubles.items():
        path = bindir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    env["MOOS_TEST_PKEXEC_LOG"] = str(log)
    env["MOOS_IMAGE_UPDATE_BACKEND"] = str(bindir / "moos-image-update")
    result = subprocess.run(
        [BASH, str(MOAI_DO), "update"],
        input="y\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        env=env,
    )
    check(result.returncode == 0, f"exact-digest update simulation failed: {result.stderr}")
    expected = (
        "/usr/libexec/moos-image-update\nstage\n--expected-digest\n"
        f"{digest}\n"
    )
    actual = log.read_text(encoding="utf-8") if log.exists() else ""
    check(actual == expected,
          "update must escalate only the fixed backend plus the confirmed exact digest; "
          f"got {actual!r}")

    # A stale production tag is reported by the resolver as a blocked downgrade.
    # The UI must not prompt and must never cross the privilege boundary.
    (bindir / "moos-image-update").write_text(
        "#!/bin/sh\nprintf '%s\\n' 'blocked-downgrade|moos-nvidia|old|older'\n",
        encoding="utf-8",
    )
    log.unlink(missing_ok=True)
    result = subprocess.run(
        [BASH, str(MOAI_DO), "update"],
        input="y\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        env=env,
    )
    check(result.returncode == 0 and "refused an older" in result.stdout,
          "a blocked downgrade must be a clear, clean no-op")
    check(not log.exists(), "a blocked downgrade must never invoke pkexec")

    # A staged image is not a terminal state when production has a newer
    # correction. The assistant must confirm and hand the replacement digest
    # to the same fixed privileged authority.
    (bindir / "moos-image-update").write_text(
        "#!/bin/sh\nprintf '%s\\n' "
        f"'replace-staged|moos-nvidia|{current}|{digest}'\n",
        encoding="utf-8",
    )
    log.unlink(missing_ok=True)
    result = subprocess.run(
        [BASH, str(MOAI_DO), "update"],
        input="y\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        env=env,
    )
    check(result.returncode == 0 and "replace the staged update" in result.stdout,
          "a newer correction must be offered as a staged-update replacement")
    actual = log.read_text(encoding="utf-8") if log.exists() else ""
    check(actual == expected,
          "a staged replacement must use the same exact-digest privileged boundary")

# ── 3. App lifecycle has ONE authority: Mo Store's backend ───────────────────
# uninstall carries the same free-form id as install, so it gets the same refusals.
for bad_id in ("../../etc/passwd", "org.foo; rm -rf ~", "org.foo && reboot", "$(id)", "org foo"):
    result = run("uninstall", bad_id)
    check(result.returncode == 2,
          f"moai-do uninstall must refuse the id {bad_id!r} with exit 2, got {result.returncode}")
    check("invalid app id" in result.stdout + result.stderr,
          f"moai-do uninstall must reject {bad_id!r} as an invalid id")
result = run("uninstall")
check(result.returncode == 2, "moai-do uninstall with no id must exit 2")

# Install, remove and update must reach moos-storectl with exactly the confirmed
# arguments, and a declined prompt must never reach it at all. Flatpak itself is
# doubled to fail, which proves moai-do no longer performs transactions directly.
with tempfile.TemporaryDirectory() as tmp:
    bindir = Path(tmp)
    store_log = bindir / "storectl.log"
    success = ('#!/bin/sh\nprintf "%s\\n" "$@" >> "$MOOS_TEST_STORE_LOG"\n'
               "printf '%s\\n' '{\"schema\":1,\"state\":\"success\",\"message\":\"Done\"}'\n")
    for name, body in {"moos-storectl": success,
                       "flatpak": "#!/bin/sh\nexit 1\n",
                       "gtk-launch": "#!/bin/sh\nexit 0\n",
                       "moos-gpu-headroom": "#!/bin/sh\nexit 0\n"}.items():
        (bindir / name).write_text(body, encoding="utf-8")
        (bindir / name).chmod(0o755)
    store_env = os.environ.copy()
    store_env["PATH"] = f"{bindir}{os.pathsep}{store_env.get('PATH', '')}"
    store_env["MOOS_TEST_STORE_LOG"] = str(store_log)

    def store_run(args, answer):
        store_log.unlink(missing_ok=True)
        completed = subprocess.run([BASH, str(MOAI_DO), *args], input=answer,
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=60, env=store_env)
        logged = store_log.read_text(encoding="utf-8") if store_log.exists() else ""
        return completed, logged

    for args, expected in ((["uninstall", "org.example.App"], "remove\norg.example.App\n"),
                           (["update-apps"], "update\n"),
                           (["install", "org.example.App"], "install\norg.example.App\n")):
        label = " ".join(args)
        completed, logged = store_run(args, "y\n")
        check(logged == expected,
              f"moai-do {label} must delegate exactly to moos-storectl; got {logged!r}")
        check(completed.returncode == 0,
              f"a successful Store job must make moai-do {label} succeed: {completed.stdout}")
        completed, logged = store_run(args, "n\n")
        check(logged == "", f"a declined moai-do {label} must never reach moos-storectl")
        check(completed.returncode == 0, f"declining moai-do {label} must be a clean no-op")

    (bindir / "moos-storectl").write_text(
        "#!/bin/sh\nprintf '%s\\n' '{\"schema\":1,\"state\":\"failed\",\"message\":"
        "\"This app is installed system-wide; Mo Store only removes user installations\"}'\n"
        "exit 1\n", encoding="utf-8")
    completed, _ = store_run(["uninstall", "org.example.App"], "y\n")
    check(completed.returncode != 0 and "system-wide" in completed.stdout,
          "a failed Store job must fail the action and show the backend's own reason")

# ── 4. A dismissed administrator prompt is a failure, never a success line ────
# `main` runs inside `if main "$@"; then`, which suspends `set -e` for every do_* function. An
# unchecked `run_priv …` is therefore followed by its own "✓" whatever happened. Until
# 2026-09-17 install-rpm printed "Package staged. Restart…", update-firmware printed "Done" and
# install-nvidia printed "Staged — reboot to activate" after the person DISMISSED the password
# prompt, and the audit trail recorded `ok`. Mo AI's tool harness reads that output back to the
# model as the result of the action, so the assistant then reported a success that never was.
#
# Structural half: no escalation anywhere in the file may go unchecked.
joined = re.sub(r"\\\n\s*", " ", MOAI_DO.read_text(encoding="utf-8"))
for number, statement in enumerate(joined.splitlines(), 1):
    stripped = statement.strip()
    if stripped.startswith("#") or stripped.startswith("run_priv()") or "run_priv " not in stripped:
        continue
    guarded = re.match(r"(if|elif|while|until)\b", stripped) or "||" in stripped \
        or "&&" in stripped or stripped.startswith("!")
    check(bool(guarded),
          "moai-do escalates without reading the result, so its success line prints even when "
          f"the administrator prompt is dismissed: `{stripped[:90]}`")

# Behavioural half: pkexec exits 126 (dismissed), exactly as polkit reports it.
with tempfile.TemporaryDirectory() as tmp:
    bindir = Path(tmp)
    doubles = {
        "pkexec": "#!/bin/sh\nexit 126\n",
        "fwupdmgr": ("#!/bin/sh\n"
                     'case "$1" in get-updates) echo "Device firmware 1.0 -> 1.1"; exit 0 ;; esac\n'
                     "exit 0\n"),
    }
    for name, body in doubles.items():
        (bindir / name).write_text(body, encoding="utf-8")
        (bindir / name).chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
    result = subprocess.run([BASH, str(MOAI_DO), "update-firmware"], input="y\n",
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=30, env=env)
    check(result.returncode != 0,
          "update-firmware must FAIL when the administrator prompt is dismissed; "
          f"it exited {result.returncode}")
    check("✓" not in result.stdout,
          f"update-firmware printed a success mark after a dismissed prompt: {result.stdout!r}")
    check("NOT updated" in result.stderr,
          "update-firmware must say plainly that nothing was updated")

# ── 5. rollback is a TOGGLE: a queued rescue is never cancelled by asking again ─────────
# `bootc rollback` makes the running system the default again when a return is already
# queued. moai-do used to run it anyway and print "next boot will use the previous version".
# The same deployment reading moos-rollback and moos-boot-assess make now decides first.
def rollback_run(deployments, answer="y\n", status_ok=True):
    with tempfile.TemporaryDirectory() as tmp:
        bindir = Path(tmp)
        log = bindir / "pkexec.log"
        import json as _json
        status = _json.dumps({"deployments": deployments})
        (bindir / "rpm-ostree").write_text(
            "#!/bin/sh\n"
            + ('case "$*" in *--json*) cat "$MOOS_TEST_STATUS";; *) echo deployments;; esac\n'
               if status_ok else "exit 1\n"), encoding="utf-8")
        (bindir / "status.json").write_text(status, encoding="utf-8")
        (bindir / "pkexec").write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$MOOS_TEST_PKEXEC_LOG"\n',
                                       encoding="utf-8")
        for name in ("rpm-ostree", "pkexec"):
            (bindir / name).chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = f"{bindir}{os.pathsep}{env.get('PATH', '')}"
        env["MOOS_TEST_PKEXEC_LOG"] = str(log)
        env["MOOS_TEST_STATUS"] = str(bindir / "status.json")
        done = subprocess.run([BASH, str(MOAI_DO), "rollback"], input=answer,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30, env=env)
        return done, (log.read_text(encoding="utf-8") if log.exists() else "")


booted = {"booted": True, "version": "44.3"}
older = {"version": "44.2"}
staged = {"staged": True, "version": "44.4"}
for label, deployments in (("queued", [older, booted]), ("queued behind a staged update",
                                                            [staged, older, booted])):
    done, escalated = rollback_run(deployments)
    check(done.returncode == 0 and escalated == "",
          f"with a rollback already {label}, moai-do rollback must not run bootc rollback "
          f"(it would CANCEL the rescue); ran {escalated!r}, exit {done.returncode}")
    check("nothing was changed" in done.stdout and "44.2" in done.stdout,
          f"a refused rollback ({label}) must say the return is already queued and name it: "
          f"{done.stdout!r}")
done, escalated = rollback_run([booted, older])
check(escalated == "bootc\nrollback\n",
      f"a ready rollback must still escalate exactly `bootc rollback`; got {escalated!r}")
check("44.2" in done.stdout, "moai-do rollback must name the version the next boot returns to")
done, escalated = rollback_run([staged, booted, older])
check(escalated == "bootc\nrollback\n" and "rolling back discards it" in done.stdout,
      "with only a staged update ahead, rollback still queues and warns about the discard")
done, escalated = rollback_run([booted])
check(done.returncode != 0 and escalated == "",
      "with no previous version, rollback must refuse instead of pressing a toggle")
done, escalated = rollback_run([booted, older], status_ok=False)
check(done.returncode != 0 and escalated == "",
      "an unreadable deployment list must never lead to a blind `bootc rollback`")

# ── 6. The Update page's two actions: one question, then a confirmed, audited run ─────────
# do/update-apps and do/update-firmware no longer open a held Konsole. moos-open asks once
# (kdialog, fail closed), then runs `moai-do <action>` with MOAI_DO_CONFIRMED=1 in the
# background. The confirmed path must record the decision as approved.
with tempfile.TemporaryDirectory() as tmp:
    bindir = Path(tmp)
    log = bindir / "moai-do.log"
    audit_log = bindir / "logger.log"
    (bindir / "kdialog").write_text(
        '#!/bin/sh\ncase "$*" in *warningyesno*) exit "${KDIALOG_ANSWER:-1}";; esac\nexit 0\n',
        encoding="utf-8")
    (bindir / "moai-do").write_text(
        '#!/bin/sh\nprintf "%s %s\\n" "${MOAI_DO_CONFIRMED:-0}" "$*" >> "$MOOS_TEST_LOG"\n'
        'echo "Done"\n', encoding="utf-8")
    (bindir / "konsole").write_text('#!/bin/sh\necho konsole >> "$MOOS_TEST_LOG"\n',
                                    encoding="utf-8")
    # moos-open says how the run ended in a notification: never on the owner's desktop.
    (bindir / "notify-send").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    for name in ("kdialog", "moai-do", "konsole", "notify-send"):
        (bindir / name).chmod(0o755)
    env = os.environ.copy()
    env.update(PATH=f"{bindir}:{LOGGER_STUB}:/usr/bin:/bin", MOOS_TEST_LOG=str(log),
               LANG="C.UTF-8")
    import time as _time

    def route(url, answer):
        log.unlink(missing_ok=True)
        subprocess.run([BASH, str(MOOS_OPEN), url], env={**env, "KDIALOG_ANSWER": answer},
                       capture_output=True, text=True, timeout=30)
        deadline = _time.monotonic() + 5
        while not log.exists() and _time.monotonic() < deadline and answer == "0":
            _time.sleep(0.05)
        _time.sleep(0.2)
        return log.read_text(encoding="utf-8") if log.exists() else ""

    for action in ("update-apps", "update-firmware"):
        ran = route(f"moos://do/{action}", "0")
        check(ran == f"1 {action}\n",
              f"moos://do/{action} must run `MOAI_DO_CONFIRMED=1 moai-do {action}` with no "
              f"terminal after the Yes; ran {ran!r}")
        check(route(f"moos://do/{action}", "1") == "",
              f"moos://do/{action} must run nothing when the question is answered No")

# The popup that says how it ended speaks ONE language. A label pair inside a status pair once
# reached kdialog as "Firmware | البرامج الثابتة: لم يكتمل | did not finish", reordered by bidi.
# The message is the notification's body: the last argument moos-open hands notify-send.
with tempfile.TemporaryDirectory() as tmp:
    bindir = Path(tmp)
    popups = bindir / "popups.log"
    (bindir / "kdialog").write_text(
        '#!/bin/sh\ncase "$*" in *warningyesno*) exit 0;; esac\nexit 0\n', encoding="utf-8")
    (bindir / "notify-send").write_text(
        '#!/bin/sh\nfor last in "$@"; do :; done\nprintf "%s\\n" "$last" >> "$MOOS_TEST_POPUPS"\n',
        encoding="utf-8")
    (bindir / "moai-do").write_text('#!/bin/sh\necho "step one"\necho "firmware said boom"\n'
                                    'exit "${MOAI_FAKE_RC:-0}"\n', encoding="utf-8")
    for name in ("kdialog", "moai-do", "notify-send"):
        (bindir / name).chmod(0o755)
    import time as _time

    def popup(url, locale, rc):
        popups.unlink(missing_ok=True)
        environment = {"PATH": f"{bindir}:{LOGGER_STUB}:/usr/bin:/bin", "HOME": tmp,
                       "LC_ALL": locale, "LANG": locale, "MOOS_TEST_POPUPS": str(popups),
                       "MOAI_FAKE_RC": rc}
        subprocess.run([BASH, str(MOOS_OPEN), url], env=environment, capture_output=True,
                       text=True, timeout=30)
        deadline = _time.monotonic() + 5
        while not popups.exists() and _time.monotonic() < deadline:
            _time.sleep(0.05)
        return popups.read_text(encoding="utf-8").strip() if popups.exists() else ""

    arabic = re.compile(r"[\u0600-\u06ff]")
    for url, rc, english, arabic_words in (
            ("moos://do/update-firmware", "1", "Firmware: did not finish — firmware said boom",
             "البرامج الثابتة: لم يكتمل"),
            ("moos://do/update-firmware", "0", "Firmware ✓ — firmware said boom", "البرامج الثابتة ✓"),
            ("moos://do/update-apps", "1", "Mo Store: did not finish — firmware said boom",
             "Mo Store: لم يكتمل")):
        shown = popup(url, "C.UTF-8", rc)
        check(shown == english, f"{url} (exit {rc}) in English showed {shown!r}")
        shown = popup(url, "ar_SA.UTF-8", rc)
        check(shown.startswith(arabic_words) and " | " not in shown
              and "did not finish" not in shown and "Firmware" not in shown,
              f"{url} (exit {rc}) in Arabic showed {shown!r}")
    check(not arabic.search(popup("moos://do/update-firmware", "C.UTF-8", "1")),
          "an English popup must carry no Arabic half")

# The confirmed path records an approval, not a silent `ok` with no decision.
with tempfile.TemporaryDirectory() as tmp:
    bindir = Path(tmp)
    (bindir / "logger").write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$MOOS_TEST_AUDIT"\n',
                                   encoding="utf-8")
    (bindir / "moos-storectl").write_text(
        "#!/bin/sh\nprintf '%s\\n' '{\"schema\":1,\"state\":\"success\",\"message\":\"Done\"}'\n",
        encoding="utf-8")
    for name in ("logger", "moos-storectl"):
        (bindir / name).chmod(0o755)
    audit = bindir / "audit.log"
    env = os.environ.copy()
    env.update(PATH=f"{bindir}{os.pathsep}{env.get('PATH', '')}", MOOS_TEST_AUDIT=str(audit),
               MOAI_DO_CONFIRMED="1")
    done = subprocess.run([BASH, str(MOAI_DO), "update-apps"], stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=30, env=env)
    trail = audit.read_text(encoding="utf-8") if audit.exists() else ""
    check(done.returncode == 0 and "action=update-apps verdict=ok" in trail,
          f"MOAI_DO_CONFIRMED=1 moai-do update-apps must run and audit ok; got {trail!r}")

# ── 7. setup-brain is a hand-off to the one brain settings page, never a privilege ─────────
setup_brain = re.search(r"^do_setup_brain\(\) \{(.*?)^\}", do_text, re.S | re.M)
check(setup_brain is not None, "moai-do must define do_setup_brain")
if setup_brain:
    live = setup_brain.group(1).split("return $?", 1)[0]
    check("open_assistant_settings" in live and "run_priv" not in live and "pkexec" not in live,
          "moai-do setup-brain must open the Mo AI settings page without escalating")
check("moos-settings --section=assistant" in do_text,
      "the brain settings hand-off must open moos-settings --section=assistant")

if errors:
    print("MoOS moai-do test failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print(f"MoOS moai-do test passed ({len(actions)} actions covered)")
