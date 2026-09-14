# NVIDIA hardware acceptance — the checklist for the real PC

**Status: PARTIAL — core boot/driver/Wayland path passed on physical hardware
2026-09-13; visual boot capture, suspend, multi-output and rollback remain.**

Everything in `moos-nvidia` that this repository can prove without a GPU is
proven in CI: the akmod and the image agree on one kernel, the driver packages
are installed, `nvidia*.ko` exists under the shipped kernel's module tree,
`force_drivers` keeps `nvidia_drm` while `nvidia_peermem` is removed, the built
initramfs is read back with `lsinitrd` and must contain an nvidia module, the
initramfs is under the 300 MiB ceiling GRUB can allocate, and
`plymouth.use-simpledrm` is withheld so Plymouth draws on the display nvidia
actually owns.

A CI runner has no NVIDIA device, so it cannot replace this physical record.
The rows marked PASS below were read from the installed machine after its first
offline-ISO install and NVIDIA reboot. Unrun rows remain open.

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
Date: 2026-09-13
Image digest: sha256:c7c58ab993345b1ce2eba7e08e903bb715f4957902fec9d4a93b1e959e4beb15
GPU / driver version: NVIDIA GeForce RTX 2080 SUPER / 615.71.09
Kernel: 7.2.4-200.fc44.x86_64

 1 Boot              PASS    signed moos-nvidia 44.20260913.819 is booted;
                              signed generic digest retained as rollback
 2 Plymouth          OPEN    cmdline has rhgb/quiet/splash and no simpledrm;
                              no boot photograph was captured
 3 Login             PASS    physical login accepted and opened this session;
                              themed greeter photograph still open
 4 Desktop           PASS    live 4K Tidal Horizon desktop captured;
                              moos-selfcheck: 49 passed, zero broken
 5 NVIDIA module     PASS    nvidia/nvidia_drm/nvidia_modeset/nvidia_uvm loaded;
                              nvidia-smi reports the GPU; no fatal NVRM line;
                              nvidia_peermem absent
 6 Wayland / KWin    PASS    XDG_SESSION_TYPE=wayland; KWin is listed by
                              nvidia-smi on the physical GPU
 7 Displays          PARTIAL HDMI-A-1 enabled at native 3840x2160@60, scale 2.5;
                              no multi-monitor configuration was attached
 8 Suspend / resume  OPEN    not exercised
 9 Update            PASS    signed NVIDIA switch staged and applied; the race
                              with generic automatic update is fixed in source
10 Rollback          OPEN    signed generic rollback exists but was not booted
11 Reboot            PASS    reboot returned to the working NVIDIA desktop
```

This proves the core NVIDIA hardware route on one machine. It does not yet
qualify suspend, multiple displays, rollback, or every supported GPU generation.
