# NVIDIA hardware acceptance — the checklist for the real PC

**Status: NOT RUN. No step below has been executed.**

Everything in `moos-nvidia` that this repository can prove without a GPU is
proven in CI: the akmod and the image agree on one kernel, the driver packages
are installed, `nvidia*.ko` exists under the shipped kernel's module tree,
`force_drivers` keeps `nvidia_drm` while `nvidia_peermem` is removed, the built
initramfs is read back with `lsinitrd` and must contain an nvidia module, the
initramfs is under the 300 MiB ceiling GRUB can allocate, and
`plymouth.use-simpledrm` is withheld so Plymouth draws on the display nvidia
actually owns.

None of that is evidence that a GPU rendered a frame. A CI runner has no NVIDIA
device, so **no session may claim NVIDIA hardware success from Oracle or from a
green build.** This file is the only thing that can, and it must be filled in
from the physical machine.

## Before you start

- The machine's previous deployment must be bootable. `rpm-ostree status` should
  list two deployments; do not start if it lists one.
- Record the digest you are testing, so the result names an image:
  `rpm-ostree status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["deployments"][0]["container-image-reference"])'`
- If any step fails, stop and record the failure. `bootc rollback` (or the
  previous GRUB entry) returns the machine to the working deployment.

## The checklist

Record PASS/FAIL and the evidence column for every row. "It looked fine" is not
evidence; the command output or the photograph is.

| # | Step | What must be true | How to tell |
|---|------|-------------------|-------------|
| 1 | **Boot** | The machine reaches the bootloader and starts the new deployment | GRUB shows the MoOS entry; `rpm-ostree status` after boot shows the digest from "Before you start" as booted |
| 2 | **Plymouth** | The MoOS splash is drawn on the real display, not a black screen | Photograph the screen during boot. This is the one that regresses silently: `plymouth.use-simpledrm` must be absent — `grep simpledrm /proc/cmdline` returns nothing |
| 3 | **Login** | Plasma Login Manager appears, themed, and accepts the password | The greeter is the MoOS look, not Breeze; a wrong password is rejected and the right one is accepted |
| 4 | **Desktop** | A full Plasma session with the MoOS theme | `moos-selfcheck` runs clean; the panel, launcher and wallpaper are the MoOS ones |
| 5 | **NVIDIA module** | The proprietary driver is loaded and bound to the GPU | `lsmod \| grep -E '^nvidia'` lists nvidia, nvidia_drm, nvidia_modeset; `nvidia-smi` prints the GPU; `dmesg \| grep -i nvrm` shows no fatal errors. `nvidia_peermem` must NOT be loaded |
| 6 | **Wayland / KWin** | KWin runs on Wayland on the NVIDIA GPU, not llvmpipe | `echo $XDG_SESSION_TYPE` is `wayland`; `journalctl --user -b -u plasma-kwin_wayland \| grep -i renderer` names the NVIDIA device; the session is not software-rendered |
| 7 | **Displays** | Every connected output lights up at its native mode | All monitors show an image; `kscreen-doctor -o` lists each output enabled at the expected resolution and refresh; HiDPI scaling is the configured one |
| 8 | **Suspend / resume** | The machine suspends and comes back with the desktop intact | `systemctl suspend`, wake it, confirm the session is alive, the displays return, and `dmesg \| grep -i nvrm` shows no new errors. This is the classic NVIDIA failure — check it twice |
| 9 | **Update** | A signed update stages and applies | `moai-do update` (or the Updater app); `rpm-ostree status` shows a new staged deployment whose origin is `ostree-image-signed:` |
| 10 | **Rollback** | The previous deployment still boots | `bootc rollback`, reboot, confirm the earlier digest is booted, then roll forward again |
| 11 | **Reboot** | A clean reboot returns to a working desktop | Repeat steps 1–7 once more after a plain `systemctl reboot` |

## Record the result here

```
Date:
Image digest:
GPU / driver version:
Kernel:

 1 Boot              PASS / FAIL   evidence:
 2 Plymouth          PASS / FAIL   evidence:
 3 Login             PASS / FAIL   evidence:
 4 Desktop           PASS / FAIL   evidence:
 5 NVIDIA module     PASS / FAIL   evidence:
 6 Wayland / KWin    PASS / FAIL   evidence:
 7 Displays          PASS / FAIL   evidence:
 8 Suspend / resume  PASS / FAIL   evidence:
 9 Update            PASS / FAIL   evidence:
10 Rollback          PASS / FAIL   evidence:
11 Reboot            PASS / FAIL   evidence:
```

Until this block is filled in from the physical machine, `moos-nvidia` is
"built, signed and gated", never "verified on hardware".
