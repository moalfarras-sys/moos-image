# MoOS — where the project actually is

**Read this before touching anything.** It is the map an agent needs on day one:
what exists, what is load-bearing, and which of the "obvious" things to do next
are traps that have already cost this project a day.

Last updated: 2026-07-13, image `44.20260713.104`.

---

## The shape of the thing

| Repository | What it is | How it reaches the user |
|---|---|---|
| `~/moos-image` | The OS. A bootc image built from `Containerfile` + `build_files/build.sh` + a literal filesystem tree in `system_files/`. | Push to `main` → GitHub Actions builds **two editions** (`moos`, `moos-nvidia`), signs them with sigstore, pushes to `ghcr.io/moalfarras-sys/`. The user's machine `bootc upgrade`s from the registry. |
| `~/MoPlayerMoOS` | The IPTV player. Flutter. **Its own repository, local-only — no GitHub remote.** | **Vendored** into `moos-image/moplayer/` by `just sync-moplayer`, then compiled *inside* the image by a Containerfile stage. The image ships the binary, never the toolchain. |
| `~/MoPlayerios` | An iOS build of MoPlayer. Not part of the OS. | — |

The machine this is developed on **boots the thing being developed**:
`ghcr.io/moalfarras-sys/moos-nvidia:latest`, signature-enforced. That is the whole
reason the gates below exist.

---

## The five traps that have actually bitten

These are not style notes. Each one shipped, or nearly shipped, and each one cost
hours to find because **the gate was green while the thing was broken**.

### 1. The shadowed-config trap
The image is right, the user still does not get it. `/etc/xdg/…` and
`/usr/share/…` are *defaults*; a file in `~/.config` or `~/.local/share`
**shadows them forever**. Staging a fix into the home directory to "prove" it on
the running desktop leaves that shadow behind. `moos-apply-theme` exists to remove
those shadows once the system copy is correct — extend it rather than writing a
new one.

**Corollary that cost two hours today:** `moos-selfcheck` verified the *system's*
keyboard layout (`localectl`, which said `de,ara`) while the *session* was running
`us`, because fcitx5 had rewritten `~/.config/kxkbrc`. A check that reads the
image instead of the running desktop cannot fail. It asks KWin now.

### 2. A gate that matches its own comment
Every file here documents the bug it prevents — so a gate written as
`"Kawkab Mono" in text` passes forever, because the *comment* names Kawkab Mono.
`tests/verify_user_experience.py` has a `code()` helper that strips comments.
**Use it.** And after writing a gate, **break the thing on purpose and watch the
gate go red.** A gate that has never failed has never been tested.

### 3. The build context is not the git tree
`COPY system_files/ /` copies from the *working tree*, and `.gitignore` has no say
in it. The image shipped `/usr/bin/__pycache__/moai-control.cpython-313.pyc` — the
bytecode cache of the build machine — while CI, building from a fresh clone,
shipped nothing of the sort. **Two different images from one commit.**
`.containerignore` now excludes it, and a gate in `build.sh` fails the build if any
`__pycache__` reaches `/usr/bin`.

And note the pattern syntax: `__pycache__/` matches only the **context root**. It
must be `**/__pycache__/`. The first version of that file looked right, read right,
and excluded nothing. The gate caught it.

### 4. Vendoring drops what git does not track
`just sync-moplayer` copies `git ls-files` from `~/MoPlayerMoOS`. An **untracked**
file is copied by nobody: the vendored tree keeps the import and loses the file,
and the image fails twenty minutes later, inside a container, on a missing URI. It
**refuses a dirty tree** now, and a gate walks every relative import in the
vendored source and fails if the target was not vendored.

### 5. The local LLM owns the graphics card
MoOS ships a local model that holds **~6 GB of an 8 GB card** while loaded. With
that little left, EGL cannot make a context: `eglMakeCurrent failed` → libepoxy
asserts → **the process aborts**. The user's own OS killed its own video player,
silently. `/usr/bin/moplayer` calls `moos-gpu-headroom` first, which unloads *only*
the brain and only when the card is nearly full. A gate requires the launcher in
`system_files/` to be **byte-identical** to MoPlayer's own
`packaging/moos/moplayer` — the guard lived in only one of them for two hours, one
`install -D` away from being lost.

**Practical rule:** check `nvidia-smi` free memory before launching anything
GPU-heavy for a screenshot. Do not open a browser to "set up a scene" — that
exhausted VRAM and took KWin down with a SIGSEGV.

