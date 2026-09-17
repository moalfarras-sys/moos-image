---
id: bluetooth-device
title_en: Connect or repair a Bluetooth device
title_ar: توصيل جهاز بلوتوث أو إصلاحه
use_when: A headset, speaker, keyboard, mouse or phone will not pair, keeps disconnecting, or is connected but does nothing.
---
## Look first
1. `get_system_status` — is Bluetooth available and on?
2. `unit_status` name=`bluetooth.service`.

## Steps
1. Bluetooth is off → `toggle_bluetooth` value=`on`.
2. Pairing needs the person: the device must be in pairing mode and a code may appear on screen → `open_settings` page=`bluetooth`, then guide them: put the device in pairing mode, choose it in the list, confirm the code.
3. A headset is paired but silent → `open_settings` page=`audio` and choose the headset as the output. For calls, choose the headset profile that has a microphone; music quality is lower in that profile, and that is normal.
4. The service has failed → `read_journal` unit=`bluetooth.service` priority=`warning` since=`boot` lines=60, then `check_drivers`: missing adapter firmware is a common cause.
5. `get_system_status` says Bluetooth is not available → this computer has no Bluetooth adapter, or it is disabled in the firmware setup. Say so; no software repair exists.

## Never
- Never use `toggle_bluetooth` value=`off` as a "reset" while the person may be using a Bluetooth keyboard or mouse: it cuts them off. The system asks them first for that reason.
