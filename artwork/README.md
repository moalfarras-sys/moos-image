# MoOS Nova artwork sources

`generate_nova_visuals.py` is the deterministic source for the original MoOS
app icons, Anaconda artwork, additional wallpaper packages, and GRUB artwork.

The generator consumes the canonical transparent emblem already shipped at
`system_files/usr/share/moos/moos-logo.png`. Its palette values mirror
`branding/PALETTE.md`, the project-wide source of truth. Runtime PNGs receive an
embedded sRGB profile. App icons and installer assets are rendered at 4x and
downsampled once with LANCZOS; wallpapers are composed directly on a native
3840x2160 canvas and only downsampled for smaller aspect variants.
The generated sRGB profile uses a fixed ICC header date, so repeated exports are
byte-for-byte rather than changing solely because LittleCMS wrote the wall-clock
second into otherwise identical PNG metadata.

Run all generators from the repository root:

```powershell
python artwork/generate_nova_visuals.py
python artwork/generate_nova_symbols.py
python artwork/verify_nova_visuals.py
```

Or run one family with `--icons`, `--installer`, `--wallpapers`, `--grub`,
`--sddm`, `--previews`, or `--plasma-style`.

The first Nova Plasma Style geometry batch generates complete `button.svg` and
`viewitem.svg` FrameSvg contracts. Their IDs and margins are pinned to official
libplasma 6.7.2. Top-level panel/dialog/tooltip masks remain on the verified
fallback path until this low-risk state batch passes live Plasma testing; this
prevents an untested mask from clipping a whole popup or panel.

`generate_nova_symbols.py` produces the renderer-safe, font-independent icon
family used to replace emoji in MoOS Welcome, Hardware Center, and Compatibility
Hub. Claude's exact QML replacement map is tracked in `NOVA_SYMBOL_MAP.md`.

The four optional sound-theme events use the separate synthesizer and
PySoundFile 0.14.0 only at generation time:

```powershell
python -m pip install soundfile==0.14.0
python artwork/generate_nova_sounds.py
```

Runtime outputs follow the freedesktop Sound Theme and Sound Naming
specifications: Vorbis I in lowercase `.oga` files, 48 kHz stereo, under
`/usr/share/sounds/moos-nova/stereo/`.

All art in this generator is original MoOS artwork, © Moalfarras. Wallpaper
package metadata licenses the wallpaper outputs under CC-BY-SA-4.0.

The installer assets are also mirrored under
`system_files/usr/share/moos/branding/anaconda/`. That canonical location is
not owned by Anaconda packages, so the build can restore the authored 200×160
logo and companion backgrounds after `anaconda-live` writes its stock pixmaps.

`nova-session-icon.svg` is the neutral MoOS session mark. The SDDM generator
installs it under every compatibility filename that SilentSDDM can request, so
an unexpected session name can never expose an upstream desktop logo.

Some upstream lookup filenames must remain (`fedora-logo-icon.png`,
`org.fedoraproject.AnacondaInstaller.png`, session names such as `ubuntu.svg`).
Their bytes are MoOS artwork, not foreign art. The verifier enforces equality
with the canonical MoOS assets and rejects every unreviewed foreign-named visual
file; removing these aliases would allow package-owned logos to return.
