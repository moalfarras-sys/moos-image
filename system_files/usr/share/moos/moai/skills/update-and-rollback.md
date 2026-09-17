---
id: update-and-rollback
title_en: Update MoOS, or go back after a bad update
title_ar: تحديث MoOS، أو الرجوع بعد تحديث سيّئ
use_when: The person wants the latest MoOS, asks what version they run, an update failed, or something broke right after an update.
---
## Know this first
A MoOS update replaces the whole system image at once. It is downloaded and STAGED while the person keeps working; nothing changes until the next restart, and the previous version is kept so the person can go back. Apps and personal files are not part of the image and are never touched by an update or a rollback.

## Look first
1. `os_state` — the booted version, a staged version (downloaded, waiting for a restart), the version kept for rollback, and whether the origin is signed.

## Steps
1. The person wants the latest → `system_update`. It asks for confirmation and the administrator password, then downloads and stages a signed image. Its answer may instead be one of these, and you must report which: already on the latest signed image (nothing to do); an update is already staged (only a restart is missing); another update is in progress (wait, do not start a second one); an older published image was refused (nothing changed — a newer release will follow).
2. When it finishes, `os_state` must show a staged version. Tell the person to restart when it suits them; never restart for them.
3. "Since the update, X is broken" → confirm with `os_state` that a rollback version exists, explain that going back returns the whole system to the previous version, then `system_rollback`. It asks first and applies on restart.
4. The update failed → `read_journal` priority=`err` since=`1h` lines=80, then `disk_status` (a full `/var` is the most common cause → skill `disk-full`) and `network_status`.
5. The origin reads UNSIGNED or local → do not update. Tell the person this computer is not following the official signed MoOS image, and offer `support_bundle`.

## Never
- Never suggest adding system packages with a package manager or editing files under `/usr`: the system image is read-only and it cannot work. Apps come from Mo Store (`install_app`) or App Drop (skill `install-an-app`).
