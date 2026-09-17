---
id: boot-problems
title_en: Slow startup, or errors while starting
title_ar: إقلاع بطيء أو أخطاء عند التشغيل
use_when: The computer takes long to start, shows errors while starting, or the person asks whether startup is healthy.
---
## Look first
1. `inspect_boot` — startup status and the recent errors.
2. `list_failed_units`.
3. `read_journal` priority=`err` since=`boot` lines=100.
4. `os_state` — did the version change recently?

## Steps
1. One unit is timing out during startup → `unit_status` name=<unit>, then skill `failed-service`.
2. The problems began with the last update → skill `update-and-rollback` (`system_rollback`).
3. `check_drivers` reports firmware updates → `update_firmware`. It asks first. Tell the person before they agree: a firmware update cannot be undone, the computer should be on mains power, and it must not be switched off while it runs.
4. Startup is slow with no errors → `top_processes` by=`cpu` a minute after login shows what is still working; many apps set to start at login are a common cause → `open_settings` page=`autostart`.

## What you cannot do
If the computer does not start at all, you are not running either. Tell the person, for next time: the startup menu keeps the previous MoOS version, and choosing it there starts the computer the way it was before the last update.
