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
| `vendor` | `vendor-rpm` | `~/Applications/<id>/` (the payload of a publisher-signed RPM, never layered, no scriptlets) + `org.moos.vendor.<id>.desktop` + record `~/.local/share/moos/vendor/<id>.json` | the launcher | files MoOS wrote |
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
  search words each, e.g. PhotoCraft: `photoshop`, `psd`; `فوتوشوب`), `accent` ("#rrggbb"),
  `icon_url` (https, allowlisted publisher hosts only — the index uses it when there is no local
  icon; the window loads it only when the person allows app pictures from the internet).
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
  - `android`: unchanged (`url`, `sha256`, `package` = id) plus optional `version`, `size` and
    `signer` (SHA-256 of the APK's signing certificate; Android refuses an update from another
    signer, so the pin records it).
  - `vendor-rpm`: `{kind, repo ("https://…/$basearch", exact allowlist), package, key_fingerprint
    (40 hex; the key must already be trusted by the image), install_root, exec, desktop, icon?,
    wm_class, risk:"downloaded-executable", requires_review:true, external:true}`. The newest
    build is resolved from the publisher's repository metadata, its SHA-256 and size come from
    that metadata, `rpmkeys --checksig` must prove the trusted key signed it, and only the files
    under `install_root` are unpacked into the person's home. Today: the official ChatGPT desktop
    app (OpenAI key `3BFA0E4AE8B8CC16A2D9BA684A3B4A566C4660E4`).
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

## As built (2026-10-14) — additions to the contracts above

These are measured facts from the implementation, recorded so the next change starts from what
exists rather than from the plan.

- **Records.** App Drop: `~/.local/share/moos/appdrop/<slug>.json` (`catalog_id`, `version`,
  `url`, `sha256`, `desktop_id`, `launcher`; no `catalog_id` = kind `dropped`, removed by its
  `slug`). Windows: `~/.local/share/moos/windows-apps/<id>.json` with the program under
  `<id>/app` and its own prefix under `<id>/prefix`. Android: `~/.local/share/moos/android/<package>.json`.
  Vendor: `~/.local/share/moos/vendor/<id>.json`. Web apps: the launcher's `X-MoOS-WebApp=<id>`.
  An update is available when a record's SHA-256 differs from the pin for the running arch.
- **Downloads** are named by their magic bytes, not the URL, and land in
  `~/.cache/moos-store/downloads/` only when that lies inside HOME (else `~/.cache/…`).
- **Windows programs** run headless while being prepared (`timeout … env -i`, no display, no
  bus, both graphics drivers disabled); 32-bit programs are refused (`windows_legacy_program`).
  A plain `remove` already deletes the prefix; `--delete-data` only changes the message.
  `wm_class` defaults to the lowercase exe file name until measured per program.
- **Permission documents** add `generated_at` and `installed`; web-app rows add `ask`
  (an unanswered permission reads `state:"deny", ask:true`); note keys are `full_access`,
  `android_managed` (Android apps are sandboxed in their container) and `not_installed`.
- **facts.json** adds top-level `state`/`message` and per-app `eol_rebase`; its permission
  words include `host-commands`.
- **updates.json** adds top-level `auto_updates`; pin rows count in `count` and `app_count`.
  `auto-updates on|off` is not a job (no lock, no job.json): read the state back with
  `check-updates`.
- **Refusals** before a job starts are written to job.json with a message key, but never over
  another request's live job (starting/running, updated in the last 120 s); `busy` carries
  `message_key:"busy"`.
- **index.json** adds `listed` (false for installed apps no listing covers — hide them from
  browse pages, keep them in My apps), `slug`/`catalog_id` on dropped apps, `needs`
  (compatibility inputs), `cat` (one of the 12 Store categories; the old `category` keeps its 14
  values), stats counters and the `--machine`/`--facts` options. `details` is a symlink to the
  current generation directory `details-<token>-<rand>`; a generation is complete only with its
  `.complete` marker. machine.json adds `swap_bytes`; `screen` falls back to the compositor's
  saved output configuration.
- **The window** keeps its state, data loading, timers, bridge calls, palette and job phrases in
  `main.qml`; every view is a file beside it that takes the window only as
  `required property var win` and reaches it as `win.<member>` (a cross-file id becomes a root
  member). `X { win: win }` written inside a view file is silently undefined.
  `activateRequested(arguments)` handles `--open-app`/`--open-page`.
- **Windows template.** One template prefix, `~/.local/share/moos/windows-apps/.template`
  (record `.template.json`: schema, wine version, density, created_at), is built headless once
  and rebuilt when `wine --version` changes; each program's prefix is a
  `cp -a --reflink=auto` copy with its own registry. Measured on the station's btrfs: 917.6 MB
  and 12.4 s once, then ~0.17 s and ~1.3 MiB of metadata per program (a full copy elsewhere:
  0.9 GB). Removing the last program removes the template. machine.json `windows` adds
  `reflink` and `template`, and the index's low-disk estimate follows them. The Windows
  runtime never writes menu entries or file associations (`winemenubuilder.exe=d` on every start).
- **Vendor kind.** Installed means record + MoOS-marked folder + MoOS's launcher; versions read
  `version-release`; `check-updates` asks the publisher (at most 45 s, no row when offline);
  an app the catalogue later drops stays openable and removable by id. Every module failure
  maps to a message key through `VENDOR_FAILURE_KEYS` (two-way gated with the window's phrases).
- **Opening by id.** `moos-storectl run <id>` opens any kind the Store installed; Mo AI's
  `open_app`, `moai-do install`'s launch and the `moos://apps/run/<id>` route fall back to it for
  every id that is not a Flatpak.
