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
from pathlib import Path

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

# The do/* routes moos-open FORWARDS to moai-do must be actions moai-do has. (Routes it
# implements itself — do/smart-setup runs `moos-setup --smart` — are not moai-do's problem.)
forwarded = re.search(r"^\s*(do/[a-z|/-]+)\)\s*\n?\s*term moai-do", open_text, re.M)
check(forwarded is not None, "moos-open must forward a do/* arm to moai-do")
if forwarded:
    for route in forwarded.group(1).split("|"):
        action = route.removeprefix("do/")
        check(action in actions,
              f"moos-open forwards {route} to moai-do, which has no '{action}' action — that "
              f"button pops 'unknown command' and does nothing")

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

if errors:
    print("MoOS moai-do test failed:", file=sys.stderr)
    for error in errors:
        print(f" - {error}", file=sys.stderr)
    raise SystemExit(1)

print(f"MoOS moai-do test passed ({len(actions)} actions covered)")
