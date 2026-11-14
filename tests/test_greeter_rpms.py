#!/usr/bin/env python3
"""Reject unreviewed native login packages before any package transaction."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import ssl
import struct
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('greeter_rpms', ROOT / 'build_files/plasma_login/rpms.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PrivateTLS:
    """A trusted loopback fixture that resets before TLS or serves one body."""
    def __init__(self, root, outcomes, payload):
        self.payload, self.outcomes, self.connections = payload, outcomes, 0
        self.closed = threading.Event()
        self.errors = []
        self.cert, key = root / 'tls.crt', root / 'tls.key'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-days', '1', '-subj', '/CN=localhost',
                        '-addext', 'subjectAltName=IP:127.0.0.1',
                        '-keyout', str(key), '-out', str(self.cert)],
                       capture_output=True, check=True, timeout=10)
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(self.cert, key)
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(5)
        self.listener.settimeout(.1)
        self.url = 'https://127.0.0.1:' + str(self.listener.getsockname()[1]) + '/source.rpm'
        self.thread = threading.Thread(target=self.run, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def run(self):
        while not self.closed.is_set():
            try:
                connection, _peer = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                outcome = self.outcomes[min(self.connections, len(self.outcomes) - 1)]
                self.connections += 1
                connection.settimeout(2)
                if outcome == 'reset':
                    connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
                    connection.close()
                    continue
                with self.context.wrap_socket(connection, server_side=True) as secure:
                    request = bytearray()
                    while b'\r\n\r\n' not in request and len(request) < 4096:
                        data = secure.recv(1024)
                        if not data:
                            break
                        request.extend(data)
                    if outcome == 'missing':
                        status, body = '404 Not Found', b'not found'
                    elif outcome == 'long-retry':
                        status, body = '503 Service Unavailable', b'try later'
                    else:
                        status, body = '200 OK', self.payload
                    retry = 'Retry-After: 86400\r\n' if outcome == 'long-retry' else ''
                    response = ('HTTP/1.1 ' + status + '\r\nContent-Length: ' + str(len(body))
                                + '\r\n' + retry + 'Connection: close\r\n\r\n').encode() + body
                    secure.sendall(response)
            except (OSError, ssl.SSLError) as exc:
                if not self.closed.is_set():
                    self.errors.append(type(exc).__name__)
            finally:
                connection.close()

    def __exit__(self, *_):
        self.closed.set()
        self.listener.close()
        self.thread.join(timeout=3)
        if self.thread.is_alive():
            raise RuntimeError('private TLS fixture did not stop')


class ReviewedSourceDownload(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / 'build_files/plasma_login/build.sh').read_text()

    def test_retry_budget_stays_finite_and_admission_order_is_unchanged(self):
        self.assertIn('--retry 3 --retry-all-errors --retry-delay 2', self.text)
        self.assertIn('--connect-timeout 30 --max-time 120 --retry-max-time 480', self.text)
        self.assertNotIn('--insecure', self.text)
        curl = self.text.index('    source_http="$(curl ')
        digest = self.text.index('sha256sum --check', curl)
        signature = self.text.index('rpmkeys --checksig --verbose', digest)
        signer = self.text.index("grep -F '96bdf4e8710b8f9ffb11d83ddb51f4cb6c33bdbb: OK'", signature)
        archive = self.text.index('    rpm2cpio ', signer)
        self.assertLess(curl, digest)
        self.assertLess(digest, signature)
        self.assertLess(signature, signer)
        self.assertLess(signer, archive)

    def fetch(self, root, server, *, old=False, wrong_digest=False, wrong_signer=False):
        """Execute the real curl/hash/signature shell block in private storage."""
        text = self.text
        begin, end = text.index('    source_http="$(curl '), text.index('    rpm2cpio ')
        block = text[begin:end].replace('/work/', str(root) + '/')
        if old:
            block = block.replace(' --retry-all-errors', '')
        curl = shutil.which('curl')
        self.assertIsNotNone(curl)
        # Certificate trust is private and explicit; no insecure/TLS bypass.
        prefix = ('set -euo pipefail\n'
                  'curl() { ' + shlex.quote(curl) + ' --cacert ' + shlex.quote(str(server.cert))
                  + ' --noproxy 127.0.0.1 "$@"; }\n'
                  'rpmkeys() { printf "%s\\n" ' + shlex.quote('wrong signer' if wrong_signer else
                   '96bdf4e8710b8f9ffb11d83ddb51f4cb6c33bdbb: OK') + '; }\n')
        digest = '0' * 64 if wrong_digest else hashlib.sha256(server.payload).hexdigest()
        result = subprocess.run(['bash', '-c', prefix + block + '\necho SOURCE_ADMITTED\n'],
                                env={**os.environ, 'source_url': server.url, 'source_sha': digest},
                                capture_output=True, text=True, timeout=20)
        return result, root / 'plasma-login.src.rpm'

    @unittest.skipUnless(os.name == 'posix' and shutil.which('curl') and shutil.which('openssl'),
                         'native TLS reset proof requires curl/OpenSSL/POSIX sockets')
    def test_actual_tls_connection_reset_refuses_old_and_fixed_retries_to_exact_bytes(self):
        for old in (True, False):
            with self.subTest(old=old), tempfile.TemporaryDirectory(prefix='moos-login-fetch-') as folder:
                root = Path(folder)
                payload = b'private reviewed SRPM bytes fixture\x00\n'
                with PrivateTLS(root, ['reset', 'ok'], payload) as server:
                    result, archive = self.fetch(root, server, old=old)
                if old:
                    self.assertEqual(result.returncode, 35, result.stderr)
                    self.assertEqual(server.connections, 1)
                    self.assertNotIn('SOURCE_ADMITTED', result.stdout)
                else:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(server.connections, 2)
                    self.assertEqual(archive.read_bytes(), payload)
                    self.assertIn('SOURCE_ADMITTED', result.stdout)
                self.assertEqual(server.errors, [])

    @unittest.skipUnless(os.name == 'posix' and shutil.which('curl') and shutil.which('openssl'),
                         'native permanent fetch proof requires curl/OpenSSL/POSIX sockets')
    def test_exhausted_reset_and_http_failure_remain_refused_after_four_attempts(self):
        for outcome, code in (('reset', 35), ('missing', 22)):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory(prefix='moos-login-fetch-') as folder:
                root = Path(folder)
                with PrivateTLS(root, [outcome], b'never admitted') as server:
                    result, _archive = self.fetch(root, server)
                self.assertEqual(result.returncode, code, result.stderr)
                self.assertEqual(server.connections, 4)
                self.assertNotIn('SOURCE_ADMITTED', result.stdout)

    @unittest.skipUnless(os.name == 'posix' and shutil.which('curl') and shutil.which('openssl'),
                         'native fetched-byte admission proof requires curl/OpenSSL/POSIX sockets')
    def test_download_success_cannot_override_wrong_digest_or_signature(self):
        for change in ('wrong_digest', 'wrong_signer'):
            with self.subTest(change=change), tempfile.TemporaryDirectory(prefix='moos-login-fetch-') as folder:
                root = Path(folder)
                with PrivateTLS(root, ['ok'], b'private fixture payload') as server:
                    result, _archive = self.fetch(root, server, **{change: True})
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(server.connections, 1, 'integrity refusals must not restart the download')
                self.assertNotIn('SOURCE_ADMITTED', result.stdout)

    @unittest.skipUnless(os.name == 'posix' and shutil.which('curl') and shutil.which('openssl'),
                         'native Retry-After budget proof requires curl/OpenSSL/POSIX sockets')
    def test_server_retry_after_cannot_expand_the_total_retry_budget(self):
        with tempfile.TemporaryDirectory(prefix='moos-login-fetch-') as folder:
            root = Path(folder)
            with PrivateTLS(root, ['long-retry'], b'never admitted') as server:
                # A previous exact archive cannot turn the actual HTTP503 into
                # success when curl itself returns0 on a long Retry-After.
                (root / 'plasma-login.src.rpm').write_bytes(server.payload)
                result, _archive = self.fetch(root, server)
            self.assertEqual(result.returncode, 22, result.stderr)
            self.assertEqual(server.connections, 1)
            self.assertNotIn('SOURCE_ADMITTED', result.stdout)


class NativePackagePreflight(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='moos-greeter-rpms-')
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)
        self.source = module.review('6.8.2-1.fc44')
        self.manifest = copy.deepcopy(self.source)
        self.manifest['packages'] = []
        for name in sorted(module.PACKAGES):
            path = self.folder / (name + '.rpm')
            path.write_bytes(b'private fixture: metadata is supplied by the test')
            self.manifest['packages'].append({'name': name, 'file': path.name, 'sha256': module.sha(path)})

    def command(self, arguments):
        if arguments == ['rpm', '--eval', '%{_arch}']:
            return 'x86_64'
        if arguments[:3] == ['rpm', '-q', '--qf']:
            self.assertIn(arguments[-1], module.PACKAGES)
            return '6.8.2-1.fc44 plasma-login-manager-6.8.2-1.fc44.src.rpm'
        if arguments[:3] == ['rpm', '-qp', '--qf']:
            name = Path(arguments[-1]).stem
            return name + ' 6.8.2-1.2.moos1.fc44 x86_64'
        self.fail('unexpected package inspection: ' + repr(arguments))

    def write(self):
        (self.folder / 'manifest.json').write_text(json.dumps(self.manifest))

    def test_reviewed_pair_passes_read_only_preflight(self):
        self.write()
        with patch.object(module, 'command', side_effect=self.command), \
                patch.object(module.subprocess, 'run', side_effect=RuntimeError('no mutation')) as mutation:
            data, selected = module.validate_manifest(self.folder)
        mutation.assert_not_called()
        self.assertEqual(data, self.source)
        self.assertEqual({Path(p).name for p in selected}, {p['file'] for p in self.manifest['packages']})

    def refused(self, inspect=None):
        self.write()
        with patch.object(module, 'command', side_effect=inspect or self.command), \
                patch.object(module.subprocess, 'run', side_effect=RuntimeError('no mutation')) as mutation:
            with self.assertRaises((AssertionError, KeyError, ValueError, FileNotFoundError)):
                module.install(self.folder)
        mutation.assert_not_called()

    def test_manifest_source_drift_is_refused_before_dnf(self):
        original = copy.deepcopy(self.manifest)
        for key, value in [('base', '6.8.3-1.fc44'), ('fixed', 'unreviewed'),
                           ('source_sha256', '0' * 64), ('source_signer', '0' * 40),
                           ('authentication_source_sha256', '0' * 64), ('arch', 'aarch64')]:
            with self.subTest(key=key):
                self.manifest = copy.deepcopy(original)
                self.manifest[key] = value
                self.refused()

    def test_missing_duplicate_and_extra_packages_are_refused_before_dnf(self):
        original = copy.deepcopy(self.manifest)
        for packages in [original['packages'][:1], original['packages'] * 2,
                         original['packages'] + [{'name': 'kernel', 'file': 'kernel.rpm', 'sha256': '0' * 64}]]:
            with self.subTest(packages=packages):
                self.manifest = copy.deepcopy(original)
                self.manifest['packages'] = packages
                self.refused()

    def test_replaced_rpm_path_and_symlink_are_refused_before_dnf(self):
        original = copy.deepcopy(self.manifest)
        for filename in ('../outside.rpm', '/outside.rpm', 'subdir/../package.rpm'):
            with self.subTest(filename=filename):
                self.manifest = copy.deepcopy(original)
                self.manifest['packages'][0]['file'] = filename
                self.refused()
        self.manifest = copy.deepcopy(original)
        target = self.folder / self.manifest['packages'][0]['file']
        target.write_bytes(b'replaced')
        self.refused()
        target.unlink()
        target.symlink_to(self.folder / self.manifest['packages'][1]['file'])
        self.refused()

    def test_actual_rpm_metadata_and_installed_origin_must_match_review(self):
        for wrong in ('newer-installed-base', 'different-source-rpm', 'wrong-package-nvr', 'wrong-architecture'):
            def inspect(arguments):
                value = self.command(arguments)
                if arguments[:2] == ['rpm', '-q']:
                    if wrong == 'newer-installed-base':
                        return value.replace('6.8.2', '6.8.3')
                    if wrong == 'different-source-rpm':
                        return value.replace('plasma-login-manager-6.8.2-1.fc44.src.rpm', 'other.src.rpm')
                if arguments[:2] == ['rpm', '-qp']:
                    if wrong == 'wrong-package-nvr':
                        return value.replace('1.2.moos1', '1')
                    if wrong == 'wrong-architecture':
                        return value.replace('x86_64', 'aarch64')
                return value
            with self.subTest(wrong=wrong):
                self.refused(inspect)

    def test_loaded_settings_binary_requires_its_exact_rpm_payload(self):
        path = self.folder/'kcm_plasmalogin.so'
        path.write_bytes(b'reviewed native settings payload')
        row = f'{path} 32 0 {module.sha(path)} 0100644 root root 0 0 0 X\n'
        with patch.object(module, 'command', return_value=row):
            module.verify_payload('kcm-plasmalogin', path)
            path.write_bytes(b'changed settings payload')
            with self.assertRaises(AssertionError):
                module.verify_payload('kcm-plasmalogin', path)


if __name__ == '__main__':
    unittest.main()
