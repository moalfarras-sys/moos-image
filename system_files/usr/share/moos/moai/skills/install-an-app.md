---
id: install-an-app
title_en: Install an app, from Mo Store or from a downloaded file
title_ar: تثبيت تطبيق من Mo Store أو من ملف منزَّل
use_when: The person asks for an app by name, downloaded an installer and does not know what to do with it, or asks how software is installed here.
---
## Know this first
MoOS has two everyday ways to add software, and neither needs a terminal:
- **Mo Store** installs apps by their id.
- **App Drop** takes a file the person downloaded — an AppImage, a portable `.tar.gz`, `.tar.xz` or `.zip`, or a `.flatpakref`. They open the file, or drop it into the Applications folder in their home. MoOS asks once, adds the app to the app menu, and needs no administrator password.

## Steps
1. `list_installed_apps` — it may already be installed; then `open_app` app_id=<id>.
2. You know the app's id (for example `org.mozilla.firefox`) → `install_app` app_id=<id>. It asks first. If you are not sure of the id, do not invent one: tell the person the app's name to search for in Mo Store.
3. The person has a downloaded AppImage, portable archive or `.flatpakref` → explain App Drop in one sentence, as above. You do not install files yourself.
4. A `.rpm` package: the last resort, and one you have no tool for. Look for the same app in Mo Store first, then for an AppImage from its maker. If neither exists, the person can use the "Install RPM" button in Mo AI's Apps panel: they pick the file from Downloads, Desktop or Documents; MoOS verifies the publisher's signature and refuses an untrusted one, asks first, needs the administrator password, and stages the package into a new system version that appears after a restart (the current version stays for rollback).
5. A `.deb` package was made for another kind of system and cannot be installed here at all. Say so; do not suggest converting it.
6. A Windows `.exe` → skill `gaming-and-windows-apps`. An Android `.apk` → `setup_waydroid`. It asks first, needs the administrator password, and downloads about 1 GB the first time.
7. After installing → `open_app` app_id=<id>, and if it does not start → skill `app-wont-start`.

## Never
- Never suggest a terminal package manager, adding software sources by hand, or running an installer script from a web page. The system image is read-only, so the first two cannot work, and the third is how computers get infected.
