# MoOS ARM — running it on Oracle Cloud (free) and on UTM

`moos-arm` is MoOS built for **aarch64**. It uses the same identity, Liquid Glass
desktop, boot experience and first-party applications as the x86 editions. The
shared `system_files/` source is finalized for each architecture during the image
build. ARM starts from Fedora's bootc base because the Kinoite base
the x86 editions use is published for amd64 only.

It targets three things:

| Target | Shape | Notes |
|---|---|---|
| **Oracle Cloud** | `VM.Standard.A1.Flex` (Ampere) | Verify the Always Free label and current tenancy allowance before launch |
| **UTM on Apple silicon** | Virtualize | Near-native speed |
| **UTM on iPhone / iPad** | Emulate (UTM SE) | Works, but see [the honest note](#utm-on-iphone) |

---

## 1. Build the image

The image is built on **native ARM runners** — emulating an aarch64 desktop build
on x86 takes hours and usually blows the job timeout.

1. Merge the reviewed ARM changes to `main` (a pull request still builds and
   verifies the container, but cannot publish over the stable update channel).
2. The `main` push builds, signs and publishes the image and then creates the
   QCOW2 automatically. To repeat it manually, Actions → **Build MoOS ARM
   (aarch64)** → *Run workflow* and select `main`.
3. When it finishes, download both release artifacts:

   - `moos-arm-qcow2`: compressed exact boot-proven QCOW2, manifest, checksums;
   - `moos-arm-utm`: ready-to-import `MoOS-ARM.utm.zip`, manifest, checksums.

   Unpack the standalone disk when Oracle needs it:

```bash
zstd -d moos-arm-*.qcow2.zst
```

You now have `moos-arm-<version>.qcow2`. Oracle imports that file. UTM users
should import the `.utm.zip`; it contains the same QCOW2 hash plus the required
NoCloud seed and current UTM configuration.

> The workflow also pushes `ghcr.io/<you>/moos-arm:latest`. That is the *update*
> channel — once an instance is running, `bootc upgrade` pulls from it. The qcow2
> is only for the initial install.

---

## 2. Oracle Cloud

### 2.1 Before you start

You need an OCI tenancy where `VM.Standard.A1.Flex` is marked Always Free in the
home region. Oracle's current Free Tier page describes 1,500 OCPU-hours and
9,000 GB-hours monthly (equivalent to 2 OCPUs and 12 GB continuously) plus
200 GB of Always Free block storage, but service limits and offers can change;
verify the console before creating chargeable resources:
<https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm>

Object/custom-image storage is not an unlimited free resource. OCI includes
**20 GB combined Object Storage** in the Always Free allowance, and Oracle
documents custom-image storage as billable storage usage. The compressed
artifact does not count after decompression/import; the uploaded QCOW2 object
and the retained custom image do. Before launch, check **Billing & Cost
Management → Cost Analysis** and create a zero/low budget alert. Delete the
temporary bucket object after a successful import. Do not claim a `$0` result
until Cost Analysis confirms the tenancy remains inside its allowances.

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
  - **2 OCPUs, 12 GB memory** — this is the current full Always Free ARM
    allowance in one instance
- **Networking**: assign a public IPv4 address
- **SSH keys**: upload your public key. Oracle hands it to cloud-init, which
  installs it for the **`moos`** user.
- **Management password**: add cloud-init user-data that assigns `moos` a
  unique strong password. SSH password authentication remains disabled; this
  password is for authenticated `sudo` and KRDP only. MoOS does not ship
  `NOPASSWD` sudo. Change it later with `passwd` if needed.
- **Boot volume**: 50 GB is fine (free tier gives 200 GB total). cloud-init grows
  the root filesystem into whatever you give it on first boot.

The deployment automation generates the password hash and user-data without
committing either one. For a manual launch, use this shape and replace
`<SHA-512-HASH>` with a fresh `openssl passwd -6` result:

```yaml
#cloud-config
chpasswd:
  expire: false
  users:
    - {name: moos, password: "<SHA-512-HASH>", type: hash}
```

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
- **Ask for less.** 1 OCPU / 6 GB is often available when 2/12 is not, and you
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

It is installed but **switched off**. A remote-desktop service with a credential
baked into the image would mean every machine ever booted from that image shares
one password on a public IP. KRDP therefore uses the instance's own PAM account
password, and the setup creates a software-rendered headless Plasma Wayland
session only after you opt in:

```bash
ssh moos@<public-ip>
sudo moos-arm-remote on moos
```

Then choose one of:

**A. SSH tunnel (recommended — nothing extra is exposed)**

```bash
ssh -L 3389:localhost:3389 moos@<public-ip>
```

Connect your RDP client to `localhost:3389` as `moos`, using the unique system
password from instance creation. Port 3389 stays
closed in both OCI and firewalld.

**B. Open the port (not recommended)**

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

Use the generated `MoOS-ARM.utm.zip`. It contains the exact QCOW2 that passed
the release boot gate; the workflow checks the raw hash before packaging and
records it in `manifest.json`.

### Apple silicon Mac

1. Download the `moos-arm-utm` workflow artifact and verify `SHA256SUMS`.
2. Import `MoOS-ARM.utm.zip` in UTM. Do not replace either bundled drive.
3. Open UTM's built-in **Terminal** view before pressing Start.
4. During first boot cloud-init prints a password generated inside this VM for
   user `moos`. The public bundle and its README contain no password.
5. Use that password on the graphical MoOS login screen, then change it from
   Settings. SSH password login and KRDP remain disabled until explicitly enabled.

The bundle uses current QEMU configuration schema v4, AArch64 `virt`, UEFI,
`virtio-ramfb`, VirtIO disk/network and a MoOS library icon. The desktop bundle
has a 4 GiB Apple-silicon profile plus a separately proven iPhone 13+ profile
with 1.5 GiB RAM, two CPUs and a 64 MiB translation cache. UTM uses hardware
virtualization only where the host exposes it and otherwise uses emulation.

### UTM on iPhone

<a name="utm-on-iphone"></a>
The same bundle is intended for UTM on iPhone/iPad, but this release must not be
called iPhone-proven until it is imported on the owner's physical device. UTM SE
uses JIT-less emulation, so a full Plasma desktop can take minutes to boot and be
slow even when the identical AArch64/UEFI/virtio path passes on a Linux host.
Apple-silicon devices with supported virtualization can be much faster. Current
mission status is **OWNER-DEVICE-TEST-REQUIRED**.

---

## 5. Updating a running instance

MoOS ARM is a bootc image, so updates are atomic and roll back:

```bash
moai-do update            # resolves and stages an exact signed digest
# reboot from the MoOS power UI after the staged deployment is verified
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
| MoPlayer (Flutter), Mo PC Remote (.NET) | native x86_64 | native aarch64, architecture-gated |
| Serial console | `ttyS0` | `ttyAMA0` |
| Remote desktop | Mo PC Remote | Mo PC Remote plus opt-in KRDP for cloud access |

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
