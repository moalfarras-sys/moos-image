"""Mira voice pipeline on the Dot itself, independent of the desktop computer.

Uses the Dot's local encrypted ESPHome API and Gemini Live's raw WebSocket API.
Credentials and conversation history stay in /data/mira (mode 0600). The client
never starts a shell, and a cloud failure leaves the existing Echo daemon alive.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import os
import socket
import struct
import time
from pathlib import Path
from urllib.parse import quote

from aioesphomeapi import APIClient, VoiceAssistantEventType as Event
from websockets.asyncio.client import connect


ROOT = Path("/data/mira")
CONFIG = ROOT / "gemini.json"
HISTORY = ROOT / "history.json"
STATUS = ROOT / "status.json"
DEVICE_KEY = Path("/data/misc/echolocal/psk")
ENDPOINT = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
)
desktop_until = 0.0


def device_address() -> str:
    override = os.environ.get("MIRA_API_HOST")
    if override:
        return override
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as peer:
        peer.connect(("1.1.1.1", 80))
        return peer.getsockname()[0]


def private_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as out:
        json.dump(value, out, ensure_ascii=False)
    os.replace(temporary, path)


def history() -> list[dict[str, str]]:
    try:
        entries = json.loads(HISTORY.read_text())
        return entries[-12:] if isinstance(entries, list) else []
    except (FileNotFoundError, ValueError):
        return []


def remember(heard: str, reply: str) -> None:
    if not heard.strip() or not reply.strip():
        return
    entries = history() + [
        {"role": "user", "text": heard.strip()[:600]},
        {"role": "model", "text": reply.strip()[:600]},
    ]
    private_json(HISTORY, entries[-12:])


def setup(config: dict) -> dict:
    return {"setup": {
        "model": "models/" + config["model"],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {
                "voiceName": config.get("voice", "Aoede")}}},
        },
        "inputAudioTranscription": {"languageCodes": ["ar-EG"]},
        "outputAudioTranscription": {},
        "realtimeInputConfig": {"automaticActivityDetection": {
            "startOfSpeechSensitivity": "START_SENSITIVITY_HIGH",
            "endOfSpeechSensitivity": "END_SENSITIVITY_LOW",
            "prefixPaddingMs": 300,
            "silenceDurationMs": 1000,
        }},
        "systemInstruction": {"parts": [{"text": (
            "اسمك ميرا. أنت المساعدة الصوتية لصاحب الجهاز. "
            "تحدثي معه بالعربية العامية الطبيعية وباختصار. "
            "أجيبي بصدق؛ ليس لديك أدوات للتحكم بالبيت أو الكمبيوتر في هذا الوضع. "
            "إذا لم تسمعي السؤال فاطلبي إعادته."
        )}]},
    }}


def pcm_24k_to_echo(raw: bytes, carry: list[int]) -> tuple[bytes, list[int]]:
    """Convert Gemini's 24 kHz mono to the Dot stream's 16 kHz mono S16LE."""
    samples = carry + list(struct.unpack("<" + "h" * (len(raw) // 2), raw))
    limit = len(samples) // 3 * 3
    output = bytearray()
    for i in range(0, limit, 3):
        output += struct.pack("<hh", samples[i],
                              (samples[i + 1] + samples[i + 2]) // 2)
    return bytes(output), samples[limit:]


class Voice:
    def __init__(self, api: APIClient, config: dict):
        self.api = api
        self.config = config
        self.turn = None
        self.connected = True

    async def cancel_turn(self):
        """Drain the old producer before another client takes the audio channel."""
        if self.turn:
            task = self.turn["task"]
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    def event(self, name: str, data: dict | None = None) -> None:
        if self.connected:
            self.api.send_voice_assistant_event(
                getattr(Event, "VOICE_ASSISTANT_" + name), data or {})

    async def start(self, conversation, flags, settings, wake):
        if self.turn:
            self.turn["task"].cancel()
        turn = {"ready": asyncio.Event(), "audio": asyncio.Queue(maxsize=128),
                "heard": "", "reply": "", "closed": False, "spoke": False,
                "started": time.monotonic()}
        self.turn = turn
        turn["task"] = asyncio.create_task(self.run(turn))
        try:
            await asyncio.wait_for(turn["ready"].wait(), 12)
        except asyncio.TimeoutError:
            turn["task"].cancel()
            return None
        if turn.get("error"):
            return None
        self.event("RUN_START")
        self.event("STT_START")
        self.status("listening")
        return 0

    async def audio(self, data, data2):
        turn = self.turn
        if not turn or turn["closed"] or turn["spoke"]:
            return
        try:
            turn["audio"].put_nowait(data)
        except asyncio.QueueFull:
            turn["error"] = "audio_queue_full"
            turn["task"].cancel()

    async def stop(self, abort):
        turn = self.turn
        if not turn:
            return
        if abort:
            turn["task"].cancel()
        elif not turn["closed"]:
            turn["closed"] = True
            await turn["audio"].put(None)
            self.status("thinking")

    def status(self, state: str, error: str | None = None) -> None:
        private_json(STATUS, {"state": state, "at": int(time.time()),
                              **({"error": error} if error else {})})

    async def send_audio(self, ws, turn):
        while True:
            chunk = await asyncio.wait_for(turn["audio"].get(), 30)
            if chunk is None:
                await ws.send(json.dumps({"realtimeInput": {"audioStreamEnd": True}}))
                return
            await ws.send(json.dumps({"realtimeInput": {"audio": {
                "data": base64.b64encode(chunk).decode("ascii"),
                "mimeType": "audio/pcm;rate=16000",
            }}}))

    async def run(self, turn):
        sender = None
        try:
            url = ENDPOINT + "?key=" + quote(self.config["api_key"], safe="")
            async with asyncio.timeout(80):
                async with connect(url, max_size=4 * 1024 * 1024) as ws:
                    await ws.send(json.dumps(setup(self.config), ensure_ascii=False))
                    if "setupComplete" not in json.loads(await ws.recv()):
                        raise RuntimeError("setup_not_acknowledged")
                    prior = history()
                    if prior:
                        await ws.send(json.dumps({"clientContent": {
                            "turns": [{"role": item["role"], "parts": [
                                {"text": item["text"]}]} for item in prior],
                            "turnComplete": False,
                        }}, ensure_ascii=False))
                    smoke_text = os.environ.get("MIRA_SMOKE_TEXT")
                    if smoke_text:
                        turn["closed"] = True
                    turn["ready"].set()
                    if smoke_text:
                        await asyncio.sleep(0.3)
                        await ws.send(json.dumps({"clientContent": {
                            "turns": [{"role": "user", "parts": [
                                {"text": smoke_text[:100]}]}],
                            "turnComplete": True,
                        }}, ensure_ascii=False))
                    else:
                        sender = asyncio.create_task(self.send_audio(ws, turn))
                    carry = []
                    async for wire in ws:
                        response = json.loads(wire)
                        content = response.get("serverContent", {})
                        turn["heard"] += content.get("inputTranscription", {}).get("text", "")
                        turn["reply"] += content.get("outputTranscription", {}).get("text", "")
                        for part in content.get("modelTurn", {}).get("parts", []):
                            encoded = part.get("inlineData", {}).get("data")
                            if not encoded:
                                continue
                            if not turn["spoke"]:
                                turn["spoke"] = True
                                self.event("STT_END", {"text": turn["heard"]})
                                self.event("TTS_START", {"text": turn["reply"]})
                                self.event("TTS_STREAM_START")
                                self.status("speaking")
                            output, carry = pcm_24k_to_echo(base64.b64decode(encoded), carry)
                            for start in range(0, len(output), 512):
                                block = output[start:start + 512]
                                self.api.send_voice_assistant_audio(block)
                                await asyncio.sleep(len(block) / 32000)
                        if content.get("turnComplete"):
                            break
                    if turn["spoke"]:
                        self.event("TTS_STREAM_END")
                    self.event("RUN_END")
                    remember(turn["heard"], turn["reply"])
                    self.status("ready")
        except asyncio.CancelledError:
            self.status("ready")
            raise
        except Exception as exc:
            # Exception text can include a URL with the API key. Emit its type only.
            turn["error"] = type(exc).__name__
            self.event("ERROR", {"code": "mira_cloud_error", "message": "تعذر الصوت"})
            self.status("error", type(exc).__name__)
        finally:
            turn["ready"].set()
            if sender:
                sender.cancel()
            if self.turn is turn:
                self.turn = None


async def status_request(reader: asyncio.StreamReader,
                         writer: asyncio.StreamWriter) -> None:
    """Read-only state for the desktop UI; never serves history or credentials."""
    global desktop_until
    try:
        request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 2)
        status = request.startswith(b"GET /status HTTP/1.")
        heartbeat = request.startswith(b"POST /heartbeat HTTP/1.")
        valid = status or heartbeat
        if heartbeat:
            headers = {}
            for line in request.split(b"\r\n")[1:]:
                if b":" in line:
                    name, value = line.split(b":", 1)
                    headers[name.strip().lower()] = value.strip()
            stamp = int(headers.get(b"x-mira-time", b"0"))
            signature = headers.get(b"x-mira-signature", b"")
            expected = hmac.new(DEVICE_KEY.read_text().strip().encode(),
                                f"heartbeat:{stamp}".encode(), hashlib.sha256).hexdigest()
            valid = abs(time.time() - stamp) <= 15 and hmac.compare_digest(
                signature.decode("ascii", "ignore"), expected)
            if valid:
                desktop_until = time.monotonic() + 6
        state = json.loads(STATUS.read_text()) if status else {}
        public = {"state": state.get("state", "offline"),
                  "at": state.get("at", 0)} if status else (
                      {"owner": "desktop"} if valid else {"error": "not_authorized"})
        body = json.dumps(public).encode("utf-8")
        code = b"200 OK" if valid else b"403 Forbidden" if heartbeat else b"404 Not Found"
        writer.write(b"HTTP/1.1 " + code + b"\r\nContent-Type: application/json\r\n"
                     b"Cache-Control: no-store\r\nContent-Length: " +
                     str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body)
        await writer.drain()
    except (OSError, ValueError, asyncio.TimeoutError,
            asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass


async def serve():
    ROOT.mkdir(mode=0o700, exist_ok=True)
    config = json.loads(CONFIG.read_text())
    while True:
        try:
            server = await asyncio.start_server(
                status_request, device_address(), 8765, limit=4096)
            break
        except OSError:
            await asyncio.sleep(5)
    while True:
        api = None
        voice = None
        unsubscribe = None
        try:
            # A standby client must not connect/configure the shared voice API:
            # reconnecting it can disturb the desktop's current subscription.
            while time.monotonic() < desktop_until:
                await asyncio.sleep(0.5)
            api = APIClient(device_address(), 6053, password=None,
                            noise_psk=DEVICE_KEY.read_text().strip(),
                            client_info="Mira On-device")
            disconnected = asyncio.Event()
            async def on_stop(expected):
                disconnected.set()
                if voice:
                    voice.connected = False
            await api.connect(login=True, on_stop=on_stop)
            entities, _ = await api.list_entities_services()
            by_id = {entity.object_id: entity for entity in entities}
            voice = Voice(api, config)
            unsubscribe = None
            for name, value, method in (
                ("reply_delivery_1", "Streamed", api.select_command),
                ("microphone_end_of_speech", True, api.switch_command),
                ("follow_up_1", 0 if os.environ.get("MIRA_SMOKE_TEXT") else 20,
                 api.number_command),
            ):
                entity = by_id.get(name)
                if entity:
                    method(entity.key, value, device_id=entity.device_id)
            while not disconnected.is_set():
                if time.monotonic() < desktop_until:
                    if unsubscribe:
                        unsubscribe()
                        unsubscribe = None
                        await voice.cancel_turn()
                        voice.status("desktop")
                    break  # Release the encrypted API completely while on standby.
                elif unsubscribe is None:
                    unsubscribe = api.subscribe_voice_assistant(
                        handle_start=voice.start, handle_stop=voice.stop,
                        handle_audio=voice.audio)
                    voice.status("ready")
                await asyncio.sleep(0.5)
        except Exception as exc:
            private_json(STATUS, {"state": "error", "at": int(time.time()),
                                  "error": type(exc).__name__})
        finally:
            if unsubscribe:
                unsubscribe()
            if voice:
                await voice.cancel_turn()
            if api:
                try:
                    await api.disconnect()
                except Exception:
                    pass  # A broken connection must not prevent the retry loop.
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(serve())
