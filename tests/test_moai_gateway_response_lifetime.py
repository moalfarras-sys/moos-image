"""Exercise the real HTTP relay with private socket-backed upstream responses."""
import importlib.util
from contextlib import ExitStack
from importlib.machinery import SourceFileLoader
from http.server import ThreadingHTTPServer
from pathlib import Path
import socket
import threading
import unittest
import urllib.request
import urllib.error
import os
import sys
from unittest.mock import patch

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

    def __init__(self, failure=False, payload=b'data: {"choices":[]}\n\ndata: [DONE]\n\n'):
        self.reader, self.peer = socket.socketpair()
        self.peer.sendall(payload)
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

    def read(self):
        chunks = []
        while chunk := self.read1(65536):
            chunks.append(chunk)
        return b''.join(chunks)


class Lifetime(unittest.TestCase):
    def exercise(self, *, upstream_failure=False, header_failure=False, write_failure=False,
                 acquisition='response'):
        upstream = Upstream(upstream_failure)
        self.addCleanup(upstream.peer.close)
        self.addCleanup(upstream.close)
        refused = None
        refusal = None
        if acquisition != 'response':
            refused = Upstream(payload=b'private provider refused')
            self.addCleanup(refused.peer.close)
            self.addCleanup(refused.close)
            refusal = urllib.error.HTTPError('https://private.invalid/chat',
                                            401 if acquisition == 'automatic-refusal' else 429,
                                            'private refusal', {}, refused)
        policy = ExitStack()
        self.addCleanup(policy.close)
        automatic = acquisition.startswith('automatic-')
        if automatic:
            policy.enter_context(patch.object(gateway.cloud_policy, 'selected_cost_policy', return_value='free'))
            policy.enter_context(patch.object(gateway.cloud_policy, 'automatic_candidates', return_value=['first', 'second']))
            policy.enter_context(patch.object(gateway.cloud_policy, 'validate'))
            policy.enter_context(patch.object(gateway.cloud_policy, 'request_body', return_value={'stream': True}))
            policy.enter_context(patch.object(gateway.cloud_policy, 'note_upstream_failure'))
        finished = threading.Event()
        errors = []
        opened = []

        class Handler(gateway.Handler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                original = self.wfile
                try:
                    # Retain the response in this harness so reference counting cannot
                    # masquerade as the relay releasing its owned upstream resource.
                    if automatic:
                        self._to_cloud({}, b'', gateway.cloud_policy.DEFAULT_MODEL, {})
                    else:
                        self._proxy('GET', '', None, None, 'openai', True,
                                    upstream=upstream if acquisition == 'response' else None)
                except OSError as error:
                    errors.append(type(error).__name__)
                finally:
                    if write_failure:
                        self.wfile = original
                    finished.set()

            def _cloud_cfg(self, _):
                return 'https://openrouter.ai/api/v1', 'private-fixture', 'openai'

            def _open_upstream(self, *_):
                opened.append(True)
                if len(opened) == 1:
                    raise refusal
                return upstream

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
        self.addCleanup(worker.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        if header_failure or write_failure:
            client = socket.create_connection(server.server_address, timeout=2)
            self.addCleanup(client.close)
            client.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
        elif acquisition in ('http-error', 'automatic-refusal'):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen('http://127.0.0.1:%d/' % server.server_address[1], timeout=2)
            with caught.exception as response:
                self.assertIn(b'private provider refused', response.read())
                self.assertEqual(response.code, refusal.code)
            self.assertEqual(len(opened), 1, 'explicit/authentication refusal must not retry')
        else:
            with urllib.request.urlopen('http://127.0.0.1:%d/' % server.server_address[1], timeout=2) as response:
                body = response.read()
                self.assertIn(b'data: [DONE]', body)
                self.assertEqual(b'upstream stream ended early' in body, upstream_failure)
        self.assertTrue(finished.wait(2), 'relay did not finish')
        self.assertEqual(bool(errors), header_failure)
        if acquisition == 'automatic-retry':
            self.assertEqual(len(opened), 2, 'free candidate refusal must reach its next candidate')
        responses = [upstream] if acquisition == 'response' else [refused]
        if acquisition == 'automatic-retry':
            responses.append(upstream)
        for response in responses:
            self.assertTrue(response.closed, 'relay returned while its owned upstream remained open')
            response.peer.settimeout(.5)
            try:
                self.assertEqual(response.peer.recv(1), b'', 'far end did not observe upstream hangup')
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

    def test_explicit_http_refusal_releases_owned_response(self):
        self.exercise(acquisition='http-error')

    def test_automatic_retry_releases_both_responses(self):
        self.exercise(acquisition='automatic-retry')

    def test_authentication_refusal_closes_without_retry(self):
        self.exercise(acquisition='automatic-refusal')


if __name__ == '__main__':
    unittest.main(verbosity=2)
