"""Wake models, announcements and test audio for the paired Echo."""

import math
import re
import struct
import threading
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from mira_bridge import IP

ROOT = Path(__file__).resolve().parent
WAKE_MODELS = Path.home() / '.local/share/mira/wake-models'


class ToneServer(BaseHTTPRequestHandler):
    """Serves the wake models and a test tone to the paired Echo only."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.client_address[0] != IP:
            self.send_error(403)
            return
        if self.path == '/tone.wav':
            frames = struct.pack('<' + 'h' * 48000,
                                 *[int(16000 * math.sin(2 * math.pi * 440 * i / 48000)) for i in range(48000)])
            self.send_response(200)
            self.send_header('Content-Type', 'audio/wav')
            self.end_headers()
            out = wave.open(self.wfile, 'wb')
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(48000)
            out.writeframes(frames)
            out.close()
        elif self.path in ('/hey_mira.json', '/hey_mira.tflite'):
            self._send_file(ROOT / self.path.lstrip('/'))
        elif re.fullmatch(r'/announce/[0-9a-f]{12}(\.16k)?\.wav', self.path):
            # A reminder or a finished job, spoken by Gemini TTS (announce.py), for the Echo to play.
            import announce
            self._send_file(announce.CACHE_DIR / self.path.rsplit('/', 1)[1], 'audio/wav')
        elif re.fullmatch(r'/models/[a-z0-9_]{3,40}\.(json|tflite)', self.path):
            # Wake models trained on this PC for the owner's voice; the Echo checks size and SHA-256.
            name = self.path.rsplit('/', 1)[1]
            folder = next((f for f in (WAKE_MODELS, ROOT / 'wake-models', ROOT / 'wake_training') if (f / name).exists()), WAKE_MODELS)
            self._send_file(folder / name)
        else:
            self.send_error(404)

    def _send_file(self, path, content_type='application/octet-stream'):
        try:
            data = path.read_bytes()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def start():
    server = HTTPServer(('0.0.0.0', 18769), ToneServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
