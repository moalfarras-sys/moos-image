/* MoOS override of plasma-desktop's defaultPanel layout template — the
 * premium MoOS dock ("Nova").
 *
 * WHY THIS EXACT SHAPE (2026-07-10, after live testing):
 *   The v8 build shipped a SINGLE bottom panel via this template and it
 *   rendered correctly in the live session (dock with the Mo launcher, tasks,
 *   tray, clock all visible). The v9 attempt to split this into a top menu-bar
 *   + a floating "fit/center" island dock produced NO panels at all in the
 *   live session — a runtime failure in one of the exotic setters
 *   (lengthMode="fit" / alignment="center" / a second `new Panel`) aborts the
 *   whole layout script inside plasmashell, leaving zero panels. A desktop
 *   with no panel is broken, so MoOS ships the PROVEN single-panel dock and
 *   only keeps the changes that were verified working live (macOS-style
 *   left-side window buttons live in /etc/xdg/kwinrc, not here).
 *   The separate top menu-bar is a future enhancement to debug with real
 *   plasmashell console access, not a live-session guess.
 *
 * This is a file-level override of the plasma-desktop copy (rpm -V will report
 * it modified — intended, same policy as the fedora-logos pixmap overrides).
 *
 * Every call below is a verified primitive that the upstream template and the
 * proven v8 build already used: `new Panel`, panel.height, panel.addWidget,
 * widget.currentConfigGroup, widget.writeConfig. No location/floating/
 * lengthMode/alignment setters (those are exactly what failed live). Plasma 6
 * floats a bottom panel by default, which already gives the dock feel.
 */

var panel = new Panel;
panel.height = Math.round(gridUnit * 2.6);   // ~46px premium dock

/* App launcher wears the MoOS emblem instead of the KDE logo. */
var launcher = panel.addWidget("org.kde.plasma.kickoff");
launcher.currentConfigGroup = ["General"];
launcher.writeConfig("icon", "/usr/share/moos/moos-logo.png");

/* Icons-Only Task Manager — Mo AI pinned FIRST (the star), then browser,
 * files, the MoOS hubs, System Settings and the terminal. icontasks silently
 * skips any launcher URL it cannot resolve (no crash). */
var tasks = panel.addWidget("org.kde.plasma.icontasks");
tasks.currentConfigGroup = ["General"];
tasks.writeConfig("launchers", [
    "applications:org.moos.moai.desktop",
    "preferred://browser",
    "applications:org.kde.dolphin.desktop",
    "applications:org.moos.compathub.desktop",
    "applications:org.moos.hardware.desktop",
    "applications:systemsettings.desktop",
    "applications:org.kde.konsole.desktop"
].join(","));
tasks.writeConfig("showOnlyCurrentDesktop", false);

/* Right-hand cluster: push status items to the edge, then tray + clock. */
panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.kde.plasma.systemtray");
panel.addWidget("org.kde.plasma.digitalclock");
panel.addWidget("org.kde.plasma.showdesktop");

/* Wallpaper (NovaHorizon) ships via the org.moos.nova Look-and-Feel defaults,
 * exactly like the upstream template — this file only builds the panel. */
