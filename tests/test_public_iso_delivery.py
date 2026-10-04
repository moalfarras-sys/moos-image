#!/usr/bin/env python3
"""Delivery regressions: a valid URL or status alone cannot qualify an ISO."""
import hashlib
import importlib.util
import io
from pathlib import Path
import unittest


path = Path(__file__).resolve().parents[1] / "scripts/verify-public-iso.py"
spec = importlib.util.spec_from_file_location("public_iso_delivery", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DATA = b"MoOS ISO fixture\x00" * 10000
SHA = hashlib.sha256(DATA).hexdigest()
URL = "https://downloads.example.org/moos.iso"


class Response(io.BytesIO):
    def __init__(self, body, status, headers, url=URL):
        super().__init__(body)
        self.status, self.headers, self.url = status, headers, url

    def geturl(self):
        return self.url


class Host:
    def __init__(self, *, full=None, range_status=206, range_header=None, length=None,
                 full_status=200, encoding=None, destination=URL, resume=True, tail=None):
        self.full = DATA if full is None else full
        self.range_status, self.full_status = range_status, full_status
        self.range_header = range_header
        self.length = str(len(DATA)) if length is None else length
        self.encoding, self.destination = encoding, destination
        self.resume, self.tail = resume, tail
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        if request.get_header("Range"):
            start, end = map(int, request.get_header("Range").removeprefix("bytes=").split("-"))
            body = DATA[start:end + 1] if start == 0 or self.tail is None else self.tail
            return Response(body, self.range_status if start == 0 or self.resume else 200, {
                "Content-Range": self.range_header or f"bytes {start}-{end}/{len(DATA)}"
            }, self.destination)
        headers = {"Content-Length": self.length}
        if self.encoding:
            headers["Content-Encoding"] = self.encoding
        return Response(self.full, self.full_status, headers, self.destination)


class DeliveryTests(unittest.TestCase):
    def verify(self, host):
        return module.verify_transfer(URL, len(DATA), SHA, opener=host)

    def test_real_bytes_are_hashed_and_no_authentication_is_sent(self):
        host = Host()
        report = self.verify(host)
        self.assertEqual(report["sha256"], SHA)
        self.assertEqual(report["sizeBytes"], len(DATA))
        self.assertTrue(report["anonymous"])
        self.assertEqual(len(host.requests), 3)
        for request in host.requests:
            self.assertIsNone(request.get_header("Authorization"))
            self.assertIsNone(request.get_header("Cookie"))
        self.assertEqual(host.requests[0].get_header("Range"), "bytes=0-65535")
        self.assertEqual(host.requests[1].get_header("Range"), f"bytes={len(DATA)-65536}-{len(DATA)-1}")

    def test_resume_must_work_from_a_nonzero_offset(self):
        with self.assertRaisesRegex(ValueError, "byte-range"):
            self.verify(Host(resume=False))

    def test_resume_must_return_the_same_signed_bytes(self):
        with self.assertRaisesRegex(ValueError, "resume range"):
            self.verify(Host(tail=b"x" * 65536))

    def test_hosts_ignoring_ranges_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "byte-range"):
            self.verify(Host(range_status=200))

    def test_wrong_file_length_in_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Content-Range"):
            self.verify(Host(range_header="bytes 0-65535/999999"))

    def test_wrong_content_length_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "exact trusted ISO size"):
            self.verify(Host(length="99999"))

    def test_error_page_with_http_200_is_not_an_iso(self):
        with self.assertRaises(ValueError):
            self.verify(Host(full=b"<html>Unavailable</html>"))

    def test_changed_bytes_with_the_same_size_are_rejected(self):
        changed = DATA[:-1] + bytes([DATA[-1] ^ 1])
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            self.verify(Host(full=changed))

    def test_truncated_and_oversized_bodies_are_rejected(self):
        for body in (DATA[:-1], DATA + b"x"):
            with self.subTest(size=len(body)), self.assertRaises(ValueError):
                self.verify(Host(full=body))

    def test_redirect_to_http_or_an_authenticated_url_is_rejected(self):
        for destination in ("http://downloads.example.org/moos.iso", "https://user:pass@example.org/moos.iso"):
            with self.subTest(url=destination), self.assertRaises(ValueError):
                self.verify(Host(destination=destination))

    def test_transformed_and_partial_full_downloads_are_rejected(self):
        for host in (Host(encoding="gzip"), Host(full_status=206)):
            with self.assertRaises(ValueError):
                self.verify(host)

    def test_input_is_rejected_before_network_access(self):
        host = Host()
        for url in ("http://example.org/moos.iso", "https://u:p@example.org/moos.iso",
                    "https://@example.org/moos.iso", "https://:@example.org/moos.iso", URL + "#fragment"):
            with self.assertRaises(ValueError):
                module.verify_transfer(url, len(DATA), SHA, opener=host)
        self.assertEqual(host.requests, [])


if __name__ == "__main__":
    unittest.main()
