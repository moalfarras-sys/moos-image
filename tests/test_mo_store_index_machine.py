#!/usr/bin/env python3
"""machine.json: what this computer is, for Mo Store's compatibility verdicts.

`moos-store-index --print-machine` runs synchronously before the Store's first frame, so it
reads files only, must stay fast, and a fact it cannot read is null — never an error. Free
space is measured where apps install (~/.local/share), never on `/`, which on MoOS is a
read-only composefs that always reads 100% full.

Every fixture machine here is a private tree (MOOS_STORE_MACHINE_ROOT) with a private HOME.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
INDEXER = Path(os.environ.get("MOOS_STORE_INDEX_UNDER_TEST")
               or ROOT / "system_files/usr/bin/moos-store-index")


def load_indexer():
    loader = importlib.machinery.SourceFileLoader("moos_store_index_machine", str(INDEXER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[loader.name] = module
    loader.exec_module(module)
    return module


index = load_indexer()

KEYS = ["android", "arch", "cpu_cores", "engines", "free_bytes", "gpu", "memory_bytes",
        "screen", "session", "swap_bytes", "windows"]


def edid(maker: str, product: int, serial: int, week: int, year: int) -> bytes:
    packed = sum((ord(letter) - 64) << shift for letter, shift in zip(maker, (10, 5, 0)))
    blob = bytearray(128)
    blob[:8] = b"\x00\xff\xff\xff\xff\xff\xff\x00"
    blob[8:10] = packed.to_bytes(2, "big")
    blob[10:12] = product.to_bytes(2, "little")
    blob[12:16] = serial.to_bytes(4, "little")
    blob[16], blob[17] = week, year - 1990
    return bytes(blob)


class Fixture:
    def __init__(self, base: Path):
        self.root = base / "root"
        self.home = base / "home"
        self.root.mkdir()
        self.home.mkdir()

    def file(self, path: str, content: str | bytes) -> Path:
        target = self.root / path.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")
        return target

    def home_file(self, path: str, content: str) -> None:
        target = self.home / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def gpu(self, card: str, bus: str, vendor: str, driver: str, *, vram: int | None = None,
            boot_vga: bool = False) -> None:
        device = self.root / "sys/devices/pci0000:00" / bus
        device.mkdir(parents=True)
        (device / "vendor").write_text(vendor + "\n", encoding="ascii")
        (device / "boot_vga").write_text("1\n" if boot_vga else "0\n", encoding="ascii")
        if vram is not None:
            (device / "mem_info_vram_total").write_text(f"{vram}\n", encoding="ascii")
        drivers = self.root / "sys/bus/pci/drivers" / driver
        drivers.mkdir(parents=True, exist_ok=True)
        (device / "driver").symlink_to(drivers)
        card_dir = self.root / "sys/class/drm" / card
        card_dir.mkdir(parents=True)
        (card_dir / "device").symlink_to(device)

    def connector(self, name: str, status: str, blob: bytes = b"") -> None:
        folder = self.root / "sys/class/drm" / name
        folder.mkdir(parents=True)
        (folder / "status").write_text(status + "\n", encoding="ascii")
        if blob:
            (folder / "edid").write_bytes(blob)

    def environment(self, **extra: str) -> dict:
        values = {"HOME": str(self.home), "XDG_DATA_HOME": str(self.home / ".local/share"),
                  "XDG_CACHE_HOME": str(self.home / ".cache"),
                  "XDG_STATE_HOME": str(self.home / ".local/state"),
                  "XDG_CONFIG_HOME": str(self.home / ".config"),
                  "XDG_SESSION_TYPE": "wayland",
                  "MOOS_STORE_MACHINE_ROOT": str(self.root)}
        values.update(extra)
        return values

    def facts(self, engines=("android", "linux", "windows"), **extra: str) -> dict:
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(("XDG_", "MOOS_"))}
        environment.update(self.environment(**extra))
        with mock.patch.dict(os.environ, environment, clear=True):
            return index.machine_facts(None if engines is None else list(engines), self.root)


KWIN_OUTPUTS = [
    {"name": "outputs", "data": [
        {"connectorName": "HDMI-A-1", "edidIdentifier": "PHL 1219 16843009 9 2018 0",
         "mode": {"width": 3840, "height": 2160, "refreshRate": 60000}, "scale": 2.5},
        {"connectorName": "HDMI-A-1", "edidIdentifier": "XXX 10321 65536 20 2019 0",
         "mode": {"width": 1920, "height": 1080, "refreshRate": 60000}, "scale": 1},
        {"connectorName": "Virtual-virtual-xdp-kde-",
         "mode": {"width": 1280, "height": 720, "refreshRate": 60000}, "scale": 1},
    ]},
    {"name": "setups", "data": [
        {"lidClosed": False, "outputs": [{"enabled": True, "outputIndex": 0, "priority": 1}]},
        {"lidClosed": False, "outputs": [{"enabled": True, "outputIndex": 1, "priority": 1},
                                         {"enabled": True, "outputIndex": 2, "priority": 2}]},
    ]},
]


def desktop_with_two_gpus(fixture: Fixture) -> None:
    fixture.file("/proc/meminfo", "MemTotal:       16187820 kB\nMemFree: 1 kB\n"
                                  "SwapTotal:       8388604 kB\n")
    fixture.gpu("card0", "0000:00:02.0", "0x8086", "i915", boot_vga=True)
    fixture.gpu("card1", "0000:01:00.0", "0x10de", "nvidia")
    fixture.file("/proc/driver/nvidia/gpus/0000:01:00.0/information",
                 "Model: \t\t NVIDIA GeForce RTX 2080 SUPER\nIRQ: 135\n")
    fixture.connector("card1-HDMI-A-1", "connected", edid("PHL", 1219, 16843009, 9, 2018))
    fixture.connector("card1-DP-1", "disconnected")
    fixture.file("/var/lib/waydroid/waydroid.cfg", "[waydroid]\n")
    fixture.home_file(".config/kwinoutputconfig.json", json.dumps(KWIN_OUTPUTS))
    fixture.home_file(".cache/moos-foreign/windows-x86-old-image.status", "blocked\n")
    newer = fixture.home / ".cache/moos-foreign/windows-x86-new-image.status"
    newer.write_text("available\n", encoding="ascii")
    os.utime(newer, ns=(4_000_000_000_000_000_000, 4_000_000_000_000_000_000))


class MachineFacts(unittest.TestCase):
    def test_a_desktop_reads_back_every_fact(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))
            desktop_with_two_gpus(fixture)
            facts = fixture.facts()
        self.assertEqual(facts["memory_bytes"], 16187820 * 1024)
        self.assertEqual(facts["swap_bytes"], 8388604 * 1024)
        self.assertEqual(facts["gpu"], {"vendor": "nvidia", "discrete": True,
                                        "name": "NVIDIA GeForce RTX 2080 SUPER"})
        self.assertEqual(facts["session"], "wayland")
        self.assertIsInstance(facts["free_bytes"]["apps"], int)
        self.assertEqual(facts["android"], {"ready": True, "initialized": True,
                                            "graphics": "hardware"})
        # No mountinfo in this fixture: whether copies can share extents is unknown; no
        # template settings folder exists yet.
        self.assertEqual(facts["windows"], {"ready": True, "x86_32": True, "reflink": None,
                                            "template": False})
        # The connected monitor is the 4K one (its EDID), not the other HDMI-A-1 screen.
        self.assertEqual(facts["screen"], {"width": 3840, "height": 2160, "scale": 2.5})

    def test_android_on_an_nvidia_only_machine_draws_in_software(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))
            fixture.gpu("card1", "0000:01:00.0", "0x10de", "nvidia", boot_vga=True)
            facts = fixture.facts()
        self.assertEqual(facts["android"]["graphics"], "software")
        self.assertFalse(facts["android"]["initialized"])

    def test_amd_memory_tells_a_card_from_an_apu(self):
        for vram, discrete in ((512 * 1024 ** 2, False), (8 * 1024 ** 3, True)):
            with self.subTest(vram=vram), tempfile.TemporaryDirectory() as raw:
                fixture = Fixture(Path(raw))
                fixture.gpu("card0", "0000:03:00.0", "0x1002", "amdgpu", vram=vram,
                            boot_vga=True)
                gpu = fixture.facts()["gpu"]
                self.assertEqual((gpu["vendor"], gpu["discrete"]), ("amd", discrete))

    def test_engines_that_are_not_ready_and_an_unknown_registry(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))
            facts = fixture.facts(engines=("linux",))
            self.assertEqual((facts["android"]["ready"], facts["windows"]["ready"]),
                             (False, False))
            facts = fixture.facts(engines=None)
            self.assertEqual((facts["android"]["ready"], facts["windows"]["ready"]),
                             (None, None))

    def test_a_machine_with_nothing_readable_is_all_unknown_never_an_error(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))
            fixture.home.rmdir()
            facts = fixture.facts(XDG_SESSION_TYPE="not a session!")
        self.assertIsNone(facts["memory_bytes"])
        self.assertIsNone(facts["gpu"])
        self.assertIsNone(facts["session"])
        self.assertIsNone(facts["screen"])
        self.assertIsNone(facts["android"]["graphics"])
        self.assertFalse(facts["windows"]["x86_32"])

    def test_free_space_is_never_measured_on_the_root_filesystem(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))
            facts = fixture.facts(HOME="/nonexistent-home-for-test",
                                  XDG_DATA_HOME="/nonexistent-home-for-test/.local/share")
        self.assertIsNone(facts["free_bytes"]["apps"])

    def test_an_ambiguous_screen_is_unknown_and_visual_tier_facts_come_first(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))
            fixture.connector("card0-DP-1", "connected")
            fixture.connector("card0-DP-2", "connected")
            fixture.home_file(".config/kwinoutputconfig.json", json.dumps([
                {"name": "outputs", "data": [
                    {"connectorName": "DP-1", "mode": {"width": 2560, "height": 1440},
                     "scale": 1.25},
                    {"connectorName": "DP-2", "mode": {"width": 1920, "height": 1080},
                     "scale": 1}]},
                {"name": "setups", "data": []}]))
            self.assertIsNone(fixture.facts()["screen"])
            fixture.home_file(".local/state/moos-visual-tier.json", json.dumps(
                {"tier": "balanced", "facts": {"gpu_class": "integrated",
                                               "gpu_drivers": ["i915"],
                                               "screen": {"width": 2560, "height": 1440,
                                                          "scale": 1.25}}}))
            facts = fixture.facts()
        self.assertEqual(facts["screen"], {"width": 2560, "height": 1440, "scale": 1.25})
        self.assertEqual(facts["gpu"], {"vendor": "intel", "name": None, "discrete": False})


class PrintMachine(unittest.TestCase):
    def test_the_document_has_the_contracts_keys_and_is_quick(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = Fixture(Path(raw))
            desktop_with_two_gpus(fixture)
            environment = {key: value for key, value in os.environ.items()
                           if not key.startswith(("XDG_", "MOOS_"))}
            environment.update(fixture.environment(
                DBUS_SESSION_BUS_ADDRESS="unix:path=/nonexistent"))
            result = subprocess.run([sys.executable, str(INDEXER), "--print-machine"],
                                    text=True, capture_output=True, check=False,
                                    env=environment)
            self.assertEqual(result.returncode, 0, result.stderr)
            document = json.loads(result.stdout)
            self.assertEqual(sorted(document), KEYS)
            self.assertEqual(sorted(document["android"]), ["graphics", "initialized", "ready"])
            self.assertEqual(sorted(document["windows"]), ["ready", "reflink", "template", "x86_32"])
            self.assertEqual(sorted(document["free_bytes"]), ["apps"])
            self.assertEqual(document["screen"], {"width": 3840, "height": 2160, "scale": 2.5})
            # The work itself, without interpreter start-up, inside the 0.15 s budget.
            with mock.patch.dict(os.environ, environment, clear=True):
                started = time.perf_counter()
                index.machine_document(root=fixture.root)
                self.assertLess(time.perf_counter() - started, 0.15)

    def test_the_filtering_profile_keeps_its_two_keys(self):
        self.assertEqual(sorted(index.machine_profile()), ["arch", "engines"])


if __name__ == "__main__":
    unittest.main()
