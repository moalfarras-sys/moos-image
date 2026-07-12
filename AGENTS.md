# Working on MoOS — read this first

This repo builds a **real operating system that is installed on a real machine**. It is not a
sandbox, and there is no staging environment between a merge and someone's desktop failing to
boot. Read this before changing anything.

## The one fact that changes how you work

**The maintainer's daily-driver PC runs this image.** `main` is built by CI, published to
`ghcr.io/moalfarras-sys/moos`, and that machine pulls from it. A bad commit does not produce a
failing test — it produces a computer that boots to a black screen, on the machine you are
talking to the maintainer on.

This has already happened once. It is the reason for most of the guards you will find in
`build_files/build.sh`, and why they are written to **fail the build loudly** rather than warn.

Do not remove a guard because it is inconvenient. If a guard fires, it is telling you the truth.

## What is actually true about this system

| | |
|---|---|
| Base | Fedora Atomic (bootc/OSTree) + KDE Plasma 6, from `ghcr.io/ublue-os/kinoite-main:44` |
| Editions | `moos` (generic) and `moos-nvidia` (**same base**, driver layered on) |
| Update path | `rpm-ostree upgrade` → applies on reboot; previous deployment is kept for rollback |
| Signing | every image is cosign-signed; the installed system **enforces** the signature |
| ISO | built in CI by `build-iso.yml` (Titanoboa), published as a workflow artifact |
| Identity | MoOS/Nova only on every user-visible surface — see `verify_image_experience.py` |

## The rules that are enforced by the build

These are not conventions, they are gates. The image build fails if you break them.

- **The initramfs must be able to boot.** `build.sh` proves the `ostree` dracut module is
  present. Without it an installed system drops to an emergency shell.
- **An NVIDIA image must contain a working NVIDIA driver.** The kmod must be built for the
  image's exact kernel, and the module must be *inside the initramfs* — verified by reading the
  initramfs, not by trusting dracut's log. A kmod/kernel mismatch, or a driver that is not
  force-loaded early, is a black screen.
- **The identity must not regress.** `verify_image_experience.py` fails the build if a
  user-visible MoOS surface reverts to another distribution's branding.
- **Every shipped QML app must actually load.** A syntax check is not enough; the build starts
  each app and fails if it exits early.
- **Remote control must ship the PipeWire path.** If `mo-remote-portal.py` is missing or is not
  the PipeWire one, the build fails — the old screenshot-per-frame path was ~1 fps.

## Things that are easy to get wrong here

**Never build an edition on a different base.** `moos-nvidia` used to build `FROM
ghcr.io/ublue-os/kinoite-nvidia:44`. That tag was abandoned upstream in May; the "NVIDIA image"
silently became a six-week-old system, 589 packages behind the generic one. Both editions now
build from the same base and the driver is layered on. If you need a variant, layer it — do not
fork the base.

**COPR before rebranding.** `dnf5`/COPR derive the chroot name from `/etc/os-release`'s
`ID`+`VERSION_ID`. `build.sh` keeps `ID=fedora` until the very last section for exactly this
reason. Anything that needs a COPR must run before section (z).

**An `ARG` used in a `FROM` must be declared before the first `FROM`.** Declared after it, the
arg belongs to that stage, `FROM ${ARG}` expands to nothing, and buildah fails the whole build
with the unhelpful `no FROM statement found`. This has already cost one red CI run.

**Build locally before you push.** `podman build` runs every gate CI runs. The `no FROM` failure
above, and an NVIDIA image whose initramfs contained no NVIDIA, were both caught by a local
build — one of them only because someone bothered to run it.

**`/var` must be clean.** `bootc container lint` is the final build stage and it will reject
content in `/var`.

**Privileged actions go through `moai-do`, and nowhere else.** It is a fixed allowlist with
confirmation and Polkit. Mo AI can *name* an action from that list — the UI turns it into a Run
button — but the model never executes anything itself. Do not add a path that lets a model, or a
web page, run a command. If you add an action, add it to `moai-do`, to `moos-open`'s case
statement, and to Mo AI's system prompt.

## Layout

```
Containerfile          both editions; IMAGE_NAME selects whether NVIDIA is layered on
build_files/build.sh   everything package-dependent, plus the boot/identity gates
system_files/          copied verbatim onto / — identity, themes, apps, units
moremote/              Mo PC Remote, vendored source; built by a stage in the Containerfile
tests/                 run these before pushing; they are the same gates CI runs
.github/workflows/     build.yml (image), build-iso.yml (ISO), build-disk.yml (qcow2)
```

## Before you push

```bash
python3 tests/verify_user_experience.py     # the user-experience gate
python3 tests/test_device_plan.py
bash -n build_files/build.sh
just build                                  # or: podman build … — catches the real gates
```

A local `podman build` is worth the wait. It runs every gate CI runs, and it has already caught
a change that would have shipped an unbootable NVIDIA image.

## Pushing workflow changes

The maintainer's `gh` token needs the `workflow` scope to update anything in
`.github/workflows/`. Without it GitHub rejects the push outright:

```bash
gh auth refresh -h github.com -s workflow
```

## What is NOT done — do not claim otherwise

Being honest about this list is more useful than shrinking it.

- **The signed install path has not been exercised on real hardware.** The kickstart now
  verifies the signature at install time (and therefore deploys a signed origin, so updates stay
  verified for life). The policy, the key and the sigstore attachment config were each verified
  against the real registry — but nobody has yet run an actual ISO install end to end. If an
  install fails with a signature error, that is where to look.
- **Qt WebEngine spell-check dictionaries are empty.** `qwebengine_convert_dict` crashes inside
  the build container, so `/usr/share/qt6/qtwebengine_dictionaries/` ships with zero `.bdic`
  files.
- **Mo AI has no model until the user downloads one.** The chat is real and the local/cloud
  routing is real, but a fresh install cannot answer until the one-time model download is
  accepted.
- **Rollback has not been tested** against a deliberately broken update.
- **Audio/Bluetooth/Wi-Fi/suspend/multi-monitor** have not been verified on hardware other than
  the maintainer's desktop.

`MOOS_ROADMAP.md` is the source of truth for status. Keep it honest: it is more valuable as a
list of what is missing than as a list of what is claimed.
