# The MoOS boot splash

A Plymouth **script** theme that plays the owner's rendered MoOS logo sting as
the boot animation: a plasma ring ignites, the mark's arcs tear out of it and
rotate into place, the solid mark lands on its reflective floor, and the MoOS
wordmark fades up. It then holds that last frame until the desktop takes over.

Nothing here is hand-authored motion. Everything in this directory is generated,
and the generators are in `artwork/`.

## What is in here

| File | What it is |
|---|---|
| `moos.script` | The whole animation. Plays the sequence, holds the last frame, composes the frame the handoff leaves on screen, and draws the LUKS/message overlays. |
| `moos.plymouth` | The theme descriptor. Selects the `script` module. |
| `intro1.png` … `intro32.png` | The sequence, cut from the render. ~1.3 s at 25 fps. |
| `logo.png` | The mark on its own. **Not drawn by the splash.** `build.sh` copies it over Fedora's `spinner/watermark.png` and gates that the two match — that is what keeps the Fedora wordmark out of the fallback splash. |
| `glow.png`, `ring.png`, `head.png` | The slow-boot cue only (see below). A fast boot never shows them. |

## Rebuilding it

```sh
python artwork/build_boot_frames.py      # the sequence, from the source video
python artwork/generate_boot_splash.py   # logo + the slow-boot cue sprites
python artwork/preview_boot_animation.py # look at it without booting
```

`build_boot_frames.py` prints the frame aspect ratio it produced. **`INTRO_ASPECT`
in `moos.script` must match it**, or the sequence is drawn stretched;
`tests/test_boot_splash_polish.py` gates that, along with `INTRO_COUNT` against
the frames actually on disk.

## Three things that are easy to break

**Filenames are literal, never built by concatenation.** Plymouth's script
language has no string formatting, and its number-to-string conversion is not
specified to yield `1` rather than `1.000000`. A name built as `"intro" + i +
".png"` can therefore resolve to nothing on some Plymouth build, every image
load fails, and the whole theme drops to Plymouth's **text console** — on a
user's machine, never in CI. The 32 loads are written out in full for that
reason.

**Frames are scaled once per displayed frame, never at load time.** Pre-scaling
the sequence would cost `frames × screen × 4` bytes inside the initramfs — around
190 MB at 1080p — on machines that may have 1 GB. `refresh()` scales only when
the displayed frame changes, and only one scaled copy exists at a time.

**The stored frame size is a memory budget, not a quality knob.** Every frame is
decoded into RAM in the initramfs on every boot. It is currently ~58 MB decoded
and ~11 MB on disk; `test_intro_frames_fit_the_initramfs_budget` pins both.

## The handoff

`plymouth-quit` runs with `--retain-splash` (see
`plymouth-quit.service.d/10-moos-retain-splash.conf`), so the last frame drawn
here stays on screen until KWin's first modeset paints over it — several seconds
on a cold boot. `quit_callback()` therefore jumps to the sequence's resting frame
and hides everything that moves, so the retained image is a composed still rather
than a comet frozen mid-orbit, which reads as a hang.

The ground is flat `#14191C`, the UI2 canvas token the desktop opens on. The
render's own near-black background was keyed to transparency when the frames were
cut, precisely so the splash could sit on that colour: splash → first desktop
frame is one continuous colour with no hue flip.

## The slow-boot cue

A fast boot is over before it appears. After ~3.8 s — a first boot, an fsck, a
cloud instance — a soft breath and a faint head running a ring fade in, so a long
boot does not present a still image that reads as a hang.

## If the splash does not appear

The theme is almost never the thing that is broken; the surface it draws on is.
`plymouth.use-simpledrm` (see `usr/lib/bootc/kargs.d/20-moos-simpledrm.toml`) is
withheld on the NVIDIA edition for exactly this reason. A splash can only be
verified by looking at a boot, on the hardware, with the GPU that machine has —
do not add a gate here that reads config and calls it proof.
