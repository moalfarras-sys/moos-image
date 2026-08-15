#!/usr/bin/env python3
"""The motion system must match the machine — proven against fake hardware.

/etc/xdg/kwinrc ships one profile for every MoOS install: blur 15, magic lamp,
the full set. That is right on the maintainer's RTX 2080 SUPER and wrong on a
cloud VPS drawing in software, where each blur pass is CPU work per frame.
moos-visual-tier reads the hardware and picks the profile.

These tests build fake /sys, /proc and /dev trees and run the REAL probe against
them, so the thing under test is the classification a user actually gets — not a
string in a file. The contract they hold:

  * a machine with no render node is `essential`, whatever else it has
  * blur is never written above 15 (higher has shipped unreadable surfaces)
  * AnimationDurationFactor is never written as 0 (Kirigami's longDuration
    floors at 1, so 0 is not "off", it is "an animation with a wrong duration")
  * applying twice changes nothing the second time
  * a setting the user changed afterwards is never taken back
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(os.environ.get("MOOS_TEST_ROOT", Path(__file__).resolve().parents[1])).resolve()
TIER = ROOT / "system_files/usr/bin/moos-visual-tier"


def load_module(fake_root: Path):
    """Import the shipped script with MOOS_TIER_ROOT pointed at a fake tree."""
    os.environ["MOOS_TIER_ROOT"] = str(fake_root)
    spec = importlib.util.spec_from_loader(
        "moos_visual_tier",
        importlib.machinery.SourceFileLoader("moos_visual_tier", str(TIER)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


import importlib.machinery  # noqa: E402  (used by load_module above)


class FakeMachine:
    """Builds the handful of files the probe is allowed to read."""

    def __init__(self, root: Path):
        self.root = root

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel.lstrip("/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def gpu(self, card: str, driver: str, *, vram_bytes: int | None = None) -> "FakeMachine":
        device = self.root / f"sys/class/drm/{card}/device"
        device.mkdir(parents=True, exist_ok=True)
        driver_dir = self.root / f"sys/bus/pci/drivers/{driver}"
        driver_dir.mkdir(parents=True, exist_ok=True)
        link = device / "driver"
        if not link.exists():
            os.symlink(driver_dir, link)
        if vram_bytes is not None:
            (device / "mem_info_vram_total").write_text(str(vram_bytes), encoding="utf-8")
        return self

    def render_node(self, name: str = "renderD128") -> "FakeMachine":
        self.write(f"dev/dri/{name}", "")
        return self

    def cpu(self, cores: int) -> "FakeMachine":
        self.write("proc/cpuinfo",
                   "".join(f"processor\t: {i}\nmodel name\t: Fake CPU\n\n"
                           for i in range(cores)))
        return self

    def memory(self, gib: float) -> "FakeMachine":
        self.write("proc/meminfo", f"MemTotal:       {int(gib * 1024 * 1024)} kB\n")
        return self

    def battery(self) -> "FakeMachine":
        self.write("sys/class/power_supply/BAT0/type", "Battery\n")
        return self

    def display(self, width: int, height: int) -> "FakeMachine":
        self.write("sys/class/drm/card0-HDMI-A-1/modes", f"{width}x{height}\n")
        return self


class Classification(unittest.TestCase):
    def tier_of(self, build) -> tuple[str, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build(FakeMachine(root))
            module = load_module(root)
            facts = module.probe()
            tier, _ = module.classify(facts)
            return tier, facts

    def test_the_maintainers_desktop_is_flagship(self) -> None:
        """RTX 2080 SUPER, 16 cores, 16 GB reporting 15.4 GiB, 4K."""
        tier, facts = self.tier_of(lambda m: m
                                   .gpu("card1", "nvidia").render_node()
                                   .cpu(16).memory(15.4).display(3840, 2160))
        self.assertEqual(facts["gpu_class"], "discrete")
        self.assertEqual(tier, "flagship",
                         "a 16 GB machine reports 15.4 GiB — a literal 16 floor "
                         "excluded the maintainer's own desktop")

    def test_a_vps_with_no_render_node_is_essential(self) -> None:
        """moos-cloud: plenty of cores, no GPU. Blur would be CPU work."""
        tier, facts = self.tier_of(lambda m: m.cpu(16).memory(32))
        self.assertEqual(facts["gpu_class"], "software")
        self.assertEqual(facts["render_nodes"], 0)
        self.assertEqual(tier, "essential",
                         "cores and RAM must never buy motion a software "
                         "renderer has to pay for per frame")

    def test_the_real_moos_cloud_vps_is_essential(self) -> None:
        """The cloud box as it ACTUALLY is, which is not what the test above modelled.

        `test_a_vps_with_no_render_node_is_essential` builds a VPS with no
        render node and passes. The real MoOS Cloud server has one, because
        moos-cloud-desktop loads vgem on purpose so KWin's virtual backend will
        offer OpenGL. Read off the live machine:

            /sys/class/drm/card0 -> bochs-drm      (QEMU emulated VGA, no 3D)
            /sys/class/drm/card1 -> faux_driver    (vgem, renders nothing)
            /dev/dri/renderD128                    (published by vgem)
            glxinfo: llvmpipe (LLVM 22.1.8, 256 bits)

        Neither name was matched — `bochs` is not `bochs-drm`, and faux_driver
        was absent — so both counted as real GPUs and the probe answered
        "integrated graphics with 8 cores and 15.6 GiB" -> balanced -> blur on
        at strength 9, in software, for three concurrent Plasma sessions.

        The green gate above is why that survived: it asserted the right answer
        about the wrong machine.
        """
        tier, facts = self.tier_of(lambda m: m
                                   .gpu("card0", "bochs-drm")
                                   .gpu("card1", "faux_driver").render_node()
                                   .cpu(8).memory(15.6).display(1920, 1080))
        self.assertEqual(facts["gpu_class"], "virtual",
                         "a render node published by vgem is not a GPU")
        self.assertEqual(tier, "essential",
                         "llvmpipe must not be asked to pay for blur")

    def test_a_drm_suffixed_driver_is_matched_like_its_bare_name(self) -> None:
        """The suffix is the whole bug: `bochs-drm` must resolve to `bochs`."""
        module = load_module(Path(tempfile.gettempdir()))
        for raw, bare in (("bochs-drm", "bochs"), ("bochs", "bochs"),
                          ("nvidia", "nvidia"), ("virtio_gpu", "virtio_gpu")):
            with self.subTest(driver=raw):
                self.assertEqual(module._driver_key(raw), bare)

    def test_a_real_gpu_beside_vgem_is_still_a_real_gpu(self) -> None:
        """vgem is loadable anywhere; it must never demote real hardware."""
        tier, facts = self.tier_of(lambda m: m
                                   .gpu("card1", "nvidia")
                                   .gpu("card2", "faux_driver").render_node()
                                   .cpu(16).memory(15.4).display(3840, 2160))
        self.assertEqual(facts["gpu_class"], "discrete")
        self.assertEqual(tier, "flagship")

    def test_a_virtual_adapter_without_acceleration_is_essential(self) -> None:
        tier, facts = self.tier_of(lambda m: m
                                   .gpu("card0", "virtio_gpu").cpu(8).memory(16))
        self.assertEqual(facts["gpu_class"], "software")
        self.assertEqual(tier, "essential")

    def test_a_virtual_adapter_WITH_a_render_node_is_not_condemned(self) -> None:
        """virgl/venus give a real context; the render node is what decides."""
        tier, facts = self.tier_of(lambda m: m
                                   .gpu("card0", "virtio_gpu").render_node()
                                   .cpu(8).memory(16))
        self.assertEqual(facts["gpu_class"], "virtual")
        self.assertEqual(tier, "essential",
                         "a virtual adapter still gets the cheap profile, but "
                         "the reason must be the adapter, not a missing node")

    def test_an_integrated_laptop_is_balanced(self) -> None:
        tier, facts = self.tier_of(lambda m: m
                                   .gpu("card0", "i915").render_node()
                                   .cpu(8).memory(16).battery())
        self.assertEqual(facts["gpu_class"], "integrated")
        self.assertTrue(facts["battery"])
        self.assertEqual(tier, "balanced")

    def test_a_small_machine_is_essential_even_with_a_gpu(self) -> None:
        for cores, memory in ((2, 16), (8, 4)):
            with self.subTest(cores=cores, memory=memory):
                tier, _ = self.tier_of(lambda m, c=cores, g=memory: m
                                       .gpu("card0", "amdgpu", vram_bytes=8 * 1024 ** 3)
                                       .render_node().cpu(c).memory(g))
                self.assertEqual(tier, "essential")

    def test_a_big_amd_card_counts_as_discrete_by_its_vram(self) -> None:
        tier, facts = self.tier_of(lambda m: m
                                   .gpu("card0", "amdgpu", vram_bytes=8 * 1024 ** 3)
                                   .render_node().cpu(16).memory(32))
        self.assertEqual(facts["gpu_class"], "discrete")
        self.assertEqual(tier, "flagship")

    def test_an_amd_apu_with_a_small_carveout_is_integrated(self) -> None:
        tier, facts = self.tier_of(lambda m: m
                                   .gpu("card0", "amdgpu", vram_bytes=512 * 1024 ** 2)
                                   .render_node().cpu(8).memory(16))
        self.assertEqual(facts["gpu_class"], "integrated",
                         "an APU's small VRAM carve-out is not a discrete card")
        self.assertEqual(tier, "balanced")

    def test_a_connector_directory_is_never_read_as_a_device(self) -> None:
        """card0-DP-1 is a connector; treating it as a card invents a GPU."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            m = FakeMachine(root)
            m.write("sys/class/drm/card0-DP-1/modes", "3840x2160\n")
            m.cpu(16).memory(32)
            module = load_module(root)
            facts = module.probe()
            self.assertEqual(facts["gpu_drivers"], [],
                             "a connector must not contribute a driver")
            self.assertEqual(facts["gpu_class"], "software")

    def test_classification_is_deterministic(self) -> None:
        build = (lambda m: m.gpu("card1", "nvidia").render_node()
                 .cpu(16).memory(32).display(3840, 2160))
        self.assertEqual(self.tier_of(build)[0], self.tier_of(build)[0])


