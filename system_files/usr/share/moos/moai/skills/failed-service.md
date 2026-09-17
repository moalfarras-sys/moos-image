---
id: failed-service
title_en: A system service has failed
title_ar: خدمة في النظام تعطّلت
use_when: A health check reports failed services, a feature stopped working with no visible error, or the person asks why something is "failed".
---
## Look first
1. `list_failed_units` — it has two parts: system units and the person's own session units.
2. For each failed unit → `unit_status` name=<unit>. Add user=true for a unit listed under the person's session.
3. `read_journal` unit=<unit> priority=`warning` since=`boot` lines=80 (user=true for a session unit). Read the LAST error, not the first warning.

## Steps — repairs that exist
Every repair below asks the person first; say what it will do before they decide.
- `pipewire.service`, `pipewire-pulse.service`, `wireplumber.service` → skill `no-sound` (`fix_audio`).
- `NetworkManager.service`, `systemd-resolved.service` → skill `no-internet` (`net_doctor`).
- `bluetooth.service` → skill `bluetooth-device`.
- `waydroid-container.service` → `setup_waydroid`, only if the person uses Android apps; otherwise it is harmless.
- App or store units → `read_moos_log` name=`store`, then `update_apps`.
- A unit that began failing right after a system update → skill `update-and-rollback`.

## Be honest
You have no tool that restarts, stops or edits an arbitrary service. When the failed unit is not in the list above: explain in plain words what its log says and what it affects, say that no automatic repair exists for it, and offer `support_bundle`. Say "a restart of the computer may clear it" only when the log shows a transient cause, such as a timeout or a dependency that was not ready.
