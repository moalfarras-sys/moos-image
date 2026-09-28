"""Push the owner's Mira profile and settings to the Echo's on-device client.

Synchronous and stdlib-only. The request is signed with the pairing key the
desktop already uses for its heartbeat: X-Mira-Signature is
HMAC-SHA256(key, "sync:<unix time>:<sha256(body) hex>"), and the Dot accepts it
within +/-15 s of its own clock, once. Nothing here logs; errors are raised as
SyncError whose text never contains the key, the profile or the reply.

Returns the Dot's reply, whose "learned" list holds the facts the owner taught
Mira on the Echo while the computer was off. The Dot forgets them once this
reply has been written, so the caller must store them (mira_memory.remember_fact).
"""
import hashlib
import hmac
import http.client
import json
import time
from pathlib import Path

DEFAULT_KEY = Path.home() / ".config/mo-dot/device.key"
PORT = 8765
MAX_BODY = 16 * 1024


class SyncError(RuntimeError):
    """The push did not complete; str() is a short code, never a secret."""


def signature(key: bytes, stamp: int, body: bytes) -> str:
    message = f"sync:{stamp}:{hashlib.sha256(body).hexdigest()}"
    return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()


def push(profile: str, weather_city: str | None = None, voice: str | None = None,
         host: str = "192.168.3.83", key_path: str | Path = DEFAULT_KEY,
         timeout: float = 3) -> dict:
    """Store {profile, weather_city, voice} on the Dot and return its reply.

    weather_city / voice: None leaves the Dot's stored value unchanged, "" clears it.
    The reply is {"ok": True, "learned": [str, ...], "profile_chars": int,
    "weather_city": str | None, "voice": str | None}.
    """
    if not isinstance(profile, str):
        raise SyncError("profile_must_be_text")
    body = json.dumps({"profile": profile, "weather_city": weather_city, "voice": voice},
                      ensure_ascii=False).encode("utf-8")
    if len(body) > MAX_BODY:
        raise SyncError("body_too_large")
    try:
        key = Path(key_path).expanduser().read_text().strip().encode()
    except OSError:
        raise SyncError("key_unreadable") from None
    stamp = int(time.time())
    connection = http.client.HTTPConnection(host, PORT, timeout=timeout)
    try:
        connection.request("POST", "/sync", body=body, headers={
            "Content-Type": "application/json; charset=utf-8",
            "X-Mira-Time": str(stamp),
            "X-Mira-Signature": signature(key, stamp, body),
            "Connection": "close",
        })
        response = connection.getresponse()
        data = response.read(65536)
    except (OSError, http.client.HTTPException) as exc:
        raise SyncError("unreachable:" + type(exc).__name__) from None
    finally:
        connection.close()
    try:
        reply = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise SyncError(f"http_{response.status}:unreadable_reply") from None
    if response.status != 200 or not isinstance(reply, dict) or reply.get("ok") is not True:
        code = reply.get("error") if isinstance(reply, dict) else None
        raise SyncError(f"http_{response.status}:{code if isinstance(code, str) else 'rejected'}")
    learned = reply.get("learned")
    reply["learned"] = [fact for fact in learned if isinstance(fact, str)] \
        if isinstance(learned, list) else []
    return reply
