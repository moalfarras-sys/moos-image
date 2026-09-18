---
id: graphics-and-nvidia
title_en: Graphics problems and NVIDIA cards
title_ar: مشاكل الرسوميات وبطاقات NVIDIA
use_when: Games or video stutter, the screen tears, the resolution is wrong, or the computer has an NVIDIA card that is not being used.
---
## Look first
1. `gpu_report` — which graphics processor, which driver, how much of its memory is in use.
2. `check_drivers` — read its recommendation; it already knows which cards need what.
3. `os_state` — the image name tells the edition. An image name that starts with `moos-nvidia` is the NVIDIA edition.

## Steps
1. An NVIDIA card is present and the edition is NOT the NVIDIA edition → `install_nvidia`. It asks first and needs the administrator password. It switches this computer to the MoOS NVIDIA edition, keeps the current system for rollback, and applies on restart. It changes nothing when no NVIDIA card is found.
2. Already the NVIDIA edition, and `gpu_report` shows the driver is not loaded → `inspect_boot`, then `read_journal` priority=`err` since=`boot` lines=80. If this began after an update → skill `update-and-rollback`.
3. Stutter or tearing in one app only → that app's own graphics settings. For games → skill `gaming-and-windows-apps`.
4. Wrong resolution, scale or refresh rate → `open_settings` page=`display`. The person chooses; no tool sets a display mode.
5. The graphics memory is nearly full in `gpu_report` → name the process using it and suggest closing it.

## Stop and tell the person when
- `os_state` names the ARM edition (`moos-arm`): there is no NVIDIA edition for ARM, and an ARM cloud server has no graphics processor at all — the processor draws the picture. Say so; there is no driver to install.
- `check_drivers` recommends nothing and `gpu_report` is healthy: the system side is fine. Do not switch editions "to try".
