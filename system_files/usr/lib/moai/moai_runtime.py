"""Mo AI's persistent agent workspace and capability broker.

Hermes owns reasoning, the gateway owns inference, this user service owns tools.
The model never receives the broker credential or an approval-resolution tool.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import signal
import sqlite3
import subprocess
import threading
import time
import uuid
import moai_web
import urllib.request


def schema(name, description, properties=None, required=None):
    return {"type": "function", "function": {"name": name, "description": description,
        "parameters": {"type": "object", "properties": properties or {},
                       "required": required or [], "additionalProperties": False}}}


STRING = {"type": "string"}
TOOLS = [
    schema("projects", "List owner-registered projects. Only these projects may be accessed."),
    schema("files", "List files in a registered project.", {"project": STRING, "path": STRING}, ["project"]),
    schema("read_file", "Read a UTF-8 project file.", {"project": STRING, "path": STRING}, ["project", "path"]),
    schema("write_file", "Create or replace a UTF-8 project file, after owner approval. Read before replacing; supply its SHA256 to prevent overwriting newer edits.",
           {"project": STRING, "path": STRING, "content": STRING, "sha256": STRING}, ["project", "path", "content", "sha256"]),
    schema("git_status", "Read real Git status.", {"project": STRING}, ["project"]),
    schema("git_diff", "Read the actual unstaged Git diff.", {"project": STRING, "path": STRING}, ["project"]),
    schema("run_command", "Run a user shell command in an isolated project with a PTY, after owner approval. No network, host home, credentials, privilege or system services. Returns real output and exit code. Maximum 60 seconds.",
           {"project": STRING, "command": STRING}, ["project", "command"]),
    schema("tasks", "List persistent project tasks.", {"project": STRING}),
    schema("web_read", "Read text from a public HTTPS page. No logged-in browser, scripts, internal networks or downloads. Requires owner-enabled web access.", {"url": STRING}, ["url"]),
    schema("documentation", "Query the reviewed Context7 MCP server for public library documentation. First supply library name, then its returned /org/project ID with your question. Requires web access.", {"library": STRING, "query": STRING}, ["library", "query"]),
]


class Runtime:
    def __init__(self, api):
        self.api = api
        self.running = {}
        self.lock = threading.RLock()
        directory = api["DATA_HOME"] / "moai-agent"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = directory / "agent.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, key TEXT UNIQUE, label TEXT, updated INTEGER, history TEXT DEFAULT '[]', active TEXT DEFAULT '');
                CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, session TEXT, role TEXT, text TEXT, status TEXT, ts INTEGER);
                CREATE TABLE IF NOT EXISTS approvals (id TEXT PRIMARY KEY, session TEXT, command TEXT, cwd TEXT, payload TEXT, decision TEXT DEFAULT '', expires INTEGER);
                CREATE TABLE IF NOT EXISTS channels (peer TEXT PRIMARY KEY, session TEXT);
                CREATE TABLE IF NOT EXISTS inbox (id TEXT PRIMARY KEY, reply TEXT DEFAULT '');
            """)
            # An interrupted service must never replay an approved command.
            db.execute("UPDATE sessions SET active=''")
            db.execute("UPDATE approvals SET decision='deny' WHERE decision=''")
        self.db.chmod(0o600)
        runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "moai-agent"
        runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.token = secrets.token_urlsafe(32)
        fd = os.open(runtime / "token", os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as out:
            os.fchmod(out.fileno(), 0o600)
            out.write(self.token)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def authorized(self, headers):
        return headers.get("Origin") is None and hmac.compare_digest(
            headers.get("Authorization", ""), "Bearer " + self.token)

    def event(self, sid, role, text, status=""):
        with self.connect() as db:
            db.execute("INSERT INTO events(session,role,text,status,ts) VALUES(?,?,?,?,?)",
                       (sid, role, str(text)[:16000], status, int(time.time())))

    def sessions(self):
        with self.connect() as db:
            rows = [dict(row, pinned=False, archived=False, project="") for row in db.execute(
                "SELECT id,key,label,updated FROM sessions ORDER BY updated DESC LIMIT 60")]
        metadata = self.api["load_workspace"]()["sessions"]
        for row in rows:
            own = metadata.get(row["id"], {})
            row.update(pinned=bool(own.get("pinned")), archived=bool(own.get("archived")),
                       label=own.get("title") or row["label"], project=own.get("project", ""))
        return rows

    def exists(self, sid):
        with self.connect() as db:
            return db.execute("SELECT id FROM sessions WHERE id=?", (sid,)).fetchone() is not None

    def cancel(self, body):
        if set(body) != {"session"}:
            raise ValueError("only a session may be cancelled")
        with self.lock, self.connect() as db:
            row = db.execute("SELECT id FROM sessions WHERE key=? OR id=?", (body["session"], body["session"])).fetchone()
            if not row:
                return {"ok": True}
            sid = row[0]
            db.execute("UPDATE sessions SET active='' WHERE id=?", (sid,))
            db.execute("UPDATE approvals SET decision='deny' WHERE session=? AND decision=''", (sid,))
            terminal = self.running.get(sid)
            if terminal:
                terminal.stop()
        self.event(sid, "assistant", "Stopped. Earlier tool results are preserved.", "cancelled")
        return {"ok": True}

    def task_action(self, body):
        if set(body) != {"id", "action"} or body["action"] not in ("start", "resume", "pause", "cancel"):
            raise ValueError("invalid task action")
        task = next((row for row in self.api["list_tasks"]() if row["id"] == body["id"]), None)
        if not task:
            raise ValueError("task does not exist")
        key = "moai-task-" + task["id"]
        if body["action"] in ("cancel", "pause"):
            self.cancel({"session": key})
            return self.api["update_task"]({"id": task["id"], "status": "cancelled" if body["action"] == "cancel" else "paused"})
        with self.api["CONFIG_WRITE_LOCK"]:
            current = next(row for row in self.api["list_tasks"]() if row["id"] == task["id"])
            if current["status"] == "running":
                raise ValueError("task is already running")
            self.api["update_task"]({"id": task["id"], "status": "running", "error": ""})
        def run():
            started = time.time()
            try:
                project = self.api["_project"](task["project"])[0] if task.get("project") else None
                prompt = self.api["_task_prompt"](task, project)
                result = self.chat(key, prompt)
                with self.api["CONFIG_WRITE_LOCK"]:
                    current = next(row for row in self.api["list_tasks"]() if row["id"] == task["id"])
                    if current["status"] != "running":
                        return
                    # A model answer is not proof of a completed coding task.
                    events = [row for row in self.messages(key) if row["ts"] >= int(started)]
                    tested = any(row["status"] == "success" and row["text"].startswith("run_command\n") and '"exit_code": 0' in row["text"] for row in events)
                    diffed = any(row["status"] == "success" and row["text"].startswith("git_diff\n") for row in events)
                    self.api["update_task"]({"id": task["id"], "status": "completed" if tested and diffed else "paused",
                        "result": result, "error": "" if tested and diffed else "Verification incomplete; inspect the session and continue."})
            except Exception:
                with self.api["CONFIG_WRITE_LOCK"]:
                    current = next(row for row in self.api["list_tasks"]() if row["id"] == task["id"])
                    if current["status"] == "running":
                        self.api["update_task"]({"id": task["id"], "status": "failed", "error": "Agent turn failed; completed results remain in its session."})
        threading.Thread(target=run, daemon=True).start()
        return {"ok": True, "id": task["id"], "status": "running", "session_key": key}

    def chat(self, key, text):
        port = int(os.environ.get("MOAI_GATEWAY_PORT", "8080"))
        req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions",
            data=json.dumps({"model": "cloud:openrouter/free", "messages": [{"role": "user", "content": text}],
                             "moai": {"agent": True, "session": key}}).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=700) as response:
            return json.load(response)["choices"][0]["message"]["content"]

    def channel_message(self, body):
        """Transport-neutral ingress. Adapters authenticate the remote sender;
        the broker independently checks the owner's channel allowlist.
        """
        if set(body) != {"channel", "sender", "message_id", "text"}:
            raise ValueError("invalid channel message")
        channel, sender, text = body["channel"], str(body["sender"]), body["text"]
        if channel not in ("telegram", "whatsapp") or not isinstance(text, str) or len(text) > 16000:
            raise ValueError("unsupported channel message")
        config = self.api["load_cfg"]().get("channels", {}).get(channel, {})
        if sender not in {str(value) for value in config.get("allowFrom", [])}:
            raise PermissionError("sender is not in the owner's channel allowlist")
        peer = channel + ":" + sender
        delivery = hashlib.sha256((peer + ":" + str(body["message_id"])).encode()).hexdigest()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT reply FROM inbox WHERE id=?", (delivery,)).fetchone()
            if previous:
                return {"reply": previous[0] or "This delivery was already received; open its session to continue. Do not repeat an approved action."}
            db.execute("INSERT INTO inbox(id) VALUES(?)", (delivery,))
            row = db.execute("SELECT session FROM channels WHERE peer=?", (peer,)).fetchone()
            session = row[0] if row else "moai-channel-" + hashlib.sha256(peer.encode()).hexdigest()[:32]
        if text.startswith("/continue "):
            selected = text.split(maxsplit=1)[1].strip()
            if not self.exists(selected):
                reply = "Unknown session. Copy the session ID from Mo AI's conversation."
            else:
                session = selected
                reply = "Connected to session " + session
        elif text == "/session":
            with self.connect() as db:
                row = db.execute("SELECT id FROM sessions WHERE key=? OR id=?", (session, session)).fetchone()
            reply = "Session: " + (row[0] if row else session)
        elif text.startswith(("/allow ", "/deny ")):
            aid = text.split(maxsplit=1)[1].strip()
            with self.connect() as db:
                row = db.execute("SELECT a.id FROM approvals a JOIN sessions s ON a.session=s.id WHERE a.id=? AND (s.id=? OR s.key=?)", (aid, session, session)).fetchone()
            if not row:
                raise ValueError("approval does not belong to this channel's active session")
            self.resolve({"id": aid, "decision": "allow-once" if text.startswith("/allow ") else "deny"})
            reply = "Approval recorded."
        else:
            with self.connect() as db:
                db.execute("INSERT INTO channels(peer,session) VALUES(?,?) ON CONFLICT(peer) DO UPDATE SET session=excluded.session", (peer, session))
            reply = self.chat(session, text)
        with self.connect() as db:
            db.execute("INSERT INTO channels(peer,session) VALUES(?,?) ON CONFLICT(peer) DO UPDATE SET session=excluded.session", (peer, session))
            db.execute("UPDATE inbox SET reply=? WHERE id=?", (reply, delivery))
        self.api["append_audit"]("channel", "message", hashlib.sha256(peer.encode()).hexdigest()[:16], "handled", {})
        return {"reply": reply, "session": session}

    def messages(self, sid):
        with self.connect() as db:
            row = db.execute("SELECT id FROM sessions WHERE id=? OR key=?", (sid, sid)).fetchone()
            if row:
                sid = row[0]
            return [dict(row) for row in reversed(list(db.execute(
                "SELECT role,text,status,ts FROM events WHERE session=? ORDER BY seq DESC LIMIT 400", (sid,))))]

    def begin(self, body):
        key = body.get("session", "")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,120}", key):
            raise ValueError("a stable session key is required")
        user = body.get("user")
        if not isinstance(user, str) or not user.strip() or len(user) > 64000:
            raise ValueError("invalid user message")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM sessions WHERE key=? OR id=?", (key, key)).fetchone()
            if row and row["active"]:
                raise ValueError("this session already has a running turn")
            sid, run = (row["id"] if row else str(uuid.uuid4())), secrets.token_urlsafe(24)
            history = json.loads(row["history"]) if row else []
            if row:
                db.execute("UPDATE sessions SET active=?,updated=? WHERE id=?", (run, int(time.time()), sid))
            else:
                db.execute("INSERT INTO sessions(id,key,label,updated,active) VALUES(?,?,?,?,?)",
                           (sid, key, user[:100], int(time.time()), run))
        self.event(sid, "user", user)
        return {"id": sid, "run": run, "history": history, "tools": TOOLS}

    def require_run(self, body):
        with self.connect() as db:
            row = db.execute("SELECT id FROM sessions WHERE id=? AND active=? AND active!=''",
                             (body.get("id"), body.get("run"))).fetchone()
        if not row:
            raise ValueError("agent turn is no longer active")
        return row["id"]

    def finish(self, body):
        sid = self.require_run(body)
        history = body.get("history", [])
        if not isinstance(history, list) or len(json.dumps(history)) > 2 * 1024 * 1024:
            raise ValueError("invalid history")
        answer = str(body.get("answer") or "Agent turn interrupted. Retry to continue.")[:32000]
        self.event(sid, "assistant", answer, "error" if body.get("error") else "")
        with self.connect() as db:
            db.execute("UPDATE sessions SET history=?,active='',updated=? WHERE id=?",
                       (json.dumps(history, ensure_ascii=False), int(time.time()), sid))
        return {"ok": True}

    def approvals(self):
        with self.connect() as db:
            return [dict(row, task="", warning="Agent action: review the complete command or file change. Runs as your user; no elevated access.",
                         allowed=["allow-once", "deny"], created=0)
                    for row in db.execute("SELECT id,session,command,cwd,expires FROM approvals WHERE decision='' AND expires>?", (int(time.time() * 1000),))]

    def resolve(self, body):
        if set(body) != {"id", "decision"} or body["decision"] not in ("allow-once", "deny"):
            raise ValueError("only one-time approval or deny is allowed")
        with self.connect() as db:
            changed = db.execute("UPDATE approvals SET decision=? WHERE id=? AND decision='' AND expires>?",
                (body["decision"], body["id"], int(time.time() * 1000))).rowcount
        if not changed:
            raise ValueError("approval is no longer pending")
        self.api["append_audit"]("approval", "resolve", body["id"], body["decision"], {})
        return {"ok": True, **body}

    def approval(self, sid, name, args, cwd):
        aid = str(uuid.uuid4())
        payload = json.dumps({"tool": name, "arguments": args}, ensure_ascii=False)
        if len(payload) > 12000:
            raise ValueError("change is too large to review; split it into smaller changes")
        with self.connect() as db:
            db.execute("INSERT INTO approvals(id,session,command,cwd,payload,expires) VALUES(?,?,?,?,?,?)",
                       (aid, sid, payload, str(cwd), payload, int((time.time() + 120) * 1000)))
        self.event(sid, "tool", f"{name}: waiting for owner approval", "pending")
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            with self.connect() as db:
                decision = db.execute("SELECT decision FROM approvals WHERE id=?", (aid,)).fetchone()[0]
            if decision:
                if decision != "allow-once":
                    raise PermissionError("owner denied the action")
                return
            time.sleep(.25)
        with self.connect() as db:
            db.execute("UPDATE approvals SET decision='expired' WHERE id=? AND decision=''", (aid,))
        raise PermissionError("approval expired; no action executed")

    def tool(self, body):
        sid = self.require_run(body)
        name, args = body.get("name"), body.get("arguments")
        definition = next((tool["function"] for tool in TOOLS if tool["function"]["name"] == name), None)
        if not definition or not isinstance(args, dict):
            raise ValueError("unknown tool")
        params = definition["parameters"]
        if set(args) - set(params["properties"]) or set(params["required"]) - set(args) or any(not isinstance(v, str) for v in args.values()):
            raise ValueError("invalid tool arguments")
        self.event(sid, "tool", name, "running")
        try:
            result = self.execute(sid, name, args)
            self.event(sid, "tool", name + "\n" + json.dumps(result, ensure_ascii=False), "error" if isinstance(result, dict) and result.get("error") else "success")
            self.api["append_audit"]("agent-tool", name, sid, "success", {})
            return result
        except Exception as exc:
            result = {"error": str(exc)[:1000]}
            self.event(sid, "tool", name + "\n" + result["error"], "error")
            self.api["append_audit"]("agent-tool", name, sid, "error", {})
            return result

    def execute(self, sid, name, args):
        if name in ("web_read", "documentation"):
            if self.api["load_state"]().get("web") is not True:
                raise PermissionError("owner must enable web access in Settings")
            if name == "web_read":
                return moai_web.read(args["url"])
            return moai_web.documentation(args["library"], args["query"])
        if name == "projects":
            return self.api["list_projects"]()
        if name == "tasks":
            return self.api["list_tasks"](args.get("project", ""))
        project = args["project"]
        _, root = self.api["_project"](project)
        # Never turn registration of the owner's whole home into model access.
        if root == self.api["HOME"].resolve() or root.name.startswith("."):
            raise PermissionError("choose a dedicated project directory")
        path = args.get("path", "")
        if any(part.startswith(".") and part not in ("", ".") for part in Path(path).parts):
            raise PermissionError("agent access to hidden files is disabled")
        if name == "files":
            return self.api["project_files"](project, path)
        if name == "read_file":
            result = self.api["project_file"](project, path)
            if len(result["content"]) > 32000:
                raise ValueError("file exceeds the agent's 32,000 character read limit")
            result["sha256"] = hashlib.sha256(result["content"].encode()).hexdigest()
            return result
        if name == "git_status":
            return self.api["project_git_status"](project)
        if name == "git_diff":
            return self.api["project_git_diff"](project, path)
        if self.api["load_state"]().get("tier", "read") not in ("project", "system", "full"):
            raise PermissionError("read-only permission tier; owner must enable project access in Settings")
        if name == "write_file":
            if not path or Path(path).is_absolute() or ".." in Path(path).parts:
                raise ValueError("invalid relative file path")
            target = root / path
            parent = target.parent.resolve(strict=True)
            if parent != root and root not in parent.parents or target.is_symlink():
                raise PermissionError("path escapes the project")
            self.approval(sid, name, args, root)
            # Open each directory without following links, including after the
            # approval wait. Never overwrite a file changed while being reviewed.
            fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                for part in Path(path).parts[:-1]:
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    os.close(fd)
                    fd = child
                leaf = Path(path).name
                try:
                    oldfd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
                except FileNotFoundError:
                    old = None
                else:
                    with os.fdopen(oldfd, "rb") as source:
                        if os.fstat(source.fileno()).st_nlink != 1:
                            raise PermissionError("hard-linked files cannot be edited")
                        old = source.read(1024 * 1024 + 1)
                if (hashlib.sha256(old).hexdigest() if old is not None else "") != args["sha256"]:
                    raise ValueError("file changed; read it again before editing")
                data = args["content"].encode()
                temp = ".moai-" + uuid.uuid4().hex
                outfd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
                try:
                    with os.fdopen(outfd, "wb") as out:
                        out.write(data)
                        os.fsync(out.fileno())
                    os.rename(temp, leaf, src_dir_fd=fd, dst_dir_fd=fd)
                finally:
                    try:
                        os.unlink(temp, dir_fd=fd)
                    except FileNotFoundError:
                        pass
            finally:
                os.close(fd)
            return {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        if name == "run_command":
            command = args["command"]
            if not command.strip() or len(command) > 8000 or "\0" in command:
                raise ValueError("invalid command")
            if not Path("/usr/bin/bwrap").is_file():
                raise PermissionError("project sandbox is unavailable; no command executed")
            self.approval(sid, name, args, root)
            argv = ["/usr/bin/bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL"]
            for folder in ("/usr", "/bin", "/lib", "/lib64"):
                if Path(folder).exists():
                    argv += ["--ro-bind", folder, folder]
            argv += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                     "--bind", str(root), "/work", "--chdir", "/work", "--clearenv",
                     "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/tmp",
                     "--setenv", "TERM", "dumb", "--", "/bin/bash", "--noprofile", "--norc", "-c", command]
            with self.lock, self.connect() as db:
                if not db.execute("SELECT id FROM sessions WHERE id=? AND active!=''", (sid,)).fetchone():
                    raise ValueError("turn was cancelled; no command executed")
                terminal = self.api["TerminalSession"](root, "Mo AI: " + command[:60], argv=argv)
                self.running[sid] = terminal
            with self.api["TERMINAL_LOCK"]:
                self.api["TERMINALS"][terminal.id] = terminal
            try:
                terminal.process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                terminal.stop()
            terminal.reader.join(timeout=2)
            with self.lock:
                self.running.pop(sid, None)
            result = terminal.output(0)
            if len(result["output"]) > 16000:
                result["output"] = result["output"][-16000:]
                result["truncated"] = True
            if result["exit_code"] != 0:
                result["error"] = "Command failed or exceeded the 60 second limit"
            return result
        raise ValueError("unsupported capability")
