# MoOS native panel center

The existing `org.kde.plasma.systemtray` containment owns this presentation.
Its C++ factory, models, applet configuration, StatusNotifier services, popup
container and notification server remain native. The clock/calendar stays its
existing owner. The center adds one panel entry rather than a second shell.

The owner rejected the clock experiment for clipping and duplicate tray icons,
then rejected the first wide two-column native center. The successor is a
narrow, Arabic-first composition: two connectivity cards with separate toggle
and details hit areas, one brightness/sound group, smaller status controls,
and a history page within the same popup. It uses the selected Plasma theme
and Kirigami roles, the existing MoOS motion durations, native keyboard/touch
controls, and reduced-motion cancellation. Native power and every accepted tray
item remain reachable. Camera and attention indications remain on the single
entry through their original native owners; this is not another camera monitor.

Design research, consulted 16–17 November 2026:

- [Apple Control Center](https://support.apple.com/en-ca/guide/mac-help/mchl50f94f8f/27/mac/27):
  a single entry, related controls grouped, and detail access. The cached official
  guide was available; direct requests returned429. No claim that its current
  full page or every current platform control was inspected.
- [Microsoft Quick Settings](https://support.microsoft.com/en-us/windows/experience/personalization/customize-the-taskbar-in-windows):
  frequent network/audio/brightness controls and a route to further settings.
  Its official Quick Settings reference image was inspected privately.
- [Google Pixel Quick Settings](https://support.google.com/pixelphone/answer/6111329?hl=en):
  distinct simple toggles and detailed actions, with touch navigation.
- [KDE theme roles](https://develop.kde.org/docs/getting-started/kirigami/style-colors/):
  use native palette roles rather than borrowing another platform's colours.

These references inform interaction hierarchy. No platform logo, artwork or
other OS presentation is shipped by this directory. KDE copyright/license
headers on the two changed native files remain intact.

`prepare_control_center.py` requires the exact reviewed upstream two files and
CMake parent before writing. The canonical workspace RPM compiles these seven
QML files; the full image still applies the original logout, package, identity,
signing and recovery checks. A scoped runtime plugin copy is development only.

Private input/geometry/theme tests must select `KirigamiPlasmaStyle` and assert
its actual `PlasmaTheme` owner and selected native surface/accent. A Qt
application palette alone previously produced misleading black symbols and
mixed accents; preserve that refusal. Source-font/private previews do not prove
physical touch, owner approval, native notification actions or a signed update.
