#!/usr/bin/env python3
"""Native CMake transfers: failed/partial/corrupt inputs never become archives."""
from pathlib import Path
import hashlib
import http.server
import shutil
import subprocess
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "moplayer/linux/cmake/VerifiedArchive.cmake"
PAYLOAD = b"private native archive fixture\n"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def cmake_literal(value):
    # CMake bracket arguments preserve UTF-8, backslashes and ${...} literally.
    # JSON's ASCII \u escapes are not CMake escapes. Select a delimiter that
    # cannot terminate inside the argument.
    delimiter = ""
    while "]" + delimiter + "]" in value:
        delimiter += "="
    return "[" + delimiter + "[" + value + "]" + delimiter + "]"


class NativeArchive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                cls.requests.append(self.path)
                if self.path == "/good":
                    self.send_response(200); self.end_headers(); self.wfile.write(PAYLOAD)
                elif self.path == "/partial":
                    self.send_response(200); self.send_header("Content-Length", "999")
                    self.end_headers(); self.wfile.write(b"partial"); self.close_connection = True
                elif self.path == "/corrupt":
                    self.send_response(200); self.end_headers(); self.wfile.write(b"wrong bytes")
                else:
                    self.send_response(503); self.end_headers()

            def log_message(self, *args):
                pass

        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def probe(self, routes, original=None, symlink=False, unfinished=False):
        if not shutil.which("cmake"):
            self.skipTest("native CMake unavailable")
        (ROOT / "test-results").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="native-archive-", dir=ROOT / "test-results") as tmp:
            root = Path(tmp) / "مسار عربي ${literal} ]] ]=]"
            root.mkdir()
            archive = root / "archive.tar.gz"
            target = root / "protected"; target.write_bytes(b"untouched")
            if symlink:
                archive.symlink_to(target)
            elif original is not None:
                archive.write_bytes(original)
            if unfinished:
                archive.with_name(archive.name + ".moos-download").write_bytes(b"interrupted")
            urls = [f"http://127.0.0.1:{self.server.server_port}/{route}" for route in routes]
            script = root / "probe.cmake"
            script.write_text("cmake_minimum_required(VERSION 3.19)\ninclude(" + cmake_literal(str(HELPER))
                              + ")\nmoos_verified_archive(" + cmake_literal(str(archive)) + " "
                              + cmake_literal(DIGEST) + " " + " ".join(map(cmake_literal, urls)) + ")\n")
            self.requests.clear()
            result = subprocess.run(["cmake", "-P", str(script)], capture_output=True, text=True, timeout=40)
            return (result, archive.read_bytes() if archive.exists() else None,
                    target.read_bytes(), list(self.requests),
                    archive.with_name(archive.name + ".moos-download").exists())

    def test_http_partial_and_corrupt_inputs_use_only_verified_fallback(self):
        for first in ("unavailable", "partial", "corrupt"):
            with self.subTest(first=first):
                result, data, _, requests, pending = self.probe([first, "good"])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(data, PAYLOAD)
                self.assertEqual(requests, ["/" + first, "/good"])
                self.assertFalse(pending)

    def test_failed_locations_preserve_previous_bytes_and_fail_configuration(self):
        result, data, _, requests, pending = self.probe(["corrupt", "unavailable"], b"old input")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(data, b"old input")
        self.assertEqual(len(requests), 2)
        self.assertFalse(pending)

    def test_verified_existing_input_needs_no_network(self):
        result, data, _, requests, _ = self.probe(["unavailable"], PAYLOAD)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data, PAYLOAD)
        self.assertEqual(requests, [])

    def test_link_and_interrupted_download_are_preserved_without_network(self):
        for arguments in ({"symlink": True}, {"unfinished": True}):
            with self.subTest(arguments=arguments):
                result, _, protected, requests, _ = self.probe(["good"], **arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(protected, b"untouched")
                self.assertEqual(requests, [])

    def test_upstream_locations_pin_and_plugin_order(self):
        source = (ROOT / "moplayer/linux/CMakeLists.txt").read_text()
        self.assertLess(source.index("moos_verified_archive("), source.index("include(flutter/generated_plugins.cmake)"))
        self.assertIn("2b1bff6f717f9725c70bf8d79e4786da13de8a270059e4ba0bdd262ae7be46eb", source)
        self.assertIn("https://codeload.github.com/microsoft/mimalloc/tar.gz/refs/tags/v2.1.2", source)
        self.assertIn("TLS_VERIFY ON", HELPER.read_text())

    def test_both_terminal_font_transfers_keep_the_exact_asset_and_digest(self):
        for name in ("build_files/build.sh", "build_files/build-arm.sh"):
            source = (ROOT / name).read_text()
            section = source[source.index("kawkab_ver=0.501"):source.index("fc-cache -f /usr/share/fonts/kawkab-mono")]
            self.assertIn("https://api.github.com/repos/aiaf/kawkab-mono/releases/assets/1214878", section)
            self.assertIn("Accept: application/octet-stream", section)
            self.assertIn("--max-time 180", section)
            self.assertIn("11c06f57dddefaf0166d74caaa072865ab6ff8d34076e7ec5d2c20edda145666", section)
            self.assertLess(section.index("sha256sum -c -"), section.index("python3 -m zipfile"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
