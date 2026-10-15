#!/usr/bin/env python3
"""usr/lib/moos/moos_android_apk.py reads what the APK Android keeps says, and holds the one rule
moos-storectl and moos-store-index share for "is the catalogue's pin an update for this app?".

The APKs here are real ones in miniature: a zip holding a compiled AndroidManifest.xml (Android's
binary XML, as aapt2 writes it: string pool, resource map, the android namespace, a <manifest>
element) and, before the central directory, an APK Signing Block with a v2 or v3 signer. apk() is
also the fixture builder for tests/test_mo_store_pinned_updates.py.

  Manifest             package, version code (decimal, hex, with versionCodeMajor) and version
                       name, from UTF-16 and UTF-8 string pools, by resource id or by name;
                       anything else says None
  Signer               the first certificate of the v3 block, else v2; none without a block
  OneApk               through no link, a regular file only; the digest only at the pin's size;
                       facts remembered by file identity, and kept as JSON
  WhereAndroidKeepsIt  both of Android's folder layouts; two copies, links, another package and
                       an unreadable folder are told apart from one APK
  ThePin               the version code in the main repository's file name
  TheRule              pin_is_update(): what Android keeps decides, else the Store's own record

Nothing here reaches the network, a display, the session bus or the person's real home.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import types
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system_files/usr/lib/moos"))
import moos_android_apk as apkfacts  # noqa: E402

ANDROID_NS = "http://schemas.android.com/apk/res/android"
NO_INDEX = 0xFFFFFFFF
V2, V3 = 0x7109871A, 0xF05368C0
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
# What each APK built here says about itself, by its SHA-256: the Android stand-in of the
# storectl suite reads it from here instead of parsing the file with the code under test.
FACTS: dict[str, tuple[str | None, int | None, str | None]] = {}


def _length8(count: int) -> bytes:
    """A UTF-8 string pool length as aapt2 writes it: one byte below 0x80, else two."""
    return bytes([count]) if count < 0x80 else bytes([0x80 | (count >> 8), count & 0xFF])


def _pool(strings: list[str], utf8: bool) -> bytes:
    offsets, blob = [], b""
    for text in strings:
        offsets.append(len(blob))
        if utf8:
            data = text.encode("utf-8")
            blob += _length8(len(text)) + _length8(len(data)) + data + b"\0"
        else:
            blob += struct.pack("<H", len(text)) + text.encode("utf-16-le") + b"\0\0"
    blob += b"\0" * (-len(blob) % 4)
    start = 28 + 4 * len(strings)
    return (struct.pack("<HHIIIIII", 0x0001, 28, start + len(blob), len(strings), 0,
                        0x100 if utf8 else 0, start, 0)
            + struct.pack(f"<{len(strings)}I", *offsets) + blob)


def axml(package: str | None, version_code: int | None, version_name: str | int | None = None, *,
         major: int | None = None, code_type: int = 0x10, name_type: int = 0x03,
         utf8: bool = False, resource_map: bool = True, root: str = "manifest") -> bytes:
    """A compiled AndroidManifest.xml whose <manifest> element carries these attributes."""
    # (name, android.R.attr id, in the android namespace, value type, value)
    attributes = []
    if version_code is not None:
        attributes.append(("versionCode", 0x0101021B, True, code_type, version_code))
    if version_name is not None:
        attributes.append(("versionName", 0x0101021C, True, name_type, version_name))
    if major is not None:
        attributes.append(("versionCodeMajor", 0x01010576, True, 0x10, major))
    if package is not None:
        attributes.append(("package", None, False, 0x03, package))
    mapped = [name for name, resource, *_ in attributes if resource is not None]
    texts = [value for *_, kind, value in attributes if kind == 0x03]
    strings = list(dict.fromkeys(mapped + ["android", ANDROID_NS, root]
                                 + [name for name, resource, *_ in attributes if resource is None]
                                 + texts))
    index = {text: number for number, text in enumerate(strings)}
    chunks = _pool(strings, utf8)
    if resource_map and mapped:
        ids = [resource for _name, resource, *_ in attributes if resource is not None]
        chunks += struct.pack("<HHI", 0x0180, 8, 8 + 4 * len(ids)) + struct.pack(f"<{len(ids)}I", *ids)
    chunks += struct.pack("<HHIIIII", 0x0100, 16, 24, 1, NO_INDEX, index["android"], index[ANDROID_NS])
    body = b""
    for name, _resource, android, kind, value in attributes:
        raw = index[value] if kind == 0x03 else NO_INDEX
        data = index[value] if kind == 0x03 else value
        body += struct.pack("<IIIHBBI", index[ANDROID_NS] if android else NO_INDEX, index[name],
                            raw, 8, 0, kind, data)
    extension = struct.pack("<IIHHHHHH", NO_INDEX, index[root], 20, 20, len(attributes), 0, 0, 0)
    chunks += struct.pack("<HHIII", 0x0102, 16, 16 + len(extension) + len(body), 1, NO_INDEX) \
        + extension + body
    return struct.pack("<HHI", 0x0003, 8, 8 + len(chunks)) + chunks


def _prefixed(data: bytes) -> bytes:
    return struct.pack("<I", len(data)) + data


def signing_block(certificates: dict[int, bytes]) -> bytes:
    """An APK Signing Block: for each scheme, one signer whose certificate is the one given, in
    order (apksigner writes v2 first)."""
    pairs = b""
    for scheme, certificate in certificates.items():
        signed = _prefixed(b"") + _prefixed(_prefixed(certificate)) + _prefixed(b"")
        signer = _prefixed(signed) + _prefixed(b"") + _prefixed(b"")
        value = _prefixed(_prefixed(signer))
        pairs += struct.pack("<QI", 4 + len(value), scheme) + value
    size = len(pairs) + 8 + 16
    return struct.pack("<Q", size) + pairs + struct.pack("<Q", size) + b"APK Sig Block 42"


def with_signing_block(archive: bytes, block: bytes) -> bytes:
    """The zip with `block` between its last entry and its central directory, as apksigner puts it."""
    end = archive.rfind(b"PK\x05\x06")
    directory = struct.unpack_from("<I", archive, end + 16)[0]
    record = bytearray(archive[end:])
    struct.pack_into("<I", record, 16, directory + len(block))
    return archive[:directory] + block + archive[directory:end] + bytes(record)


def apk(package: str | None, version_code: int | None, version_name: str | None = None, *,
        signer: bytes | None = b"the publisher's key", scheme: int = V2, payload: bytes = b"",
        manifest: bytes | None = None) -> bytes:
    """A small, real APK; the same arguments give the same bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name, data in (("AndroidManifest.xml",
                            manifest if manifest is not None else axml(package, version_code,
                                                                       version_name)),
                           ("classes.dex", b"dex\n035\0" + payload)):
            archive.writestr(zipfile.ZipInfo(name, FIXED_TIME), data)
    body = buffer.getvalue()
    if signer is not None:
        body = with_signing_block(body, signing_block({scheme: signer}))
    FACTS[sha256(body)] = (package, version_code,
                           hashlib.sha256(signer).hexdigest() if signer is not None else None)
    return body


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Folder(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.data = self.base / "waydroid/data"

    def put(self, body: bytes, folder: str) -> Path:
        path = self.data / "app" / folder / "base.apk"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return path


# ── the manifest ───────────────────────────────────────────────────────────────────────────────
class Manifest(unittest.TestCase):
    def test_package_version_code_and_name(self):
        for utf8 in (False, True):
            with self.subTest(utf8=utf8):
                self.assertEqual(apkfacts.manifest_facts(
                    axml("org.videolan.vlc", 13070108, "3.7.1", utf8=utf8)),
                    ("org.videolan.vlc", 13070108, "3.7.1"))

    def test_a_long_utf8_string_and_arabic_text(self):
        name = "٣.٧.١-" + "x" * 300
        self.assertEqual(apkfacts.manifest_facts(axml("org.example.app", 7, name, utf8=True))[2], name)

    def test_a_hex_version_code_and_the_major_part(self):
        self.assertEqual(apkfacts.manifest_facts(axml("org.example.app", 0x1F, code_type=0x11))[1], 0x1F)
        self.assertEqual(apkfacts.manifest_facts(axml("org.example.app", 5, major=2))[1], (2 << 32) | 5)

    def test_without_a_resource_map_the_android_names_are_read(self):
        self.assertEqual(apkfacts.manifest_facts(axml("org.example.app", 42, "1.0", resource_map=False)),
                         ("org.example.app", 42, "1.0"))

    def test_a_reference_is_not_a_version(self):
        # android:versionCode="@integer/…" and android:versionName="@string/…" name resources
        # this reader does not open: neither is guessed.
        self.assertEqual(apkfacts.manifest_facts(axml("org.example.app", 0x7F040001, code_type=0x01)),
                         ("org.example.app", None, None))
        name = axml("org.example.app", 42, 0x7F0B0001, name_type=0x01)
        self.assertEqual(apkfacts.manifest_facts(name), ("org.example.app", 42, None))

    def test_another_root_element_or_damaged_bytes_say_nothing(self):
        good = axml("org.example.app", 42, "1.0")
        self.assertEqual(apkfacts.manifest_facts(axml("org.example.app", 42, root="application")),
                         (None, None, None))
        for broken in (b"", b"\x03\x00\x08\x00", good[:40], good[:-8], b"\x00" * 64,
                       good[:8] + b"\xff" * (len(good) - 8)):
            with self.subTest(length=len(broken)):
                self.assertEqual(apkfacts.manifest_facts(broken), (None, None, None))

    def test_a_string_that_runs_out_of_its_pool_says_nothing(self):
        data = bytearray(axml("org.example.app", 42, "1.0"))
        # The first string's length, made longer than the whole pool.
        struct.pack_into("<H", data, 8 + 28 + 4 * struct.unpack_from("<I", data, 8 + 8)[0], 0x7000)
        self.assertEqual(apkfacts.manifest_facts(bytes(data)), (None, None, None))


# ── the signer ─────────────────────────────────────────────────────────────────────────────────
class Signer(Folder):
    def facts(self, body: bytes):
        return apkfacts.read_apk(self.put(body, "~~a==/org.example.app-a=="))

    def test_the_v2_signers_certificate(self):
        self.assertEqual(self.facts(apk("org.example.app", 1, signer=b"key A")).signer,
                         sha256(b"key A"))

    def test_v3_comes_before_v2(self):
        # A rotated key: v2 still names the first key for older Android, v3 the one in use.
        body = apk("org.example.app", 1, signer=None)
        block = signing_block({V2: b"key A", V3: b"key B"})
        self.assertEqual(self.facts(with_signing_block(body, block)).signer, sha256(b"key B"))
        self.assertEqual(self.facts(apk("org.example.app", 1, signer=b"key B", scheme=V3)).signer,
                         sha256(b"key B"))

    def test_no_block_or_a_damaged_one_names_no_signer(self):
        self.assertIsNone(self.facts(apk("org.example.app", 1, signer=None)).signer)
        body = bytearray(apk("org.example.app", 1, signer=b"key A"))
        magic = bytes(body).rfind(b"APK Sig Block 42")
        body[magic - 8:magic] = struct.pack("<Q", 10 ** 12)
        damaged = self.facts(bytes(body))
        self.assertIsNone(damaged.signer)
        self.assertEqual(damaged.version_code, 1, "the manifest is read all the same")


# ── one APK ────────────────────────────────────────────────────────────────────────────────────
class OneApk(Folder):
    def setUp(self):
        super().setUp()
        self.body = apk("org.example.app", 26092932, "2026.09.29", signer=b"key A")
        self.path = self.put(self.body, "~~a==/org.example.app-a==")

    def test_every_fact(self):
        facts = apkfacts.read_apk(self.path, len(self.body))
        self.assertEqual((facts.package, facts.version_code, facts.version_name, facts.signer,
                          facts.sha256),
                         ("org.example.app", 26092932, "2026.09.29", sha256(b"key A"),
                          sha256(self.body)))

    def test_the_digest_is_read_only_at_the_pins_size(self):
        self.assertIsNone(apkfacts.read_apk(self.path, len(self.body) + 1).sha256)
        self.assertEqual(apkfacts.read_apk(self.path).sha256, sha256(self.body))
        self.assertIsNone(apkfacts.read_apk(self.path, unsized_limit=len(self.body) - 1).sha256)

    def test_a_link_a_folder_or_a_pipe_is_not_read(self):
        link = self.base / "link.apk"
        link.symlink_to(self.path)
        self.assertIsNone(apkfacts.read_apk(link))
        self.assertIsNone(apkfacts.read_apk(self.path.parent))
        pipe = self.base / "pipe.apk"
        os.mkfifo(pipe)
        self.assertIsNone(apkfacts.read_apk(pipe), "a pipe was opened for reading")
        self.assertIsNone(apkfacts.read_apk(self.base / "missing.apk"))

    def test_a_file_that_is_no_zip_still_has_its_digest(self):
        path = self.put(b"PK\x03\x04 not really", "org.example.other-1")
        facts = apkfacts.read_apk(path)
        self.assertEqual((facts.package, facts.version_code, facts.signer, facts.sha256),
                         (None, None, None, sha256(b"PK\x03\x04 not really")))

    def test_remembered_facts_are_reused_while_the_file_is_unchanged(self):
        first = apkfacts.read_apk(self.path, len(self.body))
        self.assertIs(apkfacts.read_apk(self.path, len(self.body),
                                        remembered={str(self.path): first}), first)
        # A cache that takes items keeps what each read used, under the file's path.
        cache: dict = {}
        facts = apkfacts.kept(self.data, "org.example.app", len(self.body), remembered=cache)
        self.assertEqual(cache, {str(self.path): facts})
        self.assertIs(apkfacts.kept(self.data, "org.example.app", len(self.body), remembered=cache),
                      facts)
        frozen = types.MappingProxyType({str(self.path): first})
        self.assertIs(apkfacts.read_apk(self.path, len(self.body), remembered=frozen), first)
        # Without its digest, remembered facts do not answer for a pin of this size.
        thin = apkfacts.read_apk(self.path, len(self.body) + 1)
        again = apkfacts.read_apk(self.path, len(self.body), remembered={str(self.path): thin})
        self.assertEqual(again.sha256, sha256(self.body))
        # Another file in the same place is read again.
        replaced = apk("org.example.app", 26092933, signer=b"key A")
        self.path.write_bytes(replaced)
        self.assertEqual(apkfacts.read_apk(self.path, remembered={str(self.path): first}).version_code,
                         26092933)

    def test_facts_kept_as_json_come_back_whole_and_nothing_else_does(self):
        facts = apkfacts.read_apk(self.path, len(self.body))
        kept = json.loads(json.dumps(facts.to_json()))
        self.assertEqual(apkfacts.ApkFacts.from_json(kept), facts)
        for broken in (None, [], {**kept, "extra": 1}, {**kept, "identity": [1, 2]},
                       {**kept, "version_code": "1"}, {**kept, "version_code": -1},
                       {**kept, "sha256": "x" * 64}, {**kept, "package": 7}):
            with self.subTest(broken=broken):
                self.assertIsNone(apkfacts.ApkFacts.from_json(broken))


# ── where Android keeps an app ─────────────────────────────────────────────────────────────────
class WhereAndroidKeepsIt(Folder):
    PACKAGE = "org.example.maps"

    def test_both_layouts(self):
        body = apk(self.PACKAGE, 2)
        self.put(body, f"~~Zm9v==/{self.PACKAGE}-YmFy==")
        self.assertEqual(apkfacts.kept(self.data, self.PACKAGE).version_code, 2)
        other = self.base / "older"
        self.data = other / "waydroid/data"
        self.put(body, f"{self.PACKAGE}-1")
        self.assertEqual(apkfacts.kept(self.data, self.PACKAGE).version_code, 2)

    def test_what_cannot_be_told_apart_is_none(self):
        body = apk(self.PACKAGE, 2)

        def two_copies():
            self.put(body, f"~~YQ==/{self.PACKAGE}-YQ==")
            self.put(body, f"~~Yg==/{self.PACKAGE}-Yg==")

        def a_linked_folder():
            real = self.base / "elsewhere"
            real.mkdir()
            (real / "base.apk").write_bytes(body)
            (self.data / "app/~~YQ==").mkdir(parents=True)
            (self.data / "app/~~YQ==" / f"{self.PACKAGE}-YQ==").symlink_to(real)

        def a_linked_file():
            target = self.base / "elsewhere.apk"
            target.write_bytes(body)
            link = self.put(b"", f"~~YQ==/{self.PACKAGE}-YQ==")
            link.unlink()
            link.symlink_to(target)

        def another_package_with_a_longer_name():
            self.put(body, f"~~YQ==/{self.PACKAGE}.pro-YQ==")

        def a_manifest_naming_another_package():
            self.put(apk("org.example.other", 2), f"~~YQ==/{self.PACKAGE}-YQ==")

        for case in (two_copies, a_linked_folder, a_linked_file,
                     another_package_with_a_longer_name, a_manifest_naming_another_package):
            with self.subTest(case.__name__):
                shutil.rmtree(self.base / "waydroid", ignore_errors=True)
                shutil.rmtree(self.base / "elsewhere", ignore_errors=True)
                (self.base / "elsewhere.apk").unlink(missing_ok=True)
                case()
                self.assertIsNone(apkfacts.kept(self.data, self.PACKAGE))
        self.assertEqual(len(apkfacts.kept_apk_dirs(self.data, self.PACKAGE)), 1)

    def test_a_folder_that_cannot_be_read_is_not_an_empty_one(self):
        self.assertIsNone(apkfacts.kept_apk_dirs(self.data, self.PACKAGE), "no folder at all")
        self.put(apk(self.PACKAGE, 2), f"~~YQ==/{self.PACKAGE}-YQ==")
        self.assertEqual(len(apkfacts.kept_apk_dirs(self.data, self.PACKAGE)), 1)
        self.assertEqual(apkfacts.kept_apk_dirs(self.data, "org.example.none"), [])
        if os.geteuid() != 0:                   # root reads every account's folders
            (self.data / "app").chmod(0o111)
            self.addCleanup((self.data / "app").chmod, 0o755)
            self.assertIsNone(apkfacts.kept_apk_dirs(self.data, self.PACKAGE))
            self.assertIsNone(apkfacts.kept(self.data, self.PACKAGE))


# ── the pin and the rule ───────────────────────────────────────────────────────────────────────
class ThePin(unittest.TestCase):
    def test_the_version_code_in_the_main_repositorys_file_name(self):
        code = apkfacts.pin_version_code
        self.assertEqual(code("https://f-droid.org/repo/app.organicmaps_26092932.apk",
                              "app.organicmaps"), 26092932)
        self.assertEqual(code("https://f-droid.org/repo/org.schabi.newpipe_1015_cb84069.apk",
                              "org.schabi.newpipe"), 1015)
        for url, package in (("https://f-droid.org/repo/org.wikipedia_50610.apk", "app.organicmaps"),
                             ("https://f-droid.org/repo/app.organicmaps.apk", "app.organicmaps"),
                             ("https://f-droid.org/repo/app.organicmaps_1a.apk", "app.organicmaps"),
                             ("https://f-droid.org/repo/app_organicmaps_1.apk", "app.organicmaps"),
                             (None, "app.organicmaps")):
            with self.subTest(url=url):
                self.assertIsNone(code(url, package))


class TheRule(unittest.TestCase):
    PIN = "1" * 64
    SIGNER = sha256(b"key A")

    def kept(self, code=None, signer=None, digest=None):
        return apkfacts.ApkFacts((1, 2, 3, 4, 5), "org.example.app", code, None, signer, digest)

    def update(self, kept, recorded=None, pin_code=20, pin_signer=SIGNER):
        return apkfacts.pin_is_update(pin_sha256=self.PIN, pin_code=pin_code, pin_signer=pin_signer,
                                      kept=kept, recorded_sha256=recorded)

    def test_what_android_keeps_decides(self):
        self.assertFalse(self.update(self.kept(20, self.SIGNER, self.PIN)), "the pin itself")
        self.assertTrue(self.update(self.kept(19, self.SIGNER)), "an older build")
        self.assertFalse(self.update(self.kept(21, self.SIGNER)), "a newer build")
        self.assertFalse(self.update(self.kept(20, self.SIGNER)), "the same version")
        self.assertFalse(self.update(self.kept(19, sha256(b"key B"))), "another key")
        self.assertTrue(self.update(self.kept(19, None)), "a signer that cannot be read")
        self.assertTrue(self.update(self.kept(19, self.SIGNER), pin_signer=None))
        # A record of older bytes does not outvote a build newer than the pin.
        self.assertFalse(self.update(self.kept(21, self.SIGNER), recorded="0" * 64))

    def test_when_android_cannot_be_compared_only_the_stores_record_can_say(self):
        for case, kept, pin_code in (("no APK to read", None, 20),
                                     ("no version code in it", self.kept(None, self.SIGNER), 20),
                                     ("none in the pin's name", self.kept(19, self.SIGNER), None)):
            with self.subTest(case):
                self.assertFalse(self.update(kept, pin_code=pin_code), "no record of the Store's")
                self.assertTrue(self.update(kept, recorded="0" * 64, pin_code=pin_code))
                self.assertFalse(self.update(kept, recorded=self.PIN.upper(), pin_code=pin_code))


if __name__ == "__main__":
    unittest.main()
