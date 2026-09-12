# Horizon status cluster — 2026-09-12 live proof

Captured on the installed NVIDIA MoOS desktop at 3840×2160 and 225% scale.
The branch package was temporarily placed in the user's Plasma package path,
QML caches were cleared, and the managed plasmashell service was restarted.
The override was removed after review.

- `before.png`: the tray sits outside a second clock-only capsule and the
  otherwise Arabic/English MoOS shell inherits German date abbreviations.
- `after.png`: time, date, hidden-items affordance and status glyphs share the
  Horizon Bar's one surface. The clock has a two-line MoOS rhythm, accent rail
  and day-progress line; the tray uses Plasma's supported compact spacing.
- `calendar-ar-after.png`: the full RTL calendar after live review found and
  fixed an upstream MonthView geometry race which initially showed October
  2037 below a September 2026 header. Its backend now settles on the actual day.

Runtime evidence: `moos-bar-apply check` returned `bar: ok`; the clock package
loaded under `plasmawindowed`, and the restarted shell logged no MoOS QML error.
