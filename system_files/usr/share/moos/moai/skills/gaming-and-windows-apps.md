---
id: gaming-and-windows-apps
title_en: Games, Windows programs and Android apps
title_ar: الألعاب وبرامج ويندوز وتطبيقات أندرويد
use_when: The person wants to play games, run a Windows program or an .exe, or use Android apps on this computer.
---
## Look first
1. `gpu_report` — games need a working graphics driver. An NVIDIA card on the wrong edition comes first → skill `graphics-and-nvidia`.
2. `disk_status` — games are large; check the free space on `/var` before a big download.

## Steps
1. Games → `setup_gaming`. It asks first, then installs only what is missing: Steam, Bottles, Lutris and ProtonUp. Most Windows games on Steam run through Steam's own compatibility layer; the person turns it on in Steam's settings.
2. A Windows program that is not a game → `setup_windows`. It installs Bottles, which runs `.exe` programs in a managed environment. Opening Bottles later needs no administrator password.
3. Android apps → `setup_waydroid`. It asks first, needs the administrator password, and downloads a free Android image of about 1 GB the first time. It has no Google Play; apps come as `.apk` files or from an open app store inside it.
4. After any of these → `list_installed_apps` to confirm what is there, then `open_app` app_id=<id>.

## Be honest
- Not every Windows program or game works. Games with kernel-level anti-cheat usually do not. Say so before the person spends an evening on it.
- A game that stutters on a healthy system is usually set too high for the card; say which card `gpu_report` found.
