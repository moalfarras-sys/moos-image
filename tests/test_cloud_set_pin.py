#!/usr/bin/env python3
"""Gate: a MoOS Cloud account can always be claimed and always be recovered.

WHY THIS EXISTS

Mo PC Remote's PIN had exactly one creation path — POST /api/setup, from a browser, refused for
ever after with 409 — and exactly one change path, POST /api/pin, which needs a session token,
which needs the PIN you are trying to change. On a desktop with a person in front of it that is
fine. On a headless cloud account it produces two failures that have no way out:

  RECOVERY. Forget the PIN and that desktop is gone: the service is healthy, the stream runs, the
  machine is fine, and nobody can get in. Measured on the live server before this landed,
  moalfarras had FailedAttempts=2 against a PIN with no reset.

  CLAIM. Before anyone sets a PIN the agent is in first-run state, so /api/setup answers whoever
  reaches it first. On a tailnet carrying phones, laptops and a second developer, "first to open
  the URL owns the desktop" is not an authentication model. A new account has to be claimable from
  a root shell on the box, before its address is handed to anyone.

So both halves are checked here, and so is the property that makes the command safe to run on a
SHARED machine: the PIN must arrive on stdin and never as an argument, because /proc/<pid>/cmdline
is world-readable and an argument is visible in `ps` to every other account on the server.
"""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
CLOUD = ROOT / "system_files/usr/bin/moos-cloud-desktop"
AGENT_MAIN = ROOT / "moremote/agent-linux/Program.cs"
PATHS = ROOT / "moremote/agent/Core/Logging.cs"
AGENT_BIN = "/usr/lib/mo-remote/MoRemotePersonal"


def main() -> int:
    errors: list[str] = []

    if not CLOUD.is_file() or not AGENT_MAIN.is_file():
        print("GATE FAIL: moos-cloud-desktop or the agent entry point is missing.")
        return 1

    cloud = CLOUD.read_text(encoding="utf-8")
    agent = AGENT_MAIN.read_text(encoding="utf-8")
    paths = PATHS.read_text(encoding="utf-8")

    # --- 1. the agent has to implement the admin path at all ------------------------------------
    if '"--set-pin"' not in agent:
        errors.append("the agent has no --set-pin path, so a forgotten PIN is an unrecoverable account.")
    else:
        # It must read the PIN from stdin. Console.In.ReadToEnd is the whole point; args[1] would be
        # the bug this gate exists to prevent.
        if "Console.In.ReadToEnd" not in agent:
            errors.append("--set-pin does not read the PIN from stdin. Passing it in argv exposes it in\n"
                          "        `ps` to every other account on a shared server.")
        if re.search(r"--set-pin[\s\S]{0,600}?args\[1\]", agent):
            errors.append("--set-pin appears to read the PIN from args[1]. /proc/<pid>/cmdline is\n"
                          "        world-readable; the PIN must come in on stdin.")
        # A reset that leaves the lockout armed locks the user out of the PIN they just chose.
        if "FailedAttempts = 0" not in agent or "LockoutUntilUnix = 0" not in agent:
            errors.append("--set-pin does not clear FailedAttempts/LockoutUntilUnix. Somebody resetting a\n"
                          "        PIN has usually just failed to guess the old one, so leaving the counter\n"
                          "        armed locks them out of the PIN they have this second set.")

    # --- 2. the config path must never be relative ----------------------------------------------
    # GetFolderPath(LocalApplicationData) returns "" on Linux when $HOME/.local/share does not exist
    # yet — i.e. on every freshly created account, which is what moos-cloud-dev makes. Path.Combine
    # then yields a RELATIVE path, the agent writes a fresh empty config into its working directory,
    # FirstRun flips true, and /api/setup starts answering strangers on a running desktop.
    if "IsPathRooted" not in paths:
        errors.append("Paths.DataDir does not check that the resolved directory is absolute.\n"
                      "        On a brand-new account GetFolderPath returns '' and the config silently\n"
                      "        lands in the CWD as an unconfigured, claimable first-run config.")

    # --- 3. the wrapper, because a flag nobody knows about is not a recovery path ----------------
    if "set-pin)" not in cloud:
        errors.append("moos-cloud-desktop has no `set-pin` subcommand, so the agent flag is undiscoverable.")
    else:
        if AGENT_BIN not in cloud:
            errors.append(f"the set-pin wrapper does not invoke {AGENT_BIN} — check the path matches\n"
                          f"        the Containerfile's COPY --from=moremote-build /out/ /usr/lib/mo-remote/.")
        # The agent rewrites the whole config from memory on its next Save(), so a PIN written under
        # a running agent un-applies itself at the next failed login.
        if not re.search(r"systemctl --user stop mo-remote-personal", cloud):
            errors.append("the set-pin wrapper does not stop mo-remote-personal before writing.\n"
                          "        The running agent holds the config in memory and rewrites the file on its\n"
                          "        next Save(), so the new PIN would silently revert.")
        if not re.search(r"systemctl --user start mo-remote-personal", cloud):
            errors.append("the set-pin wrapper stops the agent but never starts it again — that turns a\n"
                          "        PIN reset into an outage.")
        # Confirmation prompt: a mistyped PIN in the act of recovering an account is the one typo
        # that cannot be undone by trying again.
        if "do not match" not in cloud:
            errors.append("the interactive set-pin does not ask for the PIN twice. A typo here locks the\n"
                          "        account with a PIN nobody knows — the exact failure being recovered from.")

    if errors:
        print("GATE FAIL: a MoOS Cloud account could be left unclaimable or unrecoverable.\n")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("OK: --set-pin reads stdin, clears lockout, resolves an absolute config dir; "
          "moos-cloud-desktop set-pin stops/starts the agent and confirms the PIN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
