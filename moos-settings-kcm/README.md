# MoOS in System Settings — the `kcm_moos*` family

MoOS's own pages are native System Settings modules (KCMs). They sit in the
**MoOS** group, first in the sidebar
(`system_files/usr/share/systemsettings/categories/settings-moos.desktop`,
`X-KDE-System-Settings-Category=moos`, weight 5). There is no second settings
window.

| Module | Directory | Weight | What it shows |
|---|---|---|---|
| `kcm_moos` | `modules/overview` | 1 | MoOS hero card, at a glance, System and This device facts, Copy details |
| `kcm_moos_update` | `modules/update` | 2 | System, Applications and Device firmware rows, each from its owner's record |
| `kcm_moos_whatsnew` | `modules/whatsnew` | 3 | What each update brought, fresh marker, "Try it" routes |
| `kcm_moos_ai` | `modules/ai` | 4 | Mo AI (slice B) |
| `kcm_moos_remote` | `modules/remote` | 5 | Mo PC Remote on/off/restart, Fast Remote, open the app |
| `kcm_moos_recovery` | `modules/recovery` | 6 | Saved images, queued rollback and its target |
| `kcm_moos_appearance` | `modules/appearance` | 1 in *appearance* | MoOS Themes: the 16 looks with their previews, apply and undo, the desktop canvas image, glass clarity, wallpaper motion, and the native pages for fine control |

`moos-settings --section=<s>` maps a section to one of these ids and runs
`systemsettings <id>`; a running System Settings receives the id itself.

## Adding a module

Add one directory and nothing else — `CMakeLists.txt` builds every directory
under `modules/`:

```
modules/<name>/<plugin id>.json   KPlugin Name/Name[ar], Description/Description[ar], Icon,
                                  X-KDE-System-Settings-Parent-Category, X-KDE-Weight,
                                  X-KDE-Keywords, X-KDE-Keywords[ar]
modules/<name>/ui/main.qml        root: KCM.SimpleKCM (it scrolls)
modules/<name>/ui/*.qml           optional: more files, same qrc directory
```

The plugin id must be `kcm_moos` or `kcm_moos_<word>`. The shared QML in
`common/` is placed in the same qrc directory (`/kcm/<plugin id>/`), so a page
uses it by plain type name. A module file may not reuse a `common/` file name.
The build writes `/usr/share/moos/settings-modules.list`; the image build loads
every module named there offscreen and fails on an early exit or a QML error.

## The page contract

* `import org.moos.ui as MoUI`; words through `t(ar, en)` keyed on
  `MoUI.Locale.rtl`; `LayoutMirroring.enabled: rtl` with `childrenInherit`.
* Secondary text is the text colour at alpha **0.72** —
  `Qt.rgba(Kirigami.Theme.textColor.r, …g, …b, 0.72)` — never
  `disabledTextColor`. The stock FormCard delegates paint their descriptions
  with the disabled role, so pages use the `common/` rows below, which do not;
  `tests/test_secondary_text_contrast.py` refuses the stock ones in a page.
* Read status groups straight from the backend with a fallback
  (`kcm.status.deployment || ({})`), show a fact only when `kcm.statusValid`,
  and let a missing value read "Unknown" (MoosFactRow does).
* Bind identity values as the helper normalised them: `kernelLabel`,
  `editionLabel`, `archLabel`, `sessionLabel` — never `kernel` or `edition`.
* Every button opens a fixed `moos://` route through `kcm.openRoute()` and
  shows an inline error (MoosRouteNotice) when it returns false.
* Motion only through MoUI components, gated on `Kirigami.Units.longDuration`;
  no infinite animation.

### Shared QML (`common/`)

| Type | Use |
|---|---|
| `MoosHero` | the Liquid Glass hero card: `logoSource`, `title`, `subtitle`, `chips: [...]`, `actions: [...]` |
| `MoosChip` | a status chip: `glyph`, `label`, `tone` (`positive`, `warning`, `negative`, `neutral`) |
| `MoosFactRow` | `label` + `value`; empty value reads "Unknown"; `technical` isolates LTR names |
| `MoosInfoRow` | a state sentence: `glyph`, `text`, `description`, `trailing: [...]` |
| `MoosActionRow` | a native button row with a MoOS glyph and readable description |
| `MoosSwitchRow` | a switch showing the MEASURED state `on`; emits `requested(wanted)` |
| `MoosStatusNotice` | reading / unavailable notice with Try again; `backend: kcm` |
| `MoosRouteNotice` | inline error for a route that could not be opened; `message` |
| `MoosNote` | a paragraph in secondary ink |
| `MoosKeyCap` | one key of a shortcut |

Glyph names come from `MoUI.SymbolCatalog` (`tests/test_moos_symbolic_icons.py`
refuses a name the catalogue does not have).

## The backend API (`kcm`, the same class in every module)

Implemented once in `src/moosbackend.{h,cpp}` and compiled into every plugin.

