#!/usr/bin/env python3
"""/boot is 974 MiB and holds two full deployments. The ARM initramfs must fit.

MEASURED ON THE LIVE ORACLE A1 (2026-09-06), before the fix this gate protects:

    /boot            974 MiB, 78% full, 205 MiB free
    2 deployments  x 351 MiB (kernel + initramfs)
    initramfs        237 MiB
      of which       137.8 MiB was firmware, and 131 MiB of THAT belonged to
                     discrete desktop GPUs that cannot exist on an Ampere A1:
                     nvidia 101.2, amdgpu 23.4, xe 3.2, i915 1.8, radeon 1.4

A third deployment needs 351 MiB and 205 MiB were free, so the next signed
update had nowhere to stage. That is a silent update failure, not a cosmetic
one, which is why this is gated in source AND against the built archive.

The four modules are omitted by exact name. dracut anchors every omit entry as
`^name$` (/usr/bin/dracut:1493, dracut-108-7.fc44), so a bare `xe` cannot reach
`sdhci-xenon-driver` or the 15 other modules whose names merely contain "xe".
That anchoring is the whole reason bare names are safe here; if a future dracut
drops it, the built-image gate in build-arm.sh is the backstop.

MEASURED, by building three real initramfs images on the live A1 with
dracut-108-7.fc44 against kernel 7.1.13-200.fc44.aarch64:

    no omission                 248,496,743 B (237 MiB)   597 nvidia fw files
    omit_drivers via conf file  104,554,992 B (99.7 MiB)   11 nvidia fw files
    omit_drivers via --omit-drivers  104,554,530 B         11 nvidia fw files

Both forms work; the conf drop-in is the one this edition uses. THE ELEVEN
REMAINING FILES ARE CORRECT: `tegra-drm` (8) and `xhci-tegra` (4) are NVIDIA
TEGRA drivers — genuine aarch64 SoC hardware — and they share the nvidia/
firmware namespace. A first version of the build gate demanded that namespace be
EMPTY and duly failed a build whose fix had worked perfectly. The contract is
"these four modules are gone" plus a size ceiling, never "this directory is
empty": a gate that cannot pass on a correct image is worse than no gate.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ARM = (REPO / "build_files/build-arm.sh").read_text(encoding="utf-8")
X86 = (REPO / "build_files/build.sh").read_text(encoding="utf-8")

# The dracut drop-in this edition installs, isolated from the rest of the script.
CONF = ARM.split("50-moos-arm.conf <<'DRACUT'", 1)[1].split("\nDRACUT\n", 1)[0]

# Each of these declares the firmware tree beside it; counts are modinfo -F
# firmware on kernel 7.1.13-200.fc44.aarch64, read off the live machine.
OMITTED = {
    "nouveau": "firmware/nvidia",
    "amdgpu": "firmware/amdgpu",
    "radeon": "firmware/radeon",
    "xe": "firmware/xe",
}


def x86_dracut_blocks():
    """Every dracut.conf.d heredoc in build.sh, whatever its delimiter.

    Matching the delimiter by name is what made the previous version of this
    check vacuous, so the delimiter is captured and back-referenced instead.
    """
    return [body for _, _, body in re.findall(
        r"dracut\.conf\.d/([^\n]*)<<'?(\w+)'?(.*?)\n\2\n", X86, re.S)]


def code(text: str) -> str:
    """Strip shell comments so prose cannot satisfy a wiring assertion."""
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


class ArmInitramfsFits(unittest.TestCase):
    def test_the_four_desktop_gpu_families_are_omitted_by_exact_name(self) -> None:
        conf = code(CONF)
        self.assertIn("omit_drivers", conf,
                      "without omit_drivers the ARM initramfs carries 131 MiB of "
                      "GPU firmware for hardware an Ampere A1 cannot have")
        declared = re.search(r'omit_drivers\+=\s*"([^"]*)"', conf)
        self.assertIsNotNone(declared, "omit_drivers must be a += \" ... \" list")
        names = set(declared.group(1).split())
        self.assertEqual(names, set(OMITTED),
                         "exactly these four families are safe to drop on ARM; "
                         "anything else needs its own measurement")

    def test_portability_is_not_what_was_traded_away(self) -> None:
        """The fix removes four GPU families, never the no-hostonly contract.

        A hostonly initramfs is how a cloud image reaches dracut's emergency
        shell with no root device — the exact failure the conf's own comment
        warns about. Shrinking /boot by making the image host-bound would be a
        different, much worse bug wearing this fix's clothes.
        """
        conf = code(CONF)
        self.assertIn('hostonly="no"', conf)
        self.assertIn('hostonly_cmdline="no"', conf)
        for driver in ("virtio_blk", "virtio_pci", "virtio_scsi",
                       "virtio_net", "virtio_gpu", "virtio_console"):
            self.assertIn(driver, conf, f"{driver} must still be force-added")

    def test_no_storage_or_network_driver_is_in_the_omit_list(self) -> None:
        """Belt and braces for the anchoring argument above."""
        conf = code(CONF)
        declared = re.search(r'omit_drivers\+=\s*"([^"]*)"', conf).group(1).split()
        for name in declared:
            self.assertNotIn("virtio", name)
            self.assertNotIn("sdhci", name)
            self.assertNotIn("mmc", name)
            self.assertNotIn("nvme", name)
            self.assertNotIn("scsi", name)

    def test_the_built_archive_is_gated_not_just_the_source(self) -> None:
        """A green dracut log says nothing about the bytes it produced."""
        # code() strips comments: the gate's own comment explains why the
        # firmware-namespace check was WRONG, so prose must not answer here.
        gate = code(ARM.split("GATE: the discrete-GPU firmware", 1)[1].split(
            "=== initramfs carries no desktop-GPU firmware", 1)[0])
        self.assertIn("/tmp/moos-arm-initrd.txt", gate,
                      "the gate must read the BUILT archive inventory")
        # Assert on the modules; the firmware namespace is shared with Tegra.
        self.assertRegex(gate, r'for _mod in nouveau amdgpu radeon xe')
        for spelling in ("firmware/nvidia", "firmware/amdgpu",
                         "firmware/radeon", "firmware/xe", "firmware/i915"):
            self.assertNotIn(
                spelling, gate,
                f"the gate must not assert on {spelling}: demanding an EMPTY "
                "firmware namespace fails a correct image, because tegra-drm "
                "and xhci-tegra legitimately ship 12 files under nvidia/. "
                "Assert the four MODULES are gone, plus the size ceiling.")
        self.assertRegex(
            ARM, r'_initrd_mib.*-gt\s+150',
            "a size ceiling must stop the bloat creeping back through some "
            "other driver family")

    def test_the_firmware_gate_runs_after_the_boot_content_gates(self) -> None:
        """Order is the argument: prove nothing was lost, then prove bloat left.

        If the firmware check ran first, a build that had silently dropped
        ostree-prepare-root or the virtio root drivers could still report the
        happy 'no GPU firmware' line before failing, and a reader skimming the
        log would draw the wrong conclusion about what this change did.
        """
        self.assertLess(
            ARM.index("ostree-prepare-root"),
            ARM.index("GATE: the discrete-GPU firmware"),
            "the OSTree/virtio/Plymouth gates must precede the firmware gate")

    def test_x86_dracut_blocks_are_actually_found(self) -> None:
        """The x86 check below is worthless if its regex matches nothing.

        It used to look for heredocs delimited `DRACUT`. The one dracut config
        x86 writes (99-moos-boot.conf) is delimited `DRC`, so the search
        returned zero blocks and the loop under it never executed: a gate that
        could not fail, guarding the boot path of the maintainer's daily driver.
        """
        self.assertTrue(x86_dracut_blocks(),
                        "no x86 dracut.conf.d heredoc found -- the gate below "
                        "would pass without inspecting anything")

    def test_x86_keeps_nvidia_in_the_initramfs(self) -> None:
        """moos-nvidia REQUIRES its driver inside the initramfs -- a black
        screen otherwise (AGENTS.md, 'An NVIDIA image must contain a working
        NVIDIA driver').

        The previous version of this test asserted x86 omits no GPU drivers at
        all. That contract was already false: build.sh deliberately omits
        nouveau, amdgpu, radeon, i915, xe and nvidiafb, which is what took the
        NVIDIA initramfs from ~368 MB (GRUB could not allocate it) to ~242 MB.
        Only the vacuous regex kept the assertion from failing the correct
        build. What actually must never happen is `nvidia` itself being omitted.
        """
        for block in x86_dracut_blocks():
            for line in block.splitlines():
                line = line.strip()
                if not line.startswith("omit_drivers"):
                    continue
                omitted = line.split("=", 1)[1].strip().strip('"').split()
                self.assertNotIn(
                    "nvidia", omitted,
                    "x86 must never omit the nvidia driver from the initramfs; "
                    "moos-nvidia would boot to a black screen")
                self.assertNotIn(
                    "nvidia_drm", omitted,
                    "omitting nvidia_drm kills early KMS and the splash")

    def test_x86_initramfs_has_a_size_ceiling(self) -> None:
        """The savings above are one deleted line from returning, and the
        failure is a machine that stops at GRUB rather than a red build.

        ARM has had a measured ceiling since 2026-09-06; x86 had none.
        """
        self.assertRegex(
            X86, r"initramfs is \$\{_initrd_mib\} MiB \(ceiling 300\)",
            "build.sh must fail an x86 initramfs over the 300 MiB ceiling")
        self.assertIn(
            'stat -c %s "/usr/lib/modules/${kver}/initramfs.img"', X86,
            "the ceiling must measure the initramfs dracut actually wrote, "
            "not infer a size from the dracut configuration")


if __name__ == "__main__":
    unittest.main(verbosity=2)
