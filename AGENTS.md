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

## A green build proves nothing about what the user sees

Everything in this section shipped while every gate passed.

**The identity gate ran before `set -e` and its failure was ignored.** It was the second line of
`build.sh`; `set -euxo pipefail` is the tenth. A build in this repo printed
`MoOS image-experience gate failed` and went on to `Successfully tagged`. It also ran before
build.sh did any work, so it could only see what `COPY` had put in place. The gate that exists
to keep another distribution's branding away from the user had never stopped anything. It runs
last now. If you add a gate, make sure it runs where it can actually fail the build.

**Gate the system that exists, not the one you remember.** Fedora Kinoite 44 replaced SDDM with
`plasma-login-manager` — `sddm` is not installed at all. MoOS was still shipping a full SDDM
theme and an SDDM config, and the gate asserted `Current=moos-nova` in that config and *passed*,
while the real login screen showed Plasma's default wallpaper. A green check on a file nobody
reads is worse than no check: it buys false confidence. The gate now resolves
`display-manager.service` and asserts on whatever it actually points at.

**The first screen was another desktop's.** `plasma-setup.service` runs
`Before=display-manager.service` and holds the screen, so a fresh install greeted the user with
"Welcome to Plasma Desktop". Hiding the plasma-welcome *app* did nothing — the *service* draws
the wizard.

**Plymouth needs `rhgb` on the kernel command line, or it draws nothing.** The image set no
kargs at all, so the MoOS splash appeared only if the installer happened to add them.

**Repoint configs before deleting what they point at.** Removing Fedora's look-and-feel packages
without first fixing the kde-settings profile that named them would leave Plasma silently
falling back to Breeze. This was written as a warning and then came true anyway — see below,
because the config that still named Fedora was not one this repo ships.

**A theme this image ships is not a theme the user gets.** Four separate Nova surfaces were
shipped, gated green, and never once reached the desktop. Every one of them lost to a config
that outranks `/etc/xdg`, and no gate on a file in `system_files/` can see any of it:

- `~/.config/*` — the user's own config, and the strongest. Existing users carry keys from the
  defaults they were *created* under, and those keys never expire. One user's `kdeglobals` still
  had `AutomaticLookAndFeel=true` + `DefaultLightLookAndFeel=org.fedoraproject.fedora.desktop`;
  the day the Fedora packages were removed, Plasma's day/night switch resolved a name that no
  longer existed, fell back to **Breeze**, and persisted it. Plasma does not fall back to your
  `LookAndFeelPackage` — it falls back to Breeze, and it writes that down.
- `~/.config/kdedefaults/*` — **comes BEFORE `/etc/xdg` in `XDG_CONFIG_DIRS`.** This is where
  `LookAndFeelManager` writes the applied Global Theme's defaults. Anything Nova's `defaults`
  file does not declare is simply left there from the last theme, forever. Nova declared no
  window decoration, so Breeze's — written when the user was created — shadowed the repo's
  `/etc/xdg/kwinrc` on *every install since day one*, while the gate on that file stayed green.
- `LookAndFeelManager` applies only a **hardcoded subset** of a defaults file. `[Sounds]` is not
  in it, so the MoOS sound theme shipped for months and never played. Arbitrary `[kwinrc]`
  groups are not in it either. `[kwinrc][org.kde.kdecoration2]` *is* — upstream
  `org.kde.breeze`'s defaults is the list of what actually works.
- **GTK reads three sources, and `settings.ini` is the weakest.** Wayland apps take
  `gtk-theme-name` from GSettings, X11/XWayland apps from the running `xsettingsd`, and
  `settings.ini` only answers when neither does. Writing just the ini changes nothing and looks
  like it worked. Plasma's `gtkconfig` module fills in icons, cursor and font in all three and
  leaves the theme *name* empty — which means Adwaita, which ignores the 84 Nova colours the
  same module faithfully regenerates into `colors.css` for a Breeze stylesheet that references
  them 965 times.

The rule: **ship the default, then pin it in the user's own config from `moos-apply-theme`, then
read it back from the running desktop.** `kreadconfig6`, `gsettings get`, and
`Gtk.Settings.get_default()` answer what the user actually has. A file in `system_files/` does
not, and neither does a gate that reads one.

**A button is only as real as its route.** Mo AI is pure QML: it cannot exec, so every button
is a `Qt.openUrlExternally("moos://…")` that lands in `moos-open`'s `case`, which runs the
matching `moai-do` action. Nothing checked that the two agreed. Eleven buttons once shipped —
every Install button, Mo PC Remote's Start/Stop/Reconnect, Install/Run for Codex and Claude —
opening `moos://` routes `moos-open` had no case for. They fell through to the default arm,
popped "unknown MoOS action", and did nothing. Every gate was green: one asserted four route
strings existed, none compared the routes the UI *opens* against the routes the router
*declares*. `verify_user_experience.py` now cross-checks both directions — every `moos://` URL
in every QML app must have a case, and every route `moos-open` hands to `moai-do` must be an
action `moai-do` implements.

When you write that kind of gate, **exclude the default arm**. The first version of this one
collected `*)` as a route, and `startswith("")` is true for every string on earth — so the gate
passed everything, including the dead buttons it was written to catch. A gate that cannot fail
is worse than no gate. Prove a new gate bites by breaking the thing it guards and watching it
go red.

**`/` is not the disk.** On bootc/OSTree, `/` is a read-only composefs overlay; `statvfs` reports
it as a ~60 MB filesystem that is 100% full. `shutil.disk_usage("/")` therefore returns 0 total,
0 free, and the Hardware Centre showed "?" for storage on every MoOS machine it ever ran on.
The real filesystem is the one under `/sysroot` (`/var` is part of it). `moai-do` already knew
this — `do_optimize` measures `/var` — and `moai-control` did not.

**Boot the image and look at it.** `podman build` + `bootc-image-builder --type qcow2` + qemu
with `screendump` takes about half an hour and is the only thing that found any of the above.

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

**`pgrep -f <name>` matches your own shell.** `until ! pgrep -f bootc-image-builder; do sleep 30;
done` never exits: the waiting shell's own command line contains the string, so pgrep finds
itself and the loop waits forever on a process that already finished — or, worse, on one that
never started. Wait on the actual thing (a PID, a container name, an output file), not on a
substring of your own command.

**Disk images do not fit in a tmpfs.** A qcow2 of this image is ~10GB and `/tmp` here is a 7.8GB
tmpfs. Build them somewhere on real disk.

**`/var` must be clean.** `bootc container lint` is the final build stage and it will reject
content in `/var`.

**Privileged actions go through `moai-do`, and nowhere else.** It is a fixed allowlist with
confirmation and Polkit. Mo AI can *name* an action from that list — the UI turns it into a Run
button — but the model never executes anything itself. Do not add a path that lets a model, or a
web page, run a command. If you add an action, add it to `moai-do`, to `moos-open`'s case
statement, and to Mo AI's system prompt.

`moos:` is a **registered URL scheme**, so any web page the user visits can hand `moos-open` a
URL. That is survivable only because every route is a fixed action: the one route that carries a
free-form value (`apps/install/<id>`, whose id comes from a Flathub search) validates the
reverse-DNS shape in `moos-open` *and* again in `moai-do`, which then refuses to install without
an explicit `y`. Keep it that way — a drive-by page must never be able to do more than raise a
prompt the user has to answer. Coding agents (`moai-do install-codex` / `install-claude`) take
**no privilege at all**: `/usr` is read-only here, so they `npm install --prefix ~/.local` and run
as the user. Do not "fix" that by reaching for pkexec.

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