class Profiles(unittest.TestCase):
    def setUp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.module = load_module(Path(tmp))

    def test_no_profile_exceeds_the_blur_ceiling(self) -> None:
        for tier, profile in self.module.PROFILES.items():
            blur = profile.get("kwinrc", {}).get("Effect-blur/BlurStrength")
            if blur is not None:
                with self.subTest(tier=tier):
                    self.assertLessEqual(
                        int(blur), self.module.BLUR_CEILING,
                        "blur above 15 has shipped unreadable surfaces")

    def test_essential_turns_blur_off_rather_than_turning_it_down(self) -> None:
        essential = self.module.PROFILES["essential"]["kwinrc"]
        self.assertEqual(essential["Plugins/blurEnabled"], "false")
        self.assertNotIn("Effect-blur/BlurStrength", essential,
                         "a disabled effect must not also carry a strength — "
                         "that reads as 'blur, but weak' to the next reader")

    def test_no_tier_writes_a_zero_animation_factor(self) -> None:
        for tier, profile in self.module.PROFILES.items():
            factor = float(profile["kdeglobals"]["KDE/AnimationDurationFactor"])
            with self.subTest(tier=tier):
                self.assertGreater(
                    factor, 0.0,
                    "Kirigami's longDuration floors at 1, so 0 is not 'off' — "
                    "it is an animation running with a nonsense duration. Off "
                    "is the user's own setting.")
                self.assertLessEqual(factor, 1.0)

    def test_every_tier_is_covered_and_the_minimize_slot_holds_one(self) -> None:
        self.assertEqual(set(self.module.PROFILES), set(self.module.TIERS))
        for tier, profile in self.module.PROFILES.items():
            kwin = profile["kwinrc"]
            with self.subTest(tier=tier):
                # KWin's minimize slot is exclusive: magiclamp vs squash.
                self.assertNotEqual(
                    (kwin["Plugins/magiclampEnabled"], kwin["Plugins/squashEnabled"]),
                    ("true", "true"),
                    "magiclamp and squash share KWin's exclusive minimize slot")

    def test_richer_hardware_never_gets_less_motion(self) -> None:
        order = {t: i for i, t in enumerate(self.module.TIERS)}
        factors = {t: float(p["kdeglobals"]["KDE/AnimationDurationFactor"])
                   for t, p in self.module.PROFILES.items()}
        ranked = sorted(self.module.TIERS, key=lambda t: order[t])
        for lower, higher in zip(ranked, ranked[1:]):
            self.assertLessEqual(factors[lower], factors[higher],
                                 f"{higher} must not animate less than {lower}")


