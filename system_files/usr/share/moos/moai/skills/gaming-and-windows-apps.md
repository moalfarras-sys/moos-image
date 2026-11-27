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
1. Games → `setup_gaming`. It asks first, then installs only the missing game and compatibility support. Most Windows games in Steam use its built-in compatibility option; the person turns it on in Steam's settings.
2. A Windows program that is not a game → `setup_windows`. It prepares an isolated environment for `.exe` programs. The person should open the file again after setup; never make them choose or configure an engine.
3. Android apps → `setup_waydroid`. It asks first, needs the administrator password, and downloads about 1 GB the first time. Afterwards the person installs an `.apk` by double-clicking it or dropping it in Mo Store; never give them a runtime command.
4. After any of these → `list_installed_apps` to confirm what is there, then `open_app` app_id=<id>.

## Be honest
- `os_state` names the ARM edition (`moos-arm`): Steam, Proton and Windows programs are built for x86 PCs, and `setup_gaming` refuses on ARM. Say so, then offer Linux apps from Mo Store instead.
- Not every Windows program or game works. Games with kernel-level anti-cheat usually do not. Say so before the person spends an evening on it.
- For an exact Steam App ID, `moos-storectl game-compatibility <id>` reads the reviewed MoOS result offline. Add `--with-valve` to check the Steam Deck rating online. A Deck rating applies to Valve’s hardware.
- Ask for the exact game and edition. EA SPORTS FC 26 lists EA Javelin Anticheat and an unsupported Steam Deck rating. Treat that title as unsupported locally through Proton. Another FIFA edition needs its own check. [Publisher listing](https://store.steampowered.com/app/3405690/)
- After gaming setup, distinguish installed launchers, an available compatibility tool and a game reaching playable content. For performance, report the game's Windows build, GPU, rendering API, resolution, settings and measured frames.
- A game that stutters on a healthy system is usually set too high for the card; say which card `gpu_report` found.
