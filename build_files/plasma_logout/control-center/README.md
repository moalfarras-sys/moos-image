# MoOS native panel center

The existing `org.kde.plasma.systemtray` containment owns this presentation.
Its C++ factory, models, applet configuration, StatusNotifier services, popup
container and notification server remain native. The clock/calendar stays its
existing owner. The center adds one panel entry rather than a second shell.

The owner rejected the clock experiment for clipping and duplicate tray icons,
then rejected the first wide two-column native center and its compact tabbed
successor. The current refinement is a narrow, Arabic-first composition: two connectivity cards with separate toggle
and details hit areas, one brightness/sound group, smaller status controls,
and notification history visible together in the same popup. Swiping the handle
up expands history; its button restores controls, and swiping down closes the
center. At short heights controls start collapsed and remain reachable. It uses the selected Plasma theme
and Kirigami roles, the existing MoOS motion durations, native keyboard/touch
controls, and reduced-motion cancellation. Native power and every accepted tray
item remain reachable. Camera and attention indications remain on the single
entry through their original native owners; this is not another camera monitor.

The existing fixed executor remains the sole measured-state/action authority.
Native audio, network, Bluetooth, notification, brightness and Night Light owners
invalidate its snapshot through one finite coalesced read while open. Pending
actions and active slider gestures defer that read; disabled, hidden or
closed-center cancellation restores measured slider state without sending it; closing unloads observers.
Automatic readback preserves a refused action. Connectivity names are native
plain text and quick controls keep visible state captions. Arabic text is checked
inside the buttons, including the original compact-footer clipping refusal.

Wi-Fi and bell silhouettes are corrected in the canonical symbolic generator,
with all paired palette copies and old/fixed native raster controls. A scoped
icon-only runtime prefix is separately inventoried for live review; source SVGs
do not establish that the installed shell selected their bytes.

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

The owner accepts the unified layout. Actual native notification delivery exposed
a floating duplicate above the open history. The existing notification applet
now accepts only the IDs published by that history model. Its original popup
delegates remain alive: native placement visibility is separate from temporary
presentation suppression, so expiry, sound and actions keep their original
owners. Popup-only notices and active reply/drag/menu interactions remain visible.
Three exact original native QML hashes are admitted before any write; both native
plugin digests are checked against their owning RPM. Real existing-server action
callback, hidden-window expiry and canonical Settings open/close were exercised.
Source font tests reserve56px for notification actions/replies after48px still
clipped Arabic ink. Content-only button press feedback never shrinks hit areas.

The revision 159 successor keeps connectivity outside two native folding cards. Sound and
display opens first; Focus and privacy exposes measured status on its header.
Only one body is enabled; pending/held input refuses switching and explicit
selection survives the popup cycle. Native pointer/keyboard/Qt-touch tests cover
closed-body Tab exclusion, all fold states and source Meyar narrow bounds. The
scoped live icon prefix now covers all 18 curated themes plus hicolor, with native
resolver/semantic raster proof and unchanged fallback icons. This development
prefix and the shell plugin still require signed immutable delivery.