class ApplyIsHonest(unittest.TestCase):
    """apply() must be idempotent and must yield to the user."""

    def run_apply(self, tier: str, state: dict | None, live: dict) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["MOOS_TIER_STATE_HOME"] = str(root / "state")
            os.environ["MOOS_TIER_CONFIG_HOME"] = str(root / "config")
            module = load_module(root)
            if state is not None:
                path = module.state_path()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(state), encoding="utf-8")
            wrote: dict[str, str] = {}
            module._kreadconfig = lambda f, g, k: live.get(f"{f}/{g}/{k}", "")
            def fake_write(f, g, k, v):
                wrote[f"{f}/{g}/{k}"] = v
                return True
            module._kwriteconfig = fake_write
            module._reconfigure_kwin = lambda: None
            result = module.apply(tier)
            result["_wrote"] = wrote
            return result

    def run_apply_motion(self, tier: str, state: dict | None, live_motion: str) -> dict:
        """apply() with the motion helpers stubbed, so the real desktop is never driven."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["MOOS_TIER_STATE_HOME"] = str(root / "state")
            os.environ["MOOS_TIER_CONFIG_HOME"] = str(root / "config")
            module = load_module(root)
            if state is not None:
                path = module.state_path()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(state), encoding="utf-8")
            asked: list[str] = []
            module._kreadconfig = lambda f, g, k: ""
            module._kwriteconfig = lambda f, g, k, v: True
            module._reconfigure_kwin = lambda: None
            module._current_motion = lambda: live_motion
            def fake_apply_motion(policy: str) -> bool:
                asked.append(policy)
                return True
            module._apply_motion = fake_apply_motion
            result = module.apply(tier)
            result["_asked"] = asked
            return result

    def test_the_tier_actually_sets_the_motion_it_declares(self) -> None:
        """The profile has always DECLARED motion; nothing ever applied it.

        Measured on the MoOS Cloud server: tier `essential` (profile "still")
        with all three desktops running `gentle` — a moving wallpaper drawn in
        software, on the machine whose whole purpose is to be streamed. The
        capture is damage-driven, so an animated background is the one thing
        guaranteed to stop the encoder ever being idle.
        """
        result = self.run_apply_motion("essential", None, "gentle")
        self.assertEqual(result["_asked"], ["still"],
                         "an essential machine must be asked for still motion")
        self.assertEqual(result["motion_written"], "still")

    def test_motion_already_correct_is_not_rewritten(self) -> None:
        result = self.run_apply_motion("essential", None, "still")
        self.assertEqual(result["_asked"], [], "nothing to do must do nothing")

    def test_a_motion_the_user_chose_is_left_alone(self) -> None:
        """Same ownership rule as every other key: theirs wins, permanently."""
        state = {"tier": "essential", "written": {}, "motion_written": "still"}
        result = self.run_apply_motion("essential", state, "alive")
        self.assertEqual(result["_asked"], [],
                         "a motion policy the user changed must never be taken back")
        self.assertIn("motion", result["skipped"])
        self.assertEqual(result["motion_written"], "still")

    def test_a_fresh_machine_gets_the_whole_profile(self) -> None:
        result = self.run_apply("flagship", None, {})
        self.assertGreater(result["changed"], 0)
        self.assertEqual(result["_wrote"]["kwinrc/Effect-blur/BlurStrength"], "15")

    def test_reapplying_the_same_tier_writes_nothing(self) -> None:
        first = self.run_apply("flagship", None, {})
        live = {key.replace("kwinrc/", "kwinrc/").replace("kdeglobals/", "kdeglobals/"): value
                for key, value in first["_wrote"].items()}
        second = self.run_apply(
            "flagship",
            {"tier": "flagship", "written": first["written"]},
            live)
        self.assertEqual(second["changed"], 0,
                         "a settled machine must not be rewritten every login")

    def test_a_setting_the_user_changed_is_left_alone(self) -> None:
        first = self.run_apply("flagship", None, {})
        live = dict(first["_wrote"])
        live["kwinrc/Effect-blur/BlurStrength"] = "4"   # the user turned blur down
        second = self.run_apply(
            "flagship",
            {"tier": "flagship", "written": first["written"]},
            live)
        self.assertIn("kwinrc/Effect-blur/BlurStrength", second["skipped"],
                      "a key the user changed after we wrote it is theirs")
        self.assertNotIn("kwinrc/Effect-blur/BlurStrength", second["_wrote"])

    def test_apply_refuses_a_profile_that_breaks_the_blur_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["MOOS_TIER_STATE_HOME"] = str(root / "state")
            os.environ["MOOS_TIER_CONFIG_HOME"] = str(root / "config")
            module = load_module(root)
            module.PROFILES["flagship"]["kwinrc"]["Effect-blur/BlurStrength"] = "40"
            module._kreadconfig = lambda f, g, k: ""
            module._kwriteconfig = lambda f, g, k, v: True
            module._reconfigure_kwin = lambda: None
            with self.assertRaises(SystemExit):
                module.apply("flagship")


class Override(unittest.TestCase):
    def test_a_pinned_tier_beats_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            FakeMachine(root).cpu(16).memory(32)          # would detect essential
            os.environ["MOOS_TIER_CONFIG_HOME"] = str(root / "config")
            os.environ["MOOS_TIER_STATE_HOME"] = str(root / "state")
            module = load_module(root)
            module.override_path().parent.mkdir(parents=True, exist_ok=True)
            module.override_path().write_text("flagship\n", encoding="utf-8")
            decision = module.resolve()
            self.assertEqual(decision["tier"], "flagship")
            self.assertEqual(decision["detected"], "essential")
            self.assertTrue(decision["pinned"],
                            "the user's pin must be visible in the report, not silent")

    def test_a_nonsense_override_falls_back_to_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            FakeMachine(root).cpu(16).memory(32)
            os.environ["MOOS_TIER_CONFIG_HOME"] = str(root / "config")
            os.environ["MOOS_TIER_STATE_HOME"] = str(root / "state")
            module = load_module(root)
            module.override_path().parent.mkdir(parents=True, exist_ok=True)
            module.override_path().write_text("ultra\n", encoding="utf-8")
            decision = module.resolve()
            self.assertEqual(decision["tier"], "essential")
            self.assertFalse(decision["pinned"])


def tearDownModule() -> None:
    for key in ("MOOS_TIER_ROOT", "MOOS_TIER_STATE_HOME", "MOOS_TIER_CONFIG_HOME"):
        os.environ.pop(key, None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