| Member | Kind | Contract |
|---|---|---|
| `status` | `QVariantMap` property | the last **accepted** status document; `{}` when none |
| `statusValid` | `bool` property | an accepted document is loaded |
| `statusError` | `string` property | `""` or `no-runtime`, `unreadable`, `invalid`, `stale`, `helper` |
| `statusGeneratedAt` | `int` property | the accepted document's `generatedAt` |
| `loading` | `bool` property | the status helper is running |
| `logoSource` | `url` property | `/usr/share/moos/moos-logo.png` when present, else empty |
| `refresh()` | method | run `/usr/libexec/moos-settings-status` now (queued behind a running one) |
| `ensureFresh()` | method | refresh only when nothing valid newer than 15 s is shown; pages call it when shown |
| `openRoute(url)` | method → `bool` | open a plain `moos://…` route; anything else is refused with `false`. After a `moos://remote/…` or `moos://do/…` route it refreshes after 3 s and 10 s |
| `env(name)` | method → `string` | only `MOAI_AGENT_PORT`, `MOAI_CONTROL_PORT`, `MOAI_GATEWAY_PORT`, and only when the value is a port number; `""` otherwise |
| `runFixed(id, argument = "")` | method → `MoOSJob` or `null` | start one verb of the fixed list below; `null` for an unknown id or a rejected argument |
| `moosThemes()` | method → list | read-only: the installed MoOS looks for `kcm_moos_appearance`, one map per `/usr/share/plasma/look-and-feel/org.moos.ui2*` package whose id `theme-apply-lnf` accepts and whose `metadata.json` names it — `id`, `name`, `nameAr`, `summaryEn`, `summaryAr` (the package's "Arabic \| English" description), `preview` (`contents/previews/preview.png` as a file URL, else `fullscreenpreview.jpg`, else empty), `light`, `family`; the base family first, each dark look before its light sibling. Takes no argument and runs no process |
| `jobFinished(id, exitCode, output)` | signal | every job, when it ends |

`MoOSJob` properties: `id`, `argument`, `running`, `ok` (exit 0), `exitCode`
(−1 when it could not start, crashed or ran past 180 s), `output` (stdout,
first 64 KiB), `errorOutput`; signal `finished()`. The module owns the job; the
page keeps a reference if it wants to read it.

### Fixed verbs

Everything a page can start. Each argument is validated in C++ before a process
exists, and `moos-theme` validates it again.

| id | argv (`/usr/bin/moos-theme …`) | argument |
|---|---|---|
| `theme-status` | *(none)* | — |
| `theme-motion-status` | `motion` | — |
| `theme-clarity-status` | `clarity` | — |
| `theme-apply-lnf` | `apply-lnf <id>` | `^org\.moos\.ui2[a-z.]*$`, ≤ 64 chars |
| `theme-undo` | `undo` | — |
| `theme-motion` | `motion <m>` | `still`, `gentle`, `alive` |
| `theme-clarity` | `clarity <c>` | `clear`, `balanced`, `solid` |
| `theme-wallpaper-reset` | `wallpaper-reset` | — |
| `theme-wallpaper-token` | `wallpaper-token <t>` | `^[A-Za-z0-9_.~%-]{1,4096}$` |

There is no verb that takes a command, a path or a URL, and none escalates.
Privileged actions go through `moos://do/…` → `moai-do`; a new unprivileged
verb is added to `FixedVerbs` in `src/moosbackend.cpp`, to this table, and to
`tests/test_moos_settings.py`.

### The status document

`$XDG_RUNTIME_DIR/moos-settings/status.json`, written atomically (0600) by
`/usr/libexec/moos-settings-status`. The backend accepts it only when
`schema == 1`, `product == "MoOS"`, `generatedAt` is within −5…45 s of now, and
every field a page binds has its declared JSON type (`StatusShape` in
`src/moosbackend.cpp`; `tests/test_moos_settings.py` checks the helper against
that table). A rejected document is dropped whole.

Both image builds EXECUTE that contract before the modules enter the image: the
`kcm-contract` stage of `Containerfile` and `Containerfile.arm` runs
`tools/check_status_contract.py`, which runs the real helper and requires the
compiled C++ (`moos-settings-contract-check`, built with the modules and never
installed) to accept its document and to refuse, with the reason a page shows,
every broken copy — stale, future-dated, another schema or product, a label
without one language, a destination that is not a flag, and each `StatusShape`
field deleted in turn.

It re-reads the document when it changes on disk and re-runs the helper when a
source record changes (`/run/moos/update-state.json`,
`~/.local/state/moos/app-updates.json`, `~/.local/state/moos/fast-remote.on`,
and Mo PC Remote's enable link under
`~/.config/systemd/user/plasma-workspace.target.wants/`), when the module is
shown again, and on Refresh — never on a blind timer, and the helper publishes
once and exits.

## Build and check locally

```bash
cmake -S moos-settings-kcm -B /tmp/b -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr \
      -DMOOS_KCM_CONTRACT_CHECK=ON
cmake --build /tmp/b -j4
/tmp/b/bin/moos-settings-contract-check "$XDG_RUNTIME_DIR/moos-settings/status.json"
# the image builds' executed contract: the real helper, then every broken copy
python3 moos-settings-kcm/tools/check_status_contract.py /tmp/b/bin/moos-settings-contract-check \
        system_files/usr/libexec/moos-settings-status moos-settings-kcm/src/moosbackend.cpp
```

Load a module offscreen the way the image build does, in an isolated session
(never on the owner's desktop). The image gate uses a private bus where
`dbus-run-session` exists; the ARM image has none, and there it points
`DBUS_SESSION_BUS_ADDRESS` at a socket that does not exist — the pages need no bus:

```bash
dbus-run-session -- env -u DISPLAY -u WAYLAND_DISPLAY QT_QPA_PLATFORM=offscreen \
    HOME="$(mktemp -d)" XDG_RUNTIME_DIR="$(mktemp -d)" timeout 12 kcmshell6 kcm_moos_update
```

`kcmshell6` stays running (exit 124) even when the page failed to load, so the
image gate also fails on any `Error loading QML`, `is not a type`,
`ReferenceError`, `TypeError`, `Unable to assign` or "module … is not
installed" line.
