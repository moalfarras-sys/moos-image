#!/usr/bin/env python3
"""Contract tests for Mo AI's OpenClaw-independent workspace metadata."""
from __future__ import annotations

import json
import runpy
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "system_files/usr/bin/moai-agent-api"


def main() -> None:
    module = runpy.run_path(str(API), run_name="moai_agent_api_test")
    assert list(module["TIERS"]) == ["read", "project", "system", "full"]
    for name, tier in module["TIERS"].items():
        cfg = {
            "agents": {"defaults": {
                "elevatedDefault": tier["elevated"],
                "sandbox": {"workspaceAccess": tier["workspace"],
                            "mode": tier["sandbox"]},
            }},
            "approvals": {"exec": {"enabled": tier["approvals"]}},
            "tools": {"exec": {"security": tier["exec_security"],
                               "ask": tier["exec_ask"]}},
        }
        assert module["_actual_tier"](cfg) == name
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        sessions = home / ".openclaw/agents/main/sessions"
        sessions.mkdir(parents=True)
        sid_old = "11111111-1111-1111-1111-111111111111"
        sid_new = "22222222-2222-2222-2222-222222222222"
        (sessions / f"{sid_old}.jsonl").write_text("\n", encoding="utf-8")
        (sessions / f"{sid_new}.jsonl").write_text("\n", encoding="utf-8")
        (sessions / "sessions.json").write_text(json.dumps({
            "agent:main:old": {"sessionId": sid_old, "updatedAt": 1000},
            "agent:main:new": {"sessionId": sid_new, "updatedAt": 2000},
        }), encoding="utf-8")
        workspace = home / ".config/moai-agent/workspace.json"

        globals_ = module["list_sessions"].__globals__
        globals_["HOME"] = home
        globals_["SESSIONS"] = sessions
        globals_["WORKSPACE"] = workspace
        globals_["ATTACHMENTS"] = home / ".local/share/moai-agent/attachments"

        initial = module["list_sessions"]()
        assert [s["id"] for s in initial] == [sid_new, sid_old]
        assert all(not s["pinned"] and not s["archived"] for s in initial)

        changed = module["update_session"]({
            "id": sid_old,
            "title": "Pinned project chat",
            "pinned": True,
            "project": str(home),
        })
        assert changed["ok"] and changed["title"] == "Pinned project chat"
        listed = module["list_sessions"]()
        assert listed[0]["id"] == sid_old and listed[0]["pinned"]
        assert module["list_sessions"]("project")[0]["id"] == sid_old

        module["update_session"]({"id": sid_old, "archived": True})
        assert all(s["id"] != sid_old for s in module["list_sessions"]())
        archived = module["list_sessions"]("", True)
        assert any(s["id"] == sid_old and s["archived"] for s in archived)

        for bad in (
            {"id": "../../etc/passwd", "title": "x"},
            {"id": sid_new, "pinned": "yes"},
            {"id": sid_new, "unknown": True},
            {"id": sid_new, "project": "/"},
        ):
            try:
                module["update_session"](bad)
            except ValueError:
                pass
            else:
                raise AssertionError(f"unsafe metadata accepted: {bad}")

        saved = json.loads(workspace.read_text(encoding="utf-8"))
        assert saved["version"] == 1
        assert saved["sessions"][sid_old]["archived"] is True
        assert workspace.stat().st_mode & 0o077 == 0

        project = module["upsert_project"]({"name": "MoOS", "path": str(home)})
        assert project["ok"] and project["path"] == str(home)
        assert module["list_projects"]()[0]["id"] == project["id"]

        task = module["create_task"]({
            "title": "Run the gates", "project": project["id"],
            "steps": ["Inspect", "Test", "Report"],
        })
        assert task["status"] == "pending" and len(task["steps"]) == 3
        running = module["update_task"]({
            "id": task["id"], "status": "running", "step": 1,
            "step_status": "completed", "result": "Inspected", "tool": "rg",
        })
        assert running["status"] == "running"
        assert running["steps"][0]["status"] == "completed"
        assert running["tools"][-1]["name"] == "rg"
        assert module["list_tasks"]()[0]["id"] == task["id"]

        # The task button must launch the fixed OpenClaw argv and persist the
        # real process outcome; no caller-provided executable or shell text.
        fake_openclaw = home / "openclaw"
        fake_openclaw.write_text(
            "#!/bin/sh\nprintf 'tracked-agent-result\\n'\n", encoding="utf-8")
        fake_openclaw.chmod(0o700)
        globals_["BIN"] = str(fake_openclaw)
        globals_["write_config"] = lambda body: {"ok": True}
        started = module["task_action"]({"id": task["id"], "action": "start"})
        assert started["status"] == "running"
        finished = None
        for _ in range(100):
            finished = module["list_tasks"]()[0]
            if finished["status"] != "running":
                break
            time.sleep(0.02)
        assert finished["status"] == "completed"
        assert all(step["status"] == "completed" for step in finished["steps"])
        assert "tracked-agent-result" in finished["result"]
        assert finished["tools"][-1]["name"] == "openclaw-agent"
        try:
            module["task_action"]({
                "id": task["id"], "action": "start", "command": "sudo sh"})
        except ValueError:
            pass
        else:
            raise AssertionError("task runner accepted a caller-controlled command")

        try:
            module["upsert_project"]({"name": "outside", "path": "/"})
        except ValueError:
            pass
        else:
            raise AssertionError("project outside home was accepted")
        try:
            module["update_task"]({"id": task["id"], "status": "invented"})
        except ValueError:
            pass
        else:
            raise AssertionError("unknown task status was accepted")

        terminal = module["start_terminal"]({"project": project["id"], "title": "Test"})
        assert terminal["running"] and terminal["cwd"] == str(home)
        module["write_terminal"]({
            "id": terminal["id"], "input": "printf 'terminal-ready\\n'\n",
        })
        output = {}
        for _ in range(30):
            output = module["_terminal"](terminal["id"]).output(0)
            if "terminal-ready" in output.get("output", ""):
                break
            time.sleep(0.02)
        assert "terminal-ready" in output["output"]
        stopped = module["stop_terminal"]({"id": terminal["id"]})
        assert not stopped["running"]
        assert module["list_terminals"]()[0]["id"] == terminal["id"]
        try:
            module["start_terminal"]({"command": "sudo sh"})
        except ValueError:
            pass
        else:
            raise AssertionError("terminal accepted a caller-controlled executable")

        note = home / "note.md"
        note.write_text("# Mo AI attachment\n", encoding="utf-8")
        attached = module["import_attachment"]({"path": note.as_uri()})
        assert attached["ok"] and attached["content_type"] == "text"
        assert attached["content"] == "# Mo AI attachment\n"
        assert module["list_attachments"]()[0]["id"] == attached["id"]
        stored_files = list(globals_["ATTACHMENTS"].iterdir())
        assert len(stored_files) == 1 and stored_files[0].stat().st_mode & 0o177 == 0
        try:
            module["import_attachment"]({"path": "/etc/hosts"})
        except ValueError:
            pass
        else:
            raise AssertionError("attachment outside home was accepted")

    source = API.read_text(encoding="utf-8")
    assert 'u.path == "/api/session/update"' in source
    assert 'u.path == "/api/project/upsert"' in source
    assert 'u.path == "/api/task/create"' in source
    assert 'u.path == "/api/task/action"' in source
    assert 'if set(body) != {"id", "action"}' in source
    assert '[BIN, "agent", "--session-key", f"moai-task-{task_id}",' in source
    assert 'def _task_session_tools(task_id: str)' in source
    assert 'u.path == "/api/terminal/start"' in source
    assert '["/bin/bash", "--noprofile", "--norc"]' in source
    assert 'u.path == "/api/attachment/import"' in source
    assert 'u.path == "/api/voice/start"' in source
    assert '[str(PW_RECORD), "--rate", "16000", "--channels", "1", str(path)]' in source
    assert '[str(TRANSCRIBE), str(path)]' in source
    assert "X-Moai-Agent" in source
    print("Mo AI workspace metadata tests passed")


if __name__ == "__main__":
    main()
