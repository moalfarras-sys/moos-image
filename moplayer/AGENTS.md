# Working on MoPlayer for MoOS — read this first

This app ships **inside an operating system**. Not alongside it: MoOS signs its
image, and a first-party app that misbehaves is the OS misbehaving. The rules
below are not style preferences — each one is a thing that already went wrong on
the maintainer's actual machine, on a real RTX 2080 SUPER running Plasma Wayland.

## The three that will bite you

### 1. The app id is written in four places and they must all agree

| Where | What |
|---|---|
| `lib/core/config/app_config.dart` | `AppConfig.appId` — the source of truth |
| `linux/CMakeLists.txt` | `APPLICATION_ID` → the GTK/Wayland `app_id` |
| `packaging/moos/org.moos.moplayer.desktop` | `StartupWMClass` + `Icon` |
| MPRIS | `org.mpris.MediaPlayer2.<AppConfig.mprisName>` |

When they drift the app still builds, still runs, and quietly wears a generic
icon with media controls that raise nothing. Nothing else in the repo would
catch it — so `test/app_identity_test.dart` does. Do not delete it to make a
rename go faster.

This is the same failure MoOS's own `moos-qml-shell` exists to prevent for the
QML apps: the runtime derived the app_id from its own binary name, Plasma could
not match it to a `.desktop`, and drew the green Qt diamond.

### 2. The video texture path crashes on NVIDIA

media_kit can hand mpv's frames to Flutter through a shared GL texture (zero
copy) or through a CPU copy. On this machine the GL path **kills the process** —
silently, no exception, no coredump — right after it logs `Using H/W rendering`
and resizes the texture to 1920x1080. On the runs where media_kit happened to
fall back to the CPU path, it played for as long as you left it.

`PlayerService._useGpuTexturePath()` therefore turns the GL path **off when an
NVIDIA driver is present**, and `MOPLAYER_VIDEO_HW=1` forces it back on for
whoever eventually tests a fixed driver. Hardware *decoding* (`hwdec`) is a
different setting and stays on; the GPU still does the work, only the last copy
is on the CPU.

Do not "optimise" this back to the default because a benchmark looks better. It
was a coin flip, and the other side of the coin is the app vanishing mid-film.

### 3. Application state does not go in Documents

`Hive.initFlutter()` stores its boxes under `getApplicationDocumentsDirectory()`,
which on Linux is the user's **Documents folder** — localised, so the first run
of this app created `~/Dokumente/moplayer/` and put a lock file in it. `bootstrap()`
passes an explicit `$XDG_DATA_HOME/moplayer` path instead. Any new store you add
gets the same treatment. path_provider is answering an iOS question; on a
freedesktop system it is simply the wrong question.

## What must keep being true

- **libmpv is the system's, not ours.** MoOS ships `mpv-libs`. The app links it
  and bundles nothing. If you ever find yourself vendoring a second copy of the
  engine, stop: the reason this app is allowed in the image at all is that it
  adds zero runtime dependencies to it.
- **A `.desktop` entry is a contract.** `Actions=Live;Movies;Series` and
  `MimeType=…m3u…` both resolve to real behaviour in `lib/app/launch_args.dart`.
  MoOS's `AGENTS.md` records what happens when they do not: eleven buttons once
  shipped that opened routes nobody had implemented, popped an error, and did
  nothing. Every gate was green.
- **Every user-visible string is bilingual.** `lib/core/l10n/strings.dart`, Arabic
  and English, both filled. The `.desktop` file too. An app that only speaks
  English is the one surface in MoOS that does not.
- **Nothing in `bootstrap()` may be fatal.** No keyring, no network, no session
  bus, no Supabase — all of them are survivable, and the app must still open into
  a usable player. A video player that will not start because a *notification*
  channel is missing is an absurd trade.
- **The player is not a route.** It is a mode of the shell (`playerViewProvider`),
  because on a desktop, closing the player must not stop the stream. Making it a
  route again would break the mini player, the media keys that arrive while
  another screen is focused, and the channel that is supposed to keep running
  while you browse.

## Verifying a change

```bash
just check      # analyze + test — the same gate CI runs
just build      # release bundle
just install    # into ~/.local, appears in Kickoff
```

`flutter analyze` must be **clean**, not merely error-free: the repo is at zero
warnings and that is worth keeping.

Then actually run it. A build proves nothing about what the user sees — all three
bugs above passed the build.

```bash
# End-to-end, without touching the mouse: play a stream, then ask the *desktop*
# what it thinks is playing.
moplayer 'https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8' &
gdbus call --session --dest org.mpris.MediaPlayer2.moplayer \
  --object-path /org/mpris/MediaPlayer2 \
  --method org.freedesktop.DBus.Properties.Get org.mpris.MediaPlayer2.Player PlaybackStatus
# -> (<'Playing'>,)   … and the window title, and the taskbar icon, are the test.
```
