# Mo Store — architecture and shared contracts

Mo Store is MoOS's one place to find, install, open, update, remove and permission apps:
Linux apps, web apps, Windows programs and Android apps. This file is the contract between
its parts. `docs/DEVELOPMENT_PLAN.md` (P4.x and the "Every app, one verb" table) owns what is
still open; `PROJECT_STATE.md` owns what is measured.

## The rules that do not move

- **Every change of state is a `moos-storectl` job.** The Store window is pure QML and acts only
  through the `StoreBridge` in `build_files/moos-qml-shell.cpp` (enabled for `org.moos.store`
  and `org.moos.welcome` only), which starts `/usr/bin/moos-storectl` with an argv list. A
  `moos:` link may open the Store or an app's page; it never installs, removes or changes a
  permission (`store/install` must never appear in `moos-open`).
- **The signed catalogue (`/usr/share/moos/store/catalog.json`) is the only authority** for
  anything that is not an ordinary Flathub app: web addresses, download URLs, SHA-256 pins,
  sizes, executables inside archives, desktop ids. Nothing a web page, a launcher or an
  argument supplies can name an address or a file to run.
- **Downloads come from the publisher, pinned.** MoOS never mirrors a third-party program.
  Every download names the publisher's own HTTPS URL, its exact size and its SHA-256; a
  mismatch, an oversize body or a non-HTTPS redirect hop fails the job. Downloads land on disk
  under `~/.cache/moos-store/downloads/`, never in the RAM-backed `/tmp`.
