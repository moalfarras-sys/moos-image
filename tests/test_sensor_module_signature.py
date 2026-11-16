#!/usr/bin/env python3
"""Real CMS controls for the sensor review helper, not kernel load acceptance."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('sensor_review', ROOT / 'scripts/review/smocf05-module.py')
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


class SignatureIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='moos-sensor-signature-')
        cls.directory = Path(cls.temporary.name)
        for identity in ('expected', 'other'):
            REVIEW.run(['openssl', 'req', '-new', '-x509', '-newkey', 'rsa:2048',
                        '-noenc', '-days', '1', '-subj', '/CN=' + identity + '/',
                        '-keyout', str(cls.directory / (identity + '.key')),
                        '-out', str(cls.directory / (identity + '.pem'))])
        # This is only a detached-signature fixture. Native proof separately
        # compiles and signs the real Linux module with kernel sign-file.
        cls.payload = b'\x7fELF' + bytes(range(256))
        (cls.directory / 'payload').write_bytes(cls.payload)
        REVIEW.run(['openssl', 'cms', '-sign', '-binary', '-noattr', '-md', 'sha256',
                    '-in', str(cls.directory / 'payload'), '-outform', 'DER',
                    '-signer', str(cls.directory / 'expected.pem'),
                    '-inkey', str(cls.directory / 'expected.key'),
                    '-out', str(cls.directory / 'signature')])
        signature = (cls.directory / 'signature').read_bytes()
        cls.signed = (cls.payload + signature +
                      struct.pack('>BBBBB3sI', 0, 0, 2, 0, 0, b'\0' * 3, len(signature)) +
                      REVIEW.MAGIC)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_exact_content_and_certificate(self):
        REVIEW.verify_signature(self.signed, self.directory / 'expected.pem')
        self.assertEqual(REVIEW.split_signature(self.signed)[0], self.payload)

    def test_changed_content_is_rejected_even_with_intact_metadata(self):
        changed = bytearray(self.signed)
        changed[24] ^= 1
        with self.assertRaises(subprocess.CalledProcessError):
            REVIEW.verify_signature(bytes(changed), self.directory / 'expected.pem')

    def test_embedded_signer_does_not_override_the_expected_certificate(self):
        with self.assertRaises(subprocess.CalledProcessError):
            REVIEW.verify_signature(self.signed, self.directory / 'other.pem')

    def test_missing_truncated_and_oversized_signature(self):
        for data in (self.payload, self.signed[:-1], b'\0' * (REVIEW.LIMIT + 1)):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                REVIEW.split_signature(data)

    def test_missing_certificate_is_unavailable_input(self):
        with self.assertRaises(ValueError):
            REVIEW.verify_signature(self.signed, self.directory / 'missing.pem')

    def test_malformed_trailer(self):
        for offset in (1, 8, 9, 12):
            changed = bytearray(self.signed)
            changed[-len(REVIEW.MAGIC)-offset] = 255
            # A changed length can still be within the file bounds. In that
            # case cryptographic content verification must reject the split.
            with self.subTest(offset=offset), self.assertRaises(
                    (ValueError, subprocess.CalledProcessError)):
                REVIEW.verify_signature(bytes(changed), self.directory / 'expected.pem')


if __name__ == '__main__':
    unittest.main()
