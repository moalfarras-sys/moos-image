# Shipping MoPlayer inside the MoOS image

This directory is what the **`moos-image`** repository needs in order to make
MoPlayer part of MoOS itself, instead of something a user installs into
`~/.local`. Nothing here is applied automatically — MoOS's `main` builds a real
operating system onto the maintainer's real machine, and a player is not a good
enough reason to touch that pipeline without a human reading the diff first.

## What MoOS already provides

| | |
|---|---|
| `mpv-libs` | **Already in the image.** It *is* the playback engine — media_kit binds `libmpv.so.2`. Nothing to add. |
| `gtk3` | Already present (Plasma pulls it in for GTK apps). |
| `libsecret` / KWallet | Already present. This is where the IPTV credentials go. |
| `ibm-plex-sans-fonts`, `ibm-plex-sans-arabic-fonts` | Already present. The app's type is the system's type. |

So the image does not gain a single new runtime dependency. What it gains is a
directory of Flutter assets, one ELF binary, a launcher, a `.desktop` file, and
an icon set.

## The four pieces

1. **The bundle** → `/usr/lib/moplayer/`
   Built by this repo's CI (`build-bundle.yml`), published as a release tarball.
   The Flutter binary needs `data/` and `lib/` beside it; that is why the whole
   bundle is copied, not just the executable.

2. **The launcher** → `/usr/bin/moplayer`
   `packaging/moos/moplayer`. It `cd`s into the bundle before exec'ing, forces
   the Wayland backend, and says something useful if `libmpv` ever goes missing.

3. **The launcher entry** → `/usr/share/applications/org.moos.moplayer.desktop`
   Bilingual, with Live/Movies/Series jump actions, and — critically —
   `StartupWMClass=org.moos.moplayer`, which is the string Plasma matches the
   window against.

4. **The icons** → `/usr/share/icons/hicolor/<size>/apps/org.moos.moplayer.png`

## Containerfile

```dockerfile
# ── MoPlayer ────────────────────────────────────────────────────────────────
ARG MOPLAYER_VERSION=1.1.0
RUN curl -fsSL -o /tmp/moplayer.tar.gz \
      "https://github.com/moalfarras-sys/MoPlayerMoOS/releases/download/v${MOPLAYER_VERSION}/moplayer-linux-x64.tar.gz" \
 && mkdir -p /usr/lib/moplayer \
 && tar -xzf /tmp/moplayer.tar.gz -C /usr/lib/moplayer --strip-components=1 \
 && rm -f /tmp/moplayer.tar.gz \
 && chmod +x /usr/lib/moplayer/moplayer
COPY packaging/moos/moplayer                     /usr/bin/moplayer
COPY packaging/moos/org.moos.moplayer.desktop    /usr/share/applications/
COPY packaging/moos/icons/hicolor/               /usr/share/icons/hicolor/
RUN chmod +x /usr/bin/moplayer
```

## The gate to add to `build_files/build.sh`

MoOS's rule is that a shipped app must be *proven* to run, not merely proven to
exist — a green build that ships a broken launcher is worse than a red one. The
QML apps are started during the build for exactly this reason. MoPlayer cannot be
started headlessly (it needs a compositor), so the gate checks the two things
that have actually broken in practice:

```bash
# MoPlayer: the bundle must be complete, and its app_id must match its launcher.
test -x /usr/lib/moplayer/moplayer || { echo "MoPlayer: binary missing"; exit 1; }
test -d /usr/lib/moplayer/data/flutter_assets || { echo "MoPlayer: assets missing"; exit 1; }

wm_class=$(grep '^StartupWMClass=' /usr/share/applications/org.moos.moplayer.desktop | cut -d= -f2)
test "$wm_class" = "org.moos.moplayer" || { echo "MoPlayer: StartupWMClass drifted"; exit 1; }
strings /usr/lib/moplayer/moplayer | grep -qx 'org.moos.moplayer' \
  || { echo "MoPlayer: binary app_id does not match the .desktop file"; exit 1; }

# The engine. If this ever disappears from the base image, MoPlayer is a black
# window and nothing in the app can tell the user why.
ldconfig -p | grep -q 'libmpv.so' || { echo "MoPlayer: libmpv missing from image"; exit 1; }
```

## The `moos://` route

MoOS apps are reachable from Mo AI and the Welcome app through the `moos:`
scheme, which `moos-open` resolves. `verify_user_experience.py` cross-checks
both directions — every `moos://` URL a QML app opens must have a case here, and
every route here must be an action that exists. To let anything in MoOS open the
player, add one line to the `case` in `system_files/usr/bin/moos-open`:

```bash
    app/moplayer) gui moplayer ;;
```

and, if Mo AI is to show a button for it, the button opens `moos://app/moplayer`.

## What is *not* here, and why

**No Flatpak manifest.** MoOS ships Bazaar and a Flatpak runtime, and a Flatpak
would be the obvious way to distribute this to *other* distros. But inside MoOS
it would bundle a second libmpv, a second GTK and a second font stack next to the
ones the image already has, to sandbox an app that the image itself is shipping
and signing. A first-party app belongs in the image.
