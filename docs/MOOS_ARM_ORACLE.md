# MoOS ARM — running it on Oracle Cloud (free) and on UTM

`moos-arm` is MoOS built for **aarch64**. Same identity, same UI2 desktop, same
boot animation as the x86 editions — the whole `system_files/` tree is shared
byte-for-byte — but built from Fedora's own bootc base, because the Kinoite base
the x86 editions use is published for amd64 only.

It targets three things:

| Target | Shape | Notes |
|---|---|---|
| **Oracle Cloud** | `VM.Standard.A1.Flex` (Ampere) | Always Free: 4 OCPU + 24 GB RAM + 200 GB storage |
| **UTM on Apple silicon** | Virtualize | Near-native speed |
| **UTM on iPhone / iPad** | Emulate (UTM SE) | Works, but see [the honest note](#utm-on-iphone) |

---

## 1. Build the image

The image is built on **native ARM runners** — emulating an aarch64 desktop build
on x86 takes hours and usually blows the job timeout.

1. Push this branch to GitHub.
2. Actions → **Build MoOS ARM (aarch64)** → *Run workflow* → leave
   **Also build the qcow2 disk image** ticked.
3. When it finishes, download the `moos-arm-qcow2` artifact and unpack it:

```bash
zstd -d moos-arm-*.qcow2.zst
```

You now have `moos-arm-YYYYMMDD.qcow2`. That one file is what both Oracle and UTM
take.

> The workflow also pushes `ghcr.io/<you>/moos-arm:latest`. That is the *update*
> channel — once an instance is running, `bootc upgrade` pulls from it. The qcow2
> is only for the initial install.

---

## 2. Oracle Cloud

### 2.1 Before you start

You need an OCI account with the **Always Free** tier. Everything below stays
inside it: the A1 shape, 200 GB of block volume, and the Object Storage used
during import are all free-tier resources.

### 2.2 Upload the image to Object Storage

Oracle imports custom images *from Object Storage*, not from your laptop.

1. **Storage → Buckets → Create Bucket** (any name, Standard tier).
2. Open it → **Upload** → select `moos-arm-YYYYMMDD.qcow2`.
3. Once uploaded, open the object's **⋮ menu → Create Pre-Authenticated Request**,
   type *Object*, permission *Read*. Copy the URL it gives you — it is shown
   **once**.

### 2.3 Import it as a Custom Image

**Compute → Custom Images → Import image**

| Field | Value |
|---|---|
| Operating system | **Linux** |
| Import from | **An Object Storage URL** (paste the PAR from above) |
| Image type | **QCOW2** |
| Launch mode | **PARAVIRTUALIZED** |

Import takes a few minutes. When it finishes, open the image and check
**Edit details → Compatible shapes** includes the `VM.Standard.A1.Flex` family.
If Oracle did not detect it, add it there by hand.

### 2.4 Launch the instance

**Compute → Instances → Create instance**

- **Image**: *Change image* → **My images** → your `moos-arm` image
- **Shape**: *Change shape* → **Ampere** → `VM.Standard.A1.Flex`
  - **4 OCPUs, 24 GB memory** — this is the entire Always Free ARM allowance in
    one instance
- **Networking**: assign a public IPv4 address
- **SSH keys**: upload your public key. Oracle hands it to cloud-init, which
  installs it for the **`moos`** user.
- **Boot volume**: 50 GB is fine (free tier gives 200 GB total). cloud-init grows
  the root filesystem into whatever you give it on first boot.

Then:

```bash
ssh moos@<public-ip>
```

### 2.5 "Out of host capacity"

This is the one thing that will actually stop you, and it is not your
configuration. Always Free Ampere capacity is genuinely scarce and Oracle
regularly refuses new A1 instances in popular regions.

What works:

- **Try every Availability Domain** in your region — AD-1, AD-2, AD-3 have
  separate pools.
- **Retry on a schedule.** Capacity frees up continuously; the same request that
  failed at noon often succeeds at 03:00 local.
- **Ask for less.** 1 OCPU / 6 GB is often available when 4/24 is not, and you
  can resize the instance upward later without rebuilding it.
- **Region matters.** Your home region is fixed once chosen, so if you have not
  created the tenancy yet, a less busy region is worth picking deliberately.
- **A paid account with a $0 balance still gets the free tier** and is given
  priority over trial accounts for A1 capacity. Upgrading to Pay As You Go does
  not by itself cost anything.

---

## 3. Seeing the desktop

An Ampere instance has no monitor, so the desktop needs a remote. MoOS ARM ships
KDE's own RDP server (KRDP), which drives the **real Plasma Wayland session** —
not a second X11 session the way `xrdp` would.

It is installed but **switched off, with no password**. A remote-desktop service
with a credential baked into the image would mean every machine ever booted from
that image shares one password on a public IP. So you set it, once, on your own
instance:

```bash
ssh moos@<public-ip>
moos-arm-remote        # asks for a password, enables the service
```

Then choose one of:

**A. SSH tunnel (recommended — nothing extra is exposed)**

```bash
ssh -L 3389:localhost:3389 moos@<public-ip>
```

Connect your RDP client to `localhost:3389`. Port 3389 stays closed to the
internet.

**B. Open the port**

In the OCI console: **Networking → VCN → Security Lists** → add an ingress rule
for **TCP 3389**. Prefer restricting the source to your own IP rather than
`0.0.0.0/0`. Then connect to `<public-ip>:3389`.

> The desktop renders in software (`llvmpipe`) — an A1 instance has no GPU. It is
> perfectly usable for work; it is not for games or video.

### The serial console

If the network or SSH ever breaks, OCI's **Console connection** is the way in.
This image is configured for it correctly on ARM: the console is
`ttyAMA0`, the ARM PL011 UART — *not* `ttyS0`, which is the x86 port and does not
exist on Ampere. Images that get this wrong show a permanently blank serial
console, which you discover exactly when you need it.

---

## 4. UTM

The same `.qcow2` file, no conversion.

### Apple silicon Mac

1. UTM → **Create a New Virtual Machine → Virtualize → Linux**
2. Tick **Boot from kernel image**: *off*. Instead, skip the ISO step.
3. In the VM's settings, remove the empty drive and **import** `moos-arm.qcow2`
   as the boot drive.
4. **System**: 4+ GB RAM, 2+ cores. **Display**: `virtio-gpu-pci` (the image ships
   the virtio drivers in its initramfs).
5. Boot. The MoOS animation plays, then the login screen.

Because there is no cloud metadata, cloud-init falls through to `None` and no SSH
key is installed — log in at the graphical greeter instead. If you want SSH in a
UTM guest, attach a `NoCloud` seed ISO; the datasource list already accepts it.

### UTM on iPhone

<a name="utm-on-iphone"></a>
It runs, and it is worth being straight about what that means. On iPhone, UTM
cannot use hardware virtualisation — **UTM SE is a JIT-less emulator**. An
emulated Plasma desktop on a phone is *slow*: minutes to reach the desktop, and
sluggish once there. It is a demonstration, not a machine to work on. On an
M-series iPad running full UTM with virtualisation, it is genuinely fast.

---

## 5. Updating a running instance

MoOS ARM is a bootc image, so updates are atomic and roll back:

```bash
sudo bootc upgrade        # pulls ghcr.io/<you>/moos-arm:latest
sudo systemctl reboot
```

If a boot goes wrong, pick the previous deployment in the boot menu, or:

```bash
sudo bootc rollback
```

---

## 6. What differs from the x86 editions

| | x86_64 (`moos`, `moos-nvidia`, `moos-cloud`) | aarch64 (`moos-arm`) |
|---|---|---|
| Base | `ghcr.io/ublue-os/kinoite-main:44` | `quay.io/fedora/fedora-bootc:44` |
| Desktop | from the Kinoite base | curated Plasma 6 list, installed by `build-arm.sh` |
| Identity, UI2, boot animation | `system_files/` | **the same `system_files/`** |
| NVIDIA | `moos-nvidia` edition | n/a |
| Gaming stack | yes | no |
| MoPlayer (Flutter), Mo Remote (.NET) | yes | not yet — both ship prebuilt `linux-x64` binaries |
| Serial console | `ttyS0` | `ttyAMA0` |
| Remote desktop | Mo Remote | KRDP |

`moos-qml-shell`, the one C++ binary MoOS compiles itself, **is** built for
aarch64 — natively, in the same throwaway stage the x86 build uses — so MoOS's own
QML applications get their proper Wayland `app_id` here too.

---

## 7. If something goes wrong

**The build fails on `plasma-login-manager`.** The package name changed in
Fedora. `build-arm.sh` prints the candidates it found; put the right name in
section (2) of that file. It fails loudly on purpose — falling back to SDDM would
produce a machine that logs in with a stock greeter, i.e. a MoOS that does not
look like MoOS, without failing anything.

**Oracle rejects the import.** Check the image type is **QCOW2** and the launch
mode is **PARAVIRTUALIZED**. `EMULATED` also boots but is slower and unnecessary.

**The instance boots but SSH is refused.** Password authentication is disabled by
design. Confirm your public key was attached at launch; if it was not, use the
serial console to add one — there is no way to enable passwords remotely, which
is the point.

**No boot animation on Oracle.** Expected. An Ampere instance has no display
device at all, so there is no framebuffer for Plymouth to draw on. The animation
is for UTM, for bare metal, and for anything with a virtual GPU.
