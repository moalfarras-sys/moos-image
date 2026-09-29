"""Protocol, storage and conversation checks for Mira's on-device voice client.

Host-runnable: the ESPHome API and the Gemini Live WebSocket are replaced by fakes, every
/data/mira path is redirected into a temporary directory, and nothing reaches the network.
"""

import array
import asyncio
import base64
import contextlib
import hashlib
import hmac
import json
import math
import struct
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import device_sync
from device import agent

KEY = "test-pairing-key"


NETWORK = []


def offline(url, timeout=8):
    NETWORK.append(url)
    raise OSError("tests never reach the network")


@contextlib.contextmanager
def isolated():
    """Point every file the agent owns at a temporary directory."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "psk").write_text(KEY + "\n")
        names = {"ROOT": root, "CONFIG": root / "gemini.json", "HISTORY": root / "history.json",
                 "STATUS": root / "status.json", "PROFILE": root / "profile.txt",
                 "SETTINGS": root / "settings.json", "LEARNED": root / "learned.json",
                 "PLACE": root / "place.json", "LOG": root / "agent.log",
                 "DEVICE_KEY": root / "psk"}
        with contextlib.ExitStack() as stack:
            for name, value in names.items():
                stack.enter_context(patch.object(agent, name, value))
            stack.enter_context(patch.object(agent, "_seen_signatures", {}))
            stack.enter_context(patch.object(agent, "desktop_until", 0.0))
            stack.enter_context(patch.object(agent, "fetch_json", offline))
            yield root


def pcm24(samples: int = 480, value: int = 1000) -> str:
    return base64.b64encode(struct.pack("<" + "h" * samples, *([value] * samples))).decode()


class FakeLive:
    """A scripted Gemini Live socket: `script(message, live)` returns server messages."""

    def __init__(self, script):
        self.script = script
        self.sent = []
        self.inbox = asyncio.Queue()
        self.closed = False

    async def send(self, text):
        message = json.loads(text)
        self.sent.append(message)
        for reply in self.script(message, self):
            await self.inbox.put(json.dumps(reply))

    async def recv(self):
        return await self.inbox.get()

    def __aiter__(self):
        return self

    async def __anext__(self):
        item = await self.inbox.get()
        if item is None:
            raise StopAsyncIteration
        return item

    async def close(self):
        if not self.closed:
            self.closed = True
            await self.inbox.put(None)

    def kinds(self):
        out = []
        for message in self.sent:
            if "setup" in message:
                out.append("setup")
            elif "toolResponse" in message:
                out.append("toolResponse")
            elif message.get("realtimeInput", {}).get("audioStreamEnd"):
                out.append("audioStreamEnd")
            elif "realtimeInput" in message:
                out.append("audio")
            elif "clientContent" in message:
                out.append("clientContent")
        return out


def spoken_answer(text="تمام"):
    return [{"serverContent": {"inputTranscription": {"text": "سؤال"}}},
            {"serverContent": {"outputTranscription": {"text": text},
                               "modelTurn": {"parts": [{"inlineData": {
                                   "mimeType": "audio/pcm;rate=24000", "data": pcm24()}}]}}},
            {"serverContent": {"turnComplete": True}}]


def answer_each_turn(message, live):
    if "setup" in message:
        return [{"setupComplete": {}}]
    if message.get("realtimeInput", {}).get("audioStreamEnd"):
        return spoken_answer()
    return []


class FakeAPI:
    def __init__(self):
        self.events = []
        self.audio = 0
        self.commands = []
        self.tools = None

    def send_voice_assistant_event(self, event, data):
        self.events.append(event.name.replace("VOICE_ASSISTANT_", ""))

    def send_voice_assistant_audio(self, block):
        self.audio += len(block)

    def media_player_command(self, key, *, volume=None, command=None, device_id=0):
        self.commands.append(("volume", key, volume, device_id))
        # echod quantises to 30 steps and publishes the state back.
        self.tools.on_state(types.SimpleNamespace(key=key, volume=round(volume * 30) / 30))

    def light_command(self, key, state=None, brightness=None, rgb=None, color_mode=None,
                      device_id=0):
        self.commands.append(("light", key, state, brightness, rgb, color_mode, device_id))
        self.tools.on_state(types.SimpleNamespace(key=key, state=state))


def make_voice(script=answer_each_turn, tools=None):
    api = FakeAPI()
    sockets = []

    async def connector(url, **options):
        assert url.startswith(agent.ENDPOINT + "?key=")
        live = FakeLive(script)
        sockets.append(live)
        return live

    voice = agent.Voice(api, {"model": "m", "api_key": "k"}, tools or agent.DeviceTools(api),
                        connector=connector, resampler="linear")
    api.tools = voice.tools
    voice.pace = False
    return voice, api, sockets


async def speak_turn(voice, api, chunks=3):
    port = await voice.start("conversation", 0, None, None)
    assert port == 0, port
    for _ in range(chunks):
        await voice.audio(b"\x01\x00" * 160, None)
    await voice.stop(False)
    turn = voice.turn
    await asyncio.wait_for(turn.done.wait(), 5)
    return turn


class DeviceAgentTests(unittest.TestCase):
    def test_handoff_waits_for_audio_producer_to_stop(self):
        async def exercise():
            voice = agent.Voice(None, {})
            stopped = asyncio.Event()

            async def producer():
                try:
                    await asyncio.sleep(60)
                finally:
                    stopped.set()
            turn = agent.Turn()
            turn.sender = asyncio.create_task(producer())
            await asyncio.sleep(0)
            voice.turn = turn
            await voice.cancel_turn()
            self.assertTrue(stopped.is_set())
            self.assertTrue(turn.sender.done())
            self.assertIsNone(voice.turn)
        with isolated():
            asyncio.run(exercise())

    def test_setup_uses_live_api_wire_fields_tools_and_persona(self):
        value = agent.setup({"model": "gemini-3.1-flash-live-preview"})["setup"]
        self.assertEqual(value["model"], "models/gemini-3.1-flash-live-preview")
        self.assertEqual(value["generationConfig"]["responseModalities"], ["AUDIO"])
        self.assertEqual(value["generationConfig"]["speechConfig"]["voiceConfig"]
                         ["prebuiltVoiceConfig"]["voiceName"], "Aoede")
        self.assertNotIn("responseModalities", value)
        self.assertIn("inputAudioTranscription", value)
        names = [f["name"] for f in value["tools"][0]["functionDeclarations"]]
        self.assertEqual(names, ["current_time", "current_weather", "set_speaker_volume",
                                 "ring_light", "research", "remember_owner_fact"])
        persona = value["systemInstruction"]["parts"][0]["text"]
        self.assertIn("غير متاح", persona)  # home/computer control is honestly unavailable
        synced = agent.setup({"model": "m"}, {"weather_city": "برلين", "voice": "Kore"},
                             "اسمي محمد")["setup"]
        self.assertEqual(synced["generationConfig"]["speechConfig"]["voiceConfig"]
                         ["prebuiltVoiceConfig"]["voiceName"], "Kore")
        text = synced["systemInstruction"]["parts"][0]["text"]
        self.assertIn("برلين", text)
        self.assertIn("اسمي محمد", text)

    def test_audio_resampling_preserves_partial_frame(self):
        first, carry = agent.pcm_24k_to_echo(struct.pack("<hh", 300, 600), [])
        self.assertEqual(first, b"")
        second, carry = agent.pcm_24k_to_echo(struct.pack("<h", 900), carry)
        self.assertEqual(struct.unpack("<hh", second), (300, 750))
        self.assertEqual(carry, [])

    def test_fir_resampler_is_seamless_across_chunks_and_keeps_level(self):
        tone = array.array("h", [int(6000 * math.sin(2 * math.pi * 440 * i / 24000))
                                 for i in range(4801)]).tobytes()
        whole = agent.Resampler("fir").feed(tone)
        pieces, converter, start = [], agent.Resampler("fir"), 0
        for size in (2, 7, 1000, 1, 333, 2402, 10000):
            pieces.append(converter.feed(tone[start:start + size]))
            start += size
        self.assertEqual(b"".join(pieces), whole)
        out = struct.unpack("<" + "h" * (len(whole) // 2), whole)
        self.assertAlmostEqual(len(out), 4801 * 2 / 3, delta=8)
        self.assertAlmostEqual(max(out[100:-100]), 6000, delta=150)  # 440 Hz passes
        dc = agent.Resampler("fir").feed(struct.pack("<" + "h" * 300, *([1234] * 300)))
        self.assertEqual(set(struct.unpack("<" + "h" * (len(dc) // 2), dc)[10:]), {1234})

    def test_history_is_private_and_bounded(self):
        with isolated() as root:
            for n in range(9):
                agent.remember(f"question {n}", f"answer {n}")
            entries = json.loads((root / "history.json").read_text())
            self.assertEqual(len(entries), 12)
            self.assertEqual(entries[0]["text"], "question 3")
            self.assertEqual((root / "history.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual(agent.history(), entries)

    def test_log_rotation_copies_and_truncates(self):
        with isolated() as root:
            log = root / "agent.log"
            log.write_bytes(b"x" * 300)
            self.assertFalse(agent.rotate_log(log, 400))
            self.assertTrue(agent.rotate_log(log, 200))
            self.assertEqual(log.stat().st_size, 0)
            self.assertEqual((root / "agent.log.1").stat().st_size, 300)
            self.assertEqual((root / "agent.log.1").stat().st_mode & 0o777, 0o600)


class HttpTests(unittest.TestCase):
    def serve(self, exercise):
        async def run():
            server = await asyncio.start_server(agent.status_request, "127.0.0.1", 0)
            port = server.sockets[0].getsockname()[1]
            try:
                await exercise(port)
            finally:
                server.close()
                await server.wait_closed()
        asyncio.run(run())

    @staticmethod
    async def request(port, data):
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(data)
        await writer.drain()
        result = await reader.read()
        writer.close()
        await writer.wait_closed()
        return result

    @staticmethod
    def sync_request(body: bytes, stamp=None, key=KEY, sign_body=None, length=None):
        stamp = int(time.time()) if stamp is None else stamp
        signature = agent.sign(key.encode(), "sync", stamp,
                               body if sign_body is None else sign_body)
        return (f"POST /sync HTTP/1.1\r\nHost: dot\r\nX-Mira-Time: {stamp}\r\n"
                f"X-Mira-Signature: {signature}\r\n"
                f"Content-Length: {len(body) if length is None else length}\r\n\r\n"
                ).encode() + body

    def test_heartbeat_requires_pairing_key_and_status_stays_public_only(self):
        async def exercise(port):
            agent.STATUS.write_text(json.dumps({"state": "speaking", "at": 5,
                                                "private": "never-serve"}))
            public = await self.request(port, b"GET /status HTTP/1.1\r\n\r\n")
            self.assertIn(b'"speaking"', public)
            self.assertNotIn(b"never-serve", public)
            denied = await self.request(port, b"POST /heartbeat HTTP/1.1\r\n\r\n")
            self.assertIn(b"403 Forbidden", denied)
            self.assertNotIn(b'"owner": "desktop"', denied)
            stamp = int(time.time())
            signature = hmac.new(KEY.encode(), f"heartbeat:{stamp}".encode(),
                                 hashlib.sha256).hexdigest()
            accepted = await self.request(
                port, f"POST /heartbeat HTTP/1.1\r\nX-Mira-Time: {stamp}\r\n"
                      f"X-Mira-Signature: {signature}\r\nContent-Length: 0\r\n\r\n".encode())
            self.assertIn(b"200 OK", accepted)
            self.assertTrue(agent.desktop_present())
        with isolated():
            self.serve(exercise)

    def test_sync_stores_private_settings_and_returns_learned_facts_once(self):
        async def exercise(port):
            agent.remember_fact("أحب القهوة بدون سكر")
            with patch.object(device_sync, "PORT", port):
                reply = await asyncio.to_thread(
                    device_sync.push, "اسمي محمد\nأطور ميرا", "برلين", "Kore",
                    host="127.0.0.1", key_path=agent.DEVICE_KEY)
                self.assertEqual(reply["learned"], ["أحب القهوة بدون سكر"])
                self.assertEqual(reply["voice"], "Kore")
                self.assertEqual(reply["weather_city"], "برلين")
                again = await asyncio.to_thread(
                    device_sync.push, "اسمي محمد\nأطور ميرا\nأحب القهوة بدون سكر",
                    host="127.0.0.1", key_path=agent.DEVICE_KEY)
            self.assertEqual(again["learned"], [])
            self.assertEqual(again["voice"], "Kore")  # None leaves it unchanged
            self.assertEqual(agent.load_settings(), {"weather_city": "برلين", "voice": "Kore"})
            await asyncio.sleep(0.2)  # the new city's zone is looked up in the background
            self.assertTrue(any("geocoding" in url for url in NETWORK))
            self.assertIn("أحب القهوة بدون سكر", agent.profile_text())
            for name in ("profile.txt", "settings.json", "learned.json"):
                self.assertEqual((agent.ROOT / name).stat().st_mode & 0o777, 0o600, name)
        with isolated():
            self.serve(exercise)

    def test_sync_rejects_stale_tampered_oversize_replayed_and_invalid(self):
        async def exercise(port):
            body = json.dumps({"profile": "x"}).encode()
            stale = await self.request(port, self.sync_request(body, stamp=int(time.time()) - 40))
            self.assertIn(b"403", stale)
            future = await self.request(port, self.sync_request(body, stamp=int(time.time()) + 40))
            self.assertIn(b"403", future)
            tampered = await self.request(port, self.sync_request(
                json.dumps({"profile": "evil"}).encode(), sign_body=body))
            self.assertIn(b"403", tampered)
            wrong_key = await self.request(port, self.sync_request(body, key="other"))
            self.assertIn(b"403", wrong_key)
            big = json.dumps({"profile": "x" * (agent.SYNC_MAX + 10)}).encode()
            oversize = await self.request(port, self.sync_request(big))
            self.assertIn(b"413", oversize)
            no_length = await self.request(port, (
                "POST /sync HTTP/1.1\r\nX-Mira-Time: 1\r\nX-Mira-Signature: 0\r\n\r\n").encode())
            self.assertIn(b"411", no_length)
            self.assertFalse(agent.PROFILE.exists())  # nothing above stored anything
            valid = self.sync_request(body)
            self.assertIn(b"200 OK", await self.request(port, valid))
            self.assertIn(b"replayed", await self.request(port, valid))
            voice = json.dumps({"profile": "x", "voice": "Hacker"}).encode()
            self.assertIn(b"unknown_voice", await self.request(port, self.sync_request(voice)))
            city = json.dumps({"profile": "x", "weather_city": "<script>"}).encode()
            self.assertIn(b"bad_weather_city", await self.request(port, self.sync_request(city)))
            bad = b"{not json"
            self.assertIn(b"bad_json", await self.request(port, self.sync_request(bad)))
            with patch.object(device_sync, "PORT", port):
                with self.assertRaises(device_sync.SyncError) as caught:
                    await asyncio.to_thread(device_sync.push, "x", host="127.0.0.1",
                                            key_path=agent.ROOT / "gemini.json")
            self.assertEqual(str(caught.exception), "key_unreadable")
        with isolated():
            self.serve(exercise)

    def test_desktop_signature_matches_device_scheme(self):
        body = "{}".encode()
        self.assertEqual(device_sync.signature(KEY.encode(), 123, body),
                         agent.sign(KEY.encode(), "sync", 123, body))


class ToolTests(unittest.TestCase):
    def tools(self, fetch=None):
        api = FakeAPI()
        speaker = types.SimpleNamespace(key=11, device_id=0)
        ring = types.SimpleNamespace(key=22, device_id=7)
        tools = agent.DeviceTools(api, {"speaker": speaker, "ring": ring},
                                  fetch=fetch or (lambda url: {}))
        api.tools = tools
        return tools, api

    def test_volume_and_ring_use_device_entities_with_readback(self):
        async def exercise():
            tools, api = self.tools()
            self.assertEqual(await tools.call("set_speaker_volume", {"level": 50}),
                             {"status": "ok", "level": 50})
            self.assertEqual(api.commands[-1], ("volume", 11, 0.5, 0))
            bad = await tools.call("set_speaker_volume", {"level": 140})
            self.assertEqual(bad["status"], "error")
            self.assertEqual(len(api.commands), 1)  # nothing sent for an invalid level
            on = await tools.call("ring_light", {"state": "on", "color": "green"})
            self.assertEqual(on, {"status": "ok", "state": "on", "color": "green"})
            self.assertEqual(api.commands[-1], ("light", 22, True, 0.25, (0.0, 1.0, 0.2), 35, 7))
            off = await tools.call("ring_light", {"state": "off"})
            self.assertEqual(off["status"], "ok")
            silent = agent.DeviceTools(types.SimpleNamespace(
                media_player_command=lambda *a, **k: None),
                {"speaker": types.SimpleNamespace(key=1, device_id=0)})
            with patch.object(agent.DeviceTools, "readback", return_value=None):
                self.assertEqual((await silent.call("set_speaker_volume", {"level": 10}))
                                 ["status"], "pending")
        with isolated():
            asyncio.run(exercise())

    def test_time_and_weather_use_saved_city(self):
        urls = []

        def fetch(url):
            urls.append(url)
            if "geocoding" in url:
                return {"results": [{"name": "برلين", "country": "ألمانيا", "latitude": 52.5,
                                     "longitude": 13.4, "timezone": "Europe/Berlin"}]}
            return {"current": {"time": "2026-09-28T23:00", "temperature_2m": 12.5,
                                "apparent_temperature": 11.0, "relative_humidity_2m": 80,
                                "weather_code": 3, "wind_speed_10m": 9.0}}

        async def exercise():
            tools, _ = self.tools(fetch)
            missing = await tools.call("current_weather", {})
            self.assertEqual(missing["error"], "no_city")
            agent.private_json(agent.SETTINGS, {"weather_city": "برلين"})
            weather = await tools.call("current_weather", {})
            self.assertEqual((weather["status"], weather["temperature_c"], weather["condition_ar"]),
                             ("ok", 12.5, "غائم"))
            clock = await tools.call("current_time", {})
            self.assertEqual((clock["status"], clock["timezone"]), ("ok", "Europe/Berlin"))
            self.assertEqual(sum("geocoding" in url for url in urls), 1)  # place is cached
            self.assertTrue(all(url.startswith("https://") for url in urls))
        with isolated():
            asyncio.run(exercise())

    def test_remember_owner_fact_is_private_queued_and_refuses_secrets(self):
        async def exercise():
            tools, _ = self.tools()
            result = await tools.call("remember_owner_fact", {"fact": "  اسمي   محمد "})
            self.assertEqual(result["status"], "ok")
            self.assertEqual(agent.profile_text(), "اسمي محمد")
            self.assertEqual(agent.pending_facts(), ["اسمي محمد"])
            await tools.call("remember_owner_fact", {"fact": "اسمي محمد"})
            self.assertEqual(agent.pending_facts(), ["اسمي محمد"])  # no duplicate
            for secret in ("my wifi password is hunter2", "كلمة السر 1234",
                           "tok_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345xyz"):
                refused = await tools.call("remember_owner_fact", {"fact": secret})
                self.assertEqual(refused["error"], "refused_looks_like_a_secret")
            self.assertEqual(agent.PROFILE.stat().st_mode & 0o777, 0o600)
            self.assertEqual(agent.LEARNED.stat().st_mode & 0o777, 0o600)
            self.assertEqual(await tools.call("open_garage", {}),
                             {"status": "error", "error": "unknown_tool"})

            async def explode(args):
                raise RuntimeError("wss://x/?key=SECRET")
            with patch.object(tools, "current_time", explode):
                self.assertEqual(await tools.call("current_time", {}),
                                 {"status": "error", "error": "RuntimeError"})
        with isolated():
            asyncio.run(exercise())


class ConversationTests(unittest.TestCase):
    def test_follow_up_turns_reuse_one_live_session(self):
        async def exercise():
            voice, api, sockets = make_voice()
            first = await speak_turn(voice, api)
            self.assertTrue(first.finished)
            self.assertFalse(first.reused)
            # echod starts the follow-up right after the reply played and closes the old run
            # with an abort that aioesphomeapi may deliver after that start.
            await voice.start("conversation", 0, None, None)
            await voice.stop(True)
            second_turn = voice.turn
            self.assertFalse(second_turn.finished)
            for _ in range(2):
                await voice.audio(b"\x01\x00" * 160, None)
            await voice.stop(False)
            await asyncio.wait_for(second_turn.done.wait(), 5)
            self.assertTrue(second_turn.reused)
            self.assertIsNone(second_turn.error)
            self.assertEqual(len(sockets), 1)
            self.assertEqual(sockets[0].kinds().count("setup"), 1)
            self.assertEqual(api.events.count("RUN_END"), 2)
            self.assertNotIn("ERROR", api.events)
            self.assertGreater(api.audio, 0)
            # the run echod closes after the second reply, then a follow-up nobody speaks in
            await voice.stop(True)
            await voice.start("conversation", 0, None, None)
            silent = voice.turn
            await voice.stop(True)
            self.assertTrue(silent.finished)
            self.assertTrue(sockets[0].closed)
            self.assertIsNone(voice.ws)
            self.assertNotIn("ERROR", api.events)
            self.assertEqual(api.events[-1], "RUN_END")
        with isolated():
            asyncio.run(exercise())

    def test_tool_call_answers_before_turn_ends(self):
        def script(message, live):
            if "setup" in message:
                return [{"setupComplete": {}}]
            if message.get("realtimeInput", {}).get("audioStreamEnd"):
                return [{"toolCall": {"functionCalls": [
                    {"id": "call-1", "name": "set_speaker_volume", "args": {"level": 40}}]}}]
            if "toolResponse" in message:
                # turnComplete may come before the answer's audio; the turn must wait for it.
                return [{"serverContent": {"turnComplete": True}}] + spoken_answer("خليته ٤٠")
            return []

        async def exercise():
            api = FakeAPI()
            tools = agent.DeviceTools(api, {"speaker": types.SimpleNamespace(key=5, device_id=0)})
            voice, _, sockets = make_voice(script, tools)
            voice.api = api
            api.tools = tools
            lines = []
            with patch.object(agent, "log", lines.append):
                turn = await speak_turn(voice, api)
            self.assertIsNone(turn.error)
            self.assertTrue(turn.spoke)
            self.assertIn("خليته ٤٠", turn.reply)
            response = next(m for m in sockets[0].sent if "toolResponse" in m)
            self.assertEqual(response["toolResponse"]["functionResponses"],
                             [{"id": "call-1", "name": "set_speaker_volume",
                               "response": {"status": "ok", "level": 40}}])
            self.assertEqual(api.commands, [("volume", 5, 0.4, 0)])
            timing = next(line for line in lines if line.startswith("turn "))
            self.assertIn("tools=set_speaker_volume:ok", timing)
            self.assertIn("first_audio=", timing)
            self.assertNotIn("خليته", " ".join(lines))  # transcripts never reach the log
        with isolated():
            asyncio.run(exercise())

    def test_idle_session_closes(self):
        async def exercise():
            voice, api, sockets = make_voice()
            with patch.object(agent, "IDLE_CLOSE", 0.05):
                await speak_turn(voice, api)
                self.assertIsNotNone(voice.ws)
                await asyncio.sleep(0.2)
            self.assertTrue(sockets[0].closed)
            self.assertIsNone(voice.ws)
        with isolated():
            asyncio.run(exercise())

    def test_cloud_failure_reports_type_only(self):
        async def failing(url, **options):
            raise OSError("wss://example/?key=SECRET-KEY")

        async def exercise():
            api = FakeAPI()
            voice = agent.Voice(api, {"model": "m", "api_key": "SECRET-KEY"},
                                connector=failing)
            lines = []
            with patch.object(agent, "log", lines.append):
                self.assertIsNone(await voice.start("c", 0, None, None))
            self.assertEqual(json.loads(agent.STATUS.read_text())["error"], "OSError")
            self.assertNotIn("SECRET", " ".join(lines))
        with isolated():
            asyncio.run(exercise())

    def test_heartbeat_during_connect_releases_api_untouched(self):
        class Client:
            instances = []

            def __init__(self, *args, **kwargs):
                self.calls = []
                Client.instances.append(self)

            async def connect(self, login, on_stop):
                agent.desktop_until = time.monotonic() + 6  # the desktop came back meanwhile

            async def list_entities_services(self):
                self.calls.append("list")
                return [], []

            def subscribe_voice_assistant(self, **kwargs):
                self.calls.append("subscribe")

            async def disconnect(self):
                self.calls.append("disconnect")

        async def exercise():
            with patch.object(agent, "libs", lambda: types.SimpleNamespace(APIClient=Client)), \
                    patch.object(agent, "device_address", lambda: "127.0.0.1"):
                why = await agent.run_active({"model": "m", "api_key": "k"}, "linear")
            self.assertEqual(why, "desktop")
            self.assertEqual(Client.instances[0].calls, ["disconnect"])
        with isolated():
            asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()


class ResearchToolTests(unittest.TestCase):
    def test_research_keeps_the_key_out_of_the_url_and_reads_sources(self):
        import json as _json
        from unittest.mock import patch as _patch
        seen = {}

        class Response:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self, n=-1):
                return _json.dumps({"candidates": [{"content": {"parts": [{"text": "الجواب"}]},
                    "groundingMetadata": {"groundingChunks": [{"web": {"title": "kde.org"}}]}}]}).encode()

        def fake_urlopen(request, timeout=0):
            seen["url"], seen["headers"] = request.full_url, dict(request.header_items())
            return Response()
        with _patch.object(agent.urllib.request, "urlopen", fake_urlopen):
            result = agent.web_research("سؤال", "SECRET-KEY")
        self.assertEqual((result["status"], result["sources"]), ("ok", ["kde.org"]))
        self.assertNotIn("SECRET-KEY", seen["url"])
        self.assertEqual(seen["headers"].get("X-goog-api-key"), "SECRET-KEY")
