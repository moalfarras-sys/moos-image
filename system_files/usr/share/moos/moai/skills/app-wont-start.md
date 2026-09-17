---
id: app-wont-start
title_en: An app does not start, or closes at once
title_ar: تطبيق لا يعمل أو يُغلق فوراً
use_when: An installed app does nothing when opened, shows its window and disappears, or stopped working after an update.
---
## Look first
1. `list_installed_apps` — find the exact id, and whether the app is installed at all.
2. `open_app` app_id=<id> — start it, then `read_journal` user=true priority=`warning` since=`1h` lines=60 to read what it said while starting.

## Steps
1. It is not installed → skill `install-an-app`.
2. The log mentions a missing runtime → `update_apps`. It asks first.
3. The log mentions the graphics driver, GL or Vulkan → `gpu_report`, then skill `graphics-and-nvidia`.
4. The log shows "permission denied" for a folder or a device → `open_settings` page=`permissions`.
5. Still broken → `uninstall_app` app_id=<id>, then `install_app` app_id=<id>. Both ask first. Tell the person before you start: the app's settings stay, but a game may have to download its data again.
6. It is a Windows program → skill `gaming-and-windows-apps`.

## Stop and tell the person when
- The app starts and the journal shows no error: ask what they expected to see. "Does not work" may be a missing file, an account or a network problem inside the app, which no system repair fixes.
