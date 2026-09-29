"""Install Mira's on-device client on the Echo over its USB serial root console.

Run on the PC (host Python, not the Flatpak sandbox):

    python3 deploy.py install    copy agent.py + run.sh to /data/mira, sha256-verified,
                                 keeping the replaced files in /data/mira/backup/
    python3 deploy.py register   back up /etc/inittab, append ::respawn:/data/mira/run.sh
                                 if absent, kill -HUP 1 (idempotent)
    python3 deploy.py restart    TERM the init-owned agent; run.sh starts it again
    python3 deploy.py status     read back processes, inittab, firewall rule, status.json
    python3 deploy.py rollback   restore /etc/inittab from the newest backup, kill -HUP 1,
                                 stop run.sh and the agent

The console transport is echo_sh.run(command, timeout) -> (output, exit code), loaded from
$MIRA_ECHO_SH (default ~/.cache/mira-claude/echo_sh.py). Only one process may use the serial
port at a time. busybox ash's line editor drops everything past ~2046 characters of one line
and then waits for the rest of an open quote, which leaves the console stuck at a ">" prompt;
every command here is therefore kept under LINE_MAX characters.
"""
import base64
import hashlib
import importlib.util
import os
import shlex
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ECHO_SH = Path(os.environ.get("MIRA_ECHO_SH",
                              Path.home() / ".cache/mira-claude/echo_sh.py"))
DEST = "/data/mira"
BACKUP = DEST + "/backup"
INITTAB_LINE = "::respawn:/data/mira/run.sh"
LINE_MAX = 1800    # the whole wrapped line must stay below busybox's ~2046-character limit
CHUNK = 1400       # base64 characters per append command
FILES = {"agent.py": 0o600, "run.sh": 0o700}


def transport():
    spec = importlib.util.spec_from_file_location("echo_sh", ECHO_SH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run


RUN = None


def sh(command: str, timeout: float = 20, check: bool = True) -> str:
    global RUN
    if len(command) > LINE_MAX - 120:
        raise SystemExit(f"refusing a {len(command)}-character console line")
    RUN = RUN or transport()
    output, code = RUN(command, timeout)
    if check and code != "0":
        raise SystemExit(f"device command failed ({code}): {command[:80]}\n{output[-400:]}")
    return output


def copy(local: Path, remote: str, mode: int) -> None:
    data = local.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    encoded = base64.b64encode(data).decode()
    staging = remote + ".b64"
    q = shlex.quote
    sh(f"rm -f {q(staging)} {q(remote + '.new')}")
    for start in range(0, len(encoded), CHUNK):
        sh(f"printf '%s' '{encoded[start:start + CHUNK]}' >> {q(staging)}")
    remote_digest = sh(f"base64 -d {q(staging)} > {q(remote + '.new')} && rm -f {q(staging)} && "
                       f"sha256sum {q(remote + '.new')}").split()[0]
    if remote_digest != digest:
        sh(f"rm -f {q(remote + '.new')}", check=False)
        raise SystemExit(f"{local.name}: sha256 mismatch ({remote_digest} != {digest}); "
                         "nothing replaced")
    stamp = time.strftime("%Y%m%dT%H%M%S")
    sh(f"mkdir -p {BACKUP} && chmod 700 {BACKUP} && "
       f"if [ -e {q(remote)} ]; then cp -p {q(remote)} {BACKUP}/{local.name}.{stamp}; fi && "
       f"chmod {mode:o} {q(remote + '.new')} && mv -f {q(remote + '.new')} {q(remote)}")
    print(f"{remote}: {digest} ({len(data)} bytes)")


def install() -> None:
    for name, mode in FILES.items():
        copy(HERE / name, f"{DEST}/{name}", mode)
    print(sh(f"busybox sh -n {DEST}/run.sh && echo run.sh syntax ok; "
             f"{DEST}/venv/bin/python -m py_compile {DEST}/agent.py && echo agent.py compiles; "
             f"rm -rf {DEST}/__pycache__/agent.*"))


def register() -> None:
    present = sh(f"grep -qxF '{INITTAB_LINE}' /etc/inittab && echo yes || echo no").strip()
    if present.endswith("yes"):
        print("inittab already has the line; nothing changed")
    else:
        stamp = time.strftime("%Y%m%dT%H%M%S")
        print(sh(f"mkdir -p {BACKUP} && cp -p /etc/inittab {BACKUP}/inittab.{stamp} && "
                 f"sha256sum /etc/inittab {BACKUP}/inittab.{stamp}"))
        sh(f"echo '{INITTAB_LINE}' >> /etc/inittab && sync && kill -HUP 1")
    print(sh("tail -3 /etc/inittab; sha256sum /etc/inittab"))


def restart() -> None:
    print(sh("for p in $(pgrep -f 'venv/bin/python -u -X faulthandler /data/mira/agent.py'); "
             "do kill -TERM $p && echo stopped $p; done; true"))


def status() -> None:
    print(sh("uptime; ps -o pid,ppid,stat,rss,args | grep -E 'run.sh|agent.py|echod run' | "
             "grep -v grep; grep -n mira /etc/inittab; "
             "iptables-legacy -S INPUT | grep 8765; cat /data/mira/status.json; echo; "
             "tail -n 12 /data/mira/agent.log", 30))


def rollback() -> None:
    newest = sh(f"ls -1t {BACKUP}/inittab.* 2>/dev/null | head -1").strip()
    if not newest:
        raise SystemExit("no inittab backup found; nothing changed")
    print(sh(f"cp -p {shlex.quote(newest)} /etc/inittab && sync && kill -HUP 1 && "
             "sha256sum /etc/inittab"))
    print(sh("for p in $(pgrep -f /data/mira/run.sh) $(pgrep -f /data/mira/agent.py); "
             "do kill -TERM $p && echo stopped $p; done; true"))


if __name__ == "__main__":
    actions = {"install": install, "register": register, "restart": restart,
               "status": status, "rollback": rollback}
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        raise SystemExit(__doc__)
    actions[sys.argv[1]]()