---

## Verification: how to actually see things

- **Synthetic input does not work on this machine.** `ydotoold` runs, the uinput
  device exists, and KWin receives nothing — in logical *or* physical coordinates.
  Proven by clicking a window's close button in both spaces and watching the
  process live. **Never plan a loop that needs to drive a GUI.** Reach the state
  from outside instead: `moplayer --section live`, `moplayer <subscription-link>`,
  a route the app opens on. If a state can only be reached by clicking, add an
  honest CLI seam (it is usually a feature someone wanted) or ask the user.
- **Screenshot:** `spectacle -b -n -f -o out.png` (not `grim` — wlroots only), then
  crop and zoom with ImageMagick and *read the image*.
- **A new window opens behind a fullscreen app.** Make a temp virtual desktop,
  switch, launch, capture, switch back, remove.
- `konsole --geometry` **is not a valid option** — the process exits instantly and
  no window appears. This silently blinded a whole session.

---

## MoPlayer: the IPTV facts that decide the design

Measured against the maintainer's real subscription, not assumed:

- A subscription is sold as **one link**:
  `…/get.php?username=U&password=P&type=m3u_plus`. Pasted into an M3U field it
  *works* — and yields channels and nothing else. Read as what it is (a panel plus
  an account), the same string opens the whole Xtream API: **12,653 channels,
  20,187 films, 10,550 series.** That is `lib/services/source/source_link.dart`,
  and it is used by both the login screen and the command line.
- **`max_connections = 1`.** One stream at a time. Never design a flow that tunes a
  channel to show a preview — the user knocks their own stream off the air. This is
  why the live screen's third pane follows the channel you are *looking at*.
- Panels lie about their own API: this one answers `get_short_epg` and
  `get_simple_data_table` with `[]` for **every** channel, while `xmltv.php`
  returns 2,587 programmes. An "empty" guide is usually an unimplemented endpoint.
- The panel publishes **duplicate** `<programme>` elements, and serves its
  catalogue with 32 identical-artwork recorded matches first. Sort by `added` or
  the film wall reads as a failed image load.
- The home page's football comes from that guide, joined against the user's own
  channels, so every card is one press from playing. A fixture on a channel the
  account does not carry is **not drawn** — a card that cannot be pressed is a
  disappointment dressed as a feature.

---

## Owner's UX rules (do not "improve" these away)

- The dock has **seven** slots: search · home · live · movies · series · favorites ·
  settings. Home *is* in the dock — the corner logo was not enough.
- Every browse page: **groups (vertical) · wall · preview**. The preview follows
  hover **and keyboard focus**.
- **The mouse wheel scrolls the page.** A rail must never turn a vertical wheel
  into sideways movement — the home page is a column of rails, so that makes
  everything below the fold unreachable. Shift+wheel and the hover arrows move a
  rail. There is a widget test that fails if this regresses.
- Settings is an Apple-style panel. Its Updates section is honest: MoPlayer ships
  *inside* the image and `bootc` replaces the whole OS atomically, so there is no
  self-update button, because there is no self-update.
- The brand palette is **measured off `assets/branding/logo.png`**, not chosen
  beside it. A test opens the PNG and fails if the tokens drift.

---

## Gates — what runs, and where

| Gate | Runs in |
|---|---|
| `tests/verify_user_experience.py` | CI (before the build) **and** `just build` |
| `tests/test_device_plan.py` | same |
| `tests/test_moai_do.py` | same — covers all 17 `moai-do` actions and rejects anything off the list |
| `build_files/verify_image_experience.py` | *inside* the image, after every package and rebrand |
| `__pycache__` / bytecode-cache gate | inside the image, at the end of `build.sh` |
| MoPlayer bundle completeness | inside the `moplayer-build` stage |
| MoPlayer: `flutter analyze` + 92 tests | `just check` in `~/MoPlayerMoOS` |

They were honour-system until today: **not in CI, not in `just build`**. If you add
a gate, wire it into both, and break it once to prove it fires.

---

## Working rules

- `git status --short` before every batch. Another agent may be in the same tree —
  it has happened, and a commit landed on the wrong branch because of it.
- Do not commit, push, or change the installed image without the owner asking.
- Every visible fix adds a gate or a test that would have caught it.
- Do not invent a new file under `system_files/` before searching for the surface
  that already does that job.