- **The engine never says its name.** Store copy may name where an app comes from ("Windows
  programs", "Android apps", "Linux apps", "Web app"), its publisher and a file the person
  holds. It never names wine, bottles, waydroid, proton, lutris, qemu, bubblewrap, flatpak,
  appimage (as a mechanism), wayland, kwin, plasma, KDE, Chromium/QtWebEngine, or another OS.
- **Honest labels.** An app that is not sandboxed (App Drop, Windows, npm) says it can see the
  person's files. "Verified" means Flathub's verified flag, nothing else. A web entry that only
  opens a publisher page says "opened", never "installed".

## Kinds of app

| kind (index) | catalogue `install.kind` | installs to | runs with | removes |
|---|---|---|---|---|
| `flatpak` | — (`source:"flathub"`) | the user Flatpak installation | `flatpak run` | libflatpak; `--delete-data` also `~/.var/app/<id>`, overrides, portal permissions |
| `webapp` | `webapp` | `~/.local/share/applications/org.moos.webapp.<id>.desktop` + `~/.local/share/moos/webapps/<id>/` | `/usr/bin/moos-webapp <id>` | launcher; `--delete-data` also the profile |
| `appdrop` | `appdrop` (artifact `appimage` or `archive`) | `~/Applications/<id>/` + a MoOS-written launcher + record `~/.local/share/moos/appdrop/<id>.json` | the launcher | App Drop `remove` |
| `windows` | `windows-portable` | `~/.local/share/moos/windows-apps/<id>/` (own prefix) + launcher + record | `/usr/bin/moos-run-foreign --app <id>` | prefix, launcher, record |
| `android` | `android` | the Android container | `waydroid app launch` (via storectl `run`) | `waydroid app remove` |
| `npm` | `npm` | `~/.local` | its command | `npm uninstall` |
| `web` | `web` | nothing (opens the publisher page) | — | — |
| `dropped` | — | an App Drop install that is not in the catalogue | its launcher | App Drop `remove` |

## catalog.json (v2)

Top level: `_comment`, `categories[]`, `collections[]`, `featured[]`, `bundles[]`, `apps[]`.

- `categories[]`: `{id, en, ar, glyph}`. Ids: `ess`, `comm`, `work`, `art`, `media`, `fun`,
  `dev`, `ai`, `edu`, `util`, `droid`, `win`.
- `collections[]`: `{id (slug), en, ar, glyph, desc_en?, desc_ar?, apps:[4..24 app ids]}` — the
  Discover rows (editorial groups; an app may be in several).
- `featured[]`: 3..8 hero cards, in display order:
  `{app, title_en, title_ar, tagline_en, tagline_ar, accent?: "#rrggbb"}`.
- `bundles[]`: unchanged (Welcome's four directions must stay).
- Per app, new optional keys: `developer` (≤80), `keywords_en[]`, `keywords_ar[]` (≤12 short
  search words each, e.g. PhotoCraft: `photoshop`, `psd`; `فوتوشوب`), `accent` ("#rrggbb").
- `install` for `source:"moos"`:
  - `webapp`: `{kind, url (https), hosts[≤24, "*." prefix allowed], identity ⊆ {google,
    microsoft, apple, github}, permissions ⊆ {notifications, microphone, camera, location,
    clipboard, screen}, accent, risk:"web-app", requires_review:true}`; app id a slug
    `^[a-z0-9][a-z0-9-]{1,62}$`; must parse with `moos_webapp_policy.parse_entry`.
  - `appdrop`: `{kind, artifact:"appimage"|"archive", version, downloads:{<arch>:{url, sha256,
    size}}, desktop_id?, wm_class?, exec?, icon?, categories?, risk:"downloaded-executable",
    requires_review:true, external:true}`; top-level `arch` = sorted `downloads` keys.
    `exec`/`icon` are paths relative to the extracted tree (archives); `desktop_id` is the app's
    own reverse-DNS id (its Wayland app id) and becomes the launcher's file name when no other
    launcher already uses it.
  - `windows-portable`: `{kind, version, downloads:{"x86_64":{url, sha256, size}}, exe,
    wm_class?, risk:"downloaded-executable", requires_review:true, external:true}`; top-level
    `engine:"windows"`, `arch:["x86_64"]`, `cat:"win"`. `exe` is the program's path inside the
    zip, or the file name of a single `.exe` download. 64-bit (PE32+) programs only.
  - `android`: unchanged (`url`, `sha256`, `package` = id) plus optional `version`, `size`.
  - `npm`, `web`: unchanged. The old `appimage` kind (a bare file in `~/.local/bin`) is retired.

## Documents in `~/.cache/moos-store/`

All written atomically (temp file + rename), mode 0600, read by the QML with XHR.

- `index.json` — written by `moos-store-index`. A LIST: per app the existing keys plus
  `kind`, `name_en`, `search` (one folded string: both names, keywords, developer, id tail —
  lowercase, Arabic diacritics/tatweel removed, أإآٱ→ا, ى/ئ→ي, ؤ→و, ة→ه, Arabic digits→ASCII),
  `branding:{light, dark}|null`, `installed_version`, `update_available`, `eol`,
  `content_rating:"all"|"teen"|"mature"|null`, `compat:{verdict:"ok"|"warn"|"blocked",
  reasons:[keys]}`, `details:"details/<id>.json"|null`. Top level adds `collections`,
  `featured`. Not-apps (BaseApp, add-ons, runtimes, console-only tools) are excluded; installed
  apps that AppStream no longer lists and every App Drop record are included.
- `details/<id>.json` — written by `moos-store-index` with the index generation:
  `{schema:1, id, screenshots:[{thumb, full, caption?, width?, height?}], releases:[{version,
  date, notes}] (≤3), urls:{homepage?, help?, bugtracker?, donation?, source?}, keywords:[],
  languages:{ar?:pct}, requires:{memory?, display_length?, internet?, controls:[]},
  verification:{method?, website?}, license, developer}`.
- `machine.json` — `moos-store-index --print-machine`: `{arch, engines, memory_bytes,
  cpu_cores, gpu:{vendor, name, discrete}, session, free_bytes:{apps}, android:{ready,
  initialized, graphics:"hardware"|"software"}, windows:{ready, x86_32}, screen:{width, height,
  scale}}`. File reads only; free space from the filesystem under `~/.local/share` (never `/`).
- `facts.json` — `moos-storectl facts` (read-only, no lock; the launcher starts it in the
  background): from the cached Flathub summary, `{schema:1, generated_at, apps:{<id>:{download,
  installed, eol, permissions:[keys], x11_only, extra_data}}}`.
- `permissions/<id>.json` — `moos-storectl permissions <id>`: `{schema:1, id, kind, sandboxed,
  rows:[{key, state:"allow"|"deny", changeable}], note_key?}`. Flatpak keys: `network`,
  `files-home`, `files-all`, `downloads`, `devices`, `sound`, `bluetooth`, `background`. Web
  apps: their catalogue permission names. Unsandboxed kinds: `sandboxed:false`, no rows,
  `note_key:"full_access"`.
- `job.json` — unchanged schema. New message keys always arrive with their UI phrase in the same
  change (`tests/test_store_job_language.py` is two-way). A refusal before a job starts (bad id,
  busy) is still published as a terminal job document so the window can say why.
- `updates.json` — items may be `{id, kind:"pin", name, version, installed_version}` for catalogue
  pins newer than what is installed.

Compatibility reason keys: `arch`, `engine_missing`, `android_setup`,
`android_software_graphics`, `low_disk`, `low_memory`, `small_screen`, `needs_internet`,
`x11_only_scaled`, `eol`, `broad_permissions`, `vendor_download`, `not_verified`.

## StoreBridge

Existing invokables keep their names and argv. Added (ids through `validId`, keys and values
through fixed lists in C++ and again in `moos-storectl`):

| QML | argv |
|---|---|
| `removeAppData(id)` | `moos-storectl remove --delete-data <id>` |
| `updateApp(id)` | `moos-storectl update <id>` |
| `appPermissions(id)` | `moos-storectl permissions <id>` |
| `setPermission(id, key, value)` | `moos-storectl set-permission <id> <key> <allow\|deny\|reset>` |
| `setAutoUpdates(on)` | `moos-storectl auto-updates <on\|off>` |

`installApps`, `removeApp` and `runApp` accept every catalogue kind by id.

## Entry points

- `moos-store [--app=<id> | appstream://<id>]` → the window receives `--open-app=<id>` in its
  arguments at start, and through `activateRequested(arguments)` when it is already running,
  and opens that app's page. Mo Store is the `x-scheme-handler/appstream` handler, so Plasma's
  "Uninstall or Manage Add-ons…" opens the app's page here.
- MoOS Search: `/usr/libexec/moos-store-krunner` (D-Bus runner `org.moos.StoreRunner`) offers
  apps that are not installed yet and opens their page; it never installs.
- `moos-webapp <id>` draws a web app (`usr/lib/moos/moos_webapp_policy.py` holds every rule).
