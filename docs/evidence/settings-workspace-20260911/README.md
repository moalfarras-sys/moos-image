# Settings workspace — native source evidence, 2026-09-11

These are actual Qt Quick renders of the repository QML using `moos-qml-shell`
and `tests/qml/settings-review.qml`; no desktop override was installed.
The before image uses Settings QML from `c0cc94e7`. The after images use the
candidate source. Read-only host state was refreshed before each capture;
hostname and network display name were redacted. This is not an image boot test.

| Capture | Palette | Locale | Size |
| --- | --- | --- | --- |
| [Before](before-dark.png) | MoOS UI Aurora | en_US | 1400×900 |
| [Workspace](after-dark.png) | MoOS UI Aurora | en_US | 1400×900 |
| [Arabic workspace](after-arabic.png) | MoOS UI Aurora | ar_SA / RTL | 1100×820 |
| [Compact light workspace](after-light.png) | MoOS UI Aurora Light | en_US | 900×700 |

The harness passed search typing/clearing, section navigation, and Enter
activation of all four cards. It asserted `app.rtl` for each after capture.
A full pass also rendered all sections and unavailable, empty-search and
missing-module states; the exported captures use `--home-only`.

Environment: `QT_QPA_PLATFORM=offscreen`, `QT_QPA_PLATFORMTHEME=kde`,
`QT_QUICK_BACKEND=software`, `QT_QUICK_CONTROLS_STYLE=Basic`, source
`QML_IMPORT_PATH=system_files/usr/lib64/qt6/qml` (absolute), source share directory
prepended to `XDG_DATA_DIRS`. An isolated `XDG_CONFIG_HOME/kdeglobals` used the
source palette, matching icon theme and `AnimationDurationFactor=0`.
Set `LANG`, `LC_ALL`, `LC_MESSAGES` **and `LANGUAGE`** for Arabic: inherited
`LANGUAGE=en` otherwise kept the review in English despite `LANG=ar_SA.UTF-8`.
Harness options: `--workspace --rtl=true|false --width=N --height=N
--out=ABSOLUTE_PATH --status=file:///REDACTED_STATUS.json`.

Resting surface separation uses `(299R + 587G + 114B)/1000`, at the same row:

| Image | Card pixel | Canvas pixel | Luminance difference |
| --- | --- | --- | --- |
| after-dark | (310,450), RGB 45,51,64 | (290,450), RGB 14,21,36 | 30.071 |
| after-light | (310,540), RGB 181,209,206 | (290,540), RGB 201,232,229 | 22.103 |

Both exceed the design plan's 15-step threshold. The light image demonstrates
that the sidebar scrolls and its bottom actions stay accessible in a short
window. It intentionally shows the main content continuing below the viewport.
Screen-reader behavior, 4K/225% physical output and every palette remain separate
acceptance items.
