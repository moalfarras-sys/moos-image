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

### 2. The video texture path — GL is correct, the CPU copy tears

media_kit can hand mpv's frames to Flutter through a shared GL texture (zero
copy) or through a CPU copy. Both have bitten this app, in opposite directions.

**The CPU copy is not a safe fallback, it is a broken picture.** media_kit's
`texture_sw_copy_pixels` hands Flutter's raster thread a raw pointer to the one
pixel buffer mpv's render callback is concurrently writing into, and takes that
buffer's mutex on the writer side only. One buffer, no fence: a frame Flutter
uploads while mpv is midway through the next one is half old and half new. That
is the horizontal break users report as "الصورة تتكسر". Clamping the surface to
720p shrinks the window the race can land in — it looks fixed for a while — but
it cannot close it, and it pays by upscaling every stream from 720p.

**The GL path used to kill the process** — silently, no exception, no coredump —
right after it logged `Using H/W rendering` and resized the texture to
1920x1080. The reason was never the interop itself: media_kit_video **1.x
rendered on Flutter's own EGL context**, and two threads driving one context is
undefined behaviour NVIDIA answers by taking the process with it.

media_kit_video **2.0 renders on an isolated context of its own** — the log line
is now `H/W rendering with isolated EGL context.` — and that is the fix. This
repo moved to 2.0.1 during the 1.2 overhaul; the NVIDIA guard simply had not
been re-tested against it and kept the app on the torn path for a release.
Verified 2026-07-26 on the RTX 2080 SUPER (open module 610.43.03, Plasma
Wayland): three minutes of unbroken 1080p, full-resolution texture, position
advancing in real time.

So the GL path is now the default **everywhere, NVIDIA included**. What keeps
that honest is `VideoPathProbe`: a marker written before the texture is created
and removed once playback has proven itself, either by ten seconds of continuous
play or by a clean shutdown. Two launches in a row that reach neither, and the
app falls back to the CPU path by itself and says so. The failure mode this
guards is unobservable from inside the process, so the check happens on the
*next* launch — that is the whole design, and `test/video_path_probe_test.dart`
is what keeps it working.

The lesson worth keeping is not "GL is dangerous". It is that the last version
of this file stated a hardware verdict — *NVIDIA crashes* — for what was really
a **library bug**, and the workaround then outlived the bug by a whole release.
When a dependency that owns the failing code moves a major version, re-run the
experiment before trusting the guard written against the old one.

Hardware *decoding* (`hwdec`) is a different setting and is on either way.
`MOPLAYER_VIDEO_HW=0` forces the CPU path back; `=1` forces GL on even after the
probe has tripped.

### 2b. "The picture is breaking up" usually means interlacing, not tearing

A large share of live IPTV channels are 1080i or 576i, because the satellite and
cable feeds they are restreamed from are. Each frame is two fields captured 20 ms
apart, and shown without deinterlacing anything that moves grows a comb of
horizontal lines. A viewer reports that in exactly the words they would use for a
torn frame — *الصورة تتكسر*, the picture is breaking.

mpv's default is `deinterlace=no`, which is right for a file player and wrong for
live TV. `_tuneForIptv()` sets `auto`, and the player exposes an override,
because the automatic answer trusts the stream's own flags and re-encoded
channels lie in both directions.

Do not add a manual `vf` deinterlacer next to it: mpv inserts its own for this
property, and a hand-set chain deinterlaces twice rather than better.

**Before blaming the renderer for a picture fault, get the numbers.** The
statistics panel (`O`, or the tune button) and the one-line `playback:` summary
in the journal report the decoder, real resolution, both dropped-frame counters
and the buffer. Software decoding, a channel that is genuinely 720p, a starved
cache and a mismatched frame rate all look identical to a viewer and produce
completely different numbers there.

### 2c. Known upstream: media_kit hands Flutter the texture without a fence

`texture_gl_populate_texture` in media_kit_video 2.0.1 renders mpv's frame on
mpv's EGL context, calls `glFlush()`, switches to Flutter's context and returns
the texture. `glFlush` only *submits* commands — it does not wait for them. The
EGL specification requires a sync object to share an image across contexts, so
Flutter's raster thread can legally sample the texture while mpv's writes for
that frame are still executing.

This is a real defect and the fix is a fence (`eglCreateSyncKHR` on mpv's
context, `eglWaitSyncKHR` on Flutter's). It is **not applied**, because applying
it means vendoring the plugin — and this app's licence to live in the MoOS image
is that it adds nothing to the image's dependency surface. That is a maintainer's
call, not a passing one. A working patch is described in the commit that added
this section.

If a torn picture survives deinterlacing, this is the next thing to try.

### 2d. Recording, timeshift and stills are libmpv, not a second pipeline

`stream-record` writes the packets mpv is already demuxing straight to disk, so
recording a 4K channel is a remux that costs almost no CPU and cannot change the
picture. Timeshift is `demuxer-max-back-bytes`: mpv keeps packets it has already
played and can seek inside them, which is why pausing and rewinding live TV
needs no recording at all. `screenshot-to-file … video` saves the decoded frame
at source resolution with no overlay.

Do not reimplement any of these on top of the app. Each one would mean a second
connection to the panel and a second decode of the same stream, and an IPTV
subscription usually caps concurrent connections — the user would lose the
channel they are watching in order to record it.

Recordings are Matroska on purpose: it is the container that survives being cut
off mid-write, which is the normal way a recording of live TV ends. An
interrupted `.mp4` has no index and plays nowhere.

### 3. The file dialog belongs to the desktop

`services/system/file_chooser.dart` calls the XDG desktop portal over the
session bus rather than pulling in a Flutter file-picker. Under Wayland a client
cannot draw a filesystem browser on its own terms, and going through the portal
means the user gets *Plasma's* dialog — their bookmarks, their recent folders —
instead of a second file browser that looks like nothing else in the session. It
also costs no new dependency, because `package:dbus` is already here for MPRIS.

A missing portal returns null and the feature quietly does not happen. That is
the same rule as `bootstrap()`: nothing in this app may be fatal because an
optional session service is absent.

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
