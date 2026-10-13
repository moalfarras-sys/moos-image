"""Exercise the real HTTP relay with private socket-backed upstream responses."""
import importlib.util
from importlib.machinery import SourceFileLoader
from http.server import ThreadingHTTPServer
from pathlib import Path
import socket
import threading
import unittest
import urllib.request
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'system_files/usr/lib/moai'))
loader = SourceFileLoader('_gateway_response_lifetime', os.environ.get(
    'MOAI_GATEWAY_LIFETIME_SOURCE', str(ROOT / 'system_files/usr/bin/moai-gateway')))
spec = importlib.util.spec_from_loader(loader.name, loader)
gateway = importlib.util.module_from_spec(spec)
loader.exec_module(gateway)


class Upstream:
    status = 200
    headers = {'Content-Type': 'text/event-stream'}

    def __init__(self, failure=False):
        self.reader, self.peer = socket.socketpair()
        self.peer.sendall(b'data: {"choices":[]}\n\ndata: [DONE]\n\n')
        self.peer.shutdown(socket.SHUT_WR)
        self.failure = failure
        self.closed = False

    def read1(self, length):
        if self.failure:
            raise OSError('private upstream disconnected')
        return self.reader.recv(length)

    def close(self):
        self.reader.close()
        self.closed = True


class Lifetime(unittest.TestCase):
    def exercise(self, *, upstream_failure=False, header_failure=False, write_failure=False):
        upstream = Upstream(upstream_failure)
        self.addCleanup(upstream.peer.close)
        self.addCleanup(upstream.close)
        finished = threading.Event()
        errors = []

        class Handler(gateway.Handler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                original = self.wfile
                try:
                    # Retain the response in this harness so reference counting cannot
                    # masquerade as the relay releasing its owned upstream resource.
                    self._proxy('GET', '', None, None, 'openai', True, upstream=upstream)
                except OSError as error:
                    errors.append(type(error).__name__)
                finally:
                    if write_failure:
                        self.wfile = original
                    finished.set()

            def send_response(self, code, message=None):
                if header_failure:
                    raise ConnectionResetError('private client left before headers')
                return super().send_response(code, message)

            def end_headers(self):
                super().end_headers()
                if write_failure:
                    class RefusingWriter:
                        def write(self, _):
                            raise BrokenPipeError('private client disconnected')
                        def flush(self):
                            pass
                    self.wfile = RefusingWriter()

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        if header_failure or write_failure:
            client = socket.create_connection(server.server_address, timeout=2)
            self.addCleanup(client.close)
            client.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        else:
            with urllib.request.urlopen('http://127.0.0.1:%d/' % server.server_address[1], timeout=2) as response:
                body = response.read()
                self.assertIn(b'data: [DONE]', body)
                self.assertEqual(b'upstream stream ended early' in body, upstream_failure)
        self.assertTrue(finished.wait(2), 'relay did not finish')
        self.assertEqual(bool(errors), header_failure)
        self.assertTrue(upstream.closed, 'relay returned while its owned upstream remained open')
        upstream.peer.settimeout(.5)
        try:
            self.assertEqual(upstream.peer.recv(1), b'', 'far end did not observe upstream hangup')
        except ConnectionResetError:
            # Closing a reader with unread data resets its peer instead of FIN.
            pass

    def test_normal_completion_releases_owned_response(self):
        self.exercise()

    def test_upstream_failure_releases_owned_response(self):
        self.exercise(upstream_failure=True)

    def test_header_failure_releases_owned_response(self):
        self.exercise(header_failure=True)

    def test_client_write_failure_releases_owned_response(self):
        self.exercise(write_failure=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
