# MoOS boot splash — Graphite Horizon

A native Plymouth script theme using the exact Graphite login landscape and the
approved rendered MoOS mark. `intro1.png` is byte-identical to the previous
sequence's resting frame (`intro32.png`); no replacement logo is introduced.

The mark appears on the first frame. A finite 360 ms opacity entrance settles
into a still; no movie, orbit, artificial percentage or minimum display time
holds up boot. Shutdown and encrypted-volume prompts immediately use the still.
Quit pins the composed frame for `--retain-splash` until the login renderer paints.

## Design and handoff

- Ground: UI2 `#14191C`; exact 1080p derivative of the Graphite login wallpaper.
- Hero: centred, width bounded by 70% of screen width and 62% of height at its
  original 856×556 aspect. Source decoding: 1.82 MiB instead of 58.1 MiB.
- Motion: opacity 0.70→1, nine ticks at 25 Hz, then idle script refresh at 1 Hz.
  Pre-login cannot read a desktop Reduced Motion preference; there is no endless
  decorative motion. The script never rescales images in refresh or quit.
- Messages: UI2 muted `#9CAFAC`; passphrase `#E8F1EF`, bullets `#4ED7C8`.
  Text is screen-bounded, event-driven and below the hero.
- Safe handoff: no extra waiting unit or timer; no GRUB rollback removal.
- `logo.png` remains the canonical fallback watermark required by identity gates.

## Reproduction and evidence

`artwork/generate_boot_backdrop.py` regenerates the exact login derivative.
`artwork/generate_boot_splash.py` maintains the canonical watermark and removes
retired sprites. The approved hero is preserved, not synthesized from a new logo.
`build_boot_frames.py --output PRIVATE_DIR` produces review cuts only and refuses
the shipped theme directory. `preview_boot_animation.py --out PRIVATE_DIR` is a
composition aid, not a native renderer or boot proof.

The SDK stage parses the actual theme with the rebuilt native script plugin,
and proves a BOM fixture is rejected. `scripts/review/plymouth-render.c` reviews
the native script/renderer on a private X server without the owner's desktop.
Full image gates retain the MoOS identity and prove the corrected Plymouth
library's exact bytes are in the initramfs. Release still requires the signed
artifact boot/reboot/poweroff and offline ISO proofs described in `RELEASE.md`.
