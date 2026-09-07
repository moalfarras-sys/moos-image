"""Telegram transport for the same Mo AI/Hermes workspace used by desktop.

One allowlisted private-message consumer; no model client or independent memory.
Never log tokens/messages or acknowledge unfinished work to Telegram.
"""
import json
import os
from pathlib import Path
import threading
import time
import urllib.request


def dispatch(sender, message_id, text):
    port = int(os.environ.get("MOAI_AGENT_PORT", "8077"))
    directory = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    token = (directory / "moai-agent/token").read_text().strip()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/runtime/channel",
        data=json.dumps({"channel": "telegram", "sender": str(sender), "message_id": str(message_id), "text": text}).encode(),
        headers={"X-Moai-Agent": "1", "Content-Type": "application/json", "Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=710) as response:
        return json.load(response)["reply"]


def serve(load_credentials, telegram, log, gateway_active):
    pending = {}
    lock = threading.Lock()
    offset = None
    def deliver(token, message, update_id):
        try:
            reply = dispatch(message["from"]["id"], update_id, message["text"])
            for start in range(0, len(reply), 3500):
                telegram(token, "sendMessage", {"chat_id": message["chat"]["id"], "text": reply[start:start + 3500]})
            with lock:
                pending[update_id] = "done"
        except Exception:
            # Do not consume a failed delivery; retry after reconnecting. The
            # broker deduplicates accepted messages before model/tool execution.
            with lock:
                pending.pop(update_id, None)
            log("Mo AI channel delivery unavailable; update retained")
    log("cloud-only Telegram transport ready; uses Mo AI's shared agent workspace")
    while True:
        token, allow = load_credentials()
        if not token or not allow or gateway_active():
            # Avoid a competing consumer if an old OpenClaw channel is active.
            time.sleep(10)
            continue
        params = {"timeout": 20, "allowed_updates": json.dumps(["message"])}
        if offset is not None:
            params["offset"] = offset
        try:
            result = telegram(token, "getUpdates", params, timeout=30)
            updates = result.get("result", []) if result.get("ok") else []
            for update in updates:
                uid, msg = update.get("update_id"), update.get("message", {})
                if not isinstance(uid, int):
                    continue
                sender = str(msg.get("from", {}).get("id", ""))
                allowed = sender in allow and msg.get("chat", {}).get("type") == "private" and isinstance(msg.get("text"), str)
                with lock:
                    if not allowed:
                        pending[uid] = "done"
                    elif uid not in pending or pending[uid] == "queued":
                        if sum(state == "running" for state in pending.values()) < 4:
                            pending[uid] = "running"
                            threading.Thread(target=deliver, args=(token, msg, uid), daemon=True).start()
                        else:
                            pending[uid] = "queued"
            with lock:
                for uid in sorted(pending):
                    if pending[uid] != "done":
                        break
                    offset = uid + 1
                    del pending[uid]
            if updates:
                time.sleep(1)
        except Exception:
            log("Telegram connection unavailable; retrying without another consumer")
            time.sleep(10)
