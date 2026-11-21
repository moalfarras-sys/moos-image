# MoOS boot splash — Liquid Glass

A native Plymouth script theme with its own fixed blue/teal canvas, independent
of all desktop themes and login wallpaper choices. Owner steering 2026-11-19:
a short, premium Liquid Glass scene; keep the MoOS mark itself, improve its
rendering and the typography.

## The scene (1.8 s, then still)

| Ticks (25 Hz) | What happens |
|---|---|
| 0 | Backdrop and the mark as a faint glass ghost: MoOS from the first frame. |
| 0–20 | Three liquid glass droplets (cyan, blue, violet) curve clockwise into the centre and dissolve. |
| 8–20 | The glass bezel forms around the mark. |
| 10–24 | The mark resolves inside the lens and settles 16 px. |
| 18–40 | A liquid sheen flows down over the glass, then rests at 80%. |
| 22–34 | A glint runs over the upper rim. |
| 24–40 | The Meyar Sans wordmark gathers letter by letter as its tracking closes. |
| 32–45 | The Meyar Arabic «مرحبًا بك» follows. Shutdown and reboot show «إلى اللقاء». |

After `ENTRANCE_TICKS` nothing moves. Quit, password entry and shutdown jump
straight to the resting composition. No minimum display time, perpetual orbit,
progress percentage or full-screen blur; refresh() never scales an image.

## Assets

| File | Source |
|---|---|
| `intro1.png` | The owner's vector master, cleaned with an edge-preserving filter that keeps its own internal lines, then rendered in Blender with a glass clear coat over rounded bevels. Same silhouette and colours. |
| `glass-bezel.png`, `glass-sheen.png`, `glass-drop-1..3.png` | Blender renders on black, keyed to straight alpha by luminance. |
| `glass-glint.png` | Deterministic numpy sprite. |
| `mark-letter-1..4.png` | Meyar Sans Light, one letter per image on a shared baseline. |
| `welcome-ar.png`, `farewell-ar.png` | Meyar Arabic Regular shaped by libraqm (HarfBuzz/FriBiDi), ink box with stacked marks plus margin. |
| `boot-backdrop.png` | Unchanged procedural canvas (`artwork/generate_boot_backdrop.py`). |
| `logo.png` | Canonical fallback watermark required by the identity gates. |

Regenerate everything with `python3 artwork/generate_boot_glass.py --work
<private real-disk dir>` (Flatpak or native Blender; `--save-blend` writes
editable scenes). The scene is `artwork/blender/moos_boot_glass.py`; provenance,
including every asset hash, is `artwork/moos-design/boot-glass.json`.

## Evidence and boundaries

`tests/test_boot_splash_polish.py` executes the actual script callbacks (finite
entrance, droplets before the greeting, quit/shutdown at rest, no work after
rest), the resting layout at seven screen sizes, decode/initramfs budgets and
asset provenance. Image builds derive the asset list from `moos.script` and
`verify_plymouth_initramfs.py` proves every loaded asset is byte-identical in
the final initramfs. Native frames from the review renderer are pixels on a
private X server, not a DRM boot. Release still requires the signed artifact
boot/reboot/poweroff and offline ISO proofs described in `RELEASE.md`.
