/* MoOS override of plasma-desktop's defaultPanel layout template — the premium
 * MoOS dock ("Nova").
 *
 * PROVEN-WORKING SINGLE PANEL (restored 2026-07-10 after v14 live test):
 *   The v8/v9.2/v11 single bottom panel rendered correctly in the live session
 *   (dock with Mo launcher, tasks, tray, clock all visible). BOTH two-panel
 *   attempts (v9 raw, v14 with per-panel try/catch) produced NO panels at all
 *   in the live session — so the top-bar + dock split is abandoned as
 *   unreliable in this layout-template context. A desktop with no panel is
 *   broken; MoOS ships the PROVEN single-panel dock. Plasma 6 floats a bottom
 *   panel by default, which already gives a macOS-like dock feel.
 *
 * Every call is a verified primitive the proven v8 dock used live: `new Panel`,
 * panel.height, panel.addWidget, widget.currentConfigGroup, widget.writeConfig.
 * No location/floating/lengthMode/alignment setters and no second panel (those
 * are what failed live).
 *
 * File-level override of the plasma-desktop copy (rpm -V reports it modified —
 * intended, same policy as the fedora-logos pixmap overrides).
 */

var panel = new Panel;
panel.height = Math.round(gridUnit * 2.6);   // ~46px premium dock

/* Float the dock off the screen edge.
 *
 * `floating` IS a real property of Plasma 6's scripting Panel — verified live on
 * this hardware before it was written here (`"floating" in panels()[0]` -> true,
 * and setting it visibly lifted the dock). It is the setter that turns the Nova
 * glass into a floating slab with a gap and rounded corners on all four sides,
 * instead of a bar welded to the bottom of the screen.
 *
 * Wrapped anyway. The header above is not paranoia: a throw inside this template
 * leaves the session with NO PANEL, which is a broken desktop. A flush dock is a
 * cosmetic regression; a missing dock is a bug report. If a future Plasma drops
 * the property, the catch keeps the dock. */
try { panel.floating = true; } catch (e) { /* keep the dock, lose the gap */ }

/* App launcher wears the MoOS emblem instead of the KDE logo. */
var launcher = panel.addWidget("org.kde.plasma.kickoff");
launcher.currentConfigGroup = ["General"];
launcher.writeConfig("icon", "/usr/share/moos/moos-logo.png");

/* Icons-Only Task Manager — Mo AI (robot icon) pinned FIRST, then browser,
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

/* Right-hand cluster: separator, system tray, clock.
 *
 * The clock puts the date BESIDE the time rather than stacked under it
 * (dateDisplayFormat: 0 = below, 1 = beside — checked on-device, not guessed).
 * Stacked, it renders as two cramped lines that dominate the right end of the
 * dock; beside, it is one calm line.
 *
 * No show-desktop button. It rendered as an empty bordered box at the end of the
 * dock — it reads as a broken widget, and a dock of this kind has no such button
 * anyway. Users who want it back: right-click the dock -> Add Widgets. */
panel.addWidget("org.kde.plasma.marginsseparator");
panel.addWidget("org.kde.plasma.systemtray");

var clock = panel.addWidget("org.kde.plasma.digitalclock");
clock.currentConfigGroup = ["Appearance"];
clock.writeConfig("showDate", true);
clock.writeConfig("dateDisplayFormat", 1);

/* Wallpaper (NovaHorizon) ships via the org.moos.nova Look-and-Feel defaults. */
