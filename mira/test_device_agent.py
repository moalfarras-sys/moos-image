"""Protocol and storage checks for Mira's small on-device voice client."""

import asyncio
import hashlib
import hmac
import json
import os
import struct
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from device import agent


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
            task = asyncio.create_task(producer())
            await asyncio.sleep(0)
            voice.turn = {"task": task}
            await voice.cancel_turn()
            self.assertTrue(stopped.is_set())
            self.assertTrue(task.done())
        asyncio.run(exercise())

    def test_setup_uses_live_api_wire_fields(self):
        value = agent.setup({"model": "gemini-3.1-flash-live-preview"})["setup"]
        self.assertEqual(value["generationConfig"]["responseModalities"], ["AUDIO"])
        self.assertEqual(value["generationConfig"]["speechConfig"]["voiceConfig"]
                         ["prebuiltVoiceConfig"]["voiceName"], "Aoede")
        self.assertNotIn("responseModalities", value)
        self.assertIn("inputAudioTranscription", value)

    def test_audio_resampling_preserves_partial_frame(self):
        first, carry = agent.pcm_24k_to_echo(struct.pack("<hh", 300, 600), [])
        self.assertEqual(first, b"")
        second, carry = agent.pcm_24k_to_echo(struct.pack("<h", 900), carry)
        self.assertEqual(struct.unpack("<hh", second), (300, 750))
        self.assertEqual(carry, [])

    def test_history_is_private_and_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            with patch.object(agent, "HISTORY", path):
                for n in range(9):
                    agent.remember(f"question {n}", f"answer {n}")
                entries = json.loads(path.read_text())
                self.assertEqual(len(entries), 12)
                self.assertEqual(entries[0]["text"], "question 3")
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(agent.history(), entries)

    def test_heartbeat_requires_pairing_key_and_status_stays_public_only(self):
        async def exercise():
            with tempfile.TemporaryDirectory() as directory:
                key = Path(directory) / "key"
                key.write_text("test-pairing-key")
                status = Path(directory) / "status.json"
                status.write_text(json.dumps({"state": "speaking", "at": 5,
                                              "private": "never-serve"}))
                with patch.object(agent, "DEVICE_KEY", key), patch.object(agent, "STATUS", status):
                    server = await asyncio.start_server(agent.status_request, "127.0.0.1", 0)
                    port = server.sockets[0].getsockname()[1]

                    async def request(data):
                        reader, writer = await asyncio.open_connection("127.0.0.1", port)
                        writer.write(data)
                        await writer.drain()
                        result = await reader.read()
                        writer.close()
                        await writer.wait_closed()
                        return result

                    try:
                        public = await request(b"GET /status HTTP/1.1\r\n\r\n")
                        self.assertIn(b'"speaking"', public)
                        self.assertNotIn(b"never-serve", public)
                        denied = await request(b"POST /heartbeat HTTP/1.1\r\n\r\n")
                        self.assertIn(b"403 Forbidden", denied)
                        self.assertNotIn(b'"owner": "desktop"', denied)
                        stamp = int(time.time())
                        signature = hmac.new(b"test-pairing-key",
                                             f"heartbeat:{stamp}".encode(),
                                             hashlib.sha256).hexdigest()
                        accepted = await request(
                            f"POST /heartbeat HTTP/1.1\r\nX-Mira-Time: {stamp}\r\n"
                            f"X-Mira-Signature: {signature}\r\n\r\n".encode())
                        self.assertIn(b"200 OK", accepted)
                        self.assertGreater(agent.desktop_until, time.monotonic())
                    finally:
                        server.close()
                        await server.wait_closed()

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
